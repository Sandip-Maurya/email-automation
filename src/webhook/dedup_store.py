"""Persistent deduplication store for webhook notifications.

Prevents duplicate email processing and replies by tracking triggered message IDs
and conversation-level reply cooldowns. State is persisted to a JSON file.
"""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from src.utils.logger import get_logger

logger = get_logger("email_automation.webhook.dedup_store")


class DedupStore:
    """Thread-safe persistent store for message and conversation deduplication."""

    def __init__(
        self,
        store_path: str | Path,
        conversation_cooldown_seconds: int = 300,
    ):
        self._store_path = Path(store_path)
        self._cooldown_seconds = conversation_cooldown_seconds
        self._lock = asyncio.Lock()
        self._triggered_message_ids: set[str] = set()
        self._conversation_replies: dict[str, str] = {}  # conversation_id -> ISO timestamp
        self._processing_message_ids: set[str] = set()  # in-flight only (not persisted)
        self._load()

    def _load(self) -> None:
        """Load state from disk. No-op if file missing or invalid."""
        if not self._store_path.exists():
            return
        try:
            data = json.loads(self._store_path.read_text(encoding="utf-8"))
            self._triggered_message_ids = set(data.get("triggered_message_ids", []))
            self._conversation_replies = data.get("conversation_replies", {})
        except Exception as e:
            logger.warning(
                "dedup_store.load_error",
                path=str(self._store_path),
                error=str(e),
            )

    def _save(self) -> None:
        """Write state to disk. Caller should hold _lock."""
        try:
            self._store_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "triggered_message_ids": list(self._triggered_message_ids),
                "conversation_replies": self._conversation_replies,
            }
            self._store_path.write_text(
                json.dumps(data, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error(
                "dedup_store.save_error",
                path=str(self._store_path),
                error=str(e),
            )

    async def has_triggered(self, message_id: str) -> bool:
        """Return True if this message_id was already accepted for processing."""
        async with self._lock:
            return message_id in self._triggered_message_ids

    async def mark_triggered(self, message_id: str) -> bool:
        """Mark message_id as triggered. Returns True if newly added, False if already present."""
        async with self._lock:
            if message_id in self._triggered_message_ids:
                return False
            self._triggered_message_ids.add(message_id)
            self._save()
            return True

    async def is_processing(self, message_id: str) -> bool:
        """Return True if this message is currently being processed (in-flight)."""
        async with self._lock:
            return message_id in self._processing_message_ids

    async def add_processing(self, message_id: str) -> None:
        """Mark message as in-flight processing."""
        async with self._lock:
            self._processing_message_ids.add(message_id)

    async def remove_processing(self, message_id: str) -> None:
        """Remove message from in-flight set."""
        async with self._lock:
            self._processing_message_ids.discard(message_id)

    def _get_conversation_last_reply(self, conversation_id: str) -> datetime | None:
        """Get last reply time for conversation (no lock; caller must hold lock)."""
        ts_str = self._conversation_replies.get(conversation_id)
        if not ts_str:
            return None
        try:
            return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except ValueError:
            return None

    async def has_recent_reply(self, conversation_id: str) -> bool:
        """Return True if we replied to this conversation within the cooldown window."""
        if not conversation_id:
            return False
        async with self._lock:
            last = self._get_conversation_last_reply(conversation_id)
            if last is None:
                return False
            now = datetime.now(timezone.utc)
            return (now - last).total_seconds() < self._cooldown_seconds

    async def mark_replied(self, conversation_id: str) -> None:
        """Record that we sent a reply to this conversation."""
        if not conversation_id:
            return
        async with self._lock:
            self._conversation_replies[conversation_id] = (
                datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            )
            self._save()
            logger.debug(
                "dedup_store.mark_replied",
                conversation_id=conversation_id,
            )
