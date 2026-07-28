"""SQLite-backed vector store with TTL expiry and LRU-by-size eviction.

The store is intentionally simple: embeddings are stored as JSON-encoded
float arrays and similarity search is a linear scan scored with cosine
similarity. This is the right tradeoff for a per-process / per-agent LLM
cache (thousands to low tens-of-thousands of entries) where an external
vector database would be operational overhead the use case doesn't need.
For workloads that outgrow a linear scan, swap in a dedicated vector index
behind the same ``VectorStore`` interface.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from semantic_cache.similarity import cosine_similarity

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cache_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    namespace TEXT NOT NULL,
    prompt TEXT NOT NULL,
    response TEXT NOT NULL,
    embedding TEXT NOT NULL,
    created_at REAL NOT NULL,
    expires_at REAL,
    last_accessed_at REAL NOT NULL,
    hit_count INTEGER NOT NULL DEFAULT 0,
    cost_estimate REAL NOT NULL DEFAULT 0.0
);
CREATE INDEX IF NOT EXISTS idx_cache_entries_namespace ON cache_entries(namespace);
"""


@dataclass
class CacheEntry:
    id: int
    namespace: str
    prompt: str
    response: str
    embedding: list[float]
    created_at: float
    expires_at: float | None
    last_accessed_at: float
    hit_count: int
    cost_estimate: float

    def is_expired(self, now: float) -> bool:
        return self.expires_at is not None and now >= self.expires_at


class VectorStore:
    """A minimal persistent store for (prompt, embedding, response) rows."""

    def __init__(self, path: str | Path = ":memory:", max_entries: int = 10_000) -> None:
        self._path = str(path)
        self._max_entries = max_entries
        self._conn = sqlite3.connect(self._path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> VectorStore:
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def put(
        self,
        namespace: str,
        prompt: str,
        response: str,
        embedding: list[float],
        ttl_seconds: float | None,
        now: float,
        cost_estimate: float = 0.0,
    ) -> int:
        expires_at = (now + ttl_seconds) if ttl_seconds is not None else None
        cursor = self._conn.execute(
            """
            INSERT INTO cache_entries
                (namespace, prompt, response, embedding, created_at, expires_at,
                 last_accessed_at, hit_count, cost_estimate)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)
            """,
            (namespace, prompt, response, json.dumps(embedding), now, expires_at, now, cost_estimate),
        )
        self._conn.commit()
        self._evict_if_needed(namespace)
        return int(cursor.lastrowid)

    def _evict_if_needed(self, namespace: str) -> None:
        (count,) = self._conn.execute(
            "SELECT COUNT(*) FROM cache_entries WHERE namespace = ?", (namespace,)
        ).fetchone()
        overflow = count - self._max_entries
        if overflow <= 0:
            return
        rows = self._conn.execute(
            """
            SELECT id FROM cache_entries WHERE namespace = ?
            ORDER BY last_accessed_at ASC LIMIT ?
            """,
            (namespace, overflow),
        ).fetchall()
        ids = [row["id"] for row in rows]
        if ids:
            placeholders = ",".join("?" for _ in ids)
            self._conn.execute(f"DELETE FROM cache_entries WHERE id IN ({placeholders})", ids)
            self._conn.commit()

    def purge_expired(self, now: float) -> int:
        cursor = self._conn.execute(
            "DELETE FROM cache_entries WHERE expires_at IS NOT NULL AND expires_at <= ?", (now,)
        )
        self._conn.commit()
        return cursor.rowcount

    def all_active(self, namespace: str, now: float) -> list[CacheEntry]:
        rows = self._conn.execute(
            "SELECT * FROM cache_entries WHERE namespace = ?", (namespace,)
        ).fetchall()
        entries = [self._row_to_entry(row) for row in rows]
        return [e for e in entries if not e.is_expired(now)]

    def touch(self, entry_id: int, now: float) -> None:
        self._conn.execute(
            """
            UPDATE cache_entries
            SET hit_count = hit_count + 1, last_accessed_at = ?
            WHERE id = ?
            """,
            (now, entry_id),
        )
        self._conn.commit()

    def clear(self, namespace: str | None = None) -> int:
        if namespace is None:
            cursor = self._conn.execute("DELETE FROM cache_entries")
        else:
            cursor = self._conn.execute("DELETE FROM cache_entries WHERE namespace = ?", (namespace,))
        self._conn.commit()
        return cursor.rowcount

    def stats(self, namespace: str | None = None) -> dict:
        if namespace is None:
            row = self._conn.execute(
                "SELECT COUNT(*) AS n, COALESCE(SUM(hit_count), 0) AS hits, "
                "COALESCE(SUM(hit_count * cost_estimate), 0.0) AS saved FROM cache_entries"
            ).fetchone()
        else:
            row = self._conn.execute(
                "SELECT COUNT(*) AS n, COALESCE(SUM(hit_count), 0) AS hits, "
                "COALESCE(SUM(hit_count * cost_estimate), 0.0) AS saved FROM cache_entries "
                "WHERE namespace = ?",
                (namespace,),
            ).fetchone()
        return {"entries": row["n"], "total_hits": row["hits"], "estimated_cost_saved": row["saved"]}

    def best_match(
        self, namespace: str, embedding: list[float], now: float
    ) -> tuple[CacheEntry, float] | None:
        best_entry: CacheEntry | None = None
        best_score = -1.0
        for entry in self.all_active(namespace, now):
            score = cosine_similarity(embedding, entry.embedding)
            if score > best_score:
                best_score = score
                best_entry = entry
        if best_entry is None:
            return None
        return best_entry, best_score

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> CacheEntry:
        return CacheEntry(
            id=row["id"],
            namespace=row["namespace"],
            prompt=row["prompt"],
            response=row["response"],
            embedding=json.loads(row["embedding"]),
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            last_accessed_at=row["last_accessed_at"],
            hit_count=row["hit_count"],
            cost_estimate=row["cost_estimate"],
        )
