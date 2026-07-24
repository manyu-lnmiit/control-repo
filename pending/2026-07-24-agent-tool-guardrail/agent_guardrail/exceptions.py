"""Shared exception hierarchy for agent_guardrail."""


class GuardrailError(Exception):
    """Base class for all agent_guardrail errors."""


class PolicyViolation(GuardrailError):
    """Raised when a tool call is denied by policy (deny-list, missing rule,
    or JSON-schema argument validation failure)."""


class BudgetExceededError(GuardrailError):
    """Raised when a tool call would exceed the configured cost budget."""


class RateLimitExceededError(GuardrailError):
    """Raised when a tool call exceeds the configured rate limit."""


class GuardedToolError(GuardrailError):
    """Wraps an exception raised by the underlying tool function itself,
    after it has already been recorded in the trace."""


class ReplayMismatchError(GuardrailError):
    """Raised during replay when the live call sequence diverges from the
    recorded trace (different tool name or arguments at a given step)."""
