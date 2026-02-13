"""Inventory API (S1): 852 / Value Track style data from DB."""

import asyncio
from typing import Any

from opentelemetry.trace import SpanKind

from src.db.repositories.inventory_repo import fetch as inventory_repo_fetch
from src.models.inputs import ProductSupplyInput
from src.triggers.registry import register_trigger
from src.utils.logger import log_agent_step
from src.utils.observability import span_attributes_for_workflow_step, set_span_input_output
from src.utils.tracing import get_tracer


@register_trigger("inventory_api")
async def inventory_api_fetch(inputs: ProductSupplyInput) -> dict[str, Any]:
    """Fetch from DB (InventorySnapshot); return records and total_quantity_available."""
    tracer = get_tracer()
    ndc_str = str(getattr(inputs, "ndc", "") or "")
    dist_str = str(getattr(inputs, "distributor", "") or "")
    attrs = {
        "api.name": "inventory",
        "api.ndc": ndc_str,
        "api.distributor": dist_str,
        **span_attributes_for_workflow_step("TOOL", input_summary={"ndc": ndc_str, "distributor": dist_str}),
    }
    with tracer.start_as_current_span("inventory_api_call", kind=SpanKind.INTERNAL, attributes=attrs) as span:
        log_agent_step("Trigger", "Inventory API fetch (db)", {"ndc": inputs.ndc, "distributor": inputs.distributor})
        result = await asyncio.to_thread(inventory_repo_fetch, inputs)
        span.set_attribute("api.records_found", len(result["records"]))
        span.set_attribute("api.total_quantity_available", result["total_quantity_available"])
        set_span_input_output(
            span,
            output_summary={
                "records_found": len(result["records"]),
                "total_quantity_available": result["total_quantity_available"],
            },
        )
        log_agent_step(
            "Trigger",
            "Calculate inventory",
            {"matches": len(result["records"]), "total_quantity": result["total_quantity_available"]},
        )
        return result
