from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from agent_trace_lens.api import create_app
from agent_trace_lens.tracer import Tracer


@pytest.fixture()
def client_and_tracer(db_path):
    app = create_app(db_path=db_path)
    tracer = Tracer(storage=app.state.storage)
    return TestClient(app), tracer


def test_health_endpoint(client_and_tracer):
    client, _ = client_and_tracer
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_list_traces_empty(client_and_tracer):
    client, _ = client_and_tracer
    resp = client.get("/traces")
    assert resp.status_code == 200
    assert resp.json() == []


def test_full_flow_trace_then_query(client_and_tracer):
    client, tracer = client_and_tracer

    with tracer.trace("api-run") as t:
        trace_id = t.trace_id
        with tracer.span("tool_call", kind="tool"):
            pass

    resp = client.get("/traces")
    assert resp.status_code == 200
    traces = resp.json()
    assert len(traces) == 1
    assert traces[0]["trace_id"] == trace_id
    assert traces[0]["span_count"] == 2

    resp = client.get(f"/traces/{trace_id}")
    assert resp.status_code == 200
    spans = resp.json()
    assert len(spans) == 2
    names = {s["name"] for s in spans}
    assert names == {"api-run", "tool_call"}


def test_get_missing_trace_returns_404(client_and_tracer):
    client, _ = client_and_tracer
    resp = client.get("/traces/does-not-exist")
    assert resp.status_code == 404


def test_timeline_html_renders_spans(client_and_tracer):
    client, tracer = client_and_tracer

    with tracer.trace("viz-run") as t:
        trace_id = t.trace_id
        with tracer.span("step_one", kind="tool"):
            pass

    resp = client.get(f"/traces/{trace_id}/timeline")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "viz-run" in resp.text
    assert "step_one" in resp.text


def test_delete_trace_endpoint_removes_spans(client_and_tracer):
    client, tracer = client_and_tracer

    with tracer.trace("to-delete") as t:
        trace_id = t.trace_id

    resp = client.delete(f"/traces/{trace_id}")
    assert resp.status_code == 200

    resp = client.get(f"/traces/{trace_id}")
    assert resp.status_code == 404
