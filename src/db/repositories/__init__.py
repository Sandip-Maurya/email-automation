"""DB repositories: sync functions that return trigger-shaped dicts."""

from src.db.repositories.allocation_repo import fetch as allocation_fetch
from src.db.repositories.customer_repo import fetch as customer_fetch
from src.db.repositories.inventory_repo import fetch as inventory_fetch

__all__ = ["inventory_fetch", "customer_fetch", "allocation_fetch"]
