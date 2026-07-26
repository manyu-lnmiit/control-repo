from agent_eval_harness.mock_agent import MockAgent
from agent_eval_harness.runner import run_suite, run_task
from agent_eval_harness.task import Task, TaskSuite


def test_run_task_pass():
    agent = MockAgent(responses={"2+2": "4"})
    task = Task(id="math", prompt="2+2", scorer="exact_match", expected="4")
    result = run_task(agent, task)
    assert result.passed
    assert result.score == 1.0
    assert result.error is None


def test_run_task_fail():
    agent = MockAgent(responses={"2+2": "5"})
    task = Task(id="math", prompt="2+2", scorer="exact_match", expected="4")
    result = run_task(agent, task)
    assert not result.passed


def test_run_task_captures_agent_exception():
    def boom(prompt: str):
        raise RuntimeError("agent exploded")

    agent = MockAgent(fn=boom)
    task = Task(id="bad", prompt="anything", scorer="exact_match", expected="x")
    result = run_task(agent, task)
    assert not result.passed
    assert result.error is not None
    assert "agent exploded" in result.error


def test_run_suite_aggregates_and_weights():
    agent = MockAgent(responses={"a": "1", "b": "wrong"})
    suite = TaskSuite(
        name="s",
        tasks=[
            Task(id="a", prompt="a", scorer="exact_match", expected="1", weight=1.0),
            Task(id="b", prompt="b", scorer="exact_match", expected="right", weight=3.0),
        ],
    )
    result = run_suite(agent, suite)
    assert result.pass_rate == 0.5
    # weighted_score = (1*1.0 + 0*3.0) / (1.0 + 3.0) = 0.25
    assert abs(result.weighted_score - 0.25) < 1e-9
    assert result.by_id("a").passed
    assert not result.by_id("b").passed
    assert [r.task_id for r in result.failed()] == ["b"]


def test_suite_run_result_to_dict_roundtrip():
    agent = MockAgent(responses={"a": "1"})
    suite = TaskSuite(name="s", tasks=[Task(id="a", prompt="a", expected="1")])
    result = run_suite(agent, suite)
    d = result.to_dict()
    assert d["suite_name"] == "s"
    assert d["results"][0]["task_id"] == "a"
    assert d["results"][0]["passed"] is True
