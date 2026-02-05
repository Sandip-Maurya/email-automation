"""Mail provider protocol (Graph-like interface)."""

from typing import Protocol

from src.mail_provider.graph_models import GraphMessage


class MailProvider(Protocol):
    """Abstract interface for getting mail and replying (Graph-style)."""

    def get_message(self, message_id: str) -> GraphMessage | None:
        """Get a single message by id."""
        ...

    def get_conversation(self, conversation_id: str) -> list[GraphMessage]:
        """Get all messages in a conversation, ordered by receivedDateTime."""
        ...

    def reply_to_message(self, message_id: str, comment: str) -> GraphMessage:
        """Reply to a message by ID; returns the sent reply (e.g. with id, receivedDateTime)."""
        ...
