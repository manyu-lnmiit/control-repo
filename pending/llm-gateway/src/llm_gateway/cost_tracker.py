"""In-memory usage and cost accounting, aggregated by API key and provider."""

from __future__ import annotations

import threading
from dataclasses import dataclass

from llm_gateway.models import Usage


@dataclass
class Totals:
    """Running totals for one aggregation bucket (a key or a provider)."""

    requests: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0

    def add(self, usage: Usage) -> None:
        self.requests += 1
        self.prompt_tokens += usage.prompt_tokens
        self.completion_tokens += usage.completion_tokens
        self.cost_usd += usage.cost_usd

    def to_dict(self) -> dict:
        return {
            "requests": self.requests,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.prompt_tokens + self.completion_tokens,
            "cost_usd": round(self.cost_usd, 6),
        }


class CostTracker:
    """Thread-safe accumulator of usage/cost, keyed by API key and by provider."""

    def __init__(self, budget_usd: dict[str, float] | None = None):
        self._by_key: dict[str, Totals] = {}
        self._by_provider: dict[str, Totals] = {}
        self._lock = threading.Lock()
        self.budget_usd = budget_usd or {}

    def record(self, key_id: str, provider: str, usage: Usage) -> None:
        with self._lock:
            self._by_key.setdefault(key_id, Totals()).add(usage)
            self._by_provider.setdefault(provider, Totals()).add(usage)

    def spend_for_key(self, key_id: str) -> float:
        with self._lock:
            totals = self._by_key.get(key_id)
            return totals.cost_usd if totals else 0.0

    def is_over_budget(self, key_id: str) -> bool:
        limit = self.budget_usd.get(key_id)
        if limit is None:
            return False
        return self.spend_for_key(key_id) >= limit

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "by_key": {k: v.to_dict() for k, v in self._by_key.items()},
                "by_provider": {k: v.to_dict() for k, v in self._by_provider.items()},
            }
