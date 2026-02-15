"""Orchestrate the full email processing workflow: A0 -> branch -> A10 -> A11 -> Send.

The pipeline is implemented as a LlamaIndex Workflow (event-driven, step-based).
See src/workflow/email_workflow.py and docs/WORKFLOW_ARCHITECTURE.md.
"""

import asyncio
from time import perf_counter
from typing import TYPE_CHECKING, Any, TypeVar

from opentelemetry.trace import SpanKind, Status, StatusCode

from src.models.email import EmailThread
from src.models.outputs import ProcessingResult
from src.utils.tracing import get_tracer
from src.utils.observability import (
    thread_preview_for_observability,
    span_attributes_for_workflow_step,
    set_span_input_output,
)
from src.orchestrator_steps import maybe_await
from src.workflow.email_workflow import EmailOrchestratorWorkflow

if TYPE_CHECKING:
    from src.mail_provider.protocol import MailProvider
from src.mail_provider.mapping import graph_messages_to_thread
from src.utils.logger import get_logger

T = TypeVar("T")
logger = get_logger("email_automation.orchestrator")


async def _maybe_await(value: T | asyncio.Future[T] | Any) -> T:
    """Await if value is a coroutine or Future; otherwise return as-is (sync provider)."""
    return await maybe_await(value)


async def process_trigger(
    thread: EmailThread,
    provider: "MailProvider",
    message_id: str | None = None,
    conversation_id: str | None = None,
    user_id: str | None = None,
) -> ProcessingResult:
    """Trigger entry: fetch thread by message_id or conversation_id, then process and send.
    user_id scopes mailbox when set (e.g. from webhook notification resource path)."""
    tracer = get_tracer()
    start = perf_counter()
    log = logger.bind(message_id=message_id, conversation_id=conversation_id)
    log.info("process_trigger.start")

    root_attrs = {
        "workflow.message_id": message_id or "",
        "workflow.conversation_id": conversation_id or "",
        **span_attributes_for_workflow_step(
            "CHAIN",
            input_summary={"message_id": message_id or "", "conversation_id": conversation_id or ""},
        ),
    }
    with tracer.start_as_current_span(
        "process_trigger",
        kind=SpanKind.SERVER,
        attributes=root_attrs,
    ) as root_span:
        try:
            with tracer.start_as_current_span(
                "fetch_thread",
                kind=SpanKind.INTERNAL,
                attributes=span_attributes_for_workflow_step("TOOL", input_summary={"message_id": message_id or "", "conversation_id": conversation_id or ""}),
            ):
                if message_id:
                    msg = await _maybe_await(provider.get_message(message_id, user_id=user_id))
                    if msg is None:
                        log.warning("process_trigger.message_not_found")
                        raise ValueError(f"Message not found: {message_id}")
                    if msg.conversationId:
                        messages = await _maybe_await(
                            provider.get_conversation(msg.conversationId, user_id=user_id)
                        )
                        if not messages:
                            log.debug(
                                "process_trigger.conversation_empty_fallback",
                                conversation_id=msg.conversationId,
                                message="Using single message (conversation query may have failed)",
                            )
                            messages = [msg]
                    else:
                        messages = [msg]
                elif conversation_id:
                    messages = await _maybe_await(
                        provider.get_conversation(conversation_id, user_id=user_id)
                    )
                    if not messages:
                        log.warning("process_trigger.conversation_not_found")
                        raise ValueError(f"Conversation not found: {conversation_id}")
                else:
                    log.warning("process_trigger.invalid_arguments")
                    raise ValueError("Provide message_id or conversation_id")
                thread = graph_messages_to_thread(messages)
                root_span.set_attribute("workflow.thread_id", thread.thread_id)
                root_span.set_attribute("workflow.input_preview", thread_preview_for_observability(thread))
            reply_to_message_id = message_id if message_id else (thread.latest_email.id if thread.latest_email else None)

            result = await process_email_thread(
                thread,
                provider=provider,
                tracer=tracer,
                reply_to_message_id=reply_to_message_id,
                user_id=user_id,
            )
            root_span.set_attribute("workflow.scenario", result.scenario)
            set_span_input_output(
                root_span,
                output_summary={"scenario": result.scenario, "thread_id": result.thread_id},
            )

            duration_ms = (perf_counter() - start) * 1000
            log.info(
                "process_trigger.complete",
                thread_id=result.thread_id,
                scenario=result.scenario,
                duration_ms=round(duration_ms, 2),
            )
            return result
        except Exception as e:
            root_span.set_status(Status(StatusCode.ERROR, str(e)))
            root_span.record_exception(e)
            raise


async def process_email_thread(
    thread: EmailThread,
    provider: "MailProvider | None" = None,
    tracer=None,
    reply_to_message_id: str | None = None,
    user_id: str | None = None,
) -> ProcessingResult:
    """Run the full agentic pipeline for one email thread; if provider and reply_to_message_id are set, reply and record sent info.
    user_id scopes the mailbox for reply when set (e.g. from webhook).

    Implemented as a LlamaIndex Workflow. When tracer is passed (e.g. from graph_workflow or
    process_trigger), all manual spans nest under that parent.
    """
    if tracer is None:
        tracer = get_tracer()
    log = logger.bind(thread_id=thread.thread_id, provider=bool(provider))
    latest = thread.latest_email
    log.info(
        "process_email_thread.start",
        original_sender=latest.sender if latest else "",
        original_subject=latest.subject if latest else "",
    )

    workflow = EmailOrchestratorWorkflow(timeout=120, verbose=False)
    handler = workflow.run(
        thread=thread,
        provider=provider,
        tracer=tracer,
        reply_to_message_id=reply_to_message_id,
        user_id=user_id,
    )
    result = await handler
    return result
