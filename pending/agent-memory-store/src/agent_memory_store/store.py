"""SQLite-backed memory store: the main entry point of the library."""

from __future__ import annotations

import sqlite3
import time
from contextlib import closing
from pathlib import Path

from .consolidation import cluster_by_similarity, consolidate_cluster
from .decay import decayed_importance, touch
from .embeddings import HashingVectorizer, cosine_similarity
from .memory import MemoryItem, MemoryType

_SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    memory_type TEXT NOT NULL,
    importance REAL NOT NULL,
    tags TEXT NOT NULL,
    metadata TEXT NOT NULL,
    embedding TEXT NOT NULL,
    created_at REAL NOT NULL,
    last_accessed_at REAL NOT NULL,
    access_count INTEGER NOT NULL,
    half_life_seconds REAL NOT NULL,
    archived INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type);
CREATE INDEX IF NOT EXISTS idx_memories_archived ON memories(archived);
"""


class MemoryStore:
    """Episodic + semantic long-term memory store for LLM agents.

    Parameters
    ----------
    db_path:
        Path to a SQLite file, or ``":memory:"`` for an ephemeral in-process
        store (the default — handy for tests and short-lived agent runs).
    vectorizer:
        Any object exposing ``embed(text) -> list[float]``. Defaults to the
        dependency-free :class:`~agent_memory_store.embeddings.HashingVectorizer`.
    clock:
        A zero-argument callable returning the current time as a float
        (unix epoch seconds by default). Overridable for deterministic tests.
    """

    def __init__(
        self,
        db_path: str | Path = ":memory:",
        vectorizer=None,
        clock=time.time,
    ) -> None:
        self.db_path = str(db_path)
        self.vectorizer = vectorizer or HashingVectorizer()
        self.clock = clock
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> MemoryStore:
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    # -- writes ----------------------------------------------------------

    def add(
        self,
        content: str,
        memory_type: MemoryType | str = MemoryType.EPISODIC,
        importance: float = 0.5,
        tags: list[str] | None = None,
        metadata: dict | None = None,
    ) -> MemoryItem:
        if not content or not content.strip():
            raise ValueError("content must be a non-empty string")
        if not 0.0 <= importance <= 1.0:
            raise ValueError("importance must be between 0 and 1")

        now = self.clock()
        item = MemoryItem(
            content=content,
            memory_type=MemoryType(memory_type),
            importance=importance,
            tags=tags or [],
            metadata=metadata or {},
            embedding=self.vectorizer.embed(content),
            created_at=now,
            last_accessed_at=now,
            access_count=0,
        )
        with closing(self._conn.cursor()) as cur:
            cur.execute(
                "INSERT INTO memories VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                item.to_row(),
            )
        self._conn.commit()
        return item

    def forget(self, memory_id: str) -> bool:
        with closing(self._conn.cursor()) as cur:
            cur.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            deleted = cur.rowcount > 0
        self._conn.commit()
        return deleted

    # -- reads -------------------------------------------------------------

    def get(self, memory_id: str) -> MemoryItem | None:
        with closing(self._conn.cursor()) as cur:
            cur.execute("SELECT * FROM memories WHERE id = ?", (memory_id,))
            row = cur.fetchone()
        return MemoryItem.from_row(row) if row else None

    def list(
        self,
        memory_type: MemoryType | str | None = None,
        include_archived: bool = False,
    ) -> list[MemoryItem]:
        query = "SELECT * FROM memories WHERE 1=1"
        params: list = []
        if memory_type is not None:
            query += " AND memory_type = ?"
            params.append(MemoryType(memory_type).value)
        if not include_archived:
            query += " AND archived = 0"
        query += " ORDER BY created_at DESC"
        with closing(self._conn.cursor()) as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
        return [MemoryItem.from_row(r) for r in rows]

    def search(
        self,
        query: str,
        k: int = 5,
        memory_type: MemoryType | str | None = None,
        similarity_weight: float = 0.6,
        importance_weight: float = 0.3,
        recency_weight: float = 0.1,
        touch_results: bool = True,
    ) -> list[tuple[MemoryItem, float]]:
        """Return the top-``k`` memories relevant to ``query``.

        Ranking blends three signals: embedding similarity to the query,
        decayed importance, and recency of last access. Retrieved items have
        their access stats refreshed (spaced-repetition style) unless
        ``touch_results`` is False.
        """

        if k <= 0:
            return []

        now = self.clock()
        query_vec = self.vectorizer.embed(query)
        candidates = self.list(memory_type=memory_type)
        if not candidates:
            return []

        oldest = min(c.created_at for c in candidates)
        newest = max(c.created_at for c in candidates)
        span = max(1e-9, newest - oldest)

        scored: list[tuple[MemoryItem, float]] = []
        for item in candidates:
            sim = cosine_similarity(query_vec, item.embedding)
            importance = decayed_importance(item, now)
            recency = (item.last_accessed_at - oldest) / span
            score = (
                similarity_weight * sim + importance_weight * importance + recency_weight * recency
            )
            scored.append((item, score))

        scored.sort(key=lambda pair: pair[1], reverse=True)
        top = scored[:k]

        if touch_results:
            for item, _ in top:
                touch(item, now)
                self._save(item)

        return top

    def stats(self) -> dict:
        with closing(self._conn.cursor()) as cur:
            cur.execute(
                "SELECT memory_type, COUNT(*), AVG(importance) FROM memories "
                "WHERE archived = 0 GROUP BY memory_type"
            )
            rows = cur.fetchall()
        by_type = {r[0]: {"count": r[1], "avg_importance": r[2]} for r in rows}
        total = sum(v["count"] for v in by_type.values())
        return {"total": total, "by_type": by_type}

    # -- maintenance -------------------------------------------------------

    def decay_all(self) -> int:
        """Recompute and persist decayed importance for every memory.

        Returns the number of memories updated.
        """

        now = self.clock()
        updated = 0
        for item in self.list(include_archived=False):
            new_importance = decayed_importance(item, now)
            if abs(new_importance - item.importance) > 1e-9:
                item.importance = new_importance
                self._save(item)
                updated += 1
        return updated

    def prune(self, threshold: float = 0.05) -> int:
        """Archive memories whose (decayed) importance has fallen below
        ``threshold``. Archived memories are excluded from search/list by
        default but are not physically deleted.
        """

        now = self.clock()
        archived = 0
        for item in self.list(include_archived=False):
            if decayed_importance(item, now) < threshold:
                item.archived = True
                self._save(item)
                archived += 1
        return archived

    def consolidate(
        self,
        similarity_threshold: float = 0.75,
        min_cluster_size: int = 3,
        archive_sources: bool = True,
    ) -> list[MemoryItem]:
        """Cluster related EPISODIC memories and distill each sufficiently
        large cluster into one new SEMANTIC memory.

        Returns the list of newly created semantic MemoryItems.
        """

        episodic = self.list(memory_type=MemoryType.EPISODIC)
        clusters = cluster_by_similarity(episodic, threshold=similarity_threshold)

        created: list[MemoryItem] = []
        for cluster in clusters:
            if len(cluster.items) < min_cluster_size:
                continue
            semantic_item = consolidate_cluster(cluster)
            semantic_item.created_at = self.clock()
            semantic_item.last_accessed_at = semantic_item.created_at
            with closing(self._conn.cursor()) as cur:
                cur.execute(
                    "INSERT INTO memories VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    semantic_item.to_row(),
                )
            created.append(semantic_item)

            if archive_sources:
                for source in cluster.items:
                    source.archived = True
                    self._save(source)

        self._conn.commit()
        return created

    # -- internal ------------------------------------------------------------

    def _save(self, item: MemoryItem) -> None:
        with closing(self._conn.cursor()) as cur:
            cur.execute(
                """
                UPDATE memories SET
                    content=?, memory_type=?, importance=?, tags=?, metadata=?,
                    embedding=?, created_at=?, last_accessed_at=?, access_count=?,
                    half_life_seconds=?, archived=?
                WHERE id=?
                """,
                (*item.to_row()[1:], item.id),
            )
        self._conn.commit()
