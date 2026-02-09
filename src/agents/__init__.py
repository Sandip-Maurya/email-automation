"""Pydantic AI agents for email automation."""

from src.agents.registry import (
    get_agent,
    get_agent_config,
    get_all_config,
    get_scenario_config,
    get_user_prompt_template,
    reload_config,
)
from src.agents.input_registry import get_input_agent, list_input_agents, register_input_agent
from src.agents.decision_agent import classify_thread
from src.agents.input_agents import (
    extract_supply,
    extract_access,
    extract_allocation,
    extract_catchall,
)
from src.agents.draft_agents import draft_supply_or_access, draft_allocation_or_catchall
from src.agents.review_agent import review_draft
from src.agents.email_agent import format_final_email

__all__ = [
    "get_agent",
    "get_agent_config",
    "get_all_config",
    "get_scenario_config",
    "get_user_prompt_template",
    "reload_config",
    "get_input_agent",
    "list_input_agents",
    "register_input_agent",
    "classify_thread",
    "extract_supply",
    "extract_access",
    "extract_allocation",
    "extract_catchall",
    "draft_supply_or_access",
    "draft_allocation_or_catchall",
    "review_draft",
    "format_final_email",
]
