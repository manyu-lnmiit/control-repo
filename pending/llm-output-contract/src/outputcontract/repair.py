"""Deterministic repair of almost-JSON text produced by language models.

Every transformation here is a pure string rewrite. Nothing is ``eval``-ed, so
a hostile payload can at worst fail to parse. Each repair records the name of
the rule that fired, which makes the behaviour auditable and lets callers
report *why* a payload needed fixing.

Rules implemented:

``smart_quotes``      Unicode curly quotes normalised to ASCII.
``comments``          ``//`` and ``/* ... */`` comments stripped.
``single_quotes``     ``'value'`` string literals re-quoted as ``"value"``.
``unquoted_keys``     ``{key: 1}`` becomes ``{"key": 1}``.
``python_literals``   ``True`` / ``False`` / ``None`` mapped to JSON literals.
``non_finite``        ``NaN`` / ``Infinity`` mapped to ``null``.
``trailing_commas``   ``[1, 2, ]`` becomes ``[1, 2]``.
``unterminated``      Dangling strings/brackets are closed at end of input.
``concatenated``      ``{...}{...}`` collapses to a JSON array of documents.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from outputcontract.errors import RepairError

_SMART_QUOTES = {
    "“": '"',
    "”": '"',
    "„": '"',
    "‘": "'",
    "’": "'",
    "«": '"',
    "»": '"',
}

_LITERALS = {
    "True": "true",
    "False": "false",
    "None": "null",
    "TRUE": "true",
    "FALSE": "false",
    "NULL": "null",
    "None,": "null,",
    "undefined": "null",
}

_NON_FINITE = {"NaN": "null", "Infinity": "null", "-Infinity": "null"}

_BARE_KEY_RE = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$.\-]*$")


def _reject_constant(token: str) -> Any:
    """Raise on JSON non-finite constants so the rewriter handles them."""
    raise ValueError(f"non-finite constant not allowed: {token}")


@dataclass
class RepairResult:
    """Outcome of a repair attempt.

    Attributes:
        value: The decoded Python object.
        text: The repaired JSON text that was finally parsed.
        rules: Names of the repair rules that fired, in application order.
    """

    value: Any
    text: str
    rules: list[str] = field(default_factory=list)

    @property
    def repaired(self) -> bool:
        """True when at least one repair rule had to fire."""
        return bool(self.rules)


def _normalise_smart_quotes(text: str) -> tuple[str, bool]:
    changed = False
    out = []
    for char in text:
        replacement = _SMART_QUOTES.get(char)
        if replacement is not None:
            changed = True
            out.append(replacement)
        else:
            out.append(char)
    return "".join(out), changed


class _Rewriter:
    """Single-pass, string-aware rewriter for lenient JSON dialects."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.rules: set[str] = set()

    def run(self) -> str:
        out: list[str] = []
        text = self.text
        index = 0
        length = len(text)
        depth_stack: list[str] = []
        expect_key = False

        while index < length:
            char = text[index]

            if char in " \t\r\n":
                out.append(char)
                index += 1
                continue

            if char == "/" and index + 1 < length and text[index + 1] in "/*":
                index = self._skip_comment(text, index)
                self.rules.add("comments")
                continue

            if char in ('"', "'"):
                literal, index = self._read_string(text, index)
                out.append(literal)
                continue

            if char in "{[":
                depth_stack.append(char)
                expect_key = char == "{"
                out.append(char)
                index += 1
                continue

            if char in "}]":
                self._trim_trailing_comma(out)
                if depth_stack:
                    depth_stack.pop()
                expect_key = bool(depth_stack) and depth_stack[-1] == "{"
                out.append(char)
                index += 1
                continue

            if char == ",":
                expect_key = bool(depth_stack) and depth_stack[-1] == "{"
                out.append(char)
                index += 1
                continue

            if char == ":":
                expect_key = False
                out.append(char)
                index += 1
                continue

            token, index = self._read_bare_token(text, index)
            out.append(self._rewrite_token(token, expect_key))

        self._trim_trailing_comma(out)
        result = "".join(out)
        result = self._close_open_containers(result, depth_stack)
        return result

    @staticmethod
    def _skip_comment(text: str, index: int) -> int:
        if text[index + 1] == "/":
            end = text.find("\n", index)
            return len(text) if end == -1 else end
        end = text.find("*/", index + 2)
        return len(text) if end == -1 else end + 2

    def _read_string(self, text: str, index: int) -> tuple[str, int]:
        quote = text[index]
        index += 1
        chars: list[str] = []
        terminated = False
        while index < len(text):
            char = text[index]
            if char == "\\":
                if index + 1 < len(text):
                    nxt = text[index + 1]
                    if quote == "'" and nxt == "'":
                        chars.append("'")
                    else:
                        chars.append(char)
                        chars.append(nxt)
                    index += 2
                    continue
                index += 1
                continue
            if char == quote:
                terminated = True
                index += 1
                break
            if char == '"' and quote == "'":
                chars.append('\\"')
                index += 1
                continue
            if char in "\r\n":
                chars.append("\\n")
                index += 1
                continue
            chars.append(char)
            index += 1

        if quote == "'":
            self.rules.add("single_quotes")
        if not terminated:
            self.rules.add("unterminated")
        return '"' + "".join(chars) + '"', index

    @staticmethod
    def _read_bare_token(text: str, index: int) -> tuple[str, int]:
        start = index
        while index < len(text) and text[index] not in ",:{}[]\"' \t\r\n":
            index += 1
        if index == start:  # unexpected char; consume it to guarantee progress
            index += 1
        return text[start:index], index

    def _rewrite_token(self, token: str, expect_key: bool) -> str:
        if token in _NON_FINITE:
            self.rules.add("non_finite")
            return _NON_FINITE[token]
        if token in _LITERALS:
            if token in {"True", "False", "None", "undefined"}:
                self.rules.add("python_literals")
            return _LITERALS[token]
        if token in {"true", "false", "null"}:
            return token
        if expect_key and _BARE_KEY_RE.match(token):
            self.rules.add("unquoted_keys")
            return json.dumps(token)
        try:
            float(token)
        except ValueError:
            if token:
                self.rules.add("unquoted_keys" if expect_key else "bare_words")
                return json.dumps(token)
            return token
        return token

    def _trim_trailing_comma(self, out: list[str]) -> None:
        index = len(out) - 1
        while index >= 0 and out[index].strip() == "":
            index -= 1
        if index >= 0 and out[index] == ",":
            del out[index]
            self.rules.add("trailing_commas")

    def _close_open_containers(self, text: str, stack: list[str]) -> str:
        if not stack:
            return text
        self.rules.add("unterminated")
        closers = {"{": "}", "[": "]"}
        return text + "".join(closers[opener] for opener in reversed(stack))


def _split_concatenated(text: str) -> list[str]:
    """Split ``{...}{...}`` or newline-delimited JSON into separate documents."""
    decoder = json.JSONDecoder()
    documents: list[str] = []
    index = 0
    length = len(text)
    while index < length:
        while index < length and text[index] in " \t\r\n,":
            index += 1
        if index >= length:
            break
        try:
            _, end = decoder.raw_decode(text, index)
        except ValueError:
            return []
        documents.append(text[index:end])
        index = end
    return documents


def repair_json(text: str, *, allow_concatenated: bool = True) -> RepairResult:
    """Parse ``text`` as JSON, repairing common LLM formatting mistakes.

    Args:
        text: Candidate payload, possibly malformed.
        allow_concatenated: When true, several top-level documents glued
            together are returned as a JSON array instead of failing.

    Returns:
        A :class:`RepairResult` with the decoded value and the rules that fired.

    Raises:
        RepairError: if the payload cannot be turned into valid JSON.
    """
    if not isinstance(text, str):
        raise TypeError(f"expected str, got {type(text).__name__}")

    candidate = text.strip()
    if not candidate:
        raise RepairError("empty payload", candidate=text)

    def _strict_load(payload: str) -> Any:
        # ``parse_constant`` rejects NaN/Infinity/-Infinity so those route
        # through the rewriter and become ``null`` instead of Python floats.
        return json.loads(payload, parse_constant=_reject_constant)

    try:
        return RepairResult(_strict_load(candidate), candidate, [])
    except ValueError:
        pass

    rules: list[str] = []
    candidate, changed = _normalise_smart_quotes(candidate)
    if changed:
        rules.append("smart_quotes")

    try:
        value = _strict_load(candidate)
        return RepairResult(value, candidate, rules)
    except ValueError:
        pass

    if allow_concatenated:
        documents = _split_concatenated(candidate)
        if len(documents) > 1:
            merged = "[" + ",".join(documents) + "]"
            rules.append("concatenated")
            return RepairResult(json.loads(merged), merged, rules)

    rewriter = _Rewriter(candidate)
    rewritten = rewriter.run()
    rules.extend(sorted(rewriter.rules))

    try:
        value = json.loads(rewritten)
    except ValueError as exc:
        if allow_concatenated:
            documents = _split_concatenated(rewritten)
            if len(documents) > 1:
                merged = "[" + ",".join(documents) + "]"
                rules.append("concatenated")
                return RepairResult(json.loads(merged), merged, rules)
        raise RepairError(f"could not repair payload into valid JSON: {exc}", candidate=text) from exc

    return RepairResult(value, rewritten, rules)
