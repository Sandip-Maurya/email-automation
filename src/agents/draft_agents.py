"""Draft Email Agents A6 (S1), A7 (S2), A8 (S3), A9 (S4)."""

from typing import Any

from src.agents.registry import get_agent, get_user_prompt_template
from src.models.outputs import DraftEmail
from src.utils.logger import log_agent_step


async def _draft_async(
    agent_id: str,
    log_name: str,
    scenario: str,
    inputs: Any,
    trigger_data: dict[str, Any],
    original_subject: str,
    email_thread: str = "",
) -> DraftEmail:
    agent = get_agent(agent_id, DraftEmail)
    template = get_user_prompt_template(agent_id)
    prompt = template.format(
        email_thread=email_thread,
        original_subject=original_subject,
        inputs=inputs,
        trigger_data=trigger_data,
    )
    result = await agent.run(prompt)
    out = result.output
    out.scenario = scenario
    out.metadata["trigger_source"] = trigger_data.get("source", "")
    log_agent_step(log_name, "Draft complete", {"subject": out.subject})
    return out


async def draft_supply(
    inputs: Any,
    trigger_data: dict[str, Any],
    original_subject: str,
    email_thread: str,
) -> DraftEmail:
    """Draft Email Agent A6 for Product Supply (S1)."""
    log_agent_step("A6", "Drafting email (Supply)", {"scenario": "S1"})
    return await _draft_async(
        "A6_draft", "A6", "S1", inputs, trigger_data, original_subject, email_thread
    )


async def draft_access(
    inputs: Any,
    trigger_data: dict[str, Any],
    original_subject: str,
    email_thread: str,
) -> DraftEmail:
    """Draft Email Agent A7 for Product Access (S2)."""
    log_agent_step("A7", "Drafting email (Access)", {"scenario": "S2"})
    return await _draft_async(
        "A7_draft", "A7", "S2", inputs, trigger_data, original_subject, email_thread
    )


async def draft_allocation(
    inputs: Any,
    trigger_data: dict[str, Any],
    original_subject: str,
    email_thread: str,
) -> DraftEmail:
    """Draft Email Agent A8 for Product Allocation (S3)."""
    log_agent_step("A8", "Drafting email (Allocation)", {"scenario": "S3"})
    return await _draft_async(
        "A8_draft", "A8", "S3", inputs, trigger_data, original_subject, email_thread
    )


async def draft_catchall(
    inputs: Any,
    trigger_data: dict[str, Any],
    original_subject: str,
    email_thread: str,
) -> DraftEmail:
    """Draft Email Agent A9 for Catch-All (S4)."""
    log_agent_step("A9", "Drafting email (Catch-All)", {"scenario": "S4"})
    return await _draft_async(
        "A9_draft", "A9", "S4", inputs, trigger_data, original_subject, email_thread
    )


async def draft_supply_or_access(
    scenario: str,
    inputs: Any,
    trigger_data: dict[str, Any],
    original_subject: str,
    email_thread: str = "",
) -> DraftEmail:
    """Legacy: S1 uses A6, S2 uses A7."""
    if scenario == "S1":
        return await draft_supply(
            inputs, trigger_data, original_subject, email_thread or ""
        )
    return await draft_access(
        inputs, trigger_data, original_subject, email_thread or ""
    )


async def draft_allocation_or_catchall(
    scenario: str,
    inputs: Any,
    trigger_data: dict[str, Any],
    original_subject: str,
    email_thread: str = "",
) -> DraftEmail:
    """Legacy: S3 uses A8, S4 uses A9."""
    if scenario == "S3":
        return await draft_allocation(
            inputs, trigger_data, original_subject, email_thread or ""
        )
    return await draft_catchall(
        inputs, trigger_data, original_subject, email_thread or ""
    )
