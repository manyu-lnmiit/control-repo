"""Retry-with-backoff and provider failover.

`run_with_failover` walks an ordered provider chain and, on a retryable
`ProviderError`, moves on to the next provider after an exponential
backoff sleep. Non-retryable errors abort that provider immediately and
proceed to the next one without waiting -- there is no point retrying a
request the provider has already rejected as invalid.
"""

from __future__ import annotations

import asyncio
import time

from llm_gateway.models import AllProvidersFailedError, ChatRequest, ProviderError, Usage
from llm_gateway.providers.base import Provider


async def run_with_failover(
    chain: list[Provider],
    request: ChatRequest,
    max_retries_per_provider: int = 2,
    base_backoff_s: float = 0.05,
    sleep=asyncio.sleep,
) -> tuple[Provider, str, Usage, int]:
    """Attempt `request` against each provider in `chain` in order.

    Within a provider, retryable errors are retried up to
    `max_retries_per_provider` times with exponential backoff before
    moving to the next provider. Returns (provider, content, usage,
    total_attempts). Raises AllProvidersFailedError if every provider in
    the chain is exhausted.
    """
    errors: list[str] = []
    total_attempts = 0

    for provider in chain:
        attempt = 0
        while attempt <= max_retries_per_provider:
            total_attempts += 1
            attempt += 1
            try:
                content, usage = await provider.complete(request)
                return provider, content, usage, total_attempts
            except ProviderError as exc:
                errors.append(str(exc))
                if not exc.retryable or attempt > max_retries_per_provider:
                    break
                await sleep(base_backoff_s * (2 ** (attempt - 1)))

    raise AllProvidersFailedError(request.model, errors)


def now_ms() -> float:
    return time.perf_counter() * 1000.0
