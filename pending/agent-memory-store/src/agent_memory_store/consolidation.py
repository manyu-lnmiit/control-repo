"""Consolidation: turn clusters of related episodic memories into a single
distilled semantic memory, the same way biological memory consolidation
turns repeated/related experiences into general knowledge.

This module is intentionally extractive and LLM-free so the core package has
zero required dependencies. If an LLM is available, a caller can subclass or
monkeypatch ``summarize`` with an abstractive summarizer for higher-quality
consolidated memories.
"""

from __future__ import annotations

from dataclasses import dataclass

from .embeddings import cosine_similarity
from .memory import MemoryItem


@dataclass
class Cluster:
    items: list[MemoryItem]
    centroid: list[float]


def _average_vector(vectors: list[list[float]]) -> list[float]:
    if not vectors:
        return []
    dims = len(vectors[0])
    out = [0.0] * dims
    for v in vectors:
        for i in range(dims):
            out[i] += v[i]
    return [x / len(vectors) for x in out]


def cluster_by_similarity(items: list[MemoryItem], threshold: float = 0.75) -> list[Cluster]:
    """Greedily group items whose embeddings are similar to a cluster's
    running centroid. O(n * clusters) — fine for the modest local working
    sets this store targets; not intended for millions of items.
    """

    clusters: list[Cluster] = []
    for item in items:
        if not item.embedding:
            continue
        best_cluster = None
        best_sim = -1.0
        for cluster in clusters:
            sim = cosine_similarity(item.embedding, cluster.centroid)
            if sim > best_sim:
                best_sim = sim
                best_cluster = cluster
        if best_cluster is not None and best_sim >= threshold:
            best_cluster.items.append(item)
            best_cluster.centroid = _average_vector([m.embedding for m in best_cluster.items])
        else:
            clusters.append(Cluster(items=[item], centroid=list(item.embedding)))
    return clusters


def summarize(contents: list[str], max_len: int = 500) -> str:
    """Produce an extractive summary of a set of related memory contents.

    Deduplicates near-identical lines, joins the rest, and truncates to
    ``max_len`` characters. This keeps consolidation dependency-free; swap in
    an LLM-backed summarizer for richer output when one is available.
    """

    seen: set[str] = set()
    parts: list[str] = []
    for content in contents:
        key = content.strip().lower()
        if key and key not in seen:
            seen.add(key)
            parts.append(content.strip())

    joined = "; ".join(parts)
    if len(joined) > max_len:
        joined = joined[: max_len - 1].rstrip() + "…"
    return joined


def consolidate_cluster(cluster: Cluster) -> MemoryItem:
    """Build a new SEMANTIC MemoryItem summarizing an episodic cluster."""

    from .memory import MemoryType  # local import to avoid a cycle at module load

    summary_text = summarize([m.content for m in cluster.items])
    importance = max(m.importance for m in cluster.items)
    tags: list[str] = sorted({tag for m in cluster.items for tag in m.tags})
    source_ids = [m.id for m in cluster.items]

    return MemoryItem(
        content=f"Consolidated from {len(cluster.items)} memories: {summary_text}",
        memory_type=MemoryType.SEMANTIC,
        importance=min(1.0, importance + 0.05),
        tags=tags,
        metadata={"consolidated_from": source_ids, "source_count": len(cluster.items)},
        embedding=cluster.centroid,
    )
