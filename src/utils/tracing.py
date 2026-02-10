"""OpenTelemetry tracing setup with Phoenix and OpenInference Pydantic AI."""

import logging
import os

from src.config import (
    DEPLOYMENT_ENVIRONMENT,
    PHOENIX_API_KEY,
    PHOENIX_COLLECTOR_ENDPOINT,
    PHOENIX_ENABLED,
    PHOENIX_PROJECT_NAME,
    PHOENIX_PROTOCOL,
    TRACE_DROP_CHILDREN_OF_SPANS,
)

logger = logging.getLogger(__name__)
_initialized = False
_tracer_provider = None


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


def _build_resource():
    """Build Resource with service identity and Phoenix project name."""
    from opentelemetry.sdk.resources import Resource

    attrs = {
        "service.name": PHOENIX_PROJECT_NAME,
        "service.version": "0.1.0",
        "deployment.environment": DEPLOYMENT_ENVIRONMENT,
    }
    try:
        from openinference.semconv.resource import ResourceAttributes as OIResourceAttributes

        attrs[OIResourceAttributes.PROJECT_NAME] = PHOENIX_PROJECT_NAME
    except ImportError:
        attrs["project.name"] = PHOENIX_PROJECT_NAME
    return Resource.create(attrs)


def _build_pipeline_with_openinference_first():
    """
    Build TracerProvider with OpenInferenceSpanProcessor first, then export to Phoenix.
    Order ensures Pydantic AI spans are enriched with OpenInference attributes before export.
    """
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    protocol = _resolve_protocol()
    endpoint = _resolve_endpoint(protocol)
    use_http = protocol in ("http/protobuf", "infer") or "6006" in endpoint or "/v1/traces" in endpoint

    headers = None
    if PHOENIX_API_KEY:
        headers = {"authorization": f"Bearer {PHOENIX_API_KEY}"}

    resource = _build_resource()
    provider = TracerProvider(resource=resource)

    try:
        from openinference.instrumentation.pydantic_ai import (
            OpenInferenceSpanProcessor,
            is_openinference_span,
        )

        provider.add_span_processor(
            OpenInferenceSpanProcessor(span_filter=is_openinference_span)
        )
    except ImportError as e:
        logger.warning(
            "OpenInferenceSpanProcessor not available; Pydantic AI spans may lack OpenInference schema: %s",
            e,
        )

    if use_http:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        exporter = OTLPSpanExporter(endpoint=endpoint, headers=headers)
    else:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )

        exporter = OTLPSpanExporter(endpoint=endpoint, headers=headers)

    from src.utils.span_filter import DropDescendantsFilterProcessor

    batch = BatchSpanProcessor(exporter)
    filter_processor = DropDescendantsFilterProcessor(
        batch,
        drop_children_of_names=set(TRACE_DROP_CHILDREN_OF_SPANS),
    )
    provider.add_span_processor(filter_processor)
    trace.set_tracer_provider(provider)
    return provider


def init_tracing() -> None:
    """Initialize Phoenix OTEL tracing (call once at startup).

    Uses OpenInferenceSpanProcessor before export so Pydantic AI spans
    are enriched with OpenInference attributes for Phoenix. Agents should
    be created with instrument=InstrumentationSettings(version=2) for full schema.
    """
    global _initialized, _tracer_provider
    if _initialized or not PHOENIX_ENABLED:
        return

    _tracer_provider = _build_pipeline_with_openinference_first()
    _initialized = True


def get_tracer():
    """Return the OpenTelemetry tracer (after init_tracing has run)."""
    from opentelemetry import trace

    return trace.get_tracer("email-automation", "0.1.0")


def get_tracer_provider():
    """Return the global tracer provider (for shutdown)."""
    from opentelemetry import trace

    return _tracer_provider if _tracer_provider is not None else trace.get_tracer_provider()


def shutdown_tracing() -> None:
    """Flush and shutdown the tracer provider so spans are exported before process exit."""
    from opentelemetry.sdk.trace import TracerProvider

    provider = get_tracer_provider()
    if isinstance(provider, TracerProvider):
        provider.force_flush(timeout_millis=5000)
        provider.shutdown()
