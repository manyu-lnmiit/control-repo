"""agent-workflow-graph: composable DAG orchestration for multi-agent LLM workflows."""

from .errors import (
    CycleDetectedError,
    DuplicateNodeError,
    GraphValidationError,
    MaxStepsExceededError,
    UnknownNodeError,
)
from .executor import ExecutionResult, Executor, NodeTrace
from .graph import END, START, Edge, Node, StateGraph
from .visualize import to_mermaid

__all__ = [
    "StateGraph",
    "Node",
    "Edge",
    "START",
    "END",
    "Executor",
    "ExecutionResult",
    "NodeTrace",
    "to_mermaid",
    "GraphValidationError",
    "CycleDetectedError",
    "DuplicateNodeError",
    "UnknownNodeError",
    "MaxStepsExceededError",
]

__version__ = "0.1.0"
