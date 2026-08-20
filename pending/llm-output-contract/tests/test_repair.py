"""Tests for deterministic JSON repair."""

from __future__ import annotations

import pytest

from outputcontract.errors import RepairError
from outputcontract.repair import repair_json


def test_clean_json_needs_no_repair():
    result = repair_json('{"a": 1, "b": [2, 3]}')
    assert result.value == {"a": 1, "b": [2, 3]}
    assert not result.repaired


def test_trailing_comma_in_object_and_array():
    result = repair_json('{"a": [1, 2, 3,], "b": 4,}')
    assert result.value == {"a": [1, 2, 3], "b": 4}
    assert "trailing_commas" in result.rules


def test_single_quotes_converted():
    result = repair_json("{'name': 'Ada', 'lang': 'python'}")
    assert result.value == {"name": "Ada", "lang": "python"}
    assert "single_quotes" in result.rules


def test_unquoted_keys():
    result = repair_json('{name: "Ada", age: 36}')
    assert result.value == {"name": "Ada", "age": 36}
    assert "unquoted_keys" in result.rules


def test_python_literals():
    result = repair_json('{"ok": True, "bad": False, "missing": None}')
    assert result.value == {"ok": True, "bad": False, "missing": None}
    assert "python_literals" in result.rules


def test_line_comments_stripped():
    text = '{\n  "a": 1, // the first value\n  "b": 2\n}'
    result = repair_json(text)
    assert result.value == {"a": 1, "b": 2}
    assert "comments" in result.rules


def test_block_comments_stripped():
    result = repair_json('{"a": 1, /* note */ "b": 2}')
    assert result.value == {"a": 1, "b": 2}


def test_smart_quotes_normalised():
    result = repair_json('{“name”: “Ada”}')
    assert result.value == {"name": "Ada"}
    assert "smart_quotes" in result.rules


def test_non_finite_becomes_null():
    result = repair_json('{"x": NaN, "y": Infinity}')
    assert result.value == {"x": None, "y": None}
    assert "non_finite" in result.rules


def test_unterminated_object_closed():
    result = repair_json('{"a": 1, "b": 2')
    assert result.value == {"a": 1, "b": 2}
    assert "unterminated" in result.rules


def test_unterminated_string_closed():
    result = repair_json('{"a": "hello')
    assert result.value == {"a": "hello"}


def test_concatenated_documents_merged():
    result = repair_json('{"id": 1}{"id": 2}')
    assert result.value == [{"id": 1}, {"id": 2}]
    assert "concatenated" in result.rules


def test_braces_in_strings_are_preserved():
    result = repair_json('{"template": "hi {name}"}')
    assert result.value == {"template": "hi {name}"}


def test_empty_payload_raises():
    with pytest.raises(RepairError):
        repair_json("   ")


def test_combined_mess():
    text = "{'user': {name: 'Ada', active: True,}, tags: ['a', 'b',],}"
    result = repair_json(text)
    assert result.value == {"user": {"name": "Ada", "active": True}, "tags": ["a", "b"]}
