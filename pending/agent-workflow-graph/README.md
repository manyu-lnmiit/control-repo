# agent-workflow-graph

[![CI](https://github.com/manyu-lnmiit/agent-workflow-graph/actions/workflows/ci.yml/badge.svg)](https://github.com/manyu-lnmiit/agent-workflow-graph/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)

**agent-workflow-graph** is a dependency-free Python engine for composing multi-agent LLM workflows as
directed graphs: plain-function nodes, conditional edges for agentic loops (plan → act → critique → retry),
and parallel fan-out/fan-in for running independent sub-agents concurrently and joining their results — all
with automatic per-node retries, a level-synchronous executor, an execution trace for debugging, and a
one-line Mermaid export for documenting the graph you built.

## Quickstart

```bash
pip install -e .
```

```python
from agentworkflow import END, Executor, StateGraph

def greet(state):
    return {"message": f"Hello, {state['name']}!"}

graph = StateGraph()
graph.add_node("greet", greet)
graph.set_entry_point("greet")
graph.add_edge("greet", END)

result = Executor(graph.compile()).run({"name": "world"})
print(result.final_state["message"])  # -> Hello, world!
```

Or run the bundled example workflow straight from the CLI:

```bash
agentworkflow run --graph examples.research_workflow:build_graph \
  --input '{"topic": "rust vs go"}' --trace
```

## Why this exists

Most "agent framework" code in the wild is a linear chain of LLM calls glued together with `if` statements.
That works until you need two things real agentic systems eventually need: **loops** (an agent that
critiques its own output and retries until a quality bar is met) and **fan-out** (multiple sub-agents
working a problem from different angles, then merging their findings). Hand-rolling both of those with plain
control flow gets messy fast — retry logic, partial-state merging, and "did everyone finish" bookkeeping
end up duplicated across every workflow.

`agent-workflow-graph` gives you a small, explicit vocabulary for this — nodes, static edges, conditional
edges, and parallel edges — compiles it into a validated graph (catching unknown node references and
un-terminating static cycles before you ever run it), and executes it round by round so fan-out and fan-in
fall out of the model for free, with no framework-specific agent abstractions, prompt templates, or vendor
lock-in. Bring your own LLM client; the graph only cares about the state dict your nodes read and write.

## Architecture

```mermaid
flowchart TD
    start([start]) --> plan
    plan --> research_technical
    plan --> research_business
    plan --> research_risks
    research_technical --> aggregate
    research_business --> aggregate
    research_risks --> aggregate
    aggregate --> critique
    critique -.revise.-> revise
    critique -.finalize.-> finalize
    revise --> research_technical
    revise --> research_business
    revise --> research_risks
    finalize --> end([end])
```

*(This is the bundled `examples/research_workflow.py` graph — a parallel fan-out of three sub-researchers,
an aggregator join, and a critique-driven revision loop. Generate this diagram for any graph you build with
`agentworkflow visualize --graph your.module:build_graph`.)*

Execution model, in short:

1. The executor tracks a **frontier** — the set of node names ready to run this round.
2. Every node in the frontier runs concurrently in a thread pool (agent nodes are typically I/O-bound LLM or
   tool calls), and its partial state update is merged into the shared state.
3. The next frontier is the **union** of each executed node's successors. This is what makes fan-out and
   fan-in "just work": three parallel branches naturally collapse back into one set entry when they all
   point at the same downstream node, so it runs once, not three times.
4. A **conditional edge** calls a plain `router(state) -> key` function and looks `key` up in a
   `path_map` to decide where to go next — this is how loops (retry, refine, re-plan) and branching
   (route to a specialist sub-agent) are expressed.
5. `max_steps` is a hard ceiling on rounds, so a conditional loop that never converges fails loudly
   (`MaxStepsExceededError`) instead of hanging forever.

## Usage examples

**Conditional loop (retry until a critic is satisfied):**

```python
from agentworkflow import END, Executor, StateGraph

def draft(state):
    return {"n": state.get("n", 0) + 1}

def route(state):
    return "again" if state["n"] < 3 else "done"

g = StateGraph()
g.add_node("draft", draft)
g.set_entry_point("draft")
g.add_conditional_edges("draft", route, {"again": "draft", "done": END})

result = Executor(g.compile()).run({})
assert result.final_state["n"] == 3
```

**Parallel fan-out with a custom reducer for merging results:**

```python
from agentworkflow import END, Executor, StateGraph

def merge_dicts(old, new):
    return {**old, **new}

g = StateGraph(reducers={"findings": merge_dicts})
g.add_node("start", lambda s: {})
g.add_node("angle_a", lambda s: {"findings": {"a": "..."}})
g.add_node("angle_b", lambda s: {"findings": {"b": "..."}})
g.add_node("join", lambda s: {"summary": sorted(s["findings"])})
g.set_entry_point("start")
g.add_parallel_edges("start", ["angle_a", "angle_b"])
g.add_edge("angle_a", "join")
g.add_edge("angle_b", "join")
g.add_edge("join", END)

result = Executor(g.compile()).run({})
```

**Node-level retries** for transient failures (rate limits, flaky tool calls):

```python
g.add_node("call_api", my_flaky_fn, retries=3, retry_delay=0.5)
```

**CLI:**

```bash
agentworkflow run --graph mypkg.workflows:build_graph --input '{"topic": "..."}' --trace
agentworkflow visualize --graph mypkg.workflows:build_graph   # prints a Mermaid flowchart
```

**Docker:**

```bash
docker build -t agent-workflow-graph .
docker run --rm agent-workflow-graph
```

## Limitations

- **No built-in persistence.** State lives in memory for the duration of a `run()` call; there is no
  checkpointing or crash-resume (if you need that, pair this with a durable-execution layer — this project
  intentionally stays focused on graph composition and in-process execution, not durability).
- **Uneven parallel branches can double-run a join.** Because fan-in is implicit (branches converging in the
  same round), branches of very different lengths can reach a shared downstream node in different rounds,
  running it more than once. Keep parallel branches roughly the same length, or make aggregator nodes
  idempotent.
- **Threads, not processes.** Node concurrency uses a `ThreadPoolExecutor`, which is the right fit for
  I/O-bound LLM/tool calls but won't parallelize CPU-bound Python work — shell out or use a process pool
  inside a node if you need that.
- **No built-in LLM client.** This is intentionally provider-agnostic; wire in whatever client you use
  inside your node functions (see `examples/research_workflow.py` for where that call would go).

## Development

```bash
pip install -e ".[dev]"
ruff check src tests examples
mypy src
pytest --cov=agentworkflow --cov-report=term-missing
```

## License

MIT © Abhimanyu — see [LICENSE](LICENSE).
