"""Email outcome repository: insert draft, supersede by conversation, get by message_id, update sent."""

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select

from src.db import get_session
from src.db.models.email_outcome import EmailOutcome

STATUS_DRAFT_CREATED = "draft_created"
STATUS_SENT = "sent"
STATUS_SUPERSEDED = "superseded"


def insert_draft(
    message_id: str,
    conversation_id: str,
    reply_to_message_id: str,
    scenario: str,
    draft_subject: str,
    draft_body: str,
    final_subject: str,
    final_body: str,
    metadata_json: Optional[str] = None,
    user_id: Optional[str] = None,
    user_name: Optional[str] = None,
) -> EmailOutcome:
    """Insert a new draft row. Call after create_reply_draft returns the immutable message_id."""
    with get_session() as session:
        row = EmailOutcome(
            message_id=message_id,
            conversation_id=conversation_id,
            user_id=user_id,
            user_name=user_name,
            reply_to_message_id=reply_to_message_id,
            scenario=scenario,
            draft_subject=draft_subject,
            draft_body=draft_body,
            final_subject=final_subject,
            final_body=final_body,
            metadata_json=metadata_json,
            status=STATUS_DRAFT_CREATED,
        )
        session.add(row)
        session.flush()
        session.refresh(row)
        session.expunge(row)
        return row


def has_recent_draft(conversation_id: str, within_seconds: int = 120) -> bool:
    """Return True if there is a draft_created row for this conversation within the last within_seconds."""
    since = datetime.now(timezone.utc) - timedelta(seconds=within_seconds)
    with get_session() as session:
        q = (
            select(EmailOutcome.id)
            .where(EmailOutcome.conversation_id == conversation_id)
            .where(EmailOutcome.status == STATUS_DRAFT_CREATED)
            .where(EmailOutcome.created_at >= since)
        )
        return session.scalars(q).first() is not None


def supersede_by_conversation(conversation_id: str, user_id: Optional[str] = None) -> None:
    """Mark all draft_created rows for this conversation as superseded (ignores user_id)."""
    now = datetime.now(timezone.utc)
    with get_session() as session:
        q = (
            select(EmailOutcome)
            .where(EmailOutcome.conversation_id == conversation_id)
            .where(EmailOutcome.status == STATUS_DRAFT_CREATED)
        )
        rows = list(session.scalars(q).all())
        for row in rows:
            row.status = STATUS_SUPERSEDED
            row.superseded_at = now


def get_by_message_id(message_id: str) -> Optional[EmailOutcome]:
    """Return the email outcome row for this Graph message_id (immutable id), or None."""
    with get_session() as session:
        row = session.scalars(
            select(EmailOutcome).where(EmailOutcome.message_id == message_id)
        ).first()
        if row is not None:
            session.refresh(row)
            session.expunge(row)
        return row


def update_sent(
    message_id: str,
    sent_subject: str,
    sent_body: str,
    sent_to: str,
    sent_at: datetime,
) -> bool:
    """Update the row with sent content and set status to sent. Returns True if a row was updated."""
    with get_session() as session:
        row = session.scalars(
            select(EmailOutcome).where(EmailOutcome.message_id == message_id)
        ).first()
        if row is None:
            return False
        row.sent_subject = sent_subject
        row.sent_body = sent_body
        row.sent_to = sent_to
        row.sent_at = sent_at
        row.status = STATUS_SENT
        return True
