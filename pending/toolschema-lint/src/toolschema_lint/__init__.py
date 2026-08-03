"""toolschema-lint: a static analyzer for LLM tool/function-calling schemas.

Public API surface for programmatic use, in addition to the CLI.
"""

from toolschema_lint.linter import Linter, LintResult
from toolschema_lint.models import Finding, Severity, ToolSchema

__all__ = [
    "Linter",
    "LintResult",
    "Finding",
    "Severity",
    "ToolSchema",
]

__version__ = "0.1.0"
