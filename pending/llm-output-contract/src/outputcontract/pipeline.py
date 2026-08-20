"""The public parsing pipeline: extract → repair → coerce → validate.

This ties the individual stages together into one function, :func:`parse`,
plus a retry helper, :func:`parse_with_retries`, that drives a repair loop by
feeding schema feedback back to a caller-supplied model function.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Callable

from outputcontract.coerce import coerce_to_schema
from outputcontract.errors import (
    ContractViolation,
    ExtractionError,
    RepairError,
    RetryBudgetExceeded,
)
from outputcontract.extract import find_candidates
from outputcontract.repair import repair_json
from outputcontract.validate import SchemaValidator, ValidationIssue


@dataclass
class ParseResult:
    """The successful outcome of :func:`parse`.

    Attributes:
        value: The validated, schema-conforming Python object.
        candidate: The raw substring that ultimately parsed.
        repairs: Names of the repair rules that fired (may be empty).
        coercions: Human-readable type coercions applied (may be empty).
        source: Where the winning candidate came from (``fence`` / ``scan`` ...).
    """

    value: Any
    candidate: str
    repairs: list[str] = field(default_factory=list)
    coercions: list[str] = field(default_factory=list)
    source: str = "raw"

    @property
    def was_clean(self) -> bool:
        """True when the model output needed no repair or coercion."""
        return not self.repairs and not self.coercions


def parse(
    raw: str,
    schema: Mapping[str, Any],
    *,
    coerce: bool = True,
    max_candidates: int = 6,
) -> ParseResult:
    """Parse ``raw`` model output into a value satisfying ``schema``.

    The best-ranked candidate that survives repair, optional coercion and
    validation wins. Candidates are tried in order so that a fenced object is
    preferred over an incidental brace pair elsewhere in the text.

    Args:
        raw: The unmodified text returned by the model.
        schema: A JSON Schema (draft 2020-12) describing the contract.
        coerce: Whether to apply type coercion before validation.
        max_candidates: Upper bound on how many candidates to attempt.

    Returns:
        A :class:`ParseResult` on success.

    Raises:
        ExtractionError: no candidate payload could be located.
        ContractViolation: a payload parsed but never satisfied the schema.
        RepairError: candidates existed but none could be repaired to JSON.
    """
    validator = SchemaValidator(schema)
    candidates = find_candidates(raw)
    if not candidates:
        raise ExtractionError("no JSON-like payload found in response", raw=raw)

    last_issues: list[ValidationIssue] = []
    last_repair_error: RepairError | None = None
    saw_valid_json = False

    for candidate in candidates[:max_candidates]:
        try:
            repaired = repair_json(candidate.text)
        except RepairError as exc:
            last_repair_error = exc
            continue

        saw_valid_json = True
        value = repaired.value
        coercions: list[str] = []
        if coerce:
            coercion = coerce_to_schema(value, schema)
            value = coercion.value
            coercions = coercion.changes

        issues = validator.iter_issues(value)
        if not issues:
            return ParseResult(
                value=value,
                candidate=repaired.text,
                repairs=repaired.rules,
                coercions=coercions,
                source=candidate.source,
            )
        last_issues = issues

    if saw_valid_json:
        raise ContractViolation(
            "model output did not satisfy the schema after repair and coercion",
            issues=last_issues,
        )
    if last_repair_error is not None:
        raise last_repair_error
    raise ExtractionError("no JSON-like payload found in response", raw=raw)


def render_feedback(issues: Sequence[ValidationIssue], *, limit: int = 8) -> str:
    """Format schema issues as a compact instruction block for a retry prompt."""
    if not issues:
        return "The previous response was not valid JSON. Return a single JSON object only."
    lines = ["Your previous JSON did not match the required schema. Fix these problems:"]
    for issue in list(issues)[:limit]:
        location = issue.path if issue.path != "/" else "(root)"
        lines.append(f"- at {location}: {issue.message}")
    lines.append("Return only the corrected JSON, with no prose or code fences.")
    return "\n".join(lines)


def parse_with_retries(
    call_model: Callable[[str | None], str],
    schema: Mapping[str, Any],
    *,
    max_attempts: int = 3,
    coerce: bool = True,
    on_attempt: Callable[[int, str, Exception | None], None] | None = None,
) -> ParseResult:
    """Call a model repeatedly until its output satisfies ``schema``.

    ``call_model`` receives ``None`` on the first attempt and, thereafter, a
    feedback string describing the previous failure. It must return the model's
    raw text output. This inverts control so the loop works with any client
    (OpenAI, Anthropic, local, a stub in tests) without importing an SDK.

    Args:
        call_model: Callable that produces raw model text given optional feedback.
        schema: The JSON Schema contract to enforce.
        max_attempts: Maximum number of model calls before giving up.
        coerce: Whether to apply type coercion each attempt.
        on_attempt: Optional observer ``(attempt_index, raw, error)`` invoked
            after every attempt for logging or metrics.

    Returns:
        A :class:`ParseResult` for the first attempt that satisfies the schema.

    Raises:
        RetryBudgetExceeded: every attempt failed within the budget.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    feedback: str | None = None
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        raw = call_model(feedback)
        try:
            result = parse(raw, schema, coerce=coerce)
        except ContractViolation as exc:
            last_error = exc
            feedback = render_feedback(exc.issues)
        except (ExtractionError, RepairError) as exc:
            last_error = exc
            feedback = render_feedback([])
        else:
            if on_attempt is not None:
                on_attempt(attempt, raw, None)
            return result

        if on_attempt is not None:
            on_attempt(attempt, raw, last_error)

    raise RetryBudgetExceeded(
        f"failed to obtain schema-valid output in {max_attempts} attempts",
        attempts=max_attempts,
        last_error=last_error,
    )
