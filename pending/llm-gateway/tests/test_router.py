import pytest

from llm_gateway.models import ChatMessage, ChatRequest, Role
from llm_gateway.providers.mock import MockProvider
from llm_gateway.router import Router, RouteRule


def make_request(model="gpt-4o-mini", task_hint=None):
    return ChatRequest(
        model=model, messages=[ChatMessage(role=Role.USER, content="hi")], task_hint=task_hint
    )


def test_router_requires_at_least_one_provider():
    with pytest.raises(ValueError):
        Router(providers={})


def test_router_matches_model_prefix():
    p1, p2 = MockProvider("p1"), MockProvider("p2")
    router = Router(
        providers={"p1": p1, "p2": p2},
        rules=[RouteRule(providers=["p1"], model_prefix="gpt-"), RouteRule(providers=["p2"])],
    )
    chain = router.resolve(make_request(model="gpt-4o-mini"))
    assert chain == [p1]

    chain2 = router.resolve(make_request(model="claude-3"))
    assert chain2 == [p2]


def test_router_matches_task_hint():
    p1, p2 = MockProvider("p1"), MockProvider("p2")
    router = Router(
        providers={"p1": p1, "p2": p2},
        rules=[RouteRule(providers=["p1"], task_hint="code"), RouteRule(providers=["p2"])],
    )
    chain = router.resolve(make_request(task_hint="code"))
    assert chain == [p1]
    chain2 = router.resolve(make_request(task_hint="chat"))
    assert chain2 == [p2]


def test_router_falls_back_to_all_providers_when_no_rule_matches():
    p1, p2 = MockProvider("p1"), MockProvider("p2")
    router = Router(providers={"p1": p1, "p2": p2}, rules=[])
    chain = router.resolve(make_request())
    assert set(chain) == {p1, p2}


def test_router_skips_rule_whose_providers_are_unregistered():
    p2 = MockProvider("p2")
    router = Router(
        providers={"p2": p2},
        rules=[RouteRule(providers=["missing"]), RouteRule(providers=["p2"])],
    )
    chain = router.resolve(make_request())
    assert chain == [p2]
