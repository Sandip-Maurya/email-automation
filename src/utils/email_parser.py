"""Parse email CSV rows and build threads."""

from datetime import datetime
from typing import Any

from src.models.email import Email, EmailThread


def parse_email_csv_row(row: dict[str, Any]) -> Email:
    """Parse a CSV row into an Email model."""
    ts = row.get("timestamp", "")
    try:
        if isinstance(ts, str) and "T" in ts:
            timestamp = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        elif isinstance(ts, str):
            timestamp = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
        else:
            timestamp = datetime.now()
    except (ValueError, TypeError):
        timestamp = datetime.now()
    return Email(
        id=row.get("email_id", ""),
        sender=row.get("sender", ""),
        subject=row.get("subject", ""),
        body=row.get("body", ""),
        timestamp=timestamp,
        thread_id=row.get("thread_id"),
    )


def build_threads(emails: list[dict[str, Any]]) -> list[EmailThread]:
    """Group emails by thread_id and build EmailThread list. Single emails become single-email threads."""
    parsed = [parse_email_csv_row(r) for r in emails]
    by_thread: dict[str, list[Email]] = {}
    for e in parsed:
        tid = e.thread_id or e.id
        if tid not in by_thread:
            by_thread[tid] = []
        by_thread[tid].append(e)
    threads = []
    for tid, ems in by_thread.items():
        ems.sort(key=lambda x: x.timestamp)
        threads.append(EmailThread(thread_id=tid, emails=ems, latest_email=ems[-1]))
    return threads
