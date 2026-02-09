"""Agent registry: loads config from YAML, creates and caches Pydantic AI agents."""

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic_ai import Agent

from src.config import PROJECT_ROOT
from src.utils.logger import get_logger

logger = get_logger("email_automation.agents.registry")

_CONFIG_PATH = PROJECT_ROOT / "config" / "agents.yaml"
_config: dict[str, Any] | None = None
_agent_cache: dict[str, Agent] = {}


def _get_config_path() -> Path:
    raw = os.environ.get("AGENTS_CONFIG_PATH", "").strip()
    if raw:
        return Path(raw)
    return _CONFIG_PATH


def _load_config() -> dict[str, Any]:
    global _config
    if _config is not None:
        return _config
    path = _get_config_path()
    if not path.exists():
        raise FileNotFoundError(
            f"Agents config not found: {path}. Set AGENTS_CONFIG_PATH or create config/agents.yaml."
        )
    try:
        raw = path.read_text(encoding="utf-8")
        _config = yaml.safe_load(raw)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in agents config {path}: {e}") from e
    if not isinstance(_config, dict):
        raise ValueError(f"Agents config must be a YAML object (dict), got {type(_config)}")
    _validate_config(_config)
    logger.info(
        "agent_registry.config_loaded",
        path=str(path),
        agent_count=len(_config.get("agents", {})),
        scenario_count=len(_config.get("scenarios", {})),
    )
    return _config


def _validate_config(config: dict[str, Any]) -> None:
    """Validate that all scenario references point to existing agents."""
    agents = config.get("agents") or {}
    scenarios = config.get("scenarios") or {}
    for scenario_id, scenario_cfg in scenarios.items():
        if not isinstance(scenario_cfg, dict):
            raise ValueError(f"Scenario {scenario_id!r} must be a dict")
        for key in ("input_agent", "draft_agent"):
            agent_id = scenario_cfg.get(key)
            if not agent_id:
                raise ValueError(f"Scenario {scenario_id!r} missing required key {key!r}")
            if agent_id not in agents:
                raise ValueError(
                    f"Scenario {scenario_id!r} references unknown agent {agent_id!r}. "
                    f"Known agents: {list(agents)}"
                )
        if not scenario_cfg.get("trigger"):
            raise ValueError(f"Scenario {scenario_id!r} missing required key trigger")


def reload_config() -> dict[str, Any]:
    """Force-reload config from disk and clear agent cache (for hot-reload via API)."""
    global _config
    _config = None
    _agent_cache.clear()
    return _load_config()


def get_agent_config(agent_id: str) -> dict[str, Any]:
    """Return merged config (defaults + per-agent overrides) for an agent."""
    config = _load_config()
    defaults = config.get("defaults") or {}
    agent_cfg = (config.get("agents") or {}).get(agent_id)
    if agent_cfg is None:
        raise ValueError(f"Unknown agent {agent_id!r}. Known: {list((config.get('agents') or {}))}")
    return {**defaults, **agent_cfg}


def get_agent(agent_id: str, output_type: type) -> Agent:
    """Get or create a Pydantic AI Agent for the given agent_id. Cached by agent_id."""
    if agent_id in _agent_cache:
        return _agent_cache[agent_id]
    cfg = get_agent_config(agent_id)
    system_prompt = cfg.get("system_prompt")
    if not system_prompt or not isinstance(system_prompt, str):
        raise ValueError(f"Agent {agent_id!r} must have a non-empty system_prompt string")
    model = cfg.get("model", "openai:gpt-4o-mini")
    retries = cfg.get("retries", 1)
    model_settings = {}
    if cfg.get("temperature") is not None:
        model_settings["temperature"] = cfg["temperature"]
    if cfg.get("max_tokens") is not None:
        model_settings["max_tokens"] = cfg["max_tokens"]
    agent = Agent(
        model=model,
        output_type=output_type,
        system_prompt=system_prompt,
        retries=retries,
        **({"model_settings": model_settings} if model_settings else {}),
    )
    _agent_cache[agent_id] = agent
    return agent


def get_user_prompt_template(agent_id: str) -> str | None:
    """Return the user prompt template for an agent, or None if not set."""
    cfg = get_agent_config(agent_id)
    template = cfg.get("user_prompt_template")
    if template is None or (isinstance(template, str) and not template.strip()):
        return None
    return template if isinstance(template, str) else str(template)


def get_scenario_config(scenario: str) -> dict[str, Any]:
    """Return the scenario config dict for the given scenario code (e.g. S1, S2)."""
    config = _load_config()
    scenarios = config.get("scenarios") or {}
    if scenario not in scenarios:
        raise ValueError(
            f"Unknown scenario {scenario!r}. Known: {list(scenarios)}"
        )
    return dict(scenarios[scenario])


def get_all_config() -> dict[str, Any]:
    """Return the full parsed config (for API)."""
    return dict(_load_config())


def save_config(config: dict[str, Any]) -> None:
    """Write config to disk as YAML and reload. Used by config API after updates."""
    path = _get_config_path()
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    reload_config()
