"""Email Agent A11: Final formatting and output generation."""

from pydantic_ai import Agent

from src.models.outputs import DraftEmail, FinalEmail, ReviewResult
from src.utils.logger import log_agent_step


EMAIL_PROMPT = """You are Email Agent A11. You take a reviewed draft and produce the final email output.
If review status is "approved", format the email for sending (to, subject, body).
Use the reply-to name when provided to personalize the greeting (e.g., "Dear John," instead of "Dear Customer,").
If review status is "needs_human_review", add a brief header note that this draft is flagged for human review.
Output: to (optional), subject, body, review_status, and metadata (dict)."""


email_agent = Agent(
    "openai:gpt-4o-mini",
    output_type=FinalEmail,
    system_prompt=EMAIL_PROMPT,
    retries=1,
)


async def format_final_email(
    draft: DraftEmail,
    review: ReviewResult,
    reply_to: str | None = None,
    sender_name: str | None = None,
) -> FinalEmail:
    log_agent_step("A11", "Formatting final email", {"review_status": review.status})
    reply_to_name = sender_name or "Customer"
    prompt = f"""Draft:
Subject: {draft.subject}
Body: {draft.body}
Scenario: {draft.scenario}

Review: status={review.status}, confidence={review.confidence}, quality_score={review.quality_score}
Accuracy notes: {review.accuracy_notes}
Suggestions: {review.suggestions}

Reply-to name (use for greeting): {reply_to_name}
Reply-to email: {reply_to or 'Not specified'}

Produce final email: to (optional), subject, body, review_status, metadata. Use the reply-to name in the greeting when appropriate."""
    result = await email_agent.run(prompt)
    out = result.output
    if reply_to and not out.to:
        out.to = reply_to
    log_agent_step("A11", "Final email ready", {"subject": out.subject})
    return out
