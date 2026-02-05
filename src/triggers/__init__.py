"""Mock API triggers for email automation."""

from src.triggers.inventory_api import inventory_api_fetch
from src.triggers.access_api import access_api_fetch
from src.triggers.allocation_api import allocation_api_simulate
from src.triggers.rag_search import rag_search_find_similar

__all__ = [
    "inventory_api_fetch",
    "access_api_fetch",
    "allocation_api_simulate",
    "rag_search_find_similar",
]
