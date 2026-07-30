"""SQLite-backed, git-like version store for LLM prompt templates.

Every ``commit`` creates a new immutable version. Nothing is ever mutated
in place, so ``diff`` and ``rollback`` are always available across the
full history of a prompt.
"""

from __future__ import annotations

import difflib
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from prompt_registry.models import PromptVersion, RenderResult
from prompt_registry.template import extract_variables, render_template

_SCHEMA = """
CREATE TABLE IF NOT EXISTS versions (
    name TEXT NOT NULL,
    version INTEGER NOT NULL,
    body TEXT NOT NULL,
    message TEXT NOT NULL DEFAULT '',
    tags TEXT NOT NULL DEFAULT '[]',
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    parent_version INTEGER,
    PRIMARY KEY (name, version)
);

CREATE INDEX IF NOT EXISTS idx_versions_name ON versions(name);
"""


class PromptNotFoundError(KeyError):
    """Raised when a prompt name has no committed versions."""


class VersionNotFoundError(KeyError):
    """Raised when a specific (name, version) pair does not exist."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class PromptRegistry:
    """A local, file-backed registry of versioned prompt templates.

    Example:
        >>> reg = PromptRegistry(":memory:")
        >>> reg.commit("greeting", "Hello, {{name}}!", message="initial")
        PromptVersion(name='greeting', version=1, ...)
        >>> reg.render("greeting", {"name": "Ada"}).text
        'Hello, Ada!'
    """

    def __init__(self, path: str | Path = "prompt_registry.db"):
        self.path = str(path)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        with self._conn:
            self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> PromptRegistry:
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------
    def commit(
        self,
        name: str,
        body: str,
        message: str = "",
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> PromptVersion:
        """Create and store a new immutable version of ``name``.

        The new version number is always ``latest + 1`` (or 1 if this is
        the first commit for ``name``).
        """
        with closing(self._conn.cursor()) as cur:
            cur.execute(
                "SELECT MAX(version) AS v FROM versions WHERE name = ?", (name,)
            )
            row = cur.fetchone()
            parent = row["v"]
            new_version = (parent or 0) + 1
            created_at = _utcnow()
            tags = tags or []
            metadata = metadata or {}
            cur.execute(
                """INSERT INTO versions
                   (name, version, body, message, tags, metadata, created_at, parent_version)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    name,
                    new_version,
                    body,
                    message,
                    json.dumps(tags),
                    json.dumps(metadata),
                    created_at,
                    parent,
                ),
            )
            self._conn.commit()
        return PromptVersion(
            name=name,
            version=new_version,
            body=body,
            message=message,
            tags=tags,
            metadata=metadata,
            created_at=created_at,
            parent_version=parent,
        )

    def tag(self, name: str, version: int, tag: str) -> PromptVersion:
        """Attach a label (e.g. "prod") to a specific version.

        A tag is moved (not duplicated) if it already exists on another
        version of the same prompt, mirroring how deployment tags like
        "prod" behave in practice.
        """
        target = self.get(name, version)  # raises if missing
        with closing(self._conn.cursor()) as cur:
            cur.execute("SELECT version, tags FROM versions WHERE name = ?", (name,))
            for r in cur.fetchall():
                existing_tags = json.loads(r["tags"])
                if tag in existing_tags and r["version"] != version:
                    existing_tags.remove(tag)
                    cur.execute(
                        "UPDATE versions SET tags = ? WHERE name = ? AND version = ?",
                        (json.dumps(existing_tags), name, r["version"]),
                    )
            cur.execute(
                "SELECT tags FROM versions WHERE name = ? AND version = ?",
                (name, version),
            )
            current_tags = json.loads(cur.fetchone()["tags"])
            if tag not in current_tags:
                current_tags.append(tag)
            cur.execute(
                "UPDATE versions SET tags = ? WHERE name = ? AND version = ?",
                (json.dumps(current_tags), name, version),
            )
            self._conn.commit()
        return PromptVersion(
            name=target.name,
            version=target.version,
            body=target.body,
            message=target.message,
            tags=current_tags,
            metadata=target.metadata,
            created_at=target.created_at,
            parent_version=target.parent_version,
        )

    def rollback(self, name: str, to_version: int, message: str | None = None) -> PromptVersion:
        """Create a *new* version whose body matches ``to_version``.

        Rollback never deletes history -- it commits a fresh version on
        top of the log, exactly like ``git revert``.
        """
        target = self.get(name, to_version)
        return self.commit(
            name,
            target.body,
            message=message or f"rollback to v{to_version}",
            metadata=dict(target.metadata),
        )

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------
    def _row_to_version(self, row: sqlite3.Row) -> PromptVersion:
        return PromptVersion(
            name=row["name"],
            version=row["version"],
            body=row["body"],
            message=row["message"],
            tags=json.loads(row["tags"]),
            metadata=json.loads(row["metadata"]),
            created_at=row["created_at"],
            parent_version=row["parent_version"],
        )

    def get(self, name: str, version: int | None = None) -> PromptVersion:
        """Fetch a specific version, or the latest committed version if
        ``version`` is omitted."""
        with closing(self._conn.cursor()) as cur:
            if version is None:
                cur.execute(
                    "SELECT * FROM versions WHERE name = ? ORDER BY version DESC LIMIT 1",
                    (name,),
                )
            else:
                cur.execute(
                    "SELECT * FROM versions WHERE name = ? AND version = ?",
                    (name, version),
                )
            row = cur.fetchone()
        if row is None:
            if version is None:
                raise PromptNotFoundError(f"No versions found for prompt {name!r}")
            raise VersionNotFoundError(f"{name!r} has no version {version}")
        return self._row_to_version(row)

    def get_by_tag(self, name: str, tag: str) -> PromptVersion:
        """Fetch whichever version of ``name`` currently carries ``tag``."""
        for pv in self.history(name):
            if tag in pv.tags:
                return pv
        raise VersionNotFoundError(f"No version of {name!r} is tagged {tag!r}")

    def history(self, name: str) -> list[PromptVersion]:
        """Return all committed versions of ``name``, oldest first."""
        with closing(self._conn.cursor()) as cur:
            cur.execute(
                "SELECT * FROM versions WHERE name = ? ORDER BY version ASC", (name,)
            )
            rows = cur.fetchall()
        if not rows:
            raise PromptNotFoundError(f"No versions found for prompt {name!r}")
        return [self._row_to_version(r) for r in rows]

    def list_names(self) -> list[str]:
        """Return every distinct prompt name currently tracked."""
        with closing(self._conn.cursor()) as cur:
            cur.execute("SELECT DISTINCT name FROM versions ORDER BY name ASC")
            return [r["name"] for r in cur.fetchall()]

    def diff(self, name: str, version_a: int, version_b: int) -> str:
        """Return a unified diff between two versions of the same prompt."""
        a = self.get(name, version_a)
        b = self.get(name, version_b)
        diff_lines = difflib.unified_diff(
            a.body.splitlines(keepends=True),
            b.body.splitlines(keepends=True),
            fromfile=f"{name}@v{version_a}",
            tofile=f"{name}@v{version_b}",
        )
        return "".join(diff_lines)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def render(
        self,
        name: str,
        variables: dict[str, Any] | None = None,
        version: int | None = None,
        tag: str | None = None,
    ) -> RenderResult:
        """Render a prompt's template body with the given variables.

        Exactly one of ``version``/``tag`` should be supplied (or
        neither, to use the latest committed version).
        """
        if version is not None and tag is not None:
            raise ValueError("Pass at most one of version= or tag=, not both")
        if tag is not None:
            pv = self.get_by_tag(name, tag)
        else:
            pv = self.get(name, version)
        variables = variables or {}
        text = render_template(pv.body, variables)
        return RenderResult(
            text=text,
            name=pv.name,
            version=pv.version,
            variables_used=extract_variables(pv.body),
        )
