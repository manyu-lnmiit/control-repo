"""Command-line interface for injection_radar.

Usage:
    injection-radar scan somefile.txt
    cat doc.txt | injection-radar scan -
    injection-radar scan doc.txt --json
    injection-radar scan doc.txt --threshold high   # nonzero exit if risk >= HIGH
    injection-radar sanitize doc.txt --mode redact
"""

from __future__ import annotations

import argparse
import json
import sys

from .models import RiskLevel
from .sanitizer import sanitize
from .scanner import default_scanner


def _read_input(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _cmd_scan(args: argparse.Namespace) -> int:
    text = _read_input(args.path)
    scanner = default_scanner()
    result = scanner.scan(text)

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(f"risk_level: {result.risk_level.name}  score: {result.score}")
        if result.findings:
            print(f"{len(result.findings)} finding(s):")
            for f in result.top_findings(n=args.max_findings):
                snippet = f.matched_text.replace("\n", "\\n")
                if len(snippet) > 60:
                    snippet = snippet[:57] + "..."
                print(f"  [{f.severity:5.1f}] {f.category:28s} {f.detector:22s} {snippet!r}")
        else:
            print("no findings")

    threshold = RiskLevel[args.threshold.upper()] if args.threshold else None
    if threshold is not None and result.risk_level >= threshold:
        return 1
    return 0


def _cmd_sanitize(args: argparse.Namespace) -> int:
    text = _read_input(args.path)
    scanner = default_scanner()
    result = scanner.scan(text)
    cleaned = sanitize(result, mode=args.mode)
    sys.stdout.write(cleaned)
    if not cleaned.endswith("\n"):
        sys.stdout.write("\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="injection-radar", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    scan_p = sub.add_parser("scan", help="Scan a file (or '-' for stdin) and report findings.")
    scan_p.add_argument("path", help="Path to a text file, or '-' to read stdin.")
    scan_p.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    scan_p.add_argument(
        "--threshold",
        choices=[lvl.name.lower() for lvl in RiskLevel],
        default=None,
        help="Exit with status 1 if risk_level is at or above this threshold (useful in CI).",
    )
    scan_p.add_argument("--max-findings", type=int, default=10, help="Max findings to print in text mode.")
    scan_p.set_defaults(func=_cmd_scan)

    san_p = sub.add_parser("sanitize", help="Print a sanitized version of a file.")
    san_p.add_argument("path", help="Path to a text file, or '-' to read stdin.")
    san_p.add_argument("--mode", choices=["redact", "quarantine", "none"], default="redact")
    san_p.set_defaults(func=_cmd_sanitize)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
