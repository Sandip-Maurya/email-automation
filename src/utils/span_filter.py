"""Allowlist-only span filter: only spans in the allowlist are exported; rest are dropped with a warning.

Config is a JSON file (e.g. config/trace_spans.json) with "allowed_span_names": [ ... ].
Entries without "*" are exact match; entries ending with "*" are prefix match.
If the allowlist is missing or empty, all spans are allowed (no filtering).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Sequence

from opentelemetry.sdk.trace import ReadableSpan, SpanProcessor

logger = logging.getLogger(__name__)


def _parse_allowed_names(entries: Sequence[str]) -> tuple[set[str], set[str]]:
    """Split allowlist into exact and prefix sets. Entries ending with '*' become prefix (stored without '*')."""
    exact: set[str] = set()
    prefix: set[str] = set()
    for s in entries:
        if not isinstance(s, str):
            continue
        s = s.strip()
        if not s:
            continue
        if s.endswith("*"):
            prefix.add(s[:-1])
        else:
            exact.add(s)
    return exact, prefix


def _load_allowed_from_path(config_path: Path) -> tuple[set[str], set[str]]:
    """Load allowed_span_names from JSON file. Returns (exact, prefix) or (set(), set()) if missing/empty."""
    if not config_path.exists():
        return set(), set()
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        names = data.get("allowed_span_names")
        if not names or not isinstance(names, (list, tuple)):
            return set(), set()
        return _parse_allowed_names(names)
    except (OSError, json.JSONDecodeError, TypeError) as e:
        logger.warning("trace_span_filter_config_load_failed path=%s error=%s", config_path, e)
        return set(), set()


class AllowlistSpanFilterProcessor(SpanProcessor):
    """
    SpanProcessor that forwards only spans whose name is in the allowlist (exact or prefix).
    All other spans are dropped and logged with a warning. Root and child spans are treated the same.
    If the allowlist is empty (no config or empty list), all spans are forwarded (no filtering).
    """

    def __init__(
        self,
        next_processor: SpanProcessor,
        allowed_span_names: Sequence[str] | None = None,
        config_path: Path | None = None,
    ) -> None:
        """
        Args:
            next_processor: Processor to forward allowed spans to (e.g. BatchSpanProcessor).
            allowed_span_names: If provided, use this list as the allowlist (for tests or explicit config).
            config_path: If allowed_span_names is not provided and this path exists, load allowlist from JSON.
            If both are None or the loaded list is empty, allow all spans (no filtering).
        """
        self._next = next_processor
        if allowed_span_names is not None:
            self._allowed_exact, self._allowed_prefix = _parse_allowed_names(allowed_span_names)
        elif config_path is not None:
            self._allowed_exact, self._allowed_prefix = _load_allowed_from_path(config_path)
        else:
            self._allowed_exact, self._allowed_prefix = set(), set()

    def _is_allowed(self, name: str) -> bool:
        if not self._allowed_exact and not self._allowed_prefix:
            return True
        if name in self._allowed_exact:
            return True
        if any(name.startswith(p) for p in self._allowed_prefix):
            return True
        return False

    def on_start(
        self,
        span: object,
        parent_context: object | None = None,
    ) -> None:
        """Forward span start to the next processor."""
        self._next.on_start(span, parent_context=parent_context)

    def on_end(self, span: ReadableSpan) -> None:
        """Forward span only if its name is in the allowlist; otherwise log warning and drop."""
        name = span.name
        if self._is_allowed(name):
            self._next.on_end(span)
            return
        logger.warning("trace_span_filtered span_name=%s", name)
        # Do not forward

    def shutdown(self) -> None:
        """Delegate to the next processor."""
        self._next.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Delegate to the next processor."""
        return self._next.force_flush(timeout_millis)
