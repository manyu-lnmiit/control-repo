"""Detects language that tries to override, ignore, or bypass prior instructions.

This is the classic "ignore all previous instructions" family of attacks,
plus requests to reveal system prompts / hidden configuration, and attempts
to reassign the model a new persona that discards its guardrails.
"""

from __future__ import annotations

import re

from ..models import Finding

_OVERRIDE_PATTERNS: list[tuple[re.Pattern, float, str]] = [
    (
        re.compile(
            r"\b(ignore|disregard|forget|override)\b[^.\n]{0,40}\b"
            r"(previous|prior|above|earlier|all)\b[^.\n]{0,40}\b"
            r"(instructions?|prompts?|rules?|guidelines?|context)\b",
            re.IGNORECASE,
        ),
        45.0,
        "instruction_override",
    ),
    (
        re.compile(
            r"\byou\s+(are\s+now|must\s+now|will\s+now)\s+(act\s+as|behave\s+as|become)\b",
            re.IGNORECASE,
        ),
        35.0,
        "persona_reassignment",
    ),
    (
        re.compile(
            r"\b(reveal|print|show|leak|output|repeat)\b[^.\n]{0,30}\b"
            r"(system\s+prompt|hidden\s+instructions?|initial\s+prompt|"
            r"developer\s+message)\b",
            re.IGNORECASE,
        ),
        40.0,
        "system_prompt_exfiltration",
    ),
    (
        re.compile(
            r"\bnew\s+(instructions?|rules?|directive)\s*:\s",
            re.IGNORECASE,
        ),
        30.0,
        "injected_directive",
    ),
    (
        re.compile(
            r"\b(do\s+not|don't)\s+(tell|inform|mention\s+(this|it)\s+to)\s+"
            r"(the\s+)?(user|human)\b",
            re.IGNORECASE,
        ),
        35.0,
        "covert_channel",
    ),
    (
        re.compile(
            r"\byour\s+(real|true|actual)\s+(goal|task|purpose|instructions?)\s+"
            r"(is|are|now\s+is)\b",
            re.IGNORECASE,
        ),
        30.0,
        "goal_hijack",
    ),
    (
        re.compile(
            r"\b(jailbreak|dan\s+mode|developer\s+mode\s+enabled|no\s+restrictions?\s+"
            r"mode)\b",
            re.IGNORECASE,
        ),
        40.0,
        "jailbreak_keyword",
    ),
]


class InstructionOverrideDetector:
    """Flags phrases characteristic of instruction-override injection attacks."""

    name = "instruction_override"

    def scan(self, text: str) -> list[Finding]:
        findings: list[Finding] = []
        for pattern, severity, category in _OVERRIDE_PATTERNS:
            for match in pattern.finditer(text):
                findings.append(
                    Finding(
                        detector=self.name,
                        category=category,
                        message=f"Text resembles a known injection phrasing pattern ({category}).",
                        span=match.span(),
                        matched_text=match.group(0),
                        severity=severity,
                    )
                )
        return findings
