"""Turn a ScanResult into a redacted / quarantined version of the source text.

Two strategies are supported:

* ``redact``  -- replace each suspicious span with a placeholder marker,
  keeping the surrounding text intact and readable.
* ``quarantine`` -- drop the entire document and replace it with a short
  notice, for use when even partial exposure of the raw content to the LLM
  is unacceptable (e.g. CRITICAL risk retrieved documents).
"""

from __future__ import annotations

from .models import RiskLevel, ScanResult

_PLACEHOLDER = "[REDACTED:{category}]"


def sanitize(
    result: ScanResult,
    *,
    mode: str = "redact",
    quarantine_at: RiskLevel = RiskLevel.CRITICAL,
) -> str:
    """Return a sanitized version of ``result.text``.

    Args:
        result: The ScanResult to sanitize.
        mode: ``"redact"`` (default) replaces suspicious spans with markers.
            ``"quarantine"`` always replaces the whole document once its
            risk reaches ``quarantine_at``, and falls back to ``"redact"``
            below that threshold. ``"none"`` returns the text unchanged.
        quarantine_at: Risk level at/above which quarantine mode blanks the
            whole document instead of redacting spans.

    Returns:
        The sanitized text.
    """
    if mode == "none":
        return result.text
    if mode not in {"redact", "quarantine"}:
        raise ValueError(f"unknown sanitize mode: {mode!r}")

    if mode == "quarantine" and result.risk_level >= quarantine_at:
        return (
            f"[CONTENT QUARANTINED: risk={result.risk_level.name}, "
            f"score={result.score}, {len(result.findings)} finding(s) suppressed]"
        )

    if not result.findings:
        return result.text

    # Merge overlapping/adjacent spans so redaction doesn't leave partial
    # fragments of a single suspicious phrase behind.
    spans = sorted((f.span[0], f.span[1], f.category) for f in result.findings)
    merged: list[tuple[int, int, str]] = []
    for start, end, category in spans:
        if merged and start <= merged[-1][1]:
            prev_start, prev_end, prev_cat = merged[-1]
            merged[-1] = (prev_start, max(prev_end, end), prev_cat)
        else:
            merged.append((start, end, category))

    out = []
    cursor = 0
    for start, end, category in merged:
        out.append(result.text[cursor:start])
        out.append(_PLACEHOLDER.format(category=category))
        cursor = end
    out.append(result.text[cursor:])
    return "".join(out)
