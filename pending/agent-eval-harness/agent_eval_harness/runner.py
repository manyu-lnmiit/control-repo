"""Execution engine: runs an agent against a task suite and collects results."""

from __future__ import annotations

import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from agent_eval_harness.scorers import ScoreResult, build_scorer
from agent_eval_harness.task import Task, TaskSuite


@runtime_checkable
class AgentRunner(Protocol):
    """Interface an agent-under-test must satisfy: a single callable ``run(prompt) -> output``."""

    def run(self, prompt: str) -> Any:
        ...


@dataclass
class RunResult:
    """The outcome of running a single :class:`Task` against an agent."""

    task_id: str
    output: Any
    score_result: ScoreResult | None
    latency_s: float
    error: str | None = None

    @property
    def passed(self) -> bool:
        return bool(self.score_result and self.score_result.passed) and self.error is None

    @property
    def score(self) -> float:
        return self.score_result.score if self.score_result else 0.0


@dataclass
class SuiteRunResult:
    """The aggregate outcome of running a full :class:`TaskSuite`."""

    suite_name: str
    results: list[RunResult] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        if not self.results:
            return 0.0
        return sum(1 for r in self.results if r.passed) / len(self.results)

    @property
    def weighted_score(self) -> float:
        """Weighted-average score across tasks, weighted by ``Task.weight``."""
        if not self._weights:
            return 0.0
        total_weight = sum(self._weights.values())
        if total_weight == 0:
            return 0.0
        return sum(r.score * self._weights.get(r.task_id, 1.0) for r in self.results) / total_weight

    _weights: dict[str, float] = field(default_factory=dict, repr=False)

    def by_id(self, task_id: str) -> RunResult | None:
        return next((r for r in self.results if r.task_id == task_id), None)

    def failed(self) -> list[RunResult]:
        return [r for r in self.results if not r.passed]

    def to_dict(self) -> dict[str, Any]:
        return {
            "suite_name": self.suite_name,
            "pass_rate": self.pass_rate,
            "weighted_score": self.weighted_score,
            "results": [
                {
                    "task_id": r.task_id,
                    "output": r.output,
                    "score": r.score,
                    "passed": r.passed,
                    "latency_s": r.latency_s,
                    "error": r.error,
                    "detail": r.score_result.detail if r.score_result else None,
                }
                for r in self.results
            ],
        }


def run_task(agent: AgentRunner, task: Task) -> RunResult:
    """Run a single task against ``agent`` and score the result.

    Any exception raised while calling the agent is captured and surfaced as a failing
    :class:`RunResult` rather than propagating, so one broken task cannot abort a whole suite.
    """
    scorer = build_scorer(task.scorer, **task.scorer_kwargs)
    start = time.monotonic()
    try:
        output = agent.run(task.prompt)
        latency = time.monotonic() - start
        score_result = scorer.score(output, task.expected)
        return RunResult(task_id=task.id, output=output, score_result=score_result, latency_s=latency)
    except Exception as exc:  # noqa: BLE001 - intentionally broad: isolate task failures
        latency = time.monotonic() - start
        return RunResult(
            task_id=task.id,
            output=None,
            score_result=None,
            latency_s=latency,
            error=f"{type(exc).__name__}: {exc}\n{traceback.format_exc(limit=3)}",
        )


def run_suite(agent: AgentRunner, suite: TaskSuite) -> SuiteRunResult:
    """Run every task in ``suite`` against ``agent`` sequentially and return aggregate results."""
    results = [run_task(agent, task) for task in suite.tasks]
    weights = {t.id: t.weight for t in suite.tasks}
    return SuiteRunResult(suite_name=suite.name, results=results, _weights=weights)
