"""agent-code-sandbox: a dependency-light sandboxed execution engine for
running LLM/agent-generated Python and shell snippets safely.

See the README for the full security model. In short: this package uses
POSIX rlimits, wall-clock timeouts, environment sanitization, an isolated
temporary working directory, and (best-effort) network namespace isolation
to reduce the blast radius of agent-generated code. It is NOT a substitute
for a container or VM-grade isolation boundary.
"""

from agent_code_sandbox.core.limits import ResourceLimits
from agent_code_sandbox.core.policy import SandboxPolicy
from agent_code_sandbox.core.result import ExecutionResult
from agent_code_sandbox.core.sandbox import Sandbox

__all__ = [
    "Sandbox",
    "SandboxPolicy",
    "ResourceLimits",
    "ExecutionResult",
]

__version__ = "0.1.0"
