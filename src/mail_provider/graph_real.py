"""Real Microsoft Graph API mail provider (async)."""

import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from msgraph import GraphServiceClient, GraphRequestAdapter
from msgraph.generated.models.subscription import Subscription as GraphSubscription

if TYPE_CHECKING:
    import httpx
from kiota_authentication_azure.azure_identity_authentication_provider import (
    AzureIdentityAuthenticationProvider,
)

from src.auth.token_cache import get_persistent_device_code_credential
from msgraph.generated.models.message import Message as GraphSDKMessage
from msgraph.generated.models.item_body import ItemBody as GraphSDKItemBody
from msgraph.generated.models.body_type import BodyType
from msgraph.generated.models.recipient import Recipient as GraphSDKRecipient
from msgraph.generated.models.email_address import EmailAddress as GraphSDKEmailAddress
from msgraph.generated.users.item.send_mail.send_mail_post_request_body import (
    SendMailPostRequestBody,
)
from msgraph.generated.users.item.messages.messages_request_builder import (
    MessagesRequestBuilder,
)

from src.mail_provider.graph_models import (
    GraphMessage,
    SendPayload,
    Recipient,
    EmailAddress,
    ItemBody,
)
from src.utils.logger import get_logger, log_agent_step

logger = get_logger("email_automation.graph_provider")

# Prefer header for immutable message IDs (draft id = sent id when item moves to Sent)
PREFER_IMMUTABLE_ID = "IdType=\"ImmutableId\""

# Delegated scopes (same as verify_graph_credentials.py); need Mail.Send for sending
DELEGATED_SCOPES = [
    "https://graph.microsoft.com/Mail.Read",
    "https://graph.microsoft.com/Mail.Send",
]


def _is_transient_network_error(e: Exception) -> bool:
    """True if the exception is a transient I/O/network error worth retrying.

    Includes: WriteError, ConnectionResetError, LocalProtocolError (e.g. SEND_HEADERS on
    closed connection from httpx/httpcore), httpx/httpcore timeout exceptions, and WinError 10054.
    """
    try:
        import httpx
        if isinstance(e, httpx.TimeoutException):
            return True
    except ImportError:
        pass
    name = type(e).__name__
    if name in (
        "ReadError",
        "WriteError",
        "ConnectionResetError",
        "ConnectionError",
        "TimeoutError",
        "LocalProtocolError",
        "RemoteProtocolError",
        "ConnectTimeout",
        "ReadTimeout",
        "WriteTimeout",
        "PoolTimeout",
    ):
        return True
    if isinstance(e, OSError) and getattr(e, "winerror", None) == 10054:
        return True
    return False


def _is_throttle_error(e: Exception) -> bool:
    """True if the exception is a Graph 429 / throttling error (ApplicationThrottled, MailboxConcurrency)."""
    err_str = str(e).strip() or repr(e)
    return (
        "429" in err_str
        or "ApplicationThrottled" in err_str
        or "MailboxConcurrency" in err_str
    )


def _throttle_retry_delay_seconds(attempt: int) -> float:
    """Delay in seconds before retrying after a throttle (429). Uses exponential backoff."""
    return 10.0 * (2**attempt)  # 10s, 20s, 40s, ...


def _convert_sdk_message(msg: GraphSDKMessage) -> GraphMessage:
    """Convert SDK message to our GraphMessage model (shared)."""
    from_recipient = None
    if msg.from_ and msg.from_.email_address:
        from_recipient = Recipient(
            emailAddress=EmailAddress(
                address=msg.from_.email_address.address or "",
                name=msg.from_.email_address.name,
            )
        )
    to_recipients = []
    for r in (msg.to_recipients or []):
        if r.email_address:
            to_recipients.append(
                Recipient(
                    emailAddress=EmailAddress(
                        address=r.email_address.address or "",
                        name=r.email_address.name,
                    )
                )
            )
    body = ItemBody()
    if msg.body:
        body = ItemBody(
            contentType="html" if msg.body.content_type == BodyType.Html else "text",
            content=msg.body.content or "",
        )
    return GraphMessage(
        id=msg.id or "",
        conversationId=msg.conversation_id,
        internetMessageId=msg.internet_message_id,
        receivedDateTime=str(msg.received_date_time) if msg.received_date_time else None,
        subject=msg.subject or "",
        body=body,
        bodyPreview=msg.body_preview,
        from_=from_recipient,
        toRecipients=to_recipients,
        isDraft=msg.is_draft or False,
    )


class GraphProvider:
    """Microsoft Graph mail provider using delegated (user sign-in) auth with MSAL token cache.

    Uses device code flow on first run (open https://microsoft.com/devicelogin and enter the code).
    Tokens are stored in ~/.email-automation/token_cache.json and auto-refreshed on subsequent runs.
    Accesses the signed-in user's mailbox via the /me endpoint.

    When http_client is provided (e.g. from webhook server lifespan), the provider uses that
    client and the caller is responsible for closing it. When None, the SDK creates its own client.
    """

    def __init__(
        self,
        tenant_id: str,
        client_id: str,
        http_client: "httpx.AsyncClient | None" = None,
    ):
        credential = get_persistent_device_code_credential(tenant_id=tenant_id, client_id=client_id)
        self._http_client = http_client
        if http_client is not None:
            auth_provider = AzureIdentityAuthenticationProvider(
                credential,
                scopes=DELEGATED_SCOPES,
            )
            request_adapter = GraphRequestAdapter(auth_provider, client=http_client)
            self._client = GraphServiceClient(request_adapter=request_adapter)
        else:
            self._client = GraphServiceClient(
                credentials=credential,
                scopes=DELEGATED_SCOPES,
            )
        logger.info("graph_provider.init", tenant_id=f"{tenant_id[:8]}...")

    async def close(self) -> None:
        """Close the HTTP client if this provider owns one (e.g. passed in from webhook lifespan)."""
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

    async def create_subscription(
        self,
        notification_url: str,
        client_state: str,
        expiration_minutes: int = 4000,
        resource: str | None = None,
        use_immutable_id: bool = False,
    ) -> GraphSubscription | None:
        """Create a webhook subscription (delegates to webhook.subscription)."""
        from src.webhook.subscription import create_subscription as _create
        return await _create(
            self._client,
            notification_url=notification_url,
            client_state=client_state,
            expiration_minutes=expiration_minutes,
            resource=resource,
            use_immutable_id=use_immutable_id,
        )

    async def create_sent_subscription(
        self,
        notification_url: str,
        client_state: str,
        expiration_minutes: int = 4000,
    ) -> GraphSubscription | None:
        """Create a subscription for Sent Items with ImmutableId (for draft->sent correlation)."""
        from src.webhook.subscription import create_sent_subscription as _create_sent
        return await _create_sent(
            self._client,
            notification_url=notification_url,
            client_state=client_state,
            expiration_minutes=expiration_minutes,
        )

    async def renew_subscription(
        self,
        subscription_id: str,
        expiration_minutes: int = 4000,
    ) -> GraphSubscription | None:
        """Renew a subscription (delegates to webhook.subscription)."""
        from src.webhook.subscription import renew_subscription as _renew
        return await _renew(self._client, subscription_id, expiration_minutes)

    async def delete_subscription(self, subscription_id: str) -> bool:
        """Delete a subscription (delegates to webhook.subscription)."""
        from src.webhook.subscription import delete_subscription as _delete
        return await _delete(self._client, subscription_id)

    async def get_message(self, message_id: str, user_id: str | None = None) -> GraphMessage | None:
        """Get a single message by ID. If user_id is set, use /users/{user_id}/messages/{id}; else /me/messages/{id}.
        Retries on transient network errors and on 429 throttle (ApplicationThrottled / MailboxConcurrency)
        with exponential backoff. ErrorItemNotFound/404 is never retried (caller handles eventual consistency)."""
        max_network_retries = 3
        max_throttle_retries = 5
        for attempt in range(max(max_network_retries, max_throttle_retries)):
            try:
                from msgraph.generated.users.item.messages.item.message_item_request_builder import (
                    MessageItemRequestBuilder,
                )
                get_config = MessageItemRequestBuilder.MessageItemRequestBuilderGetRequestConfiguration()
                get_config.headers.add("Prefer", PREFER_IMMUTABLE_ID)
                if user_id:
                    msg = await self._client.users.by_user_id(user_id).messages.by_message_id(
                        message_id
                    ).get(request_configuration=get_config)
                else:
                    msg = await self._client.me.messages.by_message_id(message_id).get(
                        request_configuration=get_config
                    )
                if msg:
                    logger.debug(
                        "graph_provider.get_message.hit",
                        message_id=message_id,
                        user_id=user_id,
                    )
                    return _convert_sdk_message(msg)
                return None
            except Exception as e:
                err_str = str(e).strip() or repr(e)
                # 404/ErrorItemNotFound: do not retry here; caller handles eventual consistency.
                if "ErrorItemNotFound" in err_str or "404" in err_str:
                    logger.debug(
                        "graph_provider.get_message.not_found",
                        message_id=message_id,
                        user_id=user_id,
                    )
                    return None
                # Retry on 429 throttle (MailboxConcurrency, ApplicationThrottled) with long backoff.
                if _is_throttle_error(e):
                    if attempt < max_throttle_retries - 1:
                        delay = _throttle_retry_delay_seconds(attempt)
                        logger.warning(
                            "graph_provider.get_message.throttled",
                            message_id=message_id,
                            user_id=user_id,
                            attempt=attempt + 1,
                            retry_after_seconds=delay,
                        )
                        await asyncio.sleep(delay)
                        continue
                    logger.error(
                        "graph_provider.get_message.error",
                        message_id=message_id,
                        user_id=user_id,
                        error=err_str,
                        error_type=type(e).__name__,
                    )
                    return None
                # Retry on transient network errors (WriteError, ConnectionResetError, etc.)
                if attempt < max_network_retries - 1 and _is_transient_network_error(e):
                    delay = 1.0 * (attempt + 1)  # 1s, then 2s
                    logger.debug(
                        "graph_provider.get_message.retry",
                        message_id=message_id,
                        user_id=user_id,
                        attempt=attempt + 1,
                        error_type=type(e).__name__,
                    )
                    await asyncio.sleep(delay)
                    continue
                logger.error(
                    "graph_provider.get_message.error",
                    message_id=message_id,
                    user_id=user_id,
                    error=err_str,
                    error_type=type(e).__name__,
                )
                return None
        return None

    async def get_conversation(self, conversation_id: str, user_id: str | None = None) -> list[GraphMessage]:
        """Get all messages in a conversation (signed-in user's mailbox, or user_id when set).

        Tries filter+orderby first; on InefficientFilter falls back to filter-only
        (sort in Python), then to fetching recent messages and filtering client-side,
        so the decision agent always gets full thread context.
        """
        select = ["id", "conversationId", "internetMessageId", "subject", "body", "bodyPreview", "from", "toRecipients", "receivedDateTime", "isDraft"]
        messages_request = (
            self._client.users.by_user_id(user_id).messages
            if user_id
            else self._client.me.messages
        )
        # Try 1: filter + orderby (preferred)
        try:
            q = MessagesRequestBuilder.MessagesRequestBuilderGetQueryParameters(
                filter=f"conversationId eq '{conversation_id}'",
                orderby=["receivedDateTime ASC"],
                select=select,
            )
            config = MessagesRequestBuilder.MessagesRequestBuilderGetRequestConfiguration(
                query_parameters=q,
            )
            result = await messages_request.get(request_configuration=config)
            messages = [_convert_sdk_message(m) for m in (result.value or [])]
            if messages:
                logger.debug(
                    "graph_provider.get_conversation",
                    conversation_id=conversation_id,
                    count=len(messages),
                )
                return messages
        except Exception as e:
            logger.debug(
                "graph_provider.get_conversation.fallback",
                conversation_id=conversation_id,
                error=str(e),
            )

        # Try 2: filter only, sort in Python (avoids InefficientFilter)
        try:
            q = MessagesRequestBuilder.MessagesRequestBuilderGetQueryParameters(
                filter=f"conversationId eq '{conversation_id}'",
                select=select,
            )
            config = MessagesRequestBuilder.MessagesRequestBuilderGetRequestConfiguration(
                query_parameters=q,
            )
            result = await messages_request.get(request_configuration=config)
            raw = result.value or []
            messages = [_convert_sdk_message(m) for m in raw]
            messages.sort(key=lambda m: m.receivedDateTime or "")
            if messages:
                logger.info(
                    "graph_provider.get_conversation.filter_only",
                    conversation_id=conversation_id,
                    count=len(messages),
                )
                return messages
        except Exception as e:
            logger.debug(
                "graph_provider.get_conversation.filter_only_failed",
                conversation_id=conversation_id,
                error=str(e),
            )

        # Try 3: no filter, fetch recent messages and filter client-side
        try:
            q = MessagesRequestBuilder.MessagesRequestBuilderGetQueryParameters(
                top=100,
                select=select,
                orderby=["receivedDateTime DESC"],
            )
            config = MessagesRequestBuilder.MessagesRequestBuilderGetRequestConfiguration(
                query_parameters=q,
            )
            result = await messages_request.get(request_configuration=config)
            matching = [
                _convert_sdk_message(m)
                for m in (result.value or [])
                if (m.conversation_id or "") == conversation_id
            ]
            matching.sort(key=lambda m: m.receivedDateTime or "")
            if matching:
                logger.info(
                    "graph_provider.get_conversation.client_side",
                    conversation_id=conversation_id,
                    count=len(matching),
                )
                return matching
        except Exception as e:
            logger.error(
                "graph_provider.get_conversation.error",
                conversation_id=conversation_id,
                error=str(e),
            )
        return []

    async def get_latest_from_sender(self, sender_email: str) -> GraphMessage | None:
        """Get the most recent message from the given sender (/me mailbox, client-side filter)."""
        sender_normalized = (sender_email or "").strip().lower()
        if not sender_normalized:
            logger.warning("graph_provider.get_latest_from_sender.empty_sender")
            return None
        query_params = MessagesRequestBuilder.MessagesRequestBuilderGetQueryParameters(
            top=50,
            select=["id", "conversationId", "internetMessageId", "subject", "body", "bodyPreview", "from", "toRecipients", "receivedDateTime", "isDraft"],
            orderby=["receivedDateTime DESC"],
        )
        config = MessagesRequestBuilder.MessagesRequestBuilderGetRequestConfiguration(
            query_parameters=query_params,
        )
        try:
            result = await self._client.me.messages.get(request_configuration=config)
            if not result.value:
                logger.info(
                    "graph_provider.get_latest_from_sender.no_messages",
                    sender=sender_normalized,
                )
                return None
            for msg in result.value:
                if msg.from_ and msg.from_.email_address and msg.from_.email_address.address:
                    if msg.from_.email_address.address.strip().lower() == sender_normalized:
                        logger.info(
                            "graph_provider.get_latest_from_sender.found",
                            sender=sender_normalized,
                            message_id=msg.id,
                        )
                        return _convert_sdk_message(msg)
            logger.info(
                "graph_provider.get_latest_from_sender.no_messages",
                sender=sender_normalized,
            )
            return None
        except Exception as e:
            logger.error(
                "graph_provider.get_latest_from_sender.error",
                sender=sender_normalized,
                error=str(e),
            )
            return None

    async def send_message(self, payload: SendPayload) -> GraphMessage:
        """Send a message as the signed-in user."""
        log_agent_step("GraphProvider", "Send message", {"to": payload.to, "subject": payload.subject})
        message = GraphSDKMessage(
            subject=payload.subject,
            body=GraphSDKItemBody(
                content_type=BodyType.Html if payload.contentType == "html" else BodyType.Text,
                content=payload.body,
            ),
            to_recipients=[
                GraphSDKRecipient(
                    email_address=GraphSDKEmailAddress(address=payload.to),
                ),
            ],
        )
        request_body = SendMailPostRequestBody(
            message=message,
            save_to_sent_items=True,
        )
        await self._client.me.send_mail.post(body=request_body)
        sent_dt = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        return GraphMessage(
            id=f"sent_{id(payload)}",
            conversationId=payload.conversationId,
            receivedDateTime=sent_dt,
            subject=payload.subject,
            body=ItemBody(contentType=payload.contentType, content=payload.body),
            toRecipients=[Recipient(emailAddress=EmailAddress(address=payload.to))],
            isDraft=False,
        )

    async def create_reply_draft(
        self,
        message_id: str,
        body: str,
        subject: str | None = None,
        user_id: str | None = None,
    ) -> GraphMessage:
        """Create a reply draft (do not send). Uses ImmutableId so the same id is used when the draft is sent.
        When user_id is set, uses /users/{id}/messages/.../createReply; else /me/.../createReply.
        """
        from msgraph.generated.users.item.messages.item.create_reply.create_reply_post_request_body import (
            CreateReplyPostRequestBody,
        )
        from msgraph.generated.users.item.messages.item.create_reply.create_reply_request_builder import (
            CreateReplyRequestBuilder,
        )
        log_agent_step("GraphProvider", "Create reply draft", {"message_id": message_id})
        html_body = (body or "").replace("\n", "<br>\n")
        message = GraphSDKMessage(
            body=GraphSDKItemBody(content_type=BodyType.Html, content=html_body),
        )
        request_body = CreateReplyPostRequestBody(message=message)
        post_config = CreateReplyRequestBuilder.CreateReplyRequestBuilderPostRequestConfiguration()
        post_config.headers.add("Prefer", PREFER_IMMUTABLE_ID)
        if user_id:
            draft = await self._client.users.by_user_id(user_id).messages.by_message_id(
                message_id
            ).create_reply.post(body=request_body, request_configuration=post_config)
        else:
            draft = await self._client.me.messages.by_message_id(
                message_id
            ).create_reply.post(body=request_body, request_configuration=post_config)
        if not draft:
            raise ValueError("create_reply returned no draft message")
        return _convert_sdk_message(draft)

    async def reply_to_message(
        self, message_id: str, comment: str, user_id: str | None = None
    ) -> GraphMessage:
        """Reply to a message using the native Graph reply API (auto-threads, saves to Sent).
        Body is sent as HTML so that newlines render correctly in Gmail and other clients.
        When user_id is set, uses /users/{id}/messages/.../reply; else /me/messages/.../reply.
        """
        from msgraph.generated.users.item.messages.item.reply.reply_post_request_body import (
            ReplyPostRequestBody,
        )
        log_agent_step("GraphProvider", "Reply to message", {"message_id": message_id})
        # Convert newlines to <br> so they render in HTML (comment as plain text loses line breaks in Gmail)
        html_body = (comment or "").replace("\n", "<br>\n")
        message = GraphSDKMessage(
            body=GraphSDKItemBody(content_type=BodyType.Html, content=html_body),
        )
        request_body = ReplyPostRequestBody(message=message)
        if user_id:
            await self._client.users.by_user_id(user_id).messages.by_message_id(
                message_id
            ).reply.post(request_body)
        else:
            await self._client.me.messages.by_message_id(message_id).reply.post(
                request_body
            )
        sent_dt = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        return GraphMessage(
            id=f"reply_{message_id}",
            receivedDateTime=sent_dt,
            subject="",
            body=ItemBody(contentType="html", content=comment),
            isDraft=False,
        )
