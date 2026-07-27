import pytest

from agentflow import ApprovalPending, SQLiteStore, StepFailed, Workflow, WorkflowFailed


def make_workflow(run_id="run-1"):
    store = SQLiteStore(":memory:")
    return Workflow(name="wf", run_id=run_id, store=store), store


def test_step_executes_once_and_returns_result():
    wf, _ = make_workflow()
    calls = []

    @wf.step("s1")
    def s1(ctx):
        calls.append(1)
        return 42

    result = wf.run(lambda w: s1(w))
    assert result == 42
    assert calls == [1]


def test_step_is_memoized_across_workflow_instances_sharing_a_store():
    store = SQLiteStore(":memory:")
    wf1 = Workflow(name="wf", run_id="run-1", store=store)
    calls = []

    @wf1.step("s1")
    def s1(ctx):
        calls.append(1)
        return "cached-value"

    assert wf1.run(lambda w: s1(w)) == "cached-value"
    assert calls == [1]

    # A brand new Workflow object bound to the SAME run_id and store should
    # skip re-executing the already-completed step.
    wf2 = Workflow(name="wf", run_id="run-1", store=store)

    @wf2.step("s1")
    def s1_again(ctx):
        calls.append(2)
        return "should-not-run"

    assert wf2.run(lambda w: s1_again(w)) == "cached-value"
    assert calls == [1]  # second definition never executed


def test_step_retries_and_eventually_succeeds():
    wf, _ = make_workflow()
    attempts = {"n": 0}
    sleeps = []

    @wf.step("flaky", max_retries=3, backoff_base=0.001, sleep_fn=sleeps.append)
    def flaky(ctx):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise ValueError("not yet")
        return "success"

    result = wf.run(lambda w: flaky(w))
    assert result == "success"
    assert attempts["n"] == 3
    assert len(sleeps) == 2  # slept between attempt 0->1 and 1->2


def test_step_raises_step_failed_after_exhausting_retries():
    wf, _ = make_workflow()

    @wf.step("always_fails", max_retries=2, backoff_base=0.001, sleep_fn=lambda d: None)
    def always_fails(ctx):
        raise RuntimeError("nope")

    with pytest.raises(WorkflowFailed) as excinfo:
        wf.run(lambda w: always_fails(w))
    assert isinstance(excinfo.value.cause, StepFailed)


def test_resume_after_failure_skips_completed_steps():
    store = SQLiteStore(":memory:")
    call_log = []

    def make_entrypoint(workflow):
        @workflow.step("step_a")
        def step_a(ctx):
            call_log.append("a")
            return "a-result"

        @workflow.step("step_b", max_retries=0)
        def step_b(ctx, a_result):
            call_log.append("b")
            raise RuntimeError("step b explodes")

        def entrypoint(w):
            a = step_a(w)
            return step_b(w, a)

        return entrypoint

    wf1 = Workflow(name="wf", run_id="run-1", store=store)
    with pytest.raises(WorkflowFailed):
        wf1.run(make_entrypoint(wf1))
    assert call_log == ["a", "b"]

    # Resuming should not re-run step_a since it already completed.
    call_log.clear()
    wf2 = Workflow(name="wf", run_id="run-1", store=store)

    def make_entrypoint_fixed(workflow):
        @workflow.step("step_a")
        def step_a(ctx):
            call_log.append("a")
            return "a-result"

        @workflow.step("step_b", max_retries=0)
        def step_b(ctx, a_result):
            call_log.append("b")
            return f"processed-{a_result}"

        def entrypoint(w):
            a = step_a(w)
            return step_b(w, a)

        return entrypoint

    result = wf2.run(make_entrypoint_fixed(wf2))
    assert result == "processed-a-result"
    assert call_log == ["b"]  # step_a was skipped (memoized)


def test_approval_gate_pauses_and_resumes():
    store = SQLiteStore(":memory:")
    wf1 = Workflow(name="wf", run_id="run-1", store=store)

    def entrypoint(w):
        w.approval_gate("go")
        return "done"

    with pytest.raises(ApprovalPending):
        wf1.run(entrypoint)

    run = store.get_run("run-1")
    assert run.status == "waiting"
    assert run.waiting_gate == "go"

    # Not yet approved: resuming still raises.
    wf2 = Workflow(name="wf", run_id="run-1", store=store)
    with pytest.raises(ApprovalPending):
        wf2.run(entrypoint)

    store.approve_gate("run-1", "go")
    wf3 = Workflow(name="wf", run_id="run-1", store=store)
    result = wf3.run(entrypoint)
    assert result == "done"
    assert store.get_run("run-1").status == "completed"


def test_step_only_retries_on_specified_exception_types():
    wf, _ = make_workflow()

    @wf.step(
        "typed",
        max_retries=3,
        backoff_base=0.001,
        retry_on=(ConnectionError,),
        sleep_fn=lambda d: None,
    )
    def typed(ctx):
        raise ValueError("not retryable per config")

    with pytest.raises(ValueError):
        wf.run(lambda w: typed(w))
