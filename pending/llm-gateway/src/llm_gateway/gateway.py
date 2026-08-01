"""The gateway: ties together rate limiting, routing, failover, and cost tracking."""

from __future__ import annotations

import logging

from llm_gateway.cost_tracker import CostTracker
from llm_gateway.models import ChatRequest, ChatResponse, RateLimitExceeded
from llm_gateway.providers.base import Provider
from llm_gateway.rate_limiter import RateLimiter
from llm_gateway.retry import now_ms, run_with_failover
from llm_gateway.router import Router

logger = logging.getLogger("llm_gateway")


class Gateway:
    """Single entry point for chat completions.

    Pipeline for every request: (1) enforce the caller's rate limit, (2)
    resolve a provider chain via the router, (3) run the request with
    retry/failover across that chain, (4) record usage/cost, (5) return a
    normalized :class:`ChatResponse`.
    """

    def __init__(
        self,
        router: Router,
        rate_limiter: RateLimiter | None = None,
        cost_tracker: CostTracker | None = None,
        max_retries_per_provider: int = 2,
    ):
        self.router = router
        self.rate_limiter = rate_limiter or RateLimiter()
        self.cost_tracker = cost_tracker or CostTracker()
        self.max_retries_per_provider = max_retries_per_provider

    @property
    def providers(self) -> dict[str, Provider]:
        return self.router.providers

    async def chat(self, request: ChatRequest) -> ChatResponse:
        self.rate_limiter.check(request.api_key_id)

        if self.cost_tracker.is_over_budget(request.api_key_id):
            raise RateLimitExceeded(request.api_key_id, retry_after_s=0.0)

        chain = self.router.resolve(request)
        start = now_ms()
        provider, content, usage, attempts = await run_with_failover(
            chain, request, max_retries_per_provider=self.max_retries_per_provider
        )
        latency_ms = now_ms() - start

        self.cost_tracker.record(request.api_key_id, provider.name, usage)

        if attempts > 1:
            logger.info(
                "request %s served by %s after %d attempt(s)",
                request.request_id,
                provider.name,
                attempts,
            )

        return ChatResponse(
            request_id=request.request_id,
            provider=provider.name,
            model=request.model,
            content=content,
            usage=usage,
            latency_ms=latency_ms,
            attempts=attempts,
        )

    def stats(self) -> dict:
        return self.cost_tracker.snapshot()
