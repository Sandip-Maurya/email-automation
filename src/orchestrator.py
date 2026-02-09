"""Orchestrate the full email processing workflow: A0 -> branch -> A10 -> A11 -> Send."""

import asyncio
from time import perf_counter
from typing import TYPE_CHECKING, Any, TypeVar

T = TypeVar("T")


async def _maybe_await(value: T | asyncio.Future[T]) -> T:
    """Await if value is a coroutine; otherwise return as-is (sync provider)."""
    if asyncio.iscoroutine(value):
        return await value
    return value

from opentelemetry.trace import Status, StatusCode

from src.models.email import EmailThread
from src.models.outputs import ProcessingResult, DraftEmail, FinalEmail, ReviewResult
from src.agents.decision_agent import classify_thread
from src.utils.tracing import get_tracer

if TYPE_CHECKING:
    from src.mail_provider.protocol import MailProvider
from src.mail_provider.mapping import graph_messages_to_thread
from src.agents.registry import get_agent, get_scenario_config, get_user_prompt_template
from src.agents.input_registry import get_input_agent
from src.agents.input_agents import (  # noqa: F401 - register input agents
    extract_supply,
    extract_access,
    extract_allocation,
    extract_catchall,
)
from src.agents.review_agent import review_draft
from src.agents.email_agent import format_final_email
from src.triggers import get_trigger  # imports trigger modules so @register_trigger runs
from src.utils.logger import get_logger, log_agent_step
from src.utils.observability import thread_preview_for_observability

logger = get_logger("email_automation.orchestrator")


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

    with tracer.start_as_current_span(
        "process_trigger",
        attributes={
            "workflow.message_id": message_id or "",
            "workflow.conversation_id": conversation_id or "",
        },
    ) as root_span:
        try:
            with tracer.start_as_current_span("fetch_thread"):
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

    When tracer is passed (e.g. from graph_workflow or process_trigger), all manual spans here nest under
    that parent. Pydantic AI Agent.instrument_all() uses the global tracer and inherits the current
    context, so LLM/agent spans automatically appear as children of the corresponding manual span.
    """
    if tracer is None:
        tracer = get_tracer()
    thread_id = thread.thread_id
    latest = thread.latest_email
    original_sender = latest.sender
    original_sender_name = latest.sender_name
    original_subject = latest.subject
    log = logger.bind(thread_id=thread_id, provider=bool(provider))
    log.info("process_email_thread.start", original_sender=original_sender, original_subject=original_subject)

    # 1. Decision Agent A0
    with tracer.start_as_current_span("A0_classify", attributes={"agent.name": "A0"}):
        decision = await classify_thread(thread)
    scenario = decision.scenario
    log = log.bind(scenario=scenario)
    log.debug("process_email_thread.scenario", confidence=decision.confidence)

    # 2. Load scenario config and run input -> trigger -> draft (generic dispatch)
    scenario_cfg = get_scenario_config(scenario)
    if not scenario_cfg.get("enabled", True):
        raise ValueError(f"Scenario {scenario} is disabled in config")

    input_agent_id = scenario_cfg["input_agent"]
    extract_fn, _ = get_input_agent(input_agent_id)
    with tracer.start_as_current_span(
        "input_extract",
        attributes={"agent.name": input_agent_id, "workflow.scenario": scenario},
    ):
        inputs = await extract_fn(thread)

    threshold = scenario_cfg.get("low_confidence_threshold", 0.5)
    if inputs.confidence < threshold and getattr(inputs, "missing_fields", None):
        log_agent_step("Orchestrator", "Low confidence / missing data -> flag for human", {"missing": inputs.missing_fields})

    trigger_name = scenario_cfg["trigger"]
    trigger_fn = get_trigger(trigger_name)
    with tracer.start_as_current_span(
        "trigger_fetch",
        attributes={"trigger.type": trigger_name, "workflow.scenario": scenario},
    ):
        trigger_data = await trigger_fn(inputs)

    draft_agent_id = scenario_cfg["draft_agent"]
    draft_agent = get_agent(draft_agent_id, DraftEmail)
    template = get_user_prompt_template(draft_agent_id)
    with tracer.start_as_current_span(
        "draft",
        attributes={"agent.name": draft_agent_id, "workflow.scenario": scenario},
    ):
        prompt = template.format(
            original_subject=original_subject,
            inputs=inputs,
            trigger_data=trigger_data,
        )
        result = await draft_agent.run(prompt)
        draft = result.output
        draft.scenario = scenario
        draft.metadata["trigger_source"] = trigger_data.get("source", "")

    context_for_review = {"inputs": inputs, "trigger_data": trigger_data}

    # 3. Review Agent A10
    with tracer.start_as_current_span("A10_review", attributes={"agent.name": "A10"}):
        review: ReviewResult = await review_draft(draft, context_for_review)

    # 4. Email Agent A11
    with tracer.start_as_current_span("A11_format", attributes={"agent.name": "A11"}):
        final_email: FinalEmail = await format_final_email(
            draft, review, reply_to=original_sender, sender_name=original_sender_name
        )

    raw_data: dict = {
        "decision_reasoning": decision.reasoning,
        "original_sender": original_sender,
        "original_subject": original_subject,
        "conversation_id": thread_id,
    }

    # 5. Reply via provider (if provided and we have a message to reply to) and record sent outcome
    if provider is not None and reply_to_message_id:
        with tracer.start_as_current_span(
            "reply_to_message",
            attributes={"provider": type(provider).__name__, "workflow.reply_to_message_id": reply_to_message_id},
        ):
            reply_body = final_email.body or ""
            log.debug("process_email_thread.reply_attempt", reply_to_message_id=reply_to_message_id)
            sent_msg = await _maybe_await(
                provider.reply_to_message(reply_to_message_id, reply_body, user_id=user_id)
            )
            raw_data["sent_message_id"] = sent_msg.id
            raw_data["sent_at"] = sent_msg.receivedDateTime
            log.info("process_email_thread.reply_complete", sent_message_id=sent_msg.id)
    log.info(
        "process_email_thread.complete",
        review_status=review.status,
        final_subject=final_email.subject,
    )

    return ProcessingResult(
        thread_id=thread_id,
        scenario=scenario,
        decision_confidence=decision.confidence,
        draft=draft,
        review=review,
        final_email=final_email,
        raw_data=raw_data,
    )
