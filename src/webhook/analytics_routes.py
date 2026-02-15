"""Analytics API routes: counts, draft-vs-sent, by-scenario, by-user."""

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from src.db import get_session
from src.db.models.email_outcome import EmailOutcome

router = APIRouter(prefix="/webhook/analytics", tags=["analytics"])


def _parse_datetime_param(value: Optional[str]) -> Optional[datetime]:
    """Parse optional ISO datetime query param."""
    if not value or not value.strip():
        return None
    try:
        s = value.strip().replace("Z", "+00:00")
        if len(s) <= 10:
            return datetime.fromisoformat(s + "T00:00:00+00:00")
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


@router.get("/counts")
async def analytics_counts(
    from_: Optional[str] = Query(None, alias="from", description="ISO date or datetime (inclusive)"),
    to: Optional[str] = Query(None, description="ISO date or datetime (inclusive)"),
) -> dict[str, Any]:
    """Return total counts by status: draft_created, sent, superseded. Optional time range on created_at."""
    from_dt = _parse_datetime_param(from_)
    to_dt = _parse_datetime_param(to)

    def _query() -> dict[str, Any]:
        with get_session() as session:
            q = select(EmailOutcome.status, func.count(EmailOutcome.id)).where(
                True
            )
            if from_dt is not None:
                q = q.where(EmailOutcome.created_at >= from_dt)
            if to_dt is not None:
                q = q.where(EmailOutcome.created_at <= to_dt)
            q = q.group_by(EmailOutcome.status)
            rows = list(session.execute(q).all())
        draft_created = sent = superseded = 0
        for status, count in rows:
            if status == "draft_created":
                draft_created = count
            elif status == "sent":
                sent = count
            elif status == "superseded":
                superseded = count
        return {
            "draft_created": draft_created,
            "sent": sent,
            "superseded": superseded,
            "from": from_,
            "to": to,
        }

    return _query()


@router.get("/draft-vs-sent")
async def analytics_draft_vs_sent(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """Return outcomes that have both draft and sent data (status=sent), with optional changed flag."""
    def _query() -> dict[str, Any]:
        with get_session() as session:
            q = (
                select(EmailOutcome)
                .where(EmailOutcome.status == "sent")
                .where(EmailOutcome.sent_at.isnot(None))
                .order_by(EmailOutcome.sent_at.desc())
                .limit(limit)
                .offset(offset)
            )
            rows = list(session.scalars(q).all())
            items = []
            for r in rows:
                subject_changed = (r.final_subject or "") != (r.sent_subject or "")
                body_changed = (r.final_body or "") != (r.sent_body or "")
                items.append({
                    "message_id": r.message_id,
                    "conversation_id": r.conversation_id,
                    "scenario": r.scenario,
                    "final_subject": r.final_subject,
                    "final_body": r.final_body,
                    "sent_subject": r.sent_subject,
                    "sent_body": r.sent_body,
                    "sent_to": r.sent_to,
                    "sent_at": r.sent_at.isoformat() if r.sent_at else None,
                    "subject_changed": subject_changed,
                    "body_changed": body_changed,
                    "changed": subject_changed or body_changed,
                })
        return {"items": items, "limit": limit, "offset": offset}

    return _query()


@router.get("/by-scenario")
async def analytics_by_scenario(
    from_: Optional[str] = Query(None, alias="from", description="ISO date or datetime (inclusive)"),
    to: Optional[str] = Query(None, description="ISO date or datetime (inclusive)"),
) -> dict[str, Any]:
    """Return counts per scenario (S1, S2, S3, S4): draft_created, sent, superseded."""
    from_dt = _parse_datetime_param(from_)
    to_dt = _parse_datetime_param(to)

    def _query() -> dict[str, Any]:
        with get_session() as session:
            q = select(
                EmailOutcome.scenario,
                EmailOutcome.status,
                func.count(EmailOutcome.id),
            ).where(True)
            if from_dt is not None:
                q = q.where(EmailOutcome.created_at >= from_dt)
            if to_dt is not None:
                q = q.where(EmailOutcome.created_at <= to_dt)
            q = q.group_by(EmailOutcome.scenario, EmailOutcome.status)
            rows = list(session.execute(q).all())
        by_scenario: dict[str, dict[str, int]] = {}
        for scenario, status, count in rows:
            if scenario not in by_scenario:
                by_scenario[scenario] = {"draft_created": 0, "sent": 0, "superseded": 0}
            by_scenario[scenario][status] = count
        items = [
            {"scenario": s, **counts}
            for s, counts in sorted(by_scenario.items())
        ]
        return {"items": items, "from": from_, "to": to}

    return _query()


@router.get("/by-user")
async def analytics_by_user(
    from_: Optional[str] = Query(None, alias="from", description="ISO date or datetime (inclusive)"),
    to: Optional[str] = Query(None, description="ISO date or datetime (inclusive)"),
) -> dict[str, Any]:
    """Return counts per user_id (or 'default' when null), including user_name when stored."""
    from_dt = _parse_datetime_param(from_)
    to_dt = _parse_datetime_param(to)

    def _query() -> dict[str, Any]:
        with get_session() as session:
            q = select(
                EmailOutcome.user_id,
                EmailOutcome.user_name,
                EmailOutcome.status,
                func.count(EmailOutcome.id),
            ).where(True)
            if from_dt is not None:
                q = q.where(EmailOutcome.created_at >= from_dt)
            if to_dt is not None:
                q = q.where(EmailOutcome.created_at <= to_dt)
            q = q.group_by(EmailOutcome.user_id, EmailOutcome.user_name, EmailOutcome.status)
            rows = list(session.execute(q).all())
        by_user: dict[str, dict[str, Any]] = {}
        for user_id, user_name, status, count in rows:
            key = user_id if user_id else "default"
            if key not in by_user:
                by_user[key] = {
                    "user_id": user_id,
                    "user_name": user_name,
                    "draft_created": 0,
                    "sent": 0,
                    "superseded": 0,
                }
            by_user[key][status] = by_user[key].get(status, 0) + count
            if user_name and not by_user[key].get("user_name"):
                by_user[key]["user_name"] = user_name
        items = list(by_user.values())
        return {"items": items, "from": from_, "to": to}

    return _query()
