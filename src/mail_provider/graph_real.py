"""Real Microsoft Graph API mail provider (async)."""

import asyncio
from datetime import datetime, timezone

from msgraph import GraphServiceClient
from msgraph.generated.models.subscription import Subscription as GraphSubscription

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

# Delegated scopes (same as verify_graph_credentials.py); need Mail.Send for sending
DELEGATED_SCOPES = [
    "https://graph.microsoft.com/Mail.Read",
    "https://graph.microsoft.com/Mail.Send",
]


def _is_transient_network_error(e: Exception) -> bool:
    """True if the exception is a transient I/O/network error worth retrying.

    Includes: WriteError, ConnectionResetError, LocalProtocolError (e.g. SEND_HEADERS on
    closed connection from httpx/httpcore), and WinError 10054.
    """
    name = type(e).__name__
    if name in (
        "WriteError",
        "ConnectionResetError",
        "ConnectionError",
        "TimeoutError",
        "LocalProtocolError",
        "RemoteProtocolError",
    ):
        return True
    if isinstance(e, OSError) and getattr(e, "winerror", None) == 10054:
        return True
    return False


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
    """

    def __init__(self, tenant_id: str, client_id: str):
        credential = get_persistent_device_code_credential(tenant_id=tenant_id, client_id=client_id)
        self._client = GraphServiceClient(
            credentials=credential,
            scopes=DELEGATED_SCOPES,
        )
        logger.info("graph_provider.init", tenant_id=tenant_id[:8])

    async def create_subscription(
        self,
        notification_url: str,
        client_state: str,
        expiration_minutes: int = 4000,
    ) -> GraphSubscription | None:
        """Create a webhook subscription for new mail (delegates to webhook.subscription)."""
        from src.webhook.subscription import create_subscription as _create
        return await _create(
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

    async def get_message(self, message_id: str) -> GraphMessage | None:
        """Get a single message by ID (signed-in user's mailbox). Retries up to 2 times on transient I/O/connection errors."""
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                msg = await self._client.me.messages.by_message_id(message_id).get()
                if msg:
                    logger.debug("graph_provider.get_message.hit", message_id=message_id)
                    return _convert_sdk_message(msg)
                return None
            except Exception as e:
                err_str = str(e).strip() or repr(e)
                if "ErrorItemNotFound" in err_str or "404" in err_str:
                    logger.debug("graph_provider.get_message.not_found", message_id=message_id)
                    return None
                # Retry on transient errors (WriteError, ConnectionResetError, LocalProtocolError, etc.)
                if attempt < max_attempts - 1 and _is_transient_network_error(e):
                    delay = 0.5 * (attempt + 1)  # 0.5s, then 1.0s
                    logger.debug(
                        "graph_provider.get_message.retry",
                        message_id=message_id,
                        attempt=attempt + 1,
                        error_type=type(e).__name__,
                    )
                    await asyncio.sleep(delay)
                    continue
                logger.error(
                    "graph_provider.get_message.error",
                    message_id=message_id,
                    error=err_str,
                    error_type=type(e).__name__,
                )
                return None
        return None

    async def get_conversation(self, conversation_id: str) -> list[GraphMessage]:
        """Get all messages in a conversation (signed-in user's mailbox).

        Tries filter+orderby first; on InefficientFilter falls back to filter-only
        (sort in Python), then to fetching recent messages and filtering client-side,
        so the decision agent always gets full thread context.
        """
        select = ["id", "conversationId", "internetMessageId", "subject", "body", "bodyPreview", "from", "toRecipients", "receivedDateTime", "isDraft"]
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
            result = await self._client.me.messages.get(request_configuration=config)
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
            result = await self._client.me.messages.get(request_configuration=config)
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
            result = await self._client.me.messages.get(request_configuration=config)
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

    async def reply_to_message(self, message_id: str, comment: str) -> GraphMessage:
        """Reply to a message using the native Graph reply API (auto-threads, saves to Sent).
        Body is sent as HTML so that newlines render correctly in Gmail and other clients.
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
        await self._client.me.messages.by_message_id(message_id).reply.post(request_body)
        sent_dt = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        return GraphMessage(
            id=f"reply_{message_id}",
            receivedDateTime=sent_dt,
            subject="",
            body=ItemBody(contentType="html", content=comment),
            isDraft=False,
        )
