from agent_memory_store.consolidation import cluster_by_similarity, summarize
from agent_memory_store.embeddings import HashingVectorizer
from agent_memory_store.memory import MemoryItem, MemoryType


def make_item(content, vectorizer):
    item = MemoryItem(content=content, memory_type=MemoryType.EPISODIC)
    item.embedding = vectorizer.embed(content)
    return item


def test_cluster_groups_similar_items_together():
    v = HashingVectorizer(dims=128)
    items = [
        make_item("user prefers dark mode", v),
        make_item("user likes dark mode enabled", v),
        make_item("completely different topic about lunch", v),
    ]
    clusters = cluster_by_similarity(items, threshold=0.4)
    sizes = sorted(len(c.items) for c in clusters)
    assert sizes[-1] >= 2


def test_cluster_skips_items_without_embeddings():
    item = MemoryItem(content="no embedding here")
    item.embedding = []
    clusters = cluster_by_similarity([item], threshold=0.5)
    assert clusters == []


def test_cluster_empty_input():
    assert cluster_by_similarity([], threshold=0.5) == []


def test_summarize_deduplicates_and_joins():
    result = summarize(["hello world", "Hello World", "goodbye"])
    assert "goodbye" in result
    assert result.count("hello world") + result.lower().count("hello world") >= 1


def test_summarize_truncates_long_input():
    long_texts = [f"memory number {i} with some extra padding text" for i in range(50)]
    result = summarize(long_texts, max_len=100)
    assert len(result) <= 100
    assert result.endswith("…")


def test_summarize_empty_list_returns_empty_string():
    assert summarize([]) == ""
