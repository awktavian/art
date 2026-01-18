"""Data conversion and compilation utilities for ForgeMatrix."""

from __future__ import annotations

import time
from typing import Any

from kagami.forge.schema import (
    Character,
    PersonalityProfile,
    QualityMetrics,
)


def compile_character(components: dict[str, Any]) -> Character:
    """Compile character components into a final Character object."""
    char_data = components.get("character_data", {})
    if not isinstance(char_data, dict):
        char_data = {}

    metadata = {
        "behavior": components.get("behavior"),
        "voice": components.get("voice"),
        "narrative": components.get("narrative"),
        "generation_timestamp": time.time(),
    }

    name = char_data.get("name", "Generated Character")
    concept = char_data.get("concept", "")

    # Construct PersonalityProfile if behavior exists
    personality = None
    if components.get("behavior"):
        try:
            personality = PersonalityProfile(**components["behavior"])
        except Exception:
            pass

    return Character(name=name, concept=concept, metadata=metadata, personality=personality)


def calculate_quality_metrics(character: Character) -> QualityMetrics:
    """Calculate quality metrics for the generated character."""
    # Simplified scoring logic
    score = 0.8 if character.personality else 0.5
    return QualityMetrics(
        overall_score=score,
        completeness_score=score,
        consistency_score=score,
        creativity_score=0.7 if character.personality else 0.4,
        technical_quality_score=score,
        rigging_quality=0.0,
        mesh_quality=0.0,
        texture_quality=0.0,
    )
