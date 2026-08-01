"""OpenAI-compatible HTTP provider adapter.

Works against the real OpenAI API or any OpenAI-compatible endpoint
(Azure OpenAI, vLLM, Ollama's OpenAI shim, etc.) by pointing ``base_url``
at the desired host. Requires an API key supplied via constructor or the
``OPENAI_API_KEY`` environment variable -- never hardcode credentials.
"""

from __future__ import annotations

import os

import httpx

from llm_gateway.models import ChatRequest, ProviderError, Usage
from llm_gateway.providers.base import Provider


class OpenAICompatibleProvider(Provider):
    """Calls a `/chat/completions` endpoint using the OpenAI wire format."""

    def __init__(
        self,
        name: str = "openai",
        base_url: str = "https://api.openai.com/v1",
        api_key_env: str = "OPENAI_API_KEY",
        api_key: str | None = None,
        price_per_1k_prompt: float = 0.5,
        price_per_1k_completion: float = 1.5,
        timeout_s: float = 30.0,
    ):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key_env = api_key_env
        self._api_key = api_key
        self.price_per_1k_prompt = price_per_1k_prompt
        self.price_per_1k_completion = price_per_1k_completion
        self.timeout_s = timeout_s

    def _resolve_key(self) -> str:
        key = self._api_key or os.environ.get(self.api_key_env)
        if not key:
            raise ProviderError(
                self.name,
                f"missing API key: set the {self.api_key_env} environment variable",
                retryable=False,
            )
        return key

    async def complete(self, request: ChatRequest) -> tuple[str, Usage]:
        key = self._resolve_key()
        payload = {
            "model": request.model,
            "messages": [m.to_dict() for m in request.messages],
            "temperature": request.temperature,
        }
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens

        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

        try:
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                resp = await client.post(
                    f"{self.base_url}/chat/completions", json=payload, headers=headers
                )
        except httpx.TimeoutException as exc:
            raise ProviderError(self.name, f"timeout: {exc}", retryable=True) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(self.name, f"transport error: {exc}", retryable=True) from exc

        if resp.status_code == 429:
            raise ProviderError(self.name, "rate limited by upstream", retryable=True)
        if resp.status_code >= 500:
            raise ProviderError(self.name, f"upstream error {resp.status_code}", retryable=True)
        if resp.status_code >= 400:
            raise ProviderError(
                self.name, f"request rejected: {resp.status_code} {resp.text[:200]}",
                retryable=False,
            )

        data = resp.json()
        try:
            content = data["choices"][0]["message"]["content"]
            usage_raw = data.get("usage", {})
            prompt_tokens = usage_raw.get("prompt_tokens", max(1, request.prompt_chars() // 4))
            completion_tokens = usage_raw.get("completion_tokens", max(1, len(content) // 4))
        except (KeyError, IndexError) as exc:
            raise ProviderError(self.name, f"malformed response: {exc}", retryable=False) from exc

        cost = self.estimate_cost(prompt_tokens, completion_tokens)
        return content, Usage(
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, cost_usd=cost
        )
