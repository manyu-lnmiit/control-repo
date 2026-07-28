# llm-semantic-cache

[![CI](https://github.com/manyu-lnmiit/llm-semantic-cache/actions/workflows/ci.yml/badge.svg)](https://github.com/manyu-lnmiit/llm-semantic-cache/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)

**llm-semantic-cache** is a drop-in caching layer for LLM and agent tool calls that matches on *meaning*, not exact strings. Agent loops, RAG pipelines, and chat features routinely re-ask the same underlying question with different wording — a plain `dict` or Redis cache keyed on the literal prompt misses every one of those near-duplicates. This library embeds each prompt with a pluggable, dependency-free-by-default embedder, stores it in a local SQLite vector store, and returns a cached response whenever a new prompt is similar enough — cutting redundant LLM spend and latency without touching your model-calling code beyond one decorator.

## Quickstart

```bash
pip install llm-semantic-cache
```

```python
from semantic_cache import SemanticCache, cached_llm_call

cache = SemanticCache(path="cache.db", threshold=0.90)

@cached_llm_call(cache, cost_estimate=0.01)
def ask_llm(prompt: str) -> str:
    return real_llm_client.complete(prompt)  # only runs on a cache miss

ask_llm(prompt="What is the capital of France?")   # miss -> calls the LLM, caches "Paris"
ask_llm(prompt="what's the capital of france?")    # hit  -> returns "Paris" instantly, no API call
```

Or inspect a running cache from the shell:

```bash
semcache stats --path cache.db
```

## Why this exists

LLM API calls are the single biggest cost and latency driver in most agent systems. Exact-match caches only help with literal repeats, but real traffic is full of paraphrases: "what's the weather in Austin" vs. "weather in Austin, TX?", or a tool-calling agent re-deriving the same sub-query across independent runs. `llm-semantic-cache` closes that gap by caching on embedding similarity instead of string equality, giving you a meaningful hit rate on real-world prompt distributions with a two-line integration.

## Architecture

```
                 ┌────────────────────┐
   prompt   ───▶ │  EmbeddingBackend   │  (HashingEmbedder by default,
                 │  .embed(text)       │   or bring your own: OpenAI, etc.)
                 └─────────┬───────────┘
                           │ vector
                           ▼
                 ┌────────────────────┐
                 │   VectorStore       │  SQLite-backed; cosine similarity
                 │  (SQLite, per-ns)   │  linear scan; TTL expiry; LRU
                 └─────────┬───────────┘  eviction on max_entries
                           │
        similarity ≥ threshold?
              │yes              │no
              ▼                 ▼
       return cached      call wrapped fn,
       response (HIT)     cache result (MISS)
```

- **`EmbeddingBackend`** — a small protocol (`embed`, `dimensions`). The bundled `HashingEmbedder` is a deterministic bag-of-words hashing vectorizer: zero dependencies, zero network calls, and good enough to catch paraphrased near-duplicates. Swap in `OpenAIEmbedder` (optional `openai` extra) for higher-fidelity semantic matching in production.
- **`VectorStore`** — a SQLite table per cache instance. Similarity search is a linear cosine-similarity scan, which is the right tradeoff for per-process/per-agent caches (thousands–low tens of thousands of entries); swap in a dedicated vector index behind the same interface if you outgrow it.
- **`SemanticCache`** — the public API: `get`, `set`, `stats`, `clear`, `purge_expired`, namespacing, per-entry TTL, and cost-saved accounting.
- **`cached_llm_call`** — a decorator that wraps any prompt-taking function so cache lookups are transparent to callers.

## Usage examples

### Namespaces (isolate caches per model / tenant / agent)

```python
cache.set("summarize this doc", "...", namespace="gpt-4o")
cache.get("summarize this doc", namespace="claude-sonnet")  # miss — different namespace
```

### TTL and cost tracking

```python
cache.set("today's top HN post", "...", ttl_seconds=3600, cost_estimate=0.015)
cache.purge_expired()          # drop stale entries
cache.stats()                  # {"entries": ..., "total_hits": ..., "estimated_cost_saved": ...}
```

### Custom threshold and embedder

```python
from semantic_cache import SemanticCache, HashingEmbedder

cache = SemanticCache(
    path="cache.db",
    threshold=0.88,                       # 0.0-1.0 cosine similarity cutoff
    embedder=HashingEmbedder(dimensions=512),
    max_entries=50_000,
)
```

### CLI

```bash
semcache stats --path cache.db                 # entries, hits, estimated $ saved
semcache lookup --path cache.db "my prompt"     # dry-run a lookup
semcache purge --path cache.db                  # remove expired entries
semcache clear --path cache.db                  # wipe the cache
```

### Docker

```bash
docker build -t llm-semantic-cache .
docker run --rm -v "$(pwd)/data:/data" llm-semantic-cache stats --path /data/cache.db
```

## Running tests

```bash
pip install -e ".[dev]"
pytest --cov=semantic_cache
ruff check src tests
```

## Limitations

- The default `HashingEmbedder` is a bag-of-words vectorizer, not a neural embedding model — it catches vocabulary-overlap paraphrases well but will miss semantically identical prompts phrased with entirely different words. Use `OpenAIEmbedder` (or another custom `EmbeddingBackend`) for stronger recall in production.
- Similarity search is a linear scan per lookup, which is fine up to roughly tens of thousands of entries per namespace; beyond that, back the `VectorStore` interface with a proper ANN index (FAISS, pgvector, etc.).
- The cache trusts that a semantically similar *prompt* implies an acceptable *response* substitution — for prompts where a small wording change changes the correct answer (e.g. differing numeric parameters that hash similarly), tune `threshold` upward or scope more precisely with namespaces.
- No built-in encryption at rest; if cached prompts/responses are sensitive, encrypt the SQLite file or the fields before storage.

## License

MIT — see [LICENSE](LICENSE).
