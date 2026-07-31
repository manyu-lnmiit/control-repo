"""Resource limit definitions and the low-level rlimit application logic.

This module wraps the POSIX ``resource`` module. It is intentionally kept
separate from the process-spawning logic so it can be unit tested and reused
by both the Python and shell executors.
"""

from __future__ import annotations

import resource
from dataclasses import dataclass


@dataclass(frozen=True)
class ResourceLimits:
    """Resource limits applied to a sandboxed subprocess.

    Attributes:
        cpu_seconds: Maximum CPU time (seconds) the child process may
            consume, enforced via ``RLIMIT_CPU``. The kernel sends
            ``SIGXCPU``/``SIGKILL`` to the process once exceeded.
        memory_mb: Maximum address space size (megabytes) the child process
            may allocate, enforced via ``RLIMIT_AS``. Exceeding this
            typically raises ``MemoryError`` inside the child or causes the
            allocator to fail.
        fsize_mb: Maximum size (megabytes) of any file the child process may
            create/write, enforced via ``RLIMIT_FSIZE``.
        wall_timeout_seconds: Wall-clock timeout enforced by the *parent*
            process (not the kernel). If the child (and its process group)
            is still alive after this many seconds, it is forcibly killed.
        nproc: Optional maximum number of processes/threads the child (and
            its descendants, subject to platform behavior) may create, via
            ``RLIMIT_NPROC``. ``None`` leaves the inherited limit untouched.
    """

    cpu_seconds: int = 5
    memory_mb: int = 256
    fsize_mb: int = 10
    wall_timeout_seconds: float = 10.0
    nproc: int | None = 64

    def __post_init__(self) -> None:
        if self.cpu_seconds <= 0:
            raise ValueError("cpu_seconds must be positive")
        if self.memory_mb <= 0:
            raise ValueError("memory_mb must be positive")
        if self.fsize_mb <= 0:
            raise ValueError("fsize_mb must be positive")
        if self.wall_timeout_seconds <= 0:
            raise ValueError("wall_timeout_seconds must be positive")
        if self.nproc is not None and self.nproc <= 0:
            raise ValueError("nproc must be positive when set")

    @property
    def memory_bytes(self) -> int:
        return self.memory_mb * 1024 * 1024

    @property
    def fsize_bytes(self) -> int:
        return self.fsize_mb * 1024 * 1024

    def as_dict(self) -> dict[str, float | int | None]:
        """Return a JSON-serializable summary, useful for audit logging."""
        return {
            "cpu_seconds": self.cpu_seconds,
            "memory_mb": self.memory_mb,
            "fsize_mb": self.fsize_mb,
            "wall_timeout_seconds": self.wall_timeout_seconds,
            "nproc": self.nproc,
        }


def apply_rlimits(limits: ResourceLimits) -> None:
    """Apply ``limits`` to the *current* process via ``resource.setrlimit``.

    This function is meant to be called from a ``preexec_fn`` passed to
    ``subprocess.Popen`` -- i.e. it runs in the forked child, after
    ``fork()`` but before ``exec()``. It must therefore avoid anything that
    isn't async-signal-safe-ish in spirit (we keep it to simple syscalls).

    Also calls ``os.setsid()`` so the child becomes the leader of a new
    process group/session, which lets the parent reliably kill the whole
    group (including any descendants) on timeout.
    """
    import os

    # New session/process group so the parent can kill the whole tree.
    try:
        os.setsid()
    except OSError:
        # Already a session/group leader; not fatal.
        pass

    resource.setrlimit(
        resource.RLIMIT_CPU, (limits.cpu_seconds, limits.cpu_seconds)
    )
    resource.setrlimit(
        resource.RLIMIT_AS, (limits.memory_bytes, limits.memory_bytes)
    )
    resource.setrlimit(
        resource.RLIMIT_FSIZE, (limits.fsize_bytes, limits.fsize_bytes)
    )
    if limits.nproc is not None:
        try:
            resource.setrlimit(
                resource.RLIMIT_NPROC, (limits.nproc, limits.nproc)
            )
        except (ValueError, OSError):
            # RLIMIT_NPROC is per-uid on Linux and may not be lowerable in
            # some environments (e.g. already below the requested value,
            # or unsupported). Not fatal -- other limits still apply.
            pass
