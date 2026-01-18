"""KagamiWorldModel training module (Dec 27, 2025).

Provides training methods for KagamiWorldModel:
- training_step(): Single training iteration
- _compute_h_jepa_loss(): H-JEPA predictive loss
- on_epoch_end(): End-of-epoch hooks

RESTORED (Dec 27, 2025):
========================
During refactoring, these methods were accidentally left empty.
Restored from git history to fix training loop.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import torch

if TYPE_CHECKING:
    from kagami.core.world_model.losses.composed import LossOutput

logger = logging.getLogger(__name__)


class TrainingMixin:
    """Training methods: training_step(), loss computation.

    This mixin expects the class to have:
    - loss_module: UnifiedLossModule
    - h_jepa_predictor: H-JEPA predictor network
    - h_jepa_target: H-JEPA target network
    - forward(): Model forward pass
    - update_h_jepa_target(): EMA update for target network
    - config.use_amp: Whether to use GPU AMP autocast
    - _amp_dtype: Cached torch dtype for AMP (float16 or bfloat16)
    """

    # Declare attributes that will be provided by the main class
    loss_module: Any
    h_jepa_predictor: Any
    h_jepa_target: Any
    _last_forward_output_detached: torch.Tensor | None
    _last_forward_output: torch.Tensor | None
    _last_forward_metrics_detached: dict[str, Any] | None
    _last_forward_metrics: dict[str, Any] | None
    _meta_tower: Any
    _meta_tower_receipts: list[dict[str, Any]]
    _meta_tower_current_epoch: int
    _meta_tower_epoch_interval: int
    unified_hourglass: Any
    organism_rssm: Any
    config: Any
    _amp_dtype: Any
    training: bool

    def training_step(
        self,
        x: torch.Tensor,
        target: torch.Tensor,
        action: torch.Tensor | None = None,
    ) -> LossOutput:
        """Execute a single training step.

        Supports GPU AMP autocast when config.use_amp=True. The entire training
        step (forward + loss computation) is wrapped with torch.amp.autocast
        for mixed precision training.

        Args:
            x: Input tensor [B, S, D] or [B, D]
            target: Target tensor [B, S, D] or [B, D]
            action: Optional action tensor for RSSM dynamics

        Returns:
            LossOutput with total loss and components
        """
        # GPU AMP autocast for mixed precision training (Jan 4, 2026)
        # FIX (Jan 4, 2026): Detect device type dynamically for TPU/GPU compatibility
        use_amp = getattr(self.config, "use_amp", False)
        if use_amp and self.training and self._amp_dtype is not None:
            # Get device type from input tensor for correct autocast context
            device_type = x.device.type
            # XLA (TPU) uses "xla" device type but torch.amp.autocast only supports "cuda"/"cpu"
            # For TPU, XLA handles mixed precision natively, so skip autocast
            if device_type == "cuda":
                with torch.amp.autocast(device_type="cuda", dtype=self._amp_dtype):
                    return self._training_step_impl(x, target, action)
            else:
                # For TPU (xla), MPS, or CPU - no autocast wrapper needed
                # TPU uses bfloat16 natively via model dtype conversion in model_core.py
                return self._training_step_impl(x, target, action)
        else:
            return self._training_step_impl(x, target, action)

    def _training_step_impl(
        self,
        x: torch.Tensor,
        target: torch.Tensor,
        action: torch.Tensor | None = None,
    ) -> LossOutput:
        """Internal training step implementation (called by training_step with optional AMP wrapping).

        Args:
            x: Input tensor [B, S, D] or [B, D]
            target: Target tensor [B, S, D] or [B, D]
            action: Optional action tensor for RSSM dynamics

        Returns:
            LossOutput with total loss and components
        """
        # Forward pass - use action if provided for RSSM conditioning
        output, metrics = self.forward(x, action=action)  # type: ignore[attr-defined]

        # Use CoreState and encoder_states from forward (don't call encode again!)
        core_state = metrics.get("core_state")
        encoder_states = metrics.get("encoder_states", {})

        # Build hierarchy levels dict[str, Any] for Matryoshka loss
        hierarchy_levels: dict[str, torch.Tensor] = {}
        for key in ("e8", "e7", "e6", "f4", "manifold", "g2"):
            val = encoder_states.get(key)
            if isinstance(val, torch.Tensor):
                hierarchy_levels[key] = val

        # Compute unified loss
        loss_output = self.loss_module(
            output,
            target,
            metrics,
            core_state=core_state,
            hierarchy_levels=hierarchy_levels if hierarchy_levels else None,
        )

        # =================================================================
        # H-JEPA LOSS (December 19, 2025)
        # =================================================================
        # Add predictive loss for multi-horizon E8 predictions
        h_jepa_loss = self._compute_h_jepa_loss(metrics, encoder_states)
        if h_jepa_loss is not None:
            # Add to loss components
            loss_output.components["h_jepa_loss"] = h_jepa_loss
            # Weight H-JEPA loss (0.1 = moderate contribution to total loss)
            h_jepa_weight = 0.1
            loss_output.total = loss_output.total + h_jepa_weight * h_jepa_loss

        # =================================================================
        # H-JEPA EMA TARGET UPDATE (December 24, 2025)
        # FIX (December 28, 2025): WARMUP - don't update target until
        # predictor has had time to diverge from initial weights
        # ENHANCEMENT (December 30, 2025): Curriculum-scheduled EMA decay
        # NOTE (Jan 4, 2026): _h_jepa_step_counter now initialized in model_core.__init__
        # =================================================================
        # Increment step counter
        self._h_jepa_step_counter += 1

        # WARMUP: Don't update target for first 1000 steps
        # This allows predictor to learn and diverge from target
        # After warmup, update every 100 steps (slower than before)
        warmup_steps = 1000
        update_interval = 100

        if self._h_jepa_step_counter > warmup_steps:
            if (self._h_jepa_step_counter - warmup_steps) % update_interval == 0:
                # Curriculum-scheduled EMA decay (Dec 30, 2025)
                # Early: lower decay (0.9) for faster adaptation
                # Late: higher decay (0.999) for stability
                step = self._h_jepa_step_counter
                curriculum_progress = min(1.0, step / 50000)  # Full curriculum at 50k steps
                # Ramp from 0.9 to 0.999 over curriculum
                scheduled_decay = 0.9 + 0.099 * curriculum_progress
                self.update_h_jepa_target(decay=scheduled_decay)  # type: ignore[attr-defined]

        # Cache for external training loops (training script adds extra losses).
        # NOTE: _last_forward_output retains the computation graph until backward().
        self._last_forward_output = output
        self._last_forward_metrics = metrics

        # Detached copies for logging/debugging without holding graph references.
        self._last_forward_output_detached = output.detach()
        try:
            detached_metrics: dict[str, Any] = {}
            for k, v in metrics.items():
                if isinstance(v, torch.Tensor):
                    detached_metrics[k] = v.detach()
                else:
                    detached_metrics[k] = v
            self._last_forward_metrics_detached = detached_metrics
        except Exception:
            self._last_forward_metrics_detached = None

        return loss_output

    def _compute_h_jepa_loss(
        self,
        metrics: dict[str, Any],
        encoder_states: dict[str, torch.Tensor],
    ) -> torch.Tensor | None:
        """Compute H-JEPA predictive loss for multi-horizon prediction.

        Args:
            metrics: Metrics dict[str, Any] from forward pass
            encoder_states: Encoder states from forward pass

        Returns:
            H-JEPA loss tensor or None if not available
        """
        h_jepa_predictions = metrics.get("h_jepa_predictions")
        h_jepa_targets = metrics.get("h_jepa_target_predictions")

        if h_jepa_predictions is None or h_jepa_targets is None:
            return None

        # Compute MSE loss between predictions and target predictions
        device = next(iter(h_jepa_predictions.values())).device
        total_loss = torch.tensor(0.0, device=device)
        count = 0

        for horizon_key in h_jepa_predictions:
            pred = h_jepa_predictions[horizon_key]
            target = h_jepa_targets.get(horizon_key)

            if target is not None:
                # Use detached target (stop gradient through target network)
                loss = (pred - target.detach()).pow(2).mean()
                total_loss = total_loss + loss
                count += 1

        if count > 0:
            return total_loss / count

        return None

    def on_epoch_end(
        self,
        epoch: int,
        receipts: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """End-of-epoch hook for MetaTower fixed point optimization.

        Args:
            epoch: Current epoch number
            receipts: Optional receipts from this epoch

        Returns:
            Dict with meta-optimization results
        """
        result: dict[str, Any] = {"epoch": epoch, "meta_tower_updated": False}

        # Collect receipts for meta-learning
        if receipts:
            self._meta_tower_receipts.extend(receipts)

        # Update MetaTower at interval
        self._meta_tower_current_epoch = epoch
        if self._meta_tower is not None and epoch % self._meta_tower_epoch_interval == 0:
            # Get policy modules to optimize
            policy_modules = {
                "unified_hourglass": self.unified_hourglass,
                "organism_rssm": self.organism_rssm,
                "h_jepa_predictor": self.h_jepa_predictor,
            }

            # Run meta-tower fixed point update
            if self._meta_tower_receipts:
                try:
                    # Wire CBF safety checker for policy safety verification
                    safety_checker = None
                    try:
                        from kagami.core.safety.optimal_cbf import get_optimal_cbf

                        cbf = get_optimal_cbf()
                        safety_checker = cbf.barrier_value
                    except (ImportError, RuntimeError) as cbf_err:
                        logger.debug(f"CBF safety checker unavailable: {cbf_err}")

                    meta_result = self._meta_tower.update_until_fixed_point(
                        policy_modules=policy_modules,
                        receipts=self._meta_tower_receipts[-100:],  # Use recent receipts
                        safety_checker=safety_checker,
                    )
                    result["meta_tower_result"] = meta_result
                    result["meta_tower_updated"] = True
                    result["meta_tower_converged"] = meta_result.get("converged", False)

                    if meta_result.get("converged"):
                        logger.info(
                            f"✅ MetaTower converged at epoch {epoch} "
                            f"(iterations={meta_result.get('iterations', 'N/A')})"
                        )

                    # Clear old receipts after processing
                    self._meta_tower_receipts = self._meta_tower_receipts[-20:]

                except Exception as e:
                    logger.warning(f"MetaTower update failed: {e}")
                    result["meta_tower_error"] = str(e)

        return result
