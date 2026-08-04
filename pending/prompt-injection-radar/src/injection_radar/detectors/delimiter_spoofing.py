"""Detects fake chat/control delimiters embedded inside untrusted content.

Tool outputs and retrieved documents should never legitimately contain
tokens like ``<|im_start|>``, ``[INST]``, or a fenced ` ```system ` block --
their presence usually means someone is trying to smuggle a fake turn
boundary into the context to make the model treat injected text as a new
system or assistant message.
"""

from __future__ import annotations

import re

from ..models import Finding

_DELIMITER_PATTERNS: list[tuple[re.Pattern, float, str]] = [
    (re.compile(r"<\|im_(start|end)\|>", re.IGNORECASE), 50.0, "chatml_delimiter"),
    (re.compile(r"\[/?(INST|SYS|SYSTEM)\]", re.IGNORECASE), 45.0, "llama_style_delimiter"),
    (re.compile(r"```\s*(system|assistant)\b", re.IGNORECASE), 40.0, "fenced_role_block"),
    (
        re.compile(r"^\s*(system|assistant)\s*:\s*", re.IGNORECASE | re.MULTILINE),
        25.0,
        "role_prefix_spoof",
    ),
    (re.compile(r"<<SYS>>|<</SYS>>"), 45.0, "sys_tag_spoof"),
    (re.compile(r"###\s*(system|instruction|override)\b", re.IGNORECASE), 30.0, "markdown_header_spoof"),
]


class DelimiterSpoofingDetector:
    """Flags fake role/control delimiters that don't belong in untrusted content."""

    name = "delimiter_spoofing"

    def scan(self, text: str) -> list[Finding]:
        findings: list[Finding] = []
        for pattern, severity, category in _DELIMITER_PATTERNS:
            for match in pattern.finditer(text):
                findings.append(
                    Finding(
                        detector=self.name,
                        category=category,
                        message=f"Untrusted content contains a fake control delimiter ({category}).",
                        span=match.span(),
                        matched_text=match.group(0),
                        severity=severity,
                    )
                )
        return findings
