"""End-to-end example: a "research agent" workflow with a flaky tool call,
retries, checkpointing, and a human-in-the-loop approval gate before
"publishing" its output.

Run it twice from the same directory with the same RUN_ID to see resumable
behavior: the first run will pause for approval; approve the gate via the
CLI, then re-run this script to see it complete without repeating the
(expensive) fetch/summarize steps.

    python examples/research_agent_workflow.py run-demo-1
    agentflow --db examples.db approve run-demo-1 publish_approval
    python examples/research_agent_workflow.py run-demo-1
"""

from __future__ import annotations

import sys

from agentflow import ApprovalPending, SQLiteStore, Workflow, WorkflowFailed

_flaky_call_count = {"n": 0}


def fetch_sources(ctx) -> list[str]:
    """Simulates an unreliable external tool call (e.g. a web search API)
    that fails the first time and succeeds on retry."""
    _flaky_call_count["n"] += 1
    if _flaky_call_count["n"] == 1:
        raise ConnectionError("search API timed out")
    return [
        "https://example.com/agentic-ai-2026",
        "https://example.com/durable-execution-patterns",
    ]


def summarize(ctx, sources: list[str]) -> str:
    """Simulates an LLM call that condenses the fetched sources."""
    return (
        f"Summary of {len(sources)} sources: agentic workflows benefit from "
        "durable, checkpointed execution."
    )


def publish(ctx, summary: str) -> dict:
    return {"published": True, "summary": summary}


def build_and_run(run_id: str, db_path: str = "examples.db") -> dict:
    store = SQLiteStore(db_path)
    workflow = Workflow(name="research_agent", run_id=run_id, store=store)

    fetch_step = workflow.step("fetch_sources", max_retries=2, backoff_base=0.01)(
        fetch_sources
    )
    summarize_step = workflow.step("summarize")(summarize)
    publish_step = workflow.step("publish")(publish)

    def entrypoint(wf: Workflow):
        sources = fetch_step(wf)
        summary = summarize_step(wf, sources)
        wf.approval_gate("publish_approval")
        return publish_step(wf, summary)

    return workflow.run(entrypoint)


def main() -> int:
    run_id = sys.argv[1] if len(sys.argv) > 1 else "run-demo-1"
    try:
        result = build_and_run(run_id)
        print(f"workflow completed: {result}")
        return 0
    except ApprovalPending as ap:
        print(
            f"paused: run {ap.run_id!r} waiting for approval at gate {ap.gate_name!r}.\n"
            f"approve with: agentflow --db examples.db approve {ap.run_id} {ap.gate_name}"
        )
        return 0
    except WorkflowFailed as wf_err:
        print(f"workflow failed: {wf_err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
