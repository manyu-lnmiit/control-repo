"""Task and TaskSuite definitions, plus loaders for YAML/JSON task files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator


class Task(BaseModel):
    """A single evaluation task to run against an agent.

    Attributes:
        id: Stable, unique identifier for the task (used for regression tracking).
        prompt: The input handed to the agent under test.
        scorer: Name of the scorer to use (e.g. "exact_match", "contains", "regex",
            "numeric_tolerance"). Must be registered in ``agent_eval_harness.scorers.REGISTRY``.
        expected: The reference value the scorer checks the agent's output against.
        scorer_kwargs: Extra keyword arguments forwarded to the scorer constructor.
        tags: Free-form labels for grouping/filtering tasks (e.g. "math", "reasoning").
        timeout_s: Optional wall-clock budget for the agent call, in seconds.
        weight: Relative importance of this task when computing a suite's aggregate score.
    """

    id: str
    prompt: str
    scorer: str = "exact_match"
    expected: Any = None
    scorer_kwargs: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    timeout_s: float | None = None
    weight: float = 1.0

    @field_validator("id")
    @classmethod
    def _id_not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Task.id must be a non-empty string")
        return v

    @field_validator("weight")
    @classmethod
    def _weight_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Task.weight must be > 0")
        return v


class TaskSuite(BaseModel):
    """An ordered collection of tasks, plus suite-level metadata."""

    name: str
    description: str = ""
    tasks: list[Task] = Field(default_factory=list)

    @field_validator("tasks")
    @classmethod
    def _unique_ids(cls, tasks: list[Task]) -> list[Task]:
        seen: set[str] = set()
        for t in tasks:
            if t.id in seen:
                raise ValueError(f"Duplicate task id in suite: {t.id!r}")
            seen.add(t.id)
        return tasks

    def filter_by_tag(self, tag: str) -> TaskSuite:
        """Return a copy of this suite containing only tasks that carry ``tag``."""
        return self.model_copy(update={"tasks": [t for t in self.tasks if tag in t.tags]})

    def __len__(self) -> int:
        return len(self.tasks)


def load_suite(path: str | Path) -> TaskSuite:
    """Load a :class:`TaskSuite` from a YAML or JSON file.

    Args:
        path: Path to a ``.yaml``, ``.yml``, or ``.json`` file describing the suite.

    Returns:
        The parsed and validated :class:`TaskSuite`.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        ValueError: If the file extension is unsupported or the content fails validation.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Task suite file not found: {p}")

    text = p.read_text(encoding="utf-8")
    if p.suffix in (".yaml", ".yml"):
        data = yaml.safe_load(text)
    elif p.suffix == ".json":
        data = json.loads(text)
    else:
        raise ValueError(f"Unsupported task suite extension: {p.suffix!r} (use .yaml/.yml/.json)")

    if not isinstance(data, dict):
        raise TypeError(f"Task suite file must contain a mapping at the top level: {p}")

    return TaskSuite.model_validate(data)
