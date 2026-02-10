# Webhook Demo – Detailed Guide (15–20 min)

This guide supports a **live demo** of the email automation POC in **webhook mode**: the webhook server receives Microsoft Graph notifications, we use Graph API to access mail content and send the final reply, and agents run in a pipeline with four business routes. Audience: technical and managerial.

**One-page cheat sheet:** [DEMO_WEBHOOK_MINDMAP.md](DEMO_WEBHOOK_MINDMAP.md).

---

## 1. Demo narrative and flow (15–20 min)

Use this as your script spine; timings are approximate.

**Intro (2–3 min)**  
*“As a POC we built a webhook server to receive notifications, used Microsoft Graph API to access mail content and send the final mail, and built agents that work in a pipeline. There are four routes aligned to business: product supply, product access, product allocation, and catch-all. Structured logging and Phoenix are in place for visibility and debugging. Let me show you the diagram first.”*  
Show the component/pipeline diagram (e.g. [CORE_WORKFLOW.md](CORE_WORKFLOW.md) or your slide).

**Demo setup and expectations (1–2 min)**  
*“Let’s see the demo in action. First I’ll add my email to the allowed sender list, then I’ll send a mail. Our app will: (1) read the notification, (2) get the full content of the mail, (3) have the classifier route to one of the four scenarios only, (4) use the input agent to infer entities for further processing and API calls, and (5) have the draft and email agents draft and send the reply based on the API result, extracted entities, and mail content. Let’s see everything in action.”*

**Live run (5–8 min)**  
- Add your email to allowed senders (API or `config/filter.json`).  
- Have **four mails ready** (one per scenario: S1, S2, S3, S4). Show **at least two routes** yourself (e.g. S1 and S4).  
- Point out in the terminal: notification received, full mail fetched, scenario (S1/S2/S3/S4), entity extraction, draft and send. Show the reply in the mailbox.  
- **Audience participation:** Ask someone to send a mail for another scenario (e.g. S2 or S3). **Add their email to the allowed sender list first**, then they send; watch the same flow and show the reply.

**Phoenix and observability (3–4 min)**  
Open Phoenix and find the trace for a run. Highlight:  
- **Input/output** and **system prompt** per agent for debugging.  
- **Latency** and **token usage** for LLM steps.  
- **Full request flow** from retrieving the mail thread through every intermediate step to sending the mail.

**Graph API and app registration (1–2 min)**  
Briefly explain how the app registers with Azure (delegated for demo: user sign-in; production: application type with client credentials), subscribes to Graph for Inbox change notifications, and uses Graph to get message content and send the reply.

**Q&A**  
Open for audience questions. Use the Q&A section below as prep.

---

## 2. Overview (for reference)

In webhook mode the app runs as a **listening service**. When new mail arrives, Graph sends a change notification to our endpoint. We fetch the message via Graph, filter by allowed sender, then run the pipeline: **classify** (A0) into one of four scenarios, **extract** entities (input agents), call the scenario **trigger** (inventory, access, allocation, or RAG), **draft** (A6–A9), **aggregate** (A11), **review** (A10), **format** (A12), and **send** the reply via Graph. Observability: structured logs and OpenTelemetry traces in Phoenix. Diagram: [CORE_WORKFLOW.md](CORE_WORKFLOW.md).

---

## 3. Prerequisites

- **Azure app registration** with **Delegated** permissions: `Mail.Read`, `Mail.Send` (for production we use **Application** type; see Q&A).
- **.env** with:
  - `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`
  - `OPENAI_API_KEY`
  - For webhook: `WEBHOOK_URL` (your dev tunnel URL), `WEBHOOK_CLIENT_STATE` (random secret), optional `TARGET_SENDER`
  - Optional: `PHOENIX_ENABLED`, `PHOENIX_COLLECTOR_ENDPOINT` (e.g. `http://localhost:6006/v1/traces`), `PHOENIX_PROJECT_NAME`
- **Microsoft Dev Tunnel** CLI installed and logged in.
- **Allowed senders**: the email address you send from must be in `config/filter.json` or added via the allowed-senders API.

Full setup steps: [WEBHOOK_DEV_TUNNEL_SETUP.md](WEBHOOK_DEV_TUNNEL_SETUP.md). Allowed senders: [FILTER_CONFIG.md](FILTER_CONFIG.md).

---

## 4. Before the demo – start order

Run in this order so the webhook can create the subscription and receive notifications.

1. **Terminal 1 – Phoenix**  
   ```bash
   phoenix serve
   ```  
   Dashboard: http://localhost:6006

2. **Terminal 2 – Dev Tunnel**  
   ```bash
   devtunnel host email-webhook
   ```  
   Leave running. Ensure `WEBHOOK_URL` in `.env` matches the tunnel URL (no trailing slash).

3. **Terminal 3 – Webhook server**  
   ```bash
   uv run python -m src.main webhook --port 8000 --create-subscription
   ```  
   On first run you may be prompted to sign in (device code). Confirm you see subscription created and server listening on `http://0.0.0.0:8000`.

**Verify**

- Subscription created (log line or Graph).
- Sender in allowed list: `GET http://localhost:8000/webhook/allowed-senders` or check `config/filter.json`.
- Optional: `GET http://localhost:8000/health`.

---

## 5. What to point out during the demo

**Terminal:** Notification received, `process_trigger.start`, classifier output (scenario S1/S2/S3/S4), input extraction, `process_trigger.complete`, `reply_complete`. Keep to 5–8 key lines.

**Mailbox:** Show the incoming reply and tie it to the scenario and pipeline (draft + review + send).

**Phoenix:** Open http://localhost:6006, find the trace (by time or thread_id). Walk: `webhook.receive` or `process_trigger` → `A0_classify` → `input_extract` → `trigger_fetch` → `draft` → `A11_aggregate` → `A10_review` → `A11_format` → `reply_to_message`. Call out: **input/output and system prompt** per agent, **latency and token usage**, and the **full flow** from retrieving the mail thread to sending the reply.

**Audience send:** Before they send, add their email to allowed senders (e.g. `POST /webhook/allowed-senders` with `{"email": "their@example.com"}` or add to `config/filter.json` and reload).

---

## 6. Sample email content (S1–S4)

**Full set (2–3 per scenario):** [DEMO_SAMPLE_EMAILS.md](DEMO_SAMPLE_EMAILS.md) — copy-paste ready Subject + Body for demo or to share with the audience.

Quick reference (one per scenario):

| Scenario | Intent | Example subject / body phrase |
|----------|--------|------------------------------|
| S1 – Product Supply | Inventory, stock, NDC | Can you confirm inventory for NDC 12345 at Distributor A? |
| S2 – Product Access | REMS, 340B, class of trade | What is our REMS status for product X? |
| S3 – Product Allocation | Allocation, year, distributor | Request allocation for 2025, NDC 11111. |
| S4 – Catch-All | General inquiry | What are your business hours? |

---

## 7. What to show, what not to show

**Show**

- Terminal logs (structured; key lines as above).
- Phoenix trace for one run (span tree and optionally attributes).
- Reply in the mailbox.
- Optionally: `GET /webhook/allowed-senders` or health check.

**Don’t show**

- `.env` or any file containing API keys or secrets.
- Full agent prompts (say *“prompts are in config/agents.yaml and can be updated via the config API”* and move on).

---

## 8. Troubleshooting

| Issue | What to check |
|-------|----------------|
| No notification | Subscription created? Tunnel running and URL correct in .env? Sender in allowed list? See [WEBHOOK_DEV_TUNNEL_SETUP.md](WEBHOOK_DEV_TUNNEL_SETUP.md) “Troubleshooting”. |
| No reply | Logs: `sender_filter` (sender not allowed), `message_not_found`, or other errors. Check [FILTER_CONFIG.md](FILTER_CONFIG.md) and allowed-senders. |
| Phoenix empty | `PHOENIX_ENABLED=true`, collector endpoint (e.g. `http://localhost:6006/v1/traces`), and that span names are in `config/trace_spans.json` allowlist if you use filtering. |
| Validation error on subscription | Tunnel must be reachable from the internet; server must respond with the validation token. |

---

## 9. Q&A – suggested list

Use these as a prep list before the session or during Q&A. Answers are 2–3 sentences.

### Core flow and setup

| Question | Suggested answer |
|----------|------------------|
| How does the app know when a new email arrives? | Microsoft Graph sends a change notification (webhook) to our endpoint when new mail hits the Inbox. We subscribe to that resource at startup (with `--create-subscription`). |
| Why do we need a tunnel? | Graph must POST to a public HTTPS URL. The tunnel exposes our local server so Graph can reach it during development. In production we’ll use a real public URL (e.g. app service or API gateway). |
| Who can trigger the pipeline? | Only senders listed in allowed senders (`config/filter.json` or the allowed-senders API). Others are ignored for safety. |
| What are S1, S2, S3, S4? | Four scenarios: Product Supply (inventory), Product Access (REMS/340B), Product Allocation (allocation requests), Catch-All (general). The classifier (A0) routes each thread to one. |
| Do we use real APIs for inventory/allocation? | Currently we use mock APIs (CSV-backed). Real 852/Value Track and DCS integration are planned; the pipeline and observability are ready. |
| How do we monitor and debug? | Structured logs in the terminal and in a JSONL file; plus Phoenix for traces. Every run has a trace with spans for classify, extract, trigger, draft, review, and send. |
| What if the reply is wrong? | The review agent (A10) can flag “needs_human_review.” We can extend to a human-in-the-loop step; for the demo we show the automated path. |
| How long do subscriptions last? | Graph mail subscriptions have a max lifetime (e.g. a few days). We set it via env; you can renew or recreate with `--create-subscription` on restart. In production we’d add a renewal job. |
| Is the pipeline config-driven? | Yes. Prompts and scenario wiring (which input agent, trigger, draft agent per scenario) are in `config/agents.yaml` and can be updated via the config API while the server runs. |

### Auth and production

| Question | Suggested answer |
|----------|------------------|
| Why “delegated” auth for the demo? What about production? | For the demo we use **delegated** permissions: a user signs in (device code), and the app acts on their behalf. In **production** we will register the app as **Application** type and use **application permissions** (client credentials or certificate). That way the app runs without interactive sign-in and can access the target mailbox(es) based on admin consent; no token cache or user session. |
| What’s the difference between delegated and application? | Delegated: app acts as the signed-in user; needs user consent/sign-in; good for dev and single-user demos. Application: app has its own identity; admin grants consent once; no user in the loop; required for unattended production services. |

### Scaling, deployment, and operations

| Question | Suggested answer |
|----------|------------------|
| How do we handle many emails at once? | The webhook returns 202 quickly and processes in a worker pool (configurable size). We can tune worker count and add a queue (e.g. Redis) if we need to scale or smooth bursts. |
| What if Microsoft throttles us (429)? | We retry with exponential backoff. Reducing concurrent workers per mailbox helps avoid throttling; we can also spread load across multiple app instances if needed. |
| Where will this run in production? | Typically as a hosted service (e.g. Azure App Service, container, or VM) with a stable HTTPS URL for the webhook, and application credentials stored in a secure vault. |
| Do we store or retain email content? | For the demo we don’t persist full bodies long-term; logs and traces use PII-safe summaries. Production policy (retention, compliance) would be defined separately and implemented as needed. |

### Security and compliance

| Question | Suggested answer |
|----------|------------------|
| How is the webhook endpoint secured? | We validate the subscription’s `client_state` on each notification so only our subscription’s callbacks are accepted. In production we’d add HTTPS, auth, and optionally signature verification. |
| Do we send email content to OpenAI? | Yes; the pipeline uses an LLM for classification and drafting. Data leaves our boundary to the LLM provider; for production we’d align with data-residency and DPA requirements. |
| Can someone abuse the endpoint? | Only allowed senders trigger the pipeline. Unknown senders are logged and skipped. Rate limiting and WAF can be added in front in production. |

### Observability and reliability

| Question | Suggested answer |
|----------|------------------|
| What if the LLM is slow or down? | We have retries in the agent layer. For production we’d define timeouts, fallback behaviour (e.g. “needs_human_review” or queue for retry), and alerting. |
| Can we trace a single email end-to-end? | Yes. Each run has a trace in Phoenix with a root span (e.g. `process_trigger` or `webhook.receive`) and child spans; you can filter by time or by attributes like thread_id. |
| Where are logs stored? | Console (structured) and a JSONL file (e.g. `output/logs/app.jsonl`). In production we’d ship to a central log store (e.g. Log Analytics, Splunk) and optionally retain per compliance policy. |

---

**See also:** [DEMO_WEBHOOK_MINDMAP.md](DEMO_WEBHOOK_MINDMAP.md), [WEBHOOK_DEV_TUNNEL_SETUP.md](WEBHOOK_DEV_TUNNEL_SETUP.md), [FILTER_CONFIG.md](FILTER_CONFIG.md), [CORE_WORKFLOW.md](CORE_WORKFLOW.md), [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md).
