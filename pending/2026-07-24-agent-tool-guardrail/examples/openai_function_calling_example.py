"""Example: guarding tools dispatched from an OpenAI-style function-calling
loop. This does NOT require the `openai` package -- it simulates the shape
of a tool_call dict that the OpenAI/most LLM SDKs return, so the example
runs offline in CI.

In a real integration you would receive `tool_call.function.name` and
`json.loads(tool_call.function.arguments)` from the model response and pass
them straight into the dispatch table built here.
"""

from __future__ import annotations

import json

from agent_guardrail import GuardedToolError, Policy, PolicyViolation, TraceRecorder, guard

policy = Policy.from_yaml("policies/example_policy.yaml")
tracer = TraceRecorder("traces/openai_example.jsonl", session_id="openai-demo")


@guard(policy=policy, tracer=tracer)
def search_web(query: str) -> str:
    return f"top result for '{query}'"


TOOL_DISPATCH = {"search_web": search_web}


def handle_tool_call(tool_call: dict) -> str:
    """Mimics the loop you'd run after receiving a `tool_calls` array from
    a chat completion response."""
    name = tool_call["function"]["name"]
    arguments = json.loads(tool_call["function"]["arguments"])
    fn = TOOL_DISPATCH.get(name)
    if fn is None:
        return json.dumps({"error": f"unknown tool '{name}'"})
    try:
        result = fn(**arguments)
        return json.dumps({"result": result})
    except (PolicyViolation, GuardedToolError) as exc:
        return json.dumps({"error": str(exc)})


if __name__ == "__main__":
    simulated_tool_call = {
        "id": "call_1",
        "type": "function",
        "function": {"name": "search_web", "arguments": json.dumps({"query": "LLM agent guardrails"})},
    }
    print(handle_tool_call(simulated_tool_call))
