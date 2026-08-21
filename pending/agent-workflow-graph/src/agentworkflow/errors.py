"""Exception hierarchy for agent-workflow-graph."""

from __future__ import annotations


class GraphValidationError(Exception):
    """Base class for errors raised while building or validating a graph."""


class DuplicateNodeError(GraphValidationError):
    """Raised when a node name is registered more than once."""


class UnknownNodeError(GraphValidationError):
    """Raised when an edge references a node that was never added."""


class CycleDetectedError(GraphValidationError):
    """Raised when the graph contains an unconditional (static) cycle.

    Conditional loops (a router that can send execution back to an earlier
    node) are allowed and are the normal way to model agentic retry/refine
    loops; this error only fires for cycles built entirely out of
    unconditional edges, which can never terminate.
    """


class MaxStepsExceededError(Exception):
    """Raised at execution time when a run exceeds ``max_steps``.

    This is the safety valve for conditional loops (e.g. a
    plan -> act -> critique -> plan cycle) that fail to converge.
    """


class NodeExecutionError(Exception):
    """Wraps an exception raised inside a node's callable, with context."""

    def __init__(self, node_name: str, original: BaseException) -> None:
        self.node_name = node_name
        self.original = original
        super().__init__(f"node '{node_name}' raised {original!r}")
