"""LlamaIndex Workflow implementation for the email automation pipeline.

Steps: classify -> extract -> trigger_or_s3 -> draft -> aggregate -> review
     -> format -> send_or_draft -> StopEvent

Conditionals:
- Scenario disabled: classify returns StopEvent with error
- S3 scaffold: trigger_or_s3 runs A_D1-A_D4 only when scenario == "S3"
- DRAFT_ONLY: send_or_draft creates draft vs sends based on config
"""

from typing import Any

from workflows import Workflow, step
from workflows.events import StartEvent, StopEvent

from src.workflow.events import (
    ClassifiedEvent,
    ExtractedEvent,
    TriggerDataEvent,
    DraftReadyEvent,
    DraftWithContextEvent,
    ReviewCompleteEvent,
    FormattedEvent,
)
from src.orchestrator_steps import (
    step_classify,
    step_extract,
    step_trigger_fetch,
    step_draft,
    step_a11_aggregate,
    run_s3_scaffold,
    step_review,
    step_format,
    run_draft_or_send,
)
from src.agents.registry import get_scenario_config
from src.models.outputs import ProcessingResult
from src.utils.tracing import get_tracer
from src.utils.logger import get_logger, log_agent_step

logger = get_logger("email_automation.workflow")


class EmailOrchestratorWorkflow(Workflow):
    """Event-driven workflow for the email automation pipeline: A0 -> branch -> A10 -> A11 -> Send."""

    @step
    async def classify(self, ev: StartEvent) -> ClassifiedEvent | StopEvent:
        """A0: Classify thread into scenario. Returns StopEvent if scenario is disabled."""
        thread = ev.get("thread")
        tracer = ev.get("tracer") or get_tracer()
        log = logger.bind(thread_id=thread.thread_id)
        log.debug("workflow.step.enter", step="classify")

        decision = await step_classify(thread, tracer)
        scenario = decision.scenario
        log = log.bind(scenario=scenario)
        log.debug("workflow.step.scenario", confidence=decision.confidence)

        scenario_cfg = get_scenario_config(scenario)
        if not scenario_cfg.get("enabled", True):
            log.warning("workflow.scenario_disabled", scenario=scenario)
            raise ValueError(f"Scenario {scenario} is disabled in config")

        log.debug("workflow.step.complete", step="classify")
        return ClassifiedEvent(
            thread=thread,
            decision=decision,
            provider=ev.get("provider"),
            reply_to_message_id=ev.get("reply_to_message_id"),
            user_id=ev.get("user_id"),
            tracer=tracer,
        )

    @step
    async def extract(self, ev: ClassifiedEvent) -> ExtractedEvent:
        """Input extraction per scenario. Logs low confidence when below threshold."""
        thread = ev.thread
        decision = ev.decision
        scenario = decision.scenario
        tracer = getattr(ev, "tracer", None) or get_tracer()
        log = logger.bind(thread_id=thread.thread_id, scenario=scenario)
        log.debug("workflow.step.enter", step="extract")

        scenario_cfg = get_scenario_config(scenario)
        inputs = await step_extract(thread, scenario, scenario_cfg, tracer)

        threshold = scenario_cfg.get("low_confidence_threshold", 0.5)
        if inputs.confidence < threshold:
            log_agent_step("Orchestrator", "Low confidence -> flag for human", {"confidence": inputs.confidence})

        log.debug("workflow.step.complete", step="extract")
        return ExtractedEvent(
            thread=thread,
            scenario=scenario,
            scenario_cfg=scenario_cfg,
            inputs=inputs,
            decision=decision,
            provider=ev.provider,
            reply_to_message_id=ev.reply_to_message_id,
            user_id=ev.user_id,
            tracer=ev.tracer,
        )

    @step
    async def trigger_or_s3(self, ev: ExtractedEvent) -> TriggerDataEvent:
        """Trigger fetch. For S3 only, runs A_D1-A_D4 scaffold first."""
        thread = ev.thread
        scenario = ev.scenario
        scenario_cfg = ev.scenario_cfg
        inputs = ev.inputs
        decision = ev.decision
        tracer = getattr(ev, "tracer", None) or get_tracer()
        log = logger.bind(thread_id=thread.thread_id, scenario=scenario)
        log.debug("workflow.step.enter", step="trigger_or_s3")

        s3_context: dict[str, Any] | None = None
        if scenario == "S3":
            s3_context = await run_s3_scaffold(inputs, tracer)

        trigger_data = await step_trigger_fetch(
            inputs, scenario, scenario_cfg, tracer, s3_context=s3_context
        )

        log.debug("workflow.step.complete", step="trigger_or_s3")
        return TriggerDataEvent(
            thread=thread,
            scenario=scenario,
            scenario_cfg=scenario_cfg,
            inputs=inputs,
            trigger_data=trigger_data,
            decision=decision,
            provider=ev.provider,
            reply_to_message_id=ev.reply_to_message_id,
            user_id=ev.user_id,
            tracer=ev.tracer,
        )

    @step
    async def draft(self, ev: TriggerDataEvent) -> DraftReadyEvent:
        """Draft agent produces DraftEmail."""
        thread = ev.thread
        scenario = ev.scenario
        scenario_cfg = ev.scenario_cfg
        inputs = ev.inputs
        trigger_data = ev.trigger_data
        decision = ev.decision
        tracer = getattr(ev, "tracer", None) or get_tracer()
        log = logger.bind(thread_id=thread.thread_id, scenario=scenario)
        log.debug("workflow.step.enter", step="draft")

        draft = await step_draft(thread, scenario, scenario_cfg, inputs, trigger_data, tracer)

        log.debug("workflow.step.complete", step="draft")
        return DraftReadyEvent(
            thread=thread,
            scenario=scenario,
            scenario_cfg=scenario_cfg,
            inputs=inputs,
            trigger_data=trigger_data,
            draft=draft,
            decision=decision,
            provider=ev.provider,
            reply_to_message_id=ev.reply_to_message_id,
            user_id=ev.user_id,
            tracer=ev.tracer,
        )

    @step
    async def aggregate(self, ev: DraftReadyEvent) -> DraftWithContextEvent:
        """Input A11: Aggregate context for Decision A10 review."""
        thread = ev.thread
        scenario = ev.scenario
        draft = ev.draft
        inputs = ev.inputs
        trigger_data = ev.trigger_data
        decision = ev.decision
        tracer = getattr(ev, "tracer", None) or get_tracer()
        log = logger.bind(thread_id=thread.thread_id, scenario=scenario)
        log.debug("workflow.step.enter", step="aggregate")

        aggregated = await step_a11_aggregate(decision, inputs, tracer)
        context_for_review = {
            "inputs": inputs,
            "trigger_data": trigger_data,
            "aggregated_context": aggregated,
        }

        latest = thread.latest_email
        original_sender = latest.sender if latest else ""
        original_sender_name = latest.sender_name if latest else ""

        log.debug("workflow.step.complete", step="aggregate")
        return DraftWithContextEvent(
            thread=thread,
            scenario=scenario,
            draft=draft,
            context_for_review=context_for_review,
            decision=decision,
            original_sender=original_sender,
            original_sender_name=original_sender_name,
            provider=ev.provider,
            reply_to_message_id=ev.reply_to_message_id,
            user_id=ev.user_id,
            tracer=ev.tracer,
        )

    @step
    async def review(self, ev: DraftWithContextEvent) -> ReviewCompleteEvent:
        """Decision A10: Review draft for approval or human review."""
        thread = ev.thread
        scenario = ev.scenario
        draft = ev.draft
        context_for_review = ev.context_for_review
        decision = ev.decision
        original_sender = ev.original_sender
        original_sender_name = ev.original_sender_name
        tracer = getattr(ev, "tracer", None) or get_tracer()
        log = logger.bind(thread_id=thread.thread_id, scenario=scenario)
        log.debug("workflow.step.enter", step="review")

        review = await step_review(draft, context_for_review, scenario, tracer)

        log.debug("workflow.step.complete", step="review")
        return ReviewCompleteEvent(
            thread=thread,
            scenario=scenario,
            draft=draft,
            review=review,
            context_for_review=context_for_review,
            decision=decision,
            original_sender=original_sender,
            original_sender_name=original_sender_name,
            provider=ev.provider,
            reply_to_message_id=ev.reply_to_message_id,
            user_id=ev.user_id,
            tracer=ev.tracer,
        )

    @step
    async def format(self, ev: ReviewCompleteEvent) -> FormattedEvent:
        """Email A12: Format final email."""
        thread = ev.thread
        scenario = ev.scenario
        draft = ev.draft
        review = ev.review
        context_for_review = ev.context_for_review
        decision = ev.decision
        original_sender = ev.original_sender
        original_sender_name = ev.original_sender_name
        tracer = getattr(ev, "tracer", None) or get_tracer()
        log = logger.bind(thread_id=thread.thread_id, scenario=scenario)
        log.debug("workflow.step.enter", step="format")

        final_email = await step_format(
            draft, review, original_sender, original_sender_name, scenario, tracer
        )

        latest = thread.latest_email
        original_subject = latest.subject if latest else ""
        raw_data: dict[str, Any] = {
            "decision_reasoning": decision.reasoning,
            "original_sender": original_sender,
            "original_subject": original_subject,
            "conversation_id": thread.thread_id,
        }

        log.debug("workflow.step.complete", step="format")
        return FormattedEvent(
            thread=thread,
            scenario=scenario,
            draft=draft,
            review=review,
            final_email=final_email,
            decision=decision,
            raw_data=raw_data,
            provider=ev.provider,
            reply_to_message_id=ev.reply_to_message_id,
            user_id=ev.user_id,
            original_sender=original_sender,
            original_sender_name=original_sender_name,
        )

    @step
    async def send_or_draft(self, ev: FormattedEvent) -> StopEvent:
        """Create draft or send reply based on DRAFT_ONLY; return ProcessingResult."""
        thread = ev.thread
        scenario = ev.scenario
        draft = ev.draft
        review = ev.review
        final_email = ev.final_email
        decision = ev.decision
        raw_data = dict(ev.raw_data)
        provider = ev.provider
        reply_to_message_id = ev.reply_to_message_id
        user_id = ev.user_id
        original_sender_name = ev.original_sender_name or ""
        tracer = getattr(ev, "tracer", None) or get_tracer()
        log = logger.bind(thread_id=thread.thread_id, scenario=scenario)
        log.debug("workflow.step.enter", step="send_or_draft")

        if provider is not None and reply_to_message_id:
            raw_data = await run_draft_or_send(
                provider=provider,
                reply_to_message_id=reply_to_message_id,
                user_id=user_id,
                thread_id=thread.thread_id,
                scenario=scenario,
                draft=draft,
                final_email=final_email,
                original_sender_name=original_sender_name,
                tracer=tracer,
                raw_data=raw_data,
            )

        log.info(
            "workflow.step.complete",
            step="send_or_draft",
            review_status=review.status,
            final_subject=final_email.subject,
        )

        result = ProcessingResult(
            thread_id=thread.thread_id,
            scenario=scenario,
            decision_confidence=decision.confidence,
            draft=draft,
            review=review,
            final_email=final_email,
            raw_data=raw_data,
        )
        return StopEvent(result=result)
