"""Parser for the Model Context Protocol ``tools/list`` result shape::

    {
      "tools": [
        {
          "name": "get_weather",
          "description": "...",
          "inputSchema": {"type": "object", "properties": {...}, "required": [...]}
        }
      ]
    }

Also accepts a bare list of the same per-tool objects.
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
                json_schema=entry.get("inputSchema"),
                raw=entry,
                source_format="mcp",
                source_index=i,
            )
        )
    return tools


def _entries(document: Any) -> list[Any]:
    if isinstance(document, list):
        return document
    if isinstance(document, dict):
        if isinstance(document.get("tools"), list):
            return document["tools"]
        result = document.get("result")
        if isinstance(result, dict) and isinstance(result.get("tools"), list):
            return result["tools"]
    return []
