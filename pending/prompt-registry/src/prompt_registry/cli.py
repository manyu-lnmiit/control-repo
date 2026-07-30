"""Command-line interface for prompt-registry.

Implemented with argparse and the standard library only, so the CLI works
with zero third-party dependencies. Run ``prompt-registry --help`` after
installing, or ``python -m prompt_registry.cli --help``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from prompt_registry.store import (
    PromptNotFoundError,
    PromptRegistry,
    VersionNotFoundError,
)
from prompt_registry.template import MissingVariableError


def _load_body(args: argparse.Namespace) -> str:
    if args.file:
        return Path(args.file).read_text(encoding="utf-8")
    if args.body is not None:
        return args.body
    return sys.stdin.read()


def _parse_vars(pairs: list[str] | None) -> dict:
    result: dict = {}
    for pair in pairs or []:
        if "=" not in pair:
            raise SystemExit(f"Invalid --var {pair!r}, expected key=value")
        key, value = pair.split("=", 1)
        result[key] = value
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="prompt-registry", description=__doc__)
    parser.add_argument(
        "--db", default="prompt_registry.db", help="Path to the SQLite store"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    commit = sub.add_parser("commit", help="Commit a new prompt version")
    commit.add_argument("name")
    commit.add_argument("--file", help="Read the template body from a file")
    commit.add_argument("--body", help="Inline template body")
    commit.add_argument("-m", "--message", default="", help="Commit message")
    commit.add_argument("--tag", action="append", dest="tags", help="Tag(s) to apply")

    show = sub.add_parser("show", help="Show one version of a prompt")
    show.add_argument("name")
    show.add_argument("--version", type=int, default=None)
    show.add_argument("--tag", default=None)

    log = sub.add_parser("log", help="Show commit history for a prompt")
    log.add_argument("name")

    sub.add_parser("list", help="List all tracked prompt names")

    diff = sub.add_parser("diff", help="Diff two versions of a prompt")
    diff.add_argument("name")
    diff.add_argument("version_a", type=int)
    diff.add_argument("version_b", type=int)

    rollback = sub.add_parser("rollback", help="Roll back to a prior version")
    rollback.add_argument("name")
    rollback.add_argument("to_version", type=int)
    rollback.add_argument("-m", "--message", default=None)

    tag_cmd = sub.add_parser("tag", help="Apply a tag to a version")
    tag_cmd.add_argument("name")
    tag_cmd.add_argument("version", type=int)
    tag_cmd.add_argument("tag")

    render = sub.add_parser("render", help="Render a prompt with variables")
    render.add_argument("name")
    render.add_argument("--version", type=int, default=None)
    render.add_argument("--tag", default=None)
    render.add_argument(
        "--var", action="append", dest="vars", help="key=value, repeatable"
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    registry = PromptRegistry(args.db)

    try:
        if args.command == "commit":
            body = _load_body(args)
            pv = registry.commit(args.name, body, message=args.message, tags=args.tags)
            print(f"committed {pv.name}@v{pv.version}")
        elif args.command == "show":
            if args.tag:
                pv = registry.get_by_tag(args.name, args.tag)
            else:
                pv = registry.get(args.name, version=args.version)
            print(json.dumps(pv.as_dict(), indent=2))
        elif args.command == "log":
            for pv in registry.history(args.name):
                tag_str = f" [{', '.join(pv.tags)}]" if pv.tags else ""
                print(f"v{pv.version}{tag_str} - {pv.message} ({pv.created_at})")
        elif args.command == "list":
            for name in registry.list_names():
                print(name)
        elif args.command == "diff":
            print(registry.diff(args.name, args.version_a, args.version_b), end="")
        elif args.command == "rollback":
            pv = registry.rollback(args.name, args.to_version, message=args.message)
            print(f"rolled back {pv.name} -> new v{pv.version} (copy of v{args.to_version})")
        elif args.command == "tag":
            pv = registry.tag(args.name, args.version, args.tag)
            print(f"tagged {pv.name}@v{pv.version} as {args.tag!r}")
        elif args.command == "render":
            result = registry.render(
                args.name,
                variables=_parse_vars(args.vars),
                version=args.version,
                tag=args.tag,
            )
            print(result.text)
        else:  # pragma: no cover - argparse enforces valid subcommands
            parser.print_help()
            return 1
    except (PromptNotFoundError, VersionNotFoundError, MissingVariableError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    finally:
        registry.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
