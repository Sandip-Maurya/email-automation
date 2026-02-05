"""FastAPI webhook server for Microsoft Graph change notifications."""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse

from src.config import (
    DEDUP_CONVERSATION_COOLDOWN_SECONDS,
    DEDUP_STORE_PATH,
    TARGET_SENDER,
    WEBHOOK_CLIENT_STATE,
)
from src.webhook.dedup_store import DedupStore
from src.webhook.models import ChangeNotificationBatch
from src.orchestrator import process_trigger, _maybe_await
from src.models.email import EmailThread, Email
from src.utils.logger import get_logger

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


async def _run_process_trigger(
    app: FastAPI,
    message_id: str,
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
    )
    app.state.background_tasks = set()
    app.state._deferred_subscription_task: asyncio.Task[None] | None = None

    if create_provider:
        import os
        from src.mail_provider.graph_real import GraphProvider

        tenant_id = os.environ.get("AZURE_TENANT_ID", "")
        client_id = os.environ.get("AZURE_CLIENT_ID", "")
        if tenant_id and client_id:
            logger.info("webhook.lifespan.creating_provider")
            provider = GraphProvider(tenant_id=tenant_id, client_id=client_id)
            app.state.provider = provider
            if subscription_config:
                notification_url = subscription_config.get("notification_url", "")
                client_state = subscription_config.get("client_state", "")
                expiration_minutes = subscription_config.get("expiration_minutes", 4000)
                if notification_url and client_state:
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
        else:
            app.state.provider = None
            logger.warning("webhook.lifespan.no_credentials")

    yield

    # Shutdown: cancel deferred subscription task and notification background tasks, then wait with timeout
    shutdown_timeout = 10.0
    all_tasks: list[asyncio.Task[Any]] = []

    deferred = getattr(app.state, "_deferred_subscription_task", None)
    if deferred is not None and not deferred.done():
        deferred.cancel()
        all_tasks.append(deferred)

    tasks = getattr(app.state, "background_tasks", None)
    if tasks:
        for t in list(tasks):
            t.cancel()
        all_tasks.extend(tasks)

    if all_tasks:
        try:
            await asyncio.wait_for(
                asyncio.gather(*all_tasks, return_exceptions=True),
                timeout=shutdown_timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "webhook.lifespan.shutdown_timeout",
                timeout=shutdown_timeout,
                pending=sum(1 for t in all_tasks if not t.done()),
            )
        except Exception as e:
            logger.debug("webhook.lifespan.shutdown_gather_error", error=str(e))


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
        )
        app.state.background_tasks = set()

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

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
        target_sender = (TARGET_SENDER or "").strip().lower()
        client_state = (WEBHOOK_CLIENT_STATE or "").strip()

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

            message_id = None
            if notification.resource_data:
                message_id = notification.resource_data.id
            if not message_id:
                logger.debug(
                    "webhook.notifications.no_resource_data",
                    change_type=notification.change_type,
                )
                continue

            if dedup is not None and await dedup.is_processing(message_id):
                logger.debug("webhook.notifications.dedup_in_flight", message_id=message_id)
                continue

            if dedup is not None and await dedup.has_triggered(message_id):
                logger.debug("webhook.notifications.skip_already_triggered", message_id=message_id)
                continue

            msg = await _maybe_await(provider.get_message(message_id))
            if not msg or not msg.from_ or not msg.from_.emailAddress:
                logger.debug("webhook.notifications.skip_no_from", message_id=message_id)
                continue

            if target_sender:
                sender_addr = (msg.from_.emailAddress.address or "").strip().lower()
                if sender_addr != target_sender:
                    logger.info(
                        "webhook.notifications.sender_filter",
                        message_id=message_id,
                        sender=sender_addr,
                        target=target_sender,
                    )
                    continue

            conversation_id = (msg.conversationId or "").strip()
            if dedup is not None and await dedup.has_recent_reply(conversation_id):
                logger.info(
                    "webhook.notifications.skip_conversation_cooldown",
                    message_id=message_id,
                    conversation_id=conversation_id,
                )
                continue

            if dedup is not None and not await dedup.mark_triggered(message_id):
                logger.debug("webhook.notifications.skip_race_triggered", message_id=message_id)
                continue

            logger.info("webhook.notifications.trigger", message_id=message_id)
            task = asyncio.create_task(_run_process_trigger(app, message_id))
            app.state.background_tasks.add(task)
            task.add_done_callback(lambda t, a=app: a.state.background_tasks.discard(t))

        return Response(status_code=202, content='{"status":"accepted"}', media_type="application/json")

    return app
