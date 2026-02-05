"""Pydantic models for email automation."""

from src.models.email import Email, EmailThread
from src.models.inputs import (
    ProductAccessInput,
    ProductAllocationInput,
    ProductSupplyInput,
    CatchAllInput,
)
from src.models.outputs import (
    ScenarioDecision,
    ReviewResult,
    ProcessingResult,
    DraftEmail,
    FinalEmail,
)
from src.models.data import (
    InventoryRecord,
    CustomerRecord,
    AllocationRecord,
    ProductRecord,
    PastEmailRecord,
)

__all__ = [
    "Email",
    "EmailThread",
    "ProductSupplyInput",
    "ProductAccessInput",
    "ProductAllocationInput",
    "CatchAllInput",
    "ScenarioDecision",
    "ReviewResult",
    "ProcessingResult",
    "DraftEmail",
    "FinalEmail",
    "InventoryRecord",
    "CustomerRecord",
    "AllocationRecord",
    "ProductRecord",
    "PastEmailRecord",
]
