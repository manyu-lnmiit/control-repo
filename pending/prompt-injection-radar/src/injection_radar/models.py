"""Core data types shared across detectors, the scanner, and the sanitizer."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum


class RiskLevel(IntEnum):
    """Overall risk classification for a scanned document.

    Ordered so comparisons (e.g. ``result.risk_level >= RiskLevel.HIGH``)
    work naturally.
    """

    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

    @classmethod
    def from_score(cls, score: float) -> RiskLevel:
        if score >= 80:
            return cls.CRITICAL
        if score >= 55:
            return cls.HIGH
        if score >= 30:
            return cls.MEDIUM
        if score > 0:
            return cls.LOW
        return cls.NONE


@dataclass(frozen=True)
class Finding:
    """A single suspicious span discovered by one detector.

    Attributes:
        detector: Name of the detector that produced this finding.
        category: Short machine-readable category, e.g. ``"instruction_override"``.
        message: Human-readable explanation of why this span is suspicious.
        span: ``(start, end)`` character offsets into the scanned text.
        matched_text: The exact substring that triggered the finding.
        severity: Contribution to the overall risk score, 0-100.
    """

    detector: str
    category: str
    message: str
    span: tuple[int, int]
    matched_text: str
    severity: float

    def __post_init__(self) -> None:
        if self.span[0] < 0 or self.span[1] < self.span[0]:
            raise ValueError(f"invalid span {self.span!r}")
        if not (0 <= self.severity <= 100):
            raise ValueError(f"severity must be in [0, 100], got {self.severity}")


@dataclass
class ScanResult:
    """Aggregate result of scanning one piece of text."""

    text: str
    findings: list[Finding] = field(default_factory=list)

    @property
    def score(self) -> float:
        """Aggregate 0-100 risk score.

        Uses a diminishing-returns combination (probabilistic OR over
        per-finding severities, scaled to 0-100) rather than a flat sum, so
        many low-severity findings can still add up without one finding
        alone always dominating, and without the score blowing past 100.
        """
        if not self.findings:
            return 0.0
        remaining = 1.0
        for f in self.findings:
            remaining *= 1.0 - (f.severity / 100.0)
        return round((1.0 - remaining) * 100.0, 2)

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.from_score(self.score)

    @property
    def is_suspicious(self) -> bool:
        return self.risk_level >= RiskLevel.MEDIUM

    def top_findings(self, n: int = 5) -> list[Finding]:
        return sorted(self.findings, key=lambda f: f.severity, reverse=True)[:n]

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "risk_level": self.risk_level.name,
            "is_suspicious": self.is_suspicious,
            "findings": [
                {
                    "detector": f.detector,
                    "category": f.category,
                    "message": f.message,
                    "span": list(f.span),
                    "matched_text": f.matched_text,
                    "severity": f.severity,
                }
                for f in self.findings
            ],
        }
