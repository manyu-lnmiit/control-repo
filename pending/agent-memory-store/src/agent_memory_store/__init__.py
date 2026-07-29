"""agent-memory-store: a dependency-free long-term memory layer for LLM agents.

Provides episodic and semantic memory storage with importance-weighted
retrieval, time-based decay, and automatic consolidation of related
episodic memories into semantic summaries.
"""

from .memory import MemoryItem, MemoryType
from .store import MemoryStore

__all__ = ["MemoryItem", "MemoryStore", "MemoryType"]
__version__ = "0.1.0"
