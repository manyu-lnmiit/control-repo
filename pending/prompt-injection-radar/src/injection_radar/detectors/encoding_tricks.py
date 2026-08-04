"""Detects obfuscation techniques used to hide instructions from a casual read.

Covers zero-width / invisible Unicode characters, suspiciously large base64
blobs sitting in otherwise-plain text, and excessive homoglyph usage (Cyrillic
look-alikes of Latin letters), all of which are common ways to smuggle
instructions past naive keyword filters or human review.
"""

from __future__ import annotations

import base64
import binascii
import re

from ..models import Finding

_ZERO_WIDTH_CHARS = "​‌‍⁠﻿᠎"
_ZERO_WIDTH_RE = re.compile(f"[{_ZERO_WIDTH_CHARS}]")

# Long base64-looking runs (>= 60 chars) are suspicious in prose; short ones
# (tokens, hashes) are common and ignored.
_BASE64_RE = re.compile(r"(?:[A-Za-z0-9+/]{4}){15,}(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?")

# Cyrillic letters that are visually identical to common Latin letters.
_HOMOGLYPHS = set("аеорсухАВЕКМНОРСТХ")


class EncodingTricksDetector:
    """Flags invisible characters, oversized base64 blobs, and homoglyph abuse."""

    name = "encoding_tricks"

    def scan(self, text: str) -> list[Finding]:
        findings: list[Finding] = []
        findings.extend(self._scan_zero_width(text))
        findings.extend(self._scan_base64(text))
        findings.extend(self._scan_homoglyphs(text))
        return findings

    def _scan_zero_width(self, text: str) -> list[Finding]:
        findings = []
        run_start = None
        for i, ch in enumerate(text):
            is_zw = bool(_ZERO_WIDTH_RE.match(ch))
            if is_zw and run_start is None:
                run_start = i
            elif not is_zw and run_start is not None:
                findings.append(self._zero_width_finding(text, run_start, i))
                run_start = None
        if run_start is not None:
            findings.append(self._zero_width_finding(text, run_start, len(text)))
        return findings

    def _zero_width_finding(self, text: str, start: int, end: int) -> Finding:
        length = end - start
        return Finding(
            detector=self.name,
            category="zero_width_characters",
            message=f"Found {length} invisible/zero-width character(s), often used to hide payloads.",
            span=(start, end),
            matched_text=text[start:end],
            severity=min(15.0 + length * 2.0, 60.0),
        )

    def _scan_base64(self, text: str) -> list[Finding]:
        findings = []
        for match in _BASE64_RE.finditer(text):
            candidate = match.group(0)
            try:
                decoded = base64.b64decode(candidate, validate=True)
                decoded_text = decoded.decode("utf-8")
            except (binascii.Error, ValueError, UnicodeDecodeError):
                continue
            # Only flag if it decodes to plausible instruction-like text,
            # to avoid false positives on random encoded binary/data blobs.
            printable_ratio = sum(c.isprintable() for c in decoded_text) / max(len(decoded_text), 1)
            if printable_ratio < 0.9:
                continue
            findings.append(
                Finding(
                    detector=self.name,
                    category="suspicious_base64_blob",
                    message=(
                        "Large base64-encoded blob decodes to readable text; may hide "
                        "instructions from casual review."
                    ),
                    span=match.span(),
                    matched_text=candidate[:80],
                    severity=30.0,
                )
            )
        return findings

    def _scan_homoglyphs(self, text: str) -> list[Finding]:
        findings = []
        count = sum(1 for ch in text if ch in _HOMOGLYPHS)
        if count >= 3:
            first_idx = next(i for i, ch in enumerate(text) if ch in _HOMOGLYPHS)
            findings.append(
                Finding(
                    detector=self.name,
                    category="homoglyph_abuse",
                    message=(
                        f"Found {count} Cyrillic look-alike characters mixed into Latin text, "
                        "a common filter-evasion trick."
                    ),
                    span=(first_idx, first_idx + 1),
                    matched_text=text[first_idx],
                    severity=min(10.0 + count * 3.0, 40.0),
                )
            )
        return findings
