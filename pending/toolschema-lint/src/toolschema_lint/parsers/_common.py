"""Shared helpers used by every format-specific parser."""

from __future__ import annotations

from typing import Any

from toolschema_lint.models import Parameter, ToolSchema


def build_tool(
    *,
    name: str,
    description: str | None,
    json_schema: dict[str, Any] | None,
    raw: dict[str, Any],
    source_format: str,
    source_index: int,
) -> ToolSchema:
    """Construct a ``ToolSchema`` from a name/description/JSON-schema triple.

    ``json_schema`` is the JSON-schema object found under ``parameters``
    (OpenAI), ``input_schema`` (Anthropic), or ``inputSchema`` (MCP) -- all
    three use the same JSON-schema object-with-properties shape.
    """
    json_schema = json_schema or {}
    properties = json_schema.get("properties") or {}
    required = set(json_schema.get("required") or [])

    parameters = tuple(
        Parameter(
            name=pname,
            schema=pschema if isinstance(pschema, dict) else {},
            required=pname in required,
        )
        for pname, pschema in properties.items()
    )

    return ToolSchema(
        name=name,
        description=description,
        parameters=parameters,
        raw=raw,
        source_format=source_format,
        source_index=source_index,
    )
