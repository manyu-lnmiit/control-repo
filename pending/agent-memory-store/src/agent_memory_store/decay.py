"""Time-based importance decay, loosely inspired by the Ebbinghaus forgetting
curve: a memory's *effective* importance fades over time since it was last
accessed, but each access refreshes it and slows future decay.
"""

from __future__ import annotations

import math

from .memory import MemoryItem


def decayed_importance(item: MemoryItem, now: float) -> float:
    """Return the effective importance of ``item`` at time ``now``.

    Uses exponential decay: effective = base_importance * 0.5 ** (elapsed /
    half_life). Access count provides a mild "spaced repetition" boost that
    extends the effective half-life, since frequently-recalled memories tend
    to be more durable.
    """

    elapsed = max(0.0, now - item.last_accessed_at)
    if item.half_life_seconds <= 0:
        return item.importance

    reinforcement = 1.0 + math.log1p(item.access_count)
    effective_half_life = item.half_life_seconds * reinforcement
    decay_factor = 0.5 ** (elapsed / effective_half_life)
    return max(0.0, min(1.0, item.importance * decay_factor))


def touch(item: MemoryItem, now: float, boost: float = 0.0) -> None:
    """Record an access to ``item`` at time ``now``.

    Refreshes ``last_accessed_at``, increments ``access_count``, and
    optionally nudges ``importance`` upward (clamped to [0, 1]).
    """

    item.last_accessed_at = now
    item.access_count += 1
    if boost:
        item.importance = max(0.0, min(1.0, item.importance + boost))
