"""Cost budgeting and per-tool rate limiting.

`CostBudget` tracks cumulative spend (in whatever unit the caller chooses,
typically USD) across a guarded session and rejects calls that would push
the total past a configured ceiling.

`RateLimiter` is a simple sliding-window limiter keyed by tool name, used to
cap calls-per-minute per tool as declared in policy.
"""

from __future__ import annotations

import threading
from collections import defaultdict, deque

from agent_guardrail.exceptions import BudgetExceededError, RateLimitExceededError


class CostBudget:
    """Tracks cumulative cost against a hard ceiling.

    Thread-safe: agent frameworks frequently dispatch tool calls from a
    thread pool, so all mutation happens under a lock.
    """

    def __init__(self, max_total_cost: float):
        if max_total_cost < 0:
            raise ValueError("max_total_cost must be >= 0")
        self.max_total_cost = max_total_cost
        self._spent = 0.0
        self._lock = threading.Lock()

    @property
    def spent(self) -> float:
        with self._lock:
            return self._spent

    @property
    def remaining(self) -> float:
        with self._lock:
            return self.max_total_cost - self._spent

    def charge(self, amount: float, *, tool_name: str = "") -> None:
        if amount < 0:
            raise ValueError("amount must be >= 0")
        with self._lock:
            projected = self._spent + amount
            if projected > self.max_total_cost:
                raise BudgetExceededError(
                    f"charging {amount:.6f} for '{tool_name}' would bring total "
                    f"spend to {projected:.6f}, exceeding budget of "
                    f"{self.max_total_cost:.6f}"
                )
            self._spent = projected

    def reset(self) -> None:
        with self._lock:
            self._spent = 0.0


class RateLimiter:
    """Sliding-window (60s) per-tool call rate limiter."""

    def __init__(self):
        self._calls: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check_and_record(self, tool_name: str, max_calls_per_minute: int, now: float) -> None:
        if max_calls_per_minute is None:
            return
        with self._lock:
            window = self._calls[tool_name]
            cutoff = now - 60.0
            while window and window[0] < cutoff:
                window.popleft()
            if len(window) >= max_calls_per_minute:
                raise RateLimitExceededError(
                    f"tool '{tool_name}' exceeded rate limit of "
                    f"{max_calls_per_minute} calls/minute"
                )
            window.append(now)
