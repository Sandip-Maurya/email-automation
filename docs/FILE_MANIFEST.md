# File Manifest

A guide to every file, folder, module, class, and function in the email-automation project.

---

## 1. Project Overview

This project is a **multi-agent email automation system** for pharmaceutical trade operations. It ingests incoming emails (from mock JSON/CSV or Microsoft Graph API), classifies each thread into one of four scenarios (Product Supply, Product Access, Product Allocation, or Catch-All), extracts structured data via LLM agents, calls scenario-specific mock APIs (inventory, access, allocation, RAG), drafts and reviews reply content with AI agents, and optionally sends the reply via a configurable mail provider. It supports interactive, batch, Graph, and webhook CLI modes, with structured logging and Phoenix/OpenTelemetry tracing. **Agent prompts, model settings, and scenario wiring** are externalized in `config/agents.yaml` and loaded via registries; the orchestrator dispatches by config (see [AGENTS_CONFIG.md](AGENTS_CONFIG.md)).

---

## 2. Architecture / Data-Flow Diagram

Plain-text diagram (no Mermaid required):

```
[ENTRY]
main.py -> Typer CLI -> interactive | batch | graph | webhook | validate-config
                   |
                   v
        orchestrator.process_trigger(message_id, provider, user_id)
                   |
                   v
[MAIL PROVIDER + MAPPING]
GraphMockProvider (JSON)  GraphProvider (Real, MSAL cache)
             \                    /
              \---> MailProvider Protocol
                         |
      get_message/get_conversation (GraphMessage list)
                         v
         mapping.graph_messages_to_thread() -> EmailThread
                         |
                         v
[PIPELINE]
A0 Decision Agent -> ScenarioDecision (S1-S4, confidence)
        |
        v
config/agents.yaml
  -> Agent Registry (A0/A7/A8/A10/A11 prompts)
  -> Input Registry (A1-A4 extractors)
  -> Trigger Registry (S1-S4 trigger functions)
        |
        v
A1-A4 Extract -> Trigger APIs (inventory/access/allocation/RAG)
        |
        v
A7/A8 Draft -> A10 Review -> A11 Email format
        |
        v
mapping.final_email_to_send_payload()
        |
        v
provider.reply_to_message() -> ProcessingResult

[WEBHOOK SUPPORT]
Filter config + Dedup store (applied before processing)

[OBSERVABILITY]
Structlog logging + Phoenix/OTel tracing (runs alongside pipeline)
```

---

## 3. Directory Tree

```
email-automation/
├── .gitignore
├── pyproject.toml
├── README.md
├── uv.lock
├── config/
│   ├── agents.yaml
│   ├── filter.example.json
│   └── filter.json
├── docs/
│   ├── AZURE_SETUP_GUIDE.md
│   ├── component_diagram.jpg
│   ├── FILTER_CONFIG.md
│   ├── CORE_WORKFLOW.md
│   ├── WORKFLOW_ARCHITECTURE.md
│   ├── DRAFT_AND_SENT_FLOW.md
│   ├── DEMO_WEBHOOK_GUIDE.md
│   ├── DEMO_WEBHOOK_MINDMAP.md
│   ├── DEMO_SAMPLE_EMAILS.md
│   ├── FILE_MANIFEST.md
│   ├── GRAPH_API_INTEGRATION_GUIDE.md
│   ├── IMPLEMENTATION_STATUS.md
│   └── WEBHOOK_DEV_TUNNEL_SETUP.md
├── scripts/
│   └── verify_graph_credentials.py
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── orchestrator.py
│   ├── orchestrator_steps.py
│   ├── workflow/
│   │   ├── __init__.py
│   │   ├── events.py
│   │   └── email_workflow.py
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── decision_agent.py
│   │   ├── draft_agents.py
│   │   ├── email_agent.py
│   │   ├── input_agents.py
│   │   ├── input_registry.py
│   │   ├── registry.py
│   │   └── review_agent.py
│   ├── auth/
│   │   ├── __init__.py
│   │   └── token_cache.py
│   ├── cli/
│   │   ├── __init__.py
│   │   ├── batch_mode.py
│   │   ├── graph_mode.py
│   │   ├── interactive_mode.py
│   │   ├── shared.py
│   │   ├── validate_config.py
│   │   └── webhook_mode.py
│   ├── mail_provider/
│   │   ├── __init__.py
│   │   ├── graph_mock.py
│   │   ├── graph_models.py
│   │   ├── graph_real.py
│   │   ├── mapping.py
│   │   └── protocol.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── data.py
│   │   ├── email.py
│   │   ├── inputs.py
│   │   └── outputs.py
│   ├── triggers/
│   │   ├── __init__.py
│   │   ├── access_api.py
│   │   ├── allocation_api.py
│   │   ├── inventory_api.py
│   │   ├── rag_search.py
│   │   └── registry.py
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── body_sanitizer.py
│   │   ├── csv_loader.py
│   │   ├── email_parser.py
│   │   ├── logger.py
│   │   ├── observability.py
│   │   └── tracing.py
│   ├── db/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── allocation.py
│   │   │   ├── email_outcome.py
│   │   │   ├── inventory.py
│   │   │   └── master.py
│   │   ├── repositories/
│   │   │   ├── __init__.py
│   │   │   ├── allocation_repo.py
│   │   │   ├── customer_repo.py
│   │   │   ├── email_outcome_repo.py
│   │   │   ├── inventory_repo.py
│   │   │   └── ...
│   │   └── seed_data.py
│   └── webhook/
│       ├── __init__.py
│       ├── analytics_routes.py
│       ├── config_routes.py
│       ├── dedup_store.py
│       ├── filter_config.py
│       ├── models.py
│       ├── server.py
│       └── subscription.py
└── tests/
    ├── __init__.py
    ├── test_agent_registry.py
    └── test_dedup_store.py
```

---

## 4. File-by-File Manifest

### Root

| File | Purpose |
|------|--------|
| **pyproject.toml** | Project metadata, dependencies, and hatch build config; defines `email-automation` console script. |
| **README.md** | Project overview, features, architecture, quick start, config, run modes, and tech stack. |
| **.gitignore** | Ignores venv, .env, __pycache__, data/, output/, logs/, dedup_state.json. |
| **uv.lock** | Locked dependency versions for the uv package manager. |

---

### config/

| File | Purpose |
|------|--------|
| **agents.yaml** | Agent prompts, model defaults, and scenario wiring (input_agent, trigger, draft_agent, low_confidence_threshold). Required; fail-fast if missing. See [AGENTS_CONFIG.md](AGENTS_CONFIG.md). |
| **filter.json** | Webhook allowed-senders list (JSON array); only notifications from these addresses trigger processing. |
| **filter.example.json** | Example template for filter config with sample sender addresses. |

---

### docs/

| File | Purpose |
|------|--------|
| **AZURE_SETUP_GUIDE.md** | Step-by-step Azure AD app registration and Graph API permissions for delegated/application auth. |
| **component_diagram.jpg** | Visual component diagram image. |
| **FILTER_CONFIG.md** | Allowed-senders filter format and REST API for managing senders. |
| **AGENTS_CONFIG.md** | Agent config (agents.yaml), validate-config CLI, and Config API (GET/PUT agents, reload, scenarios). |
| **FILE_MANIFEST.md** | This file: manifest of all files, modules, classes, and functions. |
| **CORE_WORKFLOW.md** | Core workflow: high-level pipeline and per-scenario (S1–S4) flow with ASCII diagrams. |
| **DRAFT_AND_SENT_FLOW.md** | Draft-only flow, Sent Items subscription, ImmutableId correlation, email_outcomes schema, analytics APIs. |
| **DEMO_WEBHOOK_GUIDE.md** | Detailed 15–20 min webhook demo guide: narrative script, expectations, live run (4 mails, 2+ routes, audience send), Phoenix, Graph/app registration, Q&A. |
| **DEMO_WEBHOOK_MINDMAP.md** | One-page printable mind map for webhook demo: start order, flow, what to show, sample scenarios. |
| **DEMO_SAMPLE_EMAILS.md** | 2–3 sample emails per scenario (S1–S4) in markdown (Subject + Body) for demo or to share with audience. |
| **PHARMA_TERMS_GUIDE.md** | Plain-language guide for non-technical users: pharma trade terms (NDC, REMS, 340B, DEA, class of trade, allocation, etc.) and how they relate to the app’s read–understand–process–reply flow. |
| **GRAPH_API_INTEGRATION_GUIDE.md** | Python Graph API integration: auth, read/send mail, models, error handling, examples. |
| **IMPLEMENTATION_STATUS.md** | Feature completion status, architecture summary, roadmap, and limitations. |
| **WEBHOOK_DEV_TUNNEL_SETUP.md** | Microsoft Dev Tunnel setup for local webhook development and subscription lifecycle. |

---

### scripts/

| File | Purpose |
|------|--------|
| **verify_graph_credentials.py** | Verifies Azure Graph API credentials (delegated or application mode). |
| **Functions** | |
| `verify_delegated()` | Runs device-code flow and tests Graph access. |
| `verify_application()` | Runs client-secret auth and tests Graph access. |

---

### src/ (core)

| File | Purpose |
|------|--------|
| **__init__.py** | Package marker for `src`. |
| **main.py** | Entry point; delegates to CLI app (`src.cli.app`). |
| **config.py** | Centralized configuration from environment variables. |
| **Classes / Functions** | |
| (module-level constants) | PROJECT_ROOT, DATA_DIR, OUTPUT_DIR, INBOX_PATH, SENT_ITEMS_PATH, OPENAI_API_KEY, LOG_DIR, LOG_FILE, LOG_LEVEL, VERBOSE_LOGGING, PHOENIX_*, TARGET_SENDER, WEBHOOK_*, DEDUP_*, etc. |
| **orchestrator.py** | Orchestrates the full email workflow via LlamaIndex Workflow. Fetches thread, then delegates to `EmailOrchestratorWorkflow`. See [WORKFLOW_ARCHITECTURE.md](WORKFLOW_ARCHITECTURE.md). |
| **orchestrator_steps.py** | Step implementations (classify, extract, trigger, draft, aggregate, review, format, reply) used by the workflow. Each step includes OpenTelemetry tracing. |
| **workflow/events.py** | Custom event types for the workflow (ClassifiedEvent, ExtractedEvent, etc.). |
| **workflow/email_workflow.py** | `EmailOrchestratorWorkflow` class with `@step`-decorated methods. Event flow: StartEvent → classify → extract → trigger_or_s3 → draft → aggregate → review → format → send_or_draft → StopEvent. |
| **Functions** | |
| `_maybe_await()` | Awaits coroutines or returns sync values (for provider compatibility). |
| `process_trigger()` | Entry point: fetches thread by message_id/conversation_id, runs pipeline via workflow, sends reply. |
| `process_email_thread()` | Runs the `EmailOrchestratorWorkflow` and returns the ProcessingResult. |

---

### src/models/

| File | Purpose |
|------|--------|
| **__init__.py** | Package marker; re-exports model types. |
| **email.py** | Domain models for a single email and a thread. |
| **Classes** | |
| `Email` | Single message: id, sender, subject, body, timestamp, thread_id, sender_name. |
| `EmailThread` | Thread of emails: thread_id, emails list, latest_email. |
| **inputs.py** | Pydantic models for scenario-specific extracted inputs. |
| **Classes** | |
| `ProductSupplyInput` | S1: location, distributor, ndc, confidence. |
| `ProductAccessInput` | S2: customer, distributor, ndc, dea_number, address, is_340b, contact, confidence. |
| `ProductAllocationInput` | S3: urgency, year_start, year_end, distributor, ndc, confidence. |
| `CatchAllInput` | S4: topics, question_summary, confidence. |
| **outputs.py** | Pydantic models for agent outputs and end-to-end result. |
| **Classes** | |
| `ScenarioDecision` | A0 output: scenario (S1–S4), confidence, reasoning. |
| `DraftEmail` | A7/A8 output: subject, body, scenario, metadata. |
| `ReviewResult` | A10 output: status, confidence, quality_score, accuracy_notes, suggestions. |
| `FinalEmail` | A11 output: to, subject, body, review_status, metadata. |
| `ProcessingResult` | Full result: thread_id, scenario, decision_confidence, draft, review, final_email, raw_data. |
| **data.py** | Pydantic models for mock/CSV data used by trigger APIs. |
| **Classes** | |
| `InventoryRecord` | S1: ndc, product_name, location, quantity_available, distributor. |
| `CustomerRecord` | S2: customer_id, name, dea_number, is_340b, class_of_trade, address, rems_certified. |
| `AllocationRecord` | S3: distributor, ndc, allocation_percent, year, quantity_allocated, quantity_used. |
| `ProductRecord` | Product catalog: ndc, brand_name, description. |
| `PastEmailRecord` | RAG/S4: email_id, subject, body, topic. |

---

### src/agents/

| File | Purpose |
|------|--------|
| **__init__.py** | Package marker; re-exports registry functions, input_registry, and run functions (classify_thread, extract_*, draft_*, review_draft, format_final_email). |
| **registry.py** | Loads config/agents.yaml (fail-fast if missing); creates and caches Pydantic AI agents from config. |
| **Functions** | |
| `_load_config()` | Loads and validates YAML; validates scenario→agent references. |
| `reload_config()` | Clears cache and re-reads YAML. |
| `get_agent(agent_id, output_type)` | Returns cached or newly created Agent from config. |
| `get_agent_config(agent_id)` | Returns merged defaults + per-agent config. |
| `get_user_prompt_template(agent_id)` | Returns user prompt template string or None. |
| `get_scenario_config(scenario)` | Returns scenario dict (input_agent, trigger, draft_agent, low_confidence_threshold, etc.). |
| `get_all_config()` | Returns full parsed config (for API). |
| `save_config(config)` | Writes config to YAML and reloads. |
| **input_registry.py** | Maps agent IDs to (extract_fn, input_type); used by orchestrator for generic dispatch. |
| **Functions** | |
| `register_input_agent(agent_id, input_type)` | Decorator to register an extract function. |
| `get_input_agent(agent_id)` | Returns (extract_fn, input_type). |
| `list_input_agents()` | Returns registered input agent IDs. |
| **decision_agent.py** | Agent A0: classifies email thread into scenario S1/S2/S3/S4. Uses get_agent("A0_decision", ScenarioDecision); prompt from config. |
| **Functions** | |
| `_thread_to_prompt()` | Builds prompt text from thread. |
| `classify_thread()` | Returns ScenarioDecision (scenario, confidence, reasoning). |
| **input_agents.py** | Agents A1–A4: extract structured inputs per scenario. Each extract function is decorated with @register_input_agent; uses get_agent() with config prompt. |
| **Functions** | |
| `_thread_prompt()` | Builds thread summary for input agents. |
| `extract_supply()` | A1: ProductSupplyInput (registered as A1_supply_extract). |
| `extract_access()` | A2: ProductAccessInput (A2_access_extract). |
| `extract_allocation()` | A3: ProductAllocationInput (A3_allocation_extract). |
| `extract_catchall()` | A4: CatchAllInput (A4_catchall_extract). |
| **draft_agents.py** | Agents A7, A8: generate draft reply emails. Use get_agent() and get_user_prompt_template() from config. |
| **Functions** | |
| `draft_supply_or_access()` | A7: drafts reply for S1 or S2. |
| `draft_allocation_or_catchall()` | A8: drafts reply for S3 or S4. |
| **review_agent.py** | Agent A10: quality check; uses get_agent("A10_review") and template from config. |
| **Functions** | |
| `review_draft()` | Returns ReviewResult (approved/needs_human_review, confidence, notes, suggestions). |
| **email_agent.py** | Agent A11: final formatting; uses get_agent("A11_format") and template from config. |
| **Functions** | |
| `format_final_email()` | Produces FinalEmail; adds human-review header if flagged, personalizes with sender name. |

---

### src/mail_provider/

| File | Purpose |
|------|--------|
| **__init__.py** | Package marker; re-exports provider types and mapping. |
| **protocol.py** | Abstract interface for mail operations. |
| **Classes** | |
| `MailProvider` | Protocol: get_message(), get_conversation(), reply_to_message(). |
| **graph_models.py** | Pydantic models for Microsoft Graph message and send payload. |
| **Classes** | |
| `EmailAddress` | address, name. |
| `Recipient` | emailAddress (EmailAddress). |
| `ItemBody` | contentType, content. |
| `GraphMessage` | Graph message resource: id, conversationId, subject, body, from_, toRecipients, etc. |
| `SendPayload` | Payload for sending: to, subject, body, contentType, conversationId, internetMessageId. |
| **graph_mock.py** | Mock provider: reads inbox from JSON, writes sent items to JSON. |
| **Classes** | |
| `GraphMockProvider` | Implements MailProvider using local JSON files. |
| **Methods** | get_message(), get_conversation(), list_conversations(), reply_to_message(). |
| **graph_real.py** | Real Microsoft Graph API provider with retries and subscription support. |
| **Classes** | |
| `GraphProvider` | Implements MailProvider; delegated auth via MSAL token cache. |
| **Methods** | get_message(), get_conversation(), reply_to_message(), send_message(), create_subscription(), renew_subscription(), delete_subscription(), get_latest_from_sender(). |
| **Functions** | _is_transient_network_error(), _is_throttle_error(), _throttle_retry_delay_seconds(), _convert_sdk_message(). |
| **mapping.py** | Converts between Graph messages and domain models / send payload. |
| **Functions** | |
| `_parse_datetime()` | Parses Graph datetime strings. |
| `_sender_address()` | Extracts sender email from GraphMessage. |
| `_sender_name()` | Extracts sender display name from GraphMessage. |
| `graph_messages_to_thread()` | Converts list of GraphMessage to EmailThread (sanitizes body). |
| `final_email_to_send_payload()` | Builds SendPayload from FinalEmail and reply context. |

---

### src/triggers/

| File | Purpose |
|------|--------|
| **__init__.py** | Package marker; re-exports get_trigger, list_triggers, register_trigger, and trigger functions (so decorators run on import). |
| **registry.py** | Trigger function registry: maps trigger names (from config) to async callables. |
| **Functions** | |
| `register_trigger(name)` | Decorator to register a trigger function. |
| `get_trigger(name)` | Returns the trigger function; raises ValueError if unknown. |
| `list_triggers()` | Returns registered trigger names. |
| **inventory_api.py** | Mock Inventory API for S1; `inventory_api_fetch()` decorated with @register_trigger("inventory_api"). |
| **access_api.py** | Mock Access API for S2; `access_api_fetch()` with @register_trigger("access_api"). |
| **allocation_api.py** | Mock Allocation API for S3; `allocation_api_simulate()` with @register_trigger("allocation_api"). |
| **rag_search.py** | Mock RAG search for S4; `rag_search_find_similar()` with @register_trigger("rag_search"). |

---

### src/utils/

| File | Purpose |
|------|--------|
| **__init__.py** | Package marker; re-exports logger, tracing, loaders, etc. |
| **logger.py** | Structured logging with Structlog (console + JSONL file). |
| **Functions** | |
| `_coerce_level()` | Converts level name to logging constant. |
| `_configure_logging()` | Sets up handlers and formatters. |
| `get_logger()` | Returns bound logger with optional bindings. |
| `bind_context()` | Binds key-value context to global logger. |
| `unbind_context()` | Removes context keys. |
| `clear_context()` | Clears all context. |
| `log_agent_step()` | Logs agent step with name, step, and optional data. |
| **tracing.py** | Phoenix/OpenTelemetry tracing setup. |
| **Functions** | |
| `_resolve_protocol()` | Resolves Phoenix protocol from env. |
| `_resolve_endpoint()` | Resolves collector endpoint URL. |
| `init_tracing()` | Initializes OTEL tracer provider and Pydantic AI instrumentation. |
| `get_tracer()` | Returns OpenTelemetry tracer. |
| **observability.py** | Helpers for span attributes and PII-safe previews. |
| **Functions** | |
| `thread_preview_for_observability()` | Builds PII-redacted thread preview for traces. |
| **body_sanitizer.py** | Email body sanitization pipeline (HTML→text, banners, quotes, signatures, PII, truncation). |
| **Functions** | html_to_text(), remove_security_banners(), remove_quoted_replies(), remove_signatures(), normalize_whitespace(), decode_special_characters(), truncate_long_content(), truncate_at(), redact_pii(), sanitize_email_body(), sanitize_for_observability(). |
| **Pipelines** | DEFAULT_PIPELINE, MINIMAL_PIPELINE, AGGRESSIVE_PIPELINE, OBSERVABILITY_PIPELINE. |
| **email_parser.py** | Parse email CSV rows and build threads. |
| **Functions** | |
| `parse_email_csv_row()` | Parses a CSV row dict into Email. |
| `build_threads()` | Groups emails by thread_id into list of EmailThread. |
| **csv_loader.py** | Load mock data from CSV files. |
| **Functions** | |
| `_read_csv()` | Reads CSV file to list of dicts. |
| `load_emails_csv()` | Loads emails from CSV. |
| `load_inventory()` | Loads inventory CSV. |
| `load_customers()` | Loads customers CSV. |
| `load_allocations()` | Loads allocations CSV. |
| `load_products()` | Loads products CSV. |
| `load_past_emails()` | Loads past emails CSV for RAG. |

---

### src/cli/

| File | Purpose |
|------|--------|
| **__init__.py** | Typer app setup; registers interactive, batch, graph, webhook, validate-config commands; initializes tracing. |
| **Functions** | |
| `register_commands()` | Registers all CLI commands with the Typer app. |
| **shared.py** | Shared CLI helpers: console, logger, output paths, result formatting. |
| **validate_config.py** | Validates config/agents.yaml: checks scenario→agent and scenario→trigger references, prints summary table. |
| **Functions** | |
| `validate_config()` | CLI command for `validate-config`. |
| **interactive_mode.py** | Interactive mode: list conversations, pick one, process and send. |
| **batch_mode.py** | Batch mode: process all conversations in inbox. |
| **graph_mode.py** | Graph mode: process latest email from sender via real Graph API. |
| **webhook_mode.py** | Webhook mode: run FastAPI listener for Graph change notifications. |
| **Functions** | (shared.py) get_mock_provider(), ensure_output_dirs(), write_json_result(), append_csv_log_row(), result_to_serializable(), print_result(), processing_log_row(). (Mode modules) interactive(), batch(), graph(), webhook(). |

---

### src/auth/

| File | Purpose |
|------|--------|
| **__init__.py** | Package marker. |
| **token_cache.py** | MSAL token cache for persistent delegated auth (device code flow). |
| **Classes** | |
| `MSALDelegatedCredential` | TokenCredential implementation with file-based token cache. |
| **Functions** | |
| `_ensure_cache_dir()` | Ensures cache directory exists. |
| `_load_cache()` | Loads token cache from disk. |
| `_save_cache()` | Saves token cache to disk. |
| `get_persistent_device_code_credential()` | Returns TokenCredential with persistent cache. |

---

### src/webhook/

| File | Purpose |
|------|--------|
| **__init__.py** | Package marker; re-exports server, models, subscription, dedup, filter. |
| **models.py** | Pydantic models for Graph change notifications. |
| **Classes** | |
| `ResourceData` | Resource data in notification: odata_type, id. |
| `ChangeNotification` | Single change notification: change_type, client_state, resource, resource_data, subscription_id, etc. |
| `ChangeNotificationBatch` | Request body: value (list of ChangeNotification). |
| **server.py** | FastAPI webhook server: validation, notification handler, worker pool, dedup, allowed-senders filter; includes config router. |
| **config_routes.py** | Config API router: GET/PUT /config/agents, POST /config/agents/reload, GET /config/scenarios. |
| **Endpoints** | GET/POST /webhook/notifications, GET /health, GET/POST/DELETE /webhook/allowed-senders, POST /webhook/allowed-senders/reload; GET/PUT /config/agents, GET/PUT /config/agents/{id}, POST /config/agents/reload, GET /config/scenarios, GET /config/scenarios/{id}. |
| **Functions** (server.py) | _parse_notification_resource(), _run_process_trigger(), _process_notification_message(), _notification_worker(), _setup_workers(), _setup_provider(), _shutdown_tasks(), _lifespan(), create_app(). |
| **subscription.py** | Graph subscription lifecycle. |
| **Functions** | |
| `create_subscription()` | Creates webhook subscription. |
| `renew_subscription()` | Renews subscription expiration. |
| `delete_subscription()` | Deletes subscription. |
| `list_subscriptions()` | Lists current subscriptions. |
| **dedup_store.py** | Persistent deduplication store for webhook notifications. |
| **Classes** | |
| `DedupStore` | Thread-safe store: triggered IDs, conversation cooldown, in-flight, failed IDs with TTL. |
| **Methods** | has_triggered(), mark_triggered(), is_processing(), add_processing(), remove_processing(), mark_failed(), has_failed(), has_recent_reply(), mark_replied(). |
| **filter_config.py** | Allowed-senders filter: load/save JSON, validate and normalize emails. |
| **Functions** | |
| `get_filter_config_path()` | Returns path to filter config (env override supported). |
| `is_valid_email()` | Validates email format. |
| `_normalize_email()` | Normalizes email for comparison. |
| `_parse_config()` | Loads and parses config file. |
| `load_allowed_senders()` | Returns list of allowed sender addresses. |
| `save_allowed_senders()` | Saves allowed senders to JSON. |

---

### tests/

| File | Purpose |
|------|--------|
| **__init__.py** | Package marker for tests. |
| **test_agent_registry.py** | Unit tests for agent registry: fail-fast missing config, config structure, get_agent_config merging, get_scenario_config, get_user_prompt_template, agent caching, reload_config. |
| **test_dedup_store.py** | Unit tests for DedupStore. |
| **Tests** (dedup) | test_triggered_persistence, test_conversation_cooldown, test_processing_in_flight, test_mark_triggered_atomic. |

---

## 5. Scenario Quick Reference

Scenario wiring is defined in **config/agents.yaml** (see [AGENTS_CONFIG.md](AGENTS_CONFIG.md)). The orchestrator looks up input_agent, trigger, and draft_agent by scenario code.

| Scenario | Name            | Input Agent (config) | Trigger (config) | Draft Agent (config) |
|----------|-----------------|----------------------|------------------|----------------------|
| S1       | Product Supply  | A1_supply_extract    | inventory_api    | A7_draft             |
| S2       | Product Access  | A2_access_extract    | access_api       | A7_draft             |
| S3       | Product Allocation | A3_allocation_extract | allocation_api | A8_draft             |
| S4       | Catch-All       | A4_catchall_extract  | rag_search       | A8_draft             |

After drafting, all scenarios flow through **Review Agent A10** and **Email Agent A11**, then send via the configured **MailProvider**.
