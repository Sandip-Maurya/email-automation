"""Interactive mode: list conversations from inbox, pick one, process and send (mock provider)."""

import asyncio
from pathlib import Path

import typer
from rich.table import Table

from src.config import INBOX_PATH, OUTPUT_DIR
from src.db import init_db
from src.orchestrator import process_trigger
from src.utils.logger import bind_context, clear_context

from .shared import (
    append_csv_log_row,
    console,
    get_mock_provider,
    logger,
    print_result,
    processing_log_row,
    result_to_serializable,
    write_json_result,
)


def interactive(
    inbox: Path = typer.Option(INBOX_PATH, "--inbox", "-e", help="Path to inbox.json"),
) -> None:
    """Interactive: list conversations from inbox, pick one, process and send."""
    init_db()
    log = logger.bind(command="interactive", inbox=str(inbox))
    log.info("interactive.start")
    provider = get_mock_provider(inbox_path=inbox)
    conversations = provider.list_conversations()
    if not conversations:
        console.print("[red]No conversations in inbox.[/red]")
        log.info("interactive.no_conversations")
        raise typer.Exit(1)
    table = Table(title="Conversations (inbox)")
    table.add_column("#", style="cyan")
    table.add_column("Conversation ID", style="green")
    table.add_column("Subject", style="white")
    table.add_column("Sender", style="yellow")
    table.add_column("Messages", style="dim")
    for i, c in enumerate(conversations, 1):
        subj = (c["subject"] or "")[:50] + ("..." if len(c["subject"] or "") > 50 else "")
        table.add_row(str(i), c["conversation_id"][:24] + "...", subj, c["sender"], str(c["message_count"]))
    console.print(table)
    try:
        choice = console.input("\nEnter number to process (or Enter to quit): ").strip()
        if not choice:
            log.info("interactive.exit_without_selection")
            return
        idx = int(choice)
        if idx < 1 or idx > len(conversations):
            console.print("[red]Invalid number.[/red]")
            log.warning("interactive.invalid_selection", choice=choice)
            return
    except ValueError:
        console.print("[red]Enter a number.[/red]")
        log.warning("interactive.non_numeric_selection")
        return
    conv = conversations[idx - 1]
    cid = conv["conversation_id"]
    console.print(f"\n[dim]Processing conversation {cid}...[/dim]\n")
    run_log = log.bind(conversation_id=cid)
    thread = provider.get_conversation(cid)
    try:
        bind_context(command="interactive", conversation_id=cid)
        result = asyncio.run(process_trigger(thread, provider, conversation_id=cid))
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        run_log.warning("interactive.validation_error", error=str(e))
        clear_context()
        return
    except Exception:
        run_log.exception("interactive.unexpected_error")
        clear_context()
        raise
    print_result(result)
    write_json_result(result_to_serializable(result))
    append_csv_log_row(processing_log_row(result))
    run_log.info("interactive.complete", thread_id=result.thread_id, scenario=result.scenario)
    clear_context()
    console.print(f"\n[dim]Output and sent store: {OUTPUT_DIR}[/dim]")
