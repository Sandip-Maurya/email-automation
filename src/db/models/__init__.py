"""Re-export all ORM models so Base.metadata has all tables."""

from src.db.models.allocation import (
    AllocationRecord,
    AllocationRule,
    DataDictionary,
    SpecBuyReport,
)
from src.db.models.inventory import InventorySnapshot
from src.db.models.master import Contact, Customer, Distributor, Location, Product

__all__ = [
    "Location",
    "Distributor",
    "Product",
    "Customer",
    "Contact",
    "InventorySnapshot",
    "AllocationRule",
    "AllocationRecord",
    "SpecBuyReport",
    "DataDictionary",
]
