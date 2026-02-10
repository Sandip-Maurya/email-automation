"""Mock RAG search (S4): Similar past emails for Catch-All."""

from typing import Any

from opentelemetry.trace import SpanKind

from src.models.inputs import CatchAllInput
from src.triggers.registry import register_trigger
from src.utils.csv_loader import load_past_emails
from src.utils.logger import log_agent_step
from src.utils.observability import span_attributes_for_workflow_step, set_span_input_output
from src.utils.tracing import get_tracer


@register_trigger("rag_search")
async def rag_search_find_similar(inputs: CatchAllInput) -> dict[str, Any]:
    """Mock RAG: return pre-defined similar past emails for demo."""
    tracer = get_tracer()
    topics_str = str(inputs.topics or [])[:512]
    attrs = {
        "api.name": "rag",
        "api.topics": topics_str,
        **span_attributes_for_workflow_step("TOOL", input_summary={"topics": inputs.topics or []}),
    }
    with tracer.start_as_current_span("rag_search_call", kind=SpanKind.INTERNAL, attributes=attrs) as span:
        log_agent_step("Trigger", "RAG search past emails (mock)", {"topics": inputs.topics})
        rows = load_past_emails()
        topics = [t.lower() for t in (inputs.topics or [])]
        question = (inputs.question_summary or "").lower()
        similar = []
        for r in rows:
            r_topic = (r.get("topic") or "").lower()
            r_subj = (r.get("subject") or "").lower()
            r_body = (r.get("body") or "").lower()
            if any(t in r_topic or t in r_subj or t in r_body for t in topics) or (question and (question in r_subj or question in r_body)):
                similar.append({
                    "email_id": r.get("email_id"),
                    "subject": r.get("subject"),
                    "body": r.get("body"),
                    "topic": r.get("topic"),
                })
        if not similar:
            similar = [{"email_id": r.get("email_id"), "subject": r.get("subject"), "body": r.get("body"), "topic": r.get("topic")} for r in rows[:3]]
        span.set_attribute("api.similar_emails_count", len(similar))
        set_span_input_output(span, output_summary={"similar_emails_count": len(similar), "source": "mock_rag_past_emails"})
        log_agent_step("Trigger", "RAG results", {"count": len(similar)})
        return {"similar_emails": similar, "source": "mock_rag_past_emails"}
