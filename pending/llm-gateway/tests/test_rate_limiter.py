import pytest

from llm_gateway.models import RateLimitExceeded
from llm_gateway.rate_limiter import RateLimiter, TokenBucket


def test_token_bucket_allows_within_capacity():
    clock = [0.0]
    bucket = TokenBucket(capacity=3, refill_rate_per_s=1, clock=lambda: clock[0])
    for _ in range(3):
        allowed, retry_after = bucket.try_consume()
        assert allowed
        assert retry_after == 0.0


def test_token_bucket_blocks_when_exhausted():
    clock = [0.0]
    bucket = TokenBucket(capacity=1, refill_rate_per_s=1, clock=lambda: clock[0])
    assert bucket.try_consume()[0] is True
    allowed, retry_after = bucket.try_consume()
    assert allowed is False
    assert retry_after > 0


def test_token_bucket_refills_over_time():
    clock = [0.0]
    bucket = TokenBucket(capacity=1, refill_rate_per_s=2, clock=lambda: clock[0])
    assert bucket.try_consume()[0] is True
    assert bucket.try_consume()[0] is False
    clock[0] += 0.5  # half a second at rate 2/s = 1 token
    assert bucket.try_consume()[0] is True


def test_rate_limiter_per_key_isolation():
    limiter = RateLimiter(requests_per_minute=60, burst=1)
    limiter.check("alice")
    with pytest.raises(RateLimitExceeded):
        limiter.check("alice")
    # a different key has its own bucket and is unaffected
    limiter.check("bob")


def test_rate_limiter_exception_carries_key_and_retry_after():
    limiter = RateLimiter(requests_per_minute=60, burst=1)
    limiter.check("alice")
    with pytest.raises(RateLimitExceeded) as exc_info:
        limiter.check("alice")
    assert exc_info.value.key_id == "alice"
    assert exc_info.value.retry_after_s > 0
