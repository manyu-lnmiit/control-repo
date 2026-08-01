"""Provider adapter interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from llm_gateway.models import ChatRequest, Usage


class Provider(ABC):
    """A backend LLM provider adapter.

    Concrete adapters translate a normalized :class:`ChatRequest` into a
    provider-specific call and return normalized text + usage. Adapters
    should raise :class:`llm_gateway.models.ProviderError` on failure and
    set ``retryable=False`` for errors a retry cannot fix (e.g. bad request).
    """

    #: unique adapter name, used in routing rules and responses
    name: str = "base"

    #: USD cost per 1K prompt / completion tokens, used for cost accounting
    price_per_1k_prompt: float = 0.0
    price_per_1k_completion: float = 0.0

    @abstractmethod
    async def complete(self, request: ChatRequest) -> tuple[str, Usage]:
        """Run a chat completion, returning (text, usage)."""
        raise NotImplementedError

    def estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        return (
            prompt_tokens / 1000 * self.price_per_1k_prompt
            + completion_tokens / 1000 * self.price_per_1k_completion
        )
