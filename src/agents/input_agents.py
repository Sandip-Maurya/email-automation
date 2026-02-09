"""Input Agents A1-A4: Extract structured data from emails per scenario."""

from src.agents.input_registry import register_input_agent
from src.agents.registry import get_agent
from src.models.email import EmailThread
from src.models.inputs import (
    ProductSupplyInput,
    ProductAccessInput,
    ProductAllocationInput,
    CatchAllInput,
)
from src.utils.logger import log_agent_step


def _thread_prompt(thread: EmailThread) -> str:
    parts = [f"From: {e.sender}\nSubject: {e.subject}\n{e.body}" for e in thread.emails]
    return "\n\n---\n\n".join(parts)


@register_input_agent("A1_supply_extract", ProductSupplyInput)
async def extract_supply(thread: EmailThread) -> ProductSupplyInput:
    log_agent_step("A1", "Extracting Product Supply inputs", {"thread_id": thread.thread_id})
    agent = get_agent("A1_supply_extract", ProductSupplyInput)
    result = await agent.run(_thread_prompt(thread))
    out = result.output
    log_agent_step("A1", "Extracted", {"confidence": out.confidence, "missing": out.missing_fields})
    return out


@register_input_agent("A2_access_extract", ProductAccessInput)
async def extract_access(thread: EmailThread) -> ProductAccessInput:
    log_agent_step("A2", "Extracting Product Access inputs", {"thread_id": thread.thread_id})
    agent = get_agent("A2_access_extract", ProductAccessInput)
    result = await agent.run(_thread_prompt(thread))
    out = result.output
    log_agent_step("A2", "Extracted", {"confidence": out.confidence, "missing": out.missing_fields})
    return out


@register_input_agent("A3_allocation_extract", ProductAllocationInput)
async def extract_allocation(thread: EmailThread) -> ProductAllocationInput:
    log_agent_step("A3", "Extracting Product Allocation inputs", {"thread_id": thread.thread_id})
    agent = get_agent("A3_allocation_extract", ProductAllocationInput)
    result = await agent.run(_thread_prompt(thread))
    out = result.output
    log_agent_step("A3", "Extracted", {"confidence": out.confidence, "missing": out.missing_fields})
    return out


@register_input_agent("A4_catchall_extract", CatchAllInput)
async def extract_catchall(thread: EmailThread) -> CatchAllInput:
    log_agent_step("A4", "Extracting Catch-All topics", {"thread_id": thread.thread_id})
    agent = get_agent("A4_catchall_extract", CatchAllInput)
    result = await agent.run(_thread_prompt(thread))
    out = result.output
    log_agent_step("A4", "Extracted", {"confidence": out.confidence, "topics": out.topics})
    return out
