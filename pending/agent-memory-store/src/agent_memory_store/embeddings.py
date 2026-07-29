"""Dependency-free text embeddings.

We deliberately avoid a hard dependency on numpy or sentence-transformers so
that the core package installs with zero third-party requirements. The
``HashingVectorizer`` below implements the classic "hashing trick": tokens
are hashed into a fixed-size vector, weighted by (sublinear) term frequency,
and the resulting vector is L2-normalized. This gives a stable, deterministic
embedding that is good enough for near-duplicate / topical similarity search
over short-to-medium agent memories, without shipping model weights.

If higher-quality embeddings are desired, swap ``HashingVectorizer`` out for
any callable with the same ``embed(text) -> list[float]`` signature (e.g. a
wrapper around a real embedding API).
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class HashingVectorizer:
    """Deterministic, dependency-free hashing-trick text vectorizer."""

    def __init__(self, dims: int = 256) -> None:
        if dims <= 0:
            raise ValueError("dims must be positive")
        self.dims = dims

    @staticmethod
    def _stable_hash(token: str) -> int:
        """Deterministic hash independent of PYTHONHASHSEED / process."""
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        return int.from_bytes(digest, "big", signed=False)

    def embed(self, text: str) -> list[float]:
        tokens = tokenize(text)
        if not tokens:
            return [0.0] * self.dims

        counts = Counter(tokens)
        vec = [0.0] * self.dims
        for token, count in counts.items():
            h = self._stable_hash(token)
            idx = h % self.dims
            sign = 1.0 if (h >> 1) % 2 == 0 else -1.0
            # sublinear TF scaling dampens the effect of very frequent tokens
            vec[idx] += sign * (1.0 + math.log(count))

        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return max(-1.0, min(1.0, dot / (norm_a * norm_b)))
