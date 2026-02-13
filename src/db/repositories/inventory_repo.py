"""Inventory repository: query InventorySnapshot, return trigger-shaped dict."""

from typing import Any

from sqlalchemy import or_, select
from src.db import get_session
from src.db.models.inventory import InventorySnapshot
from src.db.models.master import Distributor
from src.models.inputs import ProductSupplyInput


def fetch(inputs: ProductSupplyInput) -> dict[str, Any]:
    """Query inventory by ndc/distributor/location; return records and total_quantity_available. Source 'db'.

    Distributor filter matches both code (e.g. DIST-A) and name (e.g. Acme Distribution) via the distributors table.
    """
    with get_session() as session:
        q = select(InventorySnapshot)
        ndc = (inputs.ndc or "").strip()
        dist = (inputs.distributor or "").strip().lower()
        loc = (inputs.location or "").strip().lower()
        if ndc:
            q = q.where(InventorySnapshot.ndc.like(f"%{ndc}%"))
        if dist:
            # Resolve distributor by code or name so "Acme Distribution" matches inventory with DIST-A
            dist_codes_subq = (
                select(Distributor.code)
                .where(
                    or_(
                        Distributor.code.ilike(f"%{dist}%"),
                        Distributor.name.ilike(f"%{dist}%"),
                    )
                )
            )
            dist_codes = list(session.scalars(dist_codes_subq).all())
            if dist_codes:
                q = q.where(InventorySnapshot.distributor.in_(dist_codes))
            else:
                # Fallback: match inventory.distributor directly (e.g. user sent code)
                q = q.where(InventorySnapshot.distributor.ilike(f"%{dist}%"))
        if loc:
            q = q.where(InventorySnapshot.location.ilike(f"%{loc}%"))
        rows = list(session.scalars(q).all())
        total = sum(r.quantity_available for r in rows)
        records = [
            {
                "ndc": r.ndc or "",
                "product_name": r.product_name or "",
                "location": r.location or "",
                "quantity_available": r.quantity_available,
                "distributor": r.distributor or "",
            }
            for r in rows
        ]
        return {
            "records": records,
            "total_quantity_available": total,
            "source": "db",
        }
