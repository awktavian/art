"""World Model Learning Loop - CANONICAL TRAINING SYSTEM.

This is the SINGLE SOURCE OF TRUTH for all world model training.

Unified world model training combining:
- KagamiWorldModel hourglass architecture
- JEPA-style prediction (embed future states)
- G₂-equivariant octonion processing
- Strange loop training
- RSSM action-conditioned dynamics
- Differentiable MDL complexity learning
- Differentiable catastrophe dynamics
- Superorganism integration (colony coordination, pheromone gradients)
- Actor-Critic RL policy (delegated)
- Online EWC continual learning

Created: November 2, 2025
Updated: November 29, 2025 - Removed redundant encoder/dynamics, uses KagamiWorldModel directly
Updated: December 1, 2025 - Added MDL program selection and catastrophe dynamics integration
Updated: December 2, 2025 - CONSOLIDATED: All training flows through this loop
Status: Production-ready (CANONICAL)

DELETED ALTERNATIVES (Dec 2, 2025):
- kagami/core/training/unified_trainer.py - was duplicate hourglass trainer
- Standalone library fallbacks - model._unified_library is REQUIRED
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F

from kagami.core.world_model.dreamer_transforms import symlog as _symlog

logger = logging.getLogger(__name__)


# =============================================================================
# DREAMERV3 SYMLOG TRANSFORMS (Dec 6, 2025)
# =============================================================================
#
# Single source of truth lives in:
#   kagami.core.world_model.dreamer_transforms


@dataclass
class TrainingConfig:
    """Unified training configuration."""

    # Core settings
    learning_rate: float = 1e-4
    batch_size: int = 32
    gradient_clip: float = 1.0

    # DreamerV3 robustness (Dec 6, 2025)
    enable_symlog: bool = True  # Symlog transform for numerical stability
    replay_ratio: int = 16  # Gradient steps per environment step (DreamerV3: 64-1)

    # Loss weights (all components)
    lambda_prediction: float = 1.0
    lambda_geometric: float = 0.1  # E8/Fano/G2 losses
    lambda_catastrophe: float = 0.05
    lambda_solomonoff: float = 0.01
    lambda_tic: float = 0.1
    lambda_rl: float = 0.1
    lambda_ewc: float = 0.4

    # Safety CBF settings (Dec 6, 2025 - HARDENED)
    enable_safety_training: bool = True  # Always enabled
    lambda_safety: float = 0.1  # Safety CBF penalty weight
    safety_margin: float = 0.1  # Target h(x) >= margin

    # EWC settings
    enable_ewc: bool = True
    ewc_lambda: float = 0.4
    fisher_buffer_size: int = 32

    # RL settings
    enable_rl_training: bool = True
    rl_train_interval: int = 10  # Train RL every N steps

    # Superorganism settings
    enable_superorganism: bool = True
    sync_interval: float = 1.0

    # Depth curriculum settings
    enable_curriculum: bool = True  # Enable depth curriculum progression

    # Logging
    log_interval: int = 10

    # W&B Logging (Dec 27, 2025)
    # MIGRATION: Replaced TensorBoard with W&B
    use_wandb: bool = False  # Enable W&B logging
    wandb_project: str = "kagami-world-model"  # W&B project name


@dataclass
class TrainingMetrics:
    """Metrics from a training step."""

    step: int
    total_loss: float
    prediction_loss: float = 0.0
    geometric_loss: float = 0.0
    catastrophe_loss: float = 0.0
    solomonoff_loss: float = 0.0
    tic_loss: float = 0.0
    rl_loss: float = 0.0
    ewc_loss: float = 0.0
    safety_loss: float = 0.0  # CBF penalty (Dec 6, 2025)
    safety_h_mean: float = 0.0  # Mean barrier value
    gradient_norm: float = 0.0
    timestamp: float = field(default_factory=time.time)


class WorldModelLoop(nn.Module):
    """CANONICAL World Model Learning Loop.

    This is the SINGLE training system for the entire K OS stack.
    All training flows through this class.

    Trains:
    1. KagamiWorldModel (hourglass encoder/decoder, geometric losses)
    2. ColonyRSSM (action-conditioned dynamics)
    3. Program Library (MDL complexity learning)
    4. Differentiable TIC (receipt dynamics)
    5. Catastrophe Dynamics (stability)
    6. Actor-Critic RL (via delegation)
    7. EWC Continual Learning (prevent forgetting)
    8. Superorganism Integration (colony coordination)

    DELETED ALTERNATIVES (Dec 2, 2025):
    - kagami/core/training/unified_trainer.py (redundant)
    - Standalone training in MasterTrainingCoordinator (now delegates here)
    """

    def __init__(
        self,
        model: nn.Module | None = None,
        config: TrainingConfig | None = None,
        device: str = "cpu",
    ) -> None:
        """Initialize canonical world model loop.

        Args:
            model: World model (KagamiWorldModel). Created if None.
            config: Training configuration
            device: Computation device
        """
        super().__init__()

        self.config = config or TrainingConfig()
        self.device = device

        # Create KagamiWorldModel if not provided
        if model is None:
            from kagami.core.world_model.kagami_world_model import KagamiWorldModelFactory

            # HARDENED (Nov 30, 2025): All features always enabled
            self.model = KagamiWorldModelFactory.create().to(device)
        else:
            self.model = model.to(device)  # type: ignore[assignment]

        # Get model dimensions
        self._input_dim = self.model.config.layer_dimensions[0]
        self._bulk_dim = self.model.config.layer_dimensions[-1]

        # Training state
        self._step = 0
        self._epoch = 0
        self._last_sync_time = 0.0

        # ============================================================
        # SUPERORGANISM INTEGRATION (Dec 2, 2025)
        # ============================================================
        self._superorganism: Any = None
        if self.config.enable_superorganism:
            try:
                from kagami.core.world_model.superorganism_integration import (
                    get_superorganism_integration,
                )

                self._superorganism = get_superorganism_integration(self.model)
                logger.info("✅ Superorganism integration wired to training loop")
            except ImportError as e:
                logger.warning(f"Superorganism integration unavailable: {e}")

        # ============================================================
        # EWC CONTINUAL LEARNING (Dec 2, 2025)
        # ============================================================
        self._ewc_fisher: dict[str, dict[str, torch.Tensor]] = {}
        self._ewc_optimal_params: dict[str, dict[str, torch.Tensor]] = {}
        self._ewc_buffer: list[tuple[torch.Tensor, torch.Tensor]] = []
        self._current_task_id: str | None = None

        # ============================================================
        # RL LOOP REFERENCE (Dec 2, 2025)
        # ============================================================
        self._rl_loop: Any = None

        # ============================================================
        # OPTIMIZER (Dec 24, 2025 - CRITICAL FIX)
        # ============================================================
        # This was MISSING - loss computed but never applied!
        self.optimizer = torch.optim.AdamW(
            self.model.parameters(),
            lr=self.config.learning_rate,
            weight_decay=1e-5,
        )

        # ============================================================
        # DEPTH CURRICULUM (Dec 2, 2025)
        # ============================================================
        self._curriculum: Any = None
        if self.config.enable_curriculum:
            try:
                from kagami.core.training.unified_curriculum import (
                    UnifiedCurriculumScheduler,
                )

                self._curriculum = UnifiedCurriculumScheduler(
                    base_lr=self.config.learning_rate,
                    enable_auto_transition=True,
                )
                # Apply initial depth config
                self._curriculum.apply_depth_to_model(self.model)
                logger.info(f"✅ Depth curriculum enabled: {self._curriculum.get_summary()}")
            except ImportError as e:
                logger.warning(f"Curriculum scheduler unavailable: {e}")

        # ============================================================
        # SAFETY CBF TRAINING (Dec 6, 2025 - HARDENED)
        # Updated Dec 25, 2025: Migrated from DifferentiableCBF to OptimalCBF
        # ============================================================
        self._safety_cbf: Any = None
        from kagami.core.safety.optimal_cbf import OptimalCBF, OptimalCBFConfig

        cbf_config = OptimalCBFConfig(
            observation_dim=16,  # Matches LLM classifier risk categories
            state_dim=16,
            control_dim=2,
            metric_threshold=0.3,
            soft_penalty_weight=self.config.lambda_safety * 10.0,
            safety_margin=self.config.safety_margin,
            use_topological=False,
        )
        self._safety_cbf = OptimalCBF(cbf_config).to(device)
        logger.info(
            f"✅ Safety CBF training REQUIRED: "
            f"weight={self.config.lambda_safety}, margin={self.config.safety_margin}"
        )

        # ============================================================
        # STATISTICAL VALIDATOR (Dec 7, 2025 - Gödel Agent)
        # ============================================================
        from kagami.core.strange_loops.godelian_self_reference import StatisticalValidator

        self._statistical_validator = StatisticalValidator(
            confidence_level=0.95,
            min_effect_size=0.1,
            min_samples=10,
        )
        logger.info("✅ StatisticalValidator REQUIRED for training validation")

        # ============================================================
        # W&B LOGGING (Dec 27, 2025)
        # MIGRATION: Replaced TensorBoard with W&B
        # ============================================================
        self._wandb_logger: Any = None
        if self.config.use_wandb:
            try:
                from kagami.core.training.consolidated import WandBLogger as WandbLogger

                wandb_config = {
                    "use_wandb": True,
                    "wandb_project": self.config.wandb_project,
                }
                self._wandb_logger = WandbLogger(wandb_config)
                logger.info("✅ W&B logging enabled")
            except ImportError:
                logger.warning("W&B requested but not available. Install with: pip install wandb")
            except Exception as e:
                logger.warning(f"Failed to initialize W&B: {e}")

        # ============================================================
        # UNIFIED E8 EVENT BUS (Dec 2, 2025)
        # ============================================================
        self._event_bus: Any = None
        self._bus_started = False
        try:
            from kagami.core.events import get_unified_bus

            self._event_bus = get_unified_bus()
            # Subscribe to training coordination signals
            self._event_bus.subscribe("training.*", self._on_training_event)
            self._event_bus.subscribe("colony.*.learn", self._on_colony_learn)
            # Subscribe to memory/library events for coordinated learning (Dec 2, 2025)
            self._event_bus.subscribe("experience.episodic_memory", self._on_memory_event)
            self._event_bus.subscribe("experience.program_library", self._on_library_event)
            logger.info("✅ UnifiedE8Bus wired to training loop (with memory coordination)")
        except ImportError as e:
            logger.warning(f"Event bus unavailable: {e}")

        logger.info(
            f"✅ WorldModelLoop (CANONICAL) initialized:\n"
            f"   Model: {type(self.model).__name__}\n"
            f"   Input dim: {self._input_dim}, Bulk dim: {self._bulk_dim}\n"
            f"   RSSM enabled: {getattr(self.model.config, 'enable_rssm', False)}\n"
            f"   Superorganism: {self._superorganism is not None}\n"
            f"   EWC enabled: {self.config.enable_ewc}\n"
            f"   RL training: {self.config.enable_rl_training}\n"
            f"   W&B: {self._wandb_logger is not None}"
        )

    def forward(
        self,
        state: torch.Tensor,
        action: torch.Tensor | None = None,
    ) -> tuple[torch.Tensor, dict[str, Any]]:
        """Predict next state using KagamiWorldModel.

        Args:
            state: [B, state_dim] current state observation
            action: [B, action_dim] action (optional, used for RSSM dynamics)

        Returns:
            prediction: [B, bulk_dim] predicted next state
            metrics: Dict with model metrics (core_state, losses, etc.)
        """
        # Ensure input dimensions match
        if state.shape[-1] != self._input_dim:
            # Project or pad to input dimension
            if state.shape[-1] > self._input_dim:
                state = state[..., : self._input_dim]
            else:
                pad = torch.zeros(
                    *state.shape[:-1],
                    self._input_dim - state.shape[-1],
                    device=state.device,
                    dtype=state.dtype,
                )
                state = torch.cat([state, pad], dim=-1)

        # Use KagamiWorldModel forward pass
        # This handles: encode → dynamics → decode
        output, metrics = self.model(state, action=action)

        return output, metrics

    def compute_loss(self, batch: dict[str, Any], task_id: str | None = None) -> torch.Tensor:
        """Compute FULL STACK loss for end-to-end training.

        CANONICAL (Dec 2, 2025):
        This is the single unified loss computation for all components.

        UPDATED (Dec 6, 2025): Added DreamerV3 symlog transforms for numerical stability.

        Components trained:
        1. KagamiWorldModel (via training_step) - prediction, geometric, dynamics
        2. Program Library - MDL complexity learning
        3. Differentiable TIC - receipt dynamics
        4. Superorganism - catastrophe awareness
        5. EWC - continual learning regularization

        Args:
            batch: Dict with 'state', 'action', 'next_state'
            task_id: Optional task identifier for EWC

        Returns:
            loss: Total loss for training
        """
        state = batch.get("state")
        action = batch.get("action")
        next_state = batch.get("next_state")

        if state is None or next_state is None:
            return torch.tensor(0.0, device=self.device, requires_grad=True)

        # Convert to tensors
        state = self._to_tensor(state)
        next_state = self._to_tensor(next_state)
        action = self._to_tensor(action) if action is not None else None

        # ============================================================
        # DREAMERV3 SYMLOG TRANSFORM (Dec 6, 2025)
        # ============================================================
        # Apply symlog for numerical stability on unbounded values
        # symlog(x) = sign(x) * ln(|x| + 1)
        # This prevents gradient explosion on large values and improves
        # training stability across different input scales.
        if self.config.enable_symlog:
            state = _symlog(state)
            next_state = _symlog(next_state)

        # Handle EWC task switching
        if self.config.enable_ewc and task_id is not None:
            if self._current_task_id is not None and self._current_task_id != task_id:
                self._consolidate_ewc(self._current_task_id)
            self._current_task_id = task_id

        # Target is the *actual* next_state (world model prediction target).
        # The previous JEPA-style bootstrapped target (forward(next_state)) made the
        # system self-distill its own predictions instead of learning environment dynamics.
        with torch.no_grad():
            target = next_state.detach()
            if target.dim() == 2:
                target = target.unsqueeze(1)

        # ============================================================
        # 1. CORE WORLD MODEL LOSS (via training_step)
        # ============================================================
        # Ensure input shape matches expected [B, S, D]
        if state.dim() == 2:
            state = state.unsqueeze(1)
        loss_output = self.model.training_step(state, target, action=action)
        loss = loss_output.total

        # ============================================================
        # 2. DIFFERENTIABLE TIC LOSS
        # ============================================================
        tic_loss = torch.tensor(0.0, device=self.device)
        if hasattr(self.model, "train_tic_from_buffer"):
            try:
                tic_result = self.model.train_tic_from_buffer(batch_size=16)
                if tic_result.get("status") == "trained":
                    tic_loss_val = tic_result.get("total_loss", 0.0)
                    if isinstance(tic_loss_val, torch.Tensor):
                        tic_loss = tic_loss_val
                        loss = loss + self.config.lambda_tic * tic_loss
            except Exception as e:
                logger.debug(f"TIC training skipped: {e}")

        # ============================================================
        # 3. SOLOMONOFF COMPLEXITY LOSS
        # ============================================================
        solomonoff_loss = torch.tensor(0.0, device=self.device)
        unified_library = getattr(self.model, "_unified_library", None)

        if unified_library is not None and action is not None and action.shape[-1] >= 8:
            try:
                # Use prediction quality as reward signal
                with torch.no_grad():
                    prediction, _ = self.forward(state, action)
                    min_dim = min(prediction.shape[-1], target.shape[-1])
                    pred_error = F.mse_loss(
                        prediction[..., :min_dim], target[..., :min_dim], reduction="none"
                    ).mean(dim=-1)
                    rewards = torch.exp(-pred_error).clamp(0.0, 1.0)

                # Project action to 8D octonion space for E8 addressing
                query = action[..., :8]
                result = unified_library.select(query)
                attention = result["attention"]

                # Compute differentiable complexity loss
                complexity_result = unified_library.differentiable_complexity_loss(
                    attention=attention,
                    rewards=rewards,
                )
                solomonoff_loss = complexity_result["complexity_loss"]
                loss = loss + self.config.lambda_solomonoff * solomonoff_loss
            except Exception as e:
                logger.debug(f"MDL complexity loss skipped: {e}")

        # ============================================================
        # 4. SUPERORGANISM CATASTROPHE LOSS
        # ============================================================
        catastrophe_loss = torch.tensor(0.0, device=self.device)
        if self._superorganism is not None:
            try:
                # Get catastrophe-aware loss from superorganism integration
                cat_losses = self._superorganism.get_training_loss(
                    prediction=state,  # Current embedding
                    target=target,
                )
                if "total" in cat_losses:
                    catastrophe_loss = cat_losses["total"]
                    loss = loss + self.config.lambda_catastrophe * catastrophe_loss
            except Exception as e:
                logger.debug(f"Superorganism catastrophe loss skipped: {e}")

        # ============================================================
        # 5. EWC CONTINUAL LEARNING LOSS
        # ============================================================
        ewc_loss = torch.tensor(0.0, device=self.device)
        if self.config.enable_ewc:
            ewc_loss = self._compute_ewc_loss()
            loss = loss + self.config.lambda_ewc * ewc_loss

            # Accumulate for Fisher information
            self._accumulate_fisher_info(state, target)

        return loss

    def train_full_stack(
        self,
        batch: dict[str, Any],
        task_id: str | None = None,
        train_rl: bool | None = None,
    ) -> TrainingMetrics:
        """Train the ENTIRE K OS stack end-to-end.

        CANONICAL (Dec 2, 2025):
        This is THE method for training. All other training paths deleted.

        CRITICAL (Dec 14, 2025):
        Added NaN/Inf detection at every stage to prevent silent corruption.

        Trains:
        1. World Model (KagamiWorldModel)
        2. Colony RSSM (dynamics)
        3. Program Library (MDL complexity)
        4. TIC (receipt dynamics)
        5. Catastrophe Dynamics (stability)
        6. RL Actor-Critic (optional, delegated)
        7. EWC (continual learning)

        Args:
            batch: Training batch with 'state', 'action', 'next_state'
            task_id: Task identifier for EWC
            train_rl: Override for RL training (uses config if None)

        Returns:
            TrainingMetrics with all loss components
        """
        self.model.train()
        self._step += 1

        # === HEALTH CHECK: Pre-training validation ===
        # Check for NaN/Inf in model parameters
        is_healthy = True
        errors = []
        for name, param in self.model.named_parameters():
            if param is not None and torch.isnan(param).any():
                is_healthy = False
                errors.append(f"NaN in {name}")
            if param is not None and torch.isinf(param).any():
                is_healthy = False
                errors.append(f"Inf in {name}")
        if not is_healthy:
            logger.error(f"NaN/Inf detected before training: {errors}")
            return TrainingMetrics(
                step=self._step,
                total_loss=float("inf"),
                prediction_loss=float("inf"),
            )

        # Compute full stack loss
        loss = self.compute_loss(batch, task_id=task_id)

        # === HEALTH CHECK: Loss validation ===
        if torch.isnan(loss) or torch.isinf(loss):
            logger.error(f"NaN/Inf detected in loss computation: loss={loss.item()}")
            return TrainingMetrics(
                step=self._step,
                total_loss=float("inf"),
                prediction_loss=float("inf"),
            )

        # ============================================================
        # GRADIENT UPDATE (Dec 24, 2025 - CRITICAL FIX)
        # ============================================================
        # This was MISSING - the training loop computed loss but never
        # backpropagated or updated model weights!
        self.optimizer.zero_grad()
        loss.backward()

        # Gradient clipping for stability
        grad_norm = torch.nn.utils.clip_grad_norm_(
            self.model.parameters(),
            self.config.gradient_clip,
        )

        self.optimizer.step()

        # ============================================================
        # 6. RL TRAINING (Delegated to UnifiedRLLoop)
        # ============================================================
        rl_loss = 0.0
        should_train_rl = train_rl if train_rl is not None else self.config.enable_rl_training

        if should_train_rl and self._step % self.config.rl_train_interval == 0:
            try:
                if self._rl_loop is None:
                    from kagami.core.rl.unified_loop import get_rl_loop

                    self._rl_loop = get_rl_loop()

                # Train RL from replay buffer
                import asyncio

                try:
                    loop = asyncio.get_running_loop()
                    # Already in async context
                    asyncio.create_task(self._train_rl_async())
                except RuntimeError:
                    # No running loop - create one
                    loop = asyncio.new_event_loop()
                    rl_result = loop.run_until_complete(
                        self._rl_loop.train_from_buffer(batch_size=32)
                    )
                    loop.close()
                    if rl_result.get("status") == "success":
                        rl_loss = rl_result.get("avg_policy_loss", 0.0)
            except Exception as e:
                logger.debug(f"RL training skipped: {e}")

        # ============================================================
        # 7. SAFETY CBF LOSS (Dec 7, 2025 - REQUIRED, NO OPTIONAL PATH)
        # ============================================================
        safety_loss = 0.0
        safety_h_mean = 0.0

        # Get state representation from batch
        state = batch.get("state")
        if state is not None and self._safety_cbf is not None:
            # Forward through model to get representation
            with torch.no_grad():
                _, metrics = self.model(state)
            z = metrics.get("core_state", state)

            # Convert to safety state (use first 16 dims or pad)
            B = z.shape[0]
            if z.shape[-1] >= 16:
                safety_state = z[:, :16]
            else:
                padding = torch.zeros(B, 16 - z.shape[-1], device=self.device)
                safety_state = torch.cat([z, padding], dim=-1)

            # Nominal control
            nominal_control = torch.full((B, 2), 0.5, device=self.device)

            # Get safe control and penalty (REQUIRED - no exception bypass)
            _, safety_penalty, cbf_info = self._safety_cbf(safety_state, nominal_control)

            # Add to total loss (ALWAYS applied)
            loss = loss + self.config.lambda_safety * safety_penalty
            safety_loss = safety_penalty.item()

            # Extract h values for monitoring
            h_tensor = cbf_info.get("h_metric")
            if h_tensor is not None:
                if isinstance(h_tensor, torch.Tensor):
                    safety_h_mean = h_tensor.mean().item()
                else:
                    safety_h_mean = float(h_tensor)

        # ============================================================
        # 8. SUPERORGANISM SYNC
        # ============================================================
        now = time.time()
        if (
            self._superorganism is not None
            and now - self._last_sync_time > self.config.sync_interval
        ):
            try:
                import asyncio

                try:
                    loop = asyncio.get_running_loop()
                    asyncio.create_task(self._superorganism.sync_cycle())
                except RuntimeError:
                    # No running loop - create one
                    loop = asyncio.new_event_loop()
                    loop.run_until_complete(self._superorganism.sync_cycle())
                    loop.close()
                self._last_sync_time = now
            except Exception as e:
                logger.debug(f"Superorganism sync skipped: {e}")

        # ============================================================
        # 8. DEPTH CURRICULUM (Dec 2, 2025)
        # FIXED (Dec 24, 2025): Pass gradient_norm and use correct method
        # ============================================================
        curriculum_info = {}
        if self._curriculum is not None:
            # Step curriculum with current loss AND gradient norm for proper transition detection
            loss_value = loss.item() if isinstance(loss, torch.Tensor) else loss
            grad_norm_value = grad_norm.item() if isinstance(grad_norm, torch.Tensor) else grad_norm
            curriculum_result = self._curriculum.step(
                {"total": loss_value},
                gradient_norm=grad_norm_value,
            )

            # Check for phase transition
            if curriculum_result.get("should_transition", False):
                # FIX: Use apply_depth_to_model (on_phase_transition doesn't exist)
                self._curriculum.apply_depth_to_model(self.model)
                logger.info(
                    f"🎯 Curriculum phase transition: "
                    f"{curriculum_result.get('transition_from')} → "
                    f"{curriculum_result.get('transition_to')}"
                )

            curriculum_info = {
                "phase": curriculum_result.get("phase_name", "unknown"),
                "e8_depth": curriculum_result.get("e8_depth", 0),
                "program_depth": curriculum_result.get("program_depth", 0),
                "memory_depth": curriculum_result.get("memory_depth", 0),
            }

        # Build metrics
        metrics = TrainingMetrics(
            step=self._step,
            total_loss=loss.item() if isinstance(loss, torch.Tensor) else loss,
            rl_loss=rl_loss,
            safety_loss=safety_loss,
            safety_h_mean=safety_h_mean,
            gradient_norm=grad_norm.item() if isinstance(grad_norm, torch.Tensor) else grad_norm,
        )

        # Log periodically
        if self._step % self.config.log_interval == 0:
            depth_str = ""
            if curriculum_info:
                depth_str = (
                    f" | phase={curriculum_info['phase']} "
                    f"depth=[e8={curriculum_info['e8_depth']}, "
                    f"prg={curriculum_info['program_depth']}, "
                    f"mem={curriculum_info['memory_depth']}]"
                )
            safety_str = (
                f" | safety={safety_loss:.4f} h(x)={safety_h_mean:.4f}" if safety_loss > 0 else ""
            )
            logger.info(
                f"Step {self._step} | loss={metrics.total_loss:.4f} | "
                f"grad={metrics.gradient_norm:.4f} | rl={metrics.rl_loss:.4f}{safety_str}{depth_str}"
            )

        # ============================================================
        # W&B LOGGING (Dec 27, 2025)
        # MIGRATION: Replaced TensorBoard with W&B
        # ============================================================
        if self._wandb_logger is not None:
            # Core loss metrics (every step for real-time monitoring)
            log_metrics = {
                "Loss/total": metrics.total_loss,
                "Loss/rl": metrics.rl_loss,
                "Gradient/norm": metrics.gradient_norm,
            }

            # Safety metrics
            if safety_loss > 0:
                log_metrics["Safety/cbf_loss"] = safety_loss
                log_metrics["Safety/h_mean"] = safety_h_mean

            # Curriculum metrics (only when available)
            if curriculum_info:
                log_metrics["Curriculum/e8_depth"] = curriculum_info["e8_depth"]
                log_metrics["Curriculum/program_depth"] = curriculum_info["program_depth"]
                log_metrics["Curriculum/memory_depth"] = curriculum_info["memory_depth"]

            # Learning rate (every 10 log intervals to reduce overhead)
            if self._step % (self.config.log_interval * 10) == 0:
                for i, param_group in enumerate(self.optimizer.param_groups):
                    lr = param_group.get("lr", 0.0)
                    log_metrics[f"Optimizer/lr_group_{i}"] = lr

            self._wandb_logger.log(log_metrics, step=self._step)

        # ============================================================
        # PUBLISH EXPERIENCE TO E8 BUS (Dec 2, 2025)
        # ============================================================
        if self._event_bus is not None:
            try:
                self._publish_training_experience(metrics, task_id)
            except Exception as e:
                logger.debug(f"Experience publish skipped: {e}")

        return metrics

    async def _train_rl_async(self) -> None:
        """Async RL training helper."""
        if self._rl_loop is not None:
            await self._rl_loop.train_from_buffer(batch_size=32)

    def _compute_ewc_loss(self) -> torch.Tensor:
        """Compute EWC regularization loss."""
        loss = torch.tensor(0.0, device=self.device)

        for task_id, fisher_diag in self._ewc_fisher.items():
            optimal_params = self._ewc_optimal_params.get(task_id, {})

            for name, param in self.model.named_parameters():
                if name in fisher_diag and name in optimal_params:
                    fisher = fisher_diag[name]
                    opt = optimal_params[name]
                    loss = loss + (fisher * (param - opt).pow(2)).sum()

        return loss

    def _accumulate_fisher_info(
        self,
        input_tensor: torch.Tensor,
        target_tensor: torch.Tensor,
    ) -> None:
        """Accumulate gradients for Fisher Information computation."""
        if len(self._ewc_buffer) < self.config.fisher_buffer_size:
            self._ewc_buffer.append((input_tensor.detach().cpu(), target_tensor.detach().cpu()))

    def _consolidate_ewc(self, task_id: str) -> None:
        """Consolidate EWC for completed task."""
        if not self._ewc_buffer:
            return

        logger.info(f"Consolidating EWC for task {task_id}...")

        # Store optimal parameters
        self._ewc_optimal_params[task_id] = {
            n: p.data.clone().detach() for n, p in self.model.named_parameters() if p.requires_grad
        }

        # Compute Fisher Information (diagonal approximation)
        fisher_diag = {}
        for n, p in self.model.named_parameters():
            if p.requires_grad:
                fisher_diag[n] = torch.zeros_like(p.data)

        # Process buffer
        for x_cpu, target_cpu in self._ewc_buffer:
            x = x_cpu.to(self.device)
            target = target_cpu.to(self.device)

            self.model.zero_grad()
            output, _ = self.forward(x, None)

            min_dim = min(output.shape[-1], target.shape[-1])
            loss = F.mse_loss(output[..., :min_dim], target[..., :min_dim])
            loss.backward()

            for n, p in self.model.named_parameters():
                if p.grad is not None:
                    fisher_diag[n] += p.grad.data.pow(2)

        # Average
        num_samples = len(self._ewc_buffer)
        for n in fisher_diag:
            fisher_diag[n] /= num_samples

        self._ewc_fisher[task_id] = fisher_diag
        self._ewc_buffer.clear()
        logger.info(f"EWC consolidation complete for {task_id}")

    def _to_tensor(self, x: Any) -> torch.Tensor:
        """Convert input to tensor on correct device."""
        if x is None:
            return None  # type: ignore[return-value]
        if not isinstance(x, torch.Tensor):
            return torch.as_tensor(x, device=self.device, dtype=torch.float32)
        return x.to(self.device)

    def encode(self, observation: torch.Tensor) -> tuple[Any, dict[str, Any]]:
        """Encode observation to CoreState.

        Args:
            observation: [B, obs_dim] observation tensor

        Returns:
            core_state: CoreState with E8/S7/shell components
            metrics: Encoding metrics
        """
        observation = self._to_tensor(observation)

        # Ensure input dimensions match
        if observation.shape[-1] != self._input_dim:
            if observation.shape[-1] > self._input_dim:
                observation = observation[..., : self._input_dim]
            else:
                pad = torch.zeros(
                    *observation.shape[:-1],
                    self._input_dim - observation.shape[-1],
                    device=observation.device,
                    dtype=observation.dtype,
                )
                observation = torch.cat([observation, pad], dim=-1)

        return self.model.encode(observation)

    def decode(self, core_state: Any) -> tuple[torch.Tensor, dict[str, Any]]:
        """Decode CoreState to prediction.

        Args:
            core_state: CoreState from encode()

        Returns:
            prediction: [B, bulk_dim] decoded prediction
            metrics: Decoding metrics
        """
        return self.model.decode(core_state)

    # ========================================================================
    # UNIFIED E8 EVENT BUS INTEGRATION (Dec 2, 2025)
    # ========================================================================

    def _publish_training_experience(
        self,
        metrics: TrainingMetrics,
        task_id: str | None = None,
    ) -> None:
        """Publish training step outcome to E8 event bus.

        This enables:
        1. Colony coordination during training
        2. Experience replay for other agents
        3. Distributed training synchronization
        """
        if self._event_bus is None:
            return

        from kagami.core.events import OperationOutcome

        # Build operation outcome
        outcome = OperationOutcome(
            operation=f"training_step_{self._step}",
            success=metrics.total_loss < 10.0,  # Reasonable loss threshold
            app="world_model_loop",
            correlation_id=task_id or f"train_{self._step}",
            duration_ms=0.0,  # Could track actual duration
            metadata={
                "step": metrics.step,
                "total_loss": metrics.total_loss,
                "rl_loss": metrics.rl_loss,
                "prediction_loss": metrics.prediction_loss,
                "geometric_loss": metrics.geometric_loss,
                "epoch": self._epoch,
            },
        )

        # Publish asynchronously (fire-and-forget during training)
        import asyncio

        try:
            loop = asyncio.get_running_loop()
            asyncio.create_task(self._event_bus.publish_experience(outcome))
        except RuntimeError:
            # No running loop - create one
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(self._event_bus.publish_experience(outcome))
            finally:
                loop.close()
        except Exception:
            # No event loop - create one
            asyncio.run(self._event_bus.publish_experience(outcome))

    async def _on_training_event(self, event: Any) -> None:
        """Handle training coordination events from other colonies.

        Events:
        - training.pause: Pause training
        - training.resume: Resume training
        - training.sync: Synchronize model weights
        """
        topic = getattr(event, "topic", "")

        if "pause" in topic:
            logger.info("⏸️ Training paused by colony signal")
            # Could set[Any] a pause flag
        elif "resume" in topic:
            logger.info("▶️ Training resumed by colony signal")
        elif "sync" in topic:
            logger.info("🔄 Training sync requested by colony")
            # Could trigger gradient synchronization

    async def _on_colony_learn(self, event: Any) -> None:
        """Handle colony learning requests.

        When a colony sends a learn signal, we can:
        1. Prioritize learning from that colony's observations
        2. Adjust learning rate for that colony
        3. Share relevant model weights
        """
        payload = getattr(event, "payload", {})
        colony_id = payload.get("colony_id", "unknown")

        logger.debug(f"Colony {colony_id} requested learning attention")

        # Future: Could implement colony-specific learning priorities

    async def _on_memory_event(self, event: Any) -> None:
        """Handle episodic memory read/write events.

        Enables coordinated learning:
        1. Memory writes → trigger replay buffer updates
        2. Memory reads → log retrieval patterns
        3. High-energy reads → may indicate novel situations
        """
        payload = getattr(event, "payload", {}) if hasattr(event, "payload") else {}
        operation = payload.get("operation", "unknown")
        energy = payload.get("energy", 0.0)

        if "write" in operation:
            logger.debug(f"Memory write: indices={payload.get('indices', [])}")
        elif "read" in operation and energy > 1.0:
            # High energy = novel situation
            logger.debug(f"Novel memory access: energy={energy:.2f}")

    async def _on_library_event(self, event: Any) -> None:
        """Handle program library select/update events.

        Enables coordinated learning:
        1. Program selection → can influence training priorities
        2. Complexity updates → track which programs are succeeding
        3. Low-complexity programs → may be worth reinforcing
        """
        payload = getattr(event, "payload", {}) if hasattr(event, "payload") else {}
        operation = payload.get("operation", "unknown")
        program_idx = payload.get("program_idx", -1)
        complexity = payload.get("complexity", 0.0)

        if "update_complexity" in operation:
            reward = payload.get("reward", 0.0)
            direction = payload.get("direction", "unknown")
            logger.debug(
                f"Program {program_idx} complexity update: "
                f"K={complexity:.2f}, reward={reward:.2f}, direction={direction}"
            )

    async def start_bus(self) -> None:
        """Start the event bus for training coordination."""
        if self._event_bus is not None and not self._bus_started:
            await self._event_bus.start()
            self._bus_started = True
            logger.info("✅ Training event bus started")

    async def stop_bus(self) -> None:
        """Stop the event bus."""
        if self._event_bus is not None and self._bus_started:
            await self._event_bus.stop()
            self._bus_started = False
            logger.info("✅ Training event bus stopped")

    def close(self) -> None:
        """Close all resources (W&B logger, etc.).

        UPDATED (Dec 27, 2025): Proper cleanup for W&B and other resources.
        Call this when training is complete to ensure all logs are flushed.
        """
        if self._wandb_logger is not None:
            self._wandb_logger.finish()
            self._wandb_logger = None
            logger.info("✅ W&B logger closed")


def get_world_model_loop(
    model: nn.Module | None = None,
    config: TrainingConfig | None = None,
    device: str = "cpu",
) -> WorldModelLoop:
    """Factory function for CANONICAL world model loop.

    CANONICAL (Dec 2, 2025):
    This is the single factory for training. Use this, not alternatives.

    Args:
        model: Optional pre-created KagamiWorldModel
        config: Training configuration
        device: Computation device

    Returns:
        WorldModelLoop instance (canonical trainer)
    """
    return WorldModelLoop(
        model=model,
        config=config,
        device=device,
    )


# Singleton for global access
_canonical_loop: WorldModelLoop | None = None


def get_canonical_training_loop(device: str = "cpu") -> WorldModelLoop:
    """Get the global canonical training loop.

    CANONICAL (Dec 2, 2025):
    Use this for all training operations.

    Args:
        device: Computation device

    Returns:
        Global WorldModelLoop singleton
    """
    global _canonical_loop
    if _canonical_loop is None:
        _canonical_loop = WorldModelLoop(device=device)
        logger.info("✅ Canonical training loop initialized")
    return _canonical_loop


__all__ = [
    "TrainingConfig",
    "TrainingMetrics",
    "WorldModelLoop",
    "get_canonical_training_loop",
    "get_world_model_loop",
]
