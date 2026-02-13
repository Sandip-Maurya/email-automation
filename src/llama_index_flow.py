from typing import Any, Dict

from llama_index.core.workflow import (
    Workflow,
    step,
    Event,
    StartEvent,
    StopEvent,
)

from src.models.outputs import ProcessingResult
from src.orchestration_step import (
    _step_classify,
    _step_extract,
    _step_trigger_fetch,
    _step_draft,
    _step_a11_aggregate,
    _step_review,
    _step_format,
    _step_reply,
)

from src.agents.registry import get_scenario_config
from src.utils.tracing import get_tracer


# ============================================================
# EVENT MODELS (NO __init__)
# ============================================================

class ClassifiedEvent(Event):
    thread: Any
    provider: Any
    reply_to_message_id: str | None
    user_id: str | None
    decision: Any


class ExtractedEvent(Event):
    thread: Any
    provider: Any
    reply_to_message_id: str | None
    user_id: str | None
    decision: Any
    inputs: Any
    scenario_cfg: Dict


class DraftedEvent(Event):
    thread: Any
    provider: Any
    reply_to_message_id: str | None
    user_id: str | None
    decision: Any
    inputs: Any
    scenario_cfg: Dict
    trigger_data: Dict
    draft: Any


# ============================================================
# DEBUG HELPER
# ============================================================

def debug_print(title: str, data: dict):
    print(f"\n{title}")
    for k, v in data.items():
        print(f"   {k}: {v}")


# ============================================================
# WORKFLOW
# ============================================================

class EmailWorkflow(Workflow):

    # --------------------------------------------------------
    # STEP 1 — CLASSIFY
    # --------------------------------------------------------
    @step
    async def classify(self, ev: StartEvent) -> ClassifiedEvent:
        print("\n========== STEP A0: CLASSIFY ==========")

        tracer = get_tracer()

        debug_print("INPUT", {
            "thread_id": ev.thread.thread_id,
            "subject": ev.thread.latest_email.subject if ev.thread.latest_email else None,
        })

        decision = await _step_classify(ev.thread, tracer)

        debug_print("OUTPUT", {
            "scenario": decision.scenario,
            "confidence": decision.confidence,
        })

        return ClassifiedEvent(
            thread=ev.thread,
            provider=ev.provider,
            reply_to_message_id=ev.reply_to_message_id,
            user_id=ev.user_id,
            decision=decision,
        )

    # --------------------------------------------------------
    # STEP 2 — EXTRACT
    # --------------------------------------------------------
    @step
    async def extract(self, ev: ClassifiedEvent) -> ExtractedEvent:
        print("\n========== STEP: INPUT EXTRACT ==========")

        tracer = get_tracer()
        scenario_cfg = get_scenario_config(ev.decision.scenario)

        debug_print("INPUT", {
            "scenario": ev.decision.scenario,
            "input_agent": scenario_cfg["input_agent"],
        })

        inputs = await _step_extract(
            ev.thread,
            ev.decision.scenario,
            scenario_cfg,
            tracer,
        )

        debug_print("OUTPUT", {
            "confidence": inputs.confidence,
        })

        return ExtractedEvent(
            thread=ev.thread,
            provider=ev.provider,
            reply_to_message_id=ev.reply_to_message_id,
            user_id=ev.user_id,
            decision=ev.decision,
            inputs=inputs,
            scenario_cfg=scenario_cfg,
        )

    # --------------------------------------------------------
    # STEP 3 — TRIGGER + DRAFT
    # --------------------------------------------------------
    @step
    async def draft(self, ev: ExtractedEvent) -> DraftedEvent:
        print("\n========== STEP: TRIGGER + DRAFT ==========")

        tracer = get_tracer()

        trigger_data = await _step_trigger_fetch(
            ev.inputs,
            ev.decision.scenario,
            ev.scenario_cfg,
            tracer,
        )

        debug_print("TRIGGER OUTPUT", trigger_data)

        draft = await _step_draft(
            ev.thread,
            ev.decision.scenario,
            ev.scenario_cfg,
            ev.inputs,
            trigger_data,
            tracer,
        )

        debug_print("DRAFT OUTPUT", {
            "subject": draft.subject,
            "scenario": draft.scenario,
        })

        return DraftedEvent(
            thread=ev.thread,
            provider=ev.provider,
            reply_to_message_id=ev.reply_to_message_id,
            user_id=ev.user_id,
            decision=ev.decision,
            inputs=ev.inputs,
            scenario_cfg=ev.scenario_cfg,
            trigger_data=trigger_data,
            draft=draft,
        )

    # --------------------------------------------------------
    # STEP 4 — REVIEW + FORMAT + SEND
    # --------------------------------------------------------
    @step
    async def review_and_send(self, ev: DraftedEvent) -> StopEvent:
        print("\n========== STEP: REVIEW + FORMAT + SEND ==========")

        tracer = get_tracer()

        # A11 Aggregate
        aggregated = await _step_a11_aggregate(
            ev.decision,
            ev.inputs,
            tracer,
        )

        # A10 Review
        review = await _step_review(
            ev.draft,
            {
                "inputs": ev.inputs,
                "trigger_data": ev.trigger_data,
                "aggregated_context": aggregated,
            },
            ev.decision.scenario,
            tracer,
        )

        debug_print("REVIEW OUTPUT", {
            "status": review.status,
        })

        # Format final email
        latest = ev.thread.latest_email

        final_email = await _step_format(
            ev.draft,
            review,
            latest.sender,
            latest.sender_name,
            ev.decision.scenario,
            tracer,
        )

        debug_print("FINAL EMAIL", {
            "subject": final_email.subject,
        })

        raw_data: Dict[str, Any] = {}

        # ✅ FIXED — now using passed reply_to_message_id + user_id
        if ev.provider and ev.reply_to_message_id:
            sent = await _step_reply(
                ev.provider,
                ev.reply_to_message_id,
                final_email,
                user_id=ev.user_id,
                tracer=tracer,
            )

            debug_print("SEND OUTPUT", {
                "sent_message_id": sent.id,
            })

            raw_data["sent_message_id"] = sent.id
            raw_data["sent_at"] = sent.receivedDateTime
        else:
            print("⚠ No provider or reply_to_message_id — skipping send")

        print("\n========== WORKFLOW COMPLETE ==========\n")

        return StopEvent(
            result=ProcessingResult(
                thread_id=ev.thread.thread_id,
                scenario=ev.decision.scenario,
                decision_confidence=ev.decision.confidence,
                draft=ev.draft,
                review=review,
                final_email=final_email,
                raw_data=raw_data,
            )
        )
