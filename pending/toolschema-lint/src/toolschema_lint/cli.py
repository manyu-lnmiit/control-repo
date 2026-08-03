"""Command-line interface for toolschema-lint.

Usage::

    toolschema-lint validate schemas.json
    toolschema-lint validate schemas.json --format openai --output sarif
    toolschema-lint validate schemas.json --config .toolschemalintrc.json
    toolschema-lint rules
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from toolschema_lint.config import Config
from toolschema_lint.linter import Linter
from toolschema_lint.parsers import SUPPORTED_FORMATS, detect_format, parse
from toolschema_lint.report import FORMATTERS
from toolschema_lint.rules import DEFAULT_RULES


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="toolschema-lint",
        description="Static analysis for LLM tool/function-calling schemas.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser(
        "validate", help="Lint a tool-schema JSON file and report findings."
    )
    validate.add_argument("path", help="Path to a JSON file containing tool definitions.")
    validate.add_argument(
        "--format",
        choices=SUPPORTED_FORMATS,
        default=None,
        help="Schema format. Auto-detected if omitted.",
    )
    validate.add_argument(
        "--output",
        choices=list(FORMATTERS.keys()),
        default="text",
        help="Output format (default: text).",
    )
    validate.add_argument(
        "--config",
        default=None,
        help="Path to a .toolschemalintrc.json config file. "
        "If omitted, looks for one next to the input file's directory.",
    )
    validate.add_argument(
        "--fail-on",
        choices=["error", "warning", "info", "never"],
        default="error",
        help="Minimum severity that causes a non-zero exit code (default: error).",
    )

    subparsers.add_parser("rules", help="List all built-in rules and their default severity.")

    return parser


def _load_document(path: str) -> object:
    text = Path(path).read_text()
    return json.loads(text)


def _resolve_config(args: argparse.Namespace, input_path: str) -> Config:
    if args.config:
        return Config.load(args.config)
    return Config.find_and_load(Path(input_path).parent)


def cmd_validate(args: argparse.Namespace) -> int:
    try:
        document = _load_document(args.path)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Error reading {args.path}: {exc}", file=sys.stderr)
        return 2

    fmt = args.format
    if fmt is None:
        try:
            fmt = detect_format(document)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2

    tools = parse(document, fmt)
    if not tools:
        print(f"No tool definitions found in {args.path} (format: {fmt}).", file=sys.stderr)
        return 2

    config = _resolve_config(args, args.path)
    linter = Linter(config=config)
    result = linter.lint(tools)

    formatter = FORMATTERS[args.output]
    print(formatter(result))

    if args.fail_on == "never":
        return 0
    thresholds = {"error": 2, "warning": 1, "info": 0}
    min_rank = thresholds[args.fail_on]
    if any(f.severity.rank >= min_rank for f in result.findings):
        return 1
    return 0


def cmd_rules(_args: argparse.Namespace) -> int:
    for rule in DEFAULT_RULES:
        severity = getattr(rule, "default_severity", None)
        severity_label = severity.value if severity else "n/a"
        print(f"{rule.id:32} [{severity_label:7}] {rule.description}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "validate":
        return cmd_validate(args)
    if args.command == "rules":
        return cmd_rules(args)

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
