"""llm-semantic-cache: a semantic caching layer for LLM and agent tool calls.

Public API:
    SemanticCache   - the main cache object.
    cached_llm_call - decorator that wraps any callable making an LLM call.
    HashingEmbedder  - dependency-free default embedding backend.
    OpenAIEmbedder   - optional embedding backend using the OpenAI Embeddings API.
"""

from semantic_cache.cache import SemanticCache, cached_llm_call
from semantic_cache.embeddings import EmbeddingBackend, HashingEmbedder

__all__ = [
    "EmbeddingBackend",
    "HashingEmbedder",
    "SemanticCache",
    "cached_llm_call",
]

__version__ = "0.1.0"
