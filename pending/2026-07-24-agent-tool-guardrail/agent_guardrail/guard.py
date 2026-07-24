"""The `guard()` wrapper: the main entry point of the library.

`guard()` wraps a plain Python callable (an agent "tool") and returns a new
callable with the exact same signature that additionally:

1. Validates arguments against the tool's JSON-schema (if any).
2. Enforces allow/deny policy.
3. Enforces a per-tool rate limit.
4. Estimates & charges cost against a shared `CostBudget`.
5. Calls the underlying tool.
6. Optionally redacts PII from the output.
7. Records everything to a `TraceRecorder`.

Any violation raises before the underlying tool is ever invoked, so guarded
tools are safe to expose directly to an LLM's function-calling loop.
"""

from __future__ import annotations

import functools
import time
from collections.abc import Callable
from typing import Any

from agent_guardrail.budget import CostBudget, RateLimiter
from agent_guardrail.exceptions import (
    BudgetExceededError,
    GuardedToolError,
    PolicyViolation,
    RateLimitExceededError,
)
from agent_guardrail.policy import Policy, PolicyEngine
from agent_guardrail.redact import redact_pii
from agent_guardrail.tracing import TraceEvent, TraceRecorder

__all__ = ["guard", "GuardedToolError"]


def guard(
    fn: Callable | None = None,
    *,
    policy: Policy,
    tracer: TraceRecorder | None = None,
    budget: CostBudget | None = None,
    rate_limiter: RateLimiter | None = None,
    tool_name: str | None = None,
    cost_fn: Callable[..., float] | None = None,
):
    """Wrap `fn` with policy enforcement, budgeting and tracing.

    Can be used as ``guard(my_tool, policy=policy)`` or as a decorator
    factory: ``@guard(policy=policy)``.

    Args:
        fn: the tool function to wrap (positional use).
        policy: the `Policy` governing this (and other) tools.
        tracer: optional `TraceRecorder` to log every call to.
        budget: optional `CostBudget` shared across guarded calls.
        rate_limiter: optional `RateLimiter` to share across multiple
            guarded tools/processes. If omitted, a fresh `RateLimiter`
            dedicated to this guarded function is created.
        tool_name: override the tool name used for policy lookup / tracing
            (defaults to ``fn.__name__``).
        cost_fn: optional ``(*args, **kwargs) -> float`` callable used to
            estimate the cost of a call for budgeting purposes. Falls back
            to the rule's ``max_cost_per_call`` (charged in full) if not
            provided.
    """

    def decorator(func: Callable) -> Callable:
        name = tool_name or func.__name__
        engine = PolicyEngine(policy)
        limiter = rate_limiter or RateLimiter()

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            call_id = tracer.next_call_id() if tracer else -1
            started_at = time.time()
            arguments = _bind_arguments(func, args, kwargs)

            def _record(decision: str, output: Any = None, error: str | None = None, cost: float = 0.0):
                if tracer is None:
                    return
                duration_ms = (time.time() - started_at) * 1000.0
                tracer.record(
                    TraceEvent(
                        call_id=call_id,
                        tool_name=name,
                        arguments=arguments,
                        decision=decision,
                        output=output,
                        error=error,
                        cost=cost,
                        duration_ms=duration_ms,
                        started_at=started_at,
                        session_id=tracer.session_id,
                    )
                )

            # 1 & 2: schema validation + allow/deny
            try:
                rule = engine.check(name, arguments)
            except PolicyViolation as exc:
                _record("denied", error=str(exc))
                raise

            # 3: rate limiting
            try:
                limiter.check_and_record(name, rule.max_calls_per_minute, time.time())
            except RateLimitExceededError as exc:
                _record("denied", error=str(exc))
                raise

            # 4: budgeting
            estimated_cost = 0.0
            if cost_fn is not None:
                estimated_cost = float(cost_fn(*args, **kwargs))
            elif rule.max_cost_per_call is not None:
                estimated_cost = float(rule.max_cost_per_call)

            if budget is not None and estimated_cost > 0:
                try:
                    budget.charge(estimated_cost, tool_name=name)
                except BudgetExceededError as exc:
                    _record("denied", error=str(exc))
                    raise

            # 5: call the underlying tool
            try:
                output = func(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001 - deliberately broad, re-raised wrapped
                _record("error", error=str(exc), cost=estimated_cost)
                raise GuardedToolError(f"tool '{name}' raised: {exc}") from exc

            # 6: redact
            if rule.redact_output:
                output = redact_pii(output)

            # 7: trace success
            _record("allowed", output=output, cost=estimated_cost)
            return output

        wrapper.__guardrail_tool_name__ = name  # type: ignore[attr-defined]
        return wrapper

    if fn is not None:
        return decorator(fn)
    return decorator


def _bind_arguments(func: Callable, args: tuple, kwargs: dict) -> dict:
    """Best-effort mapping of positional+keyword args to a name->value dict
    for schema validation / tracing. Falls back to a generic layout if
    introspection fails (e.g. builtins)."""
    import inspect

    try:
        sig = inspect.signature(func)
        bound = sig.bind_partial(*args, **kwargs)
        bound.apply_defaults()
        return dict(bound.arguments)
    except (TypeError, ValueError):
        return {"args": list(args), "kwargs": kwargs}
