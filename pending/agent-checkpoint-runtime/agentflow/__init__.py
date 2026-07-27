"""agentflow: a durable execution runtime for multi-step LLM agent workflows.

Public API:
    Workflow        - orchestrates checkpointed, resumable step execution
    SQLiteStore      - default persistence backend
    ApprovalPending  - raised when a workflow pauses on a human approval gate
    StepFailed       - raised when a step exhausts its retry budget
    WorkflowFailed   - raised when a workflow run terminates in failure
"""

from .core import Workflow
from .exceptions import ApprovalPending, StepFailed, WorkflowFailed
from .store import RunRecord, SQLiteStore, StepRecord, Store

__all__ = [
    "Workflow",
    "SQLiteStore",
    "Store",
    "RunRecord",
    "StepRecord",
    "ApprovalPending",
    "StepFailed",
    "WorkflowFailed",
]

__version__ = "0.1.0"
