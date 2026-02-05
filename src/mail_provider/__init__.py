"""Mail provider: Graph-like interface and mock implementation."""

from src.mail_provider.graph_models import (
    EmailAddress,
    GraphMessage,
    ItemBody,
    Recipient,
    SendPayload,
)
from src.mail_provider.protocol import MailProvider
from src.mail_provider.graph_mock import GraphMockProvider
from src.mail_provider.mapping import (
    graph_messages_to_thread,
    final_email_to_send_payload,
)

__all__ = [
    "EmailAddress",
    "GraphMessage",
    "ItemBody",
    "Recipient",
    "SendPayload",
    "MailProvider",
    "GraphMockProvider",
    "graph_messages_to_thread",
    "final_email_to_send_payload",
]
