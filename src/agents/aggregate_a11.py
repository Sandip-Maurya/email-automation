"""Input Agent A11: Aggregate Decision, NDC, Distributor, Year for Decision A10."""

from typing import Any, Optional

from src.models.outputs import AggregatedContext, ScenarioDecision


def aggregate_context_for_decision(
    decision: ScenarioDecision,
    inputs: Any,
) -> AggregatedContext:
    """Extract Decision, NDC, Distributor, Year from classifier decision and extracted inputs.
    No LLM; pure extraction (placeholder per diagram)."""
    ndc = getattr(inputs, "ndc", None)
    distributor = getattr(inputs, "distributor", None)
    year: Optional[int] = getattr(inputs, "year_start", None)
    year_end: Optional[int] = getattr(inputs, "year_end", None)
    if year is None and hasattr(inputs, "year_end"):
        year = getattr(inputs, "year_end", None)
    return AggregatedContext(
        decision=decision.scenario,
        ndc=ndc if ndc is not None else None,
        distributor=distributor if distributor is not None else None,
        year=year,
        year_end=year_end,
    )
