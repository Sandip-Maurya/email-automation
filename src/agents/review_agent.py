"""Review Agent A10: Quality check, accuracy verification, confidence scoring."""

from typing import Any

from src.agents.registry import get_agent, get_user_prompt_template
from src.models.outputs import DraftEmail, ReviewResult
from src.utils.logger import log_agent_step


async def review_draft(draft: DraftEmail, context: Any) -> ReviewResult:
    log_agent_step("A10", "Reviewing draft", {"subject": draft.subject})
    agent = get_agent("A10_review", ReviewResult)
    template = get_user_prompt_template("A10_review")
    prompt = template.format(
        subject=draft.subject,
        body=draft.body,
        scenario=draft.scenario,
        metadata=draft.metadata,
        context=context,
    )
    result = await agent.run(prompt)
    out = result.output
    log_agent_step("A10", f"Review: {out.status}", {"confidence": out.confidence, "quality_score": out.quality_score})
    return out
