"""Config API: GET/PUT agents and scenarios, POST reload."""

from typing import Any

from fastapi import APIRouter, HTTPException

from src.agents.registry import (
    get_agent_config,
    get_all_config,
    get_scenario_config,
    reload_config,
    save_config,
)

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/agents")
async def list_agents_config() -> dict[str, Any]:
    """Return full agents config as JSON."""
    return get_all_config()


@router.post("/agents/reload")
async def reload_agents_config() -> dict[str, str]:
    """Hot-reload config from disk and clear agent cache."""
    reload_config()
    return {"status": "reloaded"}


@router.get("/agents/{agent_id}")
async def get_agent_config_endpoint(agent_id: str) -> dict[str, Any]:
    """Return merged config for one agent."""
    try:
        return get_agent_config(agent_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.put("/agents/{agent_id}")
async def update_agent_config(agent_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """Update one agent's config (system_prompt, model, retries, user_prompt_template). Writes YAML and reloads."""
    config = get_all_config()
    agents = config.get("agents") or {}
    if agent_id not in agents:
        raise HTTPException(status_code=404, detail=f"Unknown agent: {agent_id!r}")
    allowed = {"system_prompt", "model", "retries", "user_prompt_template", "temperature", "max_tokens"}
    for key, value in body.items():
        if key in allowed:
            agents[agent_id][key] = value
    save_config(config)
    return get_agent_config(agent_id)


@router.get("/scenarios")
async def list_scenarios_config() -> dict[str, Any]:
    """Return all scenario definitions."""
    config = get_all_config()
    return config.get("scenarios") or {}


@router.get("/scenarios/{scenario_id}")
async def get_scenario_config_endpoint(scenario_id: str) -> dict[str, Any]:
    """Return one scenario config."""
    try:
        return get_scenario_config(scenario_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
