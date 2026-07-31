"""Command-line interface for agent-code-sandbox.

Usage examples::

    agent-code-sandbox run-python "print(1 + 1)"
    agent-code-sandbox run-python --file snippet.py
    agent-code-sandbox run-shell "echo hello"
    agent-code-sandbox audit --last 5
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from agent_code_sandbox.audit import AuditLog
from agent_code_sandbox.core.limits import ResourceLimits
from agent_code_sandbox.core.policy import SandboxPolicy
from agent_code_sandbox.core.sandbox import Sandbox
from agent_code_sandbox.executors.python_executor import run_python
from agent_code_sandbox.executors.shell_executor import run_shell


def _build_limits(args: argparse.Namespace) -> ResourceLimits:
    return ResourceLimits(
        cpu_seconds=args.cpu_seconds,
        memory_mb=args.memory_mb,
        wall_timeout_seconds=args.timeout,
    )


def _add_limit_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Wall-clock timeout in seconds (default: 10.0)",
    )
    parser.add_argument(
        "--memory-mb",
        type=int,
        default=256,
        help="Memory limit in megabytes (default: 256)",
    )
    parser.add_argument(
        "--cpu-seconds",
        type=int,
        default=5,
        help="CPU time limit in seconds (default: 5)",
    )


def _print_result(result, stream=None) -> None:
    if stream is None:
        stream = sys.stdout
    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    if result.stderr:
        print(result.stderr, end="" if result.stderr.endswith("\n") else "\n", file=sys.stderr)
    status = "OK" if result.success else "FAILED"
    print(
        f"[{status}] exit_code={result.exit_code} timed_out={result.timed_out} "
        f"memory_exceeded={result.memory_exceeded} "
        f"duration={result.duration_seconds:.3f}s"
        + (f" reason={result.killed_reason!r}" if result.killed_reason else ""),
        file=stream,
    )


def cmd_run_python(args: argparse.Namespace) -> int:
    if args.file:
        with open(args.file, encoding="utf-8") as f:
            code = f.read()
    elif args.code is not None:
        code = args.code
    else:
        code = sys.stdin.read()

    limits = _build_limits(args)
    sandbox = Sandbox(policy=SandboxPolicy(), limits=limits)
    result = run_python(sandbox, code)
    AuditLog().record("python", code, limits, result)
    _print_result(result)
    return 0 if result.success else 1


def cmd_run_shell(args: argparse.Namespace) -> int:
    limits = _build_limits(args)
    sandbox = Sandbox(policy=SandboxPolicy(), limits=limits)
    result = run_shell(sandbox, args.command)
    AuditLog().record("shell", args.command, limits, result)
    _print_result(result)
    return 0 if result.success else 1


def cmd_audit(args: argparse.Namespace) -> int:
    log = AuditLog()
    success_filter: bool | None = None
    if args.only == "success":
        success_filter = True
    elif args.only == "failure":
        success_filter = False

    entries = log.last(args.last, success=success_filter)
    if not entries:
        print("No audit entries found.")
        return 0
    for entry in entries:
        result = entry.result
        print(
            f"{entry.timestamp:.0f}  {entry.kind:6s}  sha256={entry.payload_sha256[:12]}  "
            f"success={result.get('success')}  exit_code={result.get('exit_code')}  "
            f"timed_out={result.get('timed_out')}"
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-code-sandbox",
        description=(
            "Sandboxed execution engine for running LLM/agent-generated "
            "Python and shell snippets safely."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_python = subparsers.add_parser(
        "run-python", help="Run a Python code snippet in the sandbox."
    )
    group = p_python.add_mutually_exclusive_group()
    group.add_argument("code", nargs="?", help="Python code to execute.")
    group.add_argument("--file", help="Path to a Python file to execute.")
    _add_limit_flags(p_python)
    p_python.set_defaults(func=cmd_run_python)

    p_shell = subparsers.add_parser(
        "run-shell", help="Run a shell command in the sandbox (allowlisted)."
    )
    p_shell.add_argument("command", help="Shell command to execute.")
    _add_limit_flags(p_shell)
    p_shell.set_defaults(func=cmd_run_shell)

    p_audit = subparsers.add_parser(
        "audit", help="Query the execution audit log."
    )
    p_audit.add_argument(
        "--last", type=int, default=10, help="Number of entries to show."
    )
    p_audit.add_argument(
        "--only",
        choices=["success", "failure", "all"],
        default="all",
        help="Filter by execution outcome.",
    )
    p_audit.set_defaults(func=cmd_audit)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
