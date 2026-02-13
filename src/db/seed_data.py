"""Seed DB from CSV files when tables are first created."""

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from src.db.models.allocation import AllocationRecord
from src.db.models.inventory import InventorySnapshot
from src.db.models.master import Customer, Distributor, Location, Product
from src.utils.csv_loader import (
    load_allocations,
    load_customers,
    load_distributors,
    load_inventory,
    load_locations,
    load_products,
)
from src.utils.logger import get_logger

logger = get_logger("email_automation.db.seed_data")


def _parse_bool(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return (val or "").strip().lower() in ("true", "1", "yes")
    return False


def _parse_int(val: Any, default: int = 0) -> int:
    try:
        return int(val) if val is not None and str(val).strip() else default
    except (TypeError, ValueError):
        return default


def _parse_date(val: Any) -> date | None:
    if val is None or not str(val).strip():
        return None
    s = str(val).strip()
    try:
        return date.fromisoformat(s[:10])
    except (TypeError, ValueError):
        return None


def seed_mock_data(session: Session) -> None:
    """Read mock data from CSV files under data/ and insert into tables. FK order: locations, distributors, products, customers, inventory_snapshots, allocation_records."""
    # 1) Locations
    loc_rows = load_locations()
    code_to_location_id: dict[str, int] = {}
    for r in loc_rows:
        code = (r.get("code") or "").strip()
        if not code:
            continue
        loc = Location(
            code=code,
            name=(r.get("name") or "").strip() or None,
            region=(r.get("region") or "").strip() or None,
            is_active=True,
        )
        session.add(loc)
        session.flush()
        code_to_location_id[code] = loc.id
    if loc_rows:
        logger.info("seed_data.locations", count=len(code_to_location_id))

    # 2) Distributors
    dist_rows = load_distributors()
    code_to_distributor_id: dict[str, int] = {}
    for r in dist_rows:
        code = (r.get("code") or "").strip()
        if not code:
            continue
        d = Distributor(
            code=code,
            name=(r.get("name") or "").strip() or None,
            is_active=True,
        )
        session.add(d)
        session.flush()
        code_to_distributor_id[code] = d.id
    if dist_rows:
        logger.info("seed_data.distributors", count=len(code_to_distributor_id))

    # 3) Products
    prod_rows = load_products()
    for r in prod_rows:
        ndc = (r.get("ndc") or "").strip()
        if not ndc:
            continue
        session.add(
            Product(
                ndc=ndc,
                brand_name=(r.get("brand_name") or "").strip() or None,
                product_name=(r.get("product_name") or "").strip() or None,
                description=(r.get("description") or "").strip() or None,
                is_active=True,
            )
        )
    if prod_rows:
        session.flush()
        logger.info("seed_data.products", count=len(prod_rows))

    # 4) Customers (distributor_id from code)
    cust_rows = load_customers()
    for r in cust_rows:
        customer_id = (r.get("customer_id") or "").strip()
        if not customer_id:
            continue
        dist_code = (r.get("distributor") or "").strip()
        distributor_id = code_to_distributor_id.get(dist_code) if dist_code else None
        session.add(
            Customer(
                customer_id=customer_id,
                name=(r.get("name") or "").strip() or None,
                dea_number=(r.get("dea_number") or "").strip() or None,
                address=(r.get("address") or "").strip() or None,
                class_of_trade=(r.get("class_of_trade") or "").strip() or None,
                rems_certified=_parse_bool(r.get("rems_certified")),
                is_340b=_parse_bool(r.get("is_340b")),
                ldn=(r.get("ldn") or "").strip() or None,
                distributor_id=distributor_id,
                is_active=True,
                source="seed",
            )
        )
    if cust_rows:
        session.flush()
        logger.info("seed_data.customers", count=len(cust_rows))

    # 5) Inventory snapshots
    inv_rows = load_inventory()
    today = date.today()
    for r in inv_rows:
        ndc = (r.get("ndc") or "").strip()
        if not ndc:
            continue
        snapshot_d = _parse_date(r.get("snapshot_date")) or today
        session.add(
            InventorySnapshot(
                ndc=ndc,
                product_name=(r.get("product_name") or "").strip() or None,
                location=(r.get("location") or "").strip() or None,
                distributor=(r.get("distributor") or "").strip() or None,
                quantity_available=_parse_int(r.get("quantity_available")),
                snapshot_date=snapshot_d,
                source=(r.get("source") or "seed").strip() or None,
            )
        )
    if inv_rows:
        session.flush()
        logger.info("seed_data.inventory_snapshots", count=len(inv_rows))

    # 6) Allocation records
    alloc_rows = load_allocations()
    for r in alloc_rows:
        ndc = (r.get("ndc") or "").strip()
        if not ndc:
            continue
        session.add(
            AllocationRecord(
                ndc=ndc,
                distributor=(r.get("distributor") or "").strip() or None,
                year=_parse_int(r.get("year"), 2025),
                quantity_allocated=_parse_int(r.get("quantity_allocated")),
                quantity_used=_parse_int(r.get("quantity_used")),
                source=(r.get("source") or "seed").strip() or None,
            )
        )
    if alloc_rows:
        session.flush()
        logger.info("seed_data.allocation_records", count=len(alloc_rows))
