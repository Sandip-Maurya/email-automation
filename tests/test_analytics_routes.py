"""Tests for analytics API: counts, draft-vs-sent, by-scenario, by-user."""

import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

# Use a shared file DB so the app's get_session() sees the same data (in-memory is per-connection).
_test_db_file = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
_test_db_file.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_test_db_file.name}"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from src.db import init_db
from src.db.repositories.email_outcome_repo import insert_draft, update_sent
from src.webhook.server import create_app


class TestAnalyticsRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        # Seed outcomes: 2 draft_created, 1 sent, 1 superseded (after supersede)
        insert_draft(
            message_id="m1",
            conversation_id="c1",
            reply_to_message_id="r1",
            scenario="S1",
            draft_subject="Subj1",
            draft_body="Body1",
            final_subject="Subj1",
            final_body="Body1",
            user_id="u1",
            user_name="User One",
        )
        insert_draft(
            message_id="m2",
            conversation_id="c2",
            reply_to_message_id="r2",
            scenario="S2",
            draft_subject="Subj2",
            draft_body="Body2",
            final_subject="Subj2",
            final_body="Body2",
        )
        insert_draft(
            message_id="m3",
            conversation_id="c3",
            reply_to_message_id="r3",
            scenario="S1",
            draft_subject="Subj3",
            draft_body="Body3",
            final_subject="Subj3",
            final_body="Body3",
        )
        update_sent(
            message_id="m3",
            sent_subject="Sent3",
            sent_body="Sent body3",
            sent_to="to@example.com",
            sent_at=datetime.now(timezone.utc),
        )
        cls.app = create_app(provider=object())

    @classmethod
    def tearDownClass(cls):
        try:
            os.unlink(_test_db_file.name)
        except Exception:
            pass

    def test_counts(self):
        client = TestClient(self.app)
        r = client.get("/webhook/analytics/counts")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("draft_created", data)
        self.assertIn("sent", data)
        self.assertIn("superseded", data)
        self.assertEqual(data["draft_created"], 2)
        self.assertEqual(data["sent"], 1)
        self.assertEqual(data["superseded"], 0)

    def test_draft_vs_sent(self):
        client = TestClient(self.app)
        r = client.get("/webhook/analytics/draft-vs-sent?limit=10&offset=0")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("items", data)
        self.assertIn("limit", data)
        self.assertIn("offset", data)
        self.assertEqual(len(data["items"]), 1)
        item = data["items"][0]
        self.assertEqual(item["message_id"], "m3")
        self.assertEqual(item["scenario"], "S1")
        self.assertTrue(item.get("subject_changed") or item.get("body_changed"))

    def test_by_scenario(self):
        client = TestClient(self.app)
        r = client.get("/webhook/analytics/by-scenario")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("items", data)
        scenarios = {x["scenario"]: x for x in data["items"]}
        self.assertIn("S1", scenarios)
        self.assertIn("S2", scenarios)
        self.assertEqual(scenarios["S1"]["draft_created"], 1)
        self.assertEqual(scenarios["S1"]["sent"], 1)
        self.assertEqual(scenarios["S2"]["draft_created"], 1)

    def test_by_user(self):
        client = TestClient(self.app)
        r = client.get("/webhook/analytics/by-user")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("items", data)
        by_id = {x.get("user_id") or "default": x for x in data["items"]}
        self.assertIn("u1", by_id)
        self.assertEqual(by_id["u1"].get("user_name"), "User One")
        self.assertIn("default", by_id)
