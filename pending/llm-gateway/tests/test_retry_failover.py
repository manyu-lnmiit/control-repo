import pytest

from llm_gateway.models import AllProvidersFailedError, ChatMessage, ChatRequest, Role
from llm_gateway.providers.mock import MockProvider
from llm_gateway.retry import run_with_failover


def make_request():
    return ChatRequest(model="m", messages=[ChatMessage(role=Role.USER, content="hello")])


@pytest.mark.asyncio
async def test_succeeds_on_first_provider_no_failures():
    p1 = MockProvider("p1")
    provider, _content, usage, attempts = await run_with_failover([p1], make_request())
    assert provider is p1
    assert attempts == 1
    assert usage.total_tokens > 0


@pytest.mark.asyncio
async def test_retries_transient_failure_then_succeeds():
    p1 = MockProvider("p1", fail_times=2, fail_retryable=True)
    provider, _content, _usage, attempts = await run_with_failover(
        [p1], make_request(), max_retries_per_provider=3
    )
    assert provider is p1
    assert attempts == 3
    assert p1.call_count == 3


@pytest.mark.asyncio
async def test_fails_over_to_second_provider_on_exhaustion():
    p1 = MockProvider("p1", fail_times=99, fail_retryable=True)
    p2 = MockProvider("p2")
    provider, _content, _usage, attempts = await run_with_failover(
        [p1, p2], make_request(), max_retries_per_provider=1
    )
    assert provider is p2
    assert p1.call_count == 2  # initial attempt + 1 retry
    assert p2.call_count == 1


@pytest.mark.asyncio
async def test_non_retryable_error_skips_immediately_to_next_provider():
    p1 = MockProvider("p1", fail_times=1, fail_retryable=False)
    p2 = MockProvider("p2")
    provider, _content, _usage, _attempts = await run_with_failover(
        [p1, p2], make_request(), max_retries_per_provider=5
    )
    assert provider is p2
    assert p1.call_count == 1  # no retries attempted, moved on immediately


@pytest.mark.asyncio
async def test_all_providers_failed_raises_with_errors():
    p1 = MockProvider("p1", fail_times=99)
    p2 = MockProvider("p2", fail_times=99)
    with pytest.raises(AllProvidersFailedError) as exc_info:
        await run_with_failover([p1, p2], make_request(), max_retries_per_provider=0)
    assert len(exc_info.value.errors) == 2
