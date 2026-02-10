"""Graph mode: process latest email from sender via real Microsoft Graph API; confirm before sending."""

import asyncio
import os

import typer
from opentelemetry.trace import SpanKind, Status, StatusCode

from src.config import TARGET_SENDER
from src.mail_provider.graph_real import GraphProvider
from src.mail_provider.mapping import graph_messages_to_thread
from src.orchestrator import process_email_thread
from src.utils.logger import bind_context, clear_context
from src.utils.tracing import get_tracer
from src.utils.observability import thread_preview_for_observability, span_attributes_for_workflow_step, set_span_input_output

from .shared import (
    append_csv_log_row,
    console,
    logger,
    print_result,
    processing_log_row,
    result_to_serializable,
    write_json_result,
)


def graph(
    sender: str | None = typer.Option(None, "--sender", "-s", help="Override TARGET_SENDER"),
) -> None:
    """Process latest email from sender using real Graph API; confirm before sending reply."""
    effective_sender = (sender or os.getenv("TARGET_SENDER") or TARGET_SENDER or "").strip()
    log = logger.bind(command="graph", sender=effective_sender or None)
    log.info("graph.start")

    if not effective_sender:
        console.print("[red]Provide sender via --sender / -s or set TARGET_SENDER in .env[/red]")
        log.warning("graph.missing_sender")
        raise typer.Exit(1)

    required = ("AZURE_TENANT_ID", "AZURE_CLIENT_ID")
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        console.print(f"[red]Missing environment variables: {', '.join(missing)}[/red]")
        log.warning("graph.missing_env", missing=missing)
        raise typer.Exit(1)
    console.print("[bold]Sign-in required[/bold]: Open the URL below, enter the code, and complete sign-in within a few minutes.\n")
    provider = GraphProvider(
        tenant_id=os.environ["AZURE_TENANT_ID"],
        client_id=os.environ["AZURE_CLIENT_ID"],
    )

    def _show_draft_and_confirm(result):
        """Blocking: show draft and return user's y/n (run in executor to not block event loop)."""
        console.print("\n[bold]Draft reply (confirm to send)[/bold]")
        print_result(result)
        return console.input("\nSend this reply? [y/N]: ").strip().lower()

    async def _run_graph_flow():
        """Single async flow: one trace (graph_workflow) with fetch, process, optional send."""
        tracer = get_tracer()
        root_attrs = {
            "workflow.mode": "graph",
            "workflow.sender": effective_sender,
            **span_attributes_for_workflow_step("CHAIN", input_summary={"sender": effective_sender}),
        }
        with tracer.start_as_current_span(
            "graph_workflow",
            kind=SpanKind.INTERNAL,
            attributes=root_attrs,
        ) as root_span:
            try:
                fetch_attrs = {
                    "workflow.sender": effective_sender,
                    **span_attributes_for_workflow_step("TOOL", input_summary={"sender": effective_sender}),
                }
                with tracer.start_as_current_span("fetch_email", kind=SpanKind.INTERNAL, attributes=fetch_attrs) as fetch_span:
                    msg = await provider.get_latest_from_sender(effective_sender)
                    if not msg:
                        raise ValueError(f"No message found from sender: {effective_sender}")
                    thread = graph_messages_to_thread([msg])
                    set_span_input_output(fetch_span, output_summary={"thread_id": thread.thread_id, "message_id": msg.id})

                root_span.set_attribute("workflow.thread_id", thread.thread_id)
                root_span.set_attribute("workflow.message_id", msg.id)
                root_span.set_attribute("workflow.input_preview", thread_preview_for_observability(thread))

                bind_context(command="graph", sender=effective_sender, message_id=msg.id)
                result = await process_email_thread(thread, provider=None, tracer=tracer)
                root_span.set_attribute("workflow.scenario", result.scenario)
                set_span_input_output(root_span, output_summary={"thread_id": result.thread_id, "scenario": result.scenario})

                loop = asyncio.get_running_loop()
                confirm = await loop.run_in_executor(None, lambda: _show_draft_and_confirm(result))
                if confirm not in ("y", "yes"):
                    return result, False

                reply_body = result.final_email.body or ""
                reply_attrs = {
                    "workflow.message_id": msg.id,
                    "workflow.conversation_id": result.thread_id,
                    "provider": type(provider).__name__,
                    **span_attributes_for_workflow_step("TOOL", input_summary={"message_id": msg.id, "thread_id": result.thread_id}),
                }
                with tracer.start_as_current_span("reply_to_message", kind=SpanKind.INTERNAL, attributes=reply_attrs) as reply_span:
                    await provider.reply_to_message(msg.id, reply_body)
                    set_span_input_output(reply_span, output_summary={"sent": True})
                return result, True
            except Exception as e:
                root_span.set_status(Status(StatusCode.ERROR, str(e)))
                root_span.record_exception(e)
                raise

    try:
        result, sent = asyncio.run(_run_graph_flow())
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        log.warning("graph.validation_error", error=str(e))
        clear_context()
        raise typer.Exit(1)
    except Exception:
        log.exception("graph.unexpected_error")
        clear_context()
        raise

    if not sent:
        console.print("[dim]Not sending.[/dim]")
        log.info("graph.send_skipped")
        clear_context()
        return

    console.print("[green]Reply sent.[/green]")
    write_json_result(result_to_serializable(result))
    row = processing_log_row(result)
    row["sent_message_id"] = "sent"
    append_csv_log_row(row)
    log.info("graph.complete", thread_id=result.thread_id, scenario=result.scenario)
    clear_context()
