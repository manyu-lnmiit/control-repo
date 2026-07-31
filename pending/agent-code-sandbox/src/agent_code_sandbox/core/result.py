"""Structured result type returned by every sandboxed execution."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ExecutionResult:
    """The outcome of a single sandboxed execution.

    Attributes:
        stdout: Captured standard output (truncated at a reasonable cap by
            the caller if desired; not truncated here).
        stderr: Captured standard error.
        exit_code: Process exit code, or -1 if the process never started
            (e.g. blocked by policy) or was killed before producing one.
        timed_out: True if the wall-clock timeout was hit and the process
            group was forcibly killed.
        memory_exceeded: True if we detected the process was killed for
            exceeding its memory limit (best-effort heuristic based on
            exit signal / MemoryError markers).
        duration_seconds: Wall-clock time the execution took.
        killed_reason: Human-readable reason the process was killed/blocked,
            or None if it completed normally.
        policy_violation: True if execution was blocked before a subprocess
            was ever spawned (e.g. disallowed shell command).
        network_isolation: How network isolation was applied for this run:
            one of "unshare", "best-effort-env-only", or "disabled".
    """

    stdout: str = ""
    stderr: str = ""
    exit_code: int = -1
    timed_out: bool = False
    memory_exceeded: bool = False
    duration_seconds: float = 0.0
    killed_reason: str | None = None
    policy_violation: bool = False
    network_isolation: str = "disabled"
    extra: dict[str, str] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        """True if the process ran to completion, exited 0, and was not
        killed, timed out, or blocked by policy."""
        return (
            not self.policy_violation
            and not self.timed_out
            and not self.memory_exceeded
            and self.exit_code == 0
        )

    def to_dict(self) -> dict[str, object]:
        """JSON-serializable representation, e.g. for audit logging or the
        HTTP API."""
        return {
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "timed_out": self.timed_out,
            "memory_exceeded": self.memory_exceeded,
            "duration_seconds": self.duration_seconds,
            "killed_reason": self.killed_reason,
            "policy_violation": self.policy_violation,
            "network_isolation": self.network_isolation,
            "success": self.success,
            "extra": self.extra,
        }
