from fastapi.testclient import TestClient

from llm_gateway.config import DEFAULT_CONFIG_YAML, GatewayConfig
from llm_gateway.server import create_app


def make_client():
    cfg = GatewayConfig.from_yaml_string(DEFAULT_CONFIG_YAML)
    app = create_app(gateway=cfg.build_gateway())
    return TestClient(app)


def test_healthz():
    client = make_client()
    resp = client.get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "primary" in body["providers"]


def test_chat_completions_returns_openai_shape():
    client = make_client()
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi there"}]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["object"] == "chat.completion"
    assert body["choices"][0]["message"]["role"] == "assistant"
    assert body["usage"]["total_tokens"] > 0


def test_stats_endpoint_reflects_usage():
    client = make_client()
    client.post(
        "/v1/chat/completions",
        json={"model": "m", "messages": [{"role": "user", "content": "hi"}]},
    )
    resp = client.get("/v1/stats")
    assert resp.status_code == 200
    assert resp.json()["by_key"]["default"]["requests"] == 1


def test_rate_limit_returns_429():
    cfg = GatewayConfig.from_yaml_string(
        "rate_limit:\n  requests_per_minute: 60\n  burst: 1\n"
        "providers:\n  - name: primary\n    type: mock\n"
    )
    app = create_app(gateway=cfg.build_gateway())
    client = TestClient(app)
    payload = {"model": "m", "messages": [{"role": "user", "content": "hi"}]}
    assert client.post("/v1/chat/completions", json=payload).status_code == 200
    assert client.post("/v1/chat/completions", json=payload).status_code == 429


def test_authorization_header_used_as_api_key_id():
    client = make_client()
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "m", "messages": [{"role": "user", "content": "hi"}]},
        headers={"Authorization": "Bearer tenant-42"},
    )
    assert resp.status_code == 200
    stats = client.get("/v1/stats").json()
    assert "tenant-42" in stats["by_key"]
