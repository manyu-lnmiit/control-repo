"""Detects attempts to make the model leak data via crafted URLs/markdown.

A common attack against agents that can render markdown or fetch URLs: the
injected content asks the model to build a link or image whose query string
contains secrets, conversation history, or file contents, so that visiting
it (or an image auto-loading) exfiltrates data to an attacker-controlled
server.
"""

from __future__ import annotations

import re

from ..models import Finding

_MARKDOWN_LINK_OR_IMAGE = re.compile(r"!?\[[^\]]*\]\((https?://[^)\s]+)\)")

_EXFIL_KEYWORDS = re.compile(
    r"\b(api[_-]?key|secret|token|password|credentials?|conversation\s+history|"
    r"chat\s+history|system\s+prompt|internal\s+notes?)\b",
    re.IGNORECASE,
)

_INSTRUCT_TO_FETCH = re.compile(
    r"\b(fetch|visit|open|load|click|render|navigate\s+to)\b[^.\n]{0,60}\b(url|link|image)\b",
    re.IGNORECASE,
)


class ExfiltrationDetector:
    """Flags markdown links/images and instructions that look like data-exfil vectors."""

    name = "exfiltration"

    def scan(self, text: str) -> list[Finding]:
        findings: list[Finding] = []

        for match in _MARKDOWN_LINK_OR_IMAGE.finditer(text):
            url = match.group(1)
            severity = 20.0
            reasons = []
            context_before = text[max(0, match.start() - 60) : match.start()]
            if _EXFIL_KEYWORDS.search(url) or _EXFIL_KEYWORDS.search(context_before):
                severity += 35.0
                reasons.append("nearby reference to sensitive data")
            if len(url) > 120:
                severity += 10.0
                reasons.append("unusually long URL / query string")
            if reasons:
                findings.append(
                    Finding(
                        detector=self.name,
                        category="markdown_exfil_link",
                        message="Markdown link/image looks like a data-exfiltration vector: "
                        + ", ".join(reasons)
                        + ".",
                        span=match.span(),
                        matched_text=match.group(0)[:120],
                        severity=min(severity, 70.0),
                    )
                )

        for match in _INSTRUCT_TO_FETCH.finditer(text):
            findings.append(
                Finding(
                    detector=self.name,
                    category="instructed_fetch",
                    message="Text instructs the reader/agent to fetch or render an external URL.",
                    span=match.span(),
                    matched_text=match.group(0),
                    severity=20.0,
                )
            )

        return findings
