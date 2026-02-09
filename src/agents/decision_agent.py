"""Decision Agent A0: Classify incoming email into one of four scenarios."""

from src.agents.registry import get_agent
from src.models.email import EmailThread
from src.models.outputs import ScenarioDecision
from src.utils.logger import log_agent_step


def _thread_to_prompt(thread: EmailThread) -> str:
    """Build a single prompt string from an email thread."""
    parts = []
    for e in thread.emails:
        parts.append(f"From: {e.sender}\nSubject: {e.subject}\n{e.body}")
    return "\n\n---\n\n".join(parts)


async def classify_thread(thread: EmailThread) -> ScenarioDecision:
    """Classify an email thread into S1, S2, S3, or S4."""
    log_agent_step("A0", "Classifying email thread", {"thread_id": thread.thread_id})
    agent = get_agent("A0_decision", ScenarioDecision)
    prompt = _thread_to_prompt(thread)
    result = await agent.run(prompt)
    out = result.output
    log_agent_step("A0", f"Classified as {out.scenario}", {"confidence": out.confidence})
    return out
