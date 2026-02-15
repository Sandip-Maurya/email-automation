# Workflow Architecture

The email automation pipeline is implemented as a **LlamaIndex Workflow**: an event-driven, step-based orchestrator. This document describes the workflow model, event types, and how conditionals are handled.

## Overview

LlamaIndex Workflows use an event-driven architecture. Steps are Python functions decorated with `@step` that:

- **Accept** one or more event types as input
- **Emit** events that trigger subsequent steps
- **Return** `StopEvent` to end the workflow and yield the final result

The framework routes events to steps based on type. No explicit graph edges are defined—the flow is inferred from step signatures.

## Event Flow

```
StartEvent (thread, provider, tracer, reply_to_message_id, user_id)
    │
    ▼
classify ─────────────────► ClassifiedEvent (or StopEvent if scenario disabled)
    │
    ▼
extract ───────────────────► ExtractedEvent
    │
    ▼
trigger_or_s3 ─────────────► TriggerDataEvent  (S3 scaffold runs only when scenario == "S3")
    │
    ▼
draft ─────────────────────► DraftReadyEvent
    │
    ▼
aggregate ─────────────────► DraftWithContextEvent
    │
    ▼
review ────────────────────► ReviewCompleteEvent
    │
    ▼
format ────────────────────► FormattedEvent
    │
    ▼
send_or_draft ─────────────► StopEvent(result=ProcessingResult)
```

## Event Types

| Event | Purpose |
|-------|---------|
| `StartEvent` | Initial input from `workflow.run(thread=..., provider=..., ...)`. Carries thread, provider, tracer, reply_to_message_id, user_id. |
| `ClassifiedEvent` | After A0 classification. Carries thread, decision (scenario, confidence, reasoning), and provider/tracer/reply_to_message_id/user_id for downstream. |
| `ExtractedEvent` | After input extraction. Carries thread, scenario, scenario_cfg, inputs, decision. |
| `TriggerDataEvent` | After trigger fetch (and optionally S3 scaffold). Carries inputs, trigger_data, s3_context. |
| `DraftReadyEvent` | After draft generation. Carries draft, context_for_review components. |
| `DraftWithContextEvent` | After A11 aggregate. Carries draft, context_for_review, original_sender, original_sender_name. |
| `ReviewCompleteEvent` | After A10 review. Carries draft, review, final formatting inputs. |
| `FormattedEvent` | After A11 format. Carries final_email, raw_data, provider, reply_to_message_id, user_id. |
| `StopEvent` | Workflow end. Carries `result` (ProcessingResult). |

## Conditional Execution

### Scenario disabled

In the `classify` step, after `get_scenario_config(scenario)`:

```python
if not scenario_cfg.get("enabled", True):
    raise ValueError(f"Scenario {scenario} is disabled in config")
```

The workflow stops via exception (or you could return `StopEvent` with an error result).

### S3 scaffold

In the `trigger_or_s3` step:

```python
s3_context = None
if scenario == "S3":
    s3_context = await run_s3_scaffold(inputs, tracer)
trigger_data = await step_trigger_fetch(..., s3_context=s3_context)
```

Only when `scenario == "S3"` do we run A_D1–A_D4; otherwise `s3_context` stays `None`.

### DRAFT_ONLY vs send

In the `send_or_draft` step (and `run_draft_or_send` in `orchestrator_steps`):

```python
if DRAFT_ONLY:
    # create_reply_draft, persist in email_outcomes
else:
    # provider.reply_to_message(...)
```

## Step Implementation

Steps live in `src/workflow/email_workflow.py`. Each step:

1. Receives an event and extracts fields (thread, scenario, tracer, etc.)
2. Calls the corresponding function from `src/orchestrator_steps.py` (e.g. `step_classify`, `step_extract`)
3. Returns the next event in the chain

Tracing and logging are applied inside `orchestrator_steps` so span names (`A0_classify`, `input_extract`, etc.) match the previous implementation.

## Running the Workflow

The orchestrator (`src/orchestrator.py`) runs the workflow via:

```python
workflow = EmailOrchestratorWorkflow(timeout=120, verbose=False)
handler = workflow.run(
    thread=thread,
    provider=provider,
    tracer=tracer,
    reply_to_message_id=reply_to_message_id,
    user_id=user_id,
)
result = await handler  # ProcessingResult
```

The public API (`process_trigger`, `process_email_thread`) is unchanged; callers do not need to know about the workflow.

## References

- [LlamaIndex Workflows documentation](https://docs.llamaindex.ai/en/stable/module_guides/workflow/)
- [Introducing Workflows Beta (LlamaIndex Blog)](https://www.llamaindex.ai/blog/introducing-workflows-beta-a-new-way-to-create-complex-ai-applications-with-llamaindex)
- [CORE_WORKFLOW.md](CORE_WORKFLOW.md) – High-level pipeline and scenario flows
