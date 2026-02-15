"""ORM model for email outcomes: agent draft + optional sent version (single table)."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base, TimestampMixin


class EmailOutcome(Base, TimestampMixin):
    """One row per draft (and optional sent version). Keyed by Graph immutable message_id."""

    __tablename__ = "email_outcomes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    message_id: Mapped[str] = mapped_column(String(512), unique=True, nullable=False, index=True)
    conversation_id: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True, index=True)
    user_name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    reply_to_message_id: Mapped[str] = mapped_column(String(512), nullable=False)
    scenario: Mapped[str] = mapped_column(String(16), nullable=False, index=True)

    draft_subject: Mapped[str] = mapped_column(String(1024), nullable=False)
    draft_body: Mapped[str] = mapped_column(Text, nullable=False)
    final_subject: Mapped[str] = mapped_column(String(1024), nullable=False)
    final_body: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    superseded_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    sent_subject: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    sent_body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sent_to: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
