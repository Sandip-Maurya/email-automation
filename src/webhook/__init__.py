"""Webhook service for Microsoft Graph change notifications."""

from src.webhook.models import (
    ResourceData,
    ChangeNotification,
    ChangeNotificationBatch,
)

__all__ = [
    "ResourceData",
    "ChangeNotification",
    "ChangeNotificationBatch",
]
