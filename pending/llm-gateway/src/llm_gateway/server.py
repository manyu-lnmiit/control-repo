"""FastAPI app exposing an OpenAI-compatible gateway HTTP API."""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from llm_gateway.config import DEFAULT_CONFIG_YAML, GatewayConfig
from llm_gateway.gateway import Gateway
from llm_gateway.models import (
    AllProvidersFailedError,
    ChatMessage,
    ChatRequest,
    RateLimitExceeded,
    Role,
)


class ChatMessageIn(BaseModel):
    role: str
    content: str


class ChatCompletionIn(BaseModel):
    model: str
    messages: list[ChatMessageIn]
    temperature: float = 0.7
    max_tokens: int | None = None
    task_hint: str | None = None


def create_app(gateway: Gateway | None = None) -> FastAPI:
    """Build the FastAPI app around a Gateway instance.

    If `gateway` isn't supplied, config is loaded from the path in the
    `LLM_GATEWAY_CONFIG` environment variable, falling back to a small
    built-in mock-provider config so the server is runnable out of the box.
    """
    if gateway is None:
        config_path = os.environ.get("LLM_GATEWAY_CONFIG")
        cfg = (
            GatewayConfig.from_yaml(config_path)
            if config_path
            else GatewayConfig.from_yaml_string(DEFAULT_CONFIG_YAML)
        )
        gateway = cfg.build_gateway()

    app = FastAPI(title="llm-gateway", version="0.1.0")
    app.state.gateway = gateway

    @app.get("/healthz")
    async def healthz() -> dict[str, Any]:
        return {"status": "ok", "providers": list(gateway.providers.keys())}

    @app.get("/v1/stats")
    async def stats() -> dict[str, Any]:
        return gateway.stats()

    @app.post("/v1/chat/completions")
    async def chat_completions(
        body: ChatCompletionIn, authorization: str | None = Header(default=None)
    ) -> dict[str, Any]:
        api_key_id = "default"
        if authorization and authorization.lower().startswith("bearer "):
            api_key_id = authorization.split(" ", 1)[1].strip() or "default"

        request = ChatRequest(
            model=body.model,
            messages=[ChatMessage(role=Role(m.role), content=m.content) for m in body.messages],
            temperature=body.temperature,
            max_tokens=body.max_tokens,
            api_key_id=api_key_id,
            task_hint=body.task_hint,
        )

        try:
            response = await gateway.chat(request)
        except RateLimitExceeded as exc:
            raise HTTPException(status_code=429, detail=str(exc)) from exc
        except AllProvidersFailedError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        return response.to_openai_dict()

    return app


app = create_app()
