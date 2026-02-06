"""Configuration and settings."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "output"
INBOX_PATH = DATA_DIR / "inbox.json"
SENT_ITEMS_PATH = OUTPUT_DIR / "sent_items.json"

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Logging
LOG_DIR = OUTPUT_DIR / "logs"
LOG_FILE = LOG_DIR / "app.jsonl"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
VERBOSE_LOGGING = os.getenv("VERBOSE_LOGGING", "true").lower() == "true"

# Ensure log directory exists
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Phoenix / OpenTelemetry
PHOENIX_ENABLED = os.getenv("PHOENIX_ENABLED", "true").lower() == "true"
PHOENIX_COLLECTOR_ENDPOINT = os.getenv(
    "PHOENIX_COLLECTOR_ENDPOINT",
    "http://localhost:6006/v1/traces",
)
PHOENIX_PROJECT_NAME = os.getenv("PHOENIX_PROJECT_NAME", "email-automation")
PHOENIX_API_KEY = os.getenv("PHOENIX_API_KEY", "")
PHOENIX_PROTOCOL = os.getenv("PHOENIX_PROTOCOL", "").lower() or None  # "http/protobuf" | "grpc" | None=infer

# Graph API (for real provider)
TARGET_SENDER = os.getenv("TARGET_SENDER", "")

# Webhook (Graph change notifications)
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "8000"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").rstrip("/")
WEBHOOK_CLIENT_STATE = os.getenv("WEBHOOK_CLIENT_STATE", "")
SUBSCRIPTION_EXPIRATION_MINUTES = int(os.getenv("SUBSCRIPTION_EXPIRATION_MINUTES", "4000"))

# Webhook deduplication (avoid duplicate replies)
DEDUP_CONVERSATION_COOLDOWN_SECONDS = int(os.getenv("DEDUP_CONVERSATION_COOLDOWN_SECONDS", "120"))
DEDUP_STORE_PATH = DATA_DIR / "dedup_state.json"

# Webhook concurrency (bounded queue + worker pool).
# Lower worker count reduces 429 MailboxConcurrency from Graph when many notifications arrive.
WEBHOOK_QUEUE_MAX = int(os.getenv("WEBHOOK_QUEUE_MAX", "200"))
WEBHOOK_WORKER_COUNT = int(os.getenv("WEBHOOK_WORKER_COUNT", "2"))

# Webhook subscription resource (narrowed to Inbox by default)
WEBHOOK_SUBSCRIPTION_RESOURCE = os.getenv(
    "WEBHOOK_SUBSCRIPTION_RESOURCE",
    "me/mailFolders('Inbox')/messages",
)

# Webhook fetch retry settings (for Graph eventual consistency)
WEBHOOK_FETCH_MAX_ATTEMPTS = int(os.getenv("WEBHOOK_FETCH_MAX_ATTEMPTS", "5"))
WEBHOOK_FETCH_BASE_DELAY = float(os.getenv("WEBHOOK_FETCH_BASE_DELAY", "2.0"))

# TTL for failed message IDs in dedup store (seconds)
WEBHOOK_FAILED_MSG_TTL_SECONDS = int(os.getenv("WEBHOOK_FAILED_MSG_TTL_SECONDS", "600"))