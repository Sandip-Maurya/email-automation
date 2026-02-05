"""Input Agents A1-A4: Extract structured data from emails per scenario."""

from pydantic_ai import Agent

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


# A1: Product Supply - Location, Distributor, NDC
A1_PROMPT = """You are Input Agent A1 for Product Supply (S1).
Extract from the email thread: location, distributor, NDC (National Drug Code).
If a field is not mentioned, leave it null and add it to missing_fields.
Set confidence between 0 and 1. List any missing_fields that would be needed for a full supply inquiry."""

input_agent_a1 = Agent(
    "openai:gpt-4o-mini",
    output_type=ProductSupplyInput,
    system_prompt=A1_PROMPT,
    retries=1,
)


async def extract_supply(thread: EmailThread) -> ProductSupplyInput:
    log_agent_step("A1", "Extracting Product Supply inputs", {"thread_id": thread.thread_id})
    result = await input_agent_a1.run(_thread_prompt(thread))
    out = result.output
    log_agent_step("A1", "Extracted", {"confidence": out.confidence, "missing": out.missing_fields})
    return out


# A2: Product Access - Customer, Distributor, NDC, DEA, Address, 340B, Contact
A2_PROMPT = """You are Input Agent A2 for Product Access (S2).
Extract from the email: customer, distributor, NDC, DEA number, address, 340B status (true/false), contact.
If a field is not mentioned, leave it null and add it to missing_fields.
Set confidence between 0 and 1. List missing_fields."""

input_agent_a2 = Agent(
    "openai:gpt-4o-mini",
    output_type=ProductAccessInput,
    system_prompt=A2_PROMPT,
    retries=1,
)


async def extract_access(thread: EmailThread) -> ProductAccessInput:
    log_agent_step("A2", "Extracting Product Access inputs", {"thread_id": thread.thread_id})
    result = await input_agent_a2.run(_thread_prompt(thread))
    out = result.output
    log_agent_step("A2", "Extracted", {"confidence": out.confidence, "missing": out.missing_fields})
    return out


# A3: Product Allocation - Urgency, Years, Distributor, NDC
A3_PROMPT = """You are Input Agent A3 for Product Allocation (S3).
Extract from the email: urgency, year range (year_start, year_end), distributor, NDC.
If a field is not mentioned, leave it null and add it to missing_fields.
Set confidence between 0 and 1. List missing_fields."""

input_agent_a3 = Agent(
    "openai:gpt-4o-mini",
    output_type=ProductAllocationInput,
    system_prompt=A3_PROMPT,
    retries=1,
)


async def extract_allocation(thread: EmailThread) -> ProductAllocationInput:
    log_agent_step("A3", "Extracting Product Allocation inputs", {"thread_id": thread.thread_id})
    result = await input_agent_a3.run(_thread_prompt(thread))
    out = result.output
    log_agent_step("A3", "Extracted", {"confidence": out.confidence, "missing": out.missing_fields})
    return out


# A4: Catch-All - topics for RAG search
A4_PROMPT = """You are Input Agent A4 for Catch-All (S4).
Extract key topics and a brief question_summary from the email for RAG search over past similar emails.
Set confidence between 0 and 1. missing_fields can list any clarifying info that would help."""

input_agent_a4 = Agent(
    "openai:gpt-4o-mini",
    output_type=CatchAllInput,
    system_prompt=A4_PROMPT,
    retries=1,
)


async def extract_catchall(thread: EmailThread) -> CatchAllInput:
    log_agent_step("A4", "Extracting Catch-All topics", {"thread_id": thread.thread_id})
    result = await input_agent_a4.run(_thread_prompt(thread))
    out = result.output
    log_agent_step("A4", "Extracted", {"confidence": out.confidence, "topics": out.topics})
    return out
