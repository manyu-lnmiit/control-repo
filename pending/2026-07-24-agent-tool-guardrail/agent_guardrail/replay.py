"""Deterministic replay of a recorded trace.

Given a JSONL trace file produced by `TraceRecorder`, `ReplayEngine` lets you
step through the exact sequence of tool calls an agent made, either to:

* re-serve recorded outputs to a mocked agent loop for fast, network-free
  regression tests, or
* assert that a *new* run of the agent calls the same tools with the same
  arguments in the same order as a known-good recorded run (drift
  detection).
"""

from __future__ import annotations

from typing import Any

from agent_guardrail.exceptions import ReplayMismatchError
from agent_guardrail.tracing import TraceEvent, TraceRecorder

__all__ = ["ReplayEngine", "ReplayMismatchError"]


class ReplayEngine:
    """Replays a recorded trace file call-by-call."""

    def __init__(self, trace_path: str):
        self.trace_path = trace_path
        self.events: list[TraceEvent] = TraceRecorder.load(trace_path)
        self._cursor = 0

    def __len__(self) -> int:
        return len(self.events)

    def reset(self) -> None:
        self._cursor = 0

    def has_next(self) -> bool:
        return self._cursor < len(self.events)

    def next_output(self, tool_name: str, arguments: dict[str, Any] | None = None) -> Any:
        """Return the recorded output for the next call, verifying it matches
        `tool_name` (and `arguments`, if provided) -- otherwise the live
        agent has diverged from the recorded session."""
        if not self.has_next():
            raise ReplayMismatchError(
                f"replay exhausted: no more recorded calls, but got a call to '{tool_name}'"
            )
        event = self.events[self._cursor]
        if event.tool_name != tool_name:
            raise ReplayMismatchError(
                f"step {self._cursor}: expected call to '{event.tool_name}', got '{tool_name}'"
            )
        if arguments is not None and event.arguments != arguments:
            raise ReplayMismatchError(
                f"step {self._cursor}: expected arguments {event.arguments} for "
                f"'{tool_name}', got {arguments}"
            )
        self._cursor += 1
        if event.decision == "denied":
            raise ReplayMismatchError(
                f"step {self._cursor - 1}: recorded call to '{tool_name}' was denied: {event.error}"
            )
        if event.decision == "error":
            raise ReplayMismatchError(
                f"step {self._cursor - 1}: recorded call to '{tool_name}' errored: {event.error}"
            )
        return event.output

    def make_mock_tool(self, tool_name: str):
        """Return a zero-argument-checking mock callable that, each time it
        is invoked, yields the next recorded output for `tool_name` in trace
        order. Useful for wiring a recorded session into a test double."""

        def _mock(*args, **kwargs):
            arguments = kwargs if not args else {"args": list(args), **kwargs}
            return self.next_output(tool_name, arguments if kwargs and not args else None)

        return _mock

    def assert_matches(self, calls: list[dict[str, Any]]) -> None:
        """Assert that a live list of `{"tool_name": ..., "arguments": ...}`
        calls exactly matches the recorded (allowed) trace, in order."""
        recorded = [e for e in self.events if e.decision == "allowed"]
        if len(calls) != len(recorded):
            raise ReplayMismatchError(
                f"expected {len(recorded)} calls, got {len(calls)}"
            )
        for i, (call, event) in enumerate(zip(calls, recorded, strict=True)):
            if call.get("tool_name") != event.tool_name:
                raise ReplayMismatchError(
                    f"step {i}: expected tool '{event.tool_name}', got '{call.get('tool_name')}'"
                )
            if call.get("arguments") != event.arguments:
                raise ReplayMismatchError(
                    f"step {i}: expected arguments {event.arguments} for "
                    f"'{event.tool_name}', got {call.get('arguments')}"
                )
