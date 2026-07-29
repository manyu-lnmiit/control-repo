import math

from agent_memory_store.embeddings import HashingVectorizer, cosine_similarity, tokenize


def test_tokenize_lowercases_and_splits():
    assert tokenize("Hello, World! 123") == ["hello", "world", "123"]


def test_tokenize_empty_string():
    assert tokenize("") == []


def test_embed_is_deterministic_across_instances():
    v1 = HashingVectorizer(dims=64)
    v2 = HashingVectorizer(dims=64)
    a = v1.embed("the agent remembered the user's preference")
    b = v2.embed("the agent remembered the user's preference")
    assert a == b


def test_embed_empty_text_is_zero_vector():
    v = HashingVectorizer(dims=32)
    vec = v.embed("")
    assert vec == [0.0] * 32


def test_embed_is_unit_normalized():
    v = HashingVectorizer(dims=64)
    vec = v.embed("consolidating episodic memories into semantic knowledge")
    norm = math.sqrt(sum(x * x for x in vec))
    assert math.isclose(norm, 1.0, abs_tol=1e-6)


def test_similar_texts_score_higher_than_unrelated():
    v = HashingVectorizer(dims=128)
    a = v.embed("the user prefers dark mode in the settings panel")
    b = v.embed("user prefers dark mode setting panel")
    c = v.embed("quarterly revenue grew by twelve percent last year")

    sim_related = cosine_similarity(a, b)
    sim_unrelated = cosine_similarity(a, c)
    assert sim_related > sim_unrelated


def test_cosine_similarity_identical_vectors_is_one():
    v = HashingVectorizer(dims=32)
    vec = v.embed("identical text for similarity check")
    assert math.isclose(cosine_similarity(vec, vec), 1.0, abs_tol=1e-6)


def test_cosine_similarity_mismatched_lengths_returns_zero():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0, 0.0]) == 0.0


def test_cosine_similarity_empty_vectors_returns_zero():
    assert cosine_similarity([], []) == 0.0


def test_dims_must_be_positive():
    import pytest

    with pytest.raises(ValueError):
        HashingVectorizer(dims=0)
