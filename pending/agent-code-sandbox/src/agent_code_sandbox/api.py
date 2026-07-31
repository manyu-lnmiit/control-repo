"""Optional FastAPI HTTP service exposing the sandbox over HTTP.

This module is only usable if the ``api`` extra is installed
(``pip install agent-code-sandbox[api]``). Importing the core package
(``agent_code_sandbox``) never requires FastAPI -- only importing
``agent_code_sandbox.api`` does, and that import is guarded with a clear
error message if the extra isn't installed.

Run with::

    uvicorn agent_code_sandbox.api:app
"""

from __future__ import annotations

try:
    from fastapi import FastAPI
    from pydantic import BaseModel
except ImportError as exc:  # pragma: no cover - exercised via importorskip
    raise ImportError(
        "agent_code_sandbox.api requires the 'api' extra. Install it with: "
        "pip install agent-code-sandbox[api]"
    ) from exc

from agent_code_sandbox.audit import AuditLog
from agent_code_sandbox.core.limits import ResourceLimits
from agent_code_sandbox.core.policy import SandboxPolicy
from agent_code_sandbox.core.sandbox import Sandbox
from agent_code_sandbox.executors.python_executor import run_python
from agent_code_sandbox.executors.shell_executor import run_shell

app = FastAPI(
    title="agent-code-sandbox",
    description=(
        "HTTP API for sandboxed execution of LLM/agent-generated Python "
        "and shell snippets."
    ),
    version="0.1.0",
)


class ExecuteRequest(BaseModel):
    code: str
    timeout: float = 10.0
    memory_mb: int = 256
    cpu_seconds: int = 5


class ShellExecuteRequest(BaseModel):
    command: str
    timeout: float = 10.0
    memory_mb: int = 256
    cpu_seconds: int = 5


def _limits_from(req: ExecuteRequest | ShellExecuteRequest) -> ResourceLimits:
    return ResourceLimits(
        cpu_seconds=req.cpu_seconds,
        memory_mb=req.memory_mb,
        wall_timeout_seconds=req.timeout,
    )


@app.post("/execute/python")
def execute_python(req: ExecuteRequest) -> dict:
    """Run a Python snippet in the sandbox and return the structured
    result as JSON."""
    limits = _limits_from(req)
    sandbox = Sandbox(policy=SandboxPolicy(), limits=limits)
    result = run_python(sandbox, req.code)
    AuditLog().record("python", req.code, limits, result)
    return result.to_dict()


@app.post("/execute/shell")
def execute_shell(req: ShellExecuteRequest) -> dict:
    """Run a shell command in the sandbox (subject to allowlisting) and
    return the structured result as JSON."""
    limits = _limits_from(req)
    sandbox = Sandbox(policy=SandboxPolicy(), limits=limits)
    result = run_shell(sandbox, req.command)
    AuditLog().record("shell", req.command, limits, result)
    return result.to_dict()


@app.get("/audit")
def get_audit(last: int = 20, only: str | None = None) -> list[dict]:
    """Return the last ``last`` audit entries, optionally filtered by
    ``only=success`` or ``only=failure``."""
    success_filter = None
    if only == "success":
        success_filter = True
    elif only == "failure":
        success_filter = False
    entries = AuditLog().last(last, success=success_filter)
    return [
        {
            "timestamp": e.timestamp,
            "kind": e.kind,
            "payload_sha256": e.payload_sha256,
            "limits": e.limits,
            "result": e.result,
        }
        for e in entries
    ]
