"""Exceptions raised by the agentflow runtime."""

from __future__ import annotations


class AgentFlowError(Exception):
    """Base class for all agentflow errors."""


class ApprovalPending(AgentFlowError):
    """Raised when a workflow reaches a human-in-the-loop gate that has not
    yet been approved. The workflow run is persisted in a ``waiting`` state
    and can be resumed later by re-invoking :meth:`Workflow.run` once the
    gate has been approved (e.g. via the ``agentflow approve`` CLI command).
    """

    def __init__(self, run_id: str, gate_name: str):
        self.run_id = run_id
        self.gate_name = gate_name
        super().__init__(
            f"run {run_id!r} is waiting for approval at gate {gate_name!r}"
        )


class StepFailed(AgentFlowError):
    """Raised when a step exhausts its retry budget without succeeding."""

    def __init__(self, step_name: str, cause: BaseException | None):
        self.step_name = step_name
        self.cause = cause
        message = f"step {step_name!r} failed"
        if cause is not None:
            message += f": {cause!r}"
        super().__init__(message)


class WorkflowFailed(AgentFlowError):
    """Raised when a workflow run terminates because a step failed."""

    def __init__(self, run_id: str, cause: BaseException):
        self.run_id = run_id
        self.cause = cause
        super().__init__(f"workflow run {run_id!r} failed: {cause!r}")
