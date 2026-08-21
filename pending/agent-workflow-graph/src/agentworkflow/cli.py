"""Command-line interface for agent-workflow-graph.

    agentworkflow run --graph examples.research_workflow:build_graph --input '{"topic": "rust vs go"}'
    agentworkflow visualize --graph examples.research_workflow:build_graph
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from typing import Any

from .executor import Executor
from .graph import CompiledGraph, StateGraph
from .visualize import to_mermaid


def _load_graph(spec: str) -> CompiledGraph:
    if ":" not in spec:
        raise SystemExit(f"--graph must be 'module.path:factory_function', got {spec!r}")
    module_name, factory_name = spec.split(":", 1)
    module = importlib.import_module(module_name)
    factory = getattr(module, factory_name)
    built = factory()
    if isinstance(built, StateGraph):
        return built.compile()
    if isinstance(built, CompiledGraph):
        return built
    raise SystemExit(f"{spec} did not return a StateGraph or CompiledGraph (got {type(built)!r})")


def _cmd_run(args: argparse.Namespace) -> int:
    graph = _load_graph(args.graph)
    initial_state: dict[str, Any] = json.loads(args.input) if args.input else {}
    executor = Executor(graph, max_steps=args.max_steps)
    result = executor.run(initial_state)

    if args.trace:
        for t in result.trace:
            status = "ok" if t.error is None else f"ERROR: {t.error}"
            msg = f"[step {t.step}] {t.node} ({t.duration_ms:.1f}ms, attempts={t.attempts}) -> {status}"
            print(msg, file=sys.stderr)

    print(json.dumps(result.final_state, indent=2, default=str))
    return 0


def _cmd_visualize(args: argparse.Namespace) -> int:
    graph = _load_graph(args.graph)
    print(to_mermaid(graph))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agentworkflow", description="Run and inspect agent-workflow-graph graphs.")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Execute a compiled graph and print the final state as JSON.")
    run_p.add_argument("--graph", required=True, help="module.path:factory_function returning a StateGraph")
    run_p.add_argument("--input", default=None, help="JSON object used as the initial state")
    run_p.add_argument("--max-steps", type=int, default=100, dest="max_steps")
    run_p.add_argument("--trace", action="store_true", help="Print per-node execution trace to stderr")
    run_p.set_defaults(func=_cmd_run)

    viz_p = sub.add_parser("visualize", help="Print a Mermaid flowchart of the graph.")
    viz_p.add_argument("--graph", required=True, help="module.path:factory_function returning a StateGraph")
    viz_p.set_defaults(func=_cmd_visualize)

    return parser


def main(argv: Any = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
