"""Mail provider protocol (Graph-like interface)."""

from typing import Protocol

from src.mail_provider.graph_models import GraphMessage


class MailProvider(Protocol):
    """Abstract interface for getting mail and replying (Graph-style)."""

    def get_message(self, message_id: str, user_id: str | None = None) -> GraphMessage | None:
        """Get a single message by id. user_id scopes to /users/{id}/messages when set; else /me/messages."""
        ...

    def get_conversation(self, conversation_id: str, user_id: str | None = None) -> list[GraphMessage]:
        """Get all messages in a conversation, ordered by receivedDateTime. user_id scopes mailbox when set."""
        ...

    def reply_to_message(
        self, message_id: str, comment: str, user_id: str | None = None
    ) -> GraphMessage:
        """Reply to a message by ID; returns the sent reply. user_id scopes mailbox when set."""
        ...
