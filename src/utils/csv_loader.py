"""Load mock data from CSV files."""

from pathlib import Path
from typing import Any

from src.config import DATA_DIR


def _read_csv(path: Path) -> list[dict[str, Any]]:
    """Read a CSV file and return list of row dicts."""
    if not path.exists():
        return []
    import csv
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def load_emails_csv(csv_path: Path | None = None) -> list[dict[str, Any]]:
    """Load emails from emails.csv."""
    path = csv_path or DATA_DIR / "emails.csv"
    return _read_csv(path)


def load_inventory(csv_path: Path | None = None) -> list[dict[str, Any]]:
    """Load inventory data from inventory.csv."""
    path = csv_path or DATA_DIR / "inventory.csv"
    return _read_csv(path)


def load_customers(csv_path: Path | None = None) -> list[dict[str, Any]]:
    """Load customer data from customers.csv."""
    path = csv_path or DATA_DIR / "customers.csv"
    return _read_csv(path)


def load_allocations(csv_path: Path | None = None) -> list[dict[str, Any]]:
    """Load allocation data from allocations.csv."""
    path = csv_path or DATA_DIR / "allocations.csv"
    return _read_csv(path)


def load_products(csv_path: Path | None = None) -> list[dict[str, Any]]:
    """Load product catalog from products.csv."""
    path = csv_path or DATA_DIR / "products.csv"
    return _read_csv(path)


def load_past_emails(csv_path: Path | None = None) -> list[dict[str, Any]]:
    """Load past emails for RAG from past_emails.csv."""
    path = csv_path or DATA_DIR / "past_emails.csv"
    return _read_csv(path)
