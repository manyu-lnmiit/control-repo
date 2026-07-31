"""Filesystem, environment, and shell-command policy for sandboxed execution."""

from __future__ import annotations

import shlex
from dataclasses import dataclass, field

#: Default allowlist of environment variables copied through from the
#: parent process into the sandboxed subprocess. Everything else is
#: dropped so that secrets (API keys, tokens, etc.) sitting in the parent
#: environment are not leaked to agent-generated code.
DEFAULT_ENV_ALLOWLIST: tuple[str, ...] = ("PATH", "HOME", "LANG", "LC_ALL", "TZ")

#: Default allowlist of leading executable names permitted for
#: ``run_shell``. Deliberately conservative -- read-only, side-effect-free
#: utilities only.
DEFAULT_SHELL_ALLOWLIST: tuple[str, ...] = (
    "echo",
    "cat",
    "ls",
    "grep",
    "wc",
    "sort",
    "head",
    "tail",
    "python3",
)

#: Shell metacharacters/sequences that would allow command chaining,
#: substitution, or piping. Rejected by default unless the policy sets
#: ``allow_shell_operators=True``.
_SHELL_OPERATOR_TOKENS: tuple[str, ...] = (
    ";",
    "&&",
    "||",
    "|",
    "`",
    "$(",
    "&",
    ">",
    "<",
    "\n",
)

#: Environment variables that configure network access (proxies). Cleared
#: when ``allow_network=False`` as part of the best-effort network
#: isolation fallback (see ``Sandbox`` for the ``unshare -n`` path).
NETWORK_ENV_VARS: tuple[str, ...] = (
    "http_proxy",
    "https_proxy",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "all_proxy",
    "NO_PROXY",
    "no_proxy",
    "FTP_PROXY",
    "ftp_proxy",
)


@dataclass(frozen=True)
class SandboxPolicy:
    """Configuration for what a sandboxed execution is permitted to do.

    Attributes:
        extra_read_paths: Additional filesystem paths (beyond the isolated
            temp working directory) the sandboxed code is *conceptually*
            allowed to read. Note: this is advisory/documentation-level
            unless combined with OS-level mandatory access control -- this
            project does not implement a filesystem chroot or landlock
            sandbox (see README "Limitations / Security Model").
        extra_write_paths: Same as above, for writes.
        env_allowlist: Names of environment variables to copy from the
            parent process into the subprocess. All other parent env vars
            are dropped.
        extra_env: Additional environment variables to set explicitly in
            the subprocess environment (e.g. ``{"PYTHONDONTWRITEBYTECODE":
            "1"}``). Takes precedence over allowlisted parent values.
        shell_allowlist: Leading executable names permitted for
            ``run_shell``.
        allow_shell_operators: If False (default), shell metacharacters
            that enable chaining/substitution/piping are rejected before
            the command is ever parsed for allowlist checking.
        allow_network: If False (default), the sandbox attempts to isolate
            the subprocess from the network. Uses ``unshare -n`` when
            available; otherwise falls back to clearing proxy-related env
            vars only (best-effort, not a real network isolation
            boundary -- see README).
    """

    extra_read_paths: tuple[str, ...] = field(default_factory=tuple)
    extra_write_paths: tuple[str, ...] = field(default_factory=tuple)
    env_allowlist: tuple[str, ...] = DEFAULT_ENV_ALLOWLIST
    extra_env: dict[str, str] = field(default_factory=dict)
    shell_allowlist: tuple[str, ...] = DEFAULT_SHELL_ALLOWLIST
    allow_shell_operators: bool = False
    allow_network: bool = False

    def build_env(self, parent_env: dict[str, str]) -> dict[str, str]:
        """Build a sanitized environment dict for the subprocess.

        Starts from an *empty* environment (does not inherit the full
        parent environment) and only copies through variables named in
        ``env_allowlist`` that are actually present in ``parent_env``, then
        applies ``extra_env`` overrides. If ``allow_network`` is False,
        network-related proxy variables are stripped even if allowlisted.
        """
        env: dict[str, str] = {}
        for name in self.env_allowlist:
            if name in parent_env:
                env[name] = parent_env[name]
        env.update(self.extra_env)
        if not self.allow_network:
            for name in NETWORK_ENV_VARS:
                env.pop(name, None)
        return env

    def check_shell_command(
        self, command: str
    ) -> tuple[bool, str | None]:
        """Validate ``command`` against the shell policy.

        Returns:
            ``(True, None)`` if the command is permitted, or
            ``(False, reason)`` with a human-readable rejection reason.
        """
        if not command or not command.strip():
            return False, "empty command"

        if not self.allow_shell_operators:
            for token in _SHELL_OPERATOR_TOKENS:
                if token in command:
                    return (
                        False,
                        f"shell operator {token!r} is not allowed "
                        "(set allow_shell_operators=True to permit "
                        "chaining/substitution)",
                    )

        try:
            parts = shlex.split(command)
        except ValueError as exc:
            return False, f"could not parse command: {exc}"

        if not parts:
            return False, "empty command"

        executable = parts[0]
        # Reject absolute/relative path traversal attempts to dodge the
        # allowlist by name (e.g. "/bin/rm" vs "rm").
        base_name = executable.rsplit("/", 1)[-1]
        if base_name not in self.shell_allowlist:
            allowed = ", ".join(self.shell_allowlist)
            return (
                False,
                f"executable {executable!r} is not in the allowlist "
                f"({allowed})",
            )

        return True, None
