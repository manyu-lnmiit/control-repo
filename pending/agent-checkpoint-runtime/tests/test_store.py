
from agentflow.store import SQLiteStore


def make_store():
    return SQLiteStore(":memory:")


def test_ensure_run_creates_running_record():
    store = make_store()
    store.ensure_run("run-1", "wf")
    run = store.get_run("run-1")
    assert run is not None
    assert run.status == "running"
    assert run.workflow_name == "wf"


def test_ensure_run_is_idempotent():
    store = make_store()
    store.ensure_run("run-1", "wf")
    store.ensure_run("run-1", "wf")
    assert len(store.list_runs()) == 1


def test_ensure_run_resets_waiting_to_running():
    store = make_store()
    store.ensure_run("run-1", "wf")
    store.mark_run_waiting("run-1", "gate")
    assert store.get_run("run-1").status == "waiting"
    store.ensure_run("run-1", "wf")
    assert store.get_run("run-1").status == "running"


def test_step_lifecycle():
    store = make_store()
    store.ensure_run("run-1", "wf")
    assert store.get_step("run-1", "s1") is None

    store.mark_running("run-1", "s1", 0)
    step = store.get_step("run-1", "s1")
    assert step.status == "running"
    assert step.attempts == 0

    store.mark_completed("run-1", "s1", {"x": 1}, 0)
    step = store.get_step("run-1", "s1")
    assert step.status == "completed"
    assert step.result == {"x": 1}


def test_step_failure_then_recovery():
    store = make_store()
    store.ensure_run("run-1", "wf")
    store.mark_running("run-1", "s1", 0)
    store.mark_failed("run-1", "s1", "boom", 0)
    step = store.get_step("run-1", "s1")
    assert step.status == "failed"
    assert step.error == "boom"

    store.mark_running("run-1", "s1", 1)
    store.mark_completed("run-1", "s1", "ok", 1)
    step = store.get_step("run-1", "s1")
    assert step.status == "completed"
    assert step.attempts == 1


def test_run_completion_persists_result():
    store = make_store()
    store.ensure_run("run-1", "wf")
    store.mark_run_completed("run-1", {"done": True})
    run = store.get_run("run-1")
    assert run.status == "completed"
    assert run.result == {"done": True}


def test_gates_default_to_none_then_pending_then_approved():
    store = make_store()
    store.ensure_run("run-1", "wf")
    assert store.get_gate("run-1", "g1") is None

    store.request_gate("run-1", "g1")
    assert store.get_gate("run-1", "g1") == "pending"

    store.approve_gate("run-1", "g1", note="looks good")
    assert store.get_gate("run-1", "g1") == "approved"


def test_list_steps_ordered_by_update_time():
    store = make_store()
    store.ensure_run("run-1", "wf")
    store.mark_running("run-1", "a", 0)
    store.mark_completed("run-1", "a", 1, 0)
    store.mark_running("run-1", "b", 0)
    store.mark_completed("run-1", "b", 2, 0)
    names = [s.step_name for s in store.list_steps("run-1")]
    assert names == ["a", "b"]
