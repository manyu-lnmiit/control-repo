"""Rules about tool and parameter naming conventions.

Naming matters a lot more for LLM function-calling than for ordinary APIs:
the model only ever sees the name, description, and schema -- there's no
IDE autocomplete or code review to catch a bad name, so a vague or
inconsistent name directly increases the odds of the wrong tool being
called.
"""

from __future__ import annotations

import re

from toolschema_lint.models import Finding, Severity, ToolSchema
from toolschema_lint.rules.base import ToolRule

_VAGUE_NAMES = {
    "run",
    "do",
    "execute",
    "call",
    "action",
    "tool",
    "function",
    "handler",
    "process",
    "task",
    "invoke",
    "helper",
}

_VALID_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
_BOOL_PREFIXES = ("is_", "has_", "should_", "can_", "enable_", "disable_", "allow_", "include_")


class VagueToolName(ToolRule):
    id = "vague-tool-name"
    default_severity = Severity.WARNING
    description = "Tool name is a generic verb that doesn't say what the tool does."

    def check(self, tool: ToolSchema) -> list[Finding]:
        bare = tool.name.strip().lower()
        if bare in _VAGUE_NAMES or (len(bare) <= 4 and bare.isalpha()):
            return [
                Finding(
                    rule_id=self.id,
                    severity=self.default_severity,
                    message=(
                        f"Tool name {tool.name!r} is too generic. Use a specific, "
                        "action-oriented name such as 'search_flights' rather than 'run'."
                    ),
                    tool_name=tool.name,
                )
            ]
        return []


class InvalidToolNameFormat(ToolRule):
    id = "invalid-tool-name-format"
    default_severity = Severity.ERROR
    description = (
        "Tool name uses characters some providers reject (must match "
        "^[a-zA-Z_][a-zA-Z0-9_]*$ for OpenAI/Anthropic function-calling)."
    )

    def check(self, tool: ToolSchema) -> list[Finding]:
        if not _VALID_NAME_RE.match(tool.name):
            return [
                Finding(
                    rule_id=self.id,
                    severity=self.default_severity,
                    message=(
                        f"Tool name {tool.name!r} contains characters outside "
                        "[a-zA-Z0-9_] or starts with a digit; some providers will reject it."
                    ),
                    tool_name=tool.name,
                )
            ]
        return []


class BooleanNamingConvention(ToolRule):
    id = "boolean-naming-convention"
    default_severity = Severity.INFO
    description = "Boolean parameters read more clearly with an is_/has_/should_ prefix."

    def check(self, tool: ToolSchema) -> list[Finding]:
        findings = []
        for param in tool.parameters:
            if param.type == "boolean" and not param.name.lower().startswith(_BOOL_PREFIXES):
                findings.append(
                    Finding(
                        rule_id=self.id,
                        severity=self.default_severity,
                        message=(
                            f"Boolean parameter {param.name!r} doesn't read as a yes/no "
                            "question; consider a prefix like is_/has_/should_."
                        ),
                        tool_name=tool.name,
                        parameter_name=param.name,
                    )
                )
        return findings
