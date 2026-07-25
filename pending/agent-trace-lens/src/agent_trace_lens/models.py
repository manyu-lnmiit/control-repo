"""Data models for spans and traces."""

from __future__ import annotations

import enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class SpanKind(str, enum.Enum):
    """The category of work a span represents."""

    AGENT = "agent"
    TOOL = "tool"
    LLM = "llm"
    CHAIN = "chain"
    CUSTOM = "custom"


class SpanStatus(str, enum.Enum):
    """Terminal status of a span."""

    OK = "ok"
    ERROR = "error"
    RUNNING = "running"


class Span(BaseModel):
    """A single unit of work inside a trace (an agent step, tool call, or LLM call)."""

    id: str
    trace_id: str
    parent_id: Optional[str] = None
    name: str
    kind: SpanKind = SpanKind.CUSTOM
    start_time: float
    end_time: Optional[float] = None
    status: SpanStatus = SpanStatus.RUNNING
    error: Optional[str] = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None

    @property
    def duration_ms(self) -> Optional[float]:
        """Wall-clock duration of the span in milliseconds, if it has finished."""
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time) * 1000.0


class TraceSummary(BaseModel):
    """Aggregate view of a trace used for list endpoints."""

    trace_id: str
    root_name: Optional[str] = None
    span_count: int
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    error_count: int = 0
    total_tokens_in: int = 0
    total_tokens_out: int = 0

    @property
    def duration_ms(self) -> Optional[float]:
        if self.start_time is None or self.end_time is None:
            return None
        return (self.end_time - self.start_time) * 1000.0
