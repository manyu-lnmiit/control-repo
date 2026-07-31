from __future__ import annotations

import pytest

from agent_code_sandbox.core.limits import ResourceLimits


def test_defaults_are_sane() -> None:
    limits = ResourceLimits()
    assert limits.cpu_seconds > 0
    assert limits.memory_mb > 0
    assert limits.wall_timeout_seconds > 0


def test_memory_and_fsize_bytes_conversion() -> None:
    limits = ResourceLimits(memory_mb=10, fsize_mb=2)
    assert limits.memory_bytes == 10 * 1024 * 1024
    assert limits.fsize_bytes == 2 * 1024 * 1024


@pytest.mark.parametrize(
    "kwargs",
    [
        {"cpu_seconds": 0},
        {"memory_mb": -1},
        {"fsize_mb": 0},
        {"wall_timeout_seconds": -5},
        {"nproc": 0},
    ],
)
def test_invalid_values_rejected(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        ResourceLimits(**kwargs)


def test_as_dict_roundtrip() -> None:
    limits = ResourceLimits(cpu_seconds=3, memory_mb=64)
    d = limits.as_dict()
    assert d["cpu_seconds"] == 3
    assert d["memory_mb"] == 64
