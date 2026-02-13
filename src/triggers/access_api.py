"""Access API (S2): Class of Trade, LDN, REMS from DB."""

import asyncio
from typing import Any

from opentelemetry.trace import SpanKind

from src.db.repositories.customer_repo import fetch as customer_repo_fetch
from src.models.inputs import ProductAccessInput
from src.triggers.registry import register_trigger
from src.utils.logger import log_agent_step
from src.utils.observability import span_attributes_for_workflow_step, set_span_input_output
from src.utils.tracing import get_tracer


@register_trigger("access_api")
async def access_api_fetch(inputs: ProductAccessInput) -> dict[str, Any]:
    """Fetch from DB (Customer); return class_of_trade, rems_certified, is_340b, etc."""
    tracer = get_tracer()
    dea_str = str(getattr(inputs, "dea_number", "") or "")
    customer_str = str(getattr(inputs, "customer", "") or "")[:256]
    attrs = {
        "api.name": "access",
        "api.dea_number": dea_str,
        "api.customer": customer_str,
        **span_attributes_for_workflow_step("TOOL", input_summary={"dea_number": dea_str}),
    }
    with tracer.start_as_current_span("access_api_call", kind=SpanKind.INTERNAL, attributes=attrs) as span:
        log_agent_step("Trigger", "Access API fetch (db)", {"ndc": inputs.ndc, "dea": inputs.dea_number})
        result = await asyncio.to_thread(customer_repo_fetch, inputs)
        matched = result.get("customer_id") is not None
        span.set_attribute("api.matched", matched)
        set_span_input_output(span, output_summary={"matched": matched, "source": result.get("source", "db")})
        log_agent_step(
            "Trigger",
            "Customer match" if matched else "No customer match; returning defaults",
            {"customer_id": result.get("customer_id")},
        )
        return result
