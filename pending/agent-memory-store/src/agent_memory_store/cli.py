"""Command-line interface for agent-memory-store.

Examples
--------
    agent-memory-store add "User prefers dark mode" --importance 0.7
    agent-memory-store search "ui preferences" -k 3
    agent-memory-store decay
    agent-memory-store consolidate
    agent-memory-store stats
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from .memory import MemoryType
from .store import MemoryStore

DEFAULT_DB_PATH = os.environ.get("AGENT_MEMORY_DB", "agent_memory.db")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-memory-store", description=__doc__)
    parser.add_argument(
        "--db",
        default=DEFAULT_DB_PATH,
        help=f"path to the SQLite database (default: {DEFAULT_DB_PATH}, or $AGENT_MEMORY_DB)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    add_p = sub.add_parser("add", help="store a new memory")
    add_p.add_argument("content")
    add_p.add_argument("--type", choices=[t.value for t in MemoryType], default="episodic")
    add_p.add_argument("--importance", type=float, default=0.5)
    add_p.add_argument("--tags", default="", help="comma-separated tags")

    search_p = sub.add_parser("search", help="retrieve memories relevant to a query")
    search_p.add_argument("query")
    search_p.add_argument("-k", type=int, default=5)
    search_p.add_argument("--type", choices=[t.value for t in MemoryType], default=None)

    list_p = sub.add_parser("list", help="list stored memories")
    list_p.add_argument("--type", choices=[t.value for t in MemoryType], default=None)
    list_p.add_argument("--include-archived", action="store_true")

    forget_p = sub.add_parser("forget", help="delete a memory by id")
    forget_p.add_argument("memory_id")

    sub.add_parser("decay", help="recompute importance decay for all memories")

    prune_p = sub.add_parser("prune", help="archive memories below an importance threshold")
    prune_p.add_argument("--threshold", type=float, default=0.05)

    consolidate_p = sub.add_parser(
        "consolidate", help="cluster and distill related episodic memories into semantic ones"
    )
    consolidate_p.add_argument("--similarity-threshold", type=float, default=0.75)
    consolidate_p.add_argument("--min-cluster-size", type=int, default=3)

    sub.add_parser("stats", help="show memory counts and average importance by type")

    serve_p = sub.add_parser(
        "serve", help="run the optional HTTP API (requires the [server] extra)"
    )
    serve_p.add_argument("--host", default="127.0.0.1")
    serve_p.add_argument("--port", type=int, default=8000)

    return parser


def _print_items(items) -> None:
    for item in items:
        print(
            f"[{item.memory_type.value:8s}] {item.id[:8]}  imp={item.importance:.2f}  {item.content}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "serve":
        try:
            import uvicorn

            from .server import build_app
        except ImportError:
            print(
                "The HTTP server requires extra dependencies. Install with:\n"
                "  pip install agent-memory-store[server]",
                file=sys.stderr,
            )
            return 1
        uvicorn.run(build_app(args.db), host=args.host, port=args.port)
        return 0

    with MemoryStore(db_path=args.db) as store:
        if args.command == "add":
            tags = [t.strip() for t in args.tags.split(",") if t.strip()]
            item = store.add(
                args.content, memory_type=args.type, importance=args.importance, tags=tags
            )
            print(item.id)
        elif args.command == "search":
            results = store.search(args.query, k=args.k, memory_type=args.type)
            for item, score in results:
                print(f"{score:.4f}  [{item.memory_type.value}]  {item.content}")
        elif args.command == "list":
            _print_items(store.list(memory_type=args.type, include_archived=args.include_archived))
        elif args.command == "forget":
            ok = store.forget(args.memory_id)
            print("deleted" if ok else "not found")
            return 0 if ok else 1
        elif args.command == "decay":
            updated = store.decay_all()
            print(f"updated {updated} memories")
        elif args.command == "prune":
            archived = store.prune(threshold=args.threshold)
            print(f"archived {archived} memories")
        elif args.command == "consolidate":
            created = store.consolidate(
                similarity_threshold=args.similarity_threshold,
                min_cluster_size=args.min_cluster_size,
            )
            print(f"created {len(created)} semantic memories")
            for item in created:
                print(f"  {item.id[:8]}  {item.content}")
        elif args.command == "stats":
            print(json.dumps(store.stats(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
