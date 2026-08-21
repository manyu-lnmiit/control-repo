"""Level-synchronous executor for compiled agent workflow graphs.

Execution proceeds in rounds ("supersteps"). Every node in the current
frontier runs concurrently (via a thread pool, since agent nodes are
typically I/O-bound LLM/tool calls); their state updates are merged; then the
next frontier is computed as the union of each executed node's successors.
Fan-out (parallel edges) and fan-in (multiple branches converging on the same
downstream node) both fall out naturally from this: convergent branches
collapse into a single set entry, so the shared downstream node runs once per
round it is reached in.

Known limitation: if parallel branches have different lengths, they can
reach a shared downstream node in different rounds, which would run that
node more than once. Keep parallel branches roughly the same length, or
make downstream aggregator nodes idempotent, to avoid surprises.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from .errors import MaxStepsExceededError, NodeExecutionError
from .graph import END, CompiledGraph


@dataclass
class NodeTrace:
    """Record of a single node execution, for observability/debugging."""

    step: int
    node: str
    duration_ms: float
    updates: dict[str, Any]
    error: str | None = None
    attempts: int = 1


@dataclass
class ExecutionResult:
    """Outcome of a full graph run."""

    final_state: dict[str, Any]
    trace: list[NodeTrace] = field(default_factory=list)
    steps: int = 0
    completed: bool = False


class Executor:
    """Runs a :class:`~agentworkflow.graph.CompiledGraph` to completion."""

    def __init__(self, graph: CompiledGraph, *, max_steps: int = 100, max_workers: int = 8) -> None:
        self.graph = graph
        self.max_steps = max_steps
        self.max_workers = max_workers

    def run(self, initial_state: dict[str, Any] | None = None) -> ExecutionResult:
        state: dict[str, Any] = dict(initial_state or {})
        trace: list[NodeTrace] = []
        frontier = [n for n in self.graph.entry_targets() if n != END]
        step = 0

        while frontier:
            step += 1
            if step > self.max_steps:
                raise MaxStepsExceededError(
                    f"execution exceeded max_steps={self.max_steps}; "
                    "this usually means a conditional loop never satisfies its exit condition"
                )

            # Dedup while preserving deterministic order.
            frontier = list(dict.fromkeys(frontier))
            results = self._run_round(frontier, state, step, trace)

            for updates in results:
                state = self._merge(state, updates)

            next_frontier: list[str] = []
            seen = set()
            for node_name in frontier:
                for nxt in self.graph.resolve_next(node_name, state):
                    if nxt == END:
                        continue
                    if nxt not in seen:
                        seen.add(nxt)
                        next_frontier.append(nxt)
            frontier = next_frontier

        return ExecutionResult(final_state=state, trace=trace, steps=step, completed=True)

    def _run_round(
        self,
        frontier: list[str],
        state: dict[str, Any],
        step: int,
        trace: list[NodeTrace],
    ) -> list[dict[str, Any]]:
        if len(frontier) == 1:
            updates, node_trace = self._run_node(frontier[0], state, step)
            trace.append(node_trace)
            return [updates]

        results: list[dict[str, Any]] = [{} for _ in frontier]
        traces: list[NodeTrace | None] = [None] * len(frontier)
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(frontier))) as pool:
            futures = {pool.submit(self._run_node, name, state, step): i for i, name in enumerate(frontier)}
            for fut in futures:
                i = futures[fut]
                updates, node_trace = fut.result()
                results[i] = updates
                traces[i] = node_trace
        trace.extend(t for t in traces if t is not None)
        return results

    def _run_node(self, name: str, state: dict[str, Any], step: int) -> tuple:
        node = self.graph.nodes[name]
        attempts = 0
        last_exc: BaseException | None = None
        start = time.monotonic()
        while attempts <= node.retries:
            attempts += 1
            try:
                result = node.fn(dict(state))
                duration_ms = (time.monotonic() - start) * 1000
                return result or {}, NodeTrace(
                    step=step, node=name, duration_ms=duration_ms, updates=result or {}, attempts=attempts
                )
            except Exception as exc:  # noqa: BLE001 - intentionally broad, re-raised via NodeExecutionError
                last_exc = exc
                if attempts <= node.retries and node.retry_delay > 0:
                    time.sleep(node.retry_delay)
        if last_exc is None:  # pragma: no cover - defensive, should be unreachable
            raise RuntimeError(f"node '{name}' failed with no exception captured")
        raise NodeExecutionError(name, last_exc) from last_exc

    def _merge(self, state: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
        if not updates:
            return state
        merged = dict(state)
        for key, value in updates.items():
            reducer = self.graph.reducers.get(key)
            if reducer is not None and key in merged:
                merged[key] = reducer(merged[key], value)
            else:
                merged[key] = value
        return merged
