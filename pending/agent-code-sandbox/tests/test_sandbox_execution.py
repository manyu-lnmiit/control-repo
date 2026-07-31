"""End-to-end tests that actually spawn subprocesses under the Sandbox.

These are the most environment-sensitive tests in the suite. We keep
timeouts/limits small so the suite runs quickly, and we soften assertions
where container/CI environments may behave slightly differently (e.g.
memory-limit enforcement can surface as a nonzero exit rather than a
specific signal depending on the platform's malloc implementation).
"""

from __future__ import annotations

from agent_code_sandbox.core.limits import ResourceLimits
from agent_code_sandbox.core.policy import SandboxPolicy
from agent_code_sandbox.core.sandbox import Sandbox
from agent_code_sandbox.executors.python_executor import run_python
from agent_code_sandbox.executors.shell_executor import run_shell


def test_simple_python_snippet_succeeds(sandbox: Sandbox) -> None:
    result = run_python(sandbox, "print(1 + 1)")
    assert result.success is True
    assert result.stdout.strip() == "2"
    assert result.exit_code == 0


def test_python_snippet_with_error_exits_nonzero(sandbox: Sandbox) -> None:
    result = run_python(sandbox, "raise ValueError('boom')")
    assert result.success is False
    assert result.exit_code != 0
    assert "ValueError" in result.stderr


def test_cpu_hog_is_killed_or_marked_timed_out() -> None:
    """A tight infinite CPU loop must be stopped by either the RLIMIT_CPU
    kernel limit (surfacing as a nonzero/negative exit code) or the parent's
    wall-clock timeout (timed_out=True). Either outcome demonstrates the
    resource-limit enforcement is working; we don't require one specific
    mechanism since the exact timing race between SIGXCPU and the parent's
    `communicate(timeout=...)` can vary between environments.
    """
    limits = ResourceLimits(cpu_seconds=1, memory_mb=128, wall_timeout_seconds=4.0)
    sandbox = Sandbox(policy=SandboxPolicy(), limits=limits)
    code = "while True:\n    pass\n"
    result = run_python(sandbox, code)

    assert result.success is False
    assert (
        result.timed_out
        or result.exit_code != 0
    ), "expected the CPU hog to be killed via timeout or RLIMIT_CPU"
    # Should not have run anywhere close to unbounded -- generous upper
    # bound to avoid flakiness on slow CI runners.
    assert result.duration_seconds < 20


def test_memory_limit_kills_or_fails_allocation() -> None:
    """A process that tries to allocate far more memory than its RLIMIT_AS
    should fail to do so -- either raising MemoryError inside Python
    (nonzero exit) or being killed by the kernel (negative exit code /
    memory_exceeded). We assert it does NOT succeed, which is the
    behavior that actually matters for sandboxing.
    """
    limits = ResourceLimits(cpu_seconds=5, memory_mb=64, wall_timeout_seconds=8.0)
    sandbox = Sandbox(policy=SandboxPolicy(), limits=limits)
    code = (
        "data = []\n"
        "for _ in range(10_000):\n"
        "    data.append(bytearray(10 * 1024 * 1024))\n"  # 10MB chunks, way over 64MB
        "print('should not get here')\n"
    )
    result = run_python(sandbox, code)
    assert result.success is False


def test_fsize_limit_prevents_large_file_writes() -> None:
    limits = ResourceLimits(
        cpu_seconds=5, memory_mb=128, fsize_mb=1, wall_timeout_seconds=8.0
    )
    sandbox = Sandbox(policy=SandboxPolicy(), limits=limits)
    code = (
        "with open('big.bin', 'wb') as f:\n"
        "    for _ in range(20):\n"
        "        f.write(b'0' * 1024 * 1024)\n"  # 20MB total, way over 1MB limit
        "print('should not get here')\n"
    )
    result = run_python(sandbox, code)
    assert result.success is False


def test_env_is_sanitized_inside_sandbox(sandbox: Sandbox, monkeypatch) -> None:
    monkeypatch.setenv("SUPER_SECRET_TOKEN", "leak-me-not")
    result = run_python(
        sandbox,
        "import os\nprint('SUPER_SECRET_TOKEN' in os.environ)\n",
    )
    assert result.stdout.strip() == "False"


def test_cwd_is_isolated_temp_dir(sandbox: Sandbox) -> None:
    result = run_python(
        sandbox,
        "import os, tempfile\n"
        "cwd = os.getcwd()\n"
        "print(cwd.startswith(tempfile.gettempdir()) or 'acs-' in cwd)\n",
    )
    assert "True" in result.stdout


def test_run_shell_allowed_command_succeeds(sandbox: Sandbox) -> None:
    result = run_shell(sandbox, "echo hello-sandbox")
    assert result.success is True
    assert "hello-sandbox" in result.stdout


def test_run_shell_disallowed_command_blocked_before_spawn(sandbox: Sandbox) -> None:
    result = run_shell(sandbox, "curl http://example.com")
    assert result.policy_violation is True
    assert result.success is False
    assert result.exit_code == -1


def test_run_shell_operator_rejected(sandbox: Sandbox) -> None:
    result = run_shell(sandbox, "echo hi; rm -rf /")
    assert result.policy_violation is True
