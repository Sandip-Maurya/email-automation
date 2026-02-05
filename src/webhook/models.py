"""Pydantic models for Microsoft Graph change notification webhook payloads."""

from pydantic import BaseModel, Field


class ResourceData(BaseModel):
    """Resource data included in a change notification (e.g. message id)."""

    odata_type: str | None = Field(None, alias="@odata.type")
    id: str | None = None

    model_config = {"populate_by_name": True, "extra": "ignore"}


class ChangeNotification(BaseModel):
    """Single change notification from Microsoft Graph (changeNotification resource type)."""

    change_type: str = Field(..., alias="changeType")
    client_state: str | None = Field(None, alias="clientState")
    encrypted_content: dict | None = Field(None, alias="encryptedContent")
    id: str | None = None
    lifecycle_event: str | None = Field(None, alias="lifecycleEvent")
    resource: str | None = None
    resource_data: ResourceData | None = Field(None, alias="resourceData")
    subscription_expiration_date_time: str | None = Field(
        None, alias="subscriptionExpirationDateTime"
    )
    subscription_id: str | None = Field(None, alias="subscriptionId")
    tenant_id: str | None = Field(None, alias="tenantId")

    model_config = {"populate_by_name": True, "extra": "ignore"}


class ChangeNotificationBatch(BaseModel):
    """Request body of a Graph webhook POST: array of change notifications in 'value'."""

    value: list[ChangeNotification] = Field(default_factory=list)
