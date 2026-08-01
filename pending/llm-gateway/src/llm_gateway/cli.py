"""Command-line interface for llm-gateway."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from llm_gateway.config import DEFAULT_CONFIG_YAML, GatewayConfig
from llm_gateway.models import ChatMessage, ChatRequest, Role


def _load_gateway(config_path: str | None):
    cfg = (
        GatewayConfig.from_yaml(config_path)
        if config_path
        else GatewayConfig.from_yaml_string(DEFAULT_CONFIG_YAML)
    )
    return cfg.build_gateway()


def _cmd_chat(args: argparse.Namespace) -> int:
    gateway = _load_gateway(args.config)
    request = ChatRequest(
        model=args.model,
        messages=[ChatMessage(role=Role.USER, content=args.prompt)],
        api_key_id=args.api_key_id,
        task_hint=args.task_hint,
    )
    response = asyncio.run(gateway.chat(request))
    print(json.dumps(response.to_openai_dict(), indent=2))
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    try:
        cfg = GatewayConfig.from_yaml(args.config)
        cfg.build_gateway()
    except Exception as exc:  # noqa: BLE001 - CLI boundary reports any failure
        print(f"invalid config: {exc}", file=sys.stderr)
        return 1
    print("config is valid")
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    import os

    import uvicorn

    if args.config:
        os.environ["LLM_GATEWAY_CONFIG"] = args.config
    uvicorn.run("llm_gateway.server:app", host=args.host, port=args.port, reload=False)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="llm-gateway", description="Unified multi-provider LLM gateway")
    sub = parser.add_subparsers(dest="command", required=True)

    chat_p = sub.add_parser("chat", help="send a single chat completion through the gateway")
    chat_p.add_argument("prompt", help="the user message to send")
    chat_p.add_argument("--model", default="mock-small", help="model name (used for routing)")
    chat_p.add_argument("--config", default=None, help="path to a gateway YAML config")
    chat_p.add_argument("--api-key-id", default="default", help="caller identity for rate/cost tracking")
    chat_p.add_argument("--task-hint", default=None, help="optional routing hint, e.g. 'code'")
    chat_p.set_defaults(func=_cmd_chat)

    validate_p = sub.add_parser("validate", help="validate a gateway YAML config")
    validate_p.add_argument("config", help="path to a gateway YAML config")
    validate_p.set_defaults(func=_cmd_validate)

    serve_p = sub.add_parser("serve", help="run the HTTP gateway server")
    serve_p.add_argument("--config", default=None, help="path to a gateway YAML config")
    serve_p.add_argument("--host", default="0.0.0.0")
    serve_p.add_argument("--port", type=int, default=8000)
    serve_p.set_defaults(func=_cmd_serve)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
