"""Catastrophe Detection for Curriculum Phase Transitions.

CREATED: December 21, 2025

Extracted from UnifiedCurriculumScheduler to reduce god class complexity.
This module provides phase-specific catastrophe detection methods aligned
with Thom's catastrophe theory.

THEORETICAL FOUNDATION:
=======================
Each curriculum phase corresponds to an elementary catastrophe type:
- HIERARCHY → Fold (A₂): Simple bifurcation
- ROTATION → Cusp (A₃): Hysteresis and stability
- DYNAMICS → Swallowtail (A₄): Three-way bifurcation
- JOINT → Butterfly (A₅): Four-dimensional bifurcation
- GENERATION → Hyperbolic (D₄⁺): No transition (terminal phase)

DETECTION METHODS:
==================
Each catastrophe type has specific detection criteria:

1. Fold (A₂):
   - Gradient vanishes (reconstruction converges)
   - Recent change near zero

2. Cusp (A₃):
   - High stability (inverse coefficient of variation)
   - No oscillations over window

3. Swallowtail (A₄):
   - Alignment metric converges
   - Relational structure emerges

4. Butterfly (A₅):
   - High task complexity handling
   - Multi-dataset mixing capability

USAGE:
======
```python
from kagami.core.training.curriculum import CurriculumCatastropheDetector

detector = CurriculumCatastropheDetector(
    reconstruction_history=deque(maxlen=100),
    alignment_history=deque(maxlen=100),
    complexity_history=deque(maxlen=100),
)

# Detect phase-specific catastrophe
detected, reason = detector.detect_catastrophe(phase, loss_history, config)
```
"""

from __future__ import annotations

import logging
from collections import deque
from typing import Any

logger = logging.getLogger(__name__)


class CurriculumCatastropheDetector:
    """Catastrophe detection for curriculum phase transitions.

    Provides phase-specific detection methods for all catastrophe types:
    - Fold (A₂)
    - Cusp (A₃)
    - Swallowtail (A₄)
    - Butterfly (A₅)

    Each detection method uses mathematical criteria derived from
    catastrophe theory singularities.
    """

    def __init__(
        self,
        reconstruction_history: deque[float],
        alignment_history: deque[float],
        complexity_history: deque[float],
        loss_history: deque[float],
    ) -> None:
        """Initialize catastrophe detector with metric histories.

        Args:
            reconstruction_history: History of reconstruction losses
            alignment_history: History of alignment metrics
            complexity_history: History of task complexity metrics
            loss_history: History of overall losses
        """
        self._reconstruction_history = reconstruction_history
        self._alignment_history = alignment_history
        self._complexity_history = complexity_history
        self._loss_history = loss_history

    def detect_catastrophe(
        self,
        phase: int,  # CurriculumPhase enum value
        config: Any,  # PhaseConfig
    ) -> tuple[bool, str]:
        """Detect catastrophe type for current phase.

        Args:
            phase: Current curriculum phase (0-4)
            config: Phase configuration with thresholds

        Returns:
            (detected, reason)
        """
        # Phase 0: HIERARCHY → Fold
        if phase == 0:
            return self._detect_fold(config)
        # Phase 1: ROTATION → Cusp
        elif phase == 1:
            return self._detect_cusp()
        # Phase 2: DYNAMICS → Swallowtail
        elif phase == 2:
            return self._detect_swallowtail(config)
        # Phase 3: JOINT → Butterfly
        elif phase == 3:
            return self._detect_butterfly(config)
        # Phase 4: GENERATION → Terminal (no transition)
        else:
            return False, ""

    def _detect_fold(self, config: Any) -> tuple[bool, str]:
        """Detect fold catastrophe (A₂): simple bifurcation.

        Fold occurs when gradient vanishes (reconstruction converges).

        Mathematical condition:
        - ∂L/∂x ≈ 0 (gradient vanishes)
        - L < threshold (loss converged)

        Args:
            config: Phase configuration with loss_threshold

        Returns:
            (detected, reason)
        """
        if len(self._reconstruction_history) < 10:
            return False, ""

        window = min(10, len(self._reconstruction_history))
        recent = list(self._reconstruction_history)[-window:]
        avg_recon = sum(recent) / len(recent)

        if avg_recon < config.loss_threshold:
            # Verify gradient is small (change near zero)
            if len(recent) >= 2:
                recent_change = abs(recent[-1] - recent[-2])
                if recent_change < 0.01:
                    return True, f"fold_detected (recon={avg_recon:.4f})"

        return False, ""

    def _detect_cusp(self) -> tuple[bool, str]:
        """Detect cusp catastrophe (A₃): hysteresis and stability.

        Cusp shows stable dynamics without oscillations.

        Mathematical condition:
        - High stability: 1 / (1 + CV) > 0.9
        - CV = coefficient of variation (std/mean)
        - No oscillations over 50-step window

        Returns:
            (detected, reason)
        """
        if len(self._loss_history) < 50:
            return False, ""

        # Compute loss stability over window
        window = list(self._loss_history)[-50:]
        mean_loss = sum(window) / len(window)
        variance = sum((x - mean_loss) ** 2 for x in window) / len(window)
        std_dev = variance**0.5

        # Stability metric: inverse coefficient of variation
        if mean_loss > 1e-8:
            stability = 1.0 / (1.0 + std_dev / mean_loss)
        else:
            stability = 1.0

        # Cusp condition: high stability (no oscillations)
        if stability > 0.9:
            return True, f"cusp_detected (stability={stability:.4f})"

        return False, ""

    def _detect_swallowtail(self, config: Any) -> tuple[bool, str]:
        """Detect swallowtail catastrophe (A₄): three-way bifurcation.

        Swallowtail shows emergence of relational structure.

        Mathematical condition:
        - Alignment metric converges: A < 0.05
        - Fallback: Overall loss < threshold

        Args:
            config: Phase configuration with loss_threshold

        Returns:
            (detected, reason)
        """
        if len(self._alignment_history) < 10:
            # Fallback to loss threshold if no alignment metric
            if len(self._loss_history) >= 10:
                recent = list(self._loss_history)[-10:]
                avg_loss = sum(recent) / len(recent)
                if avg_loss < config.loss_threshold:
                    return True, f"swallowtail_detected (loss={avg_loss:.4f})"
            return False, ""

        window = min(10, len(self._alignment_history))
        recent = list(self._alignment_history)[-window:]
        avg_alignment = sum(recent) / len(recent)

        # Swallowtail condition: alignment converged
        if avg_alignment < 0.05:
            return True, f"swallowtail_detected (alignment={avg_alignment:.4f})"

        return False, ""

    def _detect_butterfly(self, config: Any) -> tuple[bool, str]:
        """Detect butterfly catastrophe (A₅): four-dimensional bifurcation.

        Butterfly shows multi-dataset mixing capability.

        Mathematical condition:
        - High complexity handling: C > 0.7
        - Fallback: Overall loss < threshold

        Args:
            config: Phase configuration with loss_threshold

        Returns:
            (detected, reason)
        """
        if len(self._complexity_history) < 10:
            # Fallback to loss threshold if no complexity metric
            if len(self._loss_history) >= 10:
                recent = list(self._loss_history)[-10:]
                avg_loss = sum(recent) / len(recent)
                if avg_loss < config.loss_threshold:
                    return True, f"butterfly_detected (loss={avg_loss:.4f})"
            return False, ""

        window = min(10, len(self._complexity_history))
        recent = list(self._complexity_history)[-window:]
        avg_complexity = sum(recent) / len(recent)

        # Butterfly condition: high complexity handling
        if avg_complexity > 0.7:
            return True, f"butterfly_detected (complexity={avg_complexity:.4f})"

        return False, ""


__all__ = ["CurriculumCatastropheDetector"]
