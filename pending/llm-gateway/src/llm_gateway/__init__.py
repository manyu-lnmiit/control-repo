"""llm-gateway: a unified multi-provider LLM gateway.

Provides rule-based routing across LLM providers, automatic failover,
per-key rate limiting, and token/cost accounting behind a single,
OpenAI-compatible chat completion interface.
"""

from llm_gateway.gateway import Gateway
from llm_gateway.models import ChatMessage, ChatRequest, ChatResponse, Usage

__all__ = [
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "Gateway",
    "Usage",
]

__version__ = "0.1.0"
