"""Pluggable scorers for judging agent outputs against expected results."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ScoreResult:
    """The outcome of scoring one agent output against an expectation.

    Attributes:
        score: A value in ``[0.0, 1.0]`` where 1.0 is a perfect match.
        passed: Whether the score cleared the scorer's pass threshold.
        detail: Human-readable explanation, useful in reports and debugging.
    """

    score: float
    passed: bool
    detail: str = ""

    def __post_init__(self) -> None:
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(f"ScoreResult.score must be within [0, 1], got {self.score}")


class Scorer(ABC):
    """Base class for all scorers. Subclasses implement :meth:`score`."""

    @abstractmethod
    def score(self, output: Any, expected: Any) -> ScoreResult:
        """Compare ``output`` (from the agent) against ``expected`` (from the task)."""
        raise NotImplementedError


class ExactMatch(Scorer):
    """Passes only if ``str(output).strip() == str(expected).strip()``."""

    def __init__(self, case_sensitive: bool = True) -> None:
        self.case_sensitive = case_sensitive

    def score(self, output: Any, expected: Any) -> ScoreResult:
        out_s, exp_s = str(output).strip(), str(expected).strip()
        if not self.case_sensitive:
            out_s, exp_s = out_s.lower(), exp_s.lower()
        passed = out_s == exp_s
        return ScoreResult(score=1.0 if passed else 0.0, passed=passed,
                            detail=f"expected={exp_s!r} got={out_s!r}")


class Contains(Scorer):
    """Passes if ``expected`` (or any item, when ``expected`` is a list) appears in output."""

    def __init__(self, case_sensitive: bool = False, require_all: bool = False) -> None:
        self.case_sensitive = case_sensitive
        self.require_all = require_all

    def score(self, output: Any, expected: Any) -> ScoreResult:
        haystack = str(output)
        needles = expected if isinstance(expected, (list, tuple)) else [expected]
        needles = [str(n) for n in needles]
        if not self.case_sensitive:
            haystack = haystack.lower()
            needles = [n.lower() for n in needles]

        hits = [n for n in needles if n in haystack]
        if self.require_all:
            passed = len(hits) == len(needles)
            frac = len(hits) / max(len(needles), 1)
        else:
            passed = len(hits) > 0
            frac = 1.0 if passed else 0.0
        return ScoreResult(score=frac, passed=passed,
                            detail=f"matched {len(hits)}/{len(needles)} substrings")


class RegexMatch(Scorer):
    """Passes if ``expected`` (a regex pattern) matches somewhere in the output."""

    def __init__(self, flags: int = 0) -> None:
        self.flags = flags

    def score(self, output: Any, expected: Any) -> ScoreResult:
        pattern = re.compile(str(expected), self.flags)
        m = pattern.search(str(output))
        passed = m is not None
        return ScoreResult(score=1.0 if passed else 0.0, passed=passed,
                            detail=f"pattern={expected!r} match={m.group(0) if m else None}")


class NumericTolerance(Scorer):
    """Passes if the numeric output is within ``abs_tol``/``rel_tol`` of the expected number.

    Any number-like string ("42", "3.14", "$1,200") is coerced by stripping non-numeric
    characters other than the leading sign and decimal point.
    """

    def __init__(self, abs_tol: float = 1e-6, rel_tol: float = 0.0) -> None:
        self.abs_tol = abs_tol
        self.rel_tol = rel_tol

    @staticmethod
    def _coerce(value: Any) -> float:
        if isinstance(value, (int, float)):
            return float(value)
        s = re.sub(r"[^0-9.\-]", "", str(value))
        if s in ("", "-", "."):
            raise ValueError(f"Cannot coerce {value!r} to a number")
        return float(s)

    def score(self, output: Any, expected: Any) -> ScoreResult:
        try:
            out_f = self._coerce(output)
            exp_f = self._coerce(expected)
        except ValueError as exc:
            return ScoreResult(score=0.0, passed=False, detail=str(exc))

        diff = abs(out_f - exp_f)
        tol = max(self.abs_tol, self.rel_tol * abs(exp_f))
        passed = diff <= tol
        return ScoreResult(score=1.0 if passed else 0.0, passed=passed,
                            detail=f"|{out_f} - {exp_f}| = {diff} (tol={tol})")


class Composite(Scorer):
    """Combines several scorers with weights and averages the results.

    Passes only if the weighted-average score is at least ``pass_threshold``.
    """

    def __init__(self, scorers: list[tuple[Scorer, float]], pass_threshold: float = 1.0) -> None:
        if not scorers:
            raise ValueError("Composite requires at least one scorer")
        self.scorers = scorers
        self.pass_threshold = pass_threshold

    def score(self, output: Any, expected: Any) -> ScoreResult:
        total_weight = sum(w for _, w in self.scorers)
        weighted_sum = 0.0
        details = []
        for scorer, weight in self.scorers:
            result = scorer.score(output, expected)
            weighted_sum += result.score * weight
            details.append(f"{type(scorer).__name__}={result.score:.2f}(w={weight})")
        avg = weighted_sum / total_weight if total_weight else 0.0
        passed = avg >= self.pass_threshold
        return ScoreResult(score=avg, passed=passed, detail="; ".join(details))


@dataclass
class CallableScorer(Scorer):
    """Wraps an arbitrary ``(output, expected) -> ScoreResult`` callable as a :class:`Scorer`."""

    fn: Callable[[Any, Any], ScoreResult]
    kwargs: dict[str, Any] = field(default_factory=dict)

    def score(self, output: Any, expected: Any) -> ScoreResult:
        return self.fn(output, expected, **self.kwargs)


#: Registry mapping scorer names (as used in task files) to their classes.
REGISTRY: dict[str, type[Scorer]] = {
    "exact_match": ExactMatch,
    "contains": Contains,
    "regex": RegexMatch,
    "numeric_tolerance": NumericTolerance,
}


def register_scorer(name: str, scorer_cls: type[Scorer]) -> None:
    """Register a custom scorer class under ``name`` so tasks can reference it by string."""
    REGISTRY[name] = scorer_cls


def build_scorer(name: str, **kwargs: Any) -> Scorer:
    """Instantiate the scorer registered under ``name`` with the given keyword arguments."""
    if name not in REGISTRY:
        raise KeyError(
            f"Unknown scorer {name!r}. Registered scorers: {sorted(REGISTRY)}. "
            "Use register_scorer() to add custom ones."
        )
    return REGISTRY[name](**kwargs)
