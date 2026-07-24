import pytest

from agent_guardrail.budget import CostBudget, RateLimiter
from agent_guardrail.exceptions import (
    BudgetExceededError,
    GuardedToolError,
    PolicyViolation,
    RateLimitExceededError,
)
from agent_guardrail.guard import guard
from agent_guardrail.tracing import TraceRecorder


def test_guard_allows_and_traces_success(policy, trace_path):
    tracer = TraceRecorder(trace_path)

    @guard(policy=policy, tracer=tracer)
    def search_web(query: str) -> str:
        return f"results for {query}"

    result = search_web(query="agents")
    assert result == "results for agents"
    events = tracer.events
    assert len(events) == 1
    assert events[0].decision == "allowed"
    assert events[0].arguments == {"query": "agents"}


def test_guard_denies_disallowed_tool(policy, trace_path):
    tracer = TraceRecorder(trace_path)

    @guard(policy=policy, tracer=tracer, tool_name="send_email")
    def send_email(to: str, body: str) -> str:
        return "sent"

    with pytest.raises(PolicyViolation):
        send_email(to="a@b.com", body="hi")

    events = tracer.events
    assert events[0].decision == "denied"


def test_guard_denies_bad_arguments(policy, trace_path):
    tracer = TraceRecorder(trace_path)

    @guard(policy=policy, tracer=tracer)
    def search_web(query: str) -> str:
        return "never reached"

    with pytest.raises(PolicyViolation):
        search_web(query="")


def test_guard_wraps_underlying_exception(policy, trace_path):
    tracer = TraceRecorder(trace_path)

    @guard(policy=policy, tracer=tracer)
    def read_file(path: str) -> str:
        raise FileNotFoundError(path)

    with pytest.raises(GuardedToolError):
        read_file(path="/nope")

    events = tracer.events
    assert events[0].decision == "error"


def test_guard_redacts_output_when_configured(policy, trace_path):
    tracer = TraceRecorder(trace_path)

    @guard(policy=policy, tracer=tracer)
    def search_web(query: str) -> str:
        return "contact jane@example.com for details"

    result = search_web(query="contact info")
    assert result == "contact [REDACTED:EMAIL] for details"


def test_guard_enforces_rate_limit(policy, trace_path):
    tracer = TraceRecorder(trace_path)
    limiter = RateLimiter()

    @guard(policy=policy, tracer=tracer, rate_limiter=limiter)
    def search_web(query: str) -> str:
        return "ok"

    for _ in range(3):
        search_web(query="q")

    with pytest.raises(RateLimitExceededError):
        search_web(query="q")


def test_guard_enforces_budget(policy, trace_path):
    tracer = TraceRecorder(trace_path)
    budget = CostBudget(max_total_cost=0.015)

    @guard(policy=policy, tracer=tracer, budget=budget)
    def search_web(query: str) -> str:
        return "ok"

    search_web(query="q1")  # costs 0.01, within budget
    with pytest.raises(BudgetExceededError):
        search_web(query="q2")  # would bring total to 0.02 > 0.015


def test_guard_custom_cost_fn(policy, trace_path):
    tracer = TraceRecorder(trace_path)
    budget = CostBudget(max_total_cost=1.0)

    @guard(policy=policy, tracer=tracer, budget=budget, cost_fn=lambda query: 0.5)
    def search_web(query: str) -> str:
        return "ok"

    search_web(query="q1")
    assert budget.spent == pytest.approx(0.5)
