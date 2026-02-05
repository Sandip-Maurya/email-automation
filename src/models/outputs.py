"""Response, decision, and processing result models."""

from typing import Any, Literal, Optional

from pydantic import BaseModel


class ScenarioDecision(BaseModel):
    """Decision Agent A0 output: which scenario to route to."""

    scenario: Literal["S1", "S2", "S3", "S4"]
    confidence: float
    reasoning: str


class DraftEmail(BaseModel):
    """Draft email from Draft Email Agents (A7/A8)."""

    subject: str
    body: str
    scenario: str
    metadata: dict[str, Any] = {}


class ReviewResult(BaseModel):
    """Review Agent A10 output: approve or flag for human."""

    status: Literal["approved", "needs_human_review"]
    confidence: float
    quality_score: float
    accuracy_notes: list[str] = []
    suggestions: list[str] = []


class FinalEmail(BaseModel):
    """Final formatted email from Email Agent A11."""

    to: Optional[str] = None
    subject: str
    body: str
    review_status: str
    metadata: dict[str, Any] = {}


class ProcessingResult(BaseModel):
    """End-to-end processing result for one email thread."""

    thread_id: str
    scenario: str
    decision_confidence: float
    draft: DraftEmail
    review: ReviewResult
    final_email: FinalEmail
    raw_data: dict[str, Any] = {}
