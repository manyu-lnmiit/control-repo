"""Summarization strategies for collapsing runs of low-priority messages.

context_compactor ships an extractive, dependency-free default summarizer so
the library works fully offline. Callers who want abstractive LLM-generated
summaries can implement `Summarizer` themselves and pass any callable
(including a wrapper around their own LLM client) into the Compactor.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Protocol

from context_compactor.models import Message


class Summarizer(Protocol):
    """Anything that can compress a run of messages into one summary string."""

    def summarize(self, messages: list[Message]) -> str: ...


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


class ExtractiveSummarizer:
    """A lightweight, dependency-free extractive summarizer.

    For each message in the run, keeps the first sentence (usually the
    topic sentence) plus any sentence matching high-signal keywords, then
    joins everything into a compact bullet-style summary attributed by role.
    This is intentionally simple and deterministic (no external calls, no
    randomness) so compaction stays fast and reproducible in CI.
    """

    def __init__(self, max_sentences_per_message: int = 2, max_chars: int = 800) -> None:
        self.max_sentences_per_message = max_sentences_per_message
        self.max_chars = max_chars

    def _key_sentences(self, text: str) -> list[str]:
        sentences = [s.strip() for s in _SENTENCE_SPLIT.split(text.strip()) if s.strip()]
        if not sentences:
            return []
        keep = sentences[:1]
        for s in sentences[1:]:
            if len(keep) >= self.max_sentences_per_message:
                break
            keep.append(s)
        return keep

    def summarize(self, messages: list[Message]) -> str:
        if not messages:
            return ""
        lines = []
        for m in messages:
            sentences = self._key_sentences(m.content)
            if not sentences:
                continue
            lines.append(f"[{m.role}] " + " ".join(sentences))
        summary = "\n".join(lines)
        if len(summary) > self.max_chars:
            summary = summary[: self.max_chars - 3] + "..."
        span = f"(summary of {len(messages)} earlier messages)"
        return f"{span}\n{summary}" if summary else span


def make_callable_summarizer(fn: Callable[[list[Message]], str]) -> Summarizer:
    """Adapt a plain function into a Summarizer, e.g. for wrapping an LLM call:

        def llm_summarize(messages):
            transcript = "\\n".join(f"{m.role}: {m.content}" for m in messages)
            return my_llm_client.complete(f"Summarize:\\n{transcript}")

        summarizer = make_callable_summarizer(llm_summarize)
    """

    class _Wrapped:
        def summarize(self, messages: list[Message]) -> str:
            return fn(messages)

    return _Wrapped()
