import pytest

from semantic_cache.store import VectorStore


@pytest.fixture()
def store():
    s = VectorStore(path=":memory:", max_entries=3)
    yield s
    s.close()


def test_put_and_best_match(store):
    now = 1000.0
    store.put("ns", "hello", "world", [1.0, 0.0], ttl_seconds=None, now=now)
    match = store.best_match("ns", [1.0, 0.0], now=now)
    assert match is not None
    entry, score = match
    assert entry.response == "world"
    assert score == pytest.approx(1.0)


def test_best_match_returns_none_when_empty(store):
    assert store.best_match("ns", [1.0, 0.0], now=0.0) is None


def test_ttl_expiry(store):
    now = 1000.0
    store.put("ns", "hello", "world", [1.0, 0.0], ttl_seconds=10, now=now)
    assert store.best_match("ns", [1.0, 0.0], now=now + 5) is not None
    assert store.best_match("ns", [1.0, 0.0], now=now + 11) is None


def test_purge_expired(store):
    now = 1000.0
    store.put("ns", "a", "1", [1.0, 0.0], ttl_seconds=5, now=now)
    store.put("ns", "b", "2", [0.0, 1.0], ttl_seconds=None, now=now)
    removed = store.purge_expired(now=now + 10)
    assert removed == 1
    assert len(store.all_active("ns", now=now + 10)) == 1


def test_lru_eviction_by_max_entries(store):
    now = 1000.0
    for i in range(5):
        store.put("ns", f"p{i}", f"r{i}", [float(i), 0.0], ttl_seconds=None, now=now + i)
    active = store.all_active("ns", now=now + 100)
    # max_entries=3, so only the 3 most-recently-accessed should survive.
    assert len(active) == 3
    responses = {e.response for e in active}
    assert responses == {"r2", "r3", "r4"}


def test_touch_increments_hit_count_and_last_accessed(store):
    now = 1000.0
    entry_id = store.put("ns", "hello", "world", [1.0, 0.0], ttl_seconds=None, now=now)
    store.touch(entry_id, now=now + 1)
    entry, _ = store.best_match("ns", [1.0, 0.0], now=now + 1)
    assert entry.hit_count == 1
    assert entry.last_accessed_at == now + 1


def test_clear_all_and_namespace(store):
    now = 1000.0
    store.put("a", "x", "1", [1.0, 0.0], ttl_seconds=None, now=now)
    store.put("b", "y", "2", [0.0, 1.0], ttl_seconds=None, now=now)
    removed = store.clear("a")
    assert removed == 1
    assert len(store.all_active("a", now=now)) == 0
    assert len(store.all_active("b", now=now)) == 1
    store.clear()
    assert len(store.all_active("b", now=now)) == 0


def test_stats(store):
    now = 1000.0
    entry_id = store.put("ns", "x", "1", [1.0, 0.0], ttl_seconds=None, now=now, cost_estimate=0.02)
    store.touch(entry_id, now=now + 1)
    store.touch(entry_id, now=now + 2)
    data = store.stats("ns")
    assert data["entries"] == 1
    assert data["total_hits"] == 2
    assert data["estimated_cost_saved"] == pytest.approx(0.04)
