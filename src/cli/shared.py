"""Shared CLI helpers: console, logger, output paths, result formatting, mock provider."""

import csv
import json
from pathlib import Path

from rich.console import Console

from src.config import INBOX_PATH, OUTPUT_DIR, SENT_ITEMS_PATH
from src.mail_provider import GraphMockProvider
from src.utils.logger import get_logger

console = Console()
logger = get_logger("email_automation.cli")


def get_mock_provider(
    inbox_path: Path | None = None,
    sent_path: Path | None = None,
) -> GraphMockProvider:
    """Return a mock mail provider (inbox.json + sent_items.json)."""
    return GraphMockProvider(
        inbox_path=inbox_path or INBOX_PATH,
        sent_items_path=sent_path or SENT_ITEMS_PATH,
    )


def ensure_output_dirs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    logger.debug("filesystem.ensure_output_dirs", output_dir=str(OUTPUT_DIR))


def write_json_result(result_dict: dict, path: Path | None = None) -> Path:
    ensure_output_dirs()
    path = path or OUTPUT_DIR / "responses.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(result_dict, f, indent=2, default=str)
    logger.info("results.write_json", path=str(path))
    return path


def append_csv_log_row(row: dict, path: Path | None = None) -> Path:
    ensure_output_dirs()
    path = path or OUTPUT_DIR / "processing_log.csv"
    file_exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=row.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)
    logger.debug("results.append_csv_row", path=str(path), headers=not file_exists)
    return path


def result_to_serializable(result) -> dict:
    """Convert ProcessingResult to a JSON-serializable dict."""
    return {
        "thread_id": result.thread_id,
        "scenario": result.scenario,
        "decision_confidence": result.decision_confidence,
        "draft": result.draft.model_dump(),
        "review": result.review.model_dump(),
        "final_email": result.final_email.model_dump(),
        "raw_data": result.raw_data,
    }


def print_result(result) -> None:
    """Print processing result and final email to console."""
    console.print("\n[bold]Processing Result[/bold]")
    console.print(f"  Thread ID: {result.thread_id}")
    console.print(f"  Scenario: {result.scenario} (confidence: {result.decision_confidence})")
    console.print(f"  Review: {result.review.status} (quality: {result.review.quality_score})")
    if result.raw_data.get("sent_message_id"):
        console.print(f"  Sent: {result.raw_data.get('sent_message_id')} at {result.raw_data.get('sent_at', '')}")
    console.print("\n[bold]Final Email[/bold]")
    console.print(f"  To: {result.final_email.to or '(reply-to)'}")
    console.print(f"  Subject: {result.final_email.subject}")
    console.print(f"  Body:\n{result.final_email.body}")


def processing_log_row(result) -> dict:
    """Build a single row for processing_log.csv from a ProcessingResult."""
    return {
        "thread_id": result.thread_id,
        "scenario": result.scenario,
        "decision_confidence": str(result.decision_confidence),
        "review_status": result.review.status,
        "subject": result.final_email.subject,
        "sent_message_id": result.raw_data.get("sent_message_id", ""),
    }
