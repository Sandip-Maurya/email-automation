"""FastAPI webhook server for Microsoft Graph change notifications."""

import asyncio
import re
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from src.config import (
    DEDUP_CONVERSATION_COOLDOWN_SECONDS,
    DEDUP_STORE_PATH,
    WEBHOOK_CLIENT_STATE,
    WEBHOOK_QUEUE_MAX,
    WEBHOOK_WORKER_COUNT,
    WEBHOOK_FETCH_BASE_DELAY,
    WEBHOOK_FETCH_MAX_ATTEMPTS,
    WEBHOOK_FAILED_MSG_TTL_SECONDS,
)
from src.webhook.filter_config import (
    is_valid_email,
    load_allowed_senders,
    save_allowed_senders,
)
from src.webhook.dedup_store import DedupStore
from src.webhook.models import ChangeNotificationBatch, ChangeNotification
from src.orchestrator import process_trigger, _maybe_await
from src.models.email import EmailThread, Email
from src.utils.logger import get_logger
from src.webhook.config_routes import router as config_router

logger = get_logger("email_automation.webhook.server")

# Placeholder thread for process_trigger (it fetches by message_id and replaces this)
_PLACEHOLDER_EMAIL = Email(
    id="",
    sender="",
    subject="",
    body="",
    timestamp=datetime.now(timezone.utc),
)
_PLACEHOLDER_THREAD = EmailThread(thread_id="", emails=[], latest_email=_PLACEHOLDER_EMAIL)


# Case-insensitive match for resource path: optional users/{id}/ then messages/{message_id}
_RESOURCE_PATTERN = re.compile(
    r"(?i)(?:users/([^/]+)/)?messages/([^?#]+)",
)


def _parse_notification_resource(notification: ChangeNotification) -> tuple[str | None, str | None]:
    """Parse notification.resource (and fallback resourceData.id) per Microsoft Graph docs.

    resource is the relative URI of the changed resource (e.g. Users/{id}/Messages/{id} or me/Messages/{id}).
    Returns (message_id, user_id); user_id is None for /me path so caller uses signed-in user.
    Uses case-insensitive matching for Graph API path segments.
    """
    resource = (notification.resource or "").strip()
    resource_data = notification.resource_data

    if resource:
        m = _RESOURCE_PATTERN.search(resource)
        if m:
            user_id_from_path = (m.group(1) or "").strip() or None
            message_id = (m.group(2) or "").strip()
            if message_id:
                logger.debug(
                    "webhook.notifications.resource_parsed",
                    resource=resource,
                    message_id=message_id,
                    user_id=user_id_from_path,
                )
                return (message_id, user_id_from_path)

    if resource_data and resource_data.id:
        raw_id = (resource_data.id or "").strip()
        m = _RESOURCE_PATTERN.search(raw_id)
        if m:
            message_id = (m.group(2) or "").strip()
            if message_id:
                logger.debug(
                    "webhook.notifications.resource_parsed",
                    raw_resource_data_id=raw_id,
                    message_id=message_id,
                    user_id=None,
                )
                return (message_id, None)
        logger.debug(
            "webhook.notifications.resource_parsed",
            raw_resource_data_id=raw_id,
            message_id=raw_id,
            user_id=None,
        )
        return (raw_id, None)

    return (None, None)


async def _run_process_trigger(
    app: FastAPI,
    message_id: str,
    user_id: str | None = None,
) -> None:
    """Run process_trigger in background; update dedup store (processing + conversation replied)."""
    dedup: DedupStore | None = getattr(app.state, "dedup_store", None)
    if dedup is not None:
        await dedup.add_processing(message_id)
    try:
        provider = getattr(app.state, "provider", None)
        if not provider:
            logger.error("webhook.background.no_provider", message_id=message_id)
            return
        result = await process_trigger(
            _PLACEHOLDER_THREAD,
            provider=provider,
            message_id=message_id,
            conversation_id=None,
            user_id=user_id,
        )
        if result.raw_data.get("sent_message_id") and dedup is not None and result.thread_id:
            await dedup.mark_replied(result.thread_id)
            logger.debug("webhook.dedup.mark_replied", conversation_id=result.thread_id)
    except ValueError as e:
        if "Message not found:" in str(e):
            logger.warning(
                "webhook.notifications.message_not_found",
                message_id=message_id,
                error=str(e),
            )
        else:
            logger.exception(
                "webhook.notifications.process_error",
                message_id=message_id,
                error=str(e),
            )
    except Exception as e:
        logger.exception(
            "webhook.notifications.process_error",
            message_id=message_id,
            error=str(e),
        )
    finally:
        if dedup is not None:
            await dedup.remove_processing(message_id)


async def _process_notification_message(
    app: FastAPI,
    message_id: str,
    user_id: str | None = None,
) -> None:
    """Process a single candidate: get_message (with optional user_id), apply filters, then run process_trigger.
    Used by the queue worker pool; concurrency is bounded by worker count.
    Skips immediately if this message_id already failed or is being processed by another worker.
    """
    provider = getattr(app.state, "provider", None)
    if not provider:
        return
    dedup: DedupStore | None = getattr(app.state, "dedup_store", None)
    allowed_senders: list[str] = getattr(app.state, "allowed_senders", [])

    # Skip duplicates: same message_id may be enqueued many times from notification bursts.
    if dedup is not None:
        if await dedup.has_failed(message_id):
            logger.debug("webhook.notifications.skip_already_failed_worker", message_id=message_id)
            return
        if await dedup.is_processing(message_id):
            logger.debug("webhook.notifications.skip_in_progress_worker", message_id=message_id)
            return
        await dedup.add_processing(message_id)
    try:
        msg = None
        # Retry loop for Graph eventual consistency (message not yet replicated). Distinct from
        # network-level retries inside provider.get_message().
        for attempt in range(WEBHOOK_FETCH_MAX_ATTEMPTS):
            msg = await _maybe_await(provider.get_message(message_id, user_id=user_id))
            if msg is not None:
                break
            if attempt < WEBHOOK_FETCH_MAX_ATTEMPTS - 1:
                delay = WEBHOOK_FETCH_BASE_DELAY * (2**attempt)
                logger.debug(
                    "webhook.notifications.get_message_retry",
                    message_id=message_id,
                    attempt=attempt + 1,
                    delay=delay,
                )
                await asyncio.sleep(delay)
        if not msg or not msg.from_ or not msg.from_.emailAddress:
            if msg is None:
                if dedup is not None:
                    await dedup.mark_failed(message_id)
                logger.warning(
                    "webhook.notifications.message_not_found_after_retry",
                    message_id=message_id,
                    user_id=user_id,
                )
            else:
                logger.debug("webhook.notifications.skip_no_from", message_id=message_id)
            return
        sender_addr = (msg.from_.emailAddress.address or "").strip().lower()
        if not allowed_senders:
            logger.info(
                "webhook.notifications.sender_filter",
                message_id=message_id,
                sender=sender_addr,
                reason="no_allowed_senders_configured",
            )
            return
        if sender_addr not in allowed_senders:
            logger.info(
                "webhook.notifications.sender_filter",
                message_id=message_id,
                sender=sender_addr,
                target_list=allowed_senders,
            )
            return
        conversation_id = (msg.conversationId or "").strip()
        if dedup is not None and await dedup.has_recent_reply(conversation_id):
            logger.info(
                "webhook.notifications.skip_conversation_cooldown",
                message_id=message_id,
                conversation_id=conversation_id,
            )
            return
        if dedup is not None and not await dedup.mark_triggered(message_id):
            logger.debug("webhook.notifications.skip_race_triggered", message_id=message_id)
            return
        logger.info("webhook.notifications.trigger", message_id=message_id)
        await _run_process_trigger(app, message_id, user_id=user_id)
    except Exception as e:
        logger.exception(
            "webhook.notifications.batch_process_error",
            message_id=message_id,
            error=str(e),
        )
    finally:
        if dedup is not None:
            await dedup.remove_processing(message_id)


async def _notification_worker(app: FastAPI, worker_id: int) -> None:
    """Worker loop: get (message_id, user_id) from queue, process one message. Stops on CancelledError."""
    queue: asyncio.Queue[tuple[str, str | None]] = app.state.notification_queue
    logger.info("webhook.worker.started", worker_id=worker_id)
    try:
        while True:
            message_id, user_id = await queue.get()
            try:
                await _process_notification_message(app, message_id, user_id)
            finally:
                queue.task_done()
    except asyncio.CancelledError:
        logger.info("webhook.worker.stopped", worker_id=worker_id)
        raise


def _setup_workers(app: FastAPI) -> None:
    """Create bounded queue and worker pool for notification processing."""
    app.state.notification_queue = asyncio.Queue(maxsize=WEBHOOK_QUEUE_MAX)
    worker_count = max(1, min(WEBHOOK_WORKER_COUNT, 64))
    app.state._worker_tasks = [
        asyncio.create_task(_notification_worker(app, i)) for i in range(worker_count)
    ]
    logger.info(
        "webhook.lifespan.queue_started",
        queue_max=WEBHOOK_QUEUE_MAX,
        worker_count=worker_count,
    )


def _setup_provider(
    app: FastAPI,
    subscription_config: dict[str, Any] | None,
) -> None:
    """Create GraphProvider and set app.state.provider; optionally schedule deferred subscription creation."""
    import os
    from src.mail_provider.graph_real import GraphProvider

    tenant_id = os.environ.get("AZURE_TENANT_ID", "")
    client_id = os.environ.get("AZURE_CLIENT_ID", "")
    if not tenant_id or not client_id:
        app.state.provider = None
        logger.warning("webhook.lifespan.no_credentials")
        return
    logger.info("webhook.lifespan.creating_provider")
    graph_http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(30.0),
        limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
    )
    provider = GraphProvider(
        tenant_id=tenant_id,
        client_id=client_id,
        http_client=graph_http_client,
    )
    app.state.provider = provider
    app.state._graph_http_client = graph_http_client
    if not subscription_config:
        return
    notification_url = subscription_config.get("notification_url", "")
    client_state = subscription_config.get("client_state", "")
    expiration_minutes = subscription_config.get("expiration_minutes", 4000)
    if not notification_url or not client_state:
        return

    async def _deferred_create_subscription() -> None:
        await asyncio.sleep(3)
        try:
            sub = await provider.create_subscription(
                notification_url=notification_url,
                client_state=client_state,
                expiration_minutes=expiration_minutes,
            )
            if sub and sub.id:
                logger.info("webhook.lifespan.subscription_created", subscription_id=sub.id)
            else:
                logger.warning("webhook.lifespan.subscription_failed")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.exception("webhook.lifespan.subscription_error", error=str(e))

    app.state._deferred_subscription_task = asyncio.create_task(_deferred_create_subscription())


async def _shutdown_tasks(app: FastAPI) -> None:
    """Cancel workers and other tasks, close Graph HTTP client, then wait for tasks to finish."""
    shutdown_timeout = 10.0
    all_tasks: list[asyncio.Task[Any]] = []

    worker_tasks = getattr(app.state, "_worker_tasks", None)
    if worker_tasks:
        for t in worker_tasks:
            t.cancel()
        all_tasks.extend(worker_tasks)

    deferred = getattr(app.state, "_deferred_subscription_task", None)
    if deferred is not None and not deferred.done():
        deferred.cancel()
        all_tasks.append(deferred)

    tasks = getattr(app.state, "background_tasks", None)
    if tasks:
        for t in list(tasks):
            t.cancel()
        all_tasks.extend(tasks)

    graph_client = getattr(app.state, "_graph_http_client", None)
    if graph_client is not None:
        try:
            await graph_client.aclose()
        except Exception as e:
            logger.debug("webhook.lifespan.graph_client_close_error", error=str(e))
        app.state._graph_http_client = None

    if all_tasks:
        try:
            await asyncio.wait_for(
                asyncio.gather(*all_tasks, return_exceptions=True),
                timeout=shutdown_timeout,
            )
        except asyncio.TimeoutError:
            pending = sum(1 for t in all_tasks if not t.done())
            logger.warning(
                "webhook.lifespan.shutdown_timeout",
                timeout=shutdown_timeout,
                pending=pending,
            )
        except Exception as e:
            logger.debug("webhook.lifespan.shutdown_gather_error", error=str(e))


@asynccontextmanager
async def _lifespan(
    app: FastAPI,
    subscription_config: dict[str, Any] | None = None,
    create_provider: bool = True,
):
    """Create provider (and optionally subscription) in the server's event loop when create_provider is True."""
    app.state.dedup_store = DedupStore(
        store_path=DEDUP_STORE_PATH,
        conversation_cooldown_seconds=DEDUP_CONVERSATION_COOLDOWN_SECONDS,
        failed_message_ttl_seconds=WEBHOOK_FAILED_MSG_TTL_SECONDS,
    )
    app.state.background_tasks = set()
    app.state._deferred_subscription_task = None
    app.state.allowed_senders = load_allowed_senders()

    _setup_workers(app)

    if create_provider:
        _setup_provider(app, subscription_config)

    yield

    await _shutdown_tasks(app)


def create_app(
    provider: Any = None,
    subscription_config: dict[str, Any] | None = None,
) -> FastAPI:
    """
    Create FastAPI app. If provider is passed (legacy), use it and do not create in lifespan.
    Otherwise the lifespan creates the provider in the server's event loop.
    subscription_config: when set and create_provider, lifespan also creates the Graph subscription.
    """
    create_provider_in_lifespan = provider is None
    app = FastAPI(
        title="Email Automation Webhook",
        version="0.1.0",
        lifespan=lambda app: _lifespan(
            app,
            subscription_config=subscription_config,
            create_provider=create_provider_in_lifespan,
        ),
    )
    if provider is not None:
        app.state.provider = provider
        app.state.dedup_store = DedupStore(
            store_path=DEDUP_STORE_PATH,
            conversation_cooldown_seconds=DEDUP_CONVERSATION_COOLDOWN_SECONDS,
            failed_message_ttl_seconds=WEBHOOK_FAILED_MSG_TTL_SECONDS,
        )
        app.state.background_tasks = set()
        app.state.allowed_senders = load_allowed_senders()

    app.include_router(config_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    # --- Allowed senders filter config API ---
    class AllowedSenderBody(BaseModel):
        email: str

    @app.get("/webhook/allowed-senders")
    async def list_allowed_senders(q: str | None = None) -> dict[str, list[str]]:
        """List allowed sender emails. Optional ?q= for case-insensitive substring filter."""
        senders: list[str] = getattr(app.state, "allowed_senders", [])
        if q is not None and q.strip():
            qn = q.strip().lower()
            senders = [s for s in senders if qn in s]
        return {"allowed_senders": senders}

    @app.post("/webhook/allowed-senders/reload")
    async def reload_allowed_senders() -> dict[str, list[str]]:
        """Reload allowed_senders from config file and return the new list."""
        app.state.allowed_senders = load_allowed_senders()
        return {"allowed_senders": list(app.state.allowed_senders)}

    @app.post("/webhook/allowed-senders")
    async def append_allowed_sender(body: AllowedSenderBody) -> dict[str, list[str] | str]:
        """Append an email to allowed senders. Validates format; persists to config and refreshes in-memory list."""
        email = (body.email or "").strip()
        if not email:
            raise HTTPException(status_code=400, detail="email is required and must be non-empty")
        if not is_valid_email(email):
            raise HTTPException(status_code=400, detail=f"Invalid email format: {body.email!r}")
        normalized = email.lower()
        current: list[str] = list(getattr(app.state, "allowed_senders", []))
        if normalized in current:
            return {"allowed_senders": current, "message": "already present"}
        current.append(normalized)
        try:
            save_allowed_senders(current)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        app.state.allowed_senders = current
        return {"allowed_senders": current, "added": normalized}

    @app.delete("/webhook/allowed-senders")
    async def delete_allowed_sender(
        request: Request,
        email: str | None = None,
    ) -> dict[str, list[str] | str]:
        """Remove an email from allowed senders. Pass ?email=... or body {\"email\": \"...\"}. Persists and refreshes."""
        if email is None or not (email := email.strip()):
            try:
                body = await request.json()
                if isinstance(body, dict) and body.get("email"):
                    email = str(body["email"]).strip()
            except Exception:
                pass
        if not email:
            raise HTTPException(status_code=400, detail="email is required (query ?email=... or body {\"email\": \"...\"})")
        normalized = email.lower()
        current: list[str] = list(getattr(app.state, "allowed_senders", []))
        if normalized not in current:
            raise HTTPException(status_code=404, detail=f"Email not in allowed list: {normalized!r}")
        current = [s for s in current if s != normalized]
        try:
            save_allowed_senders(current)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        app.state.allowed_senders = current
        return {"allowed_senders": current, "removed": normalized}

    @app.api_route("/webhook/notifications", methods=["GET", "POST"], response_model=None)
    async def notifications(request: Request) -> Response | dict[str, str]:
        # Subscription validation: Microsoft sends validationToken as query param
        validation_token = request.query_params.get("validationToken")
        if validation_token:
            return PlainTextResponse(
                content=validation_token,
                status_code=200,
                media_type="text/plain",
            )

        # Change notification: POST body with value[] of changeNotification
        try:
            body = await request.json()
            batch = ChangeNotificationBatch.model_validate(body if isinstance(body, dict) else {"value": []})
        except Exception as e:
            logger.warning("webhook.notifications.parse_error", error=str(e))
            return Response(status_code=202, content='{"status":"accepted"}', media_type="application/json")

        if not batch.value:
            logger.warning("webhook.notifications.empty_batch")
            return Response(status_code=202, content='{"status":"accepted"}', media_type="application/json")

        app = request.app
        provider = getattr(app.state, "provider", None)
        if not provider:
            logger.error("webhook.notifications.no_provider")
            return Response(status_code=503, content="Provider not configured")

        dedup: DedupStore | None = getattr(app.state, "dedup_store", None)
        client_state = (WEBHOOK_CLIENT_STATE or "").strip()

        # Fast path: parse resource (and fallback resourceData.id) per Graph docs; collect (message_id, user_id).
        candidates: list[tuple[str, str | None]] = []
        for notification in batch.value:
            if client_state and notification.client_state != client_state:
                logger.warning(
                    "webhook.notifications.client_state_mismatch",
                    subscription_id=notification.subscription_id,
                )
                continue
            if notification.change_type != "created":
                logger.debug(
                    "webhook.notifications.skip_change_type",
                    change_type=notification.change_type,
                    message_id=notification.resource_data.id if notification.resource_data else None,
                )
                continue
            message_id, user_id = _parse_notification_resource(notification)
            if not message_id:
                logger.debug(
                    "webhook.notifications.no_resource_data",
                    change_type=notification.change_type,
                    resource=notification.resource,
                )
                continue
            if dedup is not None and await dedup.is_processing(message_id):
                logger.debug("webhook.notifications.dedup_in_flight", message_id=message_id)
                continue
            if dedup is not None and await dedup.has_failed(message_id):
                logger.debug("webhook.notifications.skip_already_failed", message_id=message_id)
                continue
            if dedup is not None and await dedup.has_triggered(message_id):
                logger.debug("webhook.notifications.skip_already_triggered", message_id=message_id)
                continue
            candidates.append((message_id, user_id))

        # Enqueue candidates for worker pool; backpressure if queue full
        queue = getattr(app.state, "notification_queue", None)
        if queue is not None and candidates:
            enqueued = 0
            for item in candidates:
                await queue.put(item)
                enqueued += 1
            qsize = queue.qsize()
            logger.info(
                "webhook.notifications.enqueued",
                enqueued=enqueued,
                queue_size=qsize,
                queue_max=WEBHOOK_QUEUE_MAX,
            )

        return Response(status_code=202, content='{"status":"accepted"}', media_type="application/json")

    return app
