"""A deterministic in-memory provider used for local dev, demos, and tests.

MockProvider never makes network calls. It simulates latency, token
counting (character-based approximation), and can be configured to fail a
fixed number of times before succeeding -- useful for exercising the
gateway's retry/failover logic without any external dependency.
"""

from __future__ import annotations

import asyncio

from llm_gateway.models import ChatRequest, ProviderError, Usage
from llm_gateway.providers.base import Provider


class MockProvider(Provider):
    """Echo-style provider with configurable latency, cost, and failure modes."""

    def __init__(
        self,
        name: str = "mock",
        price_per_1k_prompt: float = 0.5,
        price_per_1k_completion: float = 1.5,
        latency_s: float = 0.0,
        fail_times: int = 0,
        fail_retryable: bool = True,
    ):
        self.name = name
        self.price_per_1k_prompt = price_per_1k_prompt
        self.price_per_1k_completion = price_per_1k_completion
        self.latency_s = latency_s
        self._fail_times = fail_times
        self._fail_retryable = fail_retryable
        self._calls = 0

    @property
    def call_count(self) -> int:
        return self._calls

    async def complete(self, request: ChatRequest) -> tuple[str, Usage]:
        self._calls += 1
        if self.latency_s:
            await asyncio.sleep(self.latency_s)

        if self._calls <= self._fail_times:
            raise ProviderError(
                self.name,
                f"simulated failure #{self._calls}",
                retryable=self._fail_retryable,
            )

        last_user = next(
            (m.content for m in reversed(request.messages) if m.role.value == "user"), ""
        )
        content = f"[{self.name}:{request.model}] {last_user[::-1] if last_user else 'ack'}"

        prompt_tokens = max(1, request.prompt_chars() // 4)
        completion_tokens = max(1, len(content) // 4)
        cost = self.estimate_cost(prompt_tokens, completion_tokens)
        return content, Usage(
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, cost_usd=cost
        )
