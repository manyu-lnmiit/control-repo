import pytest

from agent_guardrail.exceptions import PolicyViolation
from agent_guardrail.policy import Policy, PolicyEngine


def test_allowed_tool_passes(policy):
    engine = PolicyEngine(policy)
    rule = engine.check("search_web", {"query": "hi"})
    assert rule.name == "search_web"
    assert rule.max_calls_per_minute == 3


def test_denied_tool_raises(policy):
    engine = PolicyEngine(policy)
    with pytest.raises(PolicyViolation):
        engine.check("send_email", {"to": "a@b.com"})


def test_unknown_tool_denied_by_default(policy):
    engine = PolicyEngine(policy)
    with pytest.raises(PolicyViolation):
        engine.check("execute_shell", {"cmd": "rm -rf /"})


def test_default_allowed_true():
    policy = Policy.from_dict({"default_allowed": True, "tools": {}})
    engine = PolicyEngine(policy)
    rule = engine.check("anything", {})
    assert rule.allowed is True


def test_schema_validation_rejects_bad_args(policy):
    engine = PolicyEngine(policy)
    with pytest.raises(PolicyViolation):
        engine.check("search_web", {"query": ""})


def test_schema_validation_rejects_extra_fields(policy):
    engine = PolicyEngine(policy)
    with pytest.raises(PolicyViolation):
        engine.check("search_web", {"query": "ok", "extra": "nope"})


def test_from_yaml_file(tmp_path):
    p = tmp_path / "policy.yaml"
    p.write_text(
        """
default_allowed: false
tools:
  ping:
    allowed: true
"""
    )
    policy = Policy.from_yaml(str(p))
    engine = PolicyEngine(policy)
    rule = engine.check("ping", {})
    assert rule.allowed is True
