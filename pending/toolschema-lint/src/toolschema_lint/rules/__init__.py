"""The built-in rule set, and a registry for looking rules up by id.

Rules are split into ``ToolRule`` (evaluated per tool) and ``CorpusRule``
(evaluated once across the whole tool set). :data:`DEFAULT_RULES` is the
list of rule instances used unless a config file disables/reconfigures
some of them.
"""

from __future__ import annotations

from toolschema_lint.rules.base import CorpusRule, Rule, ToolRule
from toolschema_lint.rules.descriptions import (
    MissingParameterDescription,
    MissingToolDescription,
    ThinToolDescription,
)
from toolschema_lint.rules.duplicates import DuplicateToolName, OverlappingToolPurpose
from toolschema_lint.rules.naming import (
    BooleanNamingConvention,
    InvalidToolNameFormat,
    VagueToolName,
)
from toolschema_lint.rules.schema import (
    EnumValueTypeMismatch,
    InvalidParameterType,
    MissingEnumConstraint,
    RequiredParameterNotDefined,
    UnconstrainedObjectParameter,
)

DEFAULT_RULES: list[Rule] = [
    MissingToolDescription(),
    ThinToolDescription(),
    MissingParameterDescription(),
    VagueToolName(),
    InvalidToolNameFormat(),
    BooleanNamingConvention(),
    RequiredParameterNotDefined(),
    InvalidParameterType(),
    EnumValueTypeMismatch(),
    MissingEnumConstraint(),
    UnconstrainedObjectParameter(),
    DuplicateToolName(),
    OverlappingToolPurpose(),
]

RULES_BY_ID: dict[str, Rule] = {rule.id: rule for rule in DEFAULT_RULES}

__all__ = [
    "Rule",
    "ToolRule",
    "CorpusRule",
    "DEFAULT_RULES",
    "RULES_BY_ID",
]
