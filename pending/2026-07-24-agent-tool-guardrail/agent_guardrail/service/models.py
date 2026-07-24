"""Pydantic request/response models for the guardrail REST service."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EvaluateRequest(BaseModel):
    tool_name: str = Field(..., description="Name of the tool the agent wants to call.")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Proposed call arguments.")
    session_id: str = Field(default="default", description="Session used for tracing and budgeting.")
    estimated_cost: float | None = Field(
        default=None, description="Optional cost estimate for this call, for budgeting."
    )


class EvaluateResponse(BaseModel):
    allowed: bool
    tool_name: str
    reason: str | None = None
    max_calls_per_minute: int | None = None
    max_cost_per_call: float | None = None
    redact_output: bool = False
    budget_remaining: float | None = None


class RecordRequest(BaseModel):
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    decision: str
    output: Any = None
    error: str | None = None
    cost: float = 0.0
    duration_ms: float = 0.0
    session_id: str = "default"


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
