"""Mock Allocation API (S3): Allocation simulation and DCS-style data."""

from typing import Any

from opentelemetry.trace import SpanKind

from src.models.inputs import ProductAllocationInput
from src.triggers.registry import register_trigger
from src.utils.csv_loader import load_allocations
from src.utils.logger import log_agent_step
from src.utils.observability import span_attributes_for_workflow_step, set_span_input_output
from src.utils.tracing import get_tracer


@register_trigger("allocation_api")
async def allocation_api_simulate(
    inputs: ProductAllocationInput,
    s3_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Mock allocation simulation: pull allocation from DCS, spec-buy style metrics.
    Optional s3_context from S3 scaffold (A_D1–A_D4) is merged into result when provided."""
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
        log_agent_step("Trigger", "Allocation simulation (mock)", {"ndc": inputs.ndc, "distributor": inputs.distributor})
        rows = load_allocations()
        ndc = (inputs.ndc or "").strip()
        dist = (inputs.distributor or "").strip().lower()
        year_start = inputs.year_start or 2025
        year_end = inputs.year_end or 2025
        matching = [
            r for r in rows
            if (not ndc or ndc in (r.get("ndc") or ""))
            and (not dist or dist in (r.get("distributor") or "").lower())
            and year_start <= int(r.get("year", 0)) <= year_end
        ]
        total_allocated = sum(int(r.get("quantity_allocated", 0)) for r in matching)
        total_used = sum(int(r.get("quantity_used", 0)) for r in matching)
        span.set_attribute("api.records_found", len(matching))
        span.set_attribute("api.total_quantity_allocated", total_allocated)
        span.set_attribute("api.total_quantity_used", total_used)
        set_span_input_output(span, output_summary={"records_found": len(matching), "total_quantity_allocated": total_allocated, "total_quantity_used": total_used})
        log_agent_step("Trigger", "Allocation result", {"matches": len(matching), "allocated": total_allocated, "used": total_used})
        result = {
            "allocation_records": matching,
            "total_quantity_allocated": total_allocated,
            "total_quantity_used": total_used,
            "year_start": year_start,
            "year_end": year_end,
            "source": "mock_dcs_allocation",
            "spec_buy_note": "Mock spec-buy report: purchase/dispense/build/burn/WAC not simulated.",
        }
        if s3_context is not None:
            result["s3_scaffold"] = s3_context
        return result
