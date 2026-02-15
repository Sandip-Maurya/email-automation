"""Microsoft Graph subscription manager: create, renew, delete webhook subscriptions."""

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from msgraph.generated.models.subscription import Subscription as GraphSubscription

from src.config import WEBHOOK_SENT_RESOURCE, WEBHOOK_SUBSCRIPTION_RESOURCE
from src.utils.logger import get_logger

if TYPE_CHECKING:
    from msgraph import GraphServiceClient

logger = get_logger("email_automation.webhook.subscription")

# Mail messages: max 4230 minutes (~3 days)
MAIL_SUBSCRIPTION_MAX_MINUTES = 4230
CHANGE_TYPE_CREATED = "created"
PREFER_IMMUTABLE_ID = "IdType=\"ImmutableId\""


async def create_subscription(
    client: "GraphServiceClient",
    notification_url: str,
    client_state: str,
    expiration_minutes: int = 4000,
    resource: str | None = None,
    use_immutable_id: bool = False,
) -> GraphSubscription | None:
    """
    Create a Graph subscription (resource from config by default, changeType=created).
    When use_immutable_id is True, adds Prefer: IdType="ImmutableId" so notifications use immutable ids.
    Returns the created subscription or None on failure.
    """
    expiration_minutes = min(expiration_minutes, MAIL_SUBSCRIPTION_MAX_MINUTES)
    expiration = datetime.now(timezone.utc) + timedelta(minutes=expiration_minutes)
    resource_val = resource or WEBHOOK_SUBSCRIPTION_RESOURCE
    body = GraphSubscription(
        change_type=CHANGE_TYPE_CREATED,
        notification_url=notification_url,
        resource=resource_val,
        expiration_date_time=expiration,
        client_state=client_state[:128] if client_state else None,
    )
    try:
        from msgraph.generated.subscriptions.subscriptions_request_builder import (
            SubscriptionsRequestBuilder,
        )
        request_config = None
        if use_immutable_id:
            request_config = (
                SubscriptionsRequestBuilder.SubscriptionsRequestBuilderPostRequestConfiguration()
            )
            request_config.headers.add("Prefer", PREFER_IMMUTABLE_ID)
        sub = await client.subscriptions.post(
            body, request_configuration=request_config
        )
        if sub and sub.id:
            logger.info(
                "webhook.subscription.created",
                subscription_id=sub.id,
                expires=sub.expiration_date_time.isoformat() if sub.expiration_date_time else None,
            )
            return sub
        return None
    except Exception as e:
        logger.error(
            "webhook.subscription.create_error",
            error=str(e),
        )
        return None


async def create_sent_subscription(
    client: "GraphServiceClient",
    notification_url: str,
    client_state: str,
    expiration_minutes: int = 4000,
) -> GraphSubscription | None:
    """Create a subscription for Sent Items with ImmutableId (for draft->sent correlation)."""
    return await create_subscription(
        client,
        notification_url=notification_url,
        client_state=client_state,
        expiration_minutes=expiration_minutes,
        resource=WEBHOOK_SENT_RESOURCE,
        use_immutable_id=True,
    )


async def renew_subscription(
    client: "GraphServiceClient",
    subscription_id: str,
    expiration_minutes: int = 4000,
) -> GraphSubscription | None:
    """
    Renew a subscription by extending its expiration.
    Returns the updated subscription or None on failure.
    """
    expiration_minutes = min(expiration_minutes, MAIL_SUBSCRIPTION_MAX_MINUTES)
    expiration = datetime.now(timezone.utc) + timedelta(minutes=expiration_minutes)
    body = GraphSubscription(expiration_date_time=expiration)
    try:
        sub = await client.subscriptions.by_subscription_id(subscription_id).patch(body)
        if sub:
            logger.info(
                "webhook.subscription.renewed",
                subscription_id=subscription_id,
                expires=sub.expiration_date_time.isoformat() if sub.expiration_date_time else None,
            )
            return sub
        return None
    except Exception as e:
        logger.error(
            "webhook.subscription.renew_error",
            subscription_id=subscription_id,
            error=str(e),
        )
        return None


async def delete_subscription(
    client: "GraphServiceClient",
    subscription_id: str,
) -> bool:
    """Delete a subscription. Returns True on success."""
    try:
        await client.subscriptions.by_subscription_id(subscription_id).delete()
        logger.info("webhook.subscription.deleted", subscription_id=subscription_id)
        return True
    except Exception as e:
        logger.error(
            "webhook.subscription.delete_error",
            subscription_id=subscription_id,
            error=str(e),
        )
        return False


async def list_subscriptions(client: "GraphServiceClient"):
    """List current subscriptions (for debugging)."""
    try:
        result = await client.subscriptions.get()
        return result.value or []
    except Exception as e:
        logger.error("webhook.subscription.list_error", error=str(e))
        return []
