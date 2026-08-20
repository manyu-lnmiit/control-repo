"""Schema-guided coercion of loosely typed payloads.

Models frequently return the right *shape* with the wrong *types*: ``"42"``
for an integer field, ``"yes"`` for a boolean, a bare object where an array of
one object was requested, or an enum value with the wrong capitalisation. This
module walks a payload alongside its JSON Schema and repairs those mismatches
deterministically, recording every change so the caller can log or reject them.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

_TRUE_WORDS = {"true", "yes", "y", "1", "on", "t"}
_FALSE_WORDS = {"false", "no", "n", "0", "off", "f"}
_NUMBER_CLEAN_RE = re.compile(r"[,_\s$%]")


@dataclass
class CoercionResult:
    """Result of a coercion pass.

    Attributes:
        value: The coerced payload.
        changes: Human-readable ``"/path: description"`` entries, one per fix.
    """

    value: Any
    changes: list[str] = field(default_factory=list)

    @property
    def coerced(self) -> bool:
        """True when at least one value had to be changed."""
        return bool(self.changes)


def _schema_types(schema: Mapping[str, Any]) -> list[str]:
    declared = schema.get("type")
    if declared is None:
        return []
    if isinstance(declared, str):
        return [declared]
    return [item for item in declared if isinstance(item, str)]


def _to_number(text: str) -> float | None:
    cleaned = _NUMBER_CLEAN_RE.sub("", text.strip())
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _match_enum(value: Any, options: Sequence[Any]) -> Any | None:
    if value in options:
        return value
    if isinstance(value, str):
        normalised = value.strip().lower().replace("-", "_").replace(" ", "_")
        for option in options:
            if isinstance(option, str):
                candidate = option.strip().lower().replace("-", "_").replace(" ", "_")
                if candidate == normalised:
                    return option
    return None


class _Coercer:
    def __init__(self, root_schema: Mapping[str, Any]) -> None:
        self.root = root_schema
        self.changes: list[str] = []

    def resolve(self, schema: Mapping[str, Any]) -> Mapping[str, Any]:
        """Resolve a local ``$ref`` (``#/$defs/Name``) against the root schema."""
        seen = 0
        while isinstance(schema, Mapping) and "$ref" in schema and seen < 16:
            ref = schema["$ref"]
            seen += 1
            if not isinstance(ref, str) or not ref.startswith("#"):
                return schema
            node: Any = self.root
            for part in ref.lstrip("#/").split("/"):
                if not part:
                    continue
                if isinstance(node, Mapping) and part in node:
                    node = node[part]
                else:
                    return schema
            if not isinstance(node, Mapping):
                return schema
            schema = node
        return schema

    def note(self, path: str, message: str) -> None:
        self.changes.append(f"{path or '/'}: {message}")

    def walk(self, value: Any, schema: Mapping[str, Any] | None, path: str = "") -> Any:
        if not isinstance(schema, Mapping):
            return value
        schema = self.resolve(schema)

        for key in ("anyOf", "oneOf"):
            variants = schema.get(key)
            if isinstance(variants, list) and variants:
                return self._walk_union(value, variants, path)

        types = _schema_types(schema)
        enum_options = schema.get("enum")

        if isinstance(enum_options, list) and enum_options:
            matched = _match_enum(value, enum_options)
            if matched is not None and matched != value:
                self.note(path, f"enum value {value!r} normalised to {matched!r}")
                return matched
            if matched is not None:
                return matched

        if "object" in types or "properties" in schema:
            value = self._to_object(value, path, types)
            if isinstance(value, dict):
                return self._walk_object(value, schema, path)
            return value

        if "array" in types:
            value = self._to_array(value, path)
            return self._walk_array(value, schema, path)

        return self._scalar(value, types, path)

    def _walk_union(self, value: Any, variants: list[Any], path: str) -> Any:
        for variant in variants:
            if not isinstance(variant, Mapping):
                continue
            resolved = self.resolve(variant)
            types = _schema_types(resolved)
            if _matches_type(value, types) or not types:
                return self.walk(value, resolved, path)
        before = len(self.changes)
        for variant in variants:
            if not isinstance(variant, Mapping):
                continue
            attempt = self.walk(value, variant, path)
            if _matches_type(attempt, _schema_types(self.resolve(variant))):
                return attempt
            del self.changes[before:]
        return value

    def _to_object(self, value: Any, path: str, types: list[str]) -> Any:
        if isinstance(value, dict) or not types:
            return value
        if isinstance(value, list) and len(value) == 1 and isinstance(value[0], dict):
            self.note(path, "unwrapped single-element array into object")
            return value[0]
        return value

    def _walk_object(self, value: dict[str, Any], schema: Mapping[str, Any], path: str) -> dict[str, Any]:
        properties = schema.get("properties")
        properties = properties if isinstance(properties, Mapping) else {}
        additional = schema.get("additionalProperties")
        out: dict[str, Any] = {}
        lowered = {key.lower(): key for key in properties}

        for key, item in value.items():
            target_key = key
            if key not in properties and isinstance(key, str):
                canonical = lowered.get(key.lower().replace(" ", "_").replace("-", "_"))
                if canonical is not None:
                    self.note(f"{path}/{key}", f"key renamed to {canonical!r}")
                    target_key = canonical
            subschema = properties.get(target_key)
            if subschema is None and isinstance(additional, Mapping):
                subschema = additional
            out[target_key] = self.walk(item, subschema, f"{path}/{target_key}")
        return out

    def _to_array(self, value: Any, path: str) -> Any:
        if isinstance(value, list) or value is None:
            return value
        self.note(path, "scalar wrapped into a single-element array")
        return [value]

    def _walk_array(self, value: Any, schema: Mapping[str, Any], path: str) -> Any:
        if not isinstance(value, list):
            return value
        items = schema.get("items")
        if isinstance(items, list):
            return [
                self.walk(item, items[index] if index < len(items) else None, f"{path}/{index}")
                for index, item in enumerate(value)
            ]
        return [self.walk(item, items, f"{path}/{index}") for index, item in enumerate(value)]

    def _scalar(self, value: Any, types: list[str], path: str) -> Any:
        if not types or _matches_type(value, types):
            return value

        if "boolean" in types and isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in _TRUE_WORDS:
                self.note(path, f"{value!r} coerced to true")
                return True
            if lowered in _FALSE_WORDS:
                self.note(path, f"{value!r} coerced to false")
                return False

        if ("integer" in types or "number" in types) and isinstance(value, (str, bool)):
            if isinstance(value, bool):
                return value
            number = _to_number(value)
            if number is not None:
                if "integer" in types and float(number).is_integer():
                    self.note(path, f"{value!r} coerced to int")
                    return int(number)
                if "number" in types:
                    self.note(path, f"{value!r} coerced to float")
                    return number

        if "integer" in types and isinstance(value, float) and value.is_integer():
            self.note(path, "float narrowed to int")
            return int(value)

        if "string" in types and isinstance(value, (int, float)) and not isinstance(value, bool):
            self.note(path, f"{value!r} stringified")
            return str(value)

        null_words = {"none", "null", "n/a", ""}
        if "null" in types and isinstance(value, str) and value.strip().lower() in null_words:
            self.note(path, f"{value!r} coerced to null")
            return None

        return value


def _matches_type(value: Any, types: list[str]) -> bool:
    if not types:
        return True
    for declared in types:
        if declared == "string" and isinstance(value, str):
            return True
        if declared == "integer" and isinstance(value, int) and not isinstance(value, bool):
            return True
        if declared == "number" and isinstance(value, (int, float)) and not isinstance(value, bool):
            return True
        if declared == "boolean" and isinstance(value, bool):
            return True
        if declared == "array" and isinstance(value, list):
            return True
        if declared == "object" and isinstance(value, dict):
            return True
        if declared == "null" and value is None:
            return True
    return False


def coerce_to_schema(value: Any, schema: Mapping[str, Any]) -> CoercionResult:
    """Coerce ``value`` towards ``schema`` and report every change made."""
    coercer = _Coercer(schema)
    coerced = coercer.walk(value, schema, "")
    return CoercionResult(coerced, coercer.changes)
