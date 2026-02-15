"""Tests for email outcome repository: insert_draft, supersede, get_by_message_id, update_sent."""

import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db import init_db
from src.db.repositories.email_outcome_repo import (
    get_by_message_id,
    insert_draft,
    supersede_by_conversation,
    update_sent,
)


class TestEmailOutcomeRepo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def test_insert_draft_and_get_by_message_id(self):
        row = insert_draft(
            message_id="msg-1",
            conversation_id="conv-1",
            scenario="S1",
            final_subject="Re: Test",
            final_body="Final body",
            user_id="user-1",
            user_name="Test User",
        )
        self.assertIsNotNone(row)
        self.assertEqual(row.message_id, "msg-1")
        self.assertEqual(row.conversation_id, "conv-1")
        self.assertEqual(row.user_name, "Test User")
        self.assertEqual(row.status, "draft_created")

        found = get_by_message_id("msg-1")
        self.assertIsNotNone(found)
        self.assertEqual(found.message_id, "msg-1")
        self.assertEqual(found.final_subject, "Re: Test")
        self.assertIsNone(get_by_message_id("nonexistent"))

    def test_supersede_by_conversation(self):
        insert_draft(
            message_id="msg-a",
            conversation_id="conv-x",
            scenario="S1",
            final_subject="Subj",
            final_body="Body",
        )
        supersede_by_conversation("conv-x", None)
        row = get_by_message_id("msg-a")
        self.assertIsNotNone(row)
        self.assertEqual(row.status, "superseded")
        self.assertIsNotNone(row.superseded_at)

    def test_update_sent(self):
        insert_draft(
            message_id="msg-sent",
            conversation_id="conv-sent",
            scenario="S2",
            final_subject="Draft",
            final_body="Draft body",
        )
        sent_at = datetime.now(timezone.utc)
        ok = update_sent(
            message_id="msg-sent",
            sent_subject="Sent subj",
            sent_body="Sent body",
            sent_to="recipient@example.com",
            sent_at=sent_at,
        )
        self.assertTrue(ok)
        row = get_by_message_id("msg-sent")
        self.assertIsNotNone(row)
        self.assertEqual(row.status, "sent")
        self.assertEqual(row.sent_subject, "Sent subj")
        self.assertEqual(row.sent_to, "recipient@example.com")
        self.assertIsNotNone(row.sent_at)
        self.assertFalse(update_sent("nonexistent", "", "", "", sent_at))
