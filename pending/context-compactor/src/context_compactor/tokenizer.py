"""Token counting abstractions.

By default context_compactor uses a dependency-free approximate tokenizer so
the library works with zero extra installs. If `tiktoken` is available (and
the caller asks for it), a more accurate provider-specific tokenizer is used
instead.
"""

from __future__ import annotations

import math
import re
from typing import Protocol


class Tokenizer(Protocol):
    """Anything that can estimate/compute a token count for a string."""

    def count(self, text: str) -> int: ...


_WORD_RE = re.compile(r"\S+")


class SimpleTokenizer:
    """A dependency-free approximate tokenizer.

    Uses a blended heuristic (~4 characters per token, with a whitespace-word
    floor) that tracks real BPE tokenizers closely enough for budgeting
    purposes without requiring any third-party package.
    """

    CHARS_PER_TOKEN = 4.0

    def count(self, text: str) -> int:
        if not text or not text.strip():
            return 0
        stripped = text.strip()
        char_estimate = math.ceil(len(stripped) / self.CHARS_PER_TOKEN)
        word_count = len(_WORD_RE.findall(stripped))
        # Real tokenizers rarely produce fewer tokens than ~0.75 * word count
        # (punctuation, subword splits) nor drastically more than word count
        # for typical English/code text, so we blend the two signals.
        return max(char_estimate, math.ceil(word_count * 0.75), 1)


class TiktokenTokenizer:
    """Wraps `tiktoken` for accurate OpenAI-model token counts, when installed."""

    def __init__(self, encoding_name: str = "cl100k_base") -> None:
        try:
            import tiktoken  # type: ignore
        except ImportError as exc:  # pragma: no cover - exercised only without the optional dep
            raise ImportError(
                "tiktoken is not installed. Install it with `pip install tiktoken` "
                "or use SimpleTokenizer / get_default_tokenizer() instead."
            ) from exc
        self._encoding = tiktoken.get_encoding(encoding_name)

    def count(self, text: str) -> int:
        if not text:
            return 0
        return len(self._encoding.encode(text))


def get_default_tokenizer(prefer_tiktoken: bool = False) -> Tokenizer:
    """Return the best available tokenizer.

    Args:
        prefer_tiktoken: if True, try to use tiktoken and silently fall back
            to SimpleTokenizer if it isn't installed.
    """
    if prefer_tiktoken:
        try:
            return TiktokenTokenizer()
        except ImportError:
            pass
    return SimpleTokenizer()
