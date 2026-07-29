# agent-memory-store

[![CI](https://github.com/manyu-lnmiit/agent-memory-store/actions/workflows/ci.yml/badge.svg)](https://github.com/manyu-lnmiit/agent-memory-store/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)

**agent-memory-store** is a dependency-free, drop-in long-term memory layer for LLM agents. It gives your agent episodic memory (individual events and observations) and semantic memory (distilled, general knowledge), retrieves the right memories for a given moment with importance-weighted, similarity-ranked search, fades stale memories over time the way biological memory does, and periodically consolidates clusters of related episodic memories into durable semantic summaries — all backed by a single SQLite file, with zero required third-party dependencies.

## Quickstart

```bash
pip install agent-memory-store
```

```python
from agent_memory_store import MemoryStore

with MemoryStore("agent.db") as memory:
    memory.add("The user's name is Priya and she prefers concise answers.")
    memory.add("Priya asked for the deploy runbook again.")

    results = memory.search("what does the user prefer?", k=2)
    for item, score in results:
        print(f"{score:.2f}  {item.content}")
```

Or from the command line:

```bash
agent-memory-store add "The user's timezone is UTC+5:30"
agent-memory-store search "what timezone does the user use"
```

## Why

Most agent frameworks give you a context window and, at best, a vector store bolted on as "memory." That leaves every application reinventing the same three hard problems: deciding *what's worth remembering and for how long* (importance and decay), *retrieving the right memory at the right moment* (not just the most similar one), and *keeping memory from growing without bound* (consolidating raw events into durable knowledge instead of hoarding every turn forever). agent-memory-store is a small, focused library that solves those three problems directly, so an agent's memory behaves less like a growing log file and more like an actual memory system.

## Architecture

```
                    ┌─────────────────────────────┐
                    │         MemoryStore          │
                    │  (src/agent_memory_store)    │
                    └──────────────┬───────────────┘
                                   │
        ┌───────────────┬─────────┼─────────┬────────────────┐
        │               │         │         │                │
        ▼               ▼         ▼         ▼                ▼
 ┌─────────────┐ ┌────────────┐ ┌──────┐ ┌───────────┐ ┌──────────────┐
 │ embeddings  │ │   decay    │ │ SQL  │ │consolidate│ │  CLI / HTTP  │
 │ (hashing    │ │(Ebbinghaus-│ │ ite  │ │ (cluster +│ │ (cli.py /    │
 │  vectorizer)│ │ style decay│ │store │ │  extractive│ │  server.py,  │
 │             │ │ + touch)   │ │      │ │  summary) │ │  optional)   │
 └─────────────┘ └────────────┘ └──────┘ └───────────┘ └──────────────┘
```

- **`embeddings.py`** — a deterministic, dependency-free hashing-trick vectorizer used to embed memory content and search queries for cosine-similarity ranking. Swappable for a real embedding model via any object exposing `embed(text) -> list[float]`.
- **`memory.py`** — the `MemoryItem` dataclass and `MemoryType` (`EPISODIC` / `SEMANTIC`) enum.
- **`decay.py`** — exponential, Ebbinghaus-inspired importance decay: memories fade based on time since last access, and access reinforces (slows) future decay.
- **`store.py`** — the SQLite-backed `MemoryStore`: `add`, `search`, `list`, `forget`, `decay_all`, `prune`, `consolidate`, `stats`.
- **`consolidation.py`** — greedy similarity clustering of episodic memories plus extractive summarization into a new semantic memory, mirroring how repeated related experiences turn into general knowledge.
- **`cli.py` / `server.py`** — a full CLI (`agent-memory-store ...`) and an optional FastAPI HTTP API (`pip install agent-memory-store[server]`) for language-agnostic agent stacks.

## Usage examples

**Retrieval-augmented ranking.** Search blends embedding similarity, decayed importance, and recency so an agent gets the *right* memory, not just the closest one:

```python
results = memory.search(
    "does the user want technical detail?",
    k=3,
    similarity_weight=0.6,
    importance_weight=0.3,
    recency_weight=0.1,
)
```

**Decay and pruning**, run periodically (e.g. from a scheduled job or after each agent session):

```python
memory.decay_all()          # recompute importance for every memory
memory.prune(threshold=0.05)  # archive memories that have effectively been "forgotten"
```

**Consolidation**, turning repeated episodic memories into one semantic fact:

```python
new_semantic_memories = memory.consolidate(similarity_threshold=0.75, min_cluster_size=3)
```

**HTTP API** (optional):

```bash
pip install agent-memory-store[server]
agent-memory-store serve --port 8000
curl -X POST localhost:8000/memories -d '{"content": "user is on the free tier"}'
curl -X POST localhost:8000/search -d '{"query": "what plan is the user on?"}'
```

**Docker:**

```bash
docker build -t agent-memory-store .
docker run --rm -p 8000:8000 -v $(pwd)/data:/data agent-memory-store
```

## Limitations

- The default hashing-trick vectorizer captures lexical/topical overlap well but is not a semantic embedding model — swap in a real embedding API via the `vectorizer` argument for higher-quality retrieval on paraphrase-heavy content.
- `MemoryStore` is SQLite-backed and designed for a single agent's working memory (thousands to low millions of items), not as a distributed, multi-tenant vector database.
- Consolidation's summarizer is extractive (concatenate + dedupe + truncate) to keep the core package dependency-free; plug in an LLM-backed summarizer for higher-quality semantic distillation.
- `MemoryStore` uses a single SQLite connection with `check_same_thread=False`; heavy concurrent write workloads should front it with a queue or move to a server-based backend.

## Development

```bash
pip install -e ".[dev,server]"
pytest -v
ruff check src tests
ruff format src tests
```

## License

MIT — see [LICENSE](LICENSE).
