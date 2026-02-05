"""Draft Email Agents A7 (Supply/Access) and A8 (Allocation/Catch-All)."""

from typing import Any

from pydantic_ai import Agent

from src.models.outputs import DraftEmail
from src.utils.logger import log_agent_step


# A7: Supply and Access draft
A7_PROMPT = """You are Draft Email Agent A7 for Product Supply (S1) and Product Access (S2).
Given extracted inputs and data from the trigger script (inventory or access/REMS/Class of Trade),
write a professional, concise email reply. Use the data provided. Do not invent data.
Output: subject (string) and body (string). Keep tone professional and pharma-appropriate."""


draft_agent_a7 = Agent(
    "openai:gpt-4o-mini",
    output_type=DraftEmail,
    system_prompt=A7_PROMPT,
    retries=1,
)


async def draft_supply_or_access(
    scenario: str,
    inputs: Any,
    trigger_data: dict[str, Any],
    original_subject: str,
) -> DraftEmail:
    log_agent_step("A7", "Drafting email (Supply/Access)", {"scenario": scenario})
    prompt = f"""Original email subject: {original_subject}

Extracted inputs: {inputs}

Trigger/API data: {trigger_data}

Write a reply email: subject and body (professional, accurate)."""
    result = await draft_agent_a7.run(prompt)
    out = result.output
    out.scenario = scenario
    out.metadata["trigger_source"] = trigger_data.get("source", "")
    log_agent_step("A7", "Draft complete", {"subject": out.subject})
    return out


# A8: Allocation and Catch-All draft
A8_PROMPT = """You are Draft Email Agent A8 for Product Allocation (S3) and Catch-All (S4).
Given extracted inputs and either allocation data or similar past emails (with citations),
write a professional, concise email reply. Use the data provided. Do not invent data.
For Catch-All, you may reference similar past emails. Output: subject and body. Professional tone."""

draft_agent_a8 = Agent(
    "openai:gpt-4o-mini",
    output_type=DraftEmail,
    system_prompt=A8_PROMPT,
    retries=1,
)


async def draft_allocation_or_catchall(
    scenario: str,
    inputs: Any,
    trigger_data: dict[str, Any],
    original_subject: str,
) -> DraftEmail:
    log_agent_step("A8", "Drafting email (Allocation/Catch-All)", {"scenario": scenario})
    prompt = f"""Original email subject: {original_subject}

Extracted inputs: {inputs}

Trigger/API data (allocation or similar emails): {trigger_data}

Write a reply email: subject and body (professional, accurate)."""
    result = await draft_agent_a8.run(prompt)
    out = result.output
    out.scenario = scenario
    out.metadata["trigger_source"] = trigger_data.get("source", "")
    log_agent_step("A8", "Draft complete", {"subject": out.subject})
    return out
