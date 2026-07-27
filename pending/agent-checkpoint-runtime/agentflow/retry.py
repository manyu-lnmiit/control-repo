"""Retry / backoff helpers used by :mod:`agentflow.core`."""

from __future__ import annotations

import random


def compute_backoff(
    attempt: int,
    base: float = 0.5,
    cap: float = 30.0,
    jitter: float = 0.25,
    rng: random.Random | None = None,
) -> float:
    """Compute an exponential backoff delay (in seconds) with jitter.

    ``attempt`` is zero-indexed (the attempt number that just failed).
    The nominal delay is ``min(cap, base * 2 ** attempt)``; jitter adds up to
    ``jitter`` fraction of random noise (both directions) so that many
    concurrent workflow runs don't retry in lockstep.
    """
    if attempt < 0:
        raise ValueError("attempt must be >= 0")
    nominal = min(cap, base * (2**attempt))
    spread = nominal * jitter
    noise = rng.uniform(-spread, spread) if rng is not None else random.uniform(-spread, spread)
    delay = nominal + noise
    return max(0.0, delay)
