"""injection_radar: detect and sanitize prompt-injection attempts before they reach an LLM.

Public API surface. Keep this module small and stable -- it's what
downstream code should import from.
"""

from .models import Finding, RiskLevel, ScanResult
from .sanitizer import sanitize
from .scanner import Scanner, default_scanner

__all__ = [
    "Finding",
    "RiskLevel",
    "ScanResult",
    "Scanner",
    "default_scanner",
    "sanitize",
]

__version__ = "0.1.0"
