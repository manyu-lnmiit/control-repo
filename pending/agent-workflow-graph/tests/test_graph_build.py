import pytest
from agentworkflow import END, START, StateGraph
from agentworkflow.errors import (
    CycleDetectedError,
    DuplicateNodeError,
    GraphValidationError,
    UnknownNodeError,
)


def _noop(state):
    return {}


def test_simple_linear_graph_compiles():
    g = StateGraph()
    g.add_node("a", _noop)
    g.add_node("b", _noop)
    g.set_entry_point("a")
    g.add_edge("a", "b")
    g.add_edge("b", END)
    compiled = g.compile()
    assert compiled.entry_targets() == ["a"]
    assert compiled.resolve_next("a", {}) == ["b"]
    assert compiled.resolve_next("b", {}) == [END]


def test_duplicate_node_rejected():
    g = StateGraph()
    g.add_node("a", _noop)
    with pytest.raises(DuplicateNodeError):
        g.add_node("a", _noop)


def test_reserved_names_rejected():
    g = StateGraph()
    with pytest.raises(GraphValidationError):
        g.add_node(START, _noop)
    with pytest.raises(GraphValidationError):
        g.add_node(END, _noop)


def test_unknown_edge_target_rejected():
    g = StateGraph()
    g.add_node("a", _noop)
    g.set_entry_point("a")
    g.add_edge("a", "ghost")
    with pytest.raises(UnknownNodeError):
        g.compile()


def test_missing_entry_point_rejected():
    g = StateGraph()
    g.add_node("a", _noop)
    with pytest.raises(GraphValidationError):
        g.compile()


def test_empty_graph_rejected():
    g = StateGraph()
    with pytest.raises(GraphValidationError):
        g.compile()


def test_static_cycle_rejected():
    g = StateGraph()
    g.add_node("a", _noop)
    g.add_node("b", _noop)
    g.set_entry_point("a")
    g.add_edge("a", "b")
    g.add_edge("b", "a")
    with pytest.raises(CycleDetectedError):
        g.compile()


def test_conditional_loop_is_allowed_at_compile_time():
    g = StateGraph()
    g.add_node("a", _noop)
    g.add_node("b", _noop)
    g.set_entry_point("a")
    g.add_conditional_edges("a", lambda s: "loop", {"loop": "b", "stop": END})
    g.add_edge("b", "a")
    compiled = g.compile()  # must not raise
    assert compiled.resolve_next("a", {}) == ["b"]


def test_add_parallel_edges_requires_multiple_targets():
    g = StateGraph()
    g.add_node("a", _noop)
    g.add_node("b", _noop)
    g.set_entry_point("a")
    with pytest.raises(GraphValidationError):
        g.add_parallel_edges("a", ["b"])


def test_double_outgoing_edge_definition_rejected():
    g = StateGraph()
    g.add_node("a", _noop)
    g.add_node("b", _noop)
    g.add_node("c", _noop)
    g.set_entry_point("a")
    g.add_edge("a", "b")
    with pytest.raises(GraphValidationError):
        g.add_edge("a", "c")


def test_router_returning_unknown_key_raises_at_runtime():
    g = StateGraph()
    g.add_node("a", _noop)
    g.add_node("b", _noop)
    g.set_entry_point("a")
    g.add_conditional_edges("a", lambda s: "nope", {"ok": "b"})
    compiled = g.compile()
    with pytest.raises(UnknownNodeError):
        compiled.resolve_next("a", {})
