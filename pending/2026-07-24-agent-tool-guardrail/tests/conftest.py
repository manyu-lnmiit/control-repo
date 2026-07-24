import pytest

from agent_guardrail.policy import Policy

EXAMPLE_POLICY_YAML = """
default_allowed: false
tools:
  search_web:
    allowed: true
    max_calls_per_minute: 3
    max_cost_per_call: 0.01
    redact_output: true
    args_schema:
      type: object
      properties:
        query:
          type: string
          minLength: 1
      required: ["query"]
      additionalProperties: false
  read_file:
    allowed: true
    max_cost_per_call: 0.0
  send_email:
    allowed: false
"""


@pytest.fixture
def policy() -> Policy:
    return Policy.from_yaml_string(EXAMPLE_POLICY_YAML)


@pytest.fixture
def trace_path(tmp_path):
    return str(tmp_path / "trace.jsonl")
