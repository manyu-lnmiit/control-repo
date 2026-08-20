"""Exception hierarchy for :mod:`outputcontract`."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typing only
    from outputcontract.validate import ValidationIssue


class OutputContractError(Exception):
    """Base class for every error raised by this package."""


class ExtractionError(OutputContractError):
    """Raised when no JSON-ish payload can be located in a model response."""

    def __init__(self, message: str, raw: str = "") -> None:
        super().__init__(message)
        self.raw = raw


class RepairError(OutputContractError):
    """Raised when a candidate payload cannot be coerced into valid JSON."""

    def __init__(self, message: str, candidate: str = "") -> None:
        super().__init__(message)
        self.candidate = candidate


class ContractViolation(OutputContractError):
    """Raised when a parsed payload does not satisfy the schema contract."""

    def __init__(self, message: str, issues: Sequence[ValidationIssue] = ()) -> None:
        super().__init__(message)
        self.issues = list(issues)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation of the violation."""
        return {
            "message": str(self),
            "issues": [issue.as_dict() for issue in self.issues],
        }


class RetryBudgetExceeded(OutputContractError):
    """Raised when the repair loop exhausts its attempt budget."""

    def __init__(self, message: str, attempts: int, last_error: Exception | None = None) -> None:
        super().__init__(message)
        self.attempts = attempts
        self.last_error = last_error
