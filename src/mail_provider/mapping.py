"""Map Graph messages to EmailThread and FinalEmail to SendPayload."""

from datetime import datetime

from src.models.email import Email, EmailThread
from src.models.outputs import FinalEmail
from src.mail_provider.graph_models import GraphMessage, SendPayload
from src.utils.body_sanitizer import sanitize_email_body


def _parse_datetime(s: str | None) -> datetime:
    if not s:
        return datetime.now()
    try:
        s = s.replace("Z", "+00:00")
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return datetime.now()


def _sender_address(msg: GraphMessage) -> str:
    if msg.from_ and msg.from_.emailAddress:
        return msg.from_.emailAddress.address or ""
    return ""


def _sender_name(msg: GraphMessage) -> str | None:
    """Extract sender display name from Graph message."""
    if msg.from_ and msg.from_.emailAddress and msg.from_.emailAddress.name:
        return msg.from_.emailAddress.name.strip() or None
    return None


def graph_messages_to_thread(messages: list[GraphMessage]) -> EmailThread:
    """Convert ordered list of Graph messages to EmailThread.

    Email body content is sanitized to:
    - Convert HTML to plain text (if content type is html)
    - Remove quoted replies from email chains
    - Remove email signatures and disclaimers
    - Normalize whitespace
    """
    if not messages:
        raise ValueError("At least one message required")
    emails = []
    for m in messages:
        # Extract and sanitize body content
        raw_body = m.body.content if m.body else ""
        content_type = m.body.contentType if m.body else "text"
        clean_body = sanitize_email_body(raw_body, content_type=content_type)

        emails.append(
            Email(
                id=m.id,
                sender=_sender_address(m),
                subject=m.subject or "",
                body=clean_body,
                timestamp=_parse_datetime(m.receivedDateTime),
                thread_id=m.conversationId,
                sender_name=_sender_name(m),
            )
        )
    thread_id = messages[0].conversationId or messages[0].id
    return EmailThread(thread_id=thread_id, emails=emails, latest_email=emails[-1])


def final_email_to_send_payload(
    final_email: FinalEmail,
    reply_to_address: str,
    conversation_id: str | None = None,
    internet_message_id: str | None = None,
) -> SendPayload:
    """Build SendPayload from FinalEmail and thread context."""
    to = final_email.to or reply_to_address
    return SendPayload(
        to=to,
        subject=final_email.subject,
        body=final_email.body,
        contentType="text",
        conversationId=conversation_id,
        internetMessageId=internet_message_id,
    )
