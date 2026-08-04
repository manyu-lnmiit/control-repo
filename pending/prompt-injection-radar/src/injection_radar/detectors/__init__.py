"""Built-in detectors. Import from here for the default detector set."""

from .base import Detector
from .delimiter_spoofing import DelimiterSpoofingDetector
from .encoding_tricks import EncodingTricksDetector
from .exfiltration import ExfiltrationDetector
from .instruction_override import InstructionOverrideDetector

DEFAULT_DETECTORS: list[Detector] = [
    InstructionOverrideDetector(),
    DelimiterSpoofingDetector(),
    EncodingTricksDetector(),
    ExfiltrationDetector(),
]

__all__ = [
    "Detector",
    "InstructionOverrideDetector",
    "DelimiterSpoofingDetector",
    "EncodingTricksDetector",
    "ExfiltrationDetector",
    "DEFAULT_DETECTORS",
]
