"""Tests for the best-effort network isolation feature.

These are written to be robust inside constrained/CI/dev containers where
`unshare -n` may not be usable (e.g. no CAP_SYS_ADMIN, user namespaces
disabled). We never assert that `unshare` *succeeds* -- only that the
Sandbox reports a sane `network_isolation` value and does not crash either
way.
"""

from __future__ import annotations

import shutil

from agent_code_sandbox.core.limits import ResourceLimits
from agent_code_sandbox.core.policy import SandboxPolicy
from agent_code_sandbox.core.sandbox import Sandbox
from agent_code_sandbox.executors.python_executor import run_python


def test_network_isolation_field_is_populated() -> None:
    limits = ResourceLimits(cpu_seconds=2, memory_mb=64, wall_timeout_seconds=5.0)
    sandbox = Sandbox(policy=SandboxPolicy(allow_network=False), limits=limits)
    result = run_python(sandbox, "print('ok')")

    assert result.network_isolation in ("unshare", "best-effort-env-only")
    # Regardless of which isolation path was used, execution itself must
    # not crash / must still complete (possibly with a nonzero exit if
    # unshare is unprivileged in this environment -- that's handled by the
    # graceful fallback path, not surfaced as a Python exception).
    assert result.exit_code is not None


def test_allow_network_true_disables_isolation_attempt() -> None:
    limits = ResourceLimits(cpu_seconds=2, memory_mb=64, wall_timeout_seconds=5.0)
    sandbox = Sandbox(policy=SandboxPolicy(allow_network=True), limits=limits)
    result = run_python(sandbox, "print('ok')")
    assert result.network_isolation == "disabled"
    assert result.success is True


def test_proxy_env_vars_stripped_when_network_disallowed(monkeypatch) -> None:
    monkeypatch.setenv("https_proxy", "http://proxy.example:8080")
    limits = ResourceLimits(cpu_seconds=2, memory_mb=64, wall_timeout_seconds=5.0)
    policy = SandboxPolicy(
        allow_network=False,
        env_allowlist=(*SandboxPolicy().env_allowlist, "https_proxy"),
    )
    sandbox = Sandbox(policy=policy, limits=limits)
    result = run_python(
        sandbox,
        "import os\nprint('https_proxy' in os.environ)\n",
    )
    assert result.stdout.strip() == "False"


def test_unshare_present_or_absent_does_not_crash_sandbox() -> None:
    """Whether or not `unshare` is installed on this host, running a
    simple snippet with network isolation requested must complete without
    raising, and must gracefully fall back if unshare is present but
    unprivileged."""
    has_unshare = shutil.which("unshare") is not None
    limits = ResourceLimits(cpu_seconds=2, memory_mb=64, wall_timeout_seconds=5.0)
    sandbox = Sandbox(policy=SandboxPolicy(allow_network=False), limits=limits)
    result = run_python(sandbox, "print('still alive')")

    if not has_unshare:
        assert result.network_isolation == "best-effort-env-only"
        assert result.success is True
    else:
        # unshare exists but may or may not have the privileges required
        # in this sandboxed/dev-container environment; either outcome is
        # acceptable as long as we didn't crash and got *some* result.
        assert result.network_isolation in ("unshare", "best-effort-env-only")
