"""Detector protocol that every heuristic module implements."""

from __future__ import annotations

from typing import Protocol

from ..models import Finding


class Detector(Protocol):
    """A detector inspects raw text and yields zero or more Findings.

    Implementations must be pure functions of their input text -- no shared
    mutable state -- so a Scanner can run them in any order and cache
    results safely.
    """

    name: str

    def scan(self, text: str) -> list[Finding]: ...
