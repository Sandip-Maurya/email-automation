"""Tests for webhook deduplication store."""

import asyncio
import tempfile
import unittest
from pathlib import Path

import sys

# Allow importing src when running from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.webhook.dedup_store import DedupStore


class TestDedupStore(unittest.TestCase):
    """Tests for DedupStore persistence and locking."""

    def test_triggered_persistence(self):
        """Marking triggered persists and survives new instance."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dedup.json"
            store = DedupStore(store_path=path, conversation_cooldown_seconds=300)

            async def run():
                self.assertFalse(await store.has_triggered("msg-1"))
                added = await store.mark_triggered("msg-1")
                self.assertTrue(added)
                self.assertTrue(await store.has_triggered("msg-1"))
                added2 = await store.mark_triggered("msg-1")
                self.assertFalse(added2)
                store2 = DedupStore(store_path=path, conversation_cooldown_seconds=300)
                self.assertTrue(await store2.has_triggered("msg-1"))

            asyncio.run(run())

    def test_conversation_cooldown(self):
        """has_recent_reply True within cooldown, False after."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dedup.json"
            store = DedupStore(store_path=path, conversation_cooldown_seconds=1)

            async def run():
                self.assertFalse(await store.has_recent_reply("conv-A"))
                await store.mark_replied("conv-A")
                self.assertTrue(await store.has_recent_reply("conv-A"))
                await asyncio.sleep(1.1)
                self.assertFalse(await store.has_recent_reply("conv-A"))

            asyncio.run(run())

    def test_processing_in_flight(self):
        """Processing set is in-memory only (not persisted)."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dedup.json"
            store = DedupStore(store_path=path, conversation_cooldown_seconds=300)

            async def run():
                self.assertFalse(await store.is_processing("msg-1"))
                await store.add_processing("msg-1")
                self.assertTrue(await store.is_processing("msg-1"))
                await store.remove_processing("msg-1")
                self.assertFalse(await store.is_processing("msg-1"))

            asyncio.run(run())

    def test_mark_triggered_atomic(self):
        """Only one caller gets True from mark_triggered when called concurrently."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dedup.json"
            store = DedupStore(store_path=path, conversation_cooldown_seconds=300)
            results = []

            async def claim():
                r = await store.mark_triggered("race-msg")
                results.append(r)

            async def run():
                await asyncio.gather(claim(), claim(), claim())
                self.assertEqual(sum(results), 1)

            asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
