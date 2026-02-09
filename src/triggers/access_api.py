"""Mock Access API (S2): Class of Trade, LDN, REMS."""

from typing import Any

from src.models.inputs import ProductAccessInput
from src.triggers.registry import register_trigger
from src.utils.csv_loader import load_customers
from src.utils.logger import log_agent_step
from src.utils.tracing import get_tracer


def _parse_bool(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() in ("true", "1", "yes")
    return False


@register_trigger("access_api")
async def access_api_fetch(inputs: ProductAccessInput) -> dict[str, Any]:
    """Mock fetch for Class of Trade, LDN, REMS status."""
    tracer = get_tracer()
    with tracer.start_as_current_span(
        "access_api_call",
        attributes={
            "api.name": "access",
            "api.dea_number": str(getattr(inputs, "dea_number", "") or ""),
            "api.customer": str(getattr(inputs, "customer", "") or "")[:256],
        },
    ) as span:
        log_agent_step("Trigger", "Access API fetch (mock)", {"ndc": inputs.ndc, "dea": inputs.dea_number})
        rows = load_customers()
        dea = (inputs.dea_number or "").strip()
        customer = (inputs.customer or "").strip().lower()
        match = None
        for r in rows:
            r_dea = (r.get("dea_number") or "").strip()
            r_name = (r.get("name") or "").strip().lower()
            if (dea and r_dea == dea) or (customer and customer in r_name):
                match = r
                break
        if not match:
            span.set_attribute("api.matched", False)
            log_agent_step("Trigger", "No customer match; returning mock defaults", {})
            return {
                "class_of_trade": "Unknown",
                "rems_certified": False,
                "is_340b": inputs.is_340b,
                "source": "mock_access_default",
            }
        span.set_attribute("api.matched", True)
        span.set_attribute("api.customer_id", str(match.get("customer_id", "")))
        log_agent_step("Trigger", "Customer match found", {"customer_id": match.get("customer_id")})
        return {
            "class_of_trade": match.get("class_of_trade", "Unknown"),
            "rems_certified": _parse_bool(match.get("rems_certified")),
            "is_340b": _parse_bool(match.get("is_340b")),
            "address": match.get("address"),
            "customer_id": match.get("customer_id"),
            "source": "mock_access_api",
        }
