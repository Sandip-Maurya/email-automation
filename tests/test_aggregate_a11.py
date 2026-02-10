"""Tests for Input A11 aggregate (aggregate_context_for_decision)."""

import importlib.util
from pathlib import Path

import pytest

from src.models.outputs import ScenarioDecision
from src.models.inputs import (
    ProductSupplyInput,
    ProductAllocationInput,
    CatchAllInput,
)

# Load aggregate_a11 without pulling in src.agents.__init__ (avoids bs4 etc.)
_spec = importlib.util.spec_from_file_location(
    "aggregate_a11",
    Path(__file__).resolve().parent.parent / "src" / "agents" / "aggregate_a11.py",
)
_aggregate_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_aggregate_mod)
aggregate_context_for_decision = _aggregate_mod.aggregate_context_for_decision


def test_aggregate_supply_input():
    """AggregatedContext gets decision, ndc, distributor from ProductSupplyInput."""
    decision = ScenarioDecision(scenario="S1", confidence=0.9, reasoning="supply")
    inputs = ProductSupplyInput(
        location="WH1", distributor="DistA", ndc="12345-678-90", confidence=0.85
    )
    out = aggregate_context_for_decision(decision, inputs)
    assert out.decision == "S1"
    assert out.ndc == "12345-678-90"
    assert out.distributor == "DistA"
    assert out.year is None
    assert out.year_end is None


def test_aggregate_allocation_input():
    """AggregatedContext gets year from ProductAllocationInput."""
    decision = ScenarioDecision(scenario="S3", confidence=0.8, reasoning="allocation")
    inputs = ProductAllocationInput(
        urgency="high",
        year_start=2024,
        year_end=2025,
        distributor="DistB",
        ndc="11111-222-33",
        confidence=0.75,
    )
    out = aggregate_context_for_decision(decision, inputs)
    assert out.decision == "S3"
    assert out.ndc == "11111-222-33"
    assert out.distributor == "DistB"
    assert out.year == 2024
    assert out.year_end == 2025


def test_aggregate_catchall_input():
    """CatchAllInput has no ndc/distributor/year; they stay None."""
    decision = ScenarioDecision(scenario="S4", confidence=0.7, reasoning="catch-all")
    inputs = CatchAllInput(topics=["ordering"], question_summary="How to order?", confidence=0.6)
    out = aggregate_context_for_decision(decision, inputs)
    assert out.decision == "S4"
    assert out.ndc is None
    assert out.distributor is None
    assert out.year is None
