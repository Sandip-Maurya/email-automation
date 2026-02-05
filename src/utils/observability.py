"""Reusable helpers for observability: span attributes, previews, etc.

Use these when attaching human-readable, PII-safe content to traces (e.g. Phoenix).
"""

from src.models.email import EmailThread
from src.utils.body_sanitizer import sanitize_for_observability, OBSERVABILITY_MAX_CHARS


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
