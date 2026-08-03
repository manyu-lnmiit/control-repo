"""Rules that validate the JSON-schema structure of a tool's parameters
independent of any provider -- catching things that would break at call
time (a ``required`` field that doesn't exist) or silently degrade an
agent's ability to fill in a parameter correctly (an enum-like string
field left unconstrained).
"""

from __future__ import annotations

from toolschema_lint.models import Finding, Severity, ToolSchema
from toolschema_lint.rules.base import ToolRule

_ENUM_HINT_PHRASES = ("one of", "must be either", "either ", " or ", "options are", "options:")
_VALID_JSON_TYPES = {"string", "number", "integer", "boolean", "array", "object", "null"}


class RequiredParameterNotDefined(ToolRule):
    id = "required-parameter-not-defined"
    default_severity = Severity.ERROR
    description = "The JSON schema's `required` array lists a name absent from `properties`."

    def check(self, tool: ToolSchema) -> list[Finding]:
        raw_schema = _extract_raw_schema(tool)
        required = set(raw_schema.get("required") or [])
        properties = set((raw_schema.get("properties") or {}).keys())
        missing = required - properties
        return [
            Finding(
                rule_id=self.id,
                severity=self.default_severity,
                message=(
                    f"'{name}' is listed in required but has no matching entry in properties."
                ),
                tool_name=tool.name,
                parameter_name=name,
            )
            for name in sorted(missing)
        ]


class InvalidParameterType(ToolRule):
    id = "invalid-parameter-type"
    default_severity = Severity.ERROR
    description = "A parameter declares a JSON-schema `type` that isn't a real JSON-schema type."

    def check(self, tool: ToolSchema) -> list[Finding]:
        findings = []
        for param in tool.parameters:
            t = param.schema.get("type")
            types = t if isinstance(t, list) else [t] if t is not None else []
            for candidate in types:
                if candidate not in _VALID_JSON_TYPES:
                    findings.append(
                        Finding(
                            rule_id=self.id,
                            severity=self.default_severity,
                            message=(
                                f"Parameter declares type {candidate!r}, which is not a "
                                f"valid JSON-schema type ({', '.join(sorted(_VALID_JSON_TYPES))})."
                            ),
                            tool_name=tool.name,
                            parameter_name=param.name,
                        )
                    )
        return findings


class EnumValueTypeMismatch(ToolRule):
    id = "enum-value-type-mismatch"
    default_severity = Severity.ERROR
    description = "An enum value's JSON type doesn't match the parameter's declared `type`."

    _TYPE_MAP = {
        str: "string",
        bool: "boolean",  # check before int/float since bool is an int subclass
        int: "integer",
        float: "number",
    }

    def check(self, tool: ToolSchema) -> list[Finding]:
        findings = []
        for param in tool.parameters:
            enum = param.enum
            declared = param.type
            if not enum or not declared:
                continue
            for value in enum:
                actual = self._json_type_of(value)
                if actual is None:
                    continue
                if declared == "number" and actual == "integer":
                    continue  # integers are valid numbers
                if actual != declared:
                    findings.append(
                        Finding(
                            rule_id=self.id,
                            severity=self.default_severity,
                            message=(
                                f"Enum value {value!r} is of type {actual!r} but parameter "
                                f"declares type {declared!r}."
                            ),
                            tool_name=tool.name,
                            parameter_name=param.name,
                        )
                    )
        return findings

    def _json_type_of(self, value: object) -> str | None:
        for py_type, json_type in self._TYPE_MAP.items():
            if isinstance(value, py_type):
                return json_type
        return None


class MissingEnumConstraint(ToolRule):
    id = "missing-enum-constraint"
    default_severity = Severity.INFO
    description = (
        "A string parameter's description implies a fixed set of options, but no "
        "`enum` constrains it -- the model may hallucinate an invalid value."
    )

    def check(self, tool: ToolSchema) -> list[Finding]:
        findings = []
        for param in tool.parameters:
            if param.type != "string" or param.enum:
                continue
            desc = (param.description or "").lower()
            if any(phrase in desc for phrase in _ENUM_HINT_PHRASES):
                findings.append(
                    Finding(
                        rule_id=self.id,
                        severity=self.default_severity,
                        message=(
                            "Description suggests a fixed set of valid values; add an "
                            "`enum` so invalid values are rejected before the call is made."
                        ),
                        tool_name=tool.name,
                        parameter_name=param.name,
                    )
                )
        return findings


class UnconstrainedObjectParameter(ToolRule):
    id = "unconstrained-object-parameter"
    default_severity = Severity.INFO
    description = (
        "An object-typed parameter has no `properties`, giving the model no shape to fill in."
    )

    def check(self, tool: ToolSchema) -> list[Finding]:
        findings = []
        for param in tool.parameters:
            if param.type == "object" and not param.schema.get("properties"):
                findings.append(
                    Finding(
                        rule_id=self.id,
                        severity=self.default_severity,
                        message=(
                            "Object parameter has no nested `properties`; the model has no "
                            "guidance on what keys/values to provide."
                        ),
                        tool_name=tool.name,
                        parameter_name=param.name,
                    )
                )
        return findings


def _extract_raw_schema(tool: ToolSchema) -> dict:
    raw = tool.raw
    if tool.source_format == "openai" and isinstance(raw.get("function"), dict):
        return raw["function"].get("parameters") or {}
    if tool.source_format == "openai":
        return raw.get("parameters") or {}
    if tool.source_format == "anthropic":
        return raw.get("input_schema") or {}
    if tool.source_format == "mcp":
        return raw.get("inputSchema") or {}
    return {}
