from __future__ import annotations

"""Quality Space utilities shared across modules.

Centralize generation of compact quality signatures and basic similarity.
"""
import hashlib
import time
from typing import Any


def generate_quality_signature(components: dict[str, Any]) -> str:
    parts: list[str] = []
    # Bounded, predictable keys only
    for key in (
        "emotion",
        "depth",
        "purpose",
        "complexity",
        "novelty",
        "risk_level",
        "confidence",
    ):
        v = components.get(key)
        parts.append(str(v) if v is not None else "")
    # Add a coarse time salt to avoid collisions in rapid succession
    parts.append(str(int(time.time() * 1000)))
    sig = hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]
    return f"qualia-{sig}"


def jaccard_similarity(s1: str, s2: str) -> float:
    if s1 == s2:
        return 1.0
    a = set(s1.lower().split())
    b = set(s2.lower().split())
    if not a or not b:
        return 0.0
    inter = a & b
    union = a | b
    return len(inter) / len(union) if union else 0.0


_LAST_SIG: str | None = None


def observe_quality_drift(signature: str) -> None:
    """Update QUALITY_SPACE_DRIFT gauge using Jaccard distance from last signature."""
    global _LAST_SIG
    try:
        if _LAST_SIG is not None and isinstance(signature, str):
            sim = jaccard_similarity(_LAST_SIG, signature)
            # Drift computed for monitoring (metric removed Dec 2025)
            _ = max(0.0, min(1.0, 1.0 - sim))
        _LAST_SIG = signature
    except Exception:
        _LAST_SIG = signature
