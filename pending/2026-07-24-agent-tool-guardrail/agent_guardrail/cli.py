"""Command-line interface for agent_guardrail.

Examples
--------
    agent-guardrail check-policy policies/example_policy.yaml \\
        --tool search_web --args '{"query": "hello"}'

    agent-guardrail show-trace traces/session.jsonl

    agent-guardrail replay traces/session.jsonl
"""

from __future__ import annotations

import json
import sys

import click

from agent_guardrail.exceptions import GuardrailError
from agent_guardrail.policy import Policy, PolicyEngine
from agent_guardrail.replay import ReplayEngine
from agent_guardrail.tracing import TraceRecorder


@click.group()
@click.version_option(package_name="agent-guardrail")
def main():
    """agent-guardrail: policy, budget and replay tooling for LLM agent tool calls."""


@main.command("check-policy")
@click.argument("policy_path", type=click.Path(exists=True))
@click.option("--tool", "tool_name", required=True, help="Tool name to evaluate.")
@click.option("--args", "args_json", default="{}", help="JSON object of arguments.")
def check_policy(policy_path: str, tool_name: str, args_json: str):
    """Evaluate a single tool call against a policy file and print the decision."""
    policy = Policy.from_yaml(policy_path)
    engine = PolicyEngine(policy)
    arguments = json.loads(args_json)
    try:
        rule = engine.check(tool_name, arguments)
    except GuardrailError as exc:
        click.echo(f"DENIED: {exc}", err=True)
        sys.exit(1)
    click.echo(f"ALLOWED: tool='{tool_name}' rate_limit={rule.max_calls_per_minute} "
               f"max_cost={rule.max_cost_per_call} redact_output={rule.redact_output}")


@main.command("show-trace")
@click.argument("trace_path", type=click.Path(exists=True))
def show_trace(trace_path: str):
    """Pretty-print every event in a JSONL trace file."""
    events = TraceRecorder.load(trace_path)
    for event in events:
        click.echo(
            f"[{event.call_id:>4}] {event.decision.upper():<7} "
            f"{event.tool_name}({json.dumps(event.arguments)}) "
            f"cost={event.cost} duration_ms={event.duration_ms:.2f}"
        )
    click.echo(f"\n{len(events)} events total.")


@main.command("replay")
@click.argument("trace_path", type=click.Path(exists=True))
def replay(trace_path: str):
    """Step through a recorded trace and print each recorded output."""
    engine = ReplayEngine(trace_path)
    while engine.has_next():
        event = engine.events[engine._cursor]  # noqa: SLF001 - CLI convenience
        try:
            output = engine.next_output(event.tool_name)
        except GuardrailError as exc:
            click.echo(f"REPLAY ERROR: {exc}", err=True)
            sys.exit(1)
        click.echo(f"{event.tool_name} -> {json.dumps(output)}")
    click.echo(f"\nReplayed {len(engine)} events from {trace_path}.")


if __name__ == "__main__":
    main()
