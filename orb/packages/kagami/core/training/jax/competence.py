"""Competence-Aware Curriculum Learning Enhancement.

Implements adaptive difficulty adjustment based on model competence.
Based on CAMPUS (Competence-Aware Multi-Perspective) framework (2025).

Key Concepts:
- Competence: Rate of improvement on current difficulty level
- Difficulty: Adjusts dynamically based on competence
- Self-Paced: Model controls its own learning pace

References:
- CAMPUS: Competence-Aware Multi-Perspective Curriculum (2025)
- Self-Paced Learning (Kumar et al., 2010)
- Strategic Data Ordering for LLM Training (2024)

Created: January 12, 2026
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Any

import jax.numpy as jnp

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass
class CompetenceConfig:
    """Configuration for competence-aware curriculum.

    Args:
        competence_window: Steps to measure competence over
        competence_threshold: Improvement threshold for competence
        difficulty_increase_rate: Rate of difficulty increase
        difficulty_decrease_rate: Rate of difficulty decrease (faster)
        min_difficulty: Minimum difficulty level
        max_difficulty: Maximum difficulty level
        warmup_steps: Steps before competence tracking begins
    """

    competence_window: int = 100
    competence_threshold: float = 0.1
    difficulty_increase_rate: float = 0.01
    difficulty_decrease_rate: float = 0.1  # Faster decrease on struggle
    min_difficulty: float = 0.0
    max_difficulty: float = 1.0
    warmup_steps: int = 500


# =============================================================================
# COMPETENCE TRACKER
# =============================================================================


class CompetenceTracker:
    """Track model competence for adaptive curriculum.

    Measures the rate of improvement to determine if the model is:
    - Learning well (positive improvement) -> increase difficulty
    - Struggling (negative improvement) -> decrease difficulty
    - Stable (near-zero improvement) -> maintain difficulty

    The difficulty level can be used to:
    - Weight sample selection (harder samples at higher difficulty)
    - Adjust loss weights
    - Control curriculum progression
    """

    def __init__(self, config: CompetenceConfig = CompetenceConfig()):
        """Initialize competence tracker.

        Args:
            config: Competence tracking configuration
        """
        self.config = config
        self._loss_history: deque[float] = deque(maxlen=config.competence_window)
        self._difficulty: float = 0.0
        self._step: int = 0

        # Statistics
        self._competence_history: list[float] = []
        self._difficulty_history: list[float] = []

    @property
    def difficulty(self) -> float:
        """Current difficulty level [0, 1]."""
        return self._difficulty

    @property
    def step(self) -> int:
        """Current step count."""
        return self._step

    def update(self, loss: float) -> float:
        """Update competence and return new difficulty.

        Args:
            loss: Current loss value

        Returns:
            Updated difficulty level
        """
        self._step += 1
        self._loss_history.append(loss)

        # Wait for warmup and sufficient history
        if self._step < self.config.warmup_steps:
            return self._difficulty

        if len(self._loss_history) < self.config.competence_window // 2:
            return self._difficulty

        # Compute competence as improvement rate
        competence = self._compute_competence()
        self._competence_history.append(competence)

        # Adjust difficulty based on competence
        if competence > self.config.competence_threshold:
            # Model is learning well -> increase difficulty
            self._difficulty = min(
                self.config.max_difficulty,
                self._difficulty + self.config.difficulty_increase_rate,
            )
        elif competence < -self.config.competence_threshold:
            # Model is struggling -> decrease difficulty faster
            self._difficulty = max(
                self.config.min_difficulty,
                self._difficulty - self.config.difficulty_decrease_rate,
            )
        # Otherwise maintain current difficulty

        self._difficulty_history.append(self._difficulty)

        return self._difficulty

    def _compute_competence(self) -> float:
        """Compute competence as normalized improvement rate.

        Compares recent loss to older loss within the window.

        Returns:
            Competence score (positive = improving, negative = struggling)
        """
        losses = list(self._loss_history)
        mid = len(losses) // 2

        recent_mean = sum(losses[mid:]) / len(losses[mid:])
        older_mean = sum(losses[:mid]) / mid

        # Normalized improvement: (older - recent) / older
        # Positive when recent < older (improving)
        if older_mean > 0:
            improvement = (older_mean - recent_mean) / older_mean
        else:
            improvement = 0.0

        return improvement

    def get_sample_weight(self, sample_difficulty: float) -> float:
        """Get sampling weight for a sample based on its difficulty.

        Samples near the current difficulty level get higher weight.
        This implements self-paced learning.

        Args:
            sample_difficulty: Difficulty level of the sample [0, 1]

        Returns:
            Sampling weight
        """
        # Gaussian weighting centered on current difficulty
        diff = abs(sample_difficulty - self._difficulty)
        weight = float(jnp.exp(-(diff**2) / 0.2))
        return weight

    def get_statistics(self) -> dict[str, Any]:
        """Get competence tracking statistics.

        Returns:
            Dictionary with tracking statistics
        """
        return {
            "step": self._step,
            "current_difficulty": self._difficulty,
            "loss_window_size": len(self._loss_history),
            "recent_loss_mean": (
                sum(list(self._loss_history)[-10:]) / 10 if len(self._loss_history) >= 10 else None
            ),
            "competence_history_len": len(self._competence_history),
            "difficulty_history_len": len(self._difficulty_history),
        }

    def state_dict(self) -> dict[str, Any]:
        """Get state for checkpointing.

        Returns:
            State dictionary
        """
        return {
            "step": self._step,
            "difficulty": self._difficulty,
            "loss_history": list(self._loss_history),
            "competence_history": self._competence_history[-100:],  # Last 100
            "difficulty_history": self._difficulty_history[-100:],
        }

    def load_state_dict(self, state: dict[str, Any]) -> None:
        """Load state from checkpoint.

        Args:
            state: State dictionary
        """
        self._step = state.get("step", 0)
        self._difficulty = state.get("difficulty", 0.0)

        # Restore histories
        loss_hist = state.get("loss_history", [])
        self._loss_history = deque(loss_hist, maxlen=self.config.competence_window)

        self._competence_history = state.get("competence_history", [])
        self._difficulty_history = state.get("difficulty_history", [])

        logger.info(
            f"Loaded competence state: step={self._step}, difficulty={self._difficulty:.3f}"
        )


# =============================================================================
# DIFFICULTY-AWARE SAMPLING
# =============================================================================


class DifficultyAwareSampler:
    """Sample training data based on difficulty and competence.

    Implements self-paced learning by adjusting sample weights
    based on their difficulty relative to current model competence.

    Two modes:
    1. Curriculum mode: Easier samples first, harder later
    2. Anti-curriculum mode: Harder samples first (can be beneficial for some tasks)
    """

    def __init__(
        self,
        competence_tracker: CompetenceTracker,
        sample_difficulties: dict[str, float],  # sample_id -> difficulty
        anti_curriculum: bool = False,
    ):
        """Initialize difficulty-aware sampler.

        Args:
            competence_tracker: Competence tracker instance
            sample_difficulties: Mapping of sample IDs to difficulty scores
            anti_curriculum: If True, prefer harder samples
        """
        self.tracker = competence_tracker
        self.sample_difficulties = sample_difficulties
        self.anti_curriculum = anti_curriculum

    def get_sample_weights(self) -> dict[str, float]:
        """Get sampling weights for all samples.

        Returns:
            Dictionary mapping sample ID to sampling weight
        """
        current_difficulty = self.tracker.difficulty

        weights = {}
        for sample_id, sample_diff in self.sample_difficulties.items():
            if self.anti_curriculum:
                # Invert: prefer samples far from current difficulty
                diff = abs(sample_diff - current_difficulty)
                weight = 1.0 - float(jnp.exp(-(diff**2) / 0.2))
            else:
                # Standard: prefer samples near current difficulty
                weight = self.tracker.get_sample_weight(sample_diff)

            weights[sample_id] = max(0.01, weight)  # Minimum weight

        return weights

    def update(self, loss: float) -> dict[str, float]:
        """Update competence and return new sample weights.

        Args:
            loss: Current training loss

        Returns:
            Updated sample weights
        """
        self.tracker.update(loss)
        return self.get_sample_weights()


# =============================================================================
# CURRICULUM PHASE ENHANCEMENT
# =============================================================================


@dataclass
class CompetenceEnhancedPhase:
    """Curriculum phase configuration enhanced with competence tracking.

    Extends standard phase configuration with:
    - Per-phase competence tracker
    - Dynamic loss thresholds based on competence
    - Adaptive transition criteria
    """

    name: str
    min_steps: int
    max_steps: int
    base_loss_threshold: float
    competence_config: CompetenceConfig = field(default_factory=CompetenceConfig)

    # Adaptive thresholds
    loss_threshold_scale_min: float = 0.5  # Min scaling of base threshold
    loss_threshold_scale_max: float = 1.5  # Max scaling of base threshold

    def get_adaptive_loss_threshold(self, competence: float) -> float:
        """Get loss threshold adjusted for current competence.

        Higher competence -> stricter threshold (lower loss required)
        Lower competence -> relaxed threshold (higher loss allowed)

        Args:
            competence: Current competence level [-1, 1]

        Returns:
            Adjusted loss threshold
        """
        # Map competence [-1, 1] to scale [max, min]
        # High competence (1) -> min scale (stricter)
        # Low competence (-1) -> max scale (relaxed)
        normalized = (competence + 1) / 2  # [0, 1]
        scale = self.loss_threshold_scale_max - normalized * (
            self.loss_threshold_scale_max - self.loss_threshold_scale_min
        )

        return self.base_loss_threshold * scale


# =============================================================================
# INTEGRATED CURRICULUM MANAGER
# =============================================================================


class CompetenceAwareCurriculum:
    """Curriculum manager with integrated competence tracking.

    Enhances standard curriculum with:
    - Per-phase competence tracking
    - Adaptive phase transitions
    - Difficulty-aware data selection
    """

    def __init__(
        self,
        phases: list[CompetenceEnhancedPhase],
        global_config: CompetenceConfig = CompetenceConfig(),
    ):
        """Initialize competence-aware curriculum.

        Args:
            phases: List of enhanced phase configurations
            global_config: Global competence configuration
        """
        self.phases = phases
        self.global_config = global_config

        # Per-phase trackers
        self._trackers: dict[str, CompetenceTracker] = {
            phase.name: CompetenceTracker(phase.competence_config) for phase in phases
        }

        # Global tracker
        self._global_tracker = CompetenceTracker(global_config)

        # Current state
        self._current_phase_idx: int = 0
        self._phase_start_step: int = 0

    @property
    def current_phase(self) -> CompetenceEnhancedPhase:
        """Get current phase configuration."""
        return self.phases[self._current_phase_idx]

    @property
    def current_tracker(self) -> CompetenceTracker:
        """Get current phase's competence tracker."""
        return self._trackers[self.current_phase.name]

    @property
    def global_difficulty(self) -> float:
        """Get global difficulty level."""
        return self._global_tracker.difficulty

    @property
    def phase_difficulty(self) -> float:
        """Get current phase's difficulty level."""
        return self.current_tracker.difficulty

    def update(self, step: int, loss: float) -> dict[str, Any]:
        """Update curriculum state.

        Args:
            step: Current training step
            loss: Current loss value

        Returns:
            Update result including transition info
        """
        # Update trackers
        self._global_tracker.update(loss)
        phase_difficulty = self.current_tracker.update(loss)

        result = {
            "phase": self.current_phase.name,
            "global_difficulty": self.global_difficulty,
            "phase_difficulty": phase_difficulty,
            "transitioned": False,
        }

        # Check for phase transition
        if self._should_advance(step, loss):
            self._advance(step)
            result["transitioned"] = True
            result["new_phase"] = self.current_phase.name

        return result

    def _should_advance(self, step: int, loss: float) -> bool:
        """Check if should advance to next phase.

        Uses competence-aware criteria:
        1. Minimum steps completed
        2. Loss below adaptive threshold
        3. Phase difficulty at maximum (model has mastered this phase)
        """
        phase = self.current_phase
        steps_in_phase = step - self._phase_start_step

        # Don't advance past last phase
        if self._current_phase_idx >= len(self.phases) - 1:
            return False

        # Must complete minimum steps
        if steps_in_phase < phase.min_steps:
            return False

        # Force advance at max steps
        if steps_in_phase >= phase.max_steps:
            logger.info(f"Phase {phase.name}: reached max_steps, advancing")
            return True

        # Get competence-adjusted loss threshold
        competence = self._compute_recent_competence()
        adaptive_threshold = phase.get_adaptive_loss_threshold(competence)

        # Check if loss below adaptive threshold
        if loss < adaptive_threshold:
            logger.info(
                f"Phase {phase.name}: loss {loss:.4f} < threshold {adaptive_threshold:.4f} "
                f"(competence={competence:.3f}), advancing"
            )
            return True

        # Check if difficulty at maximum (mastered phase)
        if self.phase_difficulty >= self.global_config.max_difficulty * 0.95:
            logger.info(f"Phase {phase.name}: difficulty at max, advancing")
            return True

        return False

    def _advance(self, step: int) -> None:
        """Advance to next phase."""
        old_phase = self.current_phase.name
        self._current_phase_idx += 1
        self._phase_start_step = step

        new_phase = self.current_phase.name
        logger.info(f"Curriculum: {old_phase} -> {new_phase} at step {step}")

    def _compute_recent_competence(self) -> float:
        """Compute recent competence from tracker history.

        Returns:
            Recent competence [-1, 1]
        """
        history = self.current_tracker._competence_history
        if len(history) < 10:
            return 0.0

        # Average of last 10 competence measurements
        recent = history[-10:]
        return sum(recent) / len(recent)

    def get_sample_weight(self, sample_difficulty: float) -> float:
        """Get sampling weight for a sample.

        Combines global and phase-specific difficulty.

        Args:
            sample_difficulty: Sample difficulty [0, 1]

        Returns:
            Sampling weight
        """
        # Use phase difficulty for fine-grained control
        return self.current_tracker.get_sample_weight(sample_difficulty)

    def state_dict(self) -> dict[str, Any]:
        """Get state for checkpointing."""
        return {
            "current_phase_idx": self._current_phase_idx,
            "phase_start_step": self._phase_start_step,
            "global_tracker": self._global_tracker.state_dict(),
            "phase_trackers": {
                name: tracker.state_dict() for name, tracker in self._trackers.items()
            },
        }

    def load_state_dict(self, state: dict[str, Any]) -> None:
        """Load state from checkpoint."""
        self._current_phase_idx = state.get("current_phase_idx", 0)
        self._phase_start_step = state.get("phase_start_step", 0)

        if "global_tracker" in state:
            self._global_tracker.load_state_dict(state["global_tracker"])

        for name, tracker_state in state.get("phase_trackers", {}).items():
            if name in self._trackers:
                self._trackers[name].load_state_dict(tracker_state)

        logger.info(
            f"Loaded competence curriculum: phase {self._current_phase_idx}, "
            f"global_difficulty={self.global_difficulty:.3f}"
        )


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "CompetenceAwareCurriculum",
    "CompetenceConfig",
    "CompetenceEnhancedPhase",
    "CompetenceTracker",
    "DifficultyAwareSampler",
]
