"""Minimal, dependency-free ``{{variable}}`` template rendering.

This intentionally implements a small, predictable subset of Jinja-style
templating rather than depending on a full templating engine: variable
substitution with ``{{name}}`` and ``{{name|default("fallback")}}``. This
keeps the core library dependency-free while covering the overwhelming
majority of real-world LLM prompt templates.
"""

from __future__ import annotations

import re
from typing import Any

_VAR_PATTERN = re.compile(
    r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:\|\s*default\(\s*\"([^\"]*)\"\s*\)\s*)?\}\}"
)


class MissingVariableError(KeyError):
    """Raised when a template references a variable that was not supplied
    and has no ``default(...)`` fallback."""


def extract_variables(body: str) -> list[str]:
    """Return the ordered, de-duplicated list of variable names referenced
    in a template body."""
    seen: set[str] = set()
    ordered: list[str] = []
    for match in _VAR_PATTERN.finditer(body):
        name = match.group(1)
        if name not in seen:
            seen.add(name)
            ordered.append(name)
    return ordered


def render_template(body: str, variables: dict[str, Any]) -> str:
    """Render ``body`` by substituting ``{{name}}`` placeholders.

    Raises:
        MissingVariableError: if a referenced variable is absent from
            ``variables`` and the placeholder has no ``|default(...)``.
    """
    missing: list[str] = []

    def _replace(match: re.Match[str]) -> str:
        name = match.group(1)
        default = match.group(2)
        if name in variables and variables[name] is not None:
            return str(variables[name])
        if default is not None:
            return default
        missing.append(name)
        return ""

    rendered = _VAR_PATTERN.sub(_replace, body)
    if missing:
        raise MissingVariableError(
            f"Missing required template variable(s): {', '.join(sorted(set(missing)))}"
        )
    return rendered
