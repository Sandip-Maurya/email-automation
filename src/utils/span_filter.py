"""Span filter processor: drop descendant spans of configured boundary names.

Use this so Phoenix shows only top-level workflow spans (e.g. fetch_thread,
reply_to_message) without noisy Graph/HTTP child spans. Boundary names are
configurable via TRACE_DROP_CHILDREN_OF_SPANS. Thread-safe; uses a memory
cap to avoid unbounded growth in long-running processes.
"""

from __future__ import annotations

import threading
from typing import Set

from opentelemetry.sdk.trace import ReadableSpan, SpanProcessor

# Default boundary span names whose descendants are dropped (boundary spans themselves are exported).
_DEFAULT_DROP_CHILDREN_OF: frozenset[str] = frozenset({"fetch_thread", "reply_to_message"})

# Memory caps: prevent unbounded growth in long-running webhook/CLI.
_MAX_BOUNDARY_IDS = 1_000
_MAX_DROPPED_IDS = 50_000


class DropDescendantsFilterProcessor(SpanProcessor):
    """
    SpanProcessor that forwards spans to a downstream processor except for
    descendants of configured boundary span names. Boundary spans (e.g.
    fetch_thread, reply_to_message) are exported; their children and
    further descendants are not. Thread-safe; caps set sizes for memory safety.
    """

    def __init__(
        self,
        next_processor: SpanProcessor,
        drop_children_of_names: Set[str] | frozenset[str] | None = None,
        max_boundary_ids: int = _MAX_BOUNDARY_IDS,
        max_dropped_ids: int = _MAX_DROPPED_IDS,
    ) -> None:
        """
        Args:
            next_processor: Processor to forward spans to (e.g. BatchSpanProcessor).
            drop_children_of_names: Span names whose descendants should be dropped.
                The spans with these names are exported; only their children are dropped.
                Default: fetch_thread, reply_to_message.
            max_boundary_ids: Max size of internal boundary span_id set; when exceeded, clear it.
            max_dropped_ids: Max size of internal dropped span_id set; when exceeded, clear it.
        """
        self._next = next_processor
        self._drop_children_of = (
            set(drop_children_of_names)
            if drop_children_of_names is not None
            else set(_DEFAULT_DROP_CHILDREN_OF)
        )
        self._max_boundary_ids = max_boundary_ids
        self._max_dropped_ids = max_dropped_ids
        self._boundary_span_ids: set[int] = set()
        self._dropped_span_ids: set[int] = set()
        self._lock = threading.Lock()

    def on_start(
        self,
        span: object,
        parent_context: object | None = None,
    ) -> None:
        """Forward span start to the next processor."""
        self._next.on_start(span, parent_context=parent_context)

    def on_end(self, span: ReadableSpan) -> None:
        """Forward span to next processor only if it is not a descendant of a boundary span."""
        name = span.name
        ctx = span.get_span_context()
        span_id = ctx.span_id
        parent_ctx = getattr(span, "parent", None)
        parent_span_id = parent_ctx.span_id if parent_ctx is not None else None

        with self._lock:
            if self._drop_children_of and name in self._drop_children_of:
                if len(self._boundary_span_ids) >= self._max_boundary_ids:
                    self._boundary_span_ids.clear()
                self._boundary_span_ids.add(span_id)
                self._next.on_end(span)
                return

            if parent_span_id is not None and (
                parent_span_id in self._boundary_span_ids or parent_span_id in self._dropped_span_ids
            ):
                if len(self._dropped_span_ids) >= self._max_dropped_ids:
                    self._dropped_span_ids.clear()
                self._dropped_span_ids.add(span_id)
                return

        self._next.on_end(span)

    def shutdown(self) -> None:
        """Delegate to the next processor."""
        self._next.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Delegate to the next processor."""
        return self._next.force_flush(timeout_millis)
