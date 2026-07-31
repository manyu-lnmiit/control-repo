from __future__ import annotations

from agent_code_sandbox.core.result import ExecutionResult


def test_success_true_for_clean_run() -> None:
    result = ExecutionResult(exit_code=0)
    assert result.success is True


def test_success_false_on_nonzero_exit() -> None:
    result = ExecutionResult(exit_code=1)
    assert result.success is False


def test_success_false_when_timed_out() -> None:
    result = ExecutionResult(exit_code=0, timed_out=True)
    assert result.success is False


def test_success_false_when_memory_exceeded() -> None:
    result = ExecutionResult(exit_code=0, memory_exceeded=True)
    assert result.success is False


def test_success_false_on_policy_violation() -> None:
    result = ExecutionResult(exit_code=-1, policy_violation=True)
    assert result.success is False


def test_to_dict_contains_all_fields() -> None:
    result = ExecutionResult(stdout="hi", stderr="", exit_code=0)
    d = result.to_dict()
    for key in (
        "stdout",
        "stderr",
        "exit_code",
        "timed_out",
        "memory_exceeded",
        "duration_seconds",
        "killed_reason",
        "policy_violation",
        "network_isolation",
        "success",
    ):
        assert key in d
