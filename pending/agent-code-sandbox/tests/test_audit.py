from __future__ import annotations

from agent_code_sandbox.audit import AuditLog, hash_payload
from agent_code_sandbox.core.limits import ResourceLimits
from agent_code_sandbox.core.result import ExecutionResult


def test_hash_payload_is_deterministic_sha256() -> None:
    h1 = hash_payload("print(1)")
    h2 = hash_payload("print(1)")
    h3 = hash_payload("print(2)")
    assert h1 == h2
    assert h1 != h3
    assert len(h1) == 64  # sha256 hex digest length


def test_record_and_read_all(audit_log: AuditLog) -> None:
    limits = ResourceLimits()
    result = ExecutionResult(stdout="ok", exit_code=0)
    entry = audit_log.record("python", "print('hi')", limits, result)

    assert entry.kind == "python"
    assert entry.payload_sha256 == hash_payload("print('hi')")

    all_entries = audit_log.read_all()
    assert len(all_entries) == 1
    assert all_entries[0].payload_sha256 == entry.payload_sha256


def test_code_is_not_stored_verbatim(audit_log: AuditLog) -> None:
    limits = ResourceLimits()
    result = ExecutionResult(exit_code=0)
    secret_code = "print('this should not appear verbatim in the log')"
    audit_log.record("python", secret_code, limits, result)

    raw = audit_log.path.read_text()
    assert secret_code not in raw
    assert hash_payload(secret_code) in raw


def test_last_n_returns_most_recent(audit_log: AuditLog) -> None:
    limits = ResourceLimits()
    for i in range(5):
        audit_log.record(
            "shell", f"echo {i}", limits, ExecutionResult(exit_code=0)
        )
    last_two = audit_log.last(2)
    assert len(last_two) == 2
    assert last_two[-1].payload_sha256 == hash_payload("echo 4")


def test_last_filters_by_success(audit_log: AuditLog) -> None:
    limits = ResourceLimits()
    audit_log.record("shell", "echo ok", limits, ExecutionResult(exit_code=0))
    audit_log.record(
        "shell",
        "bad cmd",
        limits,
        ExecutionResult(exit_code=-1, policy_violation=True),
    )

    successes = audit_log.last(10, success=True)
    failures = audit_log.last(10, success=False)
    assert len(successes) == 1
    assert len(failures) == 1
    assert successes[0].payload_sha256 == hash_payload("echo ok")


def test_read_all_on_missing_file_returns_empty(tmp_path) -> None:
    log = AuditLog(path=tmp_path / "does-not-exist.jsonl")
    assert log.read_all() == []


def test_default_audit_log_path_env_override(monkeypatch, tmp_path) -> None:
    custom_path = tmp_path / "custom-audit.jsonl"
    monkeypatch.setenv("AGENT_SANDBOX_AUDIT_LOG_PATH", str(custom_path))
    from agent_code_sandbox.audit import default_audit_log_path

    assert default_audit_log_path() == custom_path
