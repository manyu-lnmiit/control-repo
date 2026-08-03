"""Format parsers that normalize provider-native tool definitions into
:class:`toolschema_lint.models.ToolSchema` instances.

Supported formats:

* ``openai``    -- OpenAI / Chat Completions & Responses API ``tools`` array
* ``anthropic`` -- Anthropic Messages API ``tools`` array
* ``mcp``       -- Model Context Protocol ``tools/list`` result shape

Use :func:`detect_format` to auto-detect the format of an arbitrary JSON
document, or :func:`parse` to parse with a known format name.
"""

from __future__ import annotations

from typing import Any

from toolschema_lint.models import ToolSchema
from toolschema_lint.parsers import anthropic, mcp, openai

_PARSERS = {
    "openai": openai.parse,
    "anthropic": anthropic.parse,
    "mcp": mcp.parse,
}

SUPPORTED_FORMATS = tuple(_PARSERS.keys())


def parse(document: Any, fmt: str) -> list[ToolSchema]:
    """Parse ``document`` (already-loaded JSON) using the named format."""
    if fmt not in _PARSERS:
        raise ValueError(
            f"Unknown format {fmt!r}; supported formats: {', '.join(SUPPORTED_FORMATS)}"
        )
    return _PARSERS[fmt](document)


def detect_format(document: Any) -> str:
    """Best-effort auto-detection of a tool-schema document's format.

    Raises ``ValueError`` if the format cannot be confidently determined,
    so callers can fall back to an explicit ``--format`` flag.
    """
    tools = _extract_candidate_list(document)
    if not tools:
        raise ValueError("Could not find a list of tool definitions in the document")

    sample = tools[0]
    if not isinstance(sample, dict):
        raise ValueError("Tool entries must be JSON objects")

    if sample.get("type") == "function" and isinstance(sample.get("function"), dict):
        return "openai"
    if "input_schema" in sample:
        return "anthropic"
    if "inputSchema" in sample:
        return "mcp"
    # OpenAI's older/flat "functions" shape and the responses API
    # sometimes send a bare {name, description, parameters} object.
    if "parameters" in sample and "name" in sample:
        return "openai"

    raise ValueError(
        "Could not auto-detect schema format; pass --format explicitly "
        f"(supported: {', '.join(SUPPORTED_FORMATS)})"
    )


def _extract_candidate_list(document: Any) -> list[Any]:
    if isinstance(document, list):
        return document
    if isinstance(document, dict):
        for key in ("tools", "functions", "result"):
            value = document.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, dict) and isinstance(value.get("tools"), list):
                return value["tools"]
    return []
