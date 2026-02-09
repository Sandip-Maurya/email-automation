# Agent Configuration

Agent prompts, model settings, and scenario wiring are defined in **YAML config** and loaded at runtime. This allows prompt tuning and scenario changes without code changes.

---

## Config File: `config/agents.yaml`

**Required.** The application fails at startup if this file is missing (fail-fast). Override the path with the `AGENTS_CONFIG_PATH` environment variable.

### Structure

| Section | Purpose |
|--------|--------|
| **defaults** | Default `model`, `retries` (and optional `temperature`, `max_tokens`) applied to all agents unless overridden. |
| **agents** | One entry per agent: `system_prompt` (required), optional `user_prompt_template`, and optional overrides for `model`, `retries`, `temperature`, `max_tokens`. |
| **scenarios** | One entry per scenario (S1–S4): `name`, `enabled`, `input_agent`, `trigger`, `draft_agent`, `low_confidence_threshold`. |

### Agent IDs

| Agent ID | Role | Has user_prompt_template |
|----------|------|---------------------------|
| A0_decision | Decision (classify S1–S4) | No |
| A1_supply_extract | Input extraction S1 | No |
| A2_access_extract | Input extraction S2 | No |
| A3_allocation_extract | Input extraction S3 | No |
| A4_catchall_extract | Input extraction S4 | No |
| A7_draft | Draft for S1/S2 | Yes |
| A8_draft | Draft for S3/S4 | Yes |
| A10_review | Review draft | Yes |
| A11_format | Final email format | Yes |

### User prompt templates

Templates use Python `str.format()` placeholders. For example, A7_draft uses `{original_subject}`, `{inputs}`, `{trigger_data}`. The orchestrator and agent code pass these at runtime.

### Scenario wiring

Each scenario references an **input_agent** (extract function), a **trigger** (registered trigger name), and a **draft_agent**. The orchestrator loads this config and dispatches generically; adding a new scenario only requires updating the YAML (and implementing the corresponding extract/trigger/draft if new).

---

## Validate config: `validate-config` CLI

Check that the config file is valid and all scenario references resolve:

```bash
uv run python -m src.main validate-config
```

This command:

1. Loads `config/agents.yaml`
2. Validates that every scenario’s `input_agent` and `draft_agent` exist under `agents`
3. Validates that every scenario’s `trigger` is registered (via `@register_trigger`)
4. Prints a table: agent_id, model, prompt length, has_template

Exit code 1 on any validation error.

---

## Config API (webhook server)

When the webhook server is running, you can read and update agent config over HTTP. Responses are JSON.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/config/agents` | Full config (defaults, agents, scenarios) |
| GET | `/config/agents/{agent_id}` | Merged config for one agent |
| PUT | `/config/agents/{agent_id}` | Update one agent (system_prompt, model, retries, user_prompt_template, temperature, max_tokens). Persists to YAML and reloads. |
| POST | `/config/agents/reload` | Reload config from disk and clear agent cache |
| GET | `/config/scenarios` | All scenario definitions |
| GET | `/config/scenarios/{scenario_id}` | One scenario (e.g. S1) |

### Example: update a prompt

```bash
curl -X PUT http://localhost:8000/config/agents/A0_decision \
  -H "Content-Type: application/json" \
  -d '{"system_prompt": "You are a Decision Agent..."}'
```

After a successful PUT, the next pipeline run uses the new prompt (agent cache is cleared for that agent on reload).

---

## Implementation notes

- **Registry** (`src/agents/registry.py`): Loads YAML, validates scenario→agent references, caches created Pydantic AI agents. `reload_config()` clears the cache.
- **Input registry** (`src/agents/input_registry.py`): Maps agent IDs (e.g. A1_supply_extract) to extract functions; decorator `@register_input_agent(agent_id, input_type)`.
- **Trigger registry** (`src/triggers/registry.py`): Maps trigger names (e.g. inventory_api) to async functions; decorator `@register_trigger(name)`.
- **Orchestrator**: Uses `get_scenario_config(scenario)`, `get_input_agent()`, `get_trigger()`, `get_agent()`, `get_user_prompt_template()` instead of hardcoded if/elif and inline prompts.
