from __future__ import annotations

"""Unified Cognitive State Provider

Combines embodied (digital body), enhanced (behavioral/calibration), and basic facets
into a single coherent snapshot.
"""
from typing import Any


def get_unified_cognitive_state_snapshot() -> dict[str, Any]:
    # Import locally to avoid heavy imports at module load time
    _embodied: Any = None
    _enhanced: Any = None
    _load_hist: Any = None
    _basic: Any = None

    try:
        from kagami.core.cognition.embodied import get_embodied_cognitive_state

        _embodied = get_embodied_cognitive_state
    except Exception:
        pass

    try:
        from kagami.core.cognition.state_enhanced import (
            get_enhanced_cognitive_state_snapshot,
            load_behavioral_history,
        )

        _enhanced = get_enhanced_cognitive_state_snapshot
        _load_hist = load_behavioral_history
    except Exception:
        pass

    try:
        from kagami.core.cognition.state import get_cognitive_state_snapshot

        _basic = get_cognitive_state_snapshot
    except Exception:
        pass

    # Gather components
    basic = _basic() if _basic else {"facets": {}, "rationale": {}}
    if _load_hist:
        try:
            _load_hist()
        except Exception:
            pass
    enhanced = _enhanced() if _enhanced else {"facets": {}, "rationale": {}}
    embodied = _embodied() if _embodied else {"facets": {}, "rationale": {}}

    # Merge facets: prefer embodied for C1, C2, C8; enhanced for C4, C7, C9; fallback to basic
    facets: dict[str, float] = {}
    for key in {"C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9", "C10"}:
        if key in ("C1", "C2", "C8"):
            val = (embodied.get("facets", {}) or {}).get(key)
            if val is None:
                val = (enhanced.get("facets", {}) or {}).get(key)
        elif key in ("C4", "C7", "C9"):
            val = (enhanced.get("facets", {}) or {}).get(key)
            if val is None:
                val = (embodied.get("facets", {}) or {}).get(key)
        else:
            # C3, C5, C6, C10
            val = (embodied.get("facets", {}) or {}).get(key)
            if val is None:
                val = (enhanced.get("facets", {}) or {}).get(key)
        if val is None:
            val = (basic.get("facets", {}) or {}).get(key, 0.0)
        facets[key] = float(val)

    # Build rationale summary
    rationale: dict[str, str] = {}
    for key in facets:
        src = "embodied" if key in ("C1", "C2", "C8", "C3", "C6", "C10") else "enhanced"
        rationale[key] = f"Unified from {src} provider"

    total = sum(facets.values())
    percentage = total / 50.0 * 100.0

    return {
        "version": "u1",
        "mode": "unified",
        "facets": facets,
        "rationale": rationale,
        "sources": {
            "embodied": bool(_embodied),
            "enhanced": bool(_enhanced),
            "basic": bool(_basic),
        },
        "total_score": total,
        "percentage": percentage,
    }


__all__ = ["get_unified_cognitive_state_snapshot"]
