# Pharmaceutical Email Agentic Network

Multi-agent email automation system for pharmaceutical trade operations. The system processes incoming emails, classifies them into scenarios, extracts relevant data, drafts professional responses, and sends replies via Microsoft Graph API.

## Features

- **Multi-Agent Pipeline**: Decision → Input → Draft → Review → Email agents
- **4 Scenario Types**: Product Supply (S1), Product Access (S2), Product Allocation (S3), Catch-All (S4)
- **Phoenix Dashboard**: Full OpenTelemetry tracing with LLM call visualization
- **Structured Logging**: Colored console output + JSONL file logging via Structlog
- **Graph API Ready**: Azure AD app registration with verified credentials
- **CLI Modes**: Interactive, batch, graph (latest from sender), webhook (listening)

## Architecture

```
Trigger (message_id/conversation_id)
    │
    ▼
Decision Agent (A0) ─── Classify → S1/S2/S3/S4
    │
    ├─── S1: Product Supply ─── A1 Extract → Inventory API → A7 Draft
    ├─── S2: Product Access ─── A2 Extract → Access API → A7 Draft  
    ├─── S3: Product Allocation ─── A3 Extract → Allocation API → A8 Draft
    └─── S4: Catch-All ─── A4 Extract → RAG Search → A8 Draft
    │
    ▼
Review Agent (A10) ─── Quality check, approval/flag
    │
    ▼
Email Agent (A11) ─── Final formatting
    │
    ▼
Mail Provider ─── Reply via Graph API (mock or real)
```

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager
- OpenAI API key

### Installation

```bash
# Clone and navigate to project
cd email-automation

# Install dependencies
uv sync
```

### Configuration

Create a `.env` file:

```env
# Required
OPENAI_API_KEY=sk-your-openai-key

# Logging
LOG_LEVEL=INFO
VERBOSE_LOGGING=true

# Phoenix Tracing (optional)
PHOENIX_ENABLED=true
PHOENIX_COLLECTOR_ENDPOINT=http://localhost:6006/v1/traces
PHOENIX_PROJECT_NAME=email-automation
PHOENIX_API_KEY=your-phoenix-api-key  # For cloud Phoenix

# Azure/Graph API (delegated auth only; sign in via device code)
AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_ID=your-client-id
USE_REAL_GRAPH=false  # Set to true to use real Graph API
```

### Run

```bash
# Interactive mode - list and select conversations (mock inbox)
uv run python -m src.main interactive

# Batch mode - process all conversations (mock inbox)
uv run python -m src.main batch

# Graph mode - process latest email from a sender (real Graph API, delegated auth)
uv run python -m src.main graph --sender=someone@example.com

# Webhook mode - listen for Graph notifications and trigger pipeline (see docs/WEBHOOK_DEV_TUNNEL_SETUP.md)
uv run python -m src.main webhook --port 8000 --create-subscription
```

### Webhook mode (real-time notifications)

The app can run as a **listening service** that receives Microsoft Graph change notifications and runs the agent pipeline for new mail. The subscription is **Inbox-only** by default (`me/mailFolders('Inbox')/messages`) to avoid notifications for sent items and folder transitions that can cause "message not found" errors. For local development you need a public HTTPS URL (e.g. via [Microsoft Dev Tunnels](https://learn.microsoft.com/en-us/azure/developer/dev-tunnels/)). Full setup: **[docs/WEBHOOK_DEV_TUNNEL_SETUP.md](docs/WEBHOOK_DEV_TUNNEL_SETUP.md)**.

**Allowed senders filter**: The pipeline is triggered only for messages **from** addresses listed in a JSON config file (`config/filter.json` by default). Invalid email formats are rejected. You can list, add, and remove allowed senders via REST APIs. See **[docs/FILTER_CONFIG.md](docs/FILTER_CONFIG.md)** for the config format and `GET/POST/DELETE /webhook/allowed-senders` (and `POST .../reload`).

**Webhook-related env vars** (optional overrides):

| Variable | Default | Description |
|----------|---------|-------------|
| `WEBHOOK_SUBSCRIPTION_RESOURCE` | `me/mailFolders('Inbox')/messages` | Graph resource path for the subscription |
| `WEBHOOK_FETCH_MAX_ATTEMPTS` | `5` | Retries when fetching a message (Graph eventual consistency) |
| `WEBHOOK_FETCH_BASE_DELAY` | `2.0` | Base delay in seconds for exponential backoff between fetch retries |
| `WEBHOOK_FAILED_MSG_TTL_SECONDS` | `600` | How long to remember failed message IDs (avoid re-enqueueing) |

## Data

- **Inbox**: `data/inbox.json` — Graph-format message array
- **Output**: `output/responses.json` — Processing results
- **Logs**: `output/processing_log.csv` — Summary log
- **Sent Items**: `output/sent_items.json` — Sent email store

## Observability

### Phoenix Dashboard (Tracing)

The system uses Phoenix with OpenTelemetry for comprehensive tracing:

```bash
# Start local Phoenix server
phoenix serve

# Dashboard at http://localhost:6006
```

**Traced Operations**:
- Full pipeline execution (`process_trigger`)
- Each agent step (A0, A1-A4, A7/A8, A10, A11)
- External trigger/API calls
- Email send operations
- LLM calls (auto-instrumented via Pydantic AI)

**Configuration**:
| Variable | Description |
|----------|-------------|
| `PHOENIX_ENABLED` | Enable/disable tracing |
| `PHOENIX_COLLECTOR_ENDPOINT` | Phoenix endpoint URL |
| `PHOENIX_PROJECT_NAME` | Project name in dashboard |
| `PHOENIX_API_KEY` | API key for Phoenix cloud |

### Structured Logging (Structlog)

Dual-output logging with context binding:

- **Console**: Colored, human-readable output
- **File**: `output/logs/app.jsonl` (JSON Lines format)

```bash
# View logs in real-time
tail -f output/logs/app.jsonl | jq .

# Filter by level
cat output/logs/app.jsonl | jq 'select(.level == "error")'
```

**Configuration**:
| Variable | Description |
|----------|-------------|
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `VERBOSE_LOGGING` | Enable debug-level logging |

## Azure Integration

### App Registration

The system supports Microsoft Graph API for real email operations. Complete setup guide available at [docs/AZURE_SETUP_GUIDE.md](docs/AZURE_SETUP_GUIDE.md).

### Verify Credentials

Test your Azure credentials (delegated auth) before using graph or webhook mode:

```bash
uv run python scripts/verify_graph_credentials.py
```

The script will:
1. Verify environment variables
2. Test authentication
3. Fetch sample messages
4. Display results

## Project Structure

```
email-automation/
├── src/
│   ├── agents/              # AI agents (decision, input, draft, review, email)
│   │   ├── decision_agent.py    # A0: Scenario classification
│   │   ├── input_agents.py      # A1-A4: Data extraction
│   │   ├── draft_agents.py      # A7, A8: Email drafting
│   │   ├── review_agent.py      # A10: Quality review
│   │   └── email_agent.py       # A11: Final formatting
│   ├── mail_provider/       # Graph API integration
│   │   ├── graph_mock.py        # Mock provider (JSON files)
│   │   ├── graph_models.py      # Pydantic models
│   │   └── protocol.py          # Provider interface
│   ├── models/              # Data models
│   │   ├── email.py             # Email and thread models
│   │   ├── inputs.py            # Extracted input models
│   │   └── outputs.py           # Processing result models
│   ├── triggers/            # External API integrations
│   │   ├── inventory_api.py     # S1: 852/Value Track
│   │   ├── access_api.py        # S2: Class of Trade/REMS
│   │   ├── allocation_api.py    # S3: DCS allocation
│   │   └── rag_search.py        # S4: Similar past emails
│   ├── utils/               # Utilities
│   │   ├── logger.py            # Structlog configuration
│   │   └── tracing.py           # Phoenix/OpenTelemetry setup
│   ├── config.py            # Configuration and settings
│   ├── orchestrator.py      # Pipeline orchestration
│   └── main.py              # CLI entry point
├── scripts/
│   └── verify_graph_credentials.py  # Azure credential verification
├── data/
│   └── inbox.json           # Input emails
├── output/
│   ├── logs/
│   │   └── app.jsonl        # Application logs
│   ├── responses.json       # Processing results
│   ├── processing_log.csv   # Summary log
│   └── sent_items.json      # Sent emails
├── docs/
│   ├── AZURE_SETUP_GUIDE.md         # Azure portal setup
│   ├── GRAPH_API_INTEGRATION_GUIDE.md # Python Graph API guide
│   └── IMPLEMENTATION_STATUS.md     # Feature status and roadmap
├── .env                     # Environment variables
├── pyproject.toml           # Project configuration
└── README.md                # This file
```

## Documentation

| Document | Description |
|----------|-------------|
| [Azure Setup Guide](docs/AZURE_SETUP_GUIDE.md) | Complete Azure AD app registration walkthrough |
| [Graph API Integration Guide](docs/GRAPH_API_INTEGRATION_GUIDE.md) | Python implementation guide for Graph email operations |
| [Implementation Status](docs/IMPLEMENTATION_STATUS.md) | Feature status, architecture details, and roadmap |

## Tech Stack

| Component | Technology |
|-----------|------------|
| AI Framework | Pydantic AI |
| LLM | OpenAI GPT-4o-mini |
| CLI | Typer + Rich |
| Logging | Structlog |
| Tracing | Phoenix + OpenTelemetry |
| Email API | Microsoft Graph SDK |
| Auth | MSAL (delegated, token cache) |

## Scenarios

| Scenario | Code | Description | Input Agent | Draft Agent |
|----------|------|-------------|-------------|-------------|
| Product Supply | S1 | Inventory, stock levels, NDC availability | A1 | A7 |
| Product Access | S2 | Customer access, REMS, 340B, DEA | A2 | A7 |
| Product Allocation | S3 | Allocation requests, limits, percentages | A3 | A8 |
| Catch-All | S4 | General inquiries, documentation, contact | A4 | A8 |

## License

Private / Internal Use
