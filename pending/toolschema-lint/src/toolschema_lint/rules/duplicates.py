"""Corpus-level rules: checks that require comparing every tool against
every other tool, rather than looking at one tool in isolation.

The flagship rule here, ``overlapping-tool-purpose``, is aimed at a very
concrete agent failure mode: when two tools have near-identical names or
descriptions, the model has no reliable signal for which one to call, and
production agents end up calling the wrong one (or alternating
non-deterministically). We detect this with a dependency-free token-Jaccard
similarity over the name+description text -- no embeddings required.
"""

from __future__ import annotations

import re
from itertools import combinations

from toolschema_lint.models import Finding, Severity, ToolSchema
from toolschema_lint.rules.base import CorpusRule

_WORD_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "a",
    "an",
    "the",
    "to",
    "of",
    "for",
    "and",
    "or",
    "this",
    "that",
    "with",
    "is",
    "on",
    "in",
    "returns",
    "return",
    "tool",
    "function",
}

_SIMILARITY_THRESHOLD = 0.6


def _tokenize(text: str) -> set[str]:
    words = _WORD_RE.findall(text.lower())
    return {w for w in words if w not in _STOPWORDS}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


class DuplicateToolName(CorpusRule):
    id = "duplicate-tool-name"
    default_severity = Severity.ERROR
    description = "Two or more tools share the exact same name."

    def check_all(self, tools: list[ToolSchema]) -> list[Finding]:
        seen: dict[str, int] = {}
        findings = []
        for tool in tools:
            if tool.name in seen:
                findings.append(
                    Finding(
                        rule_id=self.id,
                        severity=self.default_severity,
                        message=(
                            f"Tool name {tool.name!r} is defined more than once; providers "
                            "will only see one of them (behavior is undefined/last-wins)."
                        ),
                        tool_name=tool.name,
                    )
                )
            else:
                seen[tool.name] = tool.source_index
        return findings


class OverlappingToolPurpose(CorpusRule):
    id = "overlapping-tool-purpose"
    default_severity = Severity.WARNING
    description = (
        "Two distinct tools have highly similar name+description text, making it hard "
        "for a model to reliably pick the right one."
    )

    def __init__(self, threshold: float = _SIMILARITY_THRESHOLD) -> None:
        self.threshold = threshold

    def check_all(self, tools: list[ToolSchema]) -> list[Finding]:
        findings = []
        token_sets = {
            tool.name: _tokenize(f"{tool.name} {tool.description or ''}") for tool in tools
        }
        for a, b in combinations(tools, 2):
            if a.name == b.name:
                continue  # duplicate-tool-name already covers exact-name collisions
            score = _jaccard(token_sets[a.name], token_sets[b.name])
            if score >= self.threshold:
                findings.append(
                    Finding(
                        rule_id=self.id,
                        severity=self.default_severity,
                        message=(
                            f"Tool {a.name!r} and {b.name!r} have {score:.0%} similar "
                            "name/description text; consider merging them or sharpening "
                            "each description to state when to use one over the other."
                        ),
                        tool_name=a.name,
                    )
                )
        return findings
