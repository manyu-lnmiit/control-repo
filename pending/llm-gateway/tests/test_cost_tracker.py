from llm_gateway.cost_tracker import CostTracker
from llm_gateway.models import Usage


def test_records_and_aggregates_by_key_and_provider():
    tracker = CostTracker()
    tracker.record("alice", "p1", Usage(prompt_tokens=100, completion_tokens=50, cost_usd=0.1))
    tracker.record("alice", "p1", Usage(prompt_tokens=200, completion_tokens=100, cost_usd=0.2))
    tracker.record("bob", "p2", Usage(prompt_tokens=10, completion_tokens=5, cost_usd=0.01))

    snap = tracker.snapshot()
    assert snap["by_key"]["alice"]["requests"] == 2
    assert snap["by_key"]["alice"]["total_tokens"] == 450
    assert round(snap["by_key"]["alice"]["cost_usd"], 4) == 0.3
    assert snap["by_provider"]["p1"]["requests"] == 2
    assert snap["by_key"]["bob"]["requests"] == 1


def test_budget_enforcement():
    tracker = CostTracker(budget_usd={"alice": 0.15})
    assert tracker.is_over_budget("alice") is False
    tracker.record("alice", "p1", Usage(prompt_tokens=100, completion_tokens=50, cost_usd=0.2))
    assert tracker.is_over_budget("alice") is True
    # a key with no configured budget is never over budget
    assert tracker.is_over_budget("nobody") is False


def test_spend_for_unknown_key_is_zero():
    tracker = CostTracker()
    assert tracker.spend_for_key("ghost") == 0.0
