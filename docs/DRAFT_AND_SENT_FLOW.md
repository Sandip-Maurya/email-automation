# Draft-only flow, Sent correlation, and analytics

This document describes how the system creates reply **drafts** instead of sending immediately, how it detects when a human has sent a draft, and how both the agent draft and the sent version are stored and exposed via analytics.

---

## Overview

- **Draft-only (default):** The pipeline creates a reply **draft** in the user's Drafts folder and persists a row in the `email_outcomes` table. No email is sent by the app.
- **Human review and send:** A human opens Drafts in Outlook/OWA, may edit the draft, and sends it. The system does not send the email.
- **Sent detection:** A second Microsoft Graph subscription on **Sent Items** notifies the app when a new message appears in Sent. The app correlates that message to the stored draft using **Immutable ID** (the same Graph id for the draft and the sent item) and updates the row with the sent content (subject, body, to, sent_at).
- **Replace draft:** If the same conversation is processed again (e.g. new email in thread), the previous draft for that conversation is marked **superseded** and a new draft is created.

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DRAFT_ONLY` | `true` | When true, create draft and persist; do not send. When false, pipeline sends via `reply_to_message` (legacy behaviour). |
| `WEBHOOK_SENT_RESOURCE` | `me/mailFolders('SentItems')/messages` | Graph resource for the Sent Items subscription. |

---

## Correlation: Immutable ID

Microsoft Graph supports **immutable identifiers** for messages: the same id is used when an item moves between folders (e.g. from Drafts to Sent). See [Obtain immutable identifiers for Outlook resources](https://learn.microsoft.com/en-us/graph/outlook-immutable-id).

- When creating the reply draft, the app sends the header **`Prefer: IdType="ImmutableId"`** so the returned message id is immutable.
- When creating the **Sent Items** subscription, the same header is used so change notifications contain the immutable id.
- When the Sent webhook fires, the notification’s resource id is the same as the id we stored for the draft, so we can look up the `email_outcomes` row and update it with the sent content. No correlation token in the body is needed.

---

## Single table: `email_outcomes`

One row per outcome (agent draft + optional sent version). Key: **`message_id`** (Graph immutable id).

| Column | Description |
|--------|-------------|
| `id` | Primary key |
| `message_id` | Graph immutable message id (draft id; same after send). Unique. |
| `conversation_id`, `user_id`, `user_name` | Context (user_name optional, from message/mailbox when available). |
| `reply_to_message_id`, `scenario` | Reply and scenario (S1–S4). |
| `draft_subject`, `draft_body`, `final_subject`, `final_body`, `metadata_json` | Agent draft and formatted content. |
| `status` | `draft_created` \| `sent` \| `superseded` |
| `created_at`, `superseded_at` | Lifecycle timestamps. |
| `sent_subject`, `sent_body`, `sent_to`, `sent_at` | Filled when the Sent webhook updates the row (human sent the draft). |

---

## Flow summary

1. **Inbox notification** → Worker runs `process_trigger` (draft-only). Orchestrator: supersede previous draft for this conversation, create reply draft via Graph (ImmutableId), insert row into `email_outcomes`, put `draft_message_id` in `raw_data`. No send.
2. **Human** opens Drafts, optionally edits, sends from Outlook.
3. **Sent notification** → Worker runs `_handle_sent_notification`: fetch message by id (ImmutableId), find row by `message_id`, update `sent_*` and `status = 'sent'`. Optionally call `mark_replied(conversation_id)` for cooldown.

---

## Analytics APIs

All under **`/webhook/analytics`** (when the webhook server is running).

| Method | Path | Description |
|--------|------|-------------|
| GET | `/webhook/analytics/counts` | Total counts by status: `draft_created`, `sent`, `superseded`. Optional query params: `from`, `to` (ISO date/datetime). |
| GET | `/webhook/analytics/draft-vs-sent` | List of outcomes with both draft and sent data (`status = 'sent'`). Returns draft vs sent subject/body and a `changed` flag. Optional `limit`, `offset`. |
| GET | `/webhook/analytics/by-scenario` | Counts per scenario (S1–S2–S3–S4): draft_created, sent, superseded. Optional `from`, `to`. |
| GET | `/webhook/analytics/by-user` | Counts per `user_id` (or `"default"` when null), including `user_name` when stored. Optional `from`, `to`. |

---

## Subscriptions

When the webhook server starts with subscription config (e.g. `--create-subscription`), it creates **two** subscriptions:

1. **Inbox** — resource from `WEBHOOK_SUBSCRIPTION_RESOURCE`, with **ImmutableId**.
2. **Sent** — resource from `WEBHOOK_SENT_RESOURCE`, with **ImmutableId**.

The notification handler routes by `subscription_id`: if it matches the Sent subscription id, it runs `_handle_sent_notification`; otherwise it runs the Inbox path (filters + `process_trigger`).
