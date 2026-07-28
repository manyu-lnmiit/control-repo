import pytest

from semantic_cache.cache import SemanticCache, cached_llm_call


@pytest.fixture()
def cache():
    c = SemanticCache(path=":memory:", threshold=0.85)
    yield c
    c.close()


def test_miss_then_hit(cache):
    result = cache.get("What is the capital of France?")
    assert result.hit is False

    cache.set("What is the capital of France?", "Paris", cost_estimate=0.01)

    result = cache.get("what is the capital of france")
    assert result.hit is True
    assert result.response == "Paris"


def test_dissimilar_prompt_is_a_miss(cache):
    cache.set("What is the capital of France?", "Paris")
    result = cache.get("Write a Python function to reverse a linked list")
    assert result.hit is False


def test_threshold_enforced():
    strict_cache = SemanticCache(path=":memory:", threshold=0.999)
    strict_cache.set("What is the capital of France?", "Paris")
    result = strict_cache.get("what's the capital of france")
    assert result.hit is False
    strict_cache.close()


def test_invalid_threshold_raises():
    with pytest.raises(ValueError):
        SemanticCache(threshold=1.5)


def test_ttl_expiry_via_cache(cache):
    now = {"t": 1000.0}
    clocked_cache = SemanticCache(path=":memory:", threshold=0.85, clock=lambda: now["t"])
    clocked_cache.set("hello there", "hi", ttl_seconds=10)
    now["t"] += 5
    assert clocked_cache.get("hello there").hit is True
    now["t"] += 10
    assert clocked_cache.get("hello there").hit is False
    clocked_cache.close()


def test_namespaces_are_isolated(cache):
    cache.set("hello", "world", namespace="team-a")
    result = cache.get("hello", namespace="team-b")
    assert result.hit is False
    result = cache.get("hello", namespace="team-a")
    assert result.hit is True


def test_stats_track_hits_and_cost(cache):
    cache.set("hello world", "response", cost_estimate=0.05)
    cache.get("hello world")
    cache.get("hello world")
    data = cache.stats()
    assert data["entries"] == 1
    assert data["total_hits"] == 2
    assert data["estimated_cost_saved"] == pytest.approx(0.10)


def test_clear_and_purge(cache):
    cache.set("hello world", "response")
    assert cache.stats()["entries"] == 1
    removed = cache.clear()
    assert removed == 1
    assert cache.stats()["entries"] == 0


def test_cached_llm_call_decorator_avoids_second_call(cache):
    call_count = {"n": 0}

    @cached_llm_call(cache, cost_estimate=0.02)
    def ask_llm(prompt: str) -> str:
        call_count["n"] += 1
        return f"answer to: {prompt}"

    first = ask_llm(prompt="What is the capital of France?")
    second = ask_llm(prompt="what is the capital of france")

    assert first == second
    assert call_count["n"] == 1


def test_cached_llm_call_positional_prompt(cache):
    call_count = {"n": 0}

    @cached_llm_call(cache)
    def ask_llm(prompt: str) -> str:
        call_count["n"] += 1
        return "42"

    ask_llm("what is the meaning of life")
    ask_llm("what is the meaning of life")
    assert call_count["n"] == 1


def test_cached_llm_call_requires_prompt_arg(cache):
    @cached_llm_call(cache, prompt_arg="prompt")
    def ask_llm(**kwargs) -> str:
        return "response"

    with pytest.raises(TypeError):
        ask_llm(not_prompt="oops")
