"""Graph definition API for agent-workflow-graph.

A :class:`StateGraph` describes an agent workflow as nodes (steps that read
and produce partial state updates) connected by edges. Three edge kinds are
supported:

* **unconditional** -- ``add_edge(a, b)``: always go from ``a`` to ``b``.
* **conditional** -- ``add_conditional_edges(a, router, path_map)``: after
  ``a`` runs, call ``router(state)`` to pick a key into ``path_map``. This is
  how you express agentic loops (e.g. plan -> act -> critique -> plan) and
  branching (e.g. route to a "research" or "code" sub-agent).
* **parallel (fan-out)** -- ``add_parallel_edges(a, [b, c, d])``: after ``a``
  runs, execute ``b``, ``c`` and ``d`` concurrently. If they all route to the
  same downstream node, that node acts as an implicit join.

Call :meth:`StateGraph.compile` to validate the graph (unknown node
references, unreachable nodes, static/unconditional cycles) and obtain a
:class:`CompiledGraph` that :class:`agentworkflow.executor.Executor` can run.
"""

from __future__ import annotations

from collections.abc import Callable, Hashable
from dataclasses import dataclass, field
from typing import Any

from .errors import CycleDetectedError, DuplicateNodeError, GraphValidationError, UnknownNodeError

START = "__start__"
END = "__end__"

NodeFn = Callable[[dict[str, Any]], dict[str, Any] | None]
RouterFn = Callable[[dict[str, Any]], Hashable]


@dataclass(frozen=True)
class Node:
    """A single unit of work in the graph.

    ``fn`` receives the current shared state and returns a dict of partial
    updates to merge in (or ``None`` if it has no updates). ``retries`` and
    ``retry_delay`` give it simple resilience against transient failures
    (network hiccups, rate-limited LLM calls) without external dependencies.
    """

    name: str
    fn: NodeFn
    retries: int = 0
    retry_delay: float = 0.0


@dataclass(frozen=True)
class Edge:
    """Internal edge representation. Use the ``add_*`` methods, not this."""

    kind: str  # "static" | "conditional" | "parallel"
    targets: list[str] = field(default_factory=list)
    router: RouterFn | None = None
    path_map: dict[Hashable, str] | None = None


class StateGraph:
    """Builder for a directed graph of agent workflow nodes."""

    def __init__(self, reducers: dict[str, Callable[[Any, Any], Any]] | None = None) -> None:
        self._nodes: dict[str, Node] = {}
        self._edges: dict[str, Edge] = {}
        self._entry: str | list[str] | None = None
        self.reducers: dict[str, Callable[[Any, Any], Any]] = dict(reducers or {})

    def add_node(self, name: str, fn: NodeFn, *, retries: int = 0, retry_delay: float = 0.0) -> StateGraph:
        if name in (START, END):
            raise GraphValidationError(f"'{name}' is a reserved node name")
        if name in self._nodes:
            raise DuplicateNodeError(f"node '{name}' already added")
        self._nodes[name] = Node(name=name, fn=fn, retries=retries, retry_delay=retry_delay)
        return self

    def set_entry_point(self, name: str | list[str]) -> StateGraph:
        """Set the starting node(s). Equivalent to ``add_edge(START, name)``."""
        targets = [name] if isinstance(name, str) else list(name)
        self._entry = name
        self._edges[START] = Edge(kind="parallel" if len(targets) > 1 else "static", targets=targets)
        return self

    def add_edge(self, source: str, target: str) -> StateGraph:
        if source in self._edges:
            raise GraphValidationError(f"node '{source}' already has outgoing edges defined")
        if source == START:
            return self.set_entry_point(target)
        self._edges[source] = Edge(kind="static", targets=[target])
        return self

    def add_conditional_edges(
        self,
        source: str,
        router: RouterFn,
        path_map: dict[Hashable, str],
    ) -> StateGraph:
        if source in self._edges:
            raise GraphValidationError(f"node '{source}' already has outgoing edges defined")
        self._edges[source] = Edge(kind="conditional", router=router, path_map=dict(path_map))
        return self

    def add_parallel_edges(self, source: str, targets: list[str]) -> StateGraph:
        if len(targets) < 2:
            raise GraphValidationError("add_parallel_edges requires at least 2 targets; use add_edge otherwise")
        if source in self._edges:
            raise GraphValidationError(f"node '{source}' already has outgoing edges defined")
        self._edges[source] = Edge(kind="parallel", targets=list(targets))
        return self

    def compile(self) -> CompiledGraph:
        if not self._nodes:
            raise GraphValidationError("graph has no nodes")
        if START not in self._edges:
            raise GraphValidationError("no entry point set; call set_entry_point() or add_edge(START, ...)")

        known = set(self._nodes) | {END}
        for source, edge in self._edges.items():
            if source != START and source not in self._nodes:
                raise UnknownNodeError(f"edge source '{source}' is not a registered node")
            targets = edge.targets or []
            if edge.kind == "conditional":
                targets = list(edge.path_map.values())  # type: ignore[union-attr]
            for target in targets:
                if target not in known:
                    raise UnknownNodeError(f"edge target '{target}' is not a registered node")

        self._check_static_cycles()
        return CompiledGraph(nodes=dict(self._nodes), edges=dict(self._edges), reducers=dict(self.reducers))

    def _check_static_cycles(self) -> None:
        """Detect cycles built entirely from unconditional/parallel edges.

        Conditional edges are excluded on purpose: a router-driven loop
        (e.g. retry until a critic approves) is a normal, terminating-at-
        runtime pattern and must not be rejected at compile time.
        """
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {name: WHITE for name in self._nodes}

        def neighbors(node: str) -> list[str]:
            edge = self._edges.get(node)
            if edge is None or edge.kind == "conditional":
                return []
            return [t for t in edge.targets if t != END]

        def visit(node: str, stack: list[str]) -> None:
            color[node] = GRAY
            for nxt in neighbors(node):
                if color.get(nxt, WHITE) == GRAY:
                    cycle = " -> ".join(stack + [nxt])
                    raise CycleDetectedError(f"unconditional cycle detected: {cycle}")
                if color.get(nxt, WHITE) == WHITE:
                    visit(nxt, stack + [nxt])
            color[node] = BLACK

        for name in self._nodes:
            if color[name] == WHITE:
                visit(name, [name])


@dataclass(frozen=True)
class CompiledGraph:
    """Immutable, validated graph ready for execution."""

    nodes: dict[str, Node]
    edges: dict[str, Edge]
    reducers: dict[str, Callable[[Any, Any], Any]]

    def entry_targets(self) -> list[str]:
        return list(self.edges[START].targets)

    def resolve_next(self, node_name: str, state: dict[str, Any]) -> list[str]:
        """Given the node that just ran, return the next node name(s)."""
        edge = self.edges.get(node_name)
        if edge is None:
            return [END]
        if edge.kind in ("static", "parallel"):
            return list(edge.targets)
        # conditional
        assert edge.router is not None and edge.path_map is not None
        key = edge.router(state)
        if key not in edge.path_map:
            raise UnknownNodeError(
                f"router for '{node_name}' returned {key!r}, which is not in its path_map {list(edge.path_map)}"
            )
        return [edge.path_map[key]]
