"""Base classes for the rule engine.

Two kinds of rule:

* :class:`ToolRule` runs once per tool, independent of the rest of the tool
  set (e.g. "description is missing").
* :class:`CorpusRule` runs once across the whole set of tools, because it
  needs to compare tools against each other (e.g. "two tools look like
  near-duplicates").

Both simply return a list of :class:`~toolschema_lint.models.Finding`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from toolschema_lint.models import Finding, ToolSchema


class Rule(ABC):
    """Common identity fields shared by all rules."""

    id: str = "base-rule"
    default_severity = None
    description: str = ""


class ToolRule(Rule):
    @abstractmethod
    def check(self, tool: ToolSchema) -> list[Finding]:
        """Return findings for a single tool."""
        raise NotImplementedError


class CorpusRule(Rule):
    @abstractmethod
    def check_all(self, tools: list[ToolSchema]) -> list[Finding]:
        """Return findings computed across the full set of tools."""
        raise NotImplementedError
