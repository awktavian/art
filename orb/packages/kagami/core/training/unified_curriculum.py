"""Unified Curriculum Scheduler for Joint RSSM+EFE Training.

UNIFIED CURRICULUM (December 20, 2025):
========================================
Combines the strengths of AdaptiveCurriculumScheduler and FanoCurriculumScheduler
into a single, robust implementation with:
- Gradient-norm tracking (from Adaptive)
- Catastrophe detection (from Fano)
- Progressive colony activation (Fano plane structure)
- Depth curriculum (E8, VQ, Program, Memory)
- Smooth transitions with hysteresis

STATUS: PRODUCTION (Unified Replacement)
========================================
- Replaces: AdaptiveCurriculumScheduler, FanoCurriculumScheduler, CurriculumScheduler
- Used by: JointRSSMEFETrainer, WorldModelLoop, train_kagami.py
- Purpose: Single unified curriculum for all training scenarios

THEORETICAL FOUNDATION:
=======================
1. Catastrophe Theory (Thom 1972):
   - Elementary catastrophes guide phase transitions
   - Singularity detection provides mathematical grounding
   - Progressive complexity aligned with catastrophe types

2. Gradient-Based Learning (Bengio et al. 2009):
   - Gradient norm convergence indicates phase readiness
   - Loss velocity tracking prevents premature transitions
   - EMA smoothing reduces noise

3. Fano Plane Colony Activation:
   - Progressive colony activation: 2→3→4→7
   - Follows Fano line structure for consistency
   - Preserves G₂ geometric structure

CURRICULUM PHASES:
==================
Phase 1 (Hierarchy) - Fold Catastrophe (A₂):
  - Focus: E8→E7→E6→F₄→G₂→S⁷ hierarchy learning
  - Active colonies: [1, 2] (Spark, Forge)
  - Depths: e8=2, vq=1, program=2, memory=1
  - Transition: Fold detection + gradient convergence

Phase 2 (Rotation) - Cusp Catastrophe (A₃):
  - Focus: SE(3) equivariance and rotational structure
  - Active colonies: [1, 2, 3] (+ Flow)
  - Depths: e8=4, vq=2, program=4, memory=2
  - Transition: Cusp hysteresis + gradient stability

Phase 3 (Dynamics) - Swallowtail Catastrophe (A₄):
  - Focus: Temporal prediction and world dynamics
  - Active colonies: [1, 2, 3, 4] (+ Nexus)
  - Depths: e8=6, vq=2, program=6, memory=4
  - Transition: Swallowtail bifurcation

Phase 4 (Joint) - Butterfly Catastrophe (A₅):
  - Focus: Multi-dataset mixing and relational structure
  - Active colonies: [1, 2, 3, 4, 5, 6, 7] (all colonies)
  - Depths: e8=8, vq=3, program=8, memory=6
  - Transition: Butterfly detection

Phase 5 (Generation) - Hyperbolic Umbilic (D₄⁺):
  - Focus: Generative dynamics and policy synthesis
  - Active colonies: [1, 2, 3, 4, 5, 6, 7] (all colonies)
  - Depths: e8=16, vq=4, program=16, memory=8
  - No further transitions (terminal phase)

TRANSITION CRITERIA:
====================
Each phase transition requires ALL of:
1. Minimum step threshold reached
2. Catastrophe condition detected
3. Gradient norm convergence
4. Loss velocity stable

This multi-criteria approach prevents:
- Premature transitions (step threshold)
- False positives (catastrophe detection)
- Gradient instability (norm tracking)
- Loss oscillations (velocity check)

IMPORTS AND USAGE:
==================
Primary import:
    from kagami.core.training.unified_curriculum import UnifiedCurriculumScheduler

Example:
    scheduler = UnifiedCurriculumScheduler(
        base_lr=1e-4,
        enable_auto_transition=True,
        enable_early_generation=True,
    )

    for step in range(max_steps):
        result = scheduler.step(losses, gradient_norm)

        if result["should_transition"]:
            scheduler.apply_depth_to_model(model)
            logger.info(f"Phase: {result['phase_name']}")
            logger.info(f"Colonies: {scheduler.get_active_colonies()}")

        weights = scheduler.get_loss_weights()
        loss = compute_weighted_loss(weights)

Created: December 20, 2025
Status: Production-ready (unified)
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from enum import IntEnum
from typing import TYPE_CHECKING, Any

from kagami.core.training.curriculum import CurriculumCatastropheDetector

if TYPE_CHECKING:
    from kagami.core.world_model import KagamiWorldModel

logger = logging.getLogger(__name__)


class CurriculumPhase(IntEnum):
    """7-phase curriculum aligned with catastrophe types.

    WARMUP PHASE (Jan 5, 2026):
    ===========================
    Added Phase -1 (WARMUP) for encoder/decoder stabilization before KL training.
    Pure reconstruction with β=1e-6 (not 0) to avoid JAX recompilation.

    LANGUAGE PHASE (Jan 4, 2026):
    ============================
    Added Phase 5 (LANGUAGE) for language grounding and generation training.
    Uses Elliptic catastrophe (D₄⁻) for inward language learning.
    """

    WARMUP = -1  # Pre-fold warmup: β≈0, reconstruction-only (Jan 5, 2026)
    HIERARCHY = 0  # Fold (A₂): 2 colonies
    ROTATION = 1  # Cusp (A₃): 3 colonies (Fano line)
    DYNAMICS = 2  # Swallowtail (A₄): 4 colonies
    JOINT = 3  # Butterfly (A₅): 7 colonies (full Fano)
    GENERATION = 4  # Hyperbolic (D₄⁺): 7 colonies
    LANGUAGE = 5  # Elliptic (D₄⁻): 7 colonies, language grounding (NEW Jan 4, 2026)


PHASE_NAMES = {
    CurriculumPhase.WARMUP: "Warmup (Pre-fold)",  # NEW Jan 5, 2026
    CurriculumPhase.HIERARCHY: "Hierarchy (Fold A₂)",
    CurriculumPhase.ROTATION: "Rotation (Cusp A₃)",
    CurriculumPhase.DYNAMICS: "Dynamics (Swallowtail A₄)",
    CurriculumPhase.JOINT: "Joint (Butterfly A₅)",
    CurriculumPhase.GENERATION: "Generation (Hyperbolic D₄⁺)",
    CurriculumPhase.LANGUAGE: "Language (Elliptic D₄⁻)",  # NEW Jan 4, 2026
}

CATASTROPHE_TYPES = {
    CurriculumPhase.WARMUP: "none",  # NEW Jan 5, 2026 - no catastrophe for warmup
    CurriculumPhase.HIERARCHY: "fold",
    CurriculumPhase.ROTATION: "cusp",
    CurriculumPhase.DYNAMICS: "swallowtail",
    CurriculumPhase.JOINT: "butterfly",
    CurriculumPhase.GENERATION: "hyperbolic",
    CurriculumPhase.LANGUAGE: "elliptic",  # NEW Jan 4, 2026 - D₄⁻ inward language
}


@dataclass
class PhaseConfig:
    """Configuration for a unified curriculum phase.

    Combines depth curriculum (Adaptive) + loss weights (Fano).

    KL ANNEALING (Jan 5, 2026):
    ===========================
    Added kl_weight field for per-phase KL weighting. During WARMUP, this is 1e-6
    (not 0) to avoid JAX recompilation when transitioning to HIERARCHY.

    PLATEAU PATIENCE (Jan 5, 2026):
    ===============================
    Added plateau_patience field (default 400) for adaptive LR reduction.
    """

    name: str
    catastrophe_type: str  # fold, cusp, swallowtail, butterfly, hyperbolic, none

    # Step boundaries
    min_steps: int
    max_steps: int

    # Loss thresholds for transition
    loss_threshold: float  # Primary loss must be below this

    # Gradient/velocity criteria
    gradient_threshold: float  # Gradient norm must be below this
    velocity_threshold: float  # Loss velocity must be near zero

    # Loss weights
    loss_weights: dict[str, float]

    # Data source weights
    data_weights: dict[str, float]

    # Learning rate multiplier
    lr_multiplier: float = 1.0

    # KL weight (Jan 5, 2026): β for VAE loss (L = recon + β*KL)
    # Use 1e-6 instead of 0 to avoid JAX graph recompilation
    kl_weight: float = 1.0

    # Plateau patience (Jan 5, 2026): Steps without improvement before LR reduction
    plateau_patience: int = 400

    # Depth curriculum
    e8_depth: int = 4
    vq_depth: int = 2
    program_depth: int = 4
    memory_depth: int = 2


@dataclass
class CurriculumState:
    """Current state of the unified curriculum.

    WARMUP START (Jan 5, 2026):
    ===========================
    Default phase is now WARMUP (-1) instead of HIERARCHY (0).
    """

    phase: CurriculumPhase = CurriculumPhase.WARMUP  # Start at WARMUP (Jan 5, 2026)
    phase_step: int = 0
    total_step: int = 0
    phase_best_loss: float = float("inf")
    plateau_count: int = 0

    # Gradient tracking (from Adaptive)
    gradient_norm_ema: float = 1.0
    loss_velocity: float = 0.0

    # LR plateau tracking (Jan 5, 2026)
    lr_plateau_multiplier: float = 1.0
    lr_reductions: int = 0

    # Phase history
    phase_history: list[dict[str, Any]] = field(default_factory=list[Any])


class UnifiedCurriculumScheduler:
    """Unified curriculum scheduler combining Adaptive + Fano strengths.

    KEY FEATURES:
    =============
    - 5-phase catastrophe-guided curriculum
    - Gradient-norm + loss-velocity tracking
    - Progressive Fano colony activation (2→3→4→7)
    - Depth curriculum (E8, VQ, Program, Memory)
    - Smooth transitions with 50-step hysteresis
    - Multi-criteria transition detection

    USAGE:
    ======
    ```python
    scheduler = UnifiedCurriculumScheduler(enable_auto_transition=True)

    for step in range(max_steps):
        result = scheduler.step(losses, gradient_norm)

        if result["should_transition"]:
            scheduler.apply_depth_to_model(model)

        weights = scheduler.get_loss_weights()
        loss = compute_weighted_loss(weights)
    ```
    """

    # Fano plane colony activation by phase
    COLONY_ACTIVATION = {
        -1: [1],  # Warmup: Spark only (Jan 5, 2026)
        0: [1, 2],  # Hierarchy: Spark, Forge
        1: [1, 2, 3],  # Rotation: + Flow (Fano line)
        2: [1, 2, 3, 4],  # Dynamics: + Nexus
        3: [1, 2, 3, 4, 5, 6, 7],  # Joint: all colonies
        4: [1, 2, 3, 4, 5, 6, 7],  # Generation: all colonies
        5: [1, 2, 3, 4, 5, 6, 7],  # Language: all colonies (NEW Jan 4, 2026)
    }

    # Default phase configurations
    DEFAULT_PHASES = {
        # === WARMUP PHASE (Jan 5, 2026) ===
        # Pure reconstruction, no KL (β=1e-6 to avoid JAX recompilation)
        # Stabilizes encoder/decoder before VAE training
        CurriculumPhase.WARMUP: PhaseConfig(
            name="Warmup",
            catastrophe_type="none",
            min_steps=500,
            max_steps=2_000,
            loss_threshold=0.1,
            gradient_threshold=0.01,
            velocity_threshold=0.01,
            loss_weights={
                "reconstruction": 1.0,
                "kl": 1e-6,  # NOT 0 — avoid JAX recompilation
                "hierarchy": 0.0,
                "rotation": 0.0,
                "jepa": 0.0,
                "temporal": 0.0,
                "geometric": 0.0,
                "cbf": 0.0,
            },
            data_weights={"jepa": 1.0},  # Simple data only
            lr_multiplier=1.0,
            kl_weight=1e-6,  # NOT 0 — critical for JAX JIT
            plateau_patience=200,  # Shorter during warmup
            e8_depth=1,
            vq_depth=1,
            program_depth=1,
            memory_depth=1,
        ),
        CurriculumPhase.HIERARCHY: PhaseConfig(
            name="Hierarchy",
            catastrophe_type="fold",
            min_steps=1_000,
            max_steps=10_000,
            loss_threshold=0.08,
            gradient_threshold=0.001,
            velocity_threshold=0.001,
            loss_weights={
                "reconstruction": 1.0,
                "kl": 1.0,
                "hierarchy": 1.0,
                "rotation": 0.1,
                "jepa": 0.1,
                "temporal": 0.1,
                "geometric": 0.1,
                "cbf": 0.0,
            },
            # FIX (Dec 28, 2025): Include QM9 + TreeOfLife for SE(3) + hierarchy learning
            data_weights={"jepa": 0.6, "qm9": 0.2, "treeoflife": 0.2},
            lr_multiplier=1.0,
            kl_weight=1.0,  # Full KL after warmup
            plateau_patience=400,  # Increased from 200 (Jan 5, 2026)
            e8_depth=2,
            vq_depth=1,
            program_depth=2,
            memory_depth=1,
        ),
        CurriculumPhase.ROTATION: PhaseConfig(
            name="Rotation",
            catastrophe_type="cusp",
            min_steps=1_000,
            max_steps=15_000,
            loss_threshold=0.05,
            gradient_threshold=0.0005,
            velocity_threshold=0.0005,
            loss_weights={
                "reconstruction": 1.0,
                "kl": 1.0,
                "hierarchy": 0.8,
                "rotation": 1.0,
                "jepa": 0.1,
                "temporal": 0.3,
                "geometric": 0.1,
                "cbf": 0.5,
                "generation": 0.1,
            },
            # FIX (Dec 28, 2025): Include QM9 + TreeOfLife for geometry + hierarchy
            data_weights={"jepa": 0.5, "qm9": 0.2, "treeoflife": 0.2, "generation": 0.1},
            lr_multiplier=1.0,
            e8_depth=4,
            vq_depth=2,
            program_depth=4,
            memory_depth=2,
        ),
        CurriculumPhase.DYNAMICS: PhaseConfig(
            name="Dynamics",
            catastrophe_type="swallowtail",
            min_steps=2_000,
            max_steps=40_000,
            loss_threshold=0.1,
            gradient_threshold=0.0003,
            velocity_threshold=0.0003,
            loss_weights={
                "reconstruction": 1.0,
                "kl": 1.0,
                "hierarchy": 1.0,
                "rotation": 0.1,
                "jepa": 1.0,
                "temporal": 0.5,
                "geometric": 0.1,
                "physics": 0.3,
                "cbf": 1.0,
                "generation": 0.25,
            },
            # FIX (Dec 28, 2025): Include QM9 + TreeOfLife for dynamics + hierarchy
            data_weights={"jepa": 0.45, "qm9": 0.2, "treeoflife": 0.2, "generation": 0.15},
            lr_multiplier=0.8,
            e8_depth=6,
            vq_depth=2,
            program_depth=6,
            memory_depth=4,
        ),
        CurriculumPhase.JOINT: PhaseConfig(
            name="Joint",
            catastrophe_type="butterfly",
            min_steps=5_000,
            max_steps=80_000,
            loss_threshold=0.05,
            gradient_threshold=0.0002,
            velocity_threshold=0.0002,
            loss_weights={
                "reconstruction": 1.0,
                "kl": 1.0,
                "hierarchy": 1.0,
                "rotation": 1.0,
                "jepa": 1.0,
                "temporal": 0.8,
                "geometric": 0.1,
                "physics": 0.2,
                "cbf": 1.5,
                "generation": 0.5,
            },
            # FIX (Dec 28, 2025): Include QM9 + TreeOfLife for joint training
            data_weights={"jepa": 0.35, "qm9": 0.15, "treeoflife": 0.15, "generation": 0.35},
            lr_multiplier=0.5,
            e8_depth=8,
            vq_depth=3,
            program_depth=8,
            memory_depth=6,
        ),
        CurriculumPhase.GENERATION: PhaseConfig(
            name="Generation",
            catastrophe_type="hyperbolic",
            min_steps=5_000,
            max_steps=120_000,
            loss_threshold=0.01,
            gradient_threshold=0.0001,
            velocity_threshold=0.0001,
            loss_weights={
                "reconstruction": 1.0,
                "kl": 1.0,
                "hierarchy": 0.3,
                "rotation": 0.3,
                "jepa": 0.5,
                "temporal": 1.0,
                "geometric": 0.1,
                "cbf": 2.0,
                "generation": 1.0,
            },
            # FIX (Dec 28, 2025): Maintain QM9 + TreeOfLife in generation phase
            data_weights={"generation": 0.5, "jepa": 0.25, "qm9": 0.15, "treeoflife": 0.1},
            lr_multiplier=0.3,
            e8_depth=16,
            vq_depth=4,
            program_depth=16,
            memory_depth=8,
        ),
        # === LANGUAGE PHASE (Jan 4, 2026) ===
        # Elliptic catastrophe (D₄⁻) for inward language grounding
        # Focus: WM ↔ text alignment, caption generation, instruction-following
        CurriculumPhase.LANGUAGE: PhaseConfig(
            name="Language",
            catastrophe_type="elliptic",
            min_steps=10_000,
            max_steps=150_000,
            loss_threshold=0.05,
            gradient_threshold=0.0001,
            velocity_threshold=0.0001,
            loss_weights={
                "reconstruction": 0.5,  # Reduced - focus on language
                "kl": 0.5,
                "hierarchy": 0.2,
                "rotation": 0.2,
                "jepa": 0.3,
                "temporal": 0.5,
                "geometric": 0.1,
                "cbf": 1.0,
                "generation": 0.5,
                # Language-specific losses (NEW)
                "language_grounding": 1.0,  # Contrastive WM ↔ text
                "language_caption": 1.0,  # WM → text generation
                "language_generation": 0.5,  # VL-JEPA embedding prediction
            },
            # Data weights for language phase
            data_weights={
                "jepa": 0.3,  # Genesis with captions
                "language_corpus": 0.3,  # Text-only pretraining
                "instruction": 0.2,  # Instruction-following
                "qm9": 0.1,  # Maintain SE(3)
                "treeoflife": 0.1,  # Maintain hierarchy
            },
            lr_multiplier=0.2,  # Lower LR for fine-tuning
            e8_depth=16,  # Maintain full depth
            vq_depth=4,
            program_depth=16,
            memory_depth=8,
        ),
    }

    def __init__(
        self,
        base_lr: float = 1e-4,
        enable_auto_transition: bool = True,
        enable_early_generation: bool = True,
        transition_cooldown: int = 50,  # Hysteresis: 50 steps
        gradient_norm_ema_decay: float = 0.95,
        loss_history_window: int = 100,
        phases: dict[CurriculumPhase, PhaseConfig] | None = None,
    ) -> None:
        """Initialize unified curriculum scheduler.

        Args:
            base_lr: Base learning rate
            enable_auto_transition: Enable automatic phase transitions
            enable_early_generation: Enable generation from ROTATION phase
            transition_cooldown: Steps to wait after transition (hysteresis)
            gradient_norm_ema_decay: EMA decay for gradient norm tracking
            loss_history_window: Window size for loss smoothing
            phases: Custom phase configurations (or None for defaults)
        """
        self.base_lr = base_lr
        self.enable_auto_transition = enable_auto_transition
        self.enable_early_generation = enable_early_generation
        self.transition_cooldown = transition_cooldown
        self.gradient_norm_ema_decay = gradient_norm_ema_decay
        self.loss_history_window = loss_history_window

        # Use custom or default phases
        self.phases = phases or self.DEFAULT_PHASES.copy()

        # Enable early generation if requested
        if enable_early_generation:
            self._enable_early_generation()

        # Current state
        self.state = CurriculumState()

        # Loss history (bounded deque[Any] for memory efficiency)
        self.loss_history: deque[float] = deque(maxlen=loss_history_window * 2)

        # Gradient history (for velocity computation)
        self.gradient_history: deque[float] = deque(maxlen=loss_history_window)

        # Catastrophe-specific metric histories
        self._reconstruction_history: deque[float] = deque(maxlen=100)
        self._alignment_history: deque[float] = deque(maxlen=100)
        self._complexity_history: deque[float] = deque(maxlen=100)

        # Catastrophe detector (extracted for modularity)
        self.detector = CurriculumCatastropheDetector(
            reconstruction_history=self._reconstruction_history,
            alignment_history=self._alignment_history,
            complexity_history=self._complexity_history,
            loss_history=self.loss_history,
        )

        logger.info(
            f"✅ UnifiedCurriculumScheduler initialized: "
            f"phases=5, auto_transition={enable_auto_transition}, "
            f"early_generation={enable_early_generation}, "
            f"cooldown={transition_cooldown}"
        )

    def _enable_early_generation(self) -> None:
        """Enable generation training from ROTATION phase onwards."""
        # Already enabled in DEFAULT_PHASES, but this can be customized
        logger.debug("✅ Early generation enabled in unified curriculum")

    @property
    def current_phase(self) -> CurriculumPhase:
        """Get current training phase."""
        return self.state.phase

    @property
    def current_config(self) -> PhaseConfig:
        """Get current phase configuration."""
        return self.phases[self.state.phase]

    def step(
        self,
        losses: dict[str, float],
        gradient_norm: float | None = None,
        *,
        step_increment: int = 1,
    ) -> dict[str, Any]:
        """Update curriculum based on current losses and gradients.

        Args:
            losses: Dict of loss values (reconstruction, kl, jepa, total, etc.)
            gradient_norm: Optional gradient norm for transition detection
            step_increment: Number of steps to increment (default: 1)

        Returns:
            Dict with current curriculum state and any updates:
                - phase: CurriculumPhase enum
                - phase_name: str
                - phase_step: int
                - total_step: int
                - phase_loss: float
                - phase_best_loss: float
                - plateau_count: int
                - should_transition: bool
                - e8_depth: int
                - vq_depth: int
                - program_depth: int
                - memory_depth: int
                - gradient_norm_ema: float
                - loss_velocity: float
        """
        step_inc = max(1, int(step_increment))
        self.state.phase_step += step_inc
        self.state.total_step += step_inc

        # Get relevant loss for current phase
        phase_loss = self._get_phase_loss(losses)
        self.loss_history.append(phase_loss)

        # Update gradient tracking
        if gradient_norm is not None:
            self.gradient_history.append(gradient_norm)
            # EMA update
            self.state.gradient_norm_ema = (
                self.gradient_norm_ema_decay * self.state.gradient_norm_ema
                + (1 - self.gradient_norm_ema_decay) * gradient_norm
            )

        # Update loss velocity (rate of change)
        if len(self.loss_history) >= 2:
            recent = list(self.loss_history)[-min(10, len(self.loss_history)) :]
            if len(recent) >= 2:
                self.state.loss_velocity = (recent[-1] - recent[0]) / len(recent)

        # Update catastrophe-specific metrics
        self._update_catastrophe_metrics(losses)

        # Check for improvement
        if phase_loss < self.state.phase_best_loss:
            self.state.phase_best_loss = phase_loss
            self.state.plateau_count = 0
        else:
            self.state.plateau_count += step_inc

        # Check for plateau and reduce LR if needed (Jan 5, 2026)
        lr_reduced = self.check_plateau_and_reduce_lr()

        # Get depth config
        depths = self.get_depth_config()

        # Build result
        result = {
            "phase": self.state.phase,
            "phase_name": PHASE_NAMES[self.state.phase],
            "phase_step": self.state.phase_step,
            "total_step": self.state.total_step,
            "phase_loss": phase_loss,
            "phase_best_loss": self.state.phase_best_loss,
            "plateau_count": self.state.plateau_count,
            "should_transition": False,
            "e8_depth": depths["e8_depth"],
            "vq_depth": depths["vq_depth"],
            "program_depth": depths["program_depth"],
            "memory_depth": depths["memory_depth"],
            "gradient_norm_ema": self.state.gradient_norm_ema,
            "loss_velocity": self.state.loss_velocity,
            # KL annealing & LR plateau (Jan 5, 2026)
            "kl_weight": self.get_kl_weight(),
            "lr_plateau_multiplier": self.state.lr_plateau_multiplier,
            "lr_reduced": lr_reduced,
            "lr_reductions": self.state.lr_reductions,
            "learning_rate": self.get_learning_rate(),
        }

        # Check for phase transition
        if self.enable_auto_transition:
            should_transition, reason = self._should_transition(phase_loss)
            if should_transition:
                old_phase = self.state.phase
                self._transition_to_next_phase(reason)
                result["should_transition"] = True
                result["transition_from"] = old_phase
                result["transition_to"] = self.state.phase
                result["transition_reason"] = reason

        return result

    def _get_phase_loss(self, losses: dict[str, float]) -> float:
        """Get the primary loss for current phase."""
        if self.state.phase == CurriculumPhase.HIERARCHY:
            return losses.get(
                "hierarchy",
                losses.get(
                    "hierarchy_loss", losses.get("reconstruction", losses.get("total", 0.0))
                ),
            )
        elif self.state.phase == CurriculumPhase.ROTATION:
            return losses.get("rotation", losses.get("rotation_loss", losses.get("total", 0.0)))
        elif self.state.phase == CurriculumPhase.DYNAMICS:
            return losses.get(
                "jepa", losses.get("jepa_loss", losses.get("temporal", losses.get("total", 0.0)))
            )
        else:
            return losses.get("total", 0.0)

    def _update_catastrophe_metrics(self, losses: dict[str, float]) -> None:
        """Update metric histories for catastrophe detection."""
        # Reconstruction (all phases)
        if "reconstruction" in losses:
            self._reconstruction_history.append(float(losses["reconstruction"]))
        elif "reconstruction_loss" in losses:
            self._reconstruction_history.append(float(losses["reconstruction_loss"]))

        # Alignment (phase 3+)
        if self.state.phase >= CurriculumPhase.DYNAMICS:
            if "alignment" in losses:
                self._alignment_history.append(float(losses["alignment"]))
            elif "alignment_loss" in losses:
                self._alignment_history.append(float(losses["alignment_loss"]))

        # Task complexity (phase 4+)
        if self.state.phase >= CurriculumPhase.JOINT:
            if "task_complexity" in losses:
                self._complexity_history.append(float(losses["task_complexity"]))

    def _should_transition(self, current_loss: float) -> tuple[bool, str]:
        """Determine if should transition to next phase.

        Multi-criteria transition detection:
        1. Minimum steps reached
        2. Catastrophe condition detected
        3. Gradient norm converged
        4. Loss velocity stable

        Args:
            current_loss: Current phase loss value

        Returns:
            (should_transition, reason)
        """
        config = self.current_config

        # Cooldown: prevent rapid transitions
        if self.state.phase_step < self.transition_cooldown:
            return False, ""

        # Not enough steps yet
        if self.state.phase_step < config.min_steps:
            return False, ""

        # Maximum steps reached (forced transition)
        if self.state.phase_step >= config.max_steps:
            return True, f"max_steps ({self.state.phase_step} >= {config.max_steps})"

        # Catastrophe detection (phase-specific)
        catastrophe_detected, catastrophe_reason = self._detect_catastrophe()

        # Gradient convergence check
        gradient_converged = (
            self.state.gradient_norm_ema < config.gradient_threshold
            and len(self.gradient_history) >= 10
        )

        # Velocity stability check
        velocity_stable = (
            abs(self.state.loss_velocity) < config.velocity_threshold
            and len(self.loss_history) >= 20
        )

        # ALL criteria must be met for transition
        if catastrophe_detected and gradient_converged and velocity_stable:
            reason = (
                f"{catastrophe_reason}, "
                f"gradient_converged ({self.state.gradient_norm_ema:.6f} < {config.gradient_threshold}), "
                f"velocity_stable ({self.state.loss_velocity:.6f} < {config.velocity_threshold})"
            )
            return True, reason

        return False, ""

    def _detect_catastrophe(self) -> tuple[bool, str]:
        """Detect catastrophe type for current phase.

        Delegates to CurriculumCatastropheDetector for phase-specific detection.

        Returns:
            (detected, reason)
        """
        return self.detector.detect_catastrophe(
            phase=self.state.phase,
            config=self.current_config,
        )

    def _transition_to_next_phase(self, reason: str) -> None:
        """Transition to the next curriculum phase."""
        old_phase = self.state.phase
        old_depths = self.get_depth_config()

        # Record history
        self.state.phase_history.append(
            {
                "phase": old_phase,
                "phase_name": PHASE_NAMES[old_phase],
                "steps": self.state.phase_step,
                "best_loss": self.state.phase_best_loss,
                "reason": reason,
                "depths": old_depths,
            }
        )

        # Move to next phase (if not terminal)
        if self.state.phase < CurriculumPhase.GENERATION:
            self.state.phase = CurriculumPhase(self.state.phase + 1)

        # Reset phase state
        self.state.phase_step = 0
        self.state.phase_best_loss = float("inf")
        self.state.plateau_count = 0
        # Reset LR plateau on phase transition (Jan 5, 2026)
        self.state.lr_plateau_multiplier = 1.0

        # Get new depths
        new_depths = self.get_depth_config()

        logger.info(
            f"🔄 Curriculum transition: {PHASE_NAMES[old_phase]} → {PHASE_NAMES[self.state.phase]}\n"
            f"   Reason: {reason}\n"
            f"   Depths: e8={old_depths['e8_depth']}→{new_depths['e8_depth']}, "
            f"vq={old_depths['vq_depth']}→{new_depths['vq_depth']}, "
            f"program={old_depths['program_depth']}→{new_depths['program_depth']}, "
            f"memory={old_depths['memory_depth']}→{new_depths['memory_depth']}\n"
            f"   Colonies: {len(self.get_active_colonies())}"
        )

    def get_loss_weights(self) -> dict[str, float]:
        """Get current loss component weights.

        KL ANNEALING (Jan 5, 2026):
        ===========================
        The 'kl' weight in the returned dict is scaled by the phase's kl_weight.
        During WARMUP, this is 1e-6 (not 0) to avoid JAX recompilation.
        """
        weights = self.current_config.loss_weights.copy()
        # Apply phase-specific KL weight
        if "kl" in weights:
            weights["kl"] = weights["kl"] * self.current_config.kl_weight
        return weights

    def get_kl_weight(self) -> float:
        """Get current KL divergence weight (β).

        Returns:
            KL weight (1e-6 during WARMUP, 1.0 during other phases)

        Note:
            Uses 1e-6 instead of 0 during WARMUP to avoid JAX graph recompilation.
        """
        return self.current_config.kl_weight

    def get_data_weights(self) -> dict[str, float]:
        """Get current data source weights."""
        return self.current_config.data_weights.copy()

    def get_learning_rate(self) -> float:
        """Get current learning rate (base * phase_multiplier * plateau_multiplier).

        LR PLATEAU (Jan 5, 2026):
        =========================
        LR is now also scaled by lr_plateau_multiplier, which decays when
        plateau_count exceeds plateau_patience.
        """
        return self.base_lr * self.current_config.lr_multiplier * self.state.lr_plateau_multiplier

    def check_plateau_and_reduce_lr(self) -> bool:
        """Check if plateau detected and reduce LR if needed.

        Returns:
            True if LR was reduced, False otherwise

        Plateau Detection (Jan 5, 2026):
        =================================
        If plateau_count exceeds plateau_patience, reduce lr_plateau_multiplier by 0.5.
        """
        if self.state.plateau_count >= self.current_config.plateau_patience:
            if self.state.lr_plateau_multiplier > 0.01:  # Floor at 1% of base
                self.state.lr_plateau_multiplier *= 0.5
                self.state.lr_reductions += 1
                self.state.plateau_count = 0
                logger.info(
                    f"⚠️ Plateau detected! Reducing LR multiplier to "
                    f"{self.state.lr_plateau_multiplier:.4f} (reduction #{self.state.lr_reductions})"
                )
                return True
        return False

    def get_depth_config(self) -> dict[str, int]:
        """Get current depth configuration for all modules.

        Returns dict[str, Any] with:
        - e8_depth: SemanticResidualE8 levels
        - vq_depth: E8VQ levels
        - program_depth: UnifiedDNAProgramLibrary levels
        - memory_depth: EpisodicMemory levels
        """
        config = self.current_config
        return {
            "e8_depth": config.e8_depth,
            "vq_depth": config.vq_depth,
            "program_depth": config.program_depth,
            "memory_depth": config.memory_depth,
        }

    def get_active_colonies(self) -> list[int]:
        """Get list[Any] of active colony indices for current phase.

        Returns:
            List of colony indices (1-7)
        """
        return self.COLONY_ACTIVATION.get(self.state.phase, [1, 2])

    def get_planning_depth(self) -> int:
        """Get recommended planning depth for current phase.

        Returns:
            Planning depth (number of steps)
        """
        planning_depths = {
            0: 1,  # Hierarchy: no planning
            1: 3,  # Rotation: short horizon
            2: 5,  # Dynamics: medium horizon
            3: 11,  # Joint: long horizon
            4: 16,  # Generation: maximum horizon
        }
        return planning_depths.get(self.state.phase, 1)

    def get_catastrophe_type(self) -> str:
        """Get catastrophe type for current phase."""
        return CATASTROPHE_TYPES.get(self.state.phase, "fold")

    def apply_depth_to_model(self, model: KagamiWorldModel) -> dict[str, int]:
        """Apply current depth configuration to a world model.

        Updates training_levels on all relevant submodules:
        - model.unified_hourglass (E8 residual)
        - model._unified_library (ProgramLibrary)
        - model._episodic_memory (EpisodicMemory)
        - External VQ modules (via return value)

        Args:
            model: KagamiWorldModel or similar with depth-configurable modules

        Returns:
            Dict of applied depths per module (includes vq_depth for external use)
        """
        depths = self.get_depth_config()
        applied = {}

        # Update E8 residual depth
        if hasattr(model, "unified_hourglass") and hasattr(model.unified_hourglass, "config"):
            cfg = model.unified_hourglass.config
            if hasattr(cfg, "training_levels"):
                cfg.training_levels = int(depths["e8_depth"])
                if hasattr(cfg, "inference_levels"):
                    cfg.inference_levels = max(
                        int(getattr(cfg, "inference_levels", cfg.training_levels)),
                        cfg.training_levels,
                    )
                applied["e8"] = int(depths["e8_depth"])

        # Update ProgramLibrary depth
        if hasattr(model, "_unified_library") and model._unified_library is not None:
            lib = model._unified_library
            if hasattr(lib, "config") and hasattr(lib.config, "training_levels"):
                max_levels = int(getattr(lib.config, "max_levels", depths["program_depth"]))
                new_levels = max(1, min(int(depths["program_depth"]), max_levels))
                lib.config.training_levels = new_levels
                if hasattr(lib.config, "inference_levels"):
                    lib.config.inference_levels = new_levels
                applied["program"] = new_levels

        # Update EpisodicMemory
        if hasattr(model, "_episodic_memory") and model._episodic_memory is not None:
            model._episodic_memory.config.training_levels = depths["memory_depth"]
            applied["memory"] = depths["memory_depth"]

        # Pass through VQ depth for external modules
        applied["vq"] = depths["vq_depth"]

        if applied:
            logger.debug(
                f"📊 Applied depth curriculum: e8={applied.get('e8', '?')}, "
                f"vq={applied.get('vq', '?')}, "
                f"program={applied.get('program', '?')}, "
                f"memory={applied.get('memory', '?')}"
            )

        return applied

    def force_transition(self, target_phase: CurriculumPhase) -> None:
        """Force transition to a specific phase."""
        old_phase = self.state.phase
        self.state.phase_history.append(
            {
                "phase": old_phase,
                "phase_name": PHASE_NAMES[old_phase],
                "steps": self.state.phase_step,
                "best_loss": self.state.phase_best_loss,
                "reason": f"forced_to_{PHASE_NAMES[target_phase]}",
            }
        )

        self.state.phase = target_phase
        self.state.phase_step = 0
        self.state.phase_best_loss = float("inf")
        self.state.plateau_count = 0

        logger.info(
            f"⚡ Forced curriculum transition: {PHASE_NAMES[old_phase]} → {PHASE_NAMES[target_phase]}"
        )

    def get_state(self) -> dict[str, Any]:
        """Get scheduler state for checkpointing."""
        return {
            "phase": self.state.phase.value,
            "phase_step": self.state.phase_step,
            "total_step": self.state.total_step,
            "phase_best_loss": self.state.phase_best_loss,
            "plateau_count": self.state.plateau_count,
            "gradient_norm_ema": self.state.gradient_norm_ema,
            "loss_velocity": self.state.loss_velocity,
            "phase_history": self.state.phase_history,
            "loss_history": list(self.loss_history)[-1000:],
            "gradient_history": list(self.gradient_history)[-1000:],
        }

    def load_state(self, state: dict[str, Any]) -> None:
        """Load scheduler state from checkpoint."""
        self.state.phase = CurriculumPhase(state.get("phase", 0))
        self.state.phase_step = state.get("phase_step", 0)
        self.state.total_step = state.get("total_step", 0)
        self.state.phase_best_loss = state.get("phase_best_loss", float("inf"))
        self.state.plateau_count = state.get("plateau_count", 0)
        self.state.gradient_norm_ema = state.get("gradient_norm_ema", 1.0)
        self.state.loss_velocity = state.get("loss_velocity", 0.0)
        self.state.phase_history = state.get("phase_history", [])

        # Restore histories
        self.loss_history = deque(
            state.get("loss_history", []), maxlen=self.loss_history_window * 2
        )
        self.gradient_history = deque(
            state.get("gradient_history", []), maxlen=self.loss_history_window
        )

        logger.info(
            f"✅ UnifiedCurriculumScheduler state loaded: "
            f"step={self.state.total_step}, phase={PHASE_NAMES[self.state.phase]}"
        )

    def state_dict(self) -> dict[str, Any]:
        """PyTorch-compatible state dict for checkpointing.

        Alias for get_state() to match PyTorch conventions.
        """
        return self.get_state()

    def load_state_dict(self, state: dict[str, Any]) -> None:
        """PyTorch-compatible state dict loading.

        Alias for load_state() to match PyTorch conventions.
        """
        self.load_state(state)

    def get_summary(self) -> str:
        """Get human-readable summary of curriculum progress."""
        depths = self.get_depth_config()
        colonies = self.get_active_colonies()

        lines = [
            f"📚 Unified Curriculum Progress (Step {self.state.total_step})",
            f"   Phase: {PHASE_NAMES[self.state.phase]} ({self.get_catastrophe_type()})",
            f"   Phase Step: {self.state.phase_step}",
            f"   Best Loss: {self.state.phase_best_loss:.6f}",
            f"   Plateau: {self.state.plateau_count} steps",
            f"   LR: {self.get_learning_rate():.2e}",
            f"   Gradient EMA: {self.state.gradient_norm_ema:.6f}",
            f"   Loss Velocity: {self.state.loss_velocity:.6f}",
            f"   Depths: e8={depths['e8_depth']}, vq={depths['vq_depth']}, "
            f"program={depths['program_depth']}, memory={depths['memory_depth']}",
            f"   Active Colonies: {len(colonies)} {colonies}",
        ]

        if self.state.phase_history:
            lines.append("   History:")
            for h in self.state.phase_history[-3:]:
                lines.append(
                    f"     - {h['phase_name']}: {h['steps']} steps, "
                    f"loss={h['best_loss']:.4f} ({h['reason']})"
                )

        return "\n".join(lines)


__all__ = [
    "CATASTROPHE_TYPES",
    "PHASE_NAMES",
    "CurriculumPhase",
    "CurriculumState",
    "PhaseConfig",
    "UnifiedCurriculumScheduler",
]
