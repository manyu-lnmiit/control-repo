"""Declarative policy engine.

A `Policy` describes, per tool name, whether calls are allowed, an optional
JSON-schema for arguments, an optional rate limit, and an optional per-call
cost estimate used for budgeting. Policies are normally loaded from YAML but
can be constructed programmatically too.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

import jsonschema
import yaml

from agent_guardrail.exceptions import PolicyViolation

# Re-exported for convenience / backwards-compat with __init__.py
__all__ = ["PolicyRule", "Policy", "PolicyEngine", "PolicyViolation"]


@dataclass
class PolicyRule:
    """The policy for a single tool name."""

    name: str
    allowed: bool = True
    args_schema: dict[str, Any] | None = None
    max_calls_per_minute: int | None = None
    max_cost_per_call: float | None = None
    redact_output: bool = False
    description: str = ""

    def validate_args(self, arguments: dict[str, Any]) -> None:
        if self.args_schema is None:
            return
        try:
            jsonschema.validate(instance=arguments, schema=self.args_schema)
        except jsonschema.ValidationError as exc:
            raise PolicyViolation(
                f"tool '{self.name}' rejected arguments: {exc.message}"
            ) from exc


@dataclass
class Policy:
    """A full policy document: a set of per-tool rules plus a default for
    tools with no explicit rule."""

    rules: dict[str, PolicyRule] = field(default_factory=dict)
    default_allowed: bool = False

    def rule_for(self, tool_name: str) -> PolicyRule:
        if tool_name in self.rules:
            return self.rules[tool_name]
        return PolicyRule(name=tool_name, allowed=self.default_allowed)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Policy:
        data = copy.deepcopy(data)
        default_allowed = bool(data.get("default_allowed", False))
        rules: dict[str, PolicyRule] = {}
        for name, spec in (data.get("tools") or {}).items():
            spec = spec or {}
            rules[name] = PolicyRule(
                name=name,
                allowed=bool(spec.get("allowed", True)),
                args_schema=spec.get("args_schema"),
                max_calls_per_minute=spec.get("max_calls_per_minute"),
                max_cost_per_call=spec.get("max_cost_per_call"),
                redact_output=bool(spec.get("redact_output", False)),
                description=spec.get("description", ""),
            )
        return cls(rules=rules, default_allowed=default_allowed)

    @classmethod
    def from_yaml(cls, path: str) -> Policy:
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        return cls.from_dict(data)

    @classmethod
    def from_yaml_string(cls, text: str) -> Policy:
        data = yaml.safe_load(text) or {}
        return cls.from_dict(data)


class PolicyEngine:
    """Evaluates a `Policy` for a given tool call and raises `PolicyViolation`
    when the call is not permitted."""

    def __init__(self, policy: Policy):
        self.policy = policy

    def check(self, tool_name: str, arguments: dict[str, Any]) -> PolicyRule:
        rule = self.policy.rule_for(tool_name)
        if not rule.allowed:
            raise PolicyViolation(f"tool '{tool_name}' is not allowed by policy")
        rule.validate_args(arguments)
        return rule
