"""Rules that check how well tools and parameters are documented for an
LLM that has nothing but the schema text to decide whether/how to call
the tool.
"""

from __future__ import annotations

from toolschema_lint.models import Finding, Severity, ToolSchema
from toolschema_lint.rules.base import ToolRule

_MIN_TOOL_DESCRIPTION_LEN = 15
_MIN_PARAM_DESCRIPTION_LEN = 3
_GENERIC_DESCRIPTIONS = {
    "todo",
    "tbd",
    "n/a",
    "na",
    "function",
    "tool",
    "no description",
    "no description provided",
    "...",
}


class MissingToolDescription(ToolRule):
    id = "missing-tool-description"
    default_severity = Severity.ERROR
    description = "A tool has no description at all."

    def check(self, tool: ToolSchema) -> list[Finding]:
        if tool.description is None or not tool.description.strip():
            return [
                Finding(
                    rule_id=self.id,
                    severity=self.default_severity,
                    message=(
                        "Tool has no description. An LLM cannot decide when to call "
                        "this tool without one."
                    ),
                    tool_name=tool.name,
                )
            ]
        return []


class ThinToolDescription(ToolRule):
    id = "thin-tool-description"
    default_severity = Severity.WARNING
    description = "A tool description is present but too short or generic to be useful."

    def check(self, tool: ToolSchema) -> list[Finding]:
        desc = (tool.description or "").strip()
        if not desc:
            return []  # handled by MissingToolDescription
        findings = []
        if desc.lower() in _GENERIC_DESCRIPTIONS or len(desc) < _MIN_TOOL_DESCRIPTION_LEN:
            findings.append(
                Finding(
                    rule_id=self.id,
                    severity=self.default_severity,
                    message=(
                        f"Description {desc!r} is too short/generic ({len(desc)} chars). "
                        "Explain what the tool does, when to call it, and what it returns."
                    ),
                    tool_name=tool.name,
                )
            )
        return findings


class MissingParameterDescription(ToolRule):
    id = "missing-parameter-description"
    default_severity = Severity.WARNING
    description = "A parameter has no description, or one too short to disambiguate its meaning."

    def check(self, tool: ToolSchema) -> list[Finding]:
        findings = []
        for param in tool.parameters:
            desc = (param.description or "").strip()
            if not desc:
                findings.append(
                    Finding(
                        rule_id=self.id,
                        severity=self.default_severity,
                        message="Parameter has no description.",
                        tool_name=tool.name,
                        parameter_name=param.name,
                    )
                )
            elif len(desc) < _MIN_PARAM_DESCRIPTION_LEN:
                findings.append(
                    Finding(
                        rule_id=self.id,
                        severity=self.default_severity,
                        message=f"Parameter description {desc!r} is too short to be useful.",
                        tool_name=tool.name,
                        parameter_name=param.name,
                    )
                )
        return findings
