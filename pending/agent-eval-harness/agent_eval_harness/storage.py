"""Persistence for suite run results, enabling regression comparisons across runs."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent_eval_harness.runner import RunResult, SuiteRunResult


@dataclass
class StoredRun:
    """A single persisted run record: metadata plus the raw suite results."""

    run_id: str
    suite_name: str
    timestamp: str
    agent_label: str
    pass_rate: float
    weighted_score: float
    results: list[dict[str, Any]]


class ResultStore:
    """Append-only JSON-lines store of past suite runs, keyed by ``run_id``.

    Each line in the backing file is one JSON object describing a single run. This keeps
    the store simple to inspect, diff, and version-control, while still supporting fast
    lookups for regression comparisons.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.touch()

    def save(
        self,
        suite_result: SuiteRunResult,
        run_id: str | None = None,
        agent_label: str = "unknown",
        timestamp: str | None = None,
    ) -> StoredRun:
        """Append ``suite_result`` to the store and return the record that was written."""
        run_id = run_id or f"{suite_result.suite_name}-{_now_iso()}"
        record = StoredRun(
            run_id=run_id,
            suite_name=suite_result.suite_name,
            timestamp=timestamp or _now_iso(),
            agent_label=agent_label,
            pass_rate=suite_result.pass_rate,
            weighted_score=suite_result.weighted_score,
            results=suite_result.to_dict()["results"],
        )
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(record)) + "\n")
        return record

    def load_all(self) -> list[StoredRun]:
        """Return every stored run, oldest first."""
        runs: list[StoredRun] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            runs.append(StoredRun(**data))
        return runs

    def latest(self, suite_name: str | None = None) -> StoredRun | None:
        """Return the most recently saved run, optionally filtered to a given suite name."""
        runs = self.load_all()
        if suite_name:
            runs = [r for r in runs if r.suite_name == suite_name]
        return runs[-1] if runs else None

    def previous(self, suite_name: str | None = None) -> StoredRun | None:
        """Return the second-most-recent run (the baseline to compare the latest against)."""
        runs = self.load_all()
        if suite_name:
            runs = [r for r in runs if r.suite_name == suite_name]
        return runs[-2] if len(runs) >= 2 else None


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def result_to_dict(result: RunResult) -> dict[str, Any]:
    """Small helper used by callers that want a single run result as a plain dict."""
    return {
        "task_id": result.task_id,
        "output": result.output,
        "score": result.score,
        "passed": result.passed,
        "latency_s": result.latency_s,
        "error": result.error,
    }
