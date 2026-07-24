"""FastAPI application exposing agent_guardrail as a sidecar service.

Run with:

    uvicorn agent_guardrail.service.app:app --host 0.0.0.0 --port 8080

Environment variables (see .env.example):
    GUARDRAIL_POLICY_PATH   Path to the YAML policy file (default: policies/example_policy.yaml)
    GUARDRAIL_TRACE_PATH    Path to the JSONL trace file to append to (default: traces/service.jsonl)
    GUARDRAIL_MAX_BUDGET    Optional float; total cost budget for the process lifetime.
"""

from __future__ import annotations

import os
import time

from fastapi import FastAPI, HTTPException

from agent_guardrail import __version__
from agent_guardrail.budget import CostBudget, RateLimiter
from agent_guardrail.exceptions import GuardrailError
from agent_guardrail.policy import Policy, PolicyEngine
from agent_guardrail.service.models import (
    EvaluateRequest,
    EvaluateResponse,
    HealthResponse,
    RecordRequest,
)
from agent_guardrail.tracing import TraceEvent, TraceRecorder

POLICY_PATH = os.environ.get("GUARDRAIL_POLICY_PATH", "policies/example_policy.yaml")
TRACE_PATH = os.environ.get("GUARDRAIL_TRACE_PATH", "traces/service.jsonl")
MAX_BUDGET = os.environ.get("GUARDRAIL_MAX_BUDGET")

app = FastAPI(
    title="agent-guardrail",
    description="Policy enforcement, budgeting and tracing sidecar for LLM agent tool calls.",
    version=__version__,
)

_rate_limiter = RateLimiter()
_budget: CostBudget | None = CostBudget(float(MAX_BUDGET)) if MAX_BUDGET else None


def _load_policy() -> Policy:
    if os.path.exists(POLICY_PATH):
        return Policy.from_yaml(POLICY_PATH)
    return Policy(rules={}, default_allowed=False)


def _get_tracer() -> TraceRecorder:
    # A fresh recorder per request is cheap (append-only file) and keeps the
    # service stateless/restart-safe; call_ids are unique per-recorder call.
    return TraceRecorder(TRACE_PATH)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", version=__version__)


@app.post("/evaluate", response_model=EvaluateResponse)
def evaluate(req: EvaluateRequest) -> EvaluateResponse:
    policy = _load_policy()
    engine = PolicyEngine(policy)

    try:
        rule = engine.check(req.tool_name, req.arguments)
    except GuardrailError as exc:
        return EvaluateResponse(allowed=False, tool_name=req.tool_name, reason=str(exc))

    try:
        _rate_limiter.check_and_record(req.tool_name, rule.max_calls_per_minute, time.time())
    except GuardrailError as exc:
        return EvaluateResponse(allowed=False, tool_name=req.tool_name, reason=str(exc))

    cost = req.estimated_cost if req.estimated_cost is not None else (rule.max_cost_per_call or 0.0)
    if _budget is not None and cost:
        try:
            _budget.charge(cost, tool_name=req.tool_name)
        except GuardrailError as exc:
            return EvaluateResponse(allowed=False, tool_name=req.tool_name, reason=str(exc))

    return EvaluateResponse(
        allowed=True,
        tool_name=req.tool_name,
        max_calls_per_minute=rule.max_calls_per_minute,
        max_cost_per_call=rule.max_cost_per_call,
        redact_output=rule.redact_output,
        budget_remaining=_budget.remaining if _budget is not None else None,
    )


@app.post("/record")
def record(req: RecordRequest) -> dict:
    tracer = _get_tracer()
    call_id = tracer.next_call_id()
    tracer.record(
        TraceEvent(
            call_id=call_id,
            tool_name=req.tool_name,
            arguments=req.arguments,
            decision=req.decision,
            output=req.output,
            error=req.error,
            cost=req.cost,
            duration_ms=req.duration_ms,
            started_at=time.time(),
            session_id=req.session_id,
        )
    )
    return {"recorded": True, "call_id": call_id}


@app.get("/trace/{session_id}")
def get_trace(session_id: str) -> list:
    if not os.path.exists(TRACE_PATH):
        raise HTTPException(status_code=404, detail="no trace recorded yet")
    events = TraceRecorder.load(TRACE_PATH)
    return [e.to_dict() for e in events if e.session_id == session_id]
