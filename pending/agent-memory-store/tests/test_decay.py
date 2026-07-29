from agent_memory_store.decay import decayed_importance, touch
from agent_memory_store.memory import MemoryItem, MemoryType


def make_item(importance=0.8, half_life=100.0, last_accessed=0.0, access_count=0):
    item = MemoryItem(
        content="test",
        memory_type=MemoryType.EPISODIC,
        importance=importance,
        half_life_seconds=half_life,
    )
    item.last_accessed_at = last_accessed
    item.access_count = access_count
    return item


def test_no_elapsed_time_means_no_decay():
    item = make_item(importance=0.8, half_life=100.0, last_accessed=1000.0)
    assert decayed_importance(item, now=1000.0) == 0.8


def test_one_half_life_halves_importance():
    item = make_item(importance=0.8, half_life=100.0, last_accessed=0.0)
    result = decayed_importance(item, now=100.0)
    assert abs(result - 0.4) < 1e-9


def test_two_half_lives_quarters_importance():
    item = make_item(importance=0.8, half_life=100.0, last_accessed=0.0)
    result = decayed_importance(item, now=200.0)
    assert abs(result - 0.2) < 1e-9


def test_access_count_slows_decay():
    fresh = make_item(importance=0.8, half_life=100.0, last_accessed=0.0, access_count=0)
    reinforced = make_item(importance=0.8, half_life=100.0, last_accessed=0.0, access_count=10)
    assert decayed_importance(reinforced, now=100.0) > decayed_importance(fresh, now=100.0)


def test_decay_never_goes_negative_or_above_one():
    item = make_item(importance=1.0, half_life=1.0, last_accessed=0.0)
    result = decayed_importance(item, now=10_000.0)
    assert 0.0 <= result <= 1.0


def test_zero_half_life_returns_base_importance():
    item = make_item(importance=0.6, half_life=0.0, last_accessed=0.0)
    assert decayed_importance(item, now=999.0) == 0.6


def test_touch_updates_access_stats():
    item = make_item(importance=0.5, last_accessed=0.0, access_count=2)
    touch(item, now=50.0)
    assert item.last_accessed_at == 50.0
    assert item.access_count == 3


def test_touch_with_boost_increases_importance_and_clamps():
    item = make_item(importance=0.95)
    touch(item, now=1.0, boost=0.5)
    assert item.importance == 1.0
