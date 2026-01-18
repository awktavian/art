from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class AnimationQualityAssessor:
    """Quality assessment for animations."""

    def assess_quality(self, animation_data: dict[str, Any]) -> dict[str, float]:
        """Assess the quality of facial animation."""
        blendshapes = animation_data.get("blendshapes", {})

        if blendshapes:
            values = list(blendshapes.values())
            smoothness = 1.0 - np.std(values) if len(values) > 1 else 1.0
        else:
            smoothness = 0.0

        realism = 1.0
        for value in blendshapes.values():
            if value < 0.0 or value > 1.0:
                realism -= 0.1
        realism = max(0.0, realism)

        if blendshapes and len(blendshapes) > 0:
            distinct_values = len({round(v, 2) for v in blendshapes.values()})
            expression_clarity = min(distinct_values / len(blendshapes), 1.0)
        else:
            expression_clarity = 0.0

        overall_quality = (smoothness + realism + expression_clarity) / 3.0

        return {
            "overall_quality": overall_quality,
            "smoothness": smoothness,
            "realism": realism,
            "expression_clarity": expression_clarity,
        }
