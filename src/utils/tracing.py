"""OpenTelemetry tracing setup with Phoenix."""

from src.config import (
    PHOENIX_API_KEY,
    PHOENIX_COLLECTOR_ENDPOINT,
    PHOENIX_ENABLED,
    PHOENIX_PROJECT_NAME,
    PHOENIX_PROTOCOL,
)

_initialized = False


def _resolve_protocol() -> str:
    """Resolve protocol: env override, or http/protobuf for Phoenix Cloud (remote HTTPS)."""
    if PHOENIX_PROTOCOL in ("http/protobuf", "grpc"):
        return PHOENIX_PROTOCOL
    endpoint_lower = PHOENIX_COLLECTOR_ENDPOINT.lower()
    if "phoenix.arize.com" in endpoint_lower or (
        endpoint_lower.startswith("https://") and "localhost" not in endpoint_lower
    ):
        return "http/protobuf"
    return "infer"


def _resolve_endpoint(protocol: str) -> str:
    """Ensure HTTP endpoint includes /v1/traces path (OTLP spec)."""
    if protocol != "http/protobuf":
        return PHOENIX_COLLECTOR_ENDPOINT
    endpoint = PHOENIX_COLLECTOR_ENDPOINT.rstrip("/")
    if not endpoint.endswith("/v1/traces"):
        endpoint = f"{endpoint}/v1/traces"
    return endpoint


def init_tracing() -> None:
    """Initialize Phoenix OTEL tracing (call once at startup)."""
    global _initialized
    if _initialized or not PHOENIX_ENABLED:
        return

    from phoenix.otel import register

    protocol = _resolve_protocol()
    kwargs = {
        "project_name": PHOENIX_PROJECT_NAME,
        "endpoint": _resolve_endpoint(protocol),
        "protocol": protocol,
        "auto_instrument": False,
        # "set_global_tracer_provider": False,
    }
    if PHOENIX_API_KEY:
        kwargs["api_key"] = PHOENIX_API_KEY

    register(**kwargs)

    # Enable Pydantic AI built-in instrumentation (sends spans to global tracer)
    try:
        from pydantic_ai import Agent

        Agent.instrument_all()
    except ImportError:
        pass

    _initialized = True


def get_tracer():
    """Return the OpenTelemetry tracer (after init_tracing has run)."""
    from opentelemetry import trace

    return trace.get_tracer("email-automation", "0.1.0")
