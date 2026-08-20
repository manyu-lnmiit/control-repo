"""JSON Schema validation with clean, model-feedback-friendly messages."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

try:  # pragma: no cover - exercised indirectly
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import SchemaError as _JsonSchemaError

    _HAS_JSONSCHEMA = True
except Exception:  # pragma: no cover - optional dependency guard
    Draft202012Validator = None  # type: ignore[assignment]
    _JsonSchemaError = Exception  # type: ignore[assignment,misc]
    _HAS_JSONSCHEMA = False


@dataclass(frozen=True)
class ValidationIssue:
    """A single schema violation.

    Attributes:
        path: JSON pointer to the offending location (``/items/0/price``).
        message: Human-readable description suitable for a model retry prompt.
        validator: The failing schema keyword (``type``, ``required`` ...).
    """

    path: str
    message: str
    validator: str

    def as_dict(self) -> dict[str, str]:
        return {"path": self.path, "message": self.message, "validator": self.validator}

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.path}: {self.message}"


def _pointer(parts: Any) -> str:
    tokens = [str(part) for part in parts]
    return "/" + "/".join(tokens) if tokens else "/"


class SchemaValidator:
    """Thin wrapper around ``jsonschema`` that yields tidy issue objects."""

    def __init__(self, schema: Mapping[str, Any]) -> None:
        if not isinstance(schema, Mapping):
            raise TypeError("schema must be a mapping")
        self.schema = schema
        if _HAS_JSONSCHEMA:
            try:
                Draft202012Validator.check_schema(schema)
            except _JsonSchemaError as exc:  # pragma: no cover - defensive
                raise ValueError(f"invalid JSON Schema: {exc.message}") from exc
            self._validator = Draft202012Validator(schema)
        else:  # pragma: no cover - fallback path
            self._validator = None

    def iter_issues(self, value: Any) -> list[ValidationIssue]:
        """Return every validation issue for ``value``, sorted by location."""
        if self._validator is not None:
            issues = [
                ValidationIssue(
                    path=_pointer(error.absolute_path),
                    message=error.message,
                    validator=str(error.validator),
                )
                for error in self._validator.iter_errors(value)
            ]
            issues.sort(key=lambda issue: issue.path)
            return issues
        return _fallback_validate(value, self.schema, "")

    def is_valid(self, value: Any) -> bool:
        """True when ``value`` satisfies the schema with no issues."""
        return not self.iter_issues(value)


def _fallback_validate(value: Any, schema: Mapping[str, Any], path: str) -> list[ValidationIssue]:
    """Minimal structural validator used only when ``jsonschema`` is absent."""
    issues: list[ValidationIssue] = []
    declared = schema.get("type")
    types = [declared] if isinstance(declared, str) else list(declared or [])

    type_ok = not types
    for name in types:
        checker = {
            "object": lambda v: isinstance(v, dict),
            "array": lambda v: isinstance(v, list),
            "string": lambda v: isinstance(v, str),
            "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
            "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
            "boolean": lambda v: isinstance(v, bool),
            "null": lambda v: v is None,
        }.get(name, lambda v: True)
        if checker(value):
            type_ok = True
            break
    if not type_ok:
        issues.append(ValidationIssue(path or "/", f"{value!r} is not of type {types}", "type"))
        return issues

    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                issues.append(ValidationIssue(f"{path}/{key}", f"{key!r} is a required property", "required"))
        properties = schema.get("properties", {})
        for key, subschema in properties.items():
            if key in value and isinstance(subschema, Mapping):
                issues.extend(_fallback_validate(value[key], subschema, f"{path}/{key}"))
    elif isinstance(value, list):
        items = schema.get("items")
        if isinstance(items, Mapping):
            for index, item in enumerate(value):
                issues.extend(_fallback_validate(item, items, f"{path}/{index}"))
    return issues
