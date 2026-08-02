"""Example: plug an abstractive, LLM-backed summarizer into the Compactor.

The built-in ExtractiveSummarizer is dependency-free and deterministic, but
for higher-quality compaction you can swap in any callable that turns a run
of dropped messages into a summary string -- including a real LLM call.

This example is illustrative only: it does not require `OPENAI_API_KEY` to
be set to run `python examples/llm_summarizer.py`, and falls back to a stub
"LLM" so the example works offline.

    export OPENAI_API_KEY=sk-...
    python examples/llm_summarizer.py
"""

from __future__ import annotations

import os

from context_compactor import Compactor, Message, TokenBudget
from context_compactor.summarizer import make_callable_summarizer


def stub_llm_complete(prompt: str) -> str:
    """Stand-in for a real LLM call so this example runs without credentials."""
    return "Summary: " + prompt.splitlines()[-1][:80]


def llm_summarize(messages: list[Message]) -> str:
    transcript = "\n".join(f"{m.role}: {m.content}" for m in messages)
    prompt = f"Summarize the following conversation turns concisely:\n{transcript}"

    if os.environ.get("OPENAI_API_KEY"):
        # Real usage would look something like:
        #
        #   from openai import OpenAI
        #   client = OpenAI()
        #   response = client.chat.completions.create(
        #       model="gpt-4o-mini",
        #       messages=[{"role": "user", "content": prompt}],
        #   )
        #   return response.choices[0].message.content
        raise NotImplementedError("Wire up your real LLM client here.")

    return stub_llm_complete(prompt)


def main() -> None:
    messages = [
        Message(role="user", content=f"Tell me fact number {i} about distributed systems.")
        for i in range(20)
    ]
    messages[0].pinned = True
    messages[0].content = "SYSTEM: You are a helpful, concise assistant."
    messages[0].role = "system"

    compactor = Compactor(summarizer=make_callable_summarizer(llm_summarize))
    result = compactor.compact(messages, TokenBudget(max_tokens=120))

    for m in result.messages:
        print(f"[{m.role}] {m.content}")
    print(f"\n{result.stats}")


if __name__ == "__main__":
    main()
