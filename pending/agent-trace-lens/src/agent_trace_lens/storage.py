"""Pluggable storage backends for spans. SQLite is the default, file-based backend."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Protocol

from agent_trace_lens.models import Span, SpanKind, SpanStatus, TraceSummary

_SCHEMA = """
CREATE TABLE IF NOT EXISTS spans (
    id TEXT PRIMARY KEY,
    trace_id TEXT NOT NULL,
    parent_id TEXT,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    start_time REAL NOT NULL,
    end_time REAL,
    status TEXT NOT NULL,
    error TEXT,
    attributes TEXT NOT NULL,
    tokens_in INTEGER,
    tokens_out INTEGER
);
CREATE INDEX IF NOT EXISTS idx_spans_trace_id ON spans (trace_id);
CREATE INDEX IF NOT EXISTS idx_spans_parent_id ON spans (parent_id);
"""


class StorageBackend(Protocol):
    """Interface any trace storage backend must implement."""

    def upsert_span(self, span: Span) -> None: ...

    def get_span(self, span_id: str) -> Span | None: ...

    def get_trace(self, trace_id: str) -> list[Span]: ...

    def list_traces(self, limit: int = 50) -> list[TraceSummary]: ...

    def delete_trace(self, trace_id: str) -> None: ...


class SQLiteStorage:
    """A minimal, dependency-free SQLite-backed span store.

    Safe for concurrent use from multiple threads within a single process; each
    thread gets its own connection via a thread-local cache.
    """

    def __init__(self, db_path: str | Path = "agent_trace_lens.db") -> None:
        self.db_path = str(db_path)
        self._local = threading.local()
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return conn

    def _init_schema(self) -> None:
        conn = self._connect()
        conn.executescript(_SCHEMA)
        conn.commit()

    def upsert_span(self, span: Span) -> None:
        conn = self._connect()
        conn.execute(
            """
            INSERT INTO spans (
                id, trace_id, parent_id, name, kind, start_time, end_time,
                status, error, attributes, tokens_in, tokens_out
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                end_time = excluded.end_time,
                status = excluded.status,
                error = excluded.error,
                attributes = excluded.attributes,
                tokens_in = excluded.tokens_in,
                tokens_out = excluded.tokens_out
            """,
            (
                span.id,
                span.trace_id,
                span.parent_id,
                span.name,
                span.kind.value,
                span.start_time,
                span.end_time,
                span.status.value,
                span.error,
                json.dumps(span.attributes),
                span.tokens_in,
                span.tokens_out,
            ),
        )
        conn.commit()

    def _row_to_span(self, row: sqlite3.Row) -> Span:
        return Span(
            id=row["id"],
            trace_id=row["trace_id"],
            parent_id=row["parent_id"],
            name=row["name"],
            kind=SpanKind(row["kind"]),
            start_time=row["start_time"],
            end_time=row["end_time"],
            status=SpanStatus(row["status"]),
            error=row["error"],
            attributes=json.loads(row["attributes"]) if row["attributes"] else {},
            tokens_in=row["tokens_in"],
            tokens_out=row["tokens_out"],
        )

    def get_span(self, span_id: str) -> Span | None:
        conn = self._connect()
        row = conn.execute("SELECT * FROM spans WHERE id = ?", (span_id,)).fetchone()
        return self._row_to_span(row) if row else None

    def get_trace(self, trace_id: str) -> list[Span]:
        conn = self._connect()
        rows = conn.execute(
            "SELECT * FROM spans WHERE trace_id = ? ORDER BY start_time ASC",
            (trace_id,),
        ).fetchall()
        return [self._row_to_span(r) for r in rows]

    def list_traces(self, limit: int = 50) -> list[TraceSummary]:
        conn = self._connect()
        rows = conn.execute(
            """
            SELECT
                trace_id,
                COUNT(*) AS span_count,
                MIN(start_time) AS start_time,
                MAX(COALESCE(end_time, start_time)) AS end_time,
                SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS error_count,
                COALESCE(SUM(tokens_in), 0) AS total_tokens_in,
                COALESCE(SUM(tokens_out), 0) AS total_tokens_out
            FROM spans
            GROUP BY trace_id
            ORDER BY start_time DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        summaries: list[TraceSummary] = []
        for row in rows:
            root = conn.execute(
                "SELECT name FROM spans WHERE trace_id = ? AND parent_id IS NULL LIMIT 1",
                (row["trace_id"],),
            ).fetchone()
            summaries.append(
                TraceSummary(
                    trace_id=row["trace_id"],
                    root_name=root["name"] if root else None,
                    span_count=row["span_count"],
                    start_time=row["start_time"],
                    end_time=row["end_time"],
                    error_count=row["error_count"],
                    total_tokens_in=row["total_tokens_in"],
                    total_tokens_out=row["total_tokens_out"],
                )
            )
        return summaries

    def delete_trace(self, trace_id: str) -> None:
        conn = self._connect()
        conn.execute("DELETE FROM spans WHERE trace_id = ?", (trace_id,))
        conn.commit()

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None
