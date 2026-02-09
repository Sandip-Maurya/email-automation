"""Trigger function registry: maps trigger names (from config) to callable functions."""

from collections.abc import Awaitable, Callable
from typing import Any

from src.utils.logger import get_logger

logger = get_logger("email_automation.triggers.registry")

# Registry: trigger_name -> async function(inputs) -> dict
_TRIGGER_REGISTRY: dict[str, Callable[..., Awaitable[dict[str, Any]]]] = {}


def register_trigger(name: str):
    """Decorator to register a trigger function."""

    def decorator(fn: Callable[..., Awaitable[dict[str, Any]]]):
        _TRIGGER_REGISTRY[name] = fn
        return fn

    return decorator


def get_trigger(name: str) -> Callable[..., Awaitable[dict[str, Any]]]:
    """Return the trigger function for the given name. Raises ValueError if unknown."""
    if name not in _TRIGGER_REGISTRY:
        raise ValueError(
            f"Unknown trigger: {name!r}. Registered: {list(_TRIGGER_REGISTRY)}"
        )
    return _TRIGGER_REGISTRY[name]


def list_triggers() -> list[str]:
    """Return all registered trigger names."""
    return list(_TRIGGER_REGISTRY.keys())
