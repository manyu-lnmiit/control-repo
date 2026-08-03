# toolschema-lint

[![CI](https://github.com/manyu-lnmiit/toolschema-lint/actions/workflows/ci.yml/badge.svg)](https://github.com/manyu-lnmiit/toolschema-lint/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)

**toolschema-lint** is a static analyzer for LLM tool/function-calling schemas. It reads the
`tools` array you hand to OpenAI, Anthropic, or an MCP server and flags the schema problems that
quietly make agents unreliable — missing descriptions, ambiguous naming, unconstrained enums,
type mismatches, and near-duplicate tools the model can't tell apart — before any of it ships to
production.

## Quickstart

```bash
pip install -e .
toolschema-lint validate examples/sample_tools.json
```

```
[ERROR  ] missing-tool-description     run: Tool has no description. An LLM cannot decide when to call this tool without one.
[WARNING] vague-tool-name              run: Tool name 'run' is too generic. Use a specific, action-oriented name such as 'search_flights' rather than 'run'.
[WARNING] missing-parameter-description run.flag: Parameter has no description.
[INFO   ] boolean-naming-convention    run.flag: Boolean parameter 'flag' doesn't read as a yes/no question; consider a prefix like is_/has_/should_.
[INFO   ] missing-enum-constraint      run.mode: Description suggests a fixed set of valid values; add an `enum` so invalid values are rejected before the call is made.

Checked 1 tool(s): 1 error(s), 2 warning(s), 2 info.
```

The command exits `1` because of the error-level finding — wire it into CI and a bad tool schema
fails the build the same way a bad unit test would.

## Why this exists

Function/tool calling puts the entire contract between your code and the model into one JSON
blob: a name, a description, and a parameter schema. There's no compiler, no IDE autocomplete, and
no type checker standing between that blob and a production agent deciding which tool to call and
what arguments to fill in. In practice, that contract rots the same way any other contract does:

- A tool ships with no description, or one so short ("todo", "handles requests") that the model
  is guessing.
- Two tools end up doing almost the same thing (`get_weather_report` vs. `fetch_weather_report`),
  and the agent calls the wrong one non-deterministically.
- A parameter's description says "must be either 'fast' or 'slow'" but there's no `enum`, so the
  model is free to hallucinate `"turbo"`.
- A `required` field references a parameter that was renamed or removed from `properties`, so
  every call the model makes is rejected at the API layer.

None of these are caught by JSON-schema validation, because the JSON is perfectly valid — the
problem is semantic, not structural. toolschema-lint is a rule engine purpose-built to catch this
class of bug, the same way ESLint or Ruff catch code smells that a compiler doesn't.

## Architecture

```
                 ┌────────────────────┐
   tools.json ──▶│  format parsers    │  openai / anthropic / mcp
                 │  (auto-detected)   │  -> normalized ToolSchema[]
                 └─────────┬──────────┘
                           │
                 ┌─────────▼──────────┐
                 │    rule engine     │  ToolRule (per tool)
                 │  (Linter.lint)     │  CorpusRule (cross-tool)
                 └─────────┬──────────┘
                           │
                 ┌─────────▼──────────┐
                 │   report formatter │  text / json / sarif
                 └────────────────────┘
```

Every provider format is normalized into one internal `ToolSchema` shape, so every rule is written
once and works identically across OpenAI, Anthropic, and MCP tool definitions. Rules fall into two
kinds:

- **`ToolRule`** — evaluated independently per tool (missing description, invalid type, ...).
- **`CorpusRule`** — evaluated across the whole tool set, because some problems only exist in
  relation to other tools (duplicate names, overlapping purpose via token-Jaccard similarity on
  name + description — no embeddings or network calls required).

## Installation

```bash
pip install -e ".[dev]"   # editable install with pytest + ruff for development
```

## Usage

### CLI

```bash
# Auto-detect format (openai / anthropic / mcp)
toolschema-lint validate tools.json

# Force a format explicitly
toolschema-lint validate tools.json --format anthropic

# Machine-readable output for downstream tooling
toolschema-lint validate tools.json --output json

# SARIF output for GitHub code scanning
toolschema-lint validate tools.json --output sarif > results.sarif

# Only fail the build on errors (default), warnings, info, or never
toolschema-lint validate tools.json --fail-on warning

# List every built-in rule and its default severity
toolschema-lint rules
```

### Configuration

Drop a `.toolschemalintrc.json` next to your schema file (or point `--config` at one) to disable
rules or override severities:

```json
{
  "disable": ["boolean-naming-convention"],
  "severity": { "missing-parameter-description": "error" },
  "similarity_threshold": 0.7
}
```

### Library

```python
import json
from toolschema_lint.parsers import parse, detect_format
from toolschema_lint.linter import Linter

document = json.loads(open("tools.json").read())
tools = parse(document, detect_format(document))
result = Linter().lint(tools)

for finding in result.sorted_findings():
    print(finding.format())

assert not result.has_errors
```

### Built-in rules

| Rule | Severity | Catches |
|---|---|---|
| `missing-tool-description` | error | Tool has no description at all |
| `thin-tool-description` | warning | Description present but too short/generic |
| `missing-parameter-description` | warning | Parameter undocumented |
| `vague-tool-name` | warning | Generic names like `run`, `do`, `handler` |
| `invalid-tool-name-format` | error | Name contains characters providers reject |
| `boolean-naming-convention` | info | Boolean param not named `is_*`/`has_*`/... |
| `required-parameter-not-defined` | error | `required` references an undefined property |
| `invalid-parameter-type` | error | `type` isn't a real JSON-schema type |
| `enum-value-type-mismatch` | error | An `enum` value's type contradicts `type` |
| `missing-enum-constraint` | info | Description implies fixed options but no `enum` |
| `unconstrained-object-parameter` | info | Object param with no nested `properties` |
| `duplicate-tool-name` | error | Same tool name defined more than once |
| `overlapping-tool-purpose` | warning | Two tools are near-duplicates in name/description |

## Limitations

- Duplicate/overlap detection uses token-Jaccard similarity, not embeddings — it catches
  near-identical wording but won't catch two tools that mean the same thing in very different
  words.
- Rules operate purely on the schema text; they can't verify that a tool's actual runtime
  behavior matches its description.
- No support (yet) for provider-specific extensions beyond the common JSON-schema subset (e.g.
  OpenAI's `strict` mode nuances).
