
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text(
        """
default_allowed: false
tools:
  search_web:
    allowed: true
    max_calls_per_minute: 5
    max_cost_per_call: 0.01
    args_schema:
      type: object
      properties:
        query: {type: string, minLength: 1}
      required: [query]
"""
    )
    trace_path = tmp_path / "trace.jsonl"
    monkeypatch.setenv("GUARDRAIL_POLICY_PATH", str(policy_path))
    monkeypatch.setenv("GUARDRAIL_TRACE_PATH", str(trace_path))

    # import after env vars are set so module-level path reads pick them up
    from agent_guardrail.service import app as app_module

    monkeypatch.setattr(app_module, "POLICY_PATH", str(policy_path))
    monkeypatch.setattr(app_module, "TRACE_PATH", str(trace_path))

    return TestClient(app_module.app)


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_evaluate_allowed(client):
    resp = client.post("/evaluate", json={"tool_name": "search_web", "arguments": {"query": "hi"}})
    assert resp.status_code == 200
    body = resp.json()
    assert body["allowed"] is True
    assert body["tool_name"] == "search_web"


def test_evaluate_denied_unknown_tool(client):
    resp = client.post("/evaluate", json={"tool_name": "execute_shell", "arguments": {}})
    assert resp.status_code == 200
    body = resp.json()
    assert body["allowed"] is False
    assert "not allowed" in body["reason"]


def test_evaluate_denied_bad_args(client):
    resp = client.post("/evaluate", json={"tool_name": "search_web", "arguments": {"query": ""}})
    body = resp.json()
    assert body["allowed"] is False


def test_record_and_get_trace(client):
    resp = client.post(
        "/record",
        json={
            "tool_name": "search_web",
            "arguments": {"query": "hi"},
            "decision": "allowed",
            "output": "some result",
            "session_id": "sess-1",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["recorded"] is True

    trace_resp = client.get("/trace/sess-1")
    assert trace_resp.status_code == 200
    events = trace_resp.json()
    assert len(events) == 1
    assert events[0]["tool_name"] == "search_web"


def test_get_trace_missing_returns_404(client):
    resp = client.get("/trace/nonexistent-session")
    assert resp.status_code == 404
