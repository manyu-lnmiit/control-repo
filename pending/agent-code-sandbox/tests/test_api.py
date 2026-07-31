from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from agent_code_sandbox.api import app  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("AGENT_SANDBOX_AUDIT_LOG_PATH", str(tmp_path / "audit.jsonl"))
    return TestClient(app)


def test_execute_python_endpoint(client: TestClient) -> None:
    resp = client.post(
        "/execute/python",
        json={"code": "print(2 + 2)", "timeout": 5, "memory_mb": 128, "cpu_seconds": 2},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "4" in data["stdout"]


def test_execute_shell_endpoint_allowed(client: TestClient) -> None:
    resp = client.post(
        "/execute/shell",
        json={"command": "echo api-hello", "timeout": 5, "memory_mb": 128, "cpu_seconds": 2},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "api-hello" in data["stdout"]


def test_execute_shell_endpoint_blocked(client: TestClient) -> None:
    resp = client.post(
        "/execute/shell",
        json={"command": "rm -rf /", "timeout": 5, "memory_mb": 128, "cpu_seconds": 2},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["policy_violation"] is True
    assert data["success"] is False


def test_audit_endpoint_returns_recorded_entries(client: TestClient) -> None:
    client.post(
        "/execute/python",
        json={"code": "print(1)", "timeout": 5, "memory_mb": 128, "cpu_seconds": 2},
    )
    resp = client.get("/audit?last=5")
    assert resp.status_code == 200
    entries = resp.json()
    assert len(entries) >= 1
    assert "payload_sha256" in entries[0]
