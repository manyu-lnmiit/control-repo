"""Executes Python source code inside the Sandbox."""

from __future__ import annotations

import os
import sys
import tempfile

from agent_code_sandbox.core.result import ExecutionResult
from agent_code_sandbox.core.sandbox import Sandbox


def run_python(
    sandbox: Sandbox,
    code: str,
    *,
    args: list[str] | None = None,
) -> ExecutionResult:
    """Run ``code`` as a standalone Python script inside ``sandbox``.

    The code is written to a temporary ``.py`` file (rather than passed via
    ``python3 -c``) so that multi-line programs, syntax requiring real
    newlines, and reasonably-sized snippets all work without shell-quoting
    hazards. The file lives outside the sandbox's per-run temp cwd (it must
    be readable by the child before that directory context matters) and is
    cleaned up after execution.

    Args:
        sandbox: The configured ``Sandbox`` to execute under.
        code: Python source code to execute.
        args: Optional extra command-line arguments passed to the script.

    Returns:
        The ``ExecutionResult`` of running the script.
    """
    fd, path = tempfile.mkstemp(prefix="acs-snippet-", suffix=".py")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(code)
        argv = [sys.executable, path, *(args or [])]
        return sandbox.run(argv)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
