"""Allocation API (S3): Allocation simulation from DB."""

import asyncio
from typing import Any

from opentelemetry.trace import SpanKind

from src.db.repositories.allocation_repo import fetch as allocation_repo_fetch
from src.models.inputs import ProductAllocationInput
from src.triggers.registry import register_trigger
from src.utils.logger import log_agent_step
from src.utils.observability import span_attributes_for_workflow_step, set_span_input_output
from src.utils.tracing import get_tracer


@register_trigger("allocation_api")
async def allocation_api_simulate(
    inputs: ProductAllocationInput,
    s3_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fetch from DB (AllocationRecord); optional s3_context from S3 scaffold merged into result."""
    tracer = get_tracer()
    ndc_str = str(getattr(inputs, "ndc", "") or "")
    dist_str = str(getattr(inputs, "distributor", "") or "")
    attrs = {
        "api.name": "allocation",
        "api.ndc": ndc_str,
        "api.distributor": dist_str,
        **span_attributes_for_workflow_step("TOOL", input_summary={"ndc": ndc_str, "distributor": dist_str}),
    }
    with tracer.start_as_current_span("allocation_api_call", kind=SpanKind.INTERNAL, attributes=attrs) as span:
        log_agent_step("Trigger", "Allocation simulation (db)", {"ndc": inputs.ndc, "distributor": inputs.distributor})
        result = await asyncio.to_thread(allocation_repo_fetch, inputs, s3_context)
        span.set_attribute("api.records_found", len(result["allocation_records"]))
        span.set_attribute("api.total_quantity_allocated", result["total_quantity_allocated"])
        span.set_attribute("api.total_quantity_used", result["total_quantity_used"])
        set_span_input_output(
            span,
            output_summary={
                "records_found": len(result["allocation_records"]),
                "total_quantity_allocated": result["total_quantity_allocated"],
                "total_quantity_used": result["total_quantity_used"],
            },
        )
        log_agent_step(
            "Trigger",
            "Allocation result",
            {
                "matches": len(result["allocation_records"]),
                "allocated": result["total_quantity_allocated"],
                "used": result["total_quantity_used"],
            },
        )
        return result
