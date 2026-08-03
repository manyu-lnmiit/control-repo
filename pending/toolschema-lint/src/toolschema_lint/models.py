"""Core data model: a provider-agnostic representation of a single tool
("function") definition, plus the finding/severity types the rule engine
emits.

Every parser (OpenAI, Anthropic, MCP) normalizes its native JSON shape into
a ``ToolSchema`` so that rules only ever need to understand one shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Severity(str, Enum):
    """Finding severity, ordered from least to most important."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"

    @property
    def rank(self) -> int:
        return {"info": 0, "warning": 1, "error": 2}[self.value]


@dataclass(frozen=True)
class Parameter:
    """A single property within a tool's JSON-schema ``parameters`` object."""

    name: str
    schema: dict[str, Any] = field(default_factory=dict)
    required: bool = False

    @property
    def type(self) -> str | None:
        t = self.schema.get("type")
        if isinstance(t, list):
            return t[0] if t else None
        return t

    @property
    def description(self) -> str | None:
        return self.schema.get("description")

    @property
    def enum(self) -> list[Any] | None:
        return self.schema.get("enum")


@dataclass(frozen=True)
class ToolSchema:
    """Provider-agnostic normalized tool/function definition."""

    name: str
    description: str | None
    parameters: tuple[Parameter, ...] = field(default_factory=tuple)
    raw: dict[str, Any] = field(default_factory=dict)
    source_format: str = "unknown"
    source_index: int = 0

    def get_parameter(self, name: str) -> Parameter | None:
        for p in self.parameters:
            if p.name == name:
                return p
        return None


@dataclass(frozen=True)
class Finding:
    """One rule violation, anchored to a tool (and optionally a parameter)."""

    rule_id: str
    severity: Severity
    message: str
    tool_name: str
    parameter_name: str | None = None

    def format(self) -> str:
        loc = self.tool_name
        if self.parameter_name:
            loc = f"{self.tool_name}.{self.parameter_name}"
        return f"[{self.severity.value.upper():7}] {self.rule_id:28} {loc}: {self.message}"
