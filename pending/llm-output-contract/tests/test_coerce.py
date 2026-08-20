"""Tests for schema-guided type coercion."""

from __future__ import annotations

from outputcontract.coerce import coerce_to_schema

OBJ_SCHEMA = {
    "type": "object",
    "properties": {
        "count": {"type": "integer"},
        "ratio": {"type": "number"},
        "active": {"type": "boolean"},
        "name": {"type": "string"},
    },
}


def test_string_to_integer():
    result = coerce_to_schema({"count": "42"}, OBJ_SCHEMA)
    assert result.value == {"count": 42}
    assert result.coerced


def test_string_with_commas_to_number():
    result = coerce_to_schema({"ratio": "1,234.5"}, OBJ_SCHEMA)
    assert result.value == {"ratio": 1234.5}


def test_yes_no_to_boolean():
    result = coerce_to_schema({"active": "yes"}, OBJ_SCHEMA)
    assert result.value == {"active": True}
    result = coerce_to_schema({"active": "off"}, OBJ_SCHEMA)
    assert result.value == {"active": False}


def test_number_to_string():
    result = coerce_to_schema({"name": 123}, OBJ_SCHEMA)
    assert result.value == {"name": "123"}


def test_scalar_wrapped_into_array():
    schema = {"type": "array", "items": {"type": "integer"}}
    result = coerce_to_schema("5", schema)
    assert result.value == [5]


def test_single_element_array_unwrapped_to_object():
    schema = {"type": "object", "properties": {"a": {"type": "integer"}}}
    result = coerce_to_schema([{"a": "1"}], schema)
    assert result.value == {"a": 1}


def test_enum_case_normalised():
    schema = {"type": "string", "enum": ["low", "medium", "high"]}
    result = coerce_to_schema("HIGH", schema)
    assert result.value == "high"


def test_key_case_and_spacing_normalised():
    schema = {"type": "object", "properties": {"first_name": {"type": "string"}}}
    result = coerce_to_schema({"First Name": "Ada"}, schema)
    assert result.value == {"first_name": "Ada"}


def test_null_words_to_none():
    schema = {"type": "object", "properties": {"x": {"type": ["integer", "null"]}}}
    result = coerce_to_schema({"x": "N/A"}, schema)
    assert result.value == {"x": None}


def test_nested_arrays_and_objects():
    schema = {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"qty": {"type": "integer"}, "ok": {"type": "boolean"}},
                },
            }
        },
    }
    payload = {"items": [{"qty": "2", "ok": "true"}, {"qty": "3", "ok": "no"}]}
    result = coerce_to_schema(payload, schema)
    assert result.value == {"items": [{"qty": 2, "ok": True}, {"qty": 3, "ok": False}]}


def test_ref_resolution():
    schema = {
        "type": "object",
        "properties": {"pt": {"$ref": "#/$defs/Point"}},
        "$defs": {"Point": {"type": "object", "properties": {"x": {"type": "integer"}}}},
    }
    result = coerce_to_schema({"pt": {"x": "9"}}, schema)
    assert result.value == {"pt": {"x": 9}}


def test_valid_values_untouched():
    result = coerce_to_schema({"count": 7, "active": True}, OBJ_SCHEMA)
    assert not result.coerced
