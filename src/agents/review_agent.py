"""Review Agent A10: Quality check, accuracy verification, confidence scoring."""

from typing import Any

from pydantic_ai import Agent

from src.models.outputs import DraftEmail, ReviewResult
from src.utils.logger import log_agent_step


REVIEW_PROMPT = """You are Review Agent A10. You review drafted email responses for:
1. Professional tone and grammar
2. Accuracy of data (does the draft match the context/data provided?)
3. Completeness of response

Output: status ("approved" or "needs_human_review"), confidence (0-1), quality_score (0-1),
accuracy_notes (list of strings), suggestions (list of strings).
If data seems inconsistent or tone is off, use needs_human_review and add notes."""

review_agent = Agent(
    "openai:gpt-4o-mini",
    output_type=ReviewResult,
    system_prompt=REVIEW_PROMPT,
    retries=1,
)


async def review_draft(draft: DraftEmail, context: Any) -> ReviewResult:
    log_agent_step("A10", "Reviewing draft", {"subject": draft.subject})
    prompt = f"""Draft to review:
Subject: {draft.subject}
Body: {draft.body}
Scenario: {draft.scenario}
Metadata: {draft.metadata}

Context/data used: {context}

Evaluate and return: status, confidence, quality_score, accuracy_notes, suggestions."""
    result = await review_agent.run(prompt)
    out = result.output
    log_agent_step("A10", f"Review: {out.status}", {"confidence": out.confidence, "quality_score": out.quality_score})
    return out
