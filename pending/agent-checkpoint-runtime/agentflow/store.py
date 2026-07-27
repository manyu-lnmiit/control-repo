"""Persistence layer for agentflow workflow runs.

The runtime is storage-agnostic: :class:`Store` defines the interface that
:class:`agentflow.core.Workflow` relies on, and :class:`SQLiteStore` is the
bundled implementation backed by a local SQLite database file (or an
in-memory database for tests). A custom backend (Postgres, Redis, ...) can
be plugged in by implementing the same interface.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class StepRecord:
    run_id: str
    step_name: str
    status: str  # "running" | "completed" | "failed"
    attempts: int
    result: Any = None
    error: str | None = None
    updated_at: float = 0.0


@dataclass
class RunRecord:
    run_id: str
    workflow_name: str
    status: str  # "running" | "completed" | "failed" | "waiting"
    result: Any = None
    error: str | None = None
    waiting_gate: str | None = None
    created_at: float = 0.0
    updated_at: float = 0.0


class Store(ABC):
    """Abstract persistence interface used by :class:`agentflow.core.Workflow`."""

    @abstractmethod
    def ensure_run(self, run_id: str, workflow_name: str) -> None: ...

    @abstractmethod
    def get_run(self, run_id: str) -> RunRecord | None: ...

    @abstractmethod
    def list_runs(self) -> list[RunRecord]: ...

    @abstractmethod
    def mark_run_completed(self, run_id: str, result: Any) -> None: ...

    @abstractmethod
    def mark_run_failed(self, run_id: str, error: str) -> None: ...

    @abstractmethod
    def mark_run_waiting(self, run_id: str, gate_name: str) -> None: ...

    @abstractmethod
    def get_step(self, run_id: str, step_name: str) -> StepRecord | None: ...

    @abstractmethod
    def list_steps(self, run_id: str) -> list[StepRecord]: ...

    @abstractmethod
    def mark_running(self, run_id: str, step_name: str, attempt: int) -> None: ...

    @abstractmethod
    def mark_completed(
        self, run_id: str, step_name: str, result: Any, attempt: int
    ) -> None: ...

    @abstractmethod
    def mark_failed(
        self, run_id: str, step_name: str, error: str, attempt: int
    ) -> None: ...

    @abstractmethod
    def get_gate(self, run_id: str, gate_name: str) -> str | None: ...

    @abstractmethod
    def request_gate(self, run_id: str, gate_name: str) -> None: ...

    @abstractmethod
    def approve_gate(self, run_id: str, gate_name: str, note: str = "") -> None: ...


_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    workflow_name TEXT NOT NULL,
    status TEXT NOT NULL,
    result TEXT,
    error TEXT,
    waiting_gate TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS steps (
    run_id TEXT NOT NULL,
    step_name TEXT NOT NULL,
    status TEXT NOT NULL,
    attempts INTEGER NOT NULL,
    result TEXT,
    error TEXT,
    updated_at REAL NOT NULL,
    PRIMARY KEY (run_id, step_name)
);

CREATE TABLE IF NOT EXISTS gates (
    run_id TEXT NOT NULL,
    gate_name TEXT NOT NULL,
    status TEXT NOT NULL,
    note TEXT,
    updated_at REAL NOT NULL,
    PRIMARY KEY (run_id, gate_name)
);
"""


class SQLiteStore(Store):
    """SQLite-backed :class:`Store` implementation.

    Safe to share across threads within a single process (guarded by an
    internal lock); each connection uses ``check_same_thread=False`` and
    WAL journaling for reasonable concurrent read performance.
    """

    def __init__(self, path: str = "agentflow.db"):
        self.path = path
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # -- runs ---------------------------------------------------------

    def ensure_run(self, run_id: str, workflow_name: str) -> None:
        with self._lock:
            now = time.time()
            self._conn.execute(
                """INSERT OR IGNORE INTO runs
                   (run_id, workflow_name, status, result, error, waiting_gate,
                    created_at, updated_at)
                   VALUES (?, ?, 'running', NULL, NULL, NULL, ?, ?)""",
                (run_id, workflow_name, now, now),
            )
            # a resumed run goes back to "running" status
            self._conn.execute(
                """UPDATE runs SET status='running', waiting_gate=NULL, updated_at=?
                   WHERE run_id=? AND status IN ('waiting', 'failed')""",
                (now, run_id),
            )
            self._conn.commit()

    def get_run(self, run_id: str) -> RunRecord | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM runs WHERE run_id=?", (run_id,)
            ).fetchone()
        if row is None:
            return None
        return self._row_to_run(row)

    def list_runs(self) -> list[RunRecord]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM runs ORDER BY created_at DESC"
            ).fetchall()
        return [self._row_to_run(r) for r in rows]

    def mark_run_completed(self, run_id: str, result: Any) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE runs SET status='completed', result=?, error=NULL, "
                "waiting_gate=NULL, updated_at=? WHERE run_id=?",
                (_dumps(result), time.time(), run_id),
            )
            self._conn.commit()

    def mark_run_failed(self, run_id: str, error: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE runs SET status='failed', error=?, waiting_gate=NULL, "
                "updated_at=? WHERE run_id=?",
                (error, time.time(), run_id),
            )
            self._conn.commit()

    def mark_run_waiting(self, run_id: str, gate_name: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE runs SET status='waiting', waiting_gate=?, updated_at=? "
                "WHERE run_id=?",
                (gate_name, time.time(), run_id),
            )
            self._conn.commit()

    # -- steps --------------------------------------------------------

    def get_step(self, run_id: str, step_name: str) -> StepRecord | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM steps WHERE run_id=? AND step_name=?",
                (run_id, step_name),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_step(row)

    def list_steps(self, run_id: str) -> list[StepRecord]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM steps WHERE run_id=? ORDER BY updated_at ASC",
                (run_id,),
            ).fetchall()
        return [self._row_to_step(r) for r in rows]

    def mark_running(self, run_id: str, step_name: str, attempt: int) -> None:
        with self._lock:
            self._conn.execute(
                """INSERT INTO steps (run_id, step_name, status, attempts,
                                       result, error, updated_at)
                   VALUES (?, ?, 'running', ?, NULL, NULL, ?)
                   ON CONFLICT(run_id, step_name) DO UPDATE SET
                       status='running', attempts=excluded.attempts,
                       updated_at=excluded.updated_at""",
                (run_id, step_name, attempt, time.time()),
            )
            self._conn.commit()

    def mark_completed(
        self, run_id: str, step_name: str, result: Any, attempt: int
    ) -> None:
        with self._lock:
            self._conn.execute(
                """UPDATE steps SET status='completed', attempts=?, result=?,
                       error=NULL, updated_at=?
                   WHERE run_id=? AND step_name=?""",
                (attempt, _dumps(result), time.time(), run_id, step_name),
            )
            self._conn.commit()

    def mark_failed(
        self, run_id: str, step_name: str, error: str, attempt: int
    ) -> None:
        with self._lock:
            self._conn.execute(
                """UPDATE steps SET status='failed', attempts=?, error=?,
                       updated_at=?
                   WHERE run_id=? AND step_name=?""",
                (attempt, error, time.time(), run_id, step_name),
            )
            self._conn.commit()

    # -- gates ----------------------------------------------------------

    def get_gate(self, run_id: str, gate_name: str) -> str | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT status FROM gates WHERE run_id=? AND gate_name=?",
                (run_id, gate_name),
            ).fetchone()
        return row[0] if row else None

    def request_gate(self, run_id: str, gate_name: str) -> None:
        with self._lock:
            self._conn.execute(
                """INSERT INTO gates (run_id, gate_name, status, note, updated_at)
                   VALUES (?, ?, 'pending', NULL, ?)
                   ON CONFLICT(run_id, gate_name) DO NOTHING""",
                (run_id, gate_name, time.time()),
            )
            self._conn.commit()

    def approve_gate(self, run_id: str, gate_name: str, note: str = "") -> None:
        with self._lock:
            self._conn.execute(
                """INSERT INTO gates (run_id, gate_name, status, note, updated_at)
                   VALUES (?, ?, 'approved', ?, ?)
                   ON CONFLICT(run_id, gate_name) DO UPDATE SET
                       status='approved', note=excluded.note,
                       updated_at=excluded.updated_at""",
                (run_id, gate_name, note, time.time()),
            )
            self._conn.commit()

    # -- helpers ----------------------------------------------------------

    @staticmethod
    def _row_to_run(row) -> RunRecord:
        (
            run_id,
            workflow_name,
            status,
            result,
            error,
            waiting_gate,
            created_at,
            updated_at,
        ) = row
        return RunRecord(
            run_id=run_id,
            workflow_name=workflow_name,
            status=status,
            result=_loads(result),
            error=error,
            waiting_gate=waiting_gate,
            created_at=created_at,
            updated_at=updated_at,
        )

    @staticmethod
    def _row_to_step(row) -> StepRecord:
        run_id, step_name, status, attempts, result, error, updated_at = row
        return StepRecord(
            run_id=run_id,
            step_name=step_name,
            status=status,
            attempts=attempts,
            result=_loads(result),
            error=error,
            updated_at=updated_at,
        )


def _dumps(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value)


def _loads(value: str | None) -> Any:
    if value is None:
        return None
    return json.loads(value)
