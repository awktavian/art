"""JAX Curriculum System - 7-phase training curriculum.

Mirrors unified_curriculum.py with full feature parity:
- 7 phases (WARMUP, GEOMETRY, ROTATION, DYNAMICS, JOINT, GENERATION, LANGUAGE)
- KL annealing (β=1e-6 during WARMUP, β=1.0 afterwards)
- Plateau patience with adaptive LR reduction
- Gradient-norm + loss-velocity tracking
- Progressive Fano colony activation (1→2→3→4→7)
- Catastrophe-type aligned transitions
- Data source weight progression

BRICK-BY-BRICK COMPARISON:
=========================
PyTorch Source                                | JAX Target
----------------------------------------------|----------------------------------------
training/unified_curriculum.py:Unified...     | Curriculum
training/unified_curriculum.py:PhaseConfig    | PhaseConfig (in config.py)
training/unified_curriculum.py:CurriculumState| CurriculumState (in this file)

Created: January 8, 2026
Updated: January 9, 2026 - Added WARMUP, LANGUAGE, KL annealing, plateau patience
"""

from __future__ import annotations

import logging
import math
from typing import Any

from .config import CurriculumConfig, CurriculumPhase, PhaseConfig
from .losses import LossWeights

logger = logging.getLogger(__name__)


# =============================================================================
# CURRICULUM STATE
# =============================================================================


from collections import deque
from dataclasses import dataclass, field


@dataclass
class CurriculumState:
    """Current state of the curriculum.

    Mirrors unified_curriculum.py:CurriculumState.
    """

    phase_idx: int = 0  # Start at WARMUP (index 0)
    phase_step: int = 0  # Steps in current phase
    total_step: int = 0  # Total training steps
    phase_best_loss: float = float("inf")
    plateau_count: int = 0

    # Gradient tracking
    gradient_norm_ema: float = 1.0
    loss_velocity: float = 0.0

    # LR plateau tracking (Jan 5, 2026)
    lr_plateau_multiplier: float = 1.0
    lr_reductions: int = 0

    # Phase history
    phase_history: list[dict[str, Any]] = field(default_factory=list)


# =============================================================================
# FANO PLANE COLONY ACTIVATION
# =============================================================================


# Progressive Fano plane colony activation by phase
COLONY_ACTIVATION = {
    0: [1],  # WARMUP: Spark only
    1: [1, 2],  # GEOMETRY: Spark, Forge
    2: [1, 2, 3],  # ROTATION: + Flow (Fano line)
    3: [1, 2, 3, 4],  # DYNAMICS: + Nexus
    4: [1, 2, 3, 4, 5, 6, 7],  # JOINT: all colonies
    5: [1, 2, 3, 4, 5, 6, 7],  # GENERATION: all colonies
    6: [1, 2, 3, 4, 5, 6, 7],  # LANGUAGE: all colonies
}


# =============================================================================
# CURRICULUM (mirrors unified_curriculum.py:UnifiedCurriculumScheduler)
# =============================================================================


class Curriculum:
    """Manages 7-phase curriculum progression for TPU training.

    Mirrors unified_curriculum.py:UnifiedCurriculumScheduler.

    Curriculum Phases (7 total, aligned with catastrophe types):
    0. WARMUP: Pre-fold stabilization (β≈0, reconstruction-only)
    1. GEOMETRY: Fold (A₂) - 2 colonies, E8 lattice learning
    2. ROTATION: Cusp (A₃) - 3 colonies, SE(3) equivariance
    3. DYNAMICS: Swallowtail (A₄) - 4 colonies, world model prediction
    4. JOINT: Butterfly (A₅) - 7 colonies, RSSM + EFE unified
    5. GENERATION: Hyperbolic (D₄⁺) - 7 colonies, fine-grained generation
    6. LANGUAGE: Elliptic (D₄⁻) - 7 colonies, language grounding

    Key Features:
    - KL annealing (β=1e-6 during WARMUP)
    - Plateau patience with adaptive LR reduction
    - Gradient-norm + loss-velocity tracking
    - Progressive Fano colony activation
    - Multi-criteria transition detection
    """

    def __init__(self, config: CurriculumConfig):
        self.config = config
        self.state = CurriculumState()

        # Create phases
        self.phases = self._create_phases()

        # Loss/gradient histories
        self._loss_history: deque[float] = deque(maxlen=200)
        self._gradient_history: deque[float] = deque(maxlen=100)

        logger.info(
            f"Curriculum initialized: {len(self.phases)} phases, "
            f"chips={config.num_chips}, total_steps={config.total_steps:,}"
        )

    def _create_phases(self) -> list[PhaseConfig]:
        """Create 7 curriculum phases with appropriate settings.

        Matches unified_curriculum.py:DEFAULT_PHASES.
        """
        return [
            # === Phase 0: WARMUP ===
            # Pre-fold stabilization with small KL (NOT zero!)
            # CRITICAL FIX (Jan 12, 2026): Non-zero KL prevents posterior
            # collapse at phase transition. effective_kl = 0.001 * 0.01 = 1e-5
            PhaseConfig(
                name=CurriculumPhase.WARMUP,
                min_steps=500,
                max_steps=2000,
                loss_threshold=0.1,
                gradient_threshold=0.01,
                velocity_threshold=0.01,
                lr_multiplier=1.0,
                e8_weight=0.0,
                kl_weight=0.001,  # Small but non-zero to prevent collapse!
                kl_beta=0.01,  # Small β during warmup
                recon_weight=1.0,
                reward_weight=0.0,
                fano_weight=0.001,  # Small regularization from start
                hjepa_weight=0.001,  # Small prediction loss from start
                plateau_patience=200,
                efe_enabled=False,
                alignment_enabled=False,
                language_enabled=False,
                data_weights={"jepa": 1.0},
                extra_config={"focus": "encoder_decoder_stabilization"},
            ),
            # === Phase 1: GEOMETRY (Fold A₂) ===
            # Gradual KL increase from WARMUP
            PhaseConfig(
                name=CurriculumPhase.GEOMETRY,
                min_steps=1000,
                max_steps=10000,
                loss_threshold=0.08,
                gradient_threshold=0.001,
                velocity_threshold=0.001,
                lr_multiplier=1.0,
                e8_weight=0.5,
                kl_weight=0.1,  # Gradual increase from 0.001
                kl_beta=0.1,  # Gradual increase from 0.01
                recon_weight=1.0,
                reward_weight=0.0,
                fano_weight=0.0,
                hjepa_weight=0.0,
                plateau_patience=400,
                efe_enabled=False,
                alignment_enabled=False,
                language_enabled=False,
                data_weights={"jepa": 0.6, "qm9": 0.2, "tree_of_life": 0.2},
                extra_config={"focus": "hyperbolic_embeddings"},
            ),
            # === Phase 2: ROTATION (Cusp A₃) ===
            PhaseConfig(
                name=CurriculumPhase.ROTATION,
                min_steps=1000,
                max_steps=15000,
                loss_threshold=0.05,
                gradient_threshold=0.0005,
                velocity_threshold=0.0005,
                lr_multiplier=1.0,
                e8_weight=0.3,
                kl_weight=1.0,
                kl_beta=1.0,
                recon_weight=1.0,
                reward_weight=0.0,
                fano_weight=0.01,
                hjepa_weight=0.0,
                plateau_patience=400,
                efe_enabled=False,
                alignment_enabled=False,
                language_enabled=False,
                data_weights={"jepa": 0.5, "qm9": 0.2, "tree_of_life": 0.2, "generation": 0.1},
                extra_config={"focus": "rotational_equivariance"},
            ),
            # === Phase 3: DYNAMICS (Swallowtail A₄) ===
            PhaseConfig(
                name=CurriculumPhase.DYNAMICS,
                min_steps=2000,
                max_steps=40000,
                loss_threshold=0.1,
                gradient_threshold=0.0003,
                velocity_threshold=0.0003,
                lr_multiplier=0.8,
                e8_weight=0.1,
                kl_weight=1.0,
                kl_beta=1.0,
                recon_weight=1.0,
                reward_weight=0.5,
                fano_weight=0.05,
                hjepa_weight=0.1,
                plateau_patience=400,
                efe_enabled=False,
                alignment_enabled=False,
                language_enabled=False,
                data_weights={"jepa": 0.45, "qm9": 0.2, "tree_of_life": 0.2, "generation": 0.15},
                extra_config={"focus": "world_model_prediction"},
            ),
            # === Phase 4: JOINT (Butterfly A₅) ===
            PhaseConfig(
                name=CurriculumPhase.JOINT,
                min_steps=5000,
                max_steps=80000,
                loss_threshold=0.05,
                gradient_threshold=0.0002,
                velocity_threshold=0.0002,
                lr_multiplier=0.5,
                e8_weight=0.05,
                kl_weight=1.0,
                kl_beta=1.0,
                recon_weight=1.0,
                reward_weight=1.0,
                fano_weight=0.1,
                hjepa_weight=0.2,
                plateau_patience=400,
                efe_enabled=True,
                alignment_enabled=True,
                language_enabled=False,
                data_weights={"jepa": 0.35, "qm9": 0.15, "tree_of_life": 0.15, "generation": 0.35},
                extra_config={"focus": "unified_rssm_efe"},
            ),
            # === Phase 5: GENERATION (Hyperbolic D₄⁺) ===
            PhaseConfig(
                name=CurriculumPhase.GENERATION,
                min_steps=5000,
                max_steps=120000,
                loss_threshold=0.01,
                gradient_threshold=0.0001,
                velocity_threshold=0.0001,
                lr_multiplier=0.3,
                e8_weight=0.01,
                kl_weight=1.0,
                kl_beta=1.0,
                recon_weight=1.0,
                reward_weight=1.0,
                fano_weight=0.1,
                hjepa_weight=0.3,
                plateau_patience=400,
                efe_enabled=True,
                alignment_enabled=True,
                language_enabled=False,
                data_weights={"generation": 0.5, "jepa": 0.25, "qm9": 0.15, "tree_of_life": 0.1},
                extra_config={"focus": "fine_grained_generation"},
            ),
            # === Phase 6: LANGUAGE (Elliptic D₄⁻) ===
            PhaseConfig(
                name=CurriculumPhase.LANGUAGE,
                min_steps=10000,
                max_steps=150000,
                loss_threshold=0.05,
                gradient_threshold=0.0001,
                velocity_threshold=0.0001,
                lr_multiplier=0.2,
                e8_weight=0.01,
                kl_weight=0.5,
                kl_beta=1.0,
                recon_weight=0.5,
                reward_weight=0.5,
                fano_weight=0.1,
                hjepa_weight=0.3,
                plateau_patience=400,
                efe_enabled=True,
                alignment_enabled=True,
                language_enabled=True,
                data_weights={
                    "jepa": 0.3,
                    "language": 0.3,
                    "instruction": 0.2,
                    "qm9": 0.1,
                    "tree_of_life": 0.1,
                },
                extra_config={"focus": "language_grounding"},
            ),
        ]

    @property
    def current_phase(self) -> PhaseConfig:
        """Get current curriculum phase."""
        return self.phases[self.state.phase_idx]

    @property
    def current_phase_idx(self) -> int:
        """Get current phase index (for compatibility)."""
        return self.state.phase_idx

    @property
    def best_loss(self) -> float:
        """Get best loss in current phase."""
        return self.state.phase_best_loss

    @property
    def steps_without_improvement(self) -> int:
        """Get steps without improvement (for compatibility)."""
        return self.state.plateau_count

    def get_kl_beta(self) -> float:
        """Get current KL β value for VAE loss.

        Returns:
            β value (1e-6 during WARMUP, 1.0 otherwise)
        """
        return self.current_phase.kl_beta

    def get_active_colonies(self) -> list[int]:
        """Get list of active colony indices for current phase.

        Returns:
            List of colony indices (1-7)
        """
        return COLONY_ACTIVATION.get(self.state.phase_idx, [1, 2])

    def get_data_weights(self) -> dict[str, float]:
        """Get current data source weights for curriculum sampling."""
        return self.current_phase.data_weights.copy()

    def should_advance(self, step: int, current_loss: float) -> bool:
        """Check if curriculum should advance to next phase.

        Multi-criteria transition:
        1. Minimum steps reached
        2. Loss below threshold
        3. Gradient norm converged
        4. Loss velocity stable

        Args:
            step: Current training step
            current_loss: Current loss value

        Returns:
            Whether to advance to next phase
        """
        phase = self.current_phase
        steps_in_phase = step - self.state.phase_step

        # Don't advance if at last phase
        if self.state.phase_idx >= len(self.phases) - 1:
            return False

        # Must complete minimum steps
        if steps_in_phase < phase.min_steps:
            return False

        # Force advance at max steps
        if steps_in_phase >= phase.max_steps:
            logger.info(f"Curriculum advancing: reached max_steps {phase.max_steps}")
            return True

        # Check loss threshold
        loss_below_threshold = current_loss < phase.loss_threshold

        # Check gradient convergence
        gradient_converged = (
            self.state.gradient_norm_ema < phase.gradient_threshold
            and len(self._gradient_history) >= 10
        )

        # Check velocity stability
        velocity_stable = (
            abs(self.state.loss_velocity) < phase.velocity_threshold
            and len(self._loss_history) >= 20
        )

        # Auto-advance on all criteria met
        if (
            self.config.auto_advance
            and loss_below_threshold
            and gradient_converged
            and velocity_stable
        ):
            logger.info(
                f"Curriculum advancing: loss={current_loss:.4f} < {phase.loss_threshold}, "
                f"grad_ema={self.state.gradient_norm_ema:.6f}, "
                f"velocity={self.state.loss_velocity:.6f}"
            )
            return True

        # Track improvement for patience-based advance
        if current_loss < self.state.phase_best_loss:
            self.state.phase_best_loss = current_loss
            self.state.plateau_count = 0
        else:
            self.state.plateau_count += 1

        # Advance on patience timeout
        if self.steps_without_improvement >= self.config.phase_patience:
            logger.info(f"Curriculum advancing: patience exhausted ({self.config.phase_patience})")
            return True

        return False

    def advance(self, step: int) -> None:
        """Advance to next curriculum phase.

        Args:
            step: Current training step
        """
        if self.current_phase_idx < len(self.phases) - 1:
            self.current_phase_idx += 1
            self.phase_start_step = step
            self.best_loss = float("inf")
            self.steps_without_improvement = 0

            phase = self.current_phase
            logger.info(
                f"Advanced to phase: {phase.name.value} "
                f"(LR mult: {phase.lr_multiplier}, "
                f"E8 weight: {phase.e8_weight})"
            )

    def get_e8_weight(self, step: int) -> float:
        """Compute E8 commitment weight with warmup.

        PyTorch: curriculum.py:_compute_e8_weight()

        Uses cosine ramp from warmup_start to warmup_end, then
        multiplied by the phase-specific E8 weight.

        Args:
            step: Current training step

        Returns:
            E8 commitment weight
        """
        if step < self.config.e8_warmup_start:
            return 0.0
        elif step >= self.config.e8_warmup_end:
            return self.current_phase.e8_weight
        else:
            # Cosine ramp
            progress = (step - self.config.e8_warmup_start) / (
                self.config.e8_warmup_end - self.config.e8_warmup_start
            )
            ramp = 0.5 * (1 - math.cos(math.pi * progress))
            return ramp * self.current_phase.e8_weight

    def get_loss_weights(self, step: int) -> LossWeights:
        """Get loss weights for current phase and step.

        CRITICAL FIX (Jan 12, 2026):
        - KL weight now uses kl_weight * kl_beta (not just kl_weight)
        - Added smooth interpolation at phase boundaries (500 steps)
        - Prevents catastrophic KL collapse at phase transitions

        Args:
            step: Current training step

        Returns:
            LossWeights with phase-appropriate values
        """
        phase = self.current_phase
        phase_idx = self.state.phase_idx

        # Base weights from current phase (kl includes beta!)
        base_weights = LossWeights(
            recon=phase.recon_weight,
            kl=phase.kl_weight * phase.kl_beta,  # CRITICAL: multiply by beta
            reward=phase.reward_weight,
            e8=self.get_e8_weight(step),
            fano=phase.fano_weight,
            hjepa=phase.hjepa_weight,
            stability=0.01,
        )

        # Smooth transition at phase boundaries (prevent optimizer shock)
        if phase_idx < len(self.phases) - 1:
            next_phase = self.phases[phase_idx + 1]
            phase_progress = self.state.phase_step / max(phase.min_steps, 1)

            # Start blending 500 steps before transition
            transition_start = 0.8  # Start at 80% through min_steps
            if phase_progress > transition_start:
                # Linear blend toward next phase
                blend = (phase_progress - transition_start) / (1.0 - transition_start)
                blend = min(blend, 1.0)

                next_weights = LossWeights(
                    recon=next_phase.recon_weight,
                    kl=next_phase.kl_weight * next_phase.kl_beta,
                    reward=next_phase.reward_weight,
                    e8=next_phase.e8_weight,
                    fano=next_phase.fano_weight,
                    hjepa=next_phase.hjepa_weight,
                    stability=0.01,
                )

                # Interpolate all weights
                return LossWeights(
                    recon=base_weights.recon * (1 - blend) + next_weights.recon * blend,
                    kl=base_weights.kl * (1 - blend) + next_weights.kl * blend,
                    reward=base_weights.reward * (1 - blend) + next_weights.reward * blend,
                    e8=base_weights.e8 * (1 - blend) + next_weights.e8 * blend,
                    fano=base_weights.fano * (1 - blend) + next_weights.fano * blend,
                    hjepa=base_weights.hjepa * (1 - blend) + next_weights.hjepa * blend,
                    stability=0.01,
                )

        return base_weights

    def get_learning_rate(self, base_lr: float) -> float:
        """Get learning rate with phase multiplier.

        Args:
            base_lr: Base learning rate

        Returns:
            Learning rate for current phase
        """
        return base_lr * self.current_phase.lr_multiplier

    def state_dict(self) -> dict[str, Any]:
        """Get curriculum state for checkpointing.

        Returns:
            State dictionary
        """
        return {
            "current_phase_idx": self.current_phase_idx,
            "phase_start_step": self.phase_start_step,
            "best_loss": self.best_loss,
            "steps_without_improvement": self.steps_without_improvement,
            "version": "1.0",
        }

    def load_state_dict(self, state: dict[str, Any]) -> None:
        """Load curriculum state from checkpoint.

        Args:
            state: State dictionary
        """
        self.current_phase_idx = state["current_phase_idx"]
        self.phase_start_step = state["phase_start_step"]
        self.best_loss = state["best_loss"]
        self.steps_without_improvement = state["steps_without_improvement"]

        logger.info(
            f"Resumed curriculum at phase {self.current_phase_idx} "
            f"({self.current_phase.name.value}), best_loss={self.best_loss:.4f}"
        )


# =============================================================================
# LEARNING RATE SCHEDULE
# =============================================================================


class HyperscaleLRSchedule:
    """Learning rate schedule with warmup + cosine decay.

    PyTorch: curriculum.py:HyperscaleLRSchedule

    Implements warmup + cosine decay with optional restarts.
    """

    def __init__(
        self,
        base_lr: float,
        warmup_steps: int,
        total_steps: int,
        min_lr_ratio: float = 0.1,
        num_cycles: int = 1,
    ):
        self.base_lr = base_lr
        self.warmup_steps = warmup_steps
        self.total_steps = total_steps
        self.min_lr = base_lr * min_lr_ratio
        self.num_cycles = num_cycles

    def get_lr(self, step: int) -> float:
        """Get learning rate for step.

        Args:
            step: Training step

        Returns:
            Learning rate
        """
        if step < self.warmup_steps:
            # Linear warmup
            return self.base_lr * (step / self.warmup_steps)
        else:
            # Cosine decay with optional restarts
            decay_steps = self.total_steps - self.warmup_steps
            cycle_length = decay_steps // self.num_cycles
            cycle_step = (step - self.warmup_steps) % cycle_length

            progress = cycle_step / cycle_length
            cosine_decay = 0.5 * (1 + math.cos(math.pi * progress))

            return self.min_lr + (self.base_lr - self.min_lr) * cosine_decay

    @classmethod
    def from_curriculum(cls, curriculum: Curriculum) -> HyperscaleLRSchedule:
        """Create LR schedule from curriculum config.

        Args:
            curriculum: Curriculum instance

        Returns:
            LR schedule
        """
        return cls(
            base_lr=curriculum.config.baseline_lr,
            warmup_steps=curriculum.config.base_warmup_steps,
            total_steps=curriculum.config.total_steps,
        )


# =============================================================================
# EXPORTS
# =============================================================================


__all__ = [
    "Curriculum",
    "HyperscaleLRSchedule",
]
