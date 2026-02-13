"""Allocation repository: query AllocationRecord by ndc/distributor/year, return trigger-shaped dict."""

from typing import Any

from sqlalchemy import or_, select
from src.db import get_session
from src.db.models.allocation import AllocationRecord
from src.db.models.master import Distributor
from src.models.inputs import ProductAllocationInput


def fetch(
    inputs: ProductAllocationInput,
    s3_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Query allocation records by ndc, distributor, year range; return totals and list. Optionally merge s3_scaffold.

    Distributor filter matches both code (e.g. DIST-A) and name (e.g. Acme Distribution) via the distributors table.
    """
    with get_session() as session:
        ndc = (inputs.ndc or "").strip()
        dist = (inputs.distributor or "").strip().lower()
        year_start = inputs.year_start or 2025
        year_end = inputs.year_end or 2025
        q = (
            select(AllocationRecord)
            .where(AllocationRecord.year >= year_start, AllocationRecord.year <= year_end)
        )
        if ndc:
            q = q.where(AllocationRecord.ndc.like(f"%{ndc}%"))
        if dist:
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
                q = q.where(AllocationRecord.distributor.in_(dist_codes))
            else:
                q = q.where(AllocationRecord.distributor.ilike(f"%{dist}%"))
        rows = list(session.scalars(q).all())
        total_allocated = sum(r.quantity_allocated for r in rows)
        total_used = sum(r.quantity_used for r in rows)
        allocation_records = [
            {
                "ndc": r.ndc,
                "distributor": r.distributor,
                "year": r.year,
                "quantity_allocated": r.quantity_allocated,
                "quantity_used": r.quantity_used,
            }
            for r in rows
        ]
        result: dict[str, Any] = {
            "allocation_records": allocation_records,
            "total_quantity_allocated": total_allocated,
            "total_quantity_used": total_used,
            "year_start": year_start,
            "year_end": year_end,
            "source": "db",
            "spec_buy_note": "DB allocation data.",
        }
        if s3_context is not None:
            result["s3_scaffold"] = s3_context
        return result
