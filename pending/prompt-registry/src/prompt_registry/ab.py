"""Deterministic, weighted A/B routing between prompt versions.

Assignment is a stable hash of ``(experiment_key, unit_id)`` mapped onto a
cumulative weight table, so the same user/session is always routed to the
same variant for the lifetime of an experiment -- no external state
required.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class Variant:
    """One arm of an experiment.

    Attributes:
        name: Variant identifier (e.g. "control", "treatment").
        version: The prompt version number this variant renders.
        weight: Relative traffic weight (weights need not sum to 100; they
            are normalized automatically).
    """

    name: str
    version: int
    weight: float = 1.0


@dataclass(frozen=True)
class ExperimentConfig:
    """A named A/B (or A/B/n) experiment over versions of one prompt."""

    prompt_name: str
    key: str
    variants: list[Variant]

    def __post_init__(self) -> None:
        if not self.variants:
            raise ValueError("An experiment needs at least one variant")
        if any(v.weight <= 0 for v in self.variants):
            raise ValueError("Variant weights must be positive")


def _stable_unit_fraction(key: str, unit_id: str) -> float:
    """Map (key, unit_id) deterministically onto [0, 1)."""
    digest = hashlib.sha256(f"{key}:{unit_id}".encode()).hexdigest()
    # Use the first 13 hex digits (52 bits) for a stable, evenly distributed fraction.
    as_int = int(digest[:13], 16)
    return as_int / float(16 ** 13)


def choose_variant(config: ExperimentConfig, unit_id: str) -> Variant:
    """Deterministically pick the :class:`Variant` a given unit falls into.

    The same ``unit_id`` always resolves to the same variant for a given
    ``config.key``, which keeps a single user's experience consistent
    across an experiment's lifetime.
    """
    fraction = _stable_unit_fraction(config.key, unit_id)
    total_weight = sum(v.weight for v in config.variants)
    cumulative = 0.0
    for variant in config.variants:
        cumulative += variant.weight / total_weight
        if fraction < cumulative:
            return variant
    return config.variants[-1]
