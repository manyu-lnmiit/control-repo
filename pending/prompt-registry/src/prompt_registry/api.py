"""Optional FastAPI HTTP service exposing the registry to other services.

This module is only imported when the ``api`` extra is installed
(``pip install prompt-registry[api]``); the core library has zero
third-party dependencies and works fully offline via :mod:`prompt_registry.store`.
"""

from __future__ import annotations

import os
from typing import Any

try:
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel
except ImportError as exc:  # pragma: no cover - exercised only without the extra
    raise ImportError(
        "prompt_registry.api requires the 'api' extra: pip install prompt-registry[api]"
    ) from exc

from prompt_registry.store import PromptNotFoundError, PromptRegistry, VersionNotFoundError
from prompt_registry.template import MissingVariableError

DB_PATH = os.environ.get("PROMPT_REGISTRY_DB", "prompt_registry.db")

app = FastAPI(title="prompt-registry", version="0.1.0")
_registry = PromptRegistry(DB_PATH)


class CommitRequest(BaseModel):
    body: str
    message: str = ""
    tags: list | None = None
    metadata: dict[str, Any] | None = None


class RenderRequest(BaseModel):
    variables: dict[str, Any] = {}
    version: int | None = None
    tag: str | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/prompts/{name}/commits")
def commit(name: str, req: CommitRequest) -> dict[str, Any]:
    pv = _registry.commit(name, req.body, message=req.message, tags=req.tags, metadata=req.metadata)
    return pv.as_dict()


@app.get("/prompts/{name}")
def latest(name: str) -> dict[str, Any]:
    try:
        return _registry.get(name).as_dict()
    except PromptNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/prompts/{name}/versions/{version}")
def get_version(name: str, version: int) -> dict[str, Any]:
    try:
        return _registry.get(name, version).as_dict()
    except VersionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/prompts/{name}/history")
def history(name: str) -> list:
    try:
        return [pv.as_dict() for pv in _registry.history(name)]
    except PromptNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/prompts/{name}/render")
def render(name: str, req: RenderRequest) -> dict[str, Any]:
    try:
        result = _registry.render(name, variables=req.variables, version=req.version, tag=req.tag)
    except (PromptNotFoundError, VersionNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MissingVariableError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "text": result.text,
        "name": result.name,
        "version": result.version,
        "variables_used": result.variables_used,
    }
