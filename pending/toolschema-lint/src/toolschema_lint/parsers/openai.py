"""Parser for the OpenAI ``tools`` array shape used by both the Chat
Completions and Responses APIs::

    [
      {
        "type": "function",
        "function": {
          "name": "get_weather",
          "description": "...",
          "parameters": {"type": "object", "properties": {...}, "required": [...]}
        }
      }
    ]

Also tolerates the flatter legacy ``functions`` shape where ``name`` /
``description`` / ``parameters`` sit at the top level of each entry.
"""

from __future__ import annotations

from typing import Any

from toolschema_lint.models import ToolSchema
from toolschema_lint.parsers._common import build_tool


def parse(document: Any) -> list[ToolSchema]:
    entries = _entries(document)
    tools: list[ToolSchema] = []
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        body = entry.get("function") if isinstance(entry.get("function"), dict) else entry
        name = body.get("name", f"<unnamed-{i}>")
        tools.append(
            build_tool(
                name=name,
                description=body.get("description"),
                json_schema=body.get("parameters"),
                raw=entry,
                source_format="openai",
                source_index=i,
            )
        )
    return tools


def _entries(document: Any) -> list[Any]:
    if isinstance(document, list):
        return document
    if isinstance(document, dict):
        for key in ("tools", "functions"):
            if isinstance(document.get(key), list):
                return document[key]
    return []
