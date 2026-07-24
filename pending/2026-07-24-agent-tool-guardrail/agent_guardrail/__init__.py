"""agent_guardrail: a policy enforcement, observability and replay layer for
LLM agent tool calls.

Wrap any Python callable that an LLM agent uses as a "tool" with
`guard()` and get, for free:

* JSON-schema argument validation
* allow/deny + per-tool rate limiting
* token / dollar cost budgeting
* PII redaction of tool outputs before they are handed back to the model
* durable JSONL tracing of every call (input, output, decision, timing)
* deterministic replay of a recorded session against a mock tool set

See the project README for a full walkthrough.
"""

from agent_guardrail.budget import (
    BudgetExceededError,
    CostBudget,
    RateLimiter,
    RateLimitExceededError,
)
from agent_guardrail.guard import GuardedToolError, guard
from agent_guardrail.policy import Policy, PolicyEngine, PolicyRule, PolicyViolation
from agent_guardrail.redact import redact_pii
from agent_guardrail.replay import ReplayEngine, ReplayMismatchError
from agent_guardrail.tracing import TraceEvent, TraceRecorder

__version__ = "0.1.0"

__all__ = [
    "Policy",
    "PolicyEngine",
    "PolicyRule",
    "PolicyViolation",
    "CostBudget",
    "BudgetExceededError",
    "RateLimiter",
    "RateLimitExceededError",
    "redact_pii",
    "TraceEvent",
    "TraceRecorder",
    "guard",
    "GuardedToolError",
    "ReplayEngine",
    "ReplayMismatchError",
]
