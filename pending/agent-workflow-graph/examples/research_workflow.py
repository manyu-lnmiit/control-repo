"""Example: a fan-out/fan-in research agent workflow with a critique loop.

Shape of the graph::

    start -> plan -> [research_angle_a, research_angle_b, research_angle_c] -> aggregate
                                                                                  |
                                                                            critique <-.
                                                                             /    \\    |
                                                                        revise      finalize -> end
                                                                          `----------'

``plan`` fans out into three parallel "sub-researcher" nodes (each looks at a
different angle of the topic), ``aggregate`` joins them back into one report
draft, and ``critique`` scores the draft and either loops back to ``revise``
(which feeds back into research) or proceeds to ``finalize``.

The "LLM calls" here are deterministic stand-ins (``_fake_llm``) so the
example runs offline and its tests are fast and reproducible. Swap
``_fake_llm`` for a real client call (e.g. the Anthropic Messages API) to use
this workflow for real; the rest of the graph is unchanged either way.
"""

from __future__ import annotations

import operator
from typing import Any

from agentworkflow import END, StateGraph

ANGLES = ["technical", "business", "risks"]


def _fake_llm(prompt: str) -> str:
    """Deterministic stand-in for an LLM call, keyed off the prompt content.

    Replace this with a real call, e.g.::

        response = client.messages.create(model="claude-...", messages=[{"role": "user", "content": prompt}])
        return response.content[0].text
    """
    seed = sum(ord(c) for c in prompt) % 97
    return f"[analysis seed={seed}] {prompt[:60]}"


def plan(state: dict[str, Any]) -> dict[str, Any]:
    topic = state["topic"]
    return {"plan": f"Research '{topic}' across angles: {', '.join(ANGLES)}"}


def _research(angle: str):
    def node(state: dict[str, Any]) -> dict[str, Any]:
        topic = state["topic"]
        focus = state.get("revision_focus")
        prompt = f"Analyze the {angle} angle of '{topic}'"
        if focus == angle:
            prompt += " -- go deeper, the previous pass was too shallow"
        text = _fake_llm(prompt)
        return {"findings": {angle: text}}

    node.__name__ = f"research_{angle}"
    return node


def aggregate(state: dict[str, Any]) -> dict[str, Any]:
    findings: dict[str, str] = state.get("findings", {})
    report = "\n".join(f"## {angle}\n{findings.get(angle, '(missing)')}" for angle in ANGLES)
    iteration = state.get("iteration", 0) + 1
    return {"report": report, "iteration": iteration}


def critique(state: dict[str, Any]) -> dict[str, Any]:
    findings: dict[str, str] = state.get("findings", {})
    # Deterministic "quality" heuristic: score rises each revision pass so
    # the loop provably terminates; a real critique node would call an LLM
    # judge or a rubric-based scorer instead.
    completeness = len(findings) / len(ANGLES)
    depth_bonus = 0.34 * (state.get("iteration", 1) - 1)
    score = min(1.0, completeness * 0.66 + depth_bonus)
    weakest = min(ANGLES, key=lambda a: len(findings.get(a, "")))
    return {"score": score, "revision_focus": weakest}


def route_after_critique(state: dict[str, Any]) -> str:
    if state.get("score", 0.0) >= 0.9 or state.get("iteration", 0) >= 3:
        return "finalize"
    return "revise"


def revise(state: dict[str, Any]) -> dict[str, Any]:
    # No-op passthrough node: exists purely to route back into the parallel
    # research fan-out with `revision_focus` already set by critique().
    return {}


def finalize(state: dict[str, Any]) -> dict[str, Any]:
    report = state.get("report", "")
    score = state.get("score", 0.0)
    return {"final_report": f"{report}\n\n---\nconfidence: {score:.2f}"}


def merge_findings(old: dict[str, str], new: dict[str, str]) -> dict[str, str]:
    merged = dict(old)
    merged.update(new)
    return merged


def build_graph() -> StateGraph:
    graph: StateGraph = StateGraph(
        reducers={
            "findings": merge_findings,
            "log": operator.add,
        }
    )

    graph.add_node("plan", plan)
    for angle in ANGLES:
        graph.add_node(f"research_{angle}", _research(angle))
    graph.add_node("aggregate", aggregate)
    graph.add_node("critique", critique)
    graph.add_node("revise", revise)
    graph.add_node("finalize", finalize)

    graph.set_entry_point("plan")
    graph.add_parallel_edges("plan", [f"research_{angle}" for angle in ANGLES])
    for angle in ANGLES:
        graph.add_edge(f"research_{angle}", "aggregate")
    graph.add_edge("aggregate", "critique")
    graph.add_conditional_edges("critique", route_after_critique, {"revise": "revise", "finalize": "finalize"})
    graph.add_parallel_edges("revise", [f"research_{angle}" for angle in ANGLES])
    graph.add_edge("finalize", END)

    return graph
