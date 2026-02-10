"""Extracted input models per scenario (A1-A4)."""

from typing import Optional

from pydantic import BaseModel


class ProductSupplyInput(BaseModel):
    """Extracted inputs for Product Supply (S1)."""

    location: Optional[str] = None
    distributor: Optional[str] = None
    ndc: Optional[str] = None
    confidence: float


class ProductAccessInput(BaseModel):
    """Extracted inputs for Product Access (S2)."""

    customer: Optional[str] = None
    distributor: Optional[str] = None
    ndc: Optional[str] = None
    dea_number: Optional[str] = None
    address: Optional[str] = None
    is_340b: Optional[bool] = None
    contact: Optional[str] = None
    confidence: float


class ProductAllocationInput(BaseModel):
    """Extracted inputs for Product Allocation (S3)."""

    urgency: Optional[str] = None
    year_start: Optional[int] = None
    year_end: Optional[int] = None
    distributor: Optional[str] = None
    ndc: Optional[str] = None
    confidence: float


class CatchAllInput(BaseModel):
    """Extracted inputs for Catch-All (S4) - topics for RAG search."""

    topics: list[str] = []
    question_summary: Optional[str] = None
    confidence: float
