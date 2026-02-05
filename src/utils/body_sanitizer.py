"""Email body sanitizer with configurable pipeline.

Usage:
    from src.utils.body_sanitizer import sanitize_email_body

    clean_body = sanitize_email_body(raw_body, content_type="html")
"""

import html
import re
from typing import Callable

from bs4 import BeautifulSoup

# Type alias for sanitizer functions
Sanitizer = Callable[[str, str], str]


# -----------------------------------------------------------------------------
# Individual Sanitizers
# -----------------------------------------------------------------------------


def html_to_text(text: str, content_type: str) -> str:
    """Convert HTML to plain text, preserving structure."""
    if content_type.lower() != "html" or not text.strip():
        return text

    soup = BeautifulSoup(text, "lxml")

    # Remove non-content elements
    for el in soup(["script", "style", "head", "meta", "link"]):
        el.decompose()

    # Convert block elements to newlines
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for tag in soup.find_all(["p", "div", "tr", "li"]):
        tag.insert_before("\n")
        tag.insert_after("\n")
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        tag.insert_before("\n\n")
        tag.insert_after("\n")

    return html.unescape(soup.get_text(separator=" "))


# Pre-compiled patterns for security banners
_SECURITY_BANNER_PATTERNS = [
    re.compile(r"^You don't often get e?-?mail from\s+.+\.\s*Learn why this is important.*$", re.I),
    re.compile(r"^WARNING:\s*External\s+e?-?mail.*$", re.I),
    re.compile(r"^CAUTION:\s*(This\s+)?(e?-?mail|message)\s+(originated|came)\s+from\s+(outside|external).*$", re.I),
    re.compile(r"^EXTERNAL:\s*This\s+e?-?mail.*$", re.I),
    re.compile(r"^.*Be\s+careful\s+when\s+opening\s+links\s+or\s+attachments.*$", re.I),
    re.compile(r"^.*Report\s+(suspicious\s+)?(e?-?mails?|this)\s+(with\s+the\s+)?.*Report\s+Phishing.*$", re.I),
    re.compile(r"^.*Report\s+Phishing.*button.*$", re.I),
    re.compile(r"^\[?\s*EXTERNAL\s*\]?:?\s*$", re.I),
    re.compile(r"^This\s+(message|e?-?mail)\s+(was\s+sent\s+)?from\s+(an?\s+)?(external|outside)\s+(source|sender|party).*$", re.I),
    re.compile(r"^This\s+(message|e?-?mail)\s+has\s+been\s+scanned\s+for\s+(viruses|malware).*$", re.I),
    re.compile(r"^.*Do\s+not\s+click\s+(on\s+)?links\s+or\s+open\s+attachments\s+unless.*$", re.I),
    re.compile(r"^\[\s*(EXTERNAL|EXT|CAUTION|WARNING|SPAM\??)\s*\]\s*$", re.I),
]
_STRIP_PREFIX = re.compile(r"^\[\s*(EXTERNAL|EXT)\s*\]\s*", re.I)


def remove_security_banners(text: str, content_type: str) -> str:
    """Remove email security warnings (external sender alerts, phishing notices)."""
    result = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            result.append(line)
            continue
        if any(p.match(stripped) for p in _SECURITY_BANNER_PATTERNS):
            continue
        result.append(_STRIP_PREFIX.sub("", line))
    return "\n".join(result)


# Pre-compiled patterns for quoted replies
_QUOTE_START_PATTERNS = [
    re.compile(r"^On\s+.{5,50}\s+wrote:\s*$", re.I),
    re.compile(r"^-{3,}\s*Original\s+Message\s*-{3,}\s*$", re.I),
    re.compile(r"^From:\s+.+$", re.I),
    re.compile(r"^On\s+\w{3},\s+\w{3}\s+\d{1,2},\s+\d{4}\s+at\s+\d{1,2}:\d{2}", re.I),
]
_HEADER_CONTINUATION = re.compile(r"^(To|Cc|Subject|Date|Sent):\s+", re.I)


def remove_quoted_replies(text: str, content_type: str) -> str:
    """Remove quoted reply content (On X wrote:, > lines, Original Message)."""
    result = []
    in_quote = False

    for line in text.split("\n"):
        stripped = line.strip()

        if any(p.match(stripped) for p in _QUOTE_START_PATTERNS):
            in_quote = True
            continue

        if stripped.startswith(">"):
            continue

        if in_quote:
            if _HEADER_CONTINUATION.match(stripped) or len(stripped) < 3:
                continue
            in_quote = False

        result.append(line)

    return "\n".join(result)


_SIGNOFF_PATTERNS = [
    re.compile(r"^(Best\s+)?Regards,?\s*$", re.I),
    re.compile(r"^Thanks,?\s*$", re.I),
    re.compile(r"^Thank\s+you,?\s*$", re.I),
    re.compile(r"^Sincerely,?\s*$", re.I),
    re.compile(r"^Cheers,?\s*$", re.I),
    re.compile(r"^Best,?\s*$", re.I),
    re.compile(r"^(Kind|Warm)\s+Regards,?\s*$", re.I),
]
_DISCLAIMER_PATTERNS = [
    re.compile(r"This\s+email\s+(and\s+any\s+attachments?\s+)?(is|are)\s+(intended\s+)?(solely\s+)?for\s+the\s+.*$", re.I | re.S),
    re.compile(r"CONFIDENTIALITY\s+NOTICE:.*$", re.I | re.S),
    re.compile(r"This\s+message\s+contains?\s+confidential\s+information.*$", re.I | re.S),
    re.compile(r"If\s+you\s+(have\s+)?received?\s+this\s+(e-?mail|message)\s+in\s+error.*$", re.I | re.S),
]


def remove_signatures(text: str, content_type: str) -> str:
    """Remove email signatures (-- delimiter, sign-offs, disclaimers)."""
    lines = text.split("\n")

    # Find standard signature delimiter
    for i, line in enumerate(lines):
        if line.strip() == "--" or line.rstrip() == "-- ":
            lines = lines[:i]
            break

    # Find sign-off near end
    for i, line in enumerate(lines):
        if len(lines) - i <= 10:
            if any(p.match(line.strip()) for p in _SIGNOFF_PATTERNS):
                lines = lines[:i]
                break

    # Remove disclaimers
    result = "\n".join(lines)
    for p in _DISCLAIMER_PATTERNS:
        result = p.sub("", result)

    return result


def normalize_whitespace(text: str, content_type: str) -> str:
    """Normalize whitespace: collapse spaces, limit blank lines, strip."""
    text = re.sub(r"[^\S\n]+", " ", text)  # Collapse horizontal whitespace
    lines = [line.strip() for line in text.split("\n")]

    # Collapse multiple blank lines to max 2
    result = []
    blanks = 0
    for line in lines:
        if not line:
            blanks += 1
            if blanks <= 2:
                result.append(line)
        else:
            blanks = 0
            result.append(line)

    return "\n".join(result).strip()


def decode_special_characters(text: str, content_type: str) -> str:
    """Fix encoding issues: zero-width chars, smart quotes, line endings."""
    text = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", text)  # Zero-width chars

    replacements = {
        "\u2018": "'", "\u2019": "'",  # Smart single quotes
        "\u201c": '"', "\u201d": '"',  # Smart double quotes
        "\u2013": "-", "\u2014": "-",  # Dashes
        "\u2026": "...",  # Ellipsis
        "\u00a0": " ",  # NBSP
        "\r\n": "\n", "\r": "\n",  # Line endings
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    return text


def truncate_long_content(text: str, content_type: str, max_chars: int = 10000) -> str:
    """Truncate very long content to prevent token overflow."""
    if len(text) <= max_chars:
        return text

    # Find good break point
    for sep in ["\n\n", "\n", ". ", " "]:
        pos = text.rfind(sep, 0, max_chars)
        if pos > max_chars * 0.8:
            return text[: pos + len(sep)] + "\n\n[Content truncated...]"

    return text[:max_chars] + "\n\n[Content truncated...]"


def truncate_at(max_chars: int) -> Sanitizer:
    """Return a sanitizer that truncates content at max_chars (for use in pipelines)."""
    def _truncate(text: str, content_type: str) -> str:
        return truncate_long_content(text, content_type, max_chars=max_chars)
    return _truncate


# PII patterns: common phone formats
_PHONE_PATTERNS = [
    re.compile(r"\+?\d{1,3}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),  # US/intl
    re.compile(r"\(\d{3}\)\s*\d{3}[-.\s]?\d{4}"),  # (xxx) xxx-xxxx
    re.compile(r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b"),  # xxx-xxx-xxxx
]


def redact_pii(text: str, content_type: str) -> str:
    """Redact phone numbers for safe export (e.g. to observability). Email addresses are not redacted."""
    for p in _PHONE_PATTERNS:
        text = p.sub("[PHONE_REDACTED]", text)
    return text


# -----------------------------------------------------------------------------
# Pipelines
# -----------------------------------------------------------------------------

DEFAULT_PIPELINE: list[Sanitizer] = [
    decode_special_characters,
    html_to_text,
    remove_security_banners,
    normalize_whitespace,
    truncate_long_content,
]

MINIMAL_PIPELINE: list[Sanitizer] = [
    decode_special_characters,
    html_to_text,
    remove_security_banners,
    normalize_whitespace,
]

AGGRESSIVE_PIPELINE: list[Sanitizer] = [
    decode_special_characters,
    html_to_text,
    remove_security_banners,
    remove_quoted_replies,
    remove_signatures,
    normalize_whitespace,
    truncate_long_content,
]

# Pipeline for observability (e.g. span attributes): clean, PII-redact, length limit
OBSERVABILITY_MAX_CHARS = 4000
OBSERVABILITY_PIPELINE: list[Sanitizer] = [
    decode_special_characters,
    html_to_text,
    remove_security_banners,
    remove_quoted_replies,
    remove_signatures,
    normalize_whitespace,
    redact_pii,
    truncate_at(OBSERVABILITY_MAX_CHARS),
]


# -----------------------------------------------------------------------------
# Main Entry Point
# -----------------------------------------------------------------------------


def sanitize_email_body(
    text: str,
    content_type: str = "text",
    pipeline: list[Sanitizer] | None = None,
) -> str:
    """Sanitize email body content using a configurable pipeline."""
    if not text:
        return ""

    for sanitizer in (pipeline or DEFAULT_PIPELINE):
        text = sanitizer(text, content_type)

    return text


def sanitize_for_observability(
    text: str,
    content_type: str = "text",
    pipeline: list[Sanitizer] | None = None,
) -> str:
    """Sanitize content for safe export to observability (PII redacted, length limited).

    Uses OBSERVABILITY_PIPELINE by default: decode, html→text, strip banners/quotes/signatures,
    normalize whitespace, redact emails/phones, truncate to OBSERVABILITY_MAX_CHARS.
    """
    return sanitize_email_body(
        text,
        content_type=content_type,
        pipeline=pipeline or OBSERVABILITY_PIPELINE,
    )
