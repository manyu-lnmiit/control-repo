"""Optional FastAPI HTTP service exposing compaction as a REST endpoint.

This module is only imported when the caller actually wants the HTTP
service (`context_compactor.api:app`), so the core library stays
dependency-free. Install the `api` extra to use it:

    pip install context-compactor[api]
    uvicorn context_compactor.api:app --reload
"""

from __future__ import annotations

from typing import Any

try:
    from fastapi import FastAPI
    from pydantic import BaseModel
except ImportError as exc:  # pragma: no cover - exercised only without the optional dep
    raise ImportError(
        "FastAPI/pydantic are required for context_compactor.api. "
        "Install with `pip install context-compactor[api]`."
    ) from exc

from context_compactor.compactor import Compactor, EvictionStrategy, TokenBudget
from context_compactor.models import Message

app = FastAPI(
    title="context-compactor",
    description="Token-budget-aware context compaction for LLM agents",
    version="0.1.0",
)


class MessageIn(BaseModel):
    role: str
    content: str
    pinned: bool = False
    importance: float | None = None
    metadata: dict[str, Any] = {}


class CompactRequest(BaseModel):
    messages: list[MessageIn]
    max_tokens: int
    reserve_tokens: int = 0
    summarize: bool = True


class MessageOut(BaseModel):
    role: str
    content: str


class CompactResponse(BaseModel):
    messages: list[MessageOut]
    input_tokens: int
    output_tokens: int
    tokens_saved: int
    dropped_messages: int
    summary_blocks_created: int


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/compact", response_model=CompactResponse)
def compact(req: CompactRequest) -> CompactResponse:
    messages = [
        Message(
            role=m.role,
            content=m.content,
            index=i,
            pinned=m.pinned,
            importance=m.importance,
            metadata=m.metadata,
        )
        for i, m in enumerate(req.messages)
    ]
    budget = TokenBudget(max_tokens=req.max_tokens, reserve_tokens=req.reserve_tokens)
    strategy = EvictionStrategy.SUMMARIZE if req.summarize else EvictionStrategy.DROP
    result = Compactor(strategy=strategy).compact(messages, budget)

    return CompactResponse(
        messages=[MessageOut(role=m.role, content=m.content) for m in result.messages],
        input_tokens=result.stats.input_tokens,
        output_tokens=result.stats.output_tokens,
        tokens_saved=result.stats.tokens_saved,
        dropped_messages=result.stats.dropped_messages,
        summary_blocks_created=result.stats.summary_blocks_created,
    )
