"""Custom event types for the email orchestrator workflow.

Event flow: StartEvent -> ClassifiedEvent -> ExtractedEvent -> TriggerDataEvent
         -> DraftReadyEvent -> DraftWithContextEvent -> ReviewCompleteEvent
         -> FormattedEvent -> StopEvent

Each step receives one or more event types and emits the next event in the chain.
Conditionals (S3 scaffold, DRAFT_ONLY) are handled inside step logic.
"""

from typing import Any

from workflows.events import Event


class ClassifiedEvent(Event):
    """After A0 classification: thread and decision (scenario, confidence, reasoning)."""

    thread: Any  # EmailThread - avoids circular import
    decision: Any  # ScenarioDecision
    provider: Any = None  # MailProvider | None - from StartEvent
    reply_to_message_id: str | None = None
    user_id: str | None = None
    tracer: Any = None


class ExtractedEvent(Event):
    """After input extraction: thread, scenario config, and extracted inputs."""

    thread: Any  # EmailThread
    scenario: str
    scenario_cfg: dict[str, Any]
    inputs: Any  # ProductSupplyInput, ProductAccessInput, etc.
    decision: Any  # ScenarioDecision (for aggregate step)
    provider: Any = None
    reply_to_message_id: str | None = None
    user_id: str | None = None
    tracer: Any = None


class TriggerDataEvent(Event):
    """After trigger fetch (and optionally S3 scaffold): ready for draft."""

    thread: Any  # EmailThread
    scenario: str
    scenario_cfg: dict[str, Any]
    inputs: Any
    trigger_data: dict[str, Any]
    decision: Any  # ScenarioDecision
    provider: Any = None
    reply_to_message_id: str | None = None
    user_id: str | None = None
    tracer: Any = None


class DraftReadyEvent(Event):
    """After draft generation: draft email and trigger data for context."""

    thread: Any  # EmailThread
    scenario: str
    scenario_cfg: dict[str, Any]
    inputs: Any
    trigger_data: dict[str, Any]
    draft: Any  # DraftEmail
    decision: Any  # ScenarioDecision
    provider: Any = None
    reply_to_message_id: str | None = None
    user_id: str | None = None
    tracer: Any = None


class DraftWithContextEvent(Event):
    """After A11 aggregate: draft plus context_for_review for A10."""

    thread: Any  # EmailThread
    scenario: str
    draft: Any  # DraftEmail
    context_for_review: dict[str, Any]
    decision: Any  # ScenarioDecision
    original_sender: str
    original_sender_name: str
    provider: Any = None
    reply_to_message_id: str | None = None
    user_id: str | None = None
    tracer: Any = None


class ReviewCompleteEvent(Event):
    """After A10 review: draft, review result, ready for format."""

    thread: Any  # EmailThread
    scenario: str
    draft: Any  # DraftEmail
    review: Any  # ReviewResult
    context_for_review: dict[str, Any]
    decision: Any  # ScenarioDecision
    original_sender: str
    original_sender_name: str
    provider: Any = None
    reply_to_message_id: str | None = None
    user_id: str | None = None
    tracer: Any = None


class FormattedEvent(Event):
    """After A11 format: final email ready for send or draft creation."""

    thread: Any  # EmailThread
    scenario: str
    draft: Any  # DraftEmail
    review: Any  # ReviewResult
    final_email: Any  # FinalEmail
    decision: Any  # ScenarioDecision
    raw_data: dict[str, Any]
    provider: Any = None  # MailProvider | None
    reply_to_message_id: str | None = None
    user_id: str | None = None
    original_sender: str = ""
    original_sender_name: str = ""
