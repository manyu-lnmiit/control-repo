"""Minimal end-to-end example: wrap two tool functions with `guard()`, run a
few calls, then inspect and replay the resulting trace.

Run with:  python examples/basic_usage.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from agent_guardrail import (
    CostBudget,
    Policy,
    ReplayEngine,
    TraceRecorder,
    guard,
)


def main() -> None:
    policy = Policy.from_yaml("policies/example_policy.yaml")

    with tempfile.TemporaryDirectory() as tmp:
        trace_path = str(Path(tmp) / "session.jsonl")
        tracer = TraceRecorder(trace_path, session_id="demo-session")
        budget = CostBudget(max_total_cost=1.0)

        @guard(policy=policy, tracer=tracer, budget=budget)
        def search_web(query: str) -> str:
            return f"3 results for '{query}': example.com, docs.example.com, blog.example.com"

        @guard(policy=policy, tracer=tracer, budget=budget)
        def read_file(path: str) -> str:
            return f"contents of {path}"

        print(search_web(query="agentic AI orchestration"))
        print(read_file(path="/etc/hostname"))

        try:
            search_web(query="")  # violates minLength -> PolicyViolation
        except Exception as exc:  # noqa: BLE001
            print(f"blocked as expected: {exc}")

        print(f"\nbudget spent so far: {budget.spent:.4f} / {budget.max_total_cost}")

        print("\n--- trace ---")
        for event in tracer.events:
            print(f"[{event.call_id}] {event.decision} {event.tool_name}({event.arguments})")

        print("\n--- replay (allowed calls only) ---")
        replay = ReplayEngine(trace_path)
        replay.events = [e for e in replay.events if e.decision == "allowed"]
        while replay.has_next():
            next_event = replay.events[replay._cursor]  # noqa: SLF001
            output = replay.next_output(next_event.tool_name)
            print(f"replayed {next_event.tool_name} -> {output}")


if __name__ == "__main__":
    main()
