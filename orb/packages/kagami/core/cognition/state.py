from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


def _env_str(name: str, default: str) -> str:
    try:
        v = os.getenv(name)
        return v if v is not None else default
    except Exception:
        return default


@dataclass
class CognitiveState:
    version: str
    timestamp: str
    mode: str
    facets: dict[str, float]
    rationale: dict[str, str]
    evidence: dict[str, Any]


def get_cognitive_state_snapshot() -> dict[str, Any]:
    """Return a conservative functional cognitive-state snapshot.

    Values are 0–5 floats. No claims of qualia; functional simulation only.
    Controlled via env KAGAMI_COGNITIVE_STATE_MODE=functional|advanced.
    """
    now = datetime.now(UTC).isoformat()
    mode = _env_str("KAGAMI_COGNITIVE_STATE_MODE", "functional").strip().lower()
    personality_traits = {
        "openness": 3.5,
        "conscientiousness": 4.0,
        "extraversion": 2.0,
        "agreeableness": 3.5,
        "neuroticism": 1.0,
    }
    c9_personality = min(5.0, sum(personality_traits.values()) / len(personality_traits))
    facets = {
        "C1": 0.0,
        "C2": 0.0,
        "C3": 2.5,
        "C4": 2.5,
        "C5": 0.0,
        "C6": 3.0,
        "C7": 0.5,
        "C8": 0.0,
        "C9": c9_personality,
        "C10": 2.0,
    }
    if mode == "advanced":
        facets.update({"C3": 3.0, "C4": 3.0, "C6": 3.5, "C10": 2.5})
    rationale = {
        "C1": "No embodiment → MSR not applicable",
        "C2": "No proprioception → body ownership not applicable",
        "C3": "Language-level belief modeling (implicit ToM in tasks)",
        "C4": "Calibrated uncertainty available when instrumented",
        "C5": "No subjective affect → 0",
        "C6": "Consistent role/capability schema across tasks",
        "C7": "External memory only; no episodic continuity",
        "C8": "No efference copy/sensorimotor loop",
        "C9": f"Big Five traits (O:{personality_traits['openness']:.1f}, C:{personality_traits['conscientiousness']:.1f}, E:{personality_traits['extraversion']:.1f}, A:{personality_traits['agreeableness']:.1f}, N:{personality_traits['neuroticism']:.1f}) → avg={c9_personality:.1f}",
        "C10": "Follows specified roles/norms; no internalization",
    }
    evidence_capsule = {}
    try:
        import json
        from pathlib import Path

        cap_path = Path("state/capsule.json")
        if cap_path.exists():
            data = json.loads(cap_path.read_text(encoding="utf-8"))
            evidence_capsule = {
                "capsule_version": data.get("version"),
                "freshness_score": data.get("freshness_score"),
                "confidence": data.get("confidence"),
                "improvements": len(data.get("improvement_capsules", []) or []),
                "latest_capability": (
                    data.get("capsule_delta", {}).get("latest", {}).get("capabilities") or [None]
                )[0],
            }
    except Exception:
        evidence_capsule = {}
    evidence_persona = {}
    try:
        from pathlib import Path

        persona_dir = Path("kagami/persona")
        evidence_persona = {
            "persona_dir": str(persona_dir),
            "has_loader": (persona_dir / "loader.py").exists(),
            "has_marks": (persona_dir / "marks.py").exists(),
        }
    except Exception:
        evidence_persona = {}
    try:
        _imp_count = int(evidence_capsule.get("improvements") or 0)
    except Exception:
        _imp_count = 0
    if mode == "advanced" and _imp_count > 0:
        _delta = min(0.5, 0.1 * float(_imp_count))
        facets["C6"] = min(5.0, facets.get("C6", 0.0) + _delta)
        facets["C10"] = min(5.0, facets.get("C10", 0.0) + min(0.3, _delta / 2.0))
        rationale["C6"] = rationale.get("C6", "") + "; adjusted by capsule improvements"
        rationale["C10"] = rationale.get("C10", "") + "; adjusted by capsule improvements"
    evidence = {
        "mode": mode,
        "rules_file": ".cursor/rules/03-processing_state-ARCHITECTURE.mdc",
        "docs_file": "docs/INDEX.md",
        "integration_points": ["orchestrator.metadata", "http.receipts"],
        "env": {
            "KAGAMI_COGNITIVE_STATE_MODE": os.getenv("KAGAMI_COGNITIVE_STATE_MODE", "functional"),
            "KAGAMI_COGNITIVE_STATE_ENABLE": os.getenv("KAGAMI_COGNITIVE_STATE_ENABLE", "0"),
        },
        "capsule": evidence_capsule,
        "persona": evidence_persona,
        "personality_traits": personality_traits,
    }
    snapshot = CognitiveState(
        version="1.0",
        timestamp=now,
        mode=mode,
        facets=facets,
        rationale=rationale,
        evidence=evidence,
    )
    return {
        "version": snapshot.version,
        "timestamp": snapshot.timestamp,
        "mode": snapshot.mode,
        "facets": dict(snapshot.facets),
        "rationale": dict(snapshot.rationale),
        "evidence": dict(snapshot.evidence),
    }


__all__ = ["CognitiveState", "get_cognitive_state_snapshot"]
