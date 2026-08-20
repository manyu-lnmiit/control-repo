"""Derive a JSON Schema from a Python type hint or Pydantic model.

Defining a contract twice — once as a type and once as raw JSON Schema — is a
maintenance hazard. This module lets callers point at a dataclass, a
``TypedDict``, a Pydantic model, or a plain typing annotation and get a schema
that :func:`outputcontract.pipeline.parse` can enforce.
"""

from __future__ import annotations

import dataclasses
import types
import typing
from typing import Any, Union, get_args, get_origin

_UNION_ORIGINS = {Union, getattr(types, "UnionType", Union)}

try:  # pragma: no cover - optional dependency
    from pydantic import BaseModel

    _HAS_PYDANTIC = True
except Exception:  # pragma: no cover
    BaseModel = None  # type: ignore[assignment,misc]
    _HAS_PYDANTIC = False

_PRIMITIVES: dict[type, dict[str, Any]] = {
    str: {"type": "string"},
    bool: {"type": "boolean"},
    int: {"type": "integer"},
    float: {"type": "number"},
    type(None): {"type": "null"},
}


def schema_from(target: Any) -> dict[str, Any]:
    """Return a JSON Schema (draft 2020-12) for ``target``.

    ``target`` may be a Pydantic model class, a dataclass, a ``TypedDict`` or a
    plain typing annotation such as ``list[dict[str, int]]``.
    """
    if _HAS_PYDANTIC and isinstance(target, type) and issubclass(target, BaseModel):
        schema = target.model_json_schema()
        schema.setdefault("$schema", "https://json-schema.org/draft/2020-12/schema")
        return schema

    schema = _annotation_to_schema(target)
    schema.setdefault("$schema", "https://json-schema.org/draft/2020-12/schema")
    return schema


def _is_typeddict(target: Any) -> bool:
    return isinstance(target, type) and hasattr(target, "__annotations__") and hasattr(
        target, "__required_keys__"
    )


def _annotation_to_schema(annotation: Any) -> dict[str, Any]:
    if annotation is Any or annotation is None:
        return {}

    if annotation in _PRIMITIVES:
        return dict(_PRIMITIVES[annotation])

    if dataclasses.is_dataclass(annotation) and isinstance(annotation, type):
        return _dataclass_schema(annotation)

    if _is_typeddict(annotation):
        return _typeddict_schema(annotation)

    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin in (list, set, frozenset, tuple):
        if origin is tuple and args and args[-1] is not Ellipsis:
            return {"type": "array", "items": [_annotation_to_schema(a) for a in args]}
        item = args[0] if args else Any
        return {"type": "array", "items": _annotation_to_schema(item)}

    if origin is dict:
        value_type = args[1] if len(args) == 2 else Any
        return {"type": "object", "additionalProperties": _annotation_to_schema(value_type)}

    if origin in _UNION_ORIGINS:
        non_none = [a for a in args if a is not type(None)]
        nullable = len(non_none) != len(args)
        if len(non_none) == 1:
            schema = _annotation_to_schema(non_none[0])
            if nullable:
                return _make_nullable(schema)
            return schema
        variants = [_annotation_to_schema(a) for a in non_none]
        schema = {"anyOf": variants}
        if nullable:
            schema["anyOf"].append({"type": "null"})
        return schema

    if isinstance(annotation, type):
        # Unknown class: accept any object rather than failing hard.
        return {"type": "object"}

    return {}


def _make_nullable(schema: dict[str, Any]) -> dict[str, Any]:
    declared = schema.get("type")
    if isinstance(declared, str):
        schema = dict(schema)
        schema["type"] = [declared, "null"]
        return schema
    if declared is None and "anyOf" not in schema:
        return {"anyOf": [schema, {"type": "null"}]}
    if "anyOf" in schema:
        schema = dict(schema)
        schema["anyOf"] = list(schema["anyOf"]) + [{"type": "null"}]
    return schema


def _dataclass_schema(target: type) -> dict[str, Any]:
    hints = typing.get_type_hints(target)
    properties: dict[str, Any] = {}
    required: list[str] = []
    for field in dataclasses.fields(target):
        properties[field.name] = _annotation_to_schema(hints.get(field.name, Any))
        has_default = (
            field.default is not dataclasses.MISSING
            or field.default_factory is not dataclasses.MISSING  # type: ignore[misc]
        )
        if not has_default:
            required.append(field.name)
    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    schema["additionalProperties"] = False
    return schema


def _typeddict_schema(target: type) -> dict[str, Any]:
    hints = typing.get_type_hints(target)
    properties = {name: _annotation_to_schema(hint) for name, hint in hints.items()}
    required = sorted(getattr(target, "__required_keys__", frozenset()))
    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema
