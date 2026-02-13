"""Orchestrate the full email processing workflow: A0 -> branch -> A10 -> A11 -> Send."""

import asyncio
from time import perf_counter
from typing import TYPE_CHECKING, Any, TypeVar
from src.llama_index_flow import EmailWorkflow

T = TypeVar("T")


async def _maybe_await(value: T | asyncio.Future[T]) -> T:
    """Await if value is a coroutine; otherwise return as-is (sync provider)."""
    if asyncio.iscoroutine(value):
        return await value
    return value

from opentelemetry.trace import SpanKind, Status, StatusCode

from src.models.email import EmailThread
from src.models.outputs import (
    AggregatedContext,
    ProcessingResult,
    DraftEmail,
    FinalEmail,
    ReviewResult,
)
from src.agents.aggregate_a11 import aggregate_context_for_decision
from src.agents.decision_agent import classify_thread, thread_to_prompt
from src.utils.tracing import get_tracer
from src.utils.observability import (
    thread_preview_for_observability,
    span_attributes_for_workflow_step,
    set_span_input_output,
)

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
from src.agents.s3_scaffold import (
    step_s3_ad1,
    step_s3_ad2,
    step_s3_ad3,
    step_s3_ad4,
)
from src.triggers import get_trigger  # imports trigger modules so @register_trigger runs
from src.utils.logger import get_logger, log_agent_step

logger = get_logger("email_automation.orchestrator")


async def _step_classify(thread: EmailThread, tracer: Any) -> Any:
    """Step: A0 classify thread -> scenario."""
    thread_id = thread.thread_id
    latest = thread.latest_email
    original_subject = latest.subject if latest else ""
    a0_attrs = {"agent.name": "A0", **span_attributes_for_workflow_step("CHAIN", input_summary={"thread_id": thread_id, "subject": original_subject})}
    with tracer.start_as_current_span("A0_classify", kind=SpanKind.INTERNAL, attributes=a0_attrs) as a0_span:
        decision = await classify_thread(thread)
        set_span_input_output(a0_span, output_summary={"scenario": decision.scenario, "confidence": decision.confidence})
    return decision


async def _step_extract(thread: EmailThread, scenario: str, scenario_cfg: dict, tracer: Any) -> Any:
    """Step: input extract -> inputs."""
    input_agent_id = scenario_cfg["input_agent"]
    extract_fn, _ = get_input_agent(input_agent_id)
    extract_attrs = {
        "agent.name": input_agent_id,
        "workflow.scenario": scenario,
        **span_attributes_for_workflow_step("TOOL", input_summary={"input_agent": input_agent_id, "scenario": scenario}),
    }
    with tracer.start_as_current_span("input_extract", kind=SpanKind.INTERNAL, attributes=extract_attrs) as extract_span:
        inputs = await extract_fn(thread)
        set_span_input_output(extract_span, output_summary={"confidence": inputs.confidence})
    return inputs


async def _step_trigger_fetch(
    inputs: Any,
    scenario: str,
    scenario_cfg: dict,
    tracer: Any,
    s3_context: dict[str, Any] | None = None,
) -> dict:
    """Step: trigger fetch -> trigger_data. For S3, s3_context is passed to allocation_api."""
    trigger_name = scenario_cfg["trigger"]
    trigger_fn = get_trigger(trigger_name)
    trigger_attrs = {
        "trigger.type": trigger_name,
        "workflow.scenario": scenario,
        **span_attributes_for_workflow_step("TOOL", input_summary={"trigger": trigger_name, "scenario": scenario}),
    }
    with tracer.start_as_current_span("trigger_fetch", kind=SpanKind.INTERNAL, attributes=trigger_attrs) as trigger_span:
        if s3_context is not None and trigger_name == "allocation_api":
            trigger_data = await trigger_fn(inputs, s3_context=s3_context)
        else:
            trigger_data = await trigger_fn(inputs)
        set_span_input_output(trigger_span, output_summary={"source": trigger_data.get("source", "")})
    return trigger_data


async def _step_draft(
    thread: EmailThread,
    scenario: str,
    scenario_cfg: dict,
    inputs: Any,
    trigger_data: dict,
    tracer: Any,
) -> Any:
    """Step: draft agent -> draft."""
    draft_agent_id = scenario_cfg["draft_agent"]
    draft_agent = get_agent(draft_agent_id, DraftEmail)
    template = get_user_prompt_template(draft_agent_id)
    original_subject = thread.latest_email.subject if thread.latest_email else ""
    email_thread = thread_to_prompt(thread)
    draft_attrs = {
        "agent.name": draft_agent_id,
        "workflow.scenario": scenario,
        **span_attributes_for_workflow_step("TOOL", input_summary={"draft_agent": draft_agent_id, "scenario": scenario}),
    }
    with tracer.start_as_current_span("draft", kind=SpanKind.INTERNAL, attributes=draft_attrs) as draft_span:
        prompt = template.format(
            original_subject=original_subject,
            email_thread=email_thread,
            inputs=inputs,
            trigger_data=trigger_data,
        )
        result = await draft_agent.run(prompt)
        draft = result.output
        draft.scenario = scenario
        draft.metadata["trigger_source"] = trigger_data.get("source", "")
        set_span_input_output(draft_span, output_summary={"scenario": scenario, "trigger_source": draft.metadata.get("trigger_source", "")})
    return draft


async def _step_a11_aggregate(decision: Any, inputs: Any, tracer: Any) -> AggregatedContext:
    """Step: Input A11 aggregate -> AggregatedContext (Decision, NDC, Distributor, Year) for Decision A10."""
    a11_attrs = {
        "agent.name": "A11",
        **span_attributes_for_workflow_step(
            "TOOL",
            input_summary={"decision": decision.scenario},
        ),
    }
    with tracer.start_as_current_span(
        "A11_aggregate", kind=SpanKind.INTERNAL, attributes=a11_attrs
    ) as a11_span:
        aggregated = aggregate_context_for_decision(decision, inputs)
        set_span_input_output(
            a11_span,
            output_summary={
                "decision": aggregated.decision,
                "ndc": aggregated.ndc or "",
                "distributor": aggregated.distributor or "",
            },
        )
    return aggregated


async def _run_s3_scaffold(inputs: Any, tracer: Any) -> dict[str, Any]:
    """Run S3 Demand IQ scaffold steps A_D1–A_D4 (placeholders); return combined s3_context."""
    ad1_attrs = span_attributes_for_workflow_step("TOOL", input_summary={"step": "S3_A_D1"})
    with tracer.start_as_current_span("S3_A_D1", kind=SpanKind.INTERNAL, attributes=ad1_attrs) as span:
        ad1 = await step_s3_ad1(inputs)
        set_span_input_output(span, output_summary=ad1)
    ad2_attrs = span_attributes_for_workflow_step("TOOL", input_summary={"step": "S3_A_D2"})
    with tracer.start_as_current_span("S3_A_D2", kind=SpanKind.INTERNAL, attributes=ad2_attrs) as span:
        ad2 = await step_s3_ad2(inputs)
        set_span_input_output(span, output_summary=ad2)
    ad3_attrs = span_attributes_for_workflow_step("TOOL", input_summary={"step": "S3_A_D3"})
    with tracer.start_as_current_span("S3_A_D3", kind=SpanKind.INTERNAL, attributes=ad3_attrs) as span:
        ad3 = await step_s3_ad3(inputs)
        set_span_input_output(span, output_summary=ad3)
    ad4_attrs = span_attributes_for_workflow_step("TOOL", input_summary={"step": "S3_A_D4"})
    with tracer.start_as_current_span("S3_A_D4", kind=SpanKind.INTERNAL, attributes=ad4_attrs) as span:
        ad4 = await step_s3_ad4(inputs)
        set_span_input_output(span, output_summary=ad4)
    return {"ad1": ad1, "ad2": ad2, "ad3": ad3, "ad4": ad4}


async def _step_review(draft: Any, context_for_review: dict, scenario: str, tracer: Any) -> ReviewResult:
    """Step: Decision A10 review -> review (approve or flag for human)."""
    a10_attrs = {
        "agent.name": "A10",
        **span_attributes_for_workflow_step("CHAIN", input_summary={"scenario": scenario}),
    }
    with tracer.start_as_current_span("A10_review", kind=SpanKind.INTERNAL, attributes=a10_attrs) as a10_span:
        review = await review_draft(draft, context_for_review)
        set_span_input_output(a10_span, output_summary={"status": review.status, "scenario": scenario})
    return review


async def _step_format(
    draft: Any,
    review: ReviewResult,
    original_sender: str,
    original_sender_name: str,
    scenario: str,
    tracer: Any,
) -> FinalEmail:
    """Step: Email A12 format -> final_email."""
    a11_attrs = {
        "agent.name": "A11",
        **span_attributes_for_workflow_step("CHAIN", input_summary={"scenario": scenario}),
    }
    with tracer.start_as_current_span("A11_format", kind=SpanKind.INTERNAL, attributes=a11_attrs) as a11_span:
        final_email = await format_final_email(
            draft, review, reply_to=original_sender, sender_name=original_sender_name
        )
        set_span_input_output(a11_span, output_summary={"subject": final_email.subject, "scenario": scenario})
    return final_email


async def _step_reply(
    provider: "MailProvider",
    reply_to_message_id: str,
    final_email: FinalEmail,
    user_id: str | None,
    tracer: Any,
) -> Any:
    """Step: reply via provider -> sent message info (or None)."""
    reply_attrs = {
        "provider": type(provider).__name__,
        "workflow.reply_to_message_id": reply_to_message_id,
        **span_attributes_for_workflow_step("TOOL", input_summary={"reply_to_message_id": reply_to_message_id}),
    }
    with tracer.start_as_current_span("reply_to_message", kind=SpanKind.INTERNAL, attributes=reply_attrs) as reply_span:
        reply_body = final_email.body or ""
        sent_msg = await _maybe_await(provider.reply_to_message(reply_to_message_id, reply_body, user_id=user_id))
        set_span_input_output(reply_span, output_summary={"sent_message_id": sent_msg.id})
    return sent_msg


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
            workflow = EmailWorkflow()

            result = await workflow.run(
                thread=thread,
                provider=provider,
            )
            # result = await process_email_thread(
            #     thread,
            #     provider=provider,
            #     tracer=tracer,
            #     reply_to_message_id=reply_to_message_id,
            #     user_id=user_id,
            # )
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

    When tracer is passed (e.g. from graph_workflow or process_trigger), all manual spans here nest under
    that parent. Pydantic AI Agent.instrument_all() uses the global tracer and inherits the current
    context, so LLM/agent spans automatically appear as children of the corresponding manual span.
    """
    print('thread',thread)
    print("provider",provider)
    if tracer is None:
        tracer = get_tracer()
    thread_id = thread.thread_id
    latest = thread.latest_email
    original_sender = latest.sender
    original_sender_name = latest.sender_name
    original_subject = latest.subject
    log = logger.bind(thread_id=thread_id, provider=bool(provider))
    log.info("process_email_thread.start", original_sender=original_sender, original_subject=original_subject)

    decision = await _step_classify(thread, tracer)
    scenario = decision.scenario
    log = log.bind(scenario=scenario)
    log.debug("process_email_thread.scenario", confidence=decision.confidence)

    scenario_cfg = get_scenario_config(scenario)
    if not scenario_cfg.get("enabled", True):
        raise ValueError(f"Scenario {scenario} is disabled in config")

    inputs = await _step_extract(thread, scenario, scenario_cfg, tracer)
    threshold = scenario_cfg.get("low_confidence_threshold", 0.5)
    if inputs.confidence < threshold:
        log_agent_step("Orchestrator", "Low confidence -> flag for human", {"confidence": inputs.confidence})

    s3_context: dict[str, Any] | None = None
    if scenario == "S3":
        s3_context = await _run_s3_scaffold(inputs, tracer)

    trigger_data = await _step_trigger_fetch(
        inputs, scenario, scenario_cfg, tracer, s3_context=s3_context
    )
    draft = await _step_draft(thread, scenario, scenario_cfg, inputs, trigger_data, tracer)
    aggregated_context = await _step_a11_aggregate(decision, inputs, tracer)
    context_for_review = {
        "inputs": inputs,
        "trigger_data": trigger_data,
        "aggregated_context": aggregated_context,
    }

    review = await _step_review(draft, context_for_review, scenario, tracer)
    final_email = await _step_format(draft, review, original_sender, original_sender_name, scenario, tracer)

    raw_data: dict = {
        "decision_reasoning": decision.reasoning,
        "original_sender": original_sender,
        "original_subject": original_subject,
        "conversation_id": thread_id,
    }

    if provider is not None and reply_to_message_id:
        log.debug("process_email_thread.reply_attempt", reply_to_message_id=reply_to_message_id)
        sent_msg = await _step_reply(provider, reply_to_message_id, final_email, user_id, tracer)
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
