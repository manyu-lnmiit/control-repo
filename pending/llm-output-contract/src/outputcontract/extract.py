"""Locate JSON-ish payloads inside noisy LLM responses.

Models rarely return a bare JSON document. They wrap it in markdown fences,
prefix it with "Sure! Here is the JSON you asked for:", append a closing
remark, or emit a chain-of-thought preamble. This module extracts the most
plausible candidate payloads from that noise, ranked best-first, without ever
executing or evaluating the text.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass

from outputcontract.errors import ExtractionError

_FENCE_RE = re.compile(
    r"```[ \t]*(?P<lang>[A-Za-z0-9_+-]*)[ \t]*\r?\n(?P<body>.*?)(?:```|\Z)",
    re.DOTALL,
)

_OPENERS = {"{": "}", "[": "]"}


@dataclass(frozen=True)
class Candidate:
    """A candidate JSON payload discovered inside a raw response.

    Attributes:
        text: The raw substring believed to contain JSON.
        start: Offset of the candidate within the original response.
        source: Where the candidate came from (``fence``, ``scan`` or ``raw``).
        score: Heuristic confidence; higher is tried first.
    """

    text: str
    start: int
    source: str
    score: float

    def __len__(self) -> int:  # pragma: no cover - trivial
        return len(self.text)


def _iter_balanced_spans(text: str) -> Iterator[tuple[int, int]]:
    """Yield ``(start, end)`` spans of balanced ``{...}`` / ``[...]`` regions.

    The scanner is string- and escape-aware so that braces inside string
    literals do not corrupt the nesting depth. Unterminated regions are still
    yielded (ending at the end of input) because the repair stage can often
    close them.
    """
    depth = 0
    start = -1
    closer = ""
    in_string = False
    quote = ""
    escaped = False

    for index, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                in_string = False
            continue

        if char in ('"', "'"):
            if depth > 0:
                in_string = True
                quote = char
            continue

        if char in _OPENERS:
            if depth == 0:
                start = index
                closer = _OPENERS[char]
            depth += 1
        elif char in ("}", "]"):
            if depth == 0:
                continue
            depth -= 1
            if depth == 0 and start >= 0:
                end = index + 1
                if char == closer:
                    yield start, end
                start = -1

    if depth > 0 and start >= 0:
        yield start, len(text)


def _score(text: str, source: str) -> float:
    """Heuristic ranking: prefer fenced, object-shaped, longer payloads."""
    score = 0.0
    if source == "fence":
        score += 3.0
    stripped = text.strip()
    if stripped.startswith("{"):
        score += 2.0
    elif stripped.startswith("["):
        score += 1.5
    if stripped.endswith(("}", "]")):
        score += 1.0
    score += min(len(stripped), 4000) / 4000.0
    return score


_JSONISH_RE = re.compile(r"""^(?:[{\["']|-?\d|true|false|null)""", re.IGNORECASE)


def _looks_jsonish(text: str) -> bool:
    """Cheap guard so free-form prose is not treated as a raw candidate."""
    return bool(_JSONISH_RE.match(text.strip()))


def find_candidates(raw: str) -> list[Candidate]:
    """Return plausible JSON payloads inside ``raw``, best candidate first."""
    if not isinstance(raw, str):
        raise TypeError(f"expected str, got {type(raw).__name__}")

    candidates: list[Candidate] = []
    seen: set[str] = set()

    def add(text: str, start: int, source: str) -> None:
        stripped = text.strip()
        if len(stripped) < 2:
            return
        key = f"{start}:{stripped}"
        if key in seen:
            return
        seen.add(key)
        candidates.append(Candidate(stripped, start, source, _score(stripped, source)))

    for match in _FENCE_RE.finditer(raw):
        lang = (match.group("lang") or "").lower()
        if lang and lang not in {"json", "json5", "jsonc", "javascript", "js", "python", ""}:
            continue
        body = match.group("body")
        offset = match.start("body")
        inner = list(_iter_balanced_spans(body))
        if inner:
            for start, end in inner:
                add(body[start:end], offset + start, "fence")
        else:
            add(body, offset, "fence")

    for start, end in _iter_balanced_spans(raw):
        add(raw[start:end], start, "scan")

    stripped = raw.strip()
    if stripped and not stripped.startswith("```") and _looks_jsonish(stripped):
        add(stripped, 0, "raw")

    candidates.sort(key=lambda c: (-c.score, c.start))
    return candidates


def extract(raw: str) -> str:
    """Return the single most plausible JSON payload in ``raw``.

    Raises:
        ExtractionError: if nothing resembling a payload can be found.
    """
    candidates = find_candidates(raw)
    if not candidates:
        raise ExtractionError("no JSON-like payload found in response", raw=raw)
    return candidates[0].text
