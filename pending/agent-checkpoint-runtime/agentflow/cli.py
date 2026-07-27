"""Command-line interface for inspecting and controlling agentflow runs.

    agentflow list [--db PATH]
    agentflow status <run_id> [--db PATH]
    agentflow history <run_id> [--db PATH]
    agentflow approve <run_id> <gate_name> [--note NOTE] [--db PATH]
"""

from __future__ import annotations

import argparse
import json
import sys

from .store import SQLiteStore


def _print_run(run) -> None:
    print(f"run_id        : {run.run_id}")
    print(f"workflow      : {run.workflow_name}")
    print(f"status        : {run.status}")
    if run.waiting_gate:
        print(f"waiting_gate  : {run.waiting_gate}")
    if run.error:
        print(f"error         : {run.error}")
    if run.result is not None:
        print(f"result        : {json.dumps(run.result)}")
    print(f"created_at    : {run.created_at}")
    print(f"updated_at    : {run.updated_at}")


def cmd_list(args: argparse.Namespace) -> int:
    store = SQLiteStore(args.db)
    runs = store.list_runs()
    if not runs:
        print("no runs found")
        return 0
    for run in runs:
        gate = f" gate={run.waiting_gate}" if run.waiting_gate else ""
        print(f"{run.run_id:<24} {run.workflow_name:<24} {run.status:<10}{gate}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    store = SQLiteStore(args.db)
    run = store.get_run(args.run_id)
    if run is None:
        print(f"no such run: {args.run_id}", file=sys.stderr)
        return 1
    _print_run(run)
    return 0


def cmd_history(args: argparse.Namespace) -> int:
    store = SQLiteStore(args.db)
    run = store.get_run(args.run_id)
    if run is None:
        print(f"no such run: {args.run_id}", file=sys.stderr)
        return 1
    steps = store.list_steps(args.run_id)
    if not steps:
        print("no steps recorded yet")
        return 0
    for s in steps:
        print(
            f"{s.step_name:<24} status={s.status:<10} attempts={s.attempts:<3} "
            f"error={s.error or '-'}"
        )
    return 0


def cmd_approve(args: argparse.Namespace) -> int:
    store = SQLiteStore(args.db)
    run = store.get_run(args.run_id)
    if run is None:
        print(f"no such run: {args.run_id}", file=sys.stderr)
        return 1
    store.approve_gate(args.run_id, args.gate_name, note=args.note or "")
    print(f"approved gate {args.gate_name!r} for run {args.run_id!r}")
    print("re-run the workflow's entrypoint with the same run_id to resume.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentflow",
        description="Inspect and control durable agentflow workflow runs.",
    )
    parser.add_argument(
        "--db", default="agentflow.db", help="path to the SQLite store (default: agentflow.db)"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="list all known workflow runs")
    p_list.set_defaults(func=cmd_list)

    p_status = sub.add_parser("status", help="show a single run's status")
    p_status.add_argument("run_id")
    p_status.set_defaults(func=cmd_status)

    p_history = sub.add_parser("history", help="show a run's step-by-step history")
    p_history.add_argument("run_id")
    p_history.set_defaults(func=cmd_history)

    p_approve = sub.add_parser("approve", help="approve a pending human-in-the-loop gate")
    p_approve.add_argument("run_id")
    p_approve.add_argument("gate_name")
    p_approve.add_argument("--note", default=None)
    p_approve.set_defaults(func=cmd_approve)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
