import pytest

from llm_gateway.cost_tracker import CostTracker
from llm_gateway.gateway import Gateway
from llm_gateway.models import (
    AllProvidersFailedError,
    ChatMessage,
    ChatRequest,
    RateLimitExceeded,
    Role,
)
from llm_gateway.providers.mock import MockProvider
from llm_gateway.rate_limiter import RateLimiter
from llm_gateway.router import Router, RouteRule


def make_gateway(**kwargs):
    p1 = MockProvider("primary", **kwargs.pop("p1_kwargs", {}))
    p2 = MockProvider("secondary")
    router = Router(providers={"primary": p1, "secondary": p2}, rules=[RouteRule(providers=["primary", "secondary"])])
    gateway = Gateway(router=router, **kwargs)
    return gateway, p1, p2


@pytest.mark.asyncio
async def test_end_to_end_success_records_cost():
    gateway, p1, p2 = make_gateway()
    request = ChatRequest(model="gpt-x", messages=[ChatMessage(role=Role.USER, content="hello world")])
    response = await gateway.chat(request)

    assert response.provider == "primary"
    assert response.content
    assert response.usage.total_tokens > 0
    snap = gateway.stats()
    assert snap["by_key"]["default"]["requests"] == 1


@pytest.mark.asyncio
async def test_failover_to_secondary_on_primary_outage():
    gateway, p1, p2 = make_gateway(p1_kwargs={"fail_times": 99})
    request = ChatRequest(model="gpt-x", messages=[ChatMessage(role=Role.USER, content="hi")])
    response = await gateway.chat(request)
    assert response.provider == "secondary"


@pytest.mark.asyncio
async def test_rate_limit_enforced_across_calls():
    p1 = MockProvider("primary")
    router = Router(providers={"primary": p1})
    gateway = Gateway(router=router, rate_limiter=RateLimiter(requests_per_minute=60, burst=1))
    request = ChatRequest(model="m", messages=[ChatMessage(role=Role.USER, content="hi")])
    await gateway.chat(request)
    with pytest.raises(RateLimitExceeded):
        await gateway.chat(request)


@pytest.mark.asyncio
async def test_budget_exceeded_blocks_further_calls():
    p1 = MockProvider("primary", price_per_1k_prompt=1000.0, price_per_1k_completion=1000.0)
    router = Router(providers={"primary": p1})
    gateway = Gateway(
        router=router,
        rate_limiter=RateLimiter(requests_per_minute=1000, burst=1000),
        cost_tracker=CostTracker(budget_usd={"default": 0.001}),
    )
    request = ChatRequest(model="m", messages=[ChatMessage(role=Role.USER, content="hi")])
    await gateway.chat(request)  # first call pushes spend over budget
    with pytest.raises(RateLimitExceeded):
        await gateway.chat(request)


@pytest.mark.asyncio
async def test_all_providers_down_raises():
    p1 = MockProvider("primary", fail_times=99)
    router = Router(providers={"primary": p1})
    gateway = Gateway(router=router)
    request = ChatRequest(model="m", messages=[ChatMessage(role=Role.USER, content="hi")])
    with pytest.raises(AllProvidersFailedError):
        await gateway.chat(request)
