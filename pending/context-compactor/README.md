# context-compactor

[![CI](https://github.com/manyu-lnmiit/context-compactor/actions/workflows/ci.yml/badge.svg)](https://github.com/manyu-lnmiit/context-compactor/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)

**context-compactor** fits a growing LLM/agent conversation into a fixed token budget — automatically deciding what to keep verbatim, what to summarize, and what to drop — so long-running agents stop silently truncating or blowing their context window. It scores every message for importance (role, recency, keyword signals, or your own logic), always protects pinned turns like the system prompt, and collapses low-value runs into compact summaries instead of just chopping them off.

## Quickstart

```bash
pip install context-compactor
```

```python
from context_compactor import Compactor, Message, TokenBudget

messages = [
    Message(role="system", content="You are a helpful assistant.", pinned=True),
    Message(role="user", content="What's the weather like on Mars?"),
    Message(role="assistant", content="Cold, thin CO2 atmosphere, frequent dust storms."),
    # ... hundreds more turns from a long-running agent session ...
]

result = Compactor().compact(messages, TokenBudget(max_tokens=2000, reserve_tokens=500))

print(result.as_chat_messages())  # ready to hand straight to your LLM call
print(result.stats)               # tokens saved, messages dropped/summarized, etc.
```

That's it — no API keys, no external services, no required dependencies.

## The problem

Agent loops and chat sessions grow without bound: tool outputs, retries, intermediate reasoning, and back-and-forth all pile into the context. Naive fixes are all lossy in a specific, painful way:

- Hard truncation ("just drop the oldest N messages") silently deletes the system prompt, key decisions, or early constraints the user gave you.
- Sending everything and letting the API reject the request turns a slow-burn problem into a hard outage.
- Rolling your own priority + summarization logic is easy to get *wrong* in ways that are hard to notice until an agent forgets something important mid-run.

context-compactor gives you a small, well-tested primitive for this instead of another bespoke truncation hack per project.

## Architecture

```
                    ┌─────────────────────┐
   Message[]  ───▶  │      Compactor       │  ───▶  CompactionResult
   TokenBudget       │                      │         (messages + stats)
                    │  1. count tokens      │
                    │  2. keep pinned       │
                    │  3. score the rest    │◀── ImportanceScorer (pluggable)
                    │  4. greedily keep     │
                    │     top-scored msgs   │
                    │  5. summarize runs    │◀── Summarizer (pluggable)
                    │     of dropped msgs   │
                    │  6. last-resort trim  │
                    └─────────────────────┘
```

- **Tokenizer** — a dependency-free approximate counter by default (`SimpleTokenizer`), or wrap `tiktoken` via `TiktokenTokenizer` for OpenAI-accurate counts.
- **ImportanceScorer** — `DefaultImportanceScorer` blends recency, role weight (system > user > assistant > tool), and keyword signals ("error", "decision", "TODO", ...). Supply your own to encode domain logic, or set `Message.importance` directly to override per message.
- **Summarizer** — `ExtractiveSummarizer` compresses a dropped run into a compact, deterministic, offline summary. Swap in an LLM-backed summarizer (see `examples/llm_summarizer.py`) for abstractive summaries.
- **Compactor** — orchestrates the above: pinned messages always survive, the highest-value messages are kept verbatim up to budget, and contiguous runs of the rest are either summarized into one block (`EvictionStrategy.SUMMARIZE`) or dropped outright (`EvictionStrategy.DROP`), while preserving conversational order.

## Usage examples

### Pin the system prompt, cap the rest

```python
from context_compactor import Compactor, Message, TokenBudget

system = Message(role="system", content="You are a support triage agent.", pinned=True)
history = [Message(role="user" if i % 2 == 0 else "assistant", content=f"turn {i}") for i in range(200)]

result = Compactor().compact([system, *history], TokenBudget(max_tokens=1500))
```

### Drop instead of summarize

```python
from context_compactor.compactor import EvictionStrategy

compactor = Compactor(strategy=EvictionStrategy.DROP)
```

### Custom importance scoring

```python
from context_compactor.scoring import ImportanceScorer

class OrderIdBoostScorer(ImportanceScorer):
    def score(self, message, *, position, total):
        base = position / max(1, total - 1)
        return base + (0.5 if "order_id" in message.metadata else 0.0)

compactor = Compactor(scorer=OrderIdBoostScorer())
```

### CLI

```bash
context-compactor stats transcript.jsonl
context-compactor compact transcript.jsonl --max-tokens 2000 --output compacted.jsonl
```

### Optional HTTP service

```bash
pip install "context-compactor[api]"
uvicorn context_compactor.api:app --reload
curl -X POST localhost:8000/compact -H 'content-type: application/json' \
  -d '{"messages": [{"role": "user", "content": "hi"}], "max_tokens": 500}'
```

### Docker

```bash
docker build -t context-compactor .
docker run --rm -p 8000:8000 context-compactor
```

## Limitations

- The default `SimpleTokenizer` is an approximation (character + word heuristics); for exact OpenAI token accounting, install the `tiktoken` extra and use `TiktokenTokenizer`.
- `ExtractiveSummarizer` is intentionally simple and offline (first sentences per message) — it favors speed and determinism over summary quality. Plug in an LLM-backed summarizer for higher fidelity.
- Compaction is stateless per call: the library doesn't persist or re-derive information from messages it has already dropped. If you need durable long-term memory beyond the active context window, pair this with a separate memory store.
- Scoring and summarization run synchronously in-process; very large transcripts (tens of thousands of messages) haven't been benchmarked for latency.

## Development

```bash
pip install -e ".[dev,api]"
ruff check src tests
mypy src
pytest --cov=context_compactor
```

## License

MIT © Abhimanyu — see [LICENSE](LICENSE).
