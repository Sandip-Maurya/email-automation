"""Input agent registry: maps agent IDs to extract functions and input model types."""

from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel

from src.utils.logger import get_logger

logger = get_logger("email_automation.agents.input_registry")

# agent_id -> (extract_fn, input_type)
_INPUT_AGENT_REGISTRY: dict[
    str, tuple[Callable[..., Awaitable[Any]], type[BaseModel]]
] = {}


def register_input_agent(agent_id: str, input_type: type[BaseModel]):
    """Decorator to register an input agent extract function."""

    def decorator(fn: Callable[..., Awaitable[Any]]):
        _INPUT_AGENT_REGISTRY[agent_id] = (fn, input_type)
        return fn

    return decorator


def get_input_agent(
    agent_id: str,
) -> tuple[Callable[..., Awaitable[Any]], type[BaseModel]]:
    """Return (extract_fn, input_type) for the given agent_id. Raises ValueError if unknown."""
    if agent_id not in _INPUT_AGENT_REGISTRY:
        raise ValueError(
            f"Unknown input agent: {agent_id!r}. Registered: {list(_INPUT_AGENT_REGISTRY)}"
        )
    return _INPUT_AGENT_REGISTRY[agent_id]


def list_input_agents() -> list[str]:
    """Return all registered input agent IDs."""
    return list(_INPUT_AGENT_REGISTRY.keys())
