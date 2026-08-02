"""Importance scoring for messages.

The compactor needs to decide *which* messages matter most when the
transcript no longer fits the token budget. Scoring is pluggable: implement
`ImportanceScorer` to encode domain-specific priorities (e.g. "boost anything
mentioning an order ID", "assistant tool-call results decay faster than user
turns").
"""

from __future__ import annotations

import re
from typing import Protocol

from context_compactor.models import Message


class ImportanceScorer(Protocol):
    """Anything that can assign each message a score, higher = keep longer."""

    def score(self, message: Message, *, position: int, total: int) -> float: ...


_ROLE_WEIGHTS = {
    "system": 1.0,
    "user": 0.75,
    "assistant": 0.6,
    "tool": 0.35,
}

_SIGNAL_PATTERN = re.compile(
    r"\b(error|fail|exception|important|critical|must|deadline|decision|"
    r"todo|action item|remember|note:)\b",
    re.IGNORECASE,
)


class DefaultImportanceScorer:
    """A sensible default: blends recency, role weight, and keyword signals.

    score = recency_weight * recency + role_weight * role_score + keyword_boost

    - recency: linear ramp from 0 (oldest) to 1 (newest) over the transcript.
    - role_score: system > user > assistant > tool, since system/user turns
      typically carry more durable intent than intermediate tool chatter.
    - keyword_boost: a flat bump when the content matches common
      "this matters" signal words (errors, decisions, TODOs, etc).
    """

    def __init__(
        self,
        recency_weight: float = 0.5,
        role_weight: float = 0.35,
        keyword_boost: float = 0.25,
    ) -> None:
        self.recency_weight = recency_weight
        self.role_weight = role_weight
        self.keyword_boost = keyword_boost

    def score(self, message: Message, *, position: int, total: int) -> float:
        if message.importance is not None:
            return message.importance

        recency = position / max(1, total - 1) if total > 1 else 1.0
        role_score = _ROLE_WEIGHTS.get(message.role, 0.5)

        score = self.recency_weight * recency + self.role_weight * role_score

        if _SIGNAL_PATTERN.search(message.content or ""):
            score += self.keyword_boost

        # Very short messages ("ok", "thanks") rarely carry much information.
        if message.content and len(message.content.strip()) < 12:
            score *= 0.7

        return score
