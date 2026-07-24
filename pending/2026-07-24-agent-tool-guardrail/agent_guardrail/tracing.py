"""Durable JSONL tracing of tool calls.

Every guarded call produces a `TraceEvent` capturing the tool name,
arguments, decision (allowed/denied), output (or error), and timing. Traces
are appended to a JSONL file so a session can be reconstructed and replayed
later by `agent_guardrail.replay.ReplayEngine`.
"""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class TraceEvent:
    call_id: int
    tool_name: str
    arguments: dict[str, Any]
    decision: str  # "allowed" | "denied" | "error"
    output: Any = None
    error: str | None = None
    cost: float = 0.0
    duration_ms: float = 0.0
    started_at: float = 0.0
    session_id: str = "default"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TraceRecorder:
    """Appends `TraceEvent`s to a JSONL file (and keeps an in-memory copy for
    quick inspection). Thread-safe.
    """

    def __init__(self, path: str, session_id: str = "default"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.session_id = session_id
        self._lock = threading.Lock()
        self._events: list[TraceEvent] = []
        self._next_call_id = 0

    def next_call_id(self) -> int:
        with self._lock:
            call_id = self._next_call_id
            self._next_call_id += 1
            return call_id

    def record(self, event: TraceEvent) -> None:
        with self._lock:
            self._events.append(event)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(event.to_dict()) + "\n")

    @property
    def events(self) -> list[TraceEvent]:
        with self._lock:
            return list(self._events)

    @staticmethod
    def load(path: str) -> list[TraceEvent]:
        events: list[TraceEvent] = []
        p = Path(path)
        if not p.exists():
            return events
        with p.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                events.append(TraceEvent(**data))
        return events
