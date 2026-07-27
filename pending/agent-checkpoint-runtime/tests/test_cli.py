
from agentflow import ApprovalPending, SQLiteStore, Workflow
from agentflow.cli import main


def _make_paused_run(db_path: str, run_id: str = "run-cli-1"):
    store = SQLiteStore(db_path)
    workflow = Workflow(name="wf", run_id=run_id, store=store)

    @workflow.step("collect")
    def collect(ctx):
        return {"n": 3}

    def entrypoint(w):
        collect(w)
        w.approval_gate("ship")
        return "shipped"

    try:
        workflow.run(entrypoint)
    except ApprovalPending:
        pass
    return store


def test_cli_list_and_status(tmp_path, capsys):
    db_path = str(tmp_path / "cli.db")
    _make_paused_run(db_path)

    rc = main(["--db", db_path, "list"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "run-cli-1" in out
    assert "waiting" in out

    rc = main(["--db", db_path, "status", "run-cli-1"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "waiting_gate  : ship" in out


def test_cli_status_unknown_run(tmp_path, capsys):
    db_path = str(tmp_path / "cli.db")
    SQLiteStore(db_path)  # create empty db
    rc = main(["--db", db_path, "status", "nope"])
    assert rc == 1


def test_cli_history(tmp_path, capsys):
    db_path = str(tmp_path / "cli.db")
    _make_paused_run(db_path)

    rc = main(["--db", db_path, "history", "run-cli-1"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "collect" in out
    assert "status=completed" in out


def test_cli_approve_then_resume_completes_workflow(tmp_path):
    db_path = str(tmp_path / "cli.db")
    store = _make_paused_run(db_path)

    rc = main(["--db", db_path, "approve", "run-cli-1", "ship", "--note", "ok"])
    assert rc == 0

    # Resuming the same workflow should now complete successfully.
    workflow = Workflow(name="wf", run_id="run-cli-1", store=store)

    @workflow.step("collect")
    def collect(ctx):
        return {"n": 3}

    def entrypoint(w):
        collect(w)
        w.approval_gate("ship")
        return "shipped"

    result = workflow.run(entrypoint)
    assert result == "shipped"

    run = store.get_run("run-cli-1")
    assert run.status == "completed"
    assert run.result == "shipped"
