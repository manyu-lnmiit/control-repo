import pytest

from agent_memory_store.memory import MemoryType
from agent_memory_store.store import MemoryStore


@pytest.fixture
def clock():
    state = {"t": 1_000_000.0}

    def now():
        return state["t"]

    now.state = state
    return now


@pytest.fixture
def store(clock):
    with MemoryStore(db_path=":memory:", clock=clock) as s:
        yield s


def test_add_returns_item_with_embedding_and_defaults(store):
    item = store.add("The user's favorite color is blue")
    assert item.id
    assert item.memory_type == MemoryType.EPISODIC
    assert item.importance == 0.5
    assert len(item.embedding) > 0


def test_add_rejects_empty_content(store):
    with pytest.raises(ValueError):
        store.add("   ")


def test_add_rejects_out_of_range_importance(store):
    with pytest.raises(ValueError):
        store.add("some content", importance=1.5)


def test_get_roundtrips(store):
    item = store.add("Remember to check the API rate limit", tags=["ops"])
    fetched = store.get(item.id)
    assert fetched is not None
    assert fetched.content == item.content
    assert fetched.tags == ["ops"]


def test_get_missing_returns_none(store):
    assert store.get("does-not-exist") is None


def test_forget_deletes_and_reports(store):
    item = store.add("temporary note")
    assert store.forget(item.id) is True
    assert store.get(item.id) is None
    assert store.forget(item.id) is False


def test_list_excludes_archived_by_default(store):
    a = store.add("memory a")
    store.add("memory b")
    a.archived = True
    store._save(a)

    results = store.list()
    ids = {m.id for m in results}
    assert a.id not in ids
    assert len(results) == 1

    all_results = store.list(include_archived=True)
    assert len(all_results) == 2


def test_list_filters_by_type(store):
    store.add("episodic one", memory_type=MemoryType.EPISODIC)
    store.add("semantic one", memory_type=MemoryType.SEMANTIC)

    episodic = store.list(memory_type=MemoryType.EPISODIC)
    assert len(episodic) == 1
    assert episodic[0].memory_type == MemoryType.EPISODIC


def test_search_ranks_relevant_memory_first(store):
    store.add("The user's favorite programming language is Python")
    store.add("Quarterly revenue increased twelve percent")
    store.add("The user enjoys hiking on weekends")

    results = store.search("what programming language does the user like", k=2)
    assert len(results) == 2
    top_item, top_score = results[0]
    assert "python" in top_item.content.lower() or "language" in top_item.content.lower()
    assert top_score >= results[1][1]


def test_search_empty_store_returns_empty(store):
    assert store.search("anything") == []


def test_search_touches_results(store, clock):
    item = store.add("A memory to be retrieved")
    clock.state["t"] += 10
    store.search("memory to be retrieved", k=1)

    fetched = store.get(item.id)
    assert fetched.access_count == 1
    assert fetched.last_accessed_at == clock.state["t"]


def test_search_respects_k(store):
    for i in range(5):
        store.add(f"note number {i}")
    results = store.search("note", k=2)
    assert len(results) == 2


def test_stats_counts_by_type(store):
    store.add("e1", memory_type=MemoryType.EPISODIC)
    store.add("e2", memory_type=MemoryType.EPISODIC)
    store.add("s1", memory_type=MemoryType.SEMANTIC)

    stats = store.stats()
    assert stats["total"] == 3
    assert stats["by_type"]["episodic"]["count"] == 2
    assert stats["by_type"]["semantic"]["count"] == 1


def test_decay_all_reduces_importance_over_time(store, clock):
    item = store.add("aging memory", importance=0.9)
    clock.state["t"] += 10 * 24 * 3600  # 10 days, well past the 3-day episodic half-life

    updated = store.decay_all()
    assert updated == 1
    fetched = store.get(item.id)
    assert fetched.importance < 0.9


def test_prune_archives_low_importance_memories(store, clock):
    item = store.add("fading memory", importance=0.1)
    clock.state["t"] += 30 * 24 * 3600  # well past several half-lives

    archived = store.prune(threshold=0.05)
    assert archived == 1
    assert store.get(item.id).archived is True
    assert item.id not in {m.id for m in store.list()}


def test_consolidate_creates_semantic_memory_from_similar_cluster(store):
    store.add("user likes dark mode in settings", memory_type=MemoryType.EPISODIC)
    store.add("user prefers dark mode setting enabled", memory_type=MemoryType.EPISODIC)
    store.add("user asked for dark mode again", memory_type=MemoryType.EPISODIC)
    store.add("completely unrelated note about lunch plans", memory_type=MemoryType.EPISODIC)

    created = store.consolidate(similarity_threshold=0.5, min_cluster_size=3)
    assert len(created) == 1
    assert created[0].memory_type == MemoryType.SEMANTIC
    assert "dark mode" in created[0].content.lower() or created[0].metadata.get("source_count") == 3


def test_consolidate_archives_source_memories_by_default(store):
    for i in range(3):
        store.add(
            "repeated preference about notifications being too noisy",
            memory_type=MemoryType.EPISODIC,
        )

    created = store.consolidate(similarity_threshold=0.3, min_cluster_size=3)
    assert len(created) == 1
    remaining_episodic = store.list(memory_type=MemoryType.EPISODIC)
    assert len(remaining_episodic) == 0


def test_consolidate_ignores_clusters_below_min_size(store):
    store.add("a one-off memory about the weather today")
    store.add("another totally different memory about groceries")

    created = store.consolidate(similarity_threshold=0.9, min_cluster_size=2)
    assert created == []
