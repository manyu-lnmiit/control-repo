"""Optional FastAPI HTTP service wrapping the scanner, for use as a sidecar
in front of agent tool-calling / RAG pipelines.

Requires the ``api`` extra: ``pip install injection-radar[api]``.

Run with:
    uvicorn injection_radar.api:app --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

try:
    from fastapi import FastAPI
    from pydantic import BaseModel
except ImportError as exc:  # pragma: no cover - exercised only without the extra
    raise ImportError(
        "injection_radar.api requires the 'api' extra. Install with: pip install injection-radar[api]"
    ) from exc

from .models import RiskLevel
from .sanitizer import sanitize
from .scanner import default_scanner

app = FastAPI(
    title="injection-radar",
    description="Detects and sanitizes prompt-injection attempts in untrusted text.",
    version="0.1.0",
)

_scanner = default_scanner()


class ScanRequest(BaseModel):
    text: str
    sanitize_mode: str | None = None  # "redact" | "quarantine" | None


class ScanResponse(BaseModel):
    score: float
    risk_level: str
    is_suspicious: bool
    findings: list[dict]
    sanitized_text: str | None = None


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/scan", response_model=ScanResponse)
def scan(req: ScanRequest) -> ScanResponse:
    result = _scanner.scan(req.text)
    sanitized_text = None
    if req.sanitize_mode:
        sanitized_text = sanitize(result, mode=req.sanitize_mode)
    payload = result.to_dict()
    return ScanResponse(sanitized_text=sanitized_text, **payload)


@app.get("/risk-levels")
def risk_levels() -> list[str]:
    return [lvl.name for lvl in RiskLevel]
