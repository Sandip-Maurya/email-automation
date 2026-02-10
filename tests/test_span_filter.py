"""Tests for AllowlistSpanFilterProcessor."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils.span_filter import AllowlistSpanFilterProcessor


def _make_span(name: str, span_id: int = 1, parent_span_id: int | None = None):
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


class TestAllowlistSpanFilterProcessor(unittest.TestCase):
    """Unit tests for AllowlistSpanFilterProcessor."""

    def test_allowed_exact_forwarded(self):
        """Span name in allowed exact set is forwarded."""
        mock = MockNextProcessor()
        proc = AllowlistSpanFilterProcessor(mock, allowed_span_names=["fetch_thread", "process_trigger"])
        span = _make_span("fetch_thread", span_id=100)
        proc.on_end(span)
        self.assertEqual(mock.ended_names, ["fetch_thread"])
        self.assertEqual(mock.ended_span_ids, [100])

    def test_allowed_prefix_forwarded(self):
        """Span name matching allowed prefix is forwarded."""
        mock = MockNextProcessor()
        proc = AllowlistSpanFilterProcessor(mock, allowed_span_names=["agent*"])
        span = _make_span("agent run", span_id=101)
        proc.on_end(span)
        self.assertEqual(mock.ended_names, ["agent run"])
        self.assertEqual(mock.ended_span_ids, [101])

    def test_not_in_allowlist_dropped(self):
        """Span name not in allowlist is not forwarded."""
        mock = MockNextProcessor()
        proc = AllowlistSpanFilterProcessor(mock, allowed_span_names=["fetch_thread", "process_trigger"])
        span = _make_span("send_async", span_id=102)
        proc.on_end(span)
        self.assertEqual(mock.ended_names, [])
        self.assertEqual(mock.ended_span_ids, [])

    def test_empty_allowlist_forwards_all(self):
        """When allowlist is empty or None, all spans are forwarded."""
        mock = MockNextProcessor()
        proc = AllowlistSpanFilterProcessor(mock, allowed_span_names=[])
        span1 = _make_span("fetch_thread", span_id=1)
        span2 = _make_span("send_async", span_id=2)
        proc.on_end(span1)
        proc.on_end(span2)
        self.assertEqual(mock.ended_names, ["fetch_thread", "send_async"])
        self.assertEqual(mock.ended_span_ids, [1, 2])

    def test_none_allowlist_forwards_all(self):
        """When allowed_span_names and config_path are None, all spans are forwarded."""
        mock = MockNextProcessor()
        proc = AllowlistSpanFilterProcessor(mock)
        span = _make_span("any_span", span_id=99)
        proc.on_end(span)
        self.assertEqual(mock.ended_names, ["any_span"])
        self.assertEqual(mock.ended_span_ids, [99])

    def test_on_start_forwarded(self):
        """on_start is always forwarded to next processor."""
        mock = MockNextProcessor()
        proc = AllowlistSpanFilterProcessor(mock, allowed_span_names=["fetch_thread"])
        span = _make_span("noise", span_id=1)
        proc.on_start(span, parent_context=None)
        self.assertEqual(mock.ended_names, [])

    def test_config_path_loads_allowlist(self):
        """Processor loads allowlist from JSON config path when file exists."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"allowed_span_names": ["only_this"]}')
            config_path = Path(f.name)
        try:
            mock = MockNextProcessor()
            proc = AllowlistSpanFilterProcessor(mock, config_path=config_path)
            proc.on_end(_make_span("only_this", span_id=1))
            proc.on_end(_make_span("other", span_id=2))
            self.assertEqual(mock.ended_names, ["only_this"])
            self.assertEqual(mock.ended_span_ids, [1])
        finally:
            config_path.unlink(missing_ok=True)

    def test_config_path_missing_forwards_all(self):
        """When config_path does not exist, allowlist is empty so all spans are forwarded."""
        mock = MockNextProcessor()
        proc = AllowlistSpanFilterProcessor(mock, config_path=Path("/nonexistent/trace_spans.json"))
        proc.on_end(_make_span("any", span_id=1))
        self.assertEqual(mock.ended_names, ["any"])
        self.assertEqual(mock.ended_span_ids, [1])
