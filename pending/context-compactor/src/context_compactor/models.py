"""Core data models used throughout context_compactor."""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

_id_counter = itertools.count()


class Role(str, Enum):
    """Chat-style message roles. Extra/unknown roles are tolerated as plain strings."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class Message:
    """A single turn in an LLM conversation / agent transcript.

    Attributes:
        role: Who produced the message (system/user/assistant/tool/...).
        content: The raw text content of the message.
        index: Monotonically increasing position in the original transcript
            (assigned automatically if not supplied) — used for recency scoring
            and for producing stable, deterministic ordering after compaction.
        pinned: If True, this message is never evicted or summarized away.
            Typically used for the system prompt and other load-bearing turns.
        importance: Optional manual importance override in [0, 1]. When set,
            this bypasses the scorer's computed value.
        metadata: Free-form dict for caller-supplied context (tool name,
            timestamps, entity tags, etc.) that custom scorers can use.
        token_count: Cached token count; computed lazily by the tokenizer if
            left as None.
    """

    role: str
    content: str
    index: int = field(default_factory=lambda: next(_id_counter))
    pinned: bool = False
    importance: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    token_count: int | None = None

    def with_content(self, content: str, **overrides: Any) -> Message:
        """Return a copy of this message with new content (used when summarizing)."""
        data: dict[str, Any] = {
            "role": self.role,
            "content": content,
            "index": self.index,
            "pinned": self.pinned,
            "importance": self.importance,
            "metadata": dict(self.metadata),
            "token_count": None,
        }
        data.update(overrides)
        return Message(
            role=data["role"],
            content=data["content"],
            index=data["index"],
            pinned=data["pinned"],
            importance=data["importance"],
            metadata=data["metadata"],
            token_count=data["token_count"],
        )


@dataclass
class CompactionStats:
    """Summary statistics describing what a compaction run did."""

    input_messages: int
    output_messages: int
    input_tokens: int
    output_tokens: int
    dropped_messages: int
    summarized_messages: int
    summary_blocks_created: int

    @property
    def tokens_saved(self) -> int:
        return max(0, self.input_tokens - self.output_tokens)

    @property
    def compression_ratio(self) -> float:
        if self.input_tokens == 0:
            return 1.0
        return self.output_tokens / self.input_tokens


@dataclass
class CompactionResult:
    """The output of a `Compactor.compact()` call."""

    messages: list[Message]
    stats: CompactionStats

    def as_chat_messages(self) -> list[dict[str, str]]:
        """Convert to the plain {role, content} dicts most chat APIs expect."""
        return [{"role": m.role, "content": m.content} for m in self.messages]
