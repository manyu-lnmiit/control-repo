from agentworkflow import END, StateGraph
from agentworkflow.visualize import to_mermaid


def test_mermaid_contains_all_nodes_and_edge_styles():
    g = StateGraph()
    g.add_node("a", lambda s: {})
    g.add_node("b", lambda s: {})
    g.add_node("c", lambda s: {})
    g.set_entry_point("a")
    g.add_conditional_edges("a", lambda s: "go", {"go": "b", "stop": END})
    g.add_edge("b", "c")
    g.add_edge("c", END)

    mermaid = to_mermaid(g.compile())
    assert mermaid.startswith("flowchart TD")
    for node in ("a", "b", "c"):
        assert f"{node}[{node}]" in mermaid
    assert "-.go.-> b" in mermaid
    assert "-.stop.-> __end__" in mermaid
    assert "b --> c" in mermaid


def test_mermaid_direction_override():
    g = StateGraph()
    g.add_node("a", lambda s: {})
    g.set_entry_point("a")

    mermaid = to_mermaid(g.compile(), direction="LR")
    assert mermaid.startswith("flowchart LR")
