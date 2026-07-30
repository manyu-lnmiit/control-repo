# prompt-registry

[![CI](https://github.com/manyu-lnmiit/prompt-registry/actions/workflows/ci.yml/badge.svg)](https://github.com/manyu-lnmiit/prompt-registry/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)

**prompt-registry** gives LLM prompt templates the same discipline you already give code: every change is an immutable, timestamped commit, `diff` shows exactly what changed between two versions, `tag` marks which version is live in each environment, `rollback` reverts a bad deploy in one call, and a deterministic A/B router lets you safely ramp a new prompt version to a slice of traffic — all backed by a single dependency-free SQLite file, with an optional FastAPI service for teams that want it over HTTP.

## Quickstart

```bash
pip install prompt-registry
```

```python
from prompt_registry import PromptRegistry

with PromptRegistry("prompts.db") as reg:
    reg.commit("support/greeting", "Hello, {{name}}! How can I help today?", message="initial version")
    reg.tag("support/greeting", version=1, tag="prod")

    result = reg.render("support/greeting", {"name": "Ada"}, tag="prod")
    print(result.text)  # -> "Hello, Ada! How can I help today?"
```

Or from the command line:

```bash
prompt-registry commit support/greeting --body "Hello, {{name}}!" -m "initial version"
prompt-registry render support/greeting --var name=Ada
```

## Why this exists

Teams shipping LLM features iterate on prompts constantly, but prompts usually live as loose strings scattered across the codebase, a config file, or worse, hardcoded inline. That makes it hard to answer basic questions: which version of this prompt is actually running in production right now? What exactly changed between last week's version and today's, and did that change cause the regression a user just reported? Can we safely roll out a new version to 10% of traffic before committing to it fully, and roll back instantly if it underperforms?

`prompt-registry` treats prompts as first-class versioned artifacts. Every `commit()` call creates a new immutable row; nothing is ever overwritten in place. That gives you a full audit trail for free, makes `diff` and `rollback` trivial, and makes "what's in prod" a simple tag lookup instead of a grep through git blame.

## Architecture

```
┌─────────────────────┐        ┌──────────────────────────┐
│  Your application    │        │   prompt-registry CLI     │
│  (Python import)      │        │  (commit/log/diff/tag/…)  │
└──────────┬───────────┘        └────────────┬─────────────┘
           │                                  │
           ▼                                  ▼
   ┌────────────────────────────────────────────────┐
   │              PromptRegistry (store.py)           │
   │  commit · get · history · diff · tag · rollback  │
   └───────────────────────┬──────────────────────────┘
                           │
                           ▼
                 ┌───────────────────┐
                 │  SQLite (1 file)   │
                 │  versions table    │
                 └───────────────────┘
                           ▲
                           │ optional HTTP layer
                 ┌───────────────────┐
                 │  FastAPI (api.py)  │◄── other services, non-Python callers
                 └───────────────────┘

  render(name, vars, version|tag) ──► template.py ──► rendered prompt text
  choose_variant(experiment, unit_id) ──► ab.py ──► deterministic A/B routing
```

Everything downstream of `PromptRegistry` -- the CLI, the optional HTTP API, and the A/B router -- is a thin layer over the same SQLite-backed store, so a team can start with pure Python imports and add the HTTP service later without touching how prompts are versioned.

## Usage examples

### Versioning and diffing

```python
from prompt_registry import PromptRegistry

reg = PromptRegistry("prompts.db")
reg.commit("support/greeting", "Hi {{name}}, how can I help?", message="v1")
reg.commit("support/greeting", "Hello {{name}}! What can I do for you today?", message="friendlier tone")

print(reg.diff("support/greeting", 1, 2))
for version in reg.history("support/greeting"):
    print(version.version, version.message, version.created_at)
```

### Tagging environments and rolling back

```python
reg.tag("support/greeting", version=2, tag="prod")     # ship v2
# ...an hour later, v2 is causing issues...
reg.rollback("support/greeting", to_version=1)          # creates v3 = a copy of v1's body
reg.tag("support/greeting", version=3, tag="prod")      # prod now points at the safe body again
```

### A/B testing a new prompt version

```python
from prompt_registry import ExperimentConfig, Variant, choose_variant

experiment = ExperimentConfig(
    prompt_name="support/greeting",
    key="greeting-tone-test-2026-07",
    variants=[
        Variant(name="control", version=1, weight=90),
        Variant(name="treatment", version=2, weight=10),
    ],
)

variant = choose_variant(experiment, unit_id="user-1234")
result = reg.render("support/greeting", {"name": "Ada"}, version=variant.version)
```

Assignment is a stable hash of `(experiment.key, unit_id)`, so the same user always lands in the same variant for the life of the experiment, with no session state to manage.

### CLI reference

```bash
prompt-registry commit <name> --body "..." -m "message" [--tag prod]
prompt-registry log <name>
prompt-registry show <name> [--version N | --tag prod]
prompt-registry diff <name> <version_a> <version_b>
prompt-registry tag <name> <version> <tag>
prompt-registry rollback <name> <to_version>
prompt-registry render <name> [--version N | --tag prod] [--var key=value ...]
```

### HTTP API (optional)

```bash
pip install "prompt-registry[api]"
uvicorn prompt_registry.api:app --reload
```

```
POST /prompts/{name}/commits        { "body": "...", "message": "..." }
GET  /prompts/{name}                latest version
GET  /prompts/{name}/versions/{v}
GET  /prompts/{name}/history
POST /prompts/{name}/render         { "variables": {...}, "tag": "prod" }
```

### Docker

```bash
docker build -t prompt-registry .
docker run --rm -p 8000:8000 -v prompt-data:/data prompt-registry
```

## Limitations

The built-in template engine supports `{{variable}}` and `{{variable|default("fallback")}}` only -- there is no support for loops, conditionals, or filters beyond `default(...)`. If you need full Jinja2 semantics, render with your own templating engine and store the resulting text as the committed body instead. The SQLite store is single-writer friendly but not designed for high-concurrency multi-process writes; for a shared team deployment, put the FastAPI service in front of a single writer process, or swap the storage layer for Postgres (the `PromptRegistry` interface is small enough to reimplement against another backend). There is currently no built-in authentication on the HTTP API -- put it behind your own auth/reverse proxy before exposing it beyond a trusted network.
