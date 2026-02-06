# Allowed Senders Filter Config

The webhook only triggers the pipeline for new messages whose **sender** (From address) is in a configured list. This list is stored in a JSON config file and can be managed via REST APIs.

## Config file

- **Path**: `config/filter.json` (project root). Override with env `FILTER_CONFIG_PATH`.
- **Format**: JSON only. Single key `allowed_senders` — a list of email addresses.

Example `config/filter.json`:

```json
{
  "allowed_senders": [
    "sender1@example.com",
    "sender2@example.com"
  ]
}
```

Copy `config/filter.example.json` to `config/filter.json` and edit the list as needed.

- **Validation**: Invalid email formats are rejected. When loading the file, invalid entries are skipped and a warning is logged. When adding via API, invalid emails return `400` with a clear message.
- **Empty list or missing file**: No senders are allowed, so the pipeline is never triggered (strict default).

The webhook loads this list at startup and after any API mutation; you can also reload from file without restart using the reload endpoint.

## API endpoints

All endpoints are on the webhook server (e.g. `http://localhost:8000` when running `python -m src.main webhook --port 8000`).

| Method | Path | Description |
|--------|------|-------------|
| GET | `/webhook/allowed-senders` | List allowed sender emails. Optional query `?q=substring` for case-insensitive search. |
| POST | `/webhook/allowed-senders` | Append an email. Body: `{"email": "user@example.com"}`. Validates format; persists and refreshes. |
| DELETE | `/webhook/allowed-senders` | Remove an email. Use query `?email=user@example.com` or body `{"email": "user@example.com"}`. |
| POST | `/webhook/allowed-senders/reload` | Reload the list from the config file and return the new list. |

Responses return `{"allowed_senders": ["...", ...]}` (and optionally `added`/`removed`/`message`). Invalid email on POST returns `400`. Delete of an email not in the list returns `404`.
