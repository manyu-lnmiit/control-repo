"""Optional ``.toolschemalintrc.json`` configuration.

Config lets a project disable specific rules or override a rule's default
severity, without touching code::

    {
      "disable": ["boolean-naming-convention"],
      "severity": {"missing-parameter-description": "error"},
      "similarity_threshold": 0.7
    }
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from toolschema_lint.models import Severity

DEFAULT_CONFIG_FILENAMES = (".toolschemalintrc.json", ".toolschemalintrc")


@dataclass
class Config:
    disabled_rules: set[str] = field(default_factory=set)
    severity_overrides: dict[str, Severity] = field(default_factory=dict)
    similarity_threshold: float = 0.6

    @classmethod
    def load(cls, path: str | Path | None) -> Config:
        if path is None:
            return cls()
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Config file not found: {p}")
        data = json.loads(p.read_text())
        return cls.from_dict(data)

    @classmethod
    def find_and_load(cls, start_dir: str | Path = ".") -> Config:
        start = Path(start_dir)
        for name in DEFAULT_CONFIG_FILENAMES:
            candidate = start / name
            if candidate.exists():
                return cls.load(candidate)
        return cls()

    @classmethod
    def from_dict(cls, data: dict) -> Config:
        severity_overrides = {
            rule_id: Severity(value) for rule_id, value in (data.get("severity") or {}).items()
        }
        return cls(
            disabled_rules=set(data.get("disable") or []),
            severity_overrides=severity_overrides,
            similarity_threshold=float(data.get("similarity_threshold", 0.6)),
        )
