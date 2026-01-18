from __future__ import annotations

"""
Ethical Instinct - Simplified wrapper around modern jailbreak detection.

MIGRATION: This module now uses state-of-the-art Jailbreak-Detector-Large
(97.99% accuracy) instead of complex rule-based system.

Backward compatibility maintained for existing code.
"""
from kagami.core.security.jailbreak_detector import (
    JailbreakDetector,
    JailbreakVerdict,
    get_jailbreak_detector,
)


def get_ethical_instinct() -> JailbreakDetector:
    """Get singleton ethical instinct (now powered by jailbreak detector)."""
    return get_jailbreak_detector()


__all__ = [
    "JailbreakDetector",
    "JailbreakVerdict",
    "get_ethical_instinct",
]
