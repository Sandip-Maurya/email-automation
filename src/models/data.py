"""Data models for mock CSV / API responses."""

from typing import Optional

from pydantic import BaseModel


class InventoryRecord(BaseModel):
    """Inventory record (S1 mock data)."""

    ndc: str
    product_name: str
    location: str
    quantity_available: int
    distributor: str


class CustomerRecord(BaseModel):
    """Customer/account record (S2 mock data)."""

    customer_id: str
    name: str
    dea_number: str
    is_340b: bool
    class_of_trade: str
    address: str
    rems_certified: bool


class AllocationRecord(BaseModel):
    """Allocation record (S3 mock data)."""

    distributor: str
    ndc: str
    allocation_percent: float
    year: int
    quantity_allocated: int
    quantity_used: int


class ProductRecord(BaseModel):
    """Product catalog record."""

    ndc: str
    brand_name: str
    description: Optional[str] = None


class PastEmailRecord(BaseModel):
    """Past email for RAG (S4)."""

    email_id: str
    subject: str
    body: str
    topic: Optional[str] = None
