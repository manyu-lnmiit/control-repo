import math

import pytest

from semantic_cache.embeddings import HashingEmbedder


def test_embed_dimensions():
    embedder = HashingEmbedder(dimensions=64)
    vec = embedder.embed("hello world")
    assert len(vec) == 64
    assert embedder.dimensions == 64


def test_embed_is_normalized():
    embedder = HashingEmbedder(dimensions=32)
    vec = embedder.embed("agentic ai agentic ai agentic ai")
    norm = math.sqrt(sum(v * v for v in vec))
    assert norm == pytest.approx(1.0, abs=1e-6)


def test_empty_text_is_zero_vector():
    embedder = HashingEmbedder(dimensions=16)
    vec = embedder.embed("   ")
    assert all(v == 0.0 for v in vec)


def test_similar_text_similar_vectors():
    embedder = HashingEmbedder(dimensions=128)
    a = embedder.embed("What is the capital of France?")
    b = embedder.embed("what's the capital of france")
    # Shares most tokens after casing/tokenization -> vectors should be close.
    dot = sum(x * y for x, y in zip(a, b))
    assert dot > 0.5


def test_invalid_dimensions_raises():
    with pytest.raises(ValueError):
        HashingEmbedder(dimensions=0)
