"""Executes shell commands inside the Sandbox, subject to allowlisting."""

from __future__ import annotations

import shlex

from agent_code_sandbox.core.result import ExecutionResult
from agent_code_sandbox.core.sandbox import Sandbox


def run_shell(sandbox: Sandbox, command: str) -> ExecutionResult:
    """Run ``command`` inside ``sandbox`` after validating it against the
    sandbox's ``SandboxPolicy``.

    The command is parsed with ``shlex.split`` and executed directly as an
    argv list (never via ``shell=True``), which means shell operators like
    pipes and redirects have no special meaning to the OS even if they
    somehow made it past the policy check -- the policy check exists to
    give a clear, fast ``PolicyViolation``-style rejection *before*
    spawning any process, and to stop confusing input (e.g. `` `whoami` ``
    passed as a literal argument) from being silently accepted.

    Args:
        sandbox: The configured ``Sandbox`` to execute under.
        command: The full shell command line, e.g. ``"echo hello"``.

    Returns:
        An ``ExecutionResult``. If the command is rejected by policy,
        ``policy_violation`` is True, ``exit_code`` is -1, and
        ``killed_reason`` explains why -- no subprocess is spawned.
    """
    allowed, reason = sandbox.policy.check_shell_command(command)
    if not allowed:
        return ExecutionResult(
            stderr=reason or "rejected by policy",
            exit_code=-1,
            policy_violation=True,
            killed_reason=reason,
        )

    argv = shlex.split(command)
    return sandbox.run(argv)
