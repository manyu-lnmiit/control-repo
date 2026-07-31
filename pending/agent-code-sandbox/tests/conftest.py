"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from agent_code_sandbox.audit import AuditLog
from agent_code_sandbox.core.limits import ResourceLimits
from agent_code_sandbox.core.policy import SandboxPolicy
from agent_code_sandbox.core.sandbox import Sandbox


@pytest.fixture
def fast_limits() -> ResourceLimits:
    """Limits with a short timeout so tests run quickly."""
    return ResourceLimits(cpu_seconds=2, memory_mb=128, wall_timeout_seconds=3.0)


@pytest.fixture
def sandbox(fast_limits: ResourceLimits) -> Sandbox:
    return Sandbox(policy=SandboxPolicy(), limits=fast_limits)


@pytest.fixture
def audit_log(tmp_path) -> AuditLog:
    return AuditLog(path=tmp_path / "audit.jsonl")
