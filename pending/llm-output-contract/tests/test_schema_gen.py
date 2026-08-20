"""Tests for schema derivation from Python types."""

from __future__ import annotations

import dataclasses

import pytest

from outputcontract import parse, schema_from


@dataclasses.dataclass
class Address:
    city: str
    zip_code: str


@dataclasses.dataclass
class Person:
    name: str
    age: int
    address: Address
    nickname: str | None = None
    tags: list[str] = dataclasses.field(default_factory=list)


def test_dataclass_schema_shape():
    schema = schema_from(Person)
    assert schema["type"] == "object"
    assert set(schema["required"]) == {"name", "age", "address"}
    assert schema["properties"]["age"] == {"type": "integer"}
    assert schema["properties"]["address"]["type"] == "object"


def test_optional_becomes_nullable():
    schema = schema_from(Person)
    nickname = schema["properties"]["nickname"]
    assert "null" in nickname["type"]


def test_list_annotation():
    schema = schema_from(list[int])
    assert schema["type"] == "array"
    assert schema["items"] == {"type": "integer"}


def test_dict_annotation():
    schema = schema_from(dict[str, int])
    assert schema["type"] == "object"
    assert schema["additionalProperties"] == {"type": "integer"}


def test_generated_schema_drives_parse():
    schema = schema_from(Person)
    raw = "```json\n{name: 'Ada', age: '36', address: {city: 'Paris', zip_code: '75001'}}\n```"
    result = parse(raw, schema)
    assert result.value["age"] == 36
    assert result.value["address"]["city"] == "Paris"


def test_pydantic_model_if_available():
    pydantic = pytest.importorskip("pydantic")

    class Item(pydantic.BaseModel):
        sku: str
        qty: int

    schema = schema_from(Item)
    assert schema["properties"]["qty"]["type"] == "integer"
    result = parse('{"sku": "A1", "qty": "5"}', schema)
    assert result.value == {"sku": "A1", "qty": 5}
