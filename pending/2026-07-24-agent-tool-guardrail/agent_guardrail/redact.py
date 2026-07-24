"""Lightweight, dependency-free PII redaction for tool outputs.

This is intentionally a set of high-precision regexes for common PII shapes
(email, phone, SSN-like, credit-card-like, IPv4). It is a pragmatic
defense-in-depth layer for demo/portfolio purposes -- not a substitute for a
dedicated DLP system in a real production deployment (see README
Limitations).
"""

from __future__ import annotations

import re
from typing import Any

_PATTERNS = {
    "EMAIL": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
    "PHONE": re.compile(r"(?<!\d)(\+?\d{1,2}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)"),
    "SSN": re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)"),
    "CREDIT_CARD": re.compile(r"(?<!\d)(?:\d[ -]?){13,16}(?!\d)"),
    "IPV4": re.compile(r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?!\d)"),
}


def redact_text(text: str) -> str:
    """Replace any recognized PII substrings in `text` with `[REDACTED:TYPE]`."""
    result = text
    for label, pattern in _PATTERNS.items():
        result = pattern.sub(f"[REDACTED:{label}]", result)
    return result


def redact_pii(value: Any) -> Any:
    """Recursively redact PII from strings nested in dicts/lists/tuples.

    Non-string, non-container values are returned unchanged.
    """
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {k: redact_pii(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_pii(v) for v in value]
    if isinstance(value, tuple):
        return tuple(redact_pii(v) for v in value)
    return value
