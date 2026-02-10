# Webhook Demo – One-Page Mind Map (15–20 min)

**Purpose:** At-a-glance sheet for the presenter: script flow, start order, what to show.

---

### Demo flow (script at a glance)

1. **Intro:** POC = webhook server + Graph API (read mail, send reply) + agents in pipeline; 4 routes (product supply, product access, product allocation, catch-all). Structured logging + Phoenix for visibility. *“Let me show you the diagram first.”*
2. **Setup:** Add your email to allowed senders. Set expectations: (1) read notification (2) get full mail content (3) classifier → one of 4 scenarios (4) input agent → entities for API (5) draft + send from API + entities + mail.
3. **Live:** Send mail(s). Have 4 mails ready (S1–S4); show at least 2 routes. Ask audience to send for another case — **add their email to allowed senders first.**
4. **Phoenix:** Show trace — input/output, system prompt, latency, tokens, full flow from retrieve thread to send.
5. **Graph/app registration:** How we subscribe and use Graph (delegated demo; production = application type).
6. **Q&A.**

---

### 1. Before demo – start order

```
  Prereqs: Azure app, .env, tunnel, allowed senders, Phoenix

  Start order:
      1  -->  Phoenix   (phoenix serve)
      2  -->  Tunnel    (devtunnel host email-webhook)
      3  -->  Webhook   (webhook --port 8000 --create-subscription)
```

---

### 2. Live flow (notification to reply)

```
  Graph notification
         |
         v
  Webhook receives  -->  Filter by sender  -->  Fetch thread
         |
         v
  Classify (S1 / S2 / S3 / S4)
         |
         v
  Extract  -->  Trigger API  -->  Draft (A6-A9)
         |
         v
  A11 aggregate  -->  A10 review  -->  A12 format
         |
         v
  Send reply
```

---

### 3. What to show / don't show

```
  SHOW                          DON'T SHOW
  -----                         ----------
  Terminal:                     .env
    process_trigger             API keys
    scenario, reply_complete    Full prompts

  Phoenix:
    webhook.receive -> ... -> reply_to_message

  Mailbox:
    Incoming reply

  Sample emails:  S1 inventory | S2 access/REMS | S3 allocation | S4 catch-all
```

---

## Pre-demo checklist

- [ ] Tunnel running; `WEBHOOK_URL` in .env points to it
- [ ] Your sender email in allowed senders (`config/filter.json` or `POST /webhook/allowed-senders`)
- [ ] Phoenix: `phoenix serve`; dashboard http://localhost:6006
- [ ] Webhook server: `uv run python -m src.main webhook --port 8000 --create-subscription`
- [ ] Subscription created and server listening
- [ ] Four mails ready (one per S1, S2, S3, S4) for copy-paste or quick send

## Start order

1. **Terminal 1:** `phoenix serve`
2. **Terminal 2:** `devtunnel host email-webhook`
3. **Terminal 3:** `uv run python -m src.main webhook --port 8000 --create-subscription`

## Key log lines (terminal)

- Notification received / `process_trigger.start`
- `A0_classify` → scenario (S1/S2/S3/S4)
- `process_trigger.complete` / `reply_complete`

## Phoenix – what to call out

- **Trace path:** `webhook.receive` or `process_trigger` → `A0_classify` → `input_extract` → `trigger_fetch` → `draft` → `A11_aggregate` → `A10_review` → `A11_format` → `reply_to_message`
- **Usefulness:** input/output and system prompt per agent, latency, token usage, full flow from retrieve thread to send

## Sample one-liners (email body)

| Scenario | Example phrase |
|----------|----------------|
| S1 | Can you confirm inventory for NDC 12345 at Distributor A? |
| S2 | What is our REMS status for product X? |
| S3 | Request allocation for 2025, NDC 11111. |
| S4 | What are your business hours? |

---

**Audience send:** Add their email to allowed senders before they send. Then Q&A.  
*Full script and Q&A: [DEMO_WEBHOOK_GUIDE.md](DEMO_WEBHOOK_GUIDE.md). Setup: [WEBHOOK_DEV_TUNNEL_SETUP.md](WEBHOOK_DEV_TUNNEL_SETUP.md).*
