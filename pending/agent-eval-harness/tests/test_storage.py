from agent_eval_harness.mock_agent import MockAgent
from agent_eval_harness.report import compare_runs
from agent_eval_harness.runner import run_suite
from agent_eval_harness.storage import ResultStore
from agent_eval_harness.task import Task, TaskSuite


def _suite(expected_b: str) -> TaskSuite:
    return TaskSuite(
        name="regress-suite",
        tasks=[
            Task(id="a", prompt="a", scorer="exact_match", expected="1"),
            Task(id="b", prompt="b", scorer="exact_match", expected=expected_b),
        ],
    )


def test_store_save_and_load_all(tmp_path):
    store = ResultStore(tmp_path / "runs.jsonl")
    agent = MockAgent(responses={"a": "1", "b": "2"})
    result = run_suite(agent, _suite(expected_b="2"))
    record = store.save(result, run_id="run-1", agent_label="agentA")

    assert record.run_id == "run-1"
    all_runs = store.load_all()
    assert len(all_runs) == 1
    assert all_runs[0].agent_label == "agentA"
    assert all_runs[0].pass_rate == 1.0


def test_store_latest_and_previous(tmp_path):
    store = ResultStore(tmp_path / "runs.jsonl")
    agent = MockAgent(responses={"a": "1", "b": "wrong"})

    run1 = run_suite(agent, _suite(expected_b="2"))  # b fails
    store.save(run1, run_id="run-1")

    agent2 = MockAgent(responses={"a": "1", "b": "2"})
    run2 = run_suite(agent2, _suite(expected_b="2"))  # b now passes
    store.save(run2, run_id="run-2")

    latest = store.latest()
    previous = store.previous()
    assert latest.run_id == "run-2"
    assert previous.run_id == "run-1"


def test_store_filters_by_suite_name(tmp_path):
    store = ResultStore(tmp_path / "runs.jsonl")
    agent = MockAgent(responses={"a": "1", "b": "2"})

    other_suite = TaskSuite(name="other-suite", tasks=[Task(id="x", prompt="x", expected="y")])
    store.save(run_suite(agent, other_suite), run_id="other-1")
    store.save(run_suite(agent, _suite(expected_b="2")), run_id="regress-1")

    latest = store.latest(suite_name="regress-suite")
    assert latest.run_id == "regress-1"


def test_regression_detection_across_runs(tmp_path):
    store = ResultStore(tmp_path / "runs.jsonl")

    agent_v1 = MockAgent(responses={"a": "1", "b": "2"})
    run1 = run_suite(agent_v1, _suite(expected_b="2"))
    store.save(run1, run_id="run-1")

    # Simulate a regression: agent v2 gets "b" wrong now.
    agent_v2 = MockAgent(responses={"a": "1", "b": "broken"})
    run2 = run_suite(agent_v2, _suite(expected_b="2"))
    store.save(run2, run_id="run-2")

    baseline = store.previous()
    current = store.latest()
    report = compare_runs(baseline, current)

    assert report.regressed == ["b"]
    assert report.fixed == []
    assert report.has_regressions
    assert report.score_delta < 0
