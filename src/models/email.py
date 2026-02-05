"""Email and thread models."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class Email(BaseModel):
    """Single email message."""

    id: str
    sender: str
    subject: str
    body: str
    timestamp: datetime
    thread_id: Optional[str] = None
    sender_name: Optional[str] = None  # Display name from Graph API


class EmailThread(BaseModel):
    """Thread of emails (oldest to newest)."""

    thread_id: str
    emails: list[Email]
    latest_email: Email
