"""Mock mail provider: reads inbox.json, writes sent_items.json."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.mail_provider.graph_models import (
    EmailAddress,
    GraphMessage,
    ItemBody,
    Recipient,
)
from src.utils.logger import get_logger, log_agent_step

logger = get_logger("email_automation.mail_provider")


class GraphMockProvider:
    """Mock provider: inbox from JSON file, sent items appended to another JSON file."""

    def __init__(
        self,
        inbox_path: Path,
        sent_items_path: Path,
    ):
        self._inbox_path = inbox_path
        self._sent_items_path = sent_items_path
        self._inbox: list[GraphMessage] = []
        logger.info(
            "mail_provider.init",
            inbox_path=str(self._inbox_path),
            sent_items_path=str(self._sent_items_path),
        )
        self._load_inbox()

    def _load_inbox(self) -> None:
        if not self._inbox_path.exists():
            self._inbox = []
            logger.warning("mail_provider.inbox_missing", inbox_path=str(self._inbox_path))
            return
        with self._inbox_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        items = data if isinstance(data, list) else data.get("value", data.get("messages", []))
        self._inbox = []
        for item in items:
            try:
                self._inbox.append(GraphMessage.model_validate(item))
            except Exception:
                continue
        logger.info("mail_provider.inbox_loaded", message_count=len(self._inbox))

    def _load_sent(self) -> list[dict[str, Any]]:
        if not self._sent_items_path.exists():
            logger.debug("mail_provider.sent_missing", sent_items_path=str(self._sent_items_path))
            return []
        with self._sent_items_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        items = data if isinstance(data, list) else data.get("value", [])
        logger.debug("mail_provider.sent_loaded", count=len(items or []))
        return items or []

    def _save_sent(self, items: list[dict[str, Any]]) -> None:
        self._sent_items_path.parent.mkdir(parents=True, exist_ok=True)
        with self._sent_items_path.open("w", encoding="utf-8") as f:
            json.dump(items, f, indent=2, default=str)
        logger.info("mail_provider.sent_written", count=len(items), sent_items_path=str(self._sent_items_path))

    def get_message(self, message_id: str, user_id: str | None = None) -> GraphMessage | None:
        for m in self._inbox:
            if m.id == message_id:
                logger.debug("mail_provider.get_message.hit", message_id=message_id)
                return m
        logger.debug("mail_provider.get_message.miss", message_id=message_id)
        return None

    def get_conversation(self, conversation_id: str, user_id: str | None = None) -> list[GraphMessage]:
        matching = [m for m in self._inbox if m.conversationId == conversation_id]
        if not matching:
            msg = self.get_message(conversation_id)
            if msg is not None:
                return [msg]
            return []
        matching.sort(key=lambda x: x.receivedDateTime or "")
        logger.debug("mail_provider.get_conversation", conversation_id=conversation_id, count=len(matching))
        return matching

    def list_conversations(self) -> list[dict]:
        """List unique conversations (by conversationId) with latest message info for display."""
        by_conv: dict[str, list[GraphMessage]] = {}
        for m in self._inbox:
            cid = m.conversationId or m.id
            if cid not in by_conv:
                by_conv[cid] = []
            by_conv[cid].append(m)
        result = []
        for cid, messages in by_conv.items():
            messages.sort(key=lambda x: x.receivedDateTime or "")
            latest = messages[-1]
            sender = ""
            if latest.from_ and latest.from_.emailAddress:
                sender = latest.from_.emailAddress.address or ""
            result.append({
                "conversation_id": cid,
                "subject": latest.subject or "",
                "sender": sender,
                "latest_message_id": latest.id,
                "message_count": len(messages),
            })
        result.sort(key=lambda x: x["conversation_id"])
        logger.info("mail_provider.list_conversations", count=len(result))
        return result

    def create_reply_draft(
        self,
        message_id: str,
        body: str,
        subject: str | None = None,
        user_id: str | None = None,
    ) -> GraphMessage:
        """Mock: return a draft message with deterministic id (draft_{message_id}) for correlation in tests."""
        log_agent_step("MailProvider", "Create reply draft (mock)", {"message_id": message_id})
        logger.info("mail_provider.create_reply_draft", message_id=message_id)
        draft_id = f"draft_{message_id}"
        sent_dt = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        return GraphMessage(
            id=draft_id,
            conversationId=None,
            receivedDateTime=sent_dt,
            subject=subject or "",
            body=ItemBody(contentType="html", content=body or ""),
            bodyPreview=(body[:255] if body else "") if body else None,
            from_=None,
            toRecipients=[],
            isDraft=True,
        )

    def reply_to_message(
        self, message_id: str, comment: str, user_id: str | None = None
    ) -> GraphMessage:
        log_agent_step("MailProvider", "Reply to message (mock)", {"message_id": message_id})
        logger.info("mail_provider.reply_to_message", message_id=message_id)
        sent_id = f"AAMkAG_reply_{message_id}_{len(self._load_sent())}"
        sent_dt = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        from_recipient = Recipient(emailAddress=EmailAddress(address="trade@company.com", name="Trade Inbox"))
        msg = GraphMessage(
            id=sent_id,
            receivedDateTime=sent_dt,
            subject="",
            body=ItemBody(contentType="html", content=comment),
            bodyPreview=(comment[:255] if comment else ""),
            from_=from_recipient,
            toRecipients=[],
            isDraft=False,
        )
        sent_list = self._load_sent()
        sent_list.append(msg.model_dump(by_alias=True, exclude_none=True))
        self._save_sent(sent_list)
        return msg
