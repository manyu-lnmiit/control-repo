"""Core data models shared across the gateway."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum


class Role(str, Enum):
    """Chat message role, mirroring the OpenAI chat schema."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True)
class ChatMessage:
    """A single turn in a chat conversation."""

    role: Role
    content: str

    def to_dict(self) -> dict:
        return {"role": self.role.value, "content": self.content}

    @staticmethod
    def from_dict(data: dict) -> ChatMessage:
        return ChatMessage(role=Role(data["role"]), content=data["content"])


@dataclass
class ChatRequest:
    """A normalized, provider-agnostic chat completion request."""

    model: str
    messages: list[ChatMessage]
    temperature: float = 0.7
    max_tokens: int | None = None
    api_key_id: str = "default"
    task_hint: str | None = None
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def prompt_chars(self) -> int:
        return sum(len(m.content) for m in self.messages)


@dataclass
class Usage:
    """Token usage and derived cost for a single completion."""

    prompt_tokens: int
    completion_tokens: int
    cost_usd: float

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class ChatResponse:
    """A normalized chat completion response returned to the caller."""

    request_id: str
    provider: str
    model: str
    content: str
    usage: Usage
    latency_ms: float
    attempts: int = 1
    created: float = field(default_factory=time.time)

    def to_openai_dict(self) -> dict:
        """Render as an OpenAI-compatible chat.completion payload."""
        return {
            "id": f"chatcmpl-{self.request_id}",
            "object": "chat.completion",
            "created": int(self.created),
            "model": self.model,
            "provider": self.provider,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": self.content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": self.usage.prompt_tokens,
                "completion_tokens": self.usage.completion_tokens,
                "total_tokens": self.usage.total_tokens,
                "cost_usd": round(self.usage.cost_usd, 6),
            },
            "gateway": {
                "latency_ms": round(self.latency_ms, 2),
                "attempts": self.attempts,
            },
        }


class ProviderError(RuntimeError):
    """Raised by a provider adapter when a request fails."""

    def __init__(self, provider: str, message: str, retryable: bool = True):
        super().__init__(f"[{provider}] {message}")
        self.provider = provider
        self.retryable = retryable


class RateLimitExceeded(RuntimeError):
    """Raised when a caller exceeds its configured rate limit."""

    def __init__(self, key_id: str, retry_after_s: float):
        super().__init__(f"rate limit exceeded for '{key_id}', retry after {retry_after_s:.2f}s")
        self.key_id = key_id
        self.retry_after_s = retry_after_s


class AllProvidersFailedError(RuntimeError):
    """Raised when every candidate provider in a routing chain fails."""

    def __init__(self, model: str, errors: list[str]):
        super().__init__(f"all providers failed for model '{model}': {'; '.join(errors)}")
        self.model = model
        self.errors = errors
