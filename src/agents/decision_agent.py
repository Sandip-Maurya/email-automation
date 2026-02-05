"""Decision Agent A0: Classify incoming email into one of four scenarios."""

from pydantic_ai import Agent

from src.models.email import EmailThread
from src.models.outputs import ScenarioDecision
from src.utils.logger import log_agent_step

DECISION_SYSTEM_PROMPT = """You are a Decision Agent (A0) for pharmaceutical trade email routing.
Your job is to classify each incoming email into exactly one of four scenarios:

- S1 (Product Supply): Emails about inventory, stock levels, product availability, quantities at locations/distributors, NDC inventory checks.
- S2 (Product Access): Emails about customer access, class of trade, REMS certification, 340B eligibility, DEA registration, account/address verification.
- S3 (Product Allocation): Emails about allocation requests, allocation percentages, allocation limits, year-based allocation, distributor allocation.
- S4 (Catch-All): General inquiries, ordering process, documentation, business hours, contact info, or anything that does not clearly fit S1, S2, or S3.

Consider the full email thread context. Respond with the scenario code (S1, S2, S3, or S4), a confidence score between 0 and 1, and brief reasoning."""

decision_agent = Agent(
    "openai:gpt-4o-mini",
    output_type=ScenarioDecision,
    system_prompt=DECISION_SYSTEM_PROMPT,
    retries=1,
)


def _thread_to_prompt(thread: EmailThread) -> str:
    """Build a single prompt string from an email thread."""
    parts = []
    for e in thread.emails:
        parts.append(f"From: {e.sender}\nSubject: {e.subject}\n{e.body}")
    return "\n\n---\n\n".join(parts)


async def classify_thread(thread: EmailThread) -> ScenarioDecision:
    """Classify an email thread into S1, S2, S3, or S4."""
    log_agent_step("A0", "Classifying email thread", {"thread_id": thread.thread_id})
    prompt = _thread_to_prompt(thread)
    result = await decision_agent.run(prompt)
    out = result.output
    log_agent_step("A0", f"Classified as {out.scenario}", {"confidence": out.confidence})
    return out
