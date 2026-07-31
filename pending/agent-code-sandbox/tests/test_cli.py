from __future__ import annotations

import contextlib
import io

from agent_code_sandbox.cli import main


def _run_cli(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        exit_code = main(argv)
    return exit_code, out.getvalue(), err.getvalue()


def test_run_python_end_to_end(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AGENT_SANDBOX_AUDIT_LOG_PATH", str(tmp_path / "audit.jsonl"))
    exit_code, out, err = _run_cli(["run-python", "print(6 * 7)"])
    assert exit_code == 0
    assert "42" in out
    assert "[OK]" in out


def test_run_python_from_file(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AGENT_SANDBOX_AUDIT_LOG_PATH", str(tmp_path / "audit.jsonl"))
    script = tmp_path / "snippet.py"
    script.write_text("print('from file')\n")
    exit_code, out, err = _run_cli(["run-python", "--file", str(script)])
    assert exit_code == 0
    assert "from file" in out


def test_run_shell_allowed(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AGENT_SANDBOX_AUDIT_LOG_PATH", str(tmp_path / "audit.jsonl"))
    exit_code, out, err = _run_cli(["run-shell", "echo cli-hello"])
    assert exit_code == 0
    assert "cli-hello" in out


def test_run_shell_blocked(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AGENT_SANDBOX_AUDIT_LOG_PATH", str(tmp_path / "audit.jsonl"))
    exit_code, out, err = _run_cli(["run-shell", "sudo rm -rf /"])
    assert exit_code == 1
    assert "[FAILED]" in out
    assert "not in the allowlist" in err


def test_audit_command_lists_entries(tmp_path, monkeypatch) -> None:
    log_path = tmp_path / "audit.jsonl"
    monkeypatch.setenv("AGENT_SANDBOX_AUDIT_LOG_PATH", str(log_path))
    _run_cli(["run-python", "print('a')"])
    _run_cli(["run-shell", "echo b"])

    exit_code, out, err = _run_cli(["audit", "--last", "5"])
    assert exit_code == 0
    lines = [line for line in out.splitlines() if line.strip()]
    assert len(lines) == 2


def test_audit_command_empty_log(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv(
        "AGENT_SANDBOX_AUDIT_LOG_PATH", str(tmp_path / "nonexistent.jsonl")
    )
    exit_code, out, err = _run_cli(["audit"])
    assert exit_code == 0
    assert "No audit entries" in out


def test_cli_timeout_flag_forwarded(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AGENT_SANDBOX_AUDIT_LOG_PATH", str(tmp_path / "audit.jsonl"))
    exit_code, out, err = _run_cli(
        [
            "run-python",
            "while True: pass",
            "--timeout",
            "1",
            "--cpu-seconds",
            "1",
        ]
    )
    assert exit_code == 1
    assert "[FAILED]" in out
