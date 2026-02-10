"""Reusable helpers for observability: span attributes, previews, etc.

Use these when attaching human-readable, PII-safe content to traces (e.g. Phoenix).
"""

import json
from typing import Any

from src.models.email import EmailThread
from src.utils.body_sanitizer import sanitize_for_observability, OBSERVABILITY_MAX_CHARS

# OpenInference semantic conventions for Phoenix (kind, input/output columns)
try:
    from openinference.semconv import trace as _semconv_trace

    _OPENINFERENCE_SPAN_KIND = _semconv_trace.SpanAttributes.OPENINFERENCE_SPAN_KIND
    _INPUT_VALUE = _semconv_trace.SpanAttributes.INPUT_VALUE
    _INPUT_MIME_TYPE = _semconv_trace.SpanAttributes.INPUT_MIME_TYPE
    _OUTPUT_VALUE = _semconv_trace.SpanAttributes.OUTPUT_VALUE
    _OUTPUT_MIME_TYPE = _semconv_trace.SpanAttributes.OUTPUT_MIME_TYPE
    _SpanKindValues = _semconv_trace.OpenInferenceSpanKindValues
except ImportError:
    _OPENINFERENCE_SPAN_KIND = "openinference.span.kind"
    _INPUT_VALUE = "input.value"
    _INPUT_MIME_TYPE = "input.mime_type"
    _OUTPUT_VALUE = "output.value"
    _OUTPUT_MIME_TYPE = "output.mime_type"
    _SpanKindValues = None


def span_attributes_for_workflow_step(
    openinference_kind: str,
    input_summary: dict[str, Any] | str | None = None,
    output_summary: dict[str, Any] | str | None = None,
) -> dict[str, Any]:
    """Build span attributes for Phoenix: OpenInference kind and input/output.value.

    Use these so Phoenix UI shows kind and populates input/output columns.
    Keep payloads small and PII-safe (ids, counts, scenario names).

    Args:
        openinference_kind: One of CHAIN, TOOL, AGENT (OpenInferenceSpanKindValues).
        input_summary: Dict or JSON string for input.value.
        output_summary: Dict or JSON string for output.value.

    Returns:
        Dict of attributes to pass to start_as_current_span(attributes=...) or set_attribute.
    """
    attrs: dict[str, Any] = {}
    if _SpanKindValues is not None:
        kind_val = getattr(_SpanKindValues, openinference_kind, None)
        if kind_val is not None:
            attrs[_OPENINFERENCE_SPAN_KIND] = kind_val.value
        else:
            attrs[_OPENINFERENCE_SPAN_KIND] = openinference_kind
    else:
        attrs[_OPENINFERENCE_SPAN_KIND] = openinference_kind

    if input_summary is not None:
        s = input_summary if isinstance(input_summary, str) else json.dumps(input_summary)
        attrs[_INPUT_VALUE] = s
        attrs[_INPUT_MIME_TYPE] = "application/json"
    if output_summary is not None:
        s = output_summary if isinstance(output_summary, str) else json.dumps(output_summary)
        attrs[_OUTPUT_VALUE] = s
        attrs[_OUTPUT_MIME_TYPE] = "application/json"
    return attrs


def set_span_input_output(
    span: Any,
    input_summary: dict[str, Any] | str | None = None,
    output_summary: dict[str, Any] | str | None = None,
) -> None:
    """Set input.value and output.value (and mime_type) on an existing span."""
    if input_summary is not None:
        s = input_summary if isinstance(input_summary, str) else json.dumps(input_summary)
        span.set_attribute(_INPUT_VALUE, s)
        span.set_attribute(_INPUT_MIME_TYPE, "application/json")
    if output_summary is not None:
        s = output_summary if isinstance(output_summary, str) else json.dumps(output_summary)
        span.set_attribute(_OUTPUT_VALUE, s)
        span.set_attribute(_OUTPUT_MIME_TYPE, "application/json")


def thread_preview_for_observability(thread: EmailThread) -> str:
    """Build a PII-redacted, length-limited preview of an email thread for span attributes.

    Uses the observability pipeline (clean, redact PII, truncate). Safe to attach to
    root or child spans so the same input is visible in one place.

    Usage:
        from src.utils.observability import thread_preview_for_observability

        root_span.set_attribute("workflow.input_preview", thread_preview_for_observability(thread))
    """
    parts = []
    for e in thread.emails:
        clean_body = sanitize_for_observability(e.body or "", content_type="text")
        parts.append(f"From: {e.sender}\nSubject: {e.subject}\n{clean_body}")
    preview = "\n\n---\n\n".join(parts)
    if len(preview) > OBSERVABILITY_MAX_CHARS:
        preview = preview[:OBSERVABILITY_MAX_CHARS] + "\n\n[Preview truncated...]"
    return preview
