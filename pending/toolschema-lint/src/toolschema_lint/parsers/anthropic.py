"""Parser for the Anthropic Messages API ``tools`` array shape::

    [
      {
        "name": "get_weather",
        "description": "...",
        "input_schema": {"type": "object", "properties": {...}, "required": [...]}
      }
    ]
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
        name = entry.get("name", f"<unnamed-{i}>")
        tools.append(
            build_tool(
                name=name,
                description=entry.get("description"),
                json_schema=entry.get("input_schema"),
                raw=entry,
                source_format="anthropic",
                source_index=i,
            )
        )
    return tools


def _entries(document: Any) -> list[Any]:
    if isinstance(document, list):
        return document
    if isinstance(document, dict) and isinstance(document.get("tools"), list):
        return document["tools"]
    return []
