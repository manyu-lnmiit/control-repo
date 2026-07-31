"""Append-only JSONL audit trail for sandboxed executions.

Every execution -- whether it ran, was blocked by policy, timed out, or hit
a resource limit -- is recorded as one JSON object per line. The submitted
code/command is never stored verbatim (to keep entries compact and avoid
bloating the log with large snippets); instead a sha256 hash is stored,
which still supports tamper-evidence checks and simple dedup/lookup by
hash.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

from agent_code_sandbox.core.limits import ResourceLimits
from agent_code_sandbox.core.result import ExecutionResult

#: Environment variable that overrides the default audit log location.
ENV_AUDIT_LOG_PATH = "AGENT_SANDBOX_AUDIT_LOG_PATH"

#: Default audit log path if no override is configured.
DEFAULT_AUDIT_LOG_PATH = Path.home() / ".agent_code_sandbox" / "audit.jsonl"


def default_audit_log_path() -> Path:
    """Resolve the audit log path, honoring the
    ``AGENT_SANDBOX_AUDIT_LOG_PATH`` environment variable override."""
    override = os.environ.get(ENV_AUDIT_LOG_PATH)
    if override:
        return Path(override)
    return DEFAULT_AUDIT_LOG_PATH


def hash_payload(payload: str) -> str:
    """Return the sha256 hex digest of ``payload`` (code or command
    text)."""
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class AuditEntry:
    """A single audit log record."""

    timestamp: float
    kind: str  # "python" | "shell"
    payload_sha256: str
    limits: dict[str, float | int | None]
    result: dict[str, object]

    def to_json_line(self) -> str:
        return json.dumps(
            {
                "timestamp": self.timestamp,
                "kind": self.kind,
                "payload_sha256": self.payload_sha256,
                "limits": self.limits,
                "result": self.result,
            },
            sort_keys=True,
        )

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> AuditEntry:
        return cls(
            timestamp=float(data["timestamp"]),  # type: ignore[arg-type]
            kind=str(data["kind"]),
            payload_sha256=str(data["payload_sha256"]),
            limits=data.get("limits", {}),  # type: ignore[arg-type]
            result=data.get("result", {}),  # type: ignore[arg-type]
        )


class AuditLog:
    """Reader/writer for the JSONL audit trail."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path is not None else default_audit_log_path()

    def record(
        self,
        kind: str,
        payload: str,
        limits: ResourceLimits,
        result: ExecutionResult,
    ) -> AuditEntry:
        """Append one entry summarizing an execution and return it."""
        entry = AuditEntry(
            timestamp=time.time(),
            kind=kind,
            payload_sha256=hash_payload(payload),
            limits=limits.as_dict(),
            result=result.to_dict(),
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(entry.to_json_line())
            f.write("\n")
        return entry

    def read_all(self) -> list[AuditEntry]:
        """Read every entry from the log, oldest first. Returns an empty
        list if the log file does not yet exist."""
        if not self.path.exists():
            return []
        entries: list[AuditEntry] = []
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                entries.append(AuditEntry.from_dict(data))
        return entries

    def last(
        self, n: int = 10, *, success: bool | None = None
    ) -> list[AuditEntry]:
        """Return the last ``n`` entries, most recent last, optionally
        filtered by ``result.success``.

        Args:
            n: Maximum number of entries to return.
            success: If not None, only include entries whose recorded
                result's ``success`` field matches this value.
        """
        entries = self.read_all()
        if success is not None:
            entries = [
                e for e in entries if bool(e.result.get("success")) == success
            ]
        return entries[-n:]
