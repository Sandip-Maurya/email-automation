"""Tests for DropDescendantsFilterProcessor."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils.span_filter import DropDescendantsFilterProcessor


def _make_span(name: str, span_id: int, parent_span_id: int | None):
    """Minimal mock ReadableSpan with name, span_id, parent.span_id."""
    ctx = type("SpanContext", (), {"span_id": span_id})()
    parent = type("ParentContext", (), {"span_id": parent_span_id})() if parent_span_id is not None else None

    def get_span_context(_=None):
        return ctx

    span = type(
        "ReadableSpan",
        (),
        {"name": name, "get_span_context": get_span_context, "parent": parent},
    )()
    return span


class MockNextProcessor:
    """Records which spans received on_end and forwards on_start."""

    def __init__(self):
        self.ended_names: list[str] = []
        self.ended_span_ids: list[int] = []

    def on_start(self, span, parent_context=None):
        pass

    def on_end(self, span):
        ctx = span.get_span_context()
        self.ended_names.append(span.name)
        self.ended_span_ids.append(ctx.span_id)

    def shutdown(self):
        pass

    def force_flush(self, timeout_millis=30000):
        return True


class TestDropDescendantsFilterProcessor(unittest.TestCase):
    """Unit tests for DropDescendantsFilterProcessor."""

    def test_boundary_span_forwarded(self):
        """Boundary span (e.g. fetch_thread) is forwarded to next processor."""
        mock = MockNextProcessor()
        proc = DropDescendantsFilterProcessor(mock, drop_children_of_names={"fetch_thread", "reply_to_message"})
        span = _make_span("fetch_thread", span_id=100, parent_span_id=1)
        proc.on_end(span)
        self.assertEqual(mock.ended_names, ["fetch_thread"])
        self.assertEqual(mock.ended_span_ids, [100])

    def test_child_of_boundary_dropped(self):
        """Child of a boundary span is not forwarded."""
        mock = MockNextProcessor()
        proc = DropDescendantsFilterProcessor(mock, drop_children_of_names={"fetch_thread", "reply_to_message"})
        boundary = _make_span("fetch_thread", span_id=100, parent_span_id=1)
        child = _make_span("send_async", span_id=101, parent_span_id=100)
        proc.on_end(boundary)
        proc.on_end(child)
        self.assertEqual(mock.ended_names, ["fetch_thread"])
        self.assertEqual(mock.ended_span_ids, [100])

    def test_grandchild_of_boundary_dropped(self):
        """Grandchild of a boundary span is not forwarded."""
        mock = MockNextProcessor()
        proc = DropDescendantsFilterProcessor(mock, drop_children_of_names={"fetch_thread"})
        boundary = _make_span("fetch_thread", span_id=100, parent_span_id=1)
        child = _make_span("send_async", span_id=101, parent_span_id=100)
        grandchild = _make_span("get_http_response_message", span_id=102, parent_span_id=101)
        proc.on_end(boundary)
        proc.on_end(child)
        proc.on_end(grandchild)
        self.assertEqual(mock.ended_names, ["fetch_thread"])
        self.assertEqual(mock.ended_span_ids, [100])

    def test_root_span_forwarded(self):
        """Root span (no parent) is forwarded."""
        mock = MockNextProcessor()
        proc = DropDescendantsFilterProcessor(mock, drop_children_of_names={"fetch_thread"})
        root = _make_span("process_trigger", span_id=1, parent_span_id=None)
        proc.on_end(root)
        self.assertEqual(mock.ended_names, ["process_trigger"])
        self.assertEqual(mock.ended_span_ids, [1])

    def test_span_with_parent_not_boundary_forwarded(self):
        """Span whose parent is not a boundary and not dropped is forwarded."""
        mock = MockNextProcessor()
        proc = DropDescendantsFilterProcessor(mock, drop_children_of_names={"fetch_thread"})
        root = _make_span("A0_classify", span_id=50, parent_span_id=1)
        child = _make_span("agent run", span_id=51, parent_span_id=50)
        proc.on_end(root)
        proc.on_end(child)
        self.assertEqual(mock.ended_names, ["A0_classify", "agent run"])
        self.assertEqual(mock.ended_span_ids, [50, 51])

    def test_empty_drop_children_forwards_all(self):
        """When drop_children_of_names is empty, all spans are forwarded."""
        mock = MockNextProcessor()
        proc = DropDescendantsFilterProcessor(mock, drop_children_of_names=set())
        boundary_like = _make_span("fetch_thread", span_id=100, parent_span_id=1)
        child = _make_span("send_async", span_id=101, parent_span_id=100)
        proc.on_end(boundary_like)
        proc.on_end(child)
        self.assertEqual(mock.ended_names, ["fetch_thread", "send_async"])
        self.assertEqual(mock.ended_span_ids, [100, 101])

    def test_reply_to_message_boundary(self):
        """reply_to_message is a boundary; its child is dropped."""
        mock = MockNextProcessor()
        proc = DropDescendantsFilterProcessor(mock, drop_children_of_names={"fetch_thread", "reply_to_message"})
        reply = _make_span("reply_to_message", span_id=200, parent_span_id=1)
        child = _make_span("send_async", span_id=201, parent_span_id=200)
        proc.on_end(reply)
        proc.on_end(child)
        self.assertEqual(mock.ended_names, ["reply_to_message"])
        self.assertEqual(mock.ended_span_ids, [200])

    def test_on_start_forwarded(self):
        """on_start is always forwarded to next processor."""
        mock = MockNextProcessor()
        proc = DropDescendantsFilterProcessor(mock, drop_children_of_names={"fetch_thread"})
        span = _make_span("any", span_id=1, parent_span_id=None)
        proc.on_start(span, parent_context=None)
        self.assertEqual(mock.ended_names, [])
