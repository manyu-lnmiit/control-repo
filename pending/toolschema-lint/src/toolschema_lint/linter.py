"""The linter orchestrator: runs the configured rule set over a parsed
tool list and produces a :class:`LintResult`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from toolschema_lint.config import Config
from toolschema_lint.models import Finding, Severity, ToolSchema
from toolschema_lint.rules import DEFAULT_RULES, CorpusRule, Rule, ToolRule
from toolschema_lint.rules.duplicates import OverlappingToolPurpose


@dataclass
class LintResult:
    findings: list[Finding] = field(default_factory=list)
    tool_count: int = 0

    @property
    def error_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.WARNING)

    @property
    def info_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.INFO)

    @property
    def has_errors(self) -> bool:
        return self.error_count > 0

    def sorted_findings(self) -> list[Finding]:
        return sorted(
            self.findings,
            key=lambda f: (-f.severity.rank, f.tool_name, f.parameter_name or ""),
        )


class Linter:
    """Runs a rule set (rules + severity overrides from ``Config``) over a
    list of already-parsed ``ToolSchema`` objects."""

    def __init__(self, config: Config | None = None, rules: list[Rule] | None = None) -> None:
        self.config = config or Config()
        self.rules = list(rules) if rules is not None else list(DEFAULT_RULES)
        for rule in self.rules:
            if isinstance(rule, OverlappingToolPurpose):
                rule.threshold = self.config.similarity_threshold

    def _active_rules(self) -> list[Rule]:
        return [r for r in self.rules if r.id not in self.config.disabled_rules]

    def _apply_severity_override(self, findings: list[Finding]) -> list[Finding]:
        overrides = self.config.severity_overrides
        if not overrides:
            return findings
        result = []
        for f in findings:
            if f.rule_id in overrides:
                result.append(
                    Finding(
                        rule_id=f.rule_id,
                        severity=overrides[f.rule_id],
                        message=f.message,
                        tool_name=f.tool_name,
                        parameter_name=f.parameter_name,
                    )
                )
            else:
                result.append(f)
        return result

    def lint(self, tools: list[ToolSchema]) -> LintResult:
        findings: list[Finding] = []
        for rule in self._active_rules():
            if isinstance(rule, ToolRule):
                for tool in tools:
                    findings.extend(rule.check(tool))
            elif isinstance(rule, CorpusRule):
                findings.extend(rule.check_all(tools))
        findings = self._apply_severity_override(findings)
        return LintResult(findings=findings, tool_count=len(tools))
