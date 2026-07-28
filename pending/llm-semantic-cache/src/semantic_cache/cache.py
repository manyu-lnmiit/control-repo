"""The main SemanticCache API and the ``cached_llm_call`` decorator."""

from __future__ import annotations

import functools
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from semantic_cache.embeddings import EmbeddingBackend, HashingEmbedder
from semantic_cache.store import VectorStore


@dataclass
class CacheResult:
    """What a cache lookup returns: whether it was a hit and the payload."""

    hit: bool
    response: Any
    similarity: float = 0.0
    namespace: str = "default"


class SemanticCache:
    """A semantic cache for LLM / agent tool-call responses.

    Unlike a plain dict or Redis keyed by exact prompt string, this cache
    matches *semantically similar* prompts — the common case in agent loops,
    RAG pipelines, and chatbots where the same underlying question is asked
    with different wording, whitespace, or minor parameter changes. A hit
    saves an LLM API call entirely.

    Example:
        >>> cache = SemanticCache(path=":memory:", threshold=0.90)
        >>> cache.get("What is the capital of France?")
        CacheResult(hit=False, response=None, ...)
        >>> cache.set("What is the capital of France?", "Paris", cost_estimate=0.002)
        >>> result = cache.get("what's the capital of france")
        >>> result.hit, result.response
        (True, 'Paris')
    """

    def __init__(
        self,
        path: str = ":memory:",
        threshold: float = 0.92,
        embedder: EmbeddingBackend | None = None,
        max_entries: int = 10_000,
        namespace: str = "default",
        clock: Callable[[], float] | None = None,
    ) -> None:
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("threshold must be between 0.0 and 1.0")
        self._threshold = threshold
        self._embedder = embedder or HashingEmbedder()
        self._store = VectorStore(path=path, max_entries=max_entries)
        self._namespace = namespace
        self._clock = clock or time.time

    @property
    def threshold(self) -> float:
        return self._threshold

    def close(self) -> None:
        self._store.close()

    def __enter__(self) -> SemanticCache:
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def get(self, prompt: str, namespace: str | None = None) -> CacheResult:
        """Look up the closest cached prompt above ``threshold`` similarity."""
        ns = namespace or self._namespace
        now = self._clock()
        embedding = self._embedder.embed(prompt)
        match = self._store.best_match(ns, embedding, now)
        if match is None:
            return CacheResult(hit=False, response=None, namespace=ns)
        entry, score = match
        if score < self._threshold:
            return CacheResult(hit=False, response=None, similarity=score, namespace=ns)
        self._store.touch(entry.id, now)
        return CacheResult(hit=True, response=entry.response, similarity=score, namespace=ns)

    def set(
        self,
        prompt: str,
        response: Any,
        ttl_seconds: float | None = None,
        namespace: str | None = None,
        cost_estimate: float = 0.0,
    ) -> None:
        """Store a prompt/response pair for future semantic lookups."""
        ns = namespace or self._namespace
        now = self._clock()
        embedding = self._embedder.embed(prompt)
        self._store.put(ns, prompt, response, embedding, ttl_seconds, now, cost_estimate)

    def purge_expired(self) -> int:
        """Remove all TTL-expired entries and return how many were removed."""
        return self._store.purge_expired(self._clock())

    def clear(self, namespace: str | None = None) -> int:
        """Delete all entries, or all entries in a given namespace."""
        return self._store.clear(namespace)

    def stats(self, namespace: str | None = None) -> dict:
        """Return entry count, total hits, and estimated cost saved."""
        return self._store.stats(namespace)


def cached_llm_call(
    cache: SemanticCache,
    prompt_arg: str = "prompt",
    ttl_seconds: float | None = None,
    cost_estimate: float = 0.0,
    namespace: str | None = None,
):
    """Decorator that wraps any LLM-calling function with semantic caching.

    The decorated function must accept the prompt as a keyword argument (or
    the first positional argument) named ``prompt_arg``. On a cache miss the
    wrapped function runs normally and its return value is cached; on a hit
    the cached response is returned directly and the wrapped function is
    never called.

    Example:
        >>> cache = SemanticCache()
        >>> @cached_llm_call(cache, cost_estimate=0.01)
        ... def ask_llm(prompt: str) -> str:
        ...     return real_llm_client.complete(prompt)
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if prompt_arg in kwargs:
                prompt = kwargs[prompt_arg]
            elif args:
                prompt = args[0]
            else:
                raise TypeError(
                    f"cached_llm_call could not find prompt argument '{prompt_arg}' in call"
                )
            result = cache.get(prompt, namespace=namespace)
            if result.hit:
                return result.response
            response = func(*args, **kwargs)
            cache.set(prompt, response, ttl_seconds=ttl_seconds, namespace=namespace, cost_estimate=cost_estimate)
            return response

        wrapper.__wrapped_by_semantic_cache__ = True
        return wrapper

    return decorator
