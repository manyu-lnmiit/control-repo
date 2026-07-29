"""Core data types for agent-memory-store."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from enum import Enum


class MemoryType(str, Enum):
    """The two kinds of memory an agent can hold.

    EPISODIC memories are individual events/observations ("user said X at
    turn 12"). SEMANTIC memories are distilled, general facts, typically
    produced by consolidating many episodic memories together.
    """

    EPISODIC = "episodic"
    SEMANTIC = "semantic"


# Default half-life (in seconds) used when computing exponential decay of a
# memory's importance if the caller does not override it. Semantic memories
# are considered more durable than raw episodic ones.
DEFAULT_HALF_LIFE_SECONDS = {
    MemoryType.EPISODIC: 3 * 24 * 3600,  # 3 days
    MemoryType.SEMANTIC: 30 * 24 * 3600,  # 30 days
}


@dataclass
class MemoryItem:
    """A single unit of stored agent memory."""

    content: str
    memory_type: MemoryType = MemoryType.EPISODIC
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    importance: float = 0.5
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    embedding: list[float] = field(default_factory=list)
    created_at: float = 0.0
    last_accessed_at: float = 0.0
    access_count: int = 0
    half_life_seconds: float | None = None
    archived: bool = False

    def __post_init__(self) -> None:
        if self.half_life_seconds is None:
            self.half_life_seconds = DEFAULT_HALF_LIFE_SECONDS[MemoryType(self.memory_type)]

    def to_row(self) -> tuple:
        return (
            self.id,
            self.content,
            self.memory_type.value
            if isinstance(self.memory_type, MemoryType)
            else self.memory_type,
            self.importance,
            json.dumps(self.tags),
            json.dumps(self.metadata),
            json.dumps(self.embedding),
            self.created_at,
            self.last_accessed_at,
            self.access_count,
            self.half_life_seconds,
            int(self.archived),
        )

    @classmethod
    def from_row(cls, row: tuple) -> MemoryItem:
        (
            id_,
            content,
            memory_type,
            importance,
            tags,
            metadata,
            embedding,
            created_at,
            last_accessed_at,
            access_count,
            half_life_seconds,
            archived,
        ) = row
        return cls(
            id=id_,
            content=content,
            memory_type=MemoryType(memory_type),
            importance=importance,
            tags=json.loads(tags) if tags else [],
            metadata=json.loads(metadata) if metadata else {},
            embedding=json.loads(embedding) if embedding else [],
            created_at=created_at,
            last_accessed_at=last_accessed_at,
            access_count=access_count,
            half_life_seconds=half_life_seconds,
            archived=bool(archived),
        )
