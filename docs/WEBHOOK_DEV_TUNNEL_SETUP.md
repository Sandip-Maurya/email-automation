# Webhook and Microsoft Dev Tunnel Setup

This guide explains how to run the email automation app as a **listening system** that receives Microsoft Graph change notifications (webhooks) and triggers the agent pipeline when new mail arrives. For local development, Microsoft Dev Tunnels expose your local server over HTTPS so Graph can deliver notifications.

## Overview

1. **Webhook server** (FastAPI) runs on a port (default 8000).
2. **Dev Tunnel** forwards a public HTTPS URL (e.g. `https://abc123.devtunnels.ms`) to `localhost:8000`.
3. You **create a Graph subscription** with that URL as the notification endpoint.
4. When new mail arrives, Graph POSTs to the tunnel URL; the webhook handler filters by sender and runs the agent pipeline.

## Prerequisites

- Azure app registration with **Delegated** permissions: `Mail.Read`, `Mail.Send`
- `.env` configured with `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, and (for webhook) `TARGET_SENDER`, `WEBHOOK_URL`, `WEBHOOK_CLIENT_STATE`

## 1. Install Microsoft Dev Tunnel

**Windows (winget):**

```powershell
winget install Microsoft.devtunnel
```

**Or** install the [Dev Tunnels CLI](https://learn.microsoft.com/en-us/azure/developer/dev-tunnels/get-started?tabs=windows) for your OS.

Log in once:

```powershell
devtunnel user login
```

## 2. Create and run a tunnel

In a **separate terminal** from the webhook server:

```powershell
# Create a tunnel (one-time; name e.g. email-webhook)
devtunnel create email-webhook --allow-anonymous

# Add port 8000 so the tunnel forwards to localhost:8000
devtunnel port create email-webhook -p 8000

# Start hosting (leave this running)
devtunnel host email-webhook
```

The output will show a URL like `https://xxxxx-xxxxx.devtunnels.ms`. Copy it.

## 3. Configure .env for webhook

Add or set:

```env
WEBHOOK_PORT=8000
WEBHOOK_URL=https://your-tunnel-id.devtunnels.ms
WEBHOOK_CLIENT_STATE=your-random-secret-for-validation
SUBSCRIPTION_EXPIRATION_MINUTES=4000
TARGET_SENDER=allowed-sender@example.com
```

- `WEBHOOK_URL`: The dev tunnel URL from step 2 (no trailing slash).
- `WEBHOOK_CLIENT_STATE`: Any random string (e.g. 32 chars); used to verify notifications come from your subscription.

Optional webhook tuning (defaults are usually fine):

| Variable | Default | Description |
|----------|---------|-------------|
| `WEBHOOK_SUBSCRIPTION_RESOURCE` | `me/mailFolders('Inbox')/messages` | Subscription resource (Inbox-only avoids sent-item 404s) |
| `WEBHOOK_FETCH_MAX_ATTEMPTS` | `5` | Retries when fetching message after notification |
| `WEBHOOK_FETCH_BASE_DELAY` | `2.0` | Base delay (seconds) for exponential backoff |
| `WEBHOOK_FAILED_MSG_TTL_SECONDS` | `600` | TTL for "message not found" dedup (avoid re-enqueueing) |

## 4. Start the webhook server and create subscription

**Terminal 1** – start the tunnel (if not already running):

```powershell
devtunnel host email-webhook
```

**Terminal 2** – start the webhook server and create the subscription:

```bash
# Start listener and create subscription in one go
python -m src.main webhook --port 8000 --create-subscription
```

On first run you may be prompted to sign in (device code flow). Tokens are cached in `~/.email-automation/token_cache.json` for subsequent runs.

You should see:

- Subscription created with an ID.
- Server listening on `http://0.0.0.0:8000`.

## 5. Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/webhook/notifications` | GET, POST | Graph validation and change notifications |
| `/health` | GET | Health check |

Graph will send a **validation** request to `/webhook/notifications?validationToken=...` when creating the subscription; the server responds with the token as plain text. Change notifications are POSTed to the same path with a JSON body.

## 6. Sender filtering

Only messages from the configured `TARGET_SENDER` trigger the pipeline. Other senders are logged and skipped. Set `TARGET_SENDER` in `.env` or leave empty to process all new mail (not recommended for production).

## 7. Subscription lifecycle

- Subscriptions expire (max ~3 days for mail). Renew before expiry or use `--create-subscription` again after restart.
- To list or manage subscriptions programmatically, use `src.webhook.subscription` (e.g. `renew_subscription`, `delete_subscription`) or the Graph API.

## Troubleshooting

- **ValidationError when creating subscription**: Ensure the tunnel is running and the URL is reachable from the internet. Respond with HTTP 200 and the exact `validationToken` as plain text.
- **No notifications**: Confirm the subscription was created, the tunnel is hosting, and the webhook server is running. Check Graph subscription expiration.
- **Token expired**: Sign in again; the next run will refresh and cache tokens via the token cache.
- **Notification delay or "email in Outlook but app doesn't see it"**: The app returns HTTP 202 to Microsoft as soon as it receives the POST (so Graph doesn't time out). Processing (fetching the message, sender filter, pipeline) runs in the background. If you still see long delays: (1) Graph can take a few seconds to a minute to emit the notification after the message lands in the mailbox. (2) Dev Tunnel adds one network hop. (3) Check that the sender is in allowed senders (`config/filter.json` or `/webhook/allowed-senders`). (4) Check logs for `sender_filter`, `skip_conversation_cooldown`, or `get_message.error` (transient errors are retried; repeated failures mean the message fetch is failing).
- **"message_not_found_after_retry" in logs**: The subscription is **Inbox-only** by default so you should only get notifications for Inbox messages. If you still see this: (1) The message may have been moved or deleted before the app could fetch it. (2) Failed message IDs are remembered for `WEBHOOK_FAILED_MSG_TTL_SECONDS` (default 10 minutes) so the same ID is not retried endlessly. (3) Fetch uses exponential backoff (2s, 4s, 8s, 16s) to cope with Graph eventual consistency. If you previously used `me/messages`, recreate the subscription (restart with `--create-subscription`) so the new Inbox-only resource takes effect.
- **429 ApplicationThrottled / MailboxConcurrency**: Too many concurrent requests to the same mailbox. The app retries 429 with exponential backoff (10s, 20s, 40s, …). To reduce how often this happens, lower `WEBHOOK_WORKER_COUNT` (default is 4). If you see repeated throttle errors, set `WEBHOOK_WORKER_COUNT=2` in `.env`.
