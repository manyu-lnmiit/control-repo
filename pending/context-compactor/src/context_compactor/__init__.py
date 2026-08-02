"""context_compactor: token-budget-aware context window management for LLM agents.

Public API surface. Import the pieces you need:

    from context_compactor import Message, Compactor, TokenBudget

See the README for a full walkthrough.
"""

from context_compactor.compactor import Compactor, TokenBudget
from context_compactor.models import CompactionResult, CompactionStats, Message
from context_compactor.scoring import DefaultImportanceScorer, ImportanceScorer
from context_compactor.summarizer import ExtractiveSummarizer, Summarizer
from context_compactor.tokenizer import SimpleTokenizer, Tokenizer, get_default_tokenizer

__version__ = "0.1.0"

__all__ = [
    "Message",
    "CompactionResult",
    "CompactionStats",
    "Tokenizer",
    "SimpleTokenizer",
    "get_default_tokenizer",
    "ImportanceScorer",
    "DefaultImportanceScorer",
    "Summarizer",
    "ExtractiveSummarizer",
    "Compactor",
    "TokenBudget",
]
