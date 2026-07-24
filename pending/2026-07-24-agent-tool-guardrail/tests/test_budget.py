import pytest

from agent_guardrail.budget import CostBudget, RateLimiter
from agent_guardrail.exceptions import BudgetExceededError, RateLimitExceededError


def test_budget_charges_and_tracks_remaining():
    budget = CostBudget(max_total_cost=1.0)
    budget.charge(0.4, tool_name="search_web")
    assert budget.spent == pytest.approx(0.4)
    assert budget.remaining == pytest.approx(0.6)


def test_budget_raises_when_exceeded():
    budget = CostBudget(max_total_cost=1.0)
    budget.charge(0.9, tool_name="search_web")
    with pytest.raises(BudgetExceededError):
        budget.charge(0.2, tool_name="search_web")
    # failed charge should not partially apply
    assert budget.spent == pytest.approx(0.9)


def test_budget_reset():
    budget = CostBudget(max_total_cost=1.0)
    budget.charge(0.5)
    budget.reset()
    assert budget.spent == 0.0


def test_budget_rejects_negative_amount():
    budget = CostBudget(max_total_cost=1.0)
    with pytest.raises(ValueError):
        budget.charge(-1.0)


def test_rate_limiter_allows_under_limit():
    limiter = RateLimiter()
    now = 1000.0
    for i in range(3):
        limiter.check_and_record("tool_a", max_calls_per_minute=3, now=now + i)


def test_rate_limiter_blocks_over_limit():
    limiter = RateLimiter()
    now = 1000.0
    for i in range(3):
        limiter.check_and_record("tool_a", max_calls_per_minute=3, now=now + i)
    with pytest.raises(RateLimitExceededError):
        limiter.check_and_record("tool_a", max_calls_per_minute=3, now=now + 3)


def test_rate_limiter_window_slides():
    limiter = RateLimiter()
    now = 1000.0
    for i in range(3):
        limiter.check_and_record("tool_a", max_calls_per_minute=3, now=now + i)
    # 61 seconds later the earliest calls should have fallen out of the window
    limiter.check_and_record("tool_a", max_calls_per_minute=3, now=now + 61)


def test_rate_limiter_none_limit_is_noop():
    limiter = RateLimiter()
    for i in range(100):
        limiter.check_and_record("unlimited_tool", max_calls_per_minute=None, now=float(i))
