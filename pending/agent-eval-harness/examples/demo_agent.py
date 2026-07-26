"""Example custom agent wired to the quickstart suite in ``tasks.yaml``.

Run it with:

    agent-eval run --suite examples/tasks.yaml --agent examples.demo_agent:make_agent
"""

from __future__ import annotations

from agent_eval_harness.mock_agent import MockAgent

_CANNED_RESPONSES = {
    "Say hello": "Say hello",
    "Name a primary color": "I would pick blue.",
    "2024-01-01": "2024-01-01",
    "42": "approximately 42.0",
}


def make_agent() -> MockAgent:
    """Factory used by the CLI's ``--agent module:factory`` resolution mechanism."""
    return MockAgent(responses=_CANNED_RESPONSES, default="I don't know")
