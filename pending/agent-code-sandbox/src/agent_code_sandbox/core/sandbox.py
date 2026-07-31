"""The core Sandbox engine: spawns rlimit-constrained subprocesses, enforces
a wall-clock timeout by killing the whole process group, and produces a
structured ExecutionResult.

This module intentionally contains no knowledge of "python code" vs "shell
command" -- that distinction lives in ``executors/``. ``Sandbox.run`` takes
an already-built argv list and executes it under policy.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import tempfile
import time
from functools import partial

from agent_code_sandbox.core.limits import ResourceLimits, apply_rlimits
from agent_code_sandbox.core.policy import SandboxPolicy
from agent_code_sandbox.core.result import ExecutionResult

#: Cached lookup of whether the `unshare` binary is available on this host.
_UNSHARE_PATH = shutil.which("unshare")


class Sandbox:
    """Executes argv-style commands under resource limits, a filesystem
    policy, and a wall-clock timeout, in an isolated temporary directory.
    """

    def __init__(
        self,
        policy: SandboxPolicy | None = None,
        limits: ResourceLimits | None = None,
    ) -> None:
        self.policy = policy or SandboxPolicy()
        self.limits = limits or ResourceLimits()

    def run(self, argv: list[str]) -> ExecutionResult:
        """Run ``argv`` under the configured policy and limits.

        A fresh temporary directory is created as the subprocess's cwd for
        the duration of the call and removed afterwards. Network isolation
        (if ``policy.allow_network`` is False) is applied via ``unshare -n``
        when available, otherwise falls back to environment-variable-only
        best effort.
        """
        network_isolation = "disabled"
        effective_argv = list(argv)

        if not self.policy.allow_network:
            if _UNSHARE_PATH is not None:
                effective_argv = [_UNSHARE_PATH, "-n", "--", *effective_argv]
                network_isolation = "unshare"
            else:
                network_isolation = "best-effort-env-only"

        env = self.policy.build_env(dict(os.environ))

        with tempfile.TemporaryDirectory(prefix="acs-") as workdir:
            start = time.monotonic()
            try:
                proc = subprocess.Popen(
                    effective_argv,
                    cwd=workdir,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    preexec_fn=partial(apply_rlimits, self.limits),
                    start_new_session=True,
                )
            except PermissionError as exc:
                # Most commonly: `unshare -n` requires CAP_SYS_ADMIN /
                # unprivileged user namespaces disabled in this container.
                # Fall back gracefully to running without network
                # isolation rather than crashing the caller.
                if network_isolation == "unshare":
                    return self._run_without_unshare(argv, workdir, env)
                return ExecutionResult(
                    stderr=str(exc),
                    exit_code=-1,
                    killed_reason=f"failed to start process: {exc}",
                    network_isolation=network_isolation,
                )
            except OSError as exc:
                return ExecutionResult(
                    stderr=str(exc),
                    exit_code=-1,
                    killed_reason=f"failed to start process: {exc}",
                    network_isolation=network_isolation,
                )

            result = self._wait_with_timeout(proc, start)
            result.network_isolation = network_isolation
            return result

    def _run_without_unshare(
        self, argv: list[str], workdir: str, env: dict[str, str]
    ) -> ExecutionResult:
        """Fallback path used when ``unshare -n`` itself fails to spawn
        (e.g. permission denied for creating a new network namespace in
        this container). Re-runs the plain argv with env-only network
        best-effort isolation instead of raising.
        """
        start = time.monotonic()
        try:
            proc = subprocess.Popen(
                argv,
                cwd=workdir,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                preexec_fn=partial(apply_rlimits, self.limits),
                start_new_session=True,
            )
        except OSError as exc:
            return ExecutionResult(
                stderr=str(exc),
                exit_code=-1,
                killed_reason=f"failed to start process: {exc}",
                network_isolation="best-effort-env-only",
            )
        result = self._wait_with_timeout(proc, start)
        result.network_isolation = "best-effort-env-only"
        result.extra["unshare_fallback"] = "unshare -n failed to start; fell back"
        return result

    def _wait_with_timeout(
        self, proc: subprocess.Popen, start: float
    ) -> ExecutionResult:
        timeout = self.limits.wall_timeout_seconds
        timed_out = False
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            self._kill_process_group(proc)
            try:
                stdout, stderr = proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                stdout, stderr = "", ""
        duration = time.monotonic() - start

        exit_code = proc.returncode if proc.returncode is not None else -1
        memory_exceeded = self._looks_like_oom(exit_code, stderr)

        killed_reason: str | None = None
        if timed_out:
            killed_reason = (
                f"wall-clock timeout of {timeout}s exceeded; process group killed"
            )
        elif memory_exceeded:
            killed_reason = "exceeded memory limit (RLIMIT_AS)"
        elif exit_code < 0:
            sig = -exit_code
            try:
                sig_name = signal.Signals(sig).name
            except ValueError:
                sig_name = str(sig)
            if sig == signal.SIGXCPU:
                killed_reason = "exceeded CPU time limit (RLIMIT_CPU)"
            else:
                killed_reason = f"terminated by signal {sig_name}"

        return ExecutionResult(
            stdout=stdout or "",
            stderr=stderr or "",
            exit_code=exit_code,
            timed_out=timed_out,
            memory_exceeded=memory_exceeded,
            duration_seconds=duration,
            killed_reason=killed_reason,
        )

    @staticmethod
    def _kill_process_group(proc: subprocess.Popen) -> None:
        """Kill the entire process group led by ``proc`` (which was started
        with ``start_new_session=True``), so timed-out children can't
        survive the parent."""
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass

    @staticmethod
    def _looks_like_oom(exit_code: int, stderr: str) -> bool:
        """Best-effort heuristic: RLIMIT_AS causes malloc/mmap failures,
        which for CPython usually surfaces as a MemoryError traceback (exit
        code 1) or, for some allocation patterns, a SIGSEGV/SIGABRT
        (negative exit code). We check the common cases.
        """
        if exit_code < 0:
            sig = -exit_code
            if sig in (signal.SIGSEGV, signal.SIGABRT, signal.SIGBUS):
                return True
        if "MemoryError" in stderr:
            return True
        return False
