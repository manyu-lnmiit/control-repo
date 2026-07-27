import random

import pytest

from agentflow.retry import compute_backoff


def test_backoff_grows_exponentially_before_cap():
    rng = random.Random(0)
    d0 = compute_backoff(0, base=1.0, cap=100.0, jitter=0.0, rng=rng)
    d1 = compute_backoff(1, base=1.0, cap=100.0, jitter=0.0, rng=rng)
    d2 = compute_backoff(2, base=1.0, cap=100.0, jitter=0.0, rng=rng)
    assert d0 == 1.0
    assert d1 == 2.0
    assert d2 == 4.0


def test_backoff_respects_cap():
    rng = random.Random(0)
    delay = compute_backoff(10, base=1.0, cap=5.0, jitter=0.0, rng=rng)
    assert delay == 5.0


def test_backoff_jitter_stays_non_negative_and_bounded():
    rng = random.Random(42)
    for attempt in range(6):
        delay = compute_backoff(attempt, base=0.5, cap=30.0, jitter=0.5, rng=rng)
        assert delay >= 0.0
        nominal = min(30.0, 0.5 * 2**attempt)
        assert delay <= nominal * 1.5 + 1e-9


def test_negative_attempt_raises():
    with pytest.raises(ValueError):
        compute_backoff(-1)
