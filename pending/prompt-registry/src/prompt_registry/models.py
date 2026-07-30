"""Core dataclasses shared across the prompt-registry package."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PromptVersion:
    """An immutable, committed version of a prompt template.

    Attributes:
        name: The prompt's logical name (e.g. "support/greeting").
        version: Monotonically increasing integer version number, starting at 1.
        body: The raw template body (uses ``{{variable}}`` placeholder syntax).
        message: A short human-readable commit message describing the change.
        tags: Arbitrary labels attached to this version (e.g. "prod", "staging").
        metadata: Free-form key/value metadata (model name, temperature, author, ...).
        created_at: ISO-8601 UTC timestamp string of when the version was committed.
        parent_version: The version number this was committed on top of, or None for v1.
    """

    name: str
    version: int
    body: str
    message: str
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    parent_version: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "body": self.body,
            "message": self.message,
            "tags": list(self.tags),
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
            "parent_version": self.parent_version,
        }


@dataclass(frozen=True)
class RenderResult:
    """The result of rendering a prompt template against a variable set."""

    text: str
    name: str
    version: int
    variables_used: list[str]
