"""Validate agents config: load YAML, check scenario references, print summary table."""

from src.agents.registry import get_agent_config, get_all_config
from src.triggers import list_triggers
from .shared import console, logger


def validate_config() -> None:
    """Load config/agents.yaml, validate scenario references and triggers, print summary table."""
    log = logger.bind(command="validate-config")
    log.info("validate_config.start")

    try:
        config = get_all_config()
    except FileNotFoundError as e:
        console.print(f"[red]Config error: {e}[/red]")
        log.error("validate_config.fail", error=str(e))
        raise SystemExit(1) from e
    except ValueError as e:
        console.print(f"[red]Config error: {e}[/red]")
        log.error("validate_config.fail", error=str(e))
        raise SystemExit(1) from e

    agents = config.get("agents") or {}
    scenarios = config.get("scenarios") or {}
    registered_triggers = set(list_triggers())

    errors = []
    for scenario_id, scenario_cfg in scenarios.items():
        for key in ("input_agent", "draft_agent"):
            agent_id = scenario_cfg.get(key)
            if agent_id and agent_id not in agents:
                errors.append(f"Scenario {scenario_id!r} references unknown agent {agent_id!r}")
        trigger_name = scenario_cfg.get("trigger")
        if trigger_name and trigger_name not in registered_triggers:
            errors.append(f"Scenario {scenario_id!r} references unknown trigger {trigger_name!r}")

    if errors:
        for msg in errors:
            console.print(f"[red]{msg}[/red]")
        log.error("validate_config.validation_failed", errors=errors)
        raise SystemExit(1)

    from rich.table import Table

    table = Table(title="Agents config")
    table.add_column("Agent ID", style="cyan")
    table.add_column("Model", style="green")
    table.add_column("Prompt length", justify="right")
    table.add_column("Has template", justify="center")

    for agent_id in sorted(agents):
        try:
            merged = get_agent_config(agent_id)
        except ValueError:
            continue
        model = merged.get("model", "(default)")
        prompt = merged.get("system_prompt") or ""
        prompt_len = len(prompt)
        has_tpl = "yes" if (merged.get("user_prompt_template") or "").strip() else "no"
        table.add_row(agent_id, str(model), str(prompt_len), has_tpl)

    console.print(table)
    console.print(f"[green]Config valid. {len(agents)} agents, {len(scenarios)} scenarios.[/green]")
    log.info("validate_config.ok", agents=len(agents), scenarios=len(scenarios))
