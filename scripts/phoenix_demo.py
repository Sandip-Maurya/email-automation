#!/usr/bin/env python3
"""
Standalone script to send sample traces and spans to the Phoenix dashboard.

Implements concepts we explored:
- Resource attributes (service identity)
- OpenInference span kind (so Phoenix shows CHAIN/TOOL/AGENT instead of "unknown")
- OTel SpanKind (SERVER, INTERNAL)
- Context: parent-child link without deep nesting (set_span_in_context + pass context, and attach/detach)
- Span events (annotations), status (OK/ERROR), input/output attributes
- Optional filtering via FilteringSpanProcessor (documented; use when building custom pipeline)
- Flush on exit so spans are sent before the process exits

Usage:
  1. Start Phoenix:  phoenix serve
  2. Run this script:  uv run python scripts/phoenix_demo.py

Environment (optional):
  PHOENIX_COLLECTOR_ENDPOINT  default: http://localhost:6006/v1/traces
  PHOENIX_PROJECT_NAME        default: phoenix-demo
  PHOENIX_API_KEY             optional, for Phoenix Cloud

Does not import or modify the main application.
"""

import os
import time
from dotenv import load_dotenv

load_dotenv()
# -----------------------------------------------------------------------------
# 1. Configuration (no src imports)
# -----------------------------------------------------------------------------
ENDPOINT = os.getenv("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006/v1/traces").rstrip("/")
if not ENDPOINT.endswith("/v1/traces"):
    ENDPOINT = f"{ENDPOINT}/v1/traces"
PROJECT_NAME = os.getenv("PHOENIX_PROJECT_NAME", "phoenix-demo")
API_KEY = os.getenv("PHOENIX_API_KEY", "")


def _protocol():
    if "phoenix.arize.com" in ENDPOINT.lower() or (
        ENDPOINT.startswith("https://") and "localhost" not in ENDPOINT.lower()
    ):
        return "http/protobuf"
    return "infer"


# -----------------------------------------------------------------------------
# 2. Optional: FilteringSpanProcessor (use when building TracerProvider manually)
# -----------------------------------------------------------------------------
class FilteringSpanProcessor:
    """
    Forwards only spans whose names are in allow_names (if set).
    Wrap your existing SpanProcessor to drop unwanted spans before export.
    """

    def __init__(self, next_processor, allow_names: set[str] | None = None):
        self._next = next_processor
        self._allow_names = allow_names or set()

    def on_start(self, parent, context):
        self._next.on_start(parent, context)

    def on_end(self, span):
        if self._allow_names and getattr(span, "name", None) not in self._allow_names:
            return
        self._next.on_end(span)

    def shutdown(self):
        self._next.shutdown()

    def force_flush(self, timeout_millis: int | None = None):
        return self._next.force_flush(timeout_millis)


# -----------------------------------------------------------------------------
# 3. Register Phoenix with optional Resource (service identity)
# -----------------------------------------------------------------------------
from opentelemetry.sdk.resources import Resource

resource = Resource.create({
    "service.name": PROJECT_NAME,
    "service.version": "1.0.0",
    "deployment.environment": os.getenv("DEPLOYMENT_ENVIRONMENT", "demo"),
})

kwargs = {
    "project_name": PROJECT_NAME,
    "endpoint": ENDPOINT,
    "protocol": _protocol(),
    "auto_instrument": False,
}
if API_KEY:
    kwargs["api_key"] = API_KEY

from phoenix.otel import register

try:
    tracer_provider = register(**kwargs, resource=resource)
except TypeError:
    # Older phoenix.otel may not accept resource
    tracer_provider = register(**kwargs)

# -----------------------------------------------------------------------------
# 4. Tracer and OpenInference / OTel imports
# -----------------------------------------------------------------------------
from opentelemetry import trace, context
from opentelemetry.trace import Status, StatusCode, SpanKind, set_span_in_context
from openinference.semconv import trace as semconv_trace

tracer = trace.get_tracer("phoenix-demo-script", "1.0.0")
SpanKindValues = semconv_trace.OpenInferenceSpanKindValues

# -----------------------------------------------------------------------------
# 5. Helpers that create child spans (used with context to avoid deep nesting)
# -----------------------------------------------------------------------------


def do_work_with_passed_context(ctx):
    """Create a child span by receiving parent context (no physical nesting)."""
    with tracer.start_as_current_span(
        "demo.work",
        context=ctx,
        kind=SpanKind.INTERNAL,
        attributes={
            semconv_trace.SpanAttributes.OPENINFERENCE_SPAN_KIND: SpanKindValues.TOOL.value,
            semconv_trace.SpanAttributes.INPUT_VALUE: '{"step": "process"}',
            semconv_trace.SpanAttributes.INPUT_MIME_TYPE: "application/json",
            "input.step": "process",
        },
    ) as child:
        child.set_attribute(semconv_trace.SpanAttributes.OUTPUT_VALUE, '{"items_processed": 3}')
        child.set_attribute(semconv_trace.SpanAttributes.OUTPUT_MIME_TYPE, "application/json")
        child.set_attribute("output.items_processed", 3)
        child.add_event("batch.completed", attributes={"count": 3})
        time.sleep(0.05)
        child.set_status(Status(StatusCode.OK))


def do_step_one():
    """Runs in 'current' context (set by attach). Becomes child of attached parent."""
    with tracer.start_as_current_span(
        "demo.step_one",
        kind=SpanKind.INTERNAL,
        attributes={
            semconv_trace.SpanAttributes.OPENINFERENCE_SPAN_KIND: SpanKindValues.CHAIN.value,
            semconv_trace.SpanAttributes.INPUT_VALUE: '{"action": "validate"}',
            semconv_trace.SpanAttributes.INPUT_MIME_TYPE: "application/json",
            "input.action": "validate",
        },
    ) as span:
        span.set_attribute(semconv_trace.SpanAttributes.OUTPUT_VALUE, '{"status": "ok"}')
        span.set_attribute(semconv_trace.SpanAttributes.OUTPUT_MIME_TYPE, "application/json")
        span.set_attribute("output.status", "ok")
        span.add_event("validation.passed")
        time.sleep(0.02)


def do_step_two():
    """Also runs in attached context; sibling of step_one under same parent."""
    with tracer.start_as_current_span(
        "demo.step_two",
        kind=SpanKind.INTERNAL,
        attributes={
            semconv_trace.SpanAttributes.OPENINFERENCE_SPAN_KIND: SpanKindValues.TOOL.value,
            semconv_trace.SpanAttributes.INPUT_VALUE: '{"action": "transform"}',
            semconv_trace.SpanAttributes.INPUT_MIME_TYPE: "application/json",
            "input.action": "transform",
        },
    ) as span:
        span.set_attribute(semconv_trace.SpanAttributes.OUTPUT_VALUE, '{"records": 2}')
        span.set_attribute(semconv_trace.SpanAttributes.OUTPUT_MIME_TYPE, "application/json")
        span.set_attribute("output.records", 2)
        span.add_event("transform.done")
        time.sleep(0.02)


# -----------------------------------------------------------------------------
# 6. Trace 1: Parent + child via passed context (flattened structure)
# -----------------------------------------------------------------------------
with tracer.start_as_current_span(
    "demo.request",
    kind=SpanKind.SERVER,
    attributes={
        semconv_trace.SpanAttributes.OPENINFERENCE_SPAN_KIND: SpanKindValues.CHAIN.value,
        semconv_trace.SpanAttributes.INPUT_VALUE: '{"request_id": "req-001", "path": "/demo", "method": "GET"}',
        semconv_trace.SpanAttributes.INPUT_MIME_TYPE: "application/json",
        "input.request_id": "req-001",
        "input.path": "/demo",
        "input.method": "GET",
    },
) as parent:
    parent.set_attribute(semconv_trace.SpanAttributes.OUTPUT_VALUE, '{"status": "ok"}')
    parent.set_attribute(semconv_trace.SpanAttributes.OUTPUT_MIME_TYPE, "application/json")
    parent.set_attribute("output.status", "ok")
    parent.add_event("request.started", attributes={"at": "entry"})
    time.sleep(0.05)

    ctx = set_span_in_context(parent)
    do_work_with_passed_context(ctx)

    parent.add_event("request.completed", attributes={"at": "exit"})

# -----------------------------------------------------------------------------
# 7. Trace 2: Parent + children via attach/detach (no context passed to helpers)
# -----------------------------------------------------------------------------
with tracer.start_as_current_span(
    "demo.pipeline",
    kind=SpanKind.INTERNAL,
    attributes={
        semconv_trace.SpanAttributes.OPENINFERENCE_SPAN_KIND: SpanKindValues.AGENT.value,
        semconv_trace.SpanAttributes.INPUT_VALUE: '{"pipeline_id": "pipeline-1"}',
        semconv_trace.SpanAttributes.INPUT_MIME_TYPE: "application/json",
        "input.pipeline_id": "pipeline-1",
    },
) as parent:
    parent.add_event("pipeline.started")
    token = context.attach(set_span_in_context(parent))
    try:
        do_step_one()
        do_step_two()
    finally:
        context.detach(token)
    parent.set_attribute(semconv_trace.SpanAttributes.OUTPUT_VALUE, '{"status": "ok"}')
    parent.set_attribute(semconv_trace.SpanAttributes.OUTPUT_MIME_TYPE, "application/json")
    parent.set_attribute("output.status", "ok")
    parent.add_event("pipeline.completed")

# -----------------------------------------------------------------------------
# 8. Trace 3: Error span (status ERROR + record_exception)
# -----------------------------------------------------------------------------
with tracer.start_as_current_span(
    "demo.failing_operation",
    kind=SpanKind.INTERNAL,
    attributes={
        semconv_trace.SpanAttributes.OPENINFERENCE_SPAN_KIND: SpanKindValues.TOOL.value,
        semconv_trace.SpanAttributes.INPUT_VALUE: '{"operation": "validate", "user_id": "user-42"}',
        semconv_trace.SpanAttributes.INPUT_MIME_TYPE: "application/json",
        "input.operation": "validate",
        "input.user_id": "user-42",
    },
) as span:
    span.set_attribute(semconv_trace.SpanAttributes.OUTPUT_VALUE, '{"error_code": "VALIDATION_FAILED"}')
    span.set_attribute(semconv_trace.SpanAttributes.OUTPUT_MIME_TYPE, "application/json")
    span.set_attribute("output.error_code", "VALIDATION_FAILED")
    span.set_status(Status(StatusCode.ERROR, "Simulated validation error for demo"))
    span.record_exception(ValueError("Simulated validation error for demo"))
    span.add_event("error.recorded")
    time.sleep(0.02)

# -----------------------------------------------------------------------------
# 9. Trace 4: Simple one-span trace
# -----------------------------------------------------------------------------
with tracer.start_as_current_span(
    "demo.health_check",
    kind=SpanKind.INTERNAL,
    attributes={
        semconv_trace.SpanAttributes.OPENINFERENCE_SPAN_KIND: SpanKindValues.CHAIN.value,
        semconv_trace.SpanAttributes.INPUT_VALUE: '{"check": "ping"}',
        semconv_trace.SpanAttributes.INPUT_MIME_TYPE: "application/json",
        semconv_trace.SpanAttributes.OUTPUT_VALUE: '{"status": "healthy"}',
        semconv_trace.SpanAttributes.OUTPUT_MIME_TYPE: "application/json",
        "input.check": "ping",
        "output.status": "healthy",
    },
):
    time.sleep(0.01)

# -----------------------------------------------------------------------------
# 10. Flush so spans are sent to Phoenix before exit
# -----------------------------------------------------------------------------
from opentelemetry.sdk.trace import TracerProvider

provider = tracer_provider if tracer_provider is not None else trace.get_tracer_provider()
if isinstance(provider, TracerProvider):
    provider.force_flush(timeout_millis=5000)
    provider.shutdown()

print(f"Done. Check Phoenix project '{PROJECT_NAME}' at {ENDPOINT.replace('/v1/traces', '')} for traces.")
