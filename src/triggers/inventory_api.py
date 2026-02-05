"""Mock Inventory API (S1): 852 / Value Track style data and calculate inventory."""

from typing import Any

from src.models.inputs import ProductSupplyInput
from src.models.data import InventoryRecord
from src.utils.csv_loader import load_inventory
from src.utils.logger import log_agent_step
from src.utils.tracing import get_tracer


def _parse_inventory_rows(rows: list[dict[str, Any]]) -> list[InventoryRecord]:
    out = []
    for r in rows:
        try:
            qty = int(r.get("quantity_available", 0))
        except (TypeError, ValueError):
            qty = 0
        out.append(
            InventoryRecord(
                ndc=r.get("ndc", ""),
                product_name=r.get("product_name", ""),
                location=r.get("location", ""),
                quantity_available=qty,
                distributor=r.get("distributor", ""),
            )
        )
    return out


async def inventory_api_fetch(inputs: ProductSupplyInput) -> dict[str, Any]:
    """Mock fetch from 852 (CDP/Azure) and Value Track (IQVIA), then calculate inventory."""
    tracer = get_tracer()
    ndc_str = str(getattr(inputs, "ndc", "") or "")
    with tracer.start_as_current_span(
        "inventory_api_call",
        attributes={
            "api.name": "inventory",
            "api.ndc": ndc_str,
            "api.distributor": str(getattr(inputs, "distributor", "") or ""),
        },
    ) as span:
        log_agent_step("Trigger", "Inventory API fetch (mock)", {"ndc": inputs.ndc, "distributor": inputs.distributor})
        rows = load_inventory()
        records = _parse_inventory_rows(rows)
        ndc = (inputs.ndc or "").strip()
        dist = (inputs.distributor or "").strip().lower()
        loc = (inputs.location or "").strip().lower()
        matching = [
            r for r in records
            if (not ndc or ndc in r.ndc)
            and (not dist or dist in r.distributor.lower())
            and (not loc or loc in r.location.lower())
        ]
        total_qty = sum(r.quantity_available for r in matching)
        span.set_attribute("api.records_found", len(matching))
        span.set_attribute("api.total_quantity_available", total_qty)
        log_agent_step("Trigger", "Calculate inventory", {"matches": len(matching), "total_quantity": total_qty})
        return {
            "records": [r.model_dump() for r in matching],
            "total_quantity_available": total_qty,
            "source": "mock_852_value_track",
        }
