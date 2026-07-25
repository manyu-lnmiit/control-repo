"""FastAPI application exposing trace query endpoints and a timeline viewer."""

from __future__ import annotations

import json
import os
from importlib import resources

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from agent_trace_lens.models import Span, TraceSummary
from agent_trace_lens.storage import SQLiteStorage

DEFAULT_DB_PATH = os.environ.get("AGENT_TRACE_LENS_DB", "agent_trace_lens.db")


def _build_depth_map(spans: list[Span]) -> dict[str, int]:
    """Compute the nesting depth of each span for indentation in the timeline."""
    by_id = {s.id: s for s in spans}
    depth: dict[str, int] = {}

    def _depth_of(span_id: str) -> int:
        if span_id in depth:
            return depth[span_id]
        s = by_id.get(span_id)
        if s is None or s.parent_id is None or s.parent_id not in by_id:
            depth[span_id] = 0
        else:
            depth[span_id] = _depth_of(s.parent_id) + 1
        return depth[span_id]

    for s in spans:
        _depth_of(s.id)
    return depth


def create_app(db_path: str | None = None) -> FastAPI:
    """Application factory so tests can point at an isolated database."""
    storage = SQLiteStorage(db_path or DEFAULT_DB_PATH)
    app = FastAPI(
        title="agent-trace-lens",
        description="Tracing, storage, and timeline visualization for multi-agent LLM systems.",
        version="0.1.0",
    )
    app.state.storage = storage

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/traces", response_model=list[TraceSummary])
    def list_traces(limit: int = 50) -> list[TraceSummary]:
        return storage.list_traces(limit=limit)

    @app.get("/traces/{trace_id}", response_model=list[Span])
    def get_trace(trace_id: str) -> list[Span]:
        spans = storage.get_trace(trace_id)
        if not spans:
            raise HTTPException(status_code=404, detail="trace not found")
        return spans

    @app.delete("/traces/{trace_id}")
    def delete_trace(trace_id: str) -> dict:
        storage.delete_trace(trace_id)
        return {"status": "deleted", "trace_id": trace_id}

    @app.get("/traces/{trace_id}/timeline", response_class=HTMLResponse)
    def timeline(trace_id: str) -> HTMLResponse:
        spans = storage.get_trace(trace_id)
        depth_map = _build_depth_map(spans)
        payload = [
            {
                "name": s.name,
                "kind": s.kind.value,
                "status": s.status.value,
                "error": s.error,
                "start_time": s.start_time,
                "end_time": s.end_time,
                "depth": depth_map.get(s.id, 0),
            }
            for s in spans
        ]
        template = resources.files("agent_trace_lens.web").joinpath("timeline.html").read_text()
        html = template.replace("{{TRACE_ID}}", trace_id).replace(
            "{{SPANS_JSON}}", json.dumps(payload)
        )
        return HTMLResponse(content=html)

    return app


app = create_app()
