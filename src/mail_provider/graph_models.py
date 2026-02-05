"""Pydantic models for Microsoft Graph API message shape (subset we need)."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class EmailAddress(BaseModel):
    """Graph emailAddress."""

    address: str
    name: Optional[str] = None


class Recipient(BaseModel):
    """Graph recipient (from, toRecipients, etc.)."""

    emailAddress: EmailAddress


class ItemBody(BaseModel):
    """Graph itemBody (message body)."""

    contentType: str = "text"  # "text" | "html"
    content: str = ""


class GraphMessage(BaseModel):
    """Microsoft Graph message resource (subset)."""

    id: str
    conversationId: Optional[str] = None
    internetMessageId: Optional[str] = None
    receivedDateTime: Optional[str] = None  # ISO 8601
    subject: str = ""
    body: ItemBody = ItemBody()
    bodyPreview: Optional[str] = None
    from_: Optional[Recipient] = Field(None, alias="from")
    toRecipients: list[Recipient] = []
    ccRecipients: list[Recipient] = []
    replyTo: list[Recipient] = []
    isDraft: bool = False

    class Config:
        populate_by_name = True
        extra = "allow"


class SendPayload(BaseModel):
    """Payload for sending a message (reply or new)."""

    to: str  # single recipient address
    subject: str
    body: str
    contentType: str = "text"
    conversationId: Optional[str] = None
    internetMessageId: Optional[str] = None  # for reply threading
