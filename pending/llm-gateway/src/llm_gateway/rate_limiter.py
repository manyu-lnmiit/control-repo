"""Per-key token-bucket rate limiting."""

from __future__ import annotations

import threading
import time

from llm_gateway.models import RateLimitExceeded


class TokenBucket:
    """A single token bucket: capacity tokens, refilled at rate/second."""

    def __init__(self, capacity: float, refill_rate_per_s: float, clock=time.monotonic):
        self.capacity = capacity
        self.refill_rate_per_s = refill_rate_per_s
        self._clock = clock
        self._tokens = capacity
        self._last = clock()

    def _refill(self) -> None:
        now = self._clock()
        elapsed = max(0.0, now - self._last)
        self._tokens = min(self.capacity, self._tokens + elapsed * self.refill_rate_per_s)
        self._last = now

    def try_consume(self, amount: float = 1.0) -> tuple[bool, float]:
        """Attempt to consume `amount` tokens.

        Returns (allowed, retry_after_seconds). retry_after_seconds is 0
        when allowed is True.
        """
        self._refill()
        if self._tokens >= amount:
            self._tokens -= amount
            return True, 0.0
        deficit = amount - self._tokens
        retry_after = deficit / self.refill_rate_per_s if self.refill_rate_per_s > 0 else float("inf")
        return False, retry_after


class RateLimiter:
    """Thread-safe per-key rate limiter backed by token buckets.

    Each distinct ``key_id`` (e.g. an API key or tenant id) gets its own
    bucket, created lazily on first use with the configured default
    capacity/refill rate.
    """

    def __init__(self, requests_per_minute: float = 60.0, burst: float | None = None):
        self.requests_per_minute = requests_per_minute
        self.refill_rate_per_s = requests_per_minute / 60.0
        self.capacity = burst if burst is not None else requests_per_minute
        self._buckets: dict[str, TokenBucket] = {}
        self._lock = threading.Lock()

    def _bucket_for(self, key_id: str) -> TokenBucket:
        with self._lock:
            bucket = self._buckets.get(key_id)
            if bucket is None:
                bucket = TokenBucket(self.capacity, self.refill_rate_per_s)
                self._buckets[key_id] = bucket
            return bucket

    def check(self, key_id: str, cost: float = 1.0) -> None:
        """Raise :class:`RateLimitExceeded` if `key_id` is over its limit."""
        allowed, retry_after = self._bucket_for(key_id).try_consume(cost)
        if not allowed:
            raise RateLimitExceeded(key_id, retry_after)

    def remaining(self, key_id: str) -> float:
        bucket = self._bucket_for(key_id)
        bucket._refill()
        return bucket._tokens
