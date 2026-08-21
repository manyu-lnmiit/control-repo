import operator
import threading

import pytest
from agentworkflow import END, Executor, StateGraph
from agentworkflow.errors import MaxStepsExceededError, NodeExecutionError


def test_linear_execution_merges_state():
    g = StateGraph()
    g.add_node("a", lambda s: {"x": 1})
    g.add_node("b", lambda s: {"y": s["x"] + 1})
    g.set_entry_point("a")
    g.add_edge("a", "b")
    g.add_edge("b", END)

    result = Executor(g.compile()).run({})
    assert result.completed
    assert result.final_state == {"x": 1, "y": 2}
    assert [t.node for t in result.trace] == ["a", "b"]


def test_conditional_loop_terminates():
    def counter(state):
        return {"n": state.get("n", 0) + 1}

    def router(state):
        return "again" if state["n"] < 3 else "done"

    g = StateGraph()
    g.add_node("loop", counter)
    g.set_entry_point("loop")
    g.add_conditional_edges("loop", router, {"again": "loop", "done": END})

    result = Executor(g.compile()).run({})
    assert result.final_state["n"] == 3
    assert result.steps == 3


def test_max_steps_exceeded_raises():
    def counter(state):
        return {"n": state.get("n", 0) + 1}

    g = StateGraph()
    g.add_node("loop", counter)
    g.set_entry_point("loop")
    g.add_conditional_edges("loop", lambda s: "again", {"again": "loop"})

    with pytest.raises(MaxStepsExceededError):
        Executor(g.compile(), max_steps=5).run({})


def test_parallel_fanout_runs_concurrently_and_joins():
    barrier = threading.Barrier(3, timeout=2)

    def make_branch(name):
        def node(state):
            barrier.wait()  # only passes if all 3 branches are running at once
            return {name: True}

        return node

    g = StateGraph()
    g.add_node("start", lambda s: {})
    g.add_node("a", make_branch("a"))
    g.add_node("b", make_branch("b"))
    g.add_node("c", make_branch("c"))
    g.add_node("join", lambda s: {"joined": sorted(k for k in ("a", "b", "c") if s.get(k))})
    g.set_entry_point("start")
    g.add_parallel_edges("start", ["a", "b", "c"])
    g.add_edge("a", "join")
    g.add_edge("b", "join")
    g.add_edge("c", "join")
    g.add_edge("join", END)

    result = Executor(g.compile()).run({})
    assert result.final_state["joined"] == ["a", "b", "c"]
    # join should run exactly once, not once per branch
    assert [t.node for t in result.trace].count("join") == 1


def test_custom_reducer_appends_instead_of_overwriting():
    g = StateGraph(reducers={"log": operator.add})
    g.add_node("a", lambda s: {"log": ["a ran"]})
    g.add_node("b", lambda s: {"log": ["b ran"]})
    g.set_entry_point("a")
    g.add_edge("a", "b")
    g.add_edge("b", END)

    result = Executor(g.compile()).run({"log": []})
    assert result.final_state["log"] == ["a ran", "b ran"]


def test_node_retries_then_succeeds():
    attempts = {"count": 0}

    def flaky(state):
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise RuntimeError("transient failure")
        return {"ok": True}

    g = StateGraph()
    g.add_node("flaky", flaky, retries=3, retry_delay=0.0)
    g.set_entry_point("flaky")
    g.add_edge("flaky", END)

    result = Executor(g.compile()).run({})
    assert result.final_state == {"ok": True}
    assert attempts["count"] == 3


def test_node_failure_raises_node_execution_error_after_exhausting_retries():
    def always_fails(state):
        raise ValueError("boom")

    g = StateGraph()
    g.add_node("bad", always_fails, retries=1)
    g.set_entry_point("bad")
    g.add_edge("bad", END)

    with pytest.raises(NodeExecutionError) as exc_info:
        Executor(g.compile()).run({})
    assert exc_info.value.node_name == "bad"
    assert isinstance(exc_info.value.original, ValueError)


def test_node_with_no_outgoing_edge_implicitly_ends():
    g = StateGraph()
    g.add_node("only", lambda s: {"done": True})
    g.set_entry_point("only")

    result = Executor(g.compile()).run({})
    assert result.final_state == {"done": True}
    assert result.completed
