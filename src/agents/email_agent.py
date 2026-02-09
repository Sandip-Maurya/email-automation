"""Email Agent A11: Final formatting and output generation."""

from src.agents.registry import get_agent, get_user_prompt_template
from src.models.outputs import DraftEmail, FinalEmail, ReviewResult
from src.utils.logger import log_agent_step


async def format_final_email(
    draft: DraftEmail,
    review: ReviewResult,
    reply_to: str | None = None,
    sender_name: str | None = None,
) -> FinalEmail:
    log_agent_step("A11", "Formatting final email", {"review_status": review.status})
    reply_to_name = sender_name or "Customer"
    agent = get_agent("A11_format", FinalEmail)
    template = get_user_prompt_template("A11_format")
    prompt = template.format(
        subject=draft.subject,
        body=draft.body,
        scenario=draft.scenario,
        review_status=review.status,
        review_confidence=review.confidence,
        quality_score=review.quality_score,
        accuracy_notes=review.accuracy_notes,
        suggestions=review.suggestions,
        reply_to_name=reply_to_name,
        reply_to_email=reply_to or "Not specified",
    )
    result = await agent.run(prompt)
    out = result.output
    if reply_to and not out.to:
        out.to = reply_to
    log_agent_step("A11", "Final email ready", {"subject": out.subject})
    return out
