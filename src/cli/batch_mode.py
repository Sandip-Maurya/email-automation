"""Batch mode: process all conversations in inbox, draft and send each reply (mock provider)."""

import asyncio
import json
from pathlib import Path

import typer

from src.config import INBOX_PATH, OUTPUT_DIR
from src.orchestrator import process_trigger
from src.utils.logger import bind_context, clear_context

from .shared import (
    append_csv_log_row,
    console,
    get_mock_provider,
    logger,
    processing_log_row,
    result_to_serializable,
    write_json_result,
)


def batch(
    inbox: Path = typer.Option(INBOX_PATH, "--inbox", "-i", help="Path to inbox.json"),
    output_dir: Path = typer.Option(OUTPUT_DIR, "--output", "-o", help="Output directory"),
) -> None:
    """Process all conversations in inbox: draft and send each reply."""
    log = logger.bind(command="batch", inbox=str(inbox), output_dir=str(output_dir))
    log.info("batch.start")
    provider = get_mock_provider(inbox_path=inbox, sent_path=output_dir / "sent_items.json")
    conversations = provider.list_conversations()
    if not conversations:
        console.print("[red]No conversations in inbox.[/red]")
        log.info("batch.no_conversations")
        raise typer.Exit(1)
    results = []
    for i, c in enumerate(conversations, 1):
        cid = c["conversation_id"]
        console.print(f"[dim]Processing {i}/{len(conversations)}: {cid[:30]}...[/dim]")
        try:
            bind_context(command="batch", conversation_id=cid)
            thread = provider.get_conversation(cid)
            result = asyncio.run(process_trigger(thread, provider, conversation_id=cid))
            results.append(result)
            log.debug("batch.processed_conversation", conversation_id=cid, scenario=result.scenario)
        except Exception as e:
            console.print(f"[red]Error {cid}: {e}[/red]")
            log.exception("batch.conversation_error", conversation_id=cid)
        finally:
            clear_context()
    if not results:
        console.print("[red]No results to write.[/red]")
        log.warning("batch.no_results")
        raise typer.Exit(1)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "responses.json"
    with json_path.open("w", encoding="utf-8") as f:
        json.dump([result_to_serializable(r) for r in results], f, indent=2, default=str)
    console.print(f"[green]Wrote {json_path}[/green]")
    log.info("batch.responses_written", path=str(json_path), processed=len(results))
    log_path = output_dir / "processing_log.csv"
    if log_path.exists():
        log_path.unlink()
        log.debug("batch.reset_processing_log", path=str(log_path))
    for r in results:
        append_csv_log_row(processing_log_row(r), path=log_path)
    console.print(f"[green]Wrote {log_path}[/green]")
    console.print(f"[green]Sent items: {output_dir / 'sent_items.json'}[/green]")
    console.print(f"\n[bold]Processed {len(results)} conversations.[/bold]")
    log.info("batch.complete", processed=len(results))
    clear_context()
