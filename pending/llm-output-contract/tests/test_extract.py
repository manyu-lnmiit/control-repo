"""Tests for candidate extraction from noisy responses."""

from __future__ import annotations

import pytest

from outputcontract.errors import ExtractionError
from outputcontract.extract import extract, find_candidates


def test_extract_from_markdown_fence():
    raw = 'Sure! Here is the data:\n```json\n{"name": "Ada", "age": 36}\n```\nHope that helps.'
    assert extract(raw) == '{"name": "Ada", "age": 36}'


def test_extract_prefers_fenced_over_incidental_braces():
    raw = "The set {a, b} is small.\n```json\n{\"ok\": true}\n```"
    candidates = find_candidates(raw)
    assert candidates[0].source == "fence"
    assert candidates[0].text == '{"ok": true}'


def test_extract_bare_object_without_fence():
    raw = 'Result: {"status": "done", "count": 3}'
    assert extract(raw) == '{"status": "done", "count": 3}'


def test_extract_array_payload():
    raw = "```\n[1, 2, 3]\n```"
    assert extract(raw) == "[1, 2, 3]"


def test_braces_inside_strings_do_not_break_scanner():
    raw = '{"template": "hello {name}", "closing": "bye }"}'
    assert extract(raw) == raw


def test_unterminated_object_still_extracted():
    raw = 'Here: {"a": 1, "b": 2'
    candidate = extract(raw)
    assert candidate.startswith('{"a": 1')


def test_no_payload_raises():
    with pytest.raises(ExtractionError):
        extract("there is absolutely nothing structured here")


def test_non_string_input_rejected():
    with pytest.raises(TypeError):
        find_candidates(123)  # type: ignore[arg-type]


def test_multiple_candidates_ranked_by_score():
    raw = '{"tiny": 1}\n\n```json\n{"bigger": {"nested": [1,2,3,4,5]}}\n```'
    candidates = find_candidates(raw)
    assert candidates[0].source == "fence"
