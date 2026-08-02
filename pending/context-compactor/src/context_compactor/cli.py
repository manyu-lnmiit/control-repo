"""Command-line interface for context_compactor.

Usage:
    context-compactor compact transcript.jsonl --max-tokens 2000
    context-compactor stats transcript.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from context_compactor.compactor import Compactor, EvictionStrategy, TokenBudget
from context_compactor.models import Message
from context_compactor.tokenizer import get_default_tokenizer


def _load_messages(path: str) -> list[Message]:
    messages: list[Message] = []
    with open(path, encoding="utf-8") as f:
        for line_no, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            data: dict[str, Any] = json.loads(line)
            messages.append(
                Message(
                    role=data.get("role", "user"),
                    content=data.get("content", ""),
                    index=data.get("index", line_no),
                    pinned=data.get("pinned", False),
                    importance=data.get("importance"),
                    metadata=data.get("metadata", {}),
                )
            )
    return messages


def _write_messages(path: str, messages: list[Message]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for m in messages:
            f.write(
                json.dumps(
                    {
                        "role": m.role,
                        "content": m.content,
                        "index": m.index,
                        "pinned": m.pinned,
                        "metadata": m.metadata,
                    }
                )
                + "\n"
            )


def cmd_compact(args: argparse.Namespace) -> int:
    messages = _load_messages(args.input)
    budget = TokenBudget(max_tokens=args.max_tokens, reserve_tokens=args.reserve_tokens)
    strategy = EvictionStrategy.DROP if args.no_summarize else EvictionStrategy.SUMMARIZE
    compactor = Compactor(strategy=strategy)
    result = compactor.compact(messages, budget)

    if args.output:
        _write_messages(args.output, result.messages)
    else:
        for m in result.messages:
            sys.stdout.write(json.dumps({"role": m.role, "content": m.content}) + "\n")

    stats = result.stats
    print(
        f"input: {stats.input_messages} msgs / {stats.input_tokens} tokens  ->  "
        f"output: {stats.output_messages} msgs / {stats.output_tokens} tokens "
        f"({stats.compression_ratio:.0%} of original, {stats.tokens_saved} tokens saved, "
        f"{stats.summary_blocks_created} summary block(s), {stats.dropped_messages} dropped)",
        file=sys.stderr,
    )
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    messages = _load_messages(args.input)
    tokenizer = get_default_tokenizer()
    total = sum(tokenizer.count(m.content) for m in messages)
    by_role: dict[str, int] = {}
    for m in messages:
        by_role[m.role] = by_role.get(m.role, 0) + tokenizer.count(m.content)
    print(f"messages: {len(messages)}")
    print(f"total tokens (approx): {total}")
    for role, count in sorted(by_role.items(), key=lambda kv: -kv[1]):
        print(f"  {role}: {count} tokens")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="context-compactor",
        description="Fit LLM/agent transcripts into a token budget.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_compact = sub.add_parser("compact", help="Compact a transcript to fit a token budget")
    p_compact.add_argument("input", help="Path to a JSONL transcript file (one message per line)")
    p_compact.add_argument("--max-tokens", type=int, required=True, help="Total token budget")
    p_compact.add_argument(
        "--reserve-tokens", type=int, default=0, help="Tokens to reserve for the model's reply"
    )
    p_compact.add_argument("--output", help="Write compacted JSONL here instead of stdout")
    p_compact.add_argument(
        "--no-summarize",
        action="store_true",
        help="Drop excess messages instead of summarizing them",
    )
    p_compact.set_defaults(func=cmd_compact)

    p_stats = sub.add_parser("stats", help="Print token usage stats for a transcript")
    p_stats.add_argument("input", help="Path to a JSONL transcript file")
    p_stats.set_defaults(func=cmd_stats)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
