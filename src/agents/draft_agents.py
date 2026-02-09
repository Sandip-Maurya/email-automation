"""Draft Email Agents A7 (Supply/Access) and A8 (Allocation/Catch-All)."""

from typing import Any

from src.agents.registry import get_agent, get_user_prompt_template
from src.models.outputs import DraftEmail
from src.utils.logger import log_agent_step


async def draft_supply_or_access(
    scenario: str,
    inputs: Any,
    trigger_data: dict[str, Any],
    original_subject: str,
) -> DraftEmail:
    log_agent_step("A7", "Drafting email (Supply/Access)", {"scenario": scenario})
    agent = get_agent("A7_draft", DraftEmail)
    template = get_user_prompt_template("A7_draft")
    prompt = template.format(
        original_subject=original_subject,
        inputs=inputs,
        trigger_data=trigger_data,
    )
    result = await agent.run(prompt)
    out = result.output
    out.scenario = scenario
    out.metadata["trigger_source"] = trigger_data.get("source", "")
    log_agent_step("A7", "Draft complete", {"subject": out.subject})
    return out


async def draft_allocation_or_catchall(
    scenario: str,
    inputs: Any,
    trigger_data: dict[str, Any],
    original_subject: str,
) -> DraftEmail:
    log_agent_step("A8", "Drafting email (Allocation/Catch-All)", {"scenario": scenario})
    agent = get_agent("A8_draft", DraftEmail)
    template = get_user_prompt_template("A8_draft")
    prompt = template.format(
        original_subject=original_subject,
        inputs=inputs,
        trigger_data=trigger_data,
    )
    result = await agent.run(prompt)
    out = result.output
    out.scenario = scenario
    out.metadata["trigger_source"] = trigger_data.get("source", "")
    log_agent_step("A8", "Draft complete", {"subject": out.subject})
    return out
