"""Pydantic AI agents for email automation."""

from src.agents.decision_agent import decision_agent
from src.agents.input_agents import (
    input_agent_a1,
    input_agent_a2,
    input_agent_a3,
    input_agent_a4,
)
from src.agents.draft_agents import draft_agent_a7, draft_agent_a8
from src.agents.review_agent import review_agent
from src.agents.email_agent import email_agent

__all__ = [
    "decision_agent",
    "input_agent_a1",
    "input_agent_a2",
    "input_agent_a3",
    "input_agent_a4",
    "draft_agent_a7",
    "draft_agent_a8",
    "review_agent",
    "email_agent",
]
