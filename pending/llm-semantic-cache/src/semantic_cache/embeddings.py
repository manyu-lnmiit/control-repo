"""Embedding backends used to turn prompt text into vectors for similarity search.

The package ships with a dependency-free ``HashingEmbedder`` so the cache works
fully offline and in tests without any network access or ML model download.
Production deployments that want higher-quality semantic matching can plug in
``OpenAIEmbedder`` (requires the ``openai`` extra and an API key) or any other
class implementing the ``EmbeddingBackend`` protocol.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Sequence
from typing import Protocol

_TOKEN_RE = re.compile(r"[a-z0-9]+")


class EmbeddingBackend(Protocol):
    """Anything that can turn text into a fixed-length numeric vector."""

    def embed(self, text: str) -> Sequence[float]:
        ...

    @property
    def dimensions(self) -> int:
        ...


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class HashingEmbedder:
    """A deterministic, dependency-free bag-of-words hashing embedder.

    Each token is hashed into one of ``dimensions`` buckets and the resulting
    term-frequency vector is L2-normalized. This is not as semantically rich
    as a neural embedding model, but it is fast, requires zero dependencies or
    network access, and is good enough to catch near-duplicate / paraphrased
    prompts that share vocabulary — the common case for repeated LLM calls in
    agent loops (e.g. the same tool being asked the same question with minor
    wording differences).
    """

    def __init__(self, dimensions: int = 256) -> None:
        if dimensions <= 0:
            raise ValueError("dimensions must be positive")
        self._dimensions = dimensions

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def _bucket(self, token: str) -> int:
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        return int(digest, 16) % self._dimensions

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self._dimensions
        tokens = _tokenize(text)
        if not tokens:
            return vector
        for token in tokens:
            vector[self._bucket(token)] += 1.0
        norm = math.sqrt(sum(component * component for component in vector))
        if norm == 0:
            return vector
        return [component / norm for component in vector]


class OpenAIEmbedder:
    """Embedding backend that calls the OpenAI Embeddings API.

    Requires the ``openai`` extra (``pip install llm-semantic-cache[openai]``)
    and an ``OPENAI_API_KEY`` environment variable (or a client passed in
    explicitly). Not used by default and not exercised in the test suite,
    since it requires network access and a real API key.
    """

    def __init__(self, model: str = "text-embedding-3-small", client=None, dimensions: int = 1536):
        self._model = model
        self._dimensions = dimensions
        self._client = client

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - exercised only without extra
            raise ImportError(
                "OpenAIEmbedder requires the 'openai' extra: pip install llm-semantic-cache[openai]"
            ) from exc
        self._client = OpenAI()
        return self._client

    def embed(self, text: str) -> list[float]:  # pragma: no cover - network call
        client = self._get_client()
        response = client.embeddings.create(model=self._model, input=text)
        return list(response.data[0].embedding)
