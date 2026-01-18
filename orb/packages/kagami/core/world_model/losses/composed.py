"""Composed loss orchestrator.

This module provides the UnifiedLossModule that orchestrates all loss
components into a single training objective.

ARCHITECTURAL REDESIGN (Dec 22, 2025):
=====================================
- REMOVED: GradNorm dynamic weighting (causes gradient conflicts)
- REMOVED: CBF-aware scaling (unnecessary complexity)
- REMOVED: Wasserstein IB (simple KL is more stable)
- TIERED: 3-tier loss hierarchy for stable training

Tier 1 - Core (always enabled):
  - prediction: symlog reconstruction (1.0)

Tier 2 - Essential (for VQ/dynamics/identity):
  - e8_commitment: VQ codebook training (0.1)
  - rssm_kl: dynamics learning (0.1)
  - loop_closure: strange loop μ_self convergence (0.01) - CRITICAL for Kagami
  - fano_synergy: colony coordination via Fano lines (0.01)
  - h_jepa_pred: multi-horizon prediction (0.05) - CRITICAL for world model
  - stability: gradient magnitude regularization (0.01)
  - seq_ib_recon/kl: sequence IB decoder (0.1/0.01)
  - ib_kl: latent compression (0.01)

Tier 3 - Auxiliary (disabled by default):
  - All other losses → zero weight initially

Created: December 15, 2025 (refactored from unified_loss.py)
Redesigned: December 22, 2025 (gradient surgery + tier 2 migration)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F

from kagami.core.world_model.losses.prediction import (
    DynamicLossComputer,
    RegularizationLossComputer,
    SelfReferenceLossComputer,
)
from kagami.core.world_model.losses.reconstruction import (
    GeometricLossComputer,
    symlog_squared_loss,
)
from kagami.core.world_model.losses.uncertainty_weighted import (
    UncertaintyWeightedLoss,
)

logger = logging.getLogger(__name__)


@dataclass
class LossConfig:
    """Loss configuration - TIERED for stable training.

    ARCHITECTURAL REDESIGN (Dec 22, 2025):
    =====================================
    - Tiered loss structure for stable gradient flow
    - Fixed weights (no dynamic rebalancing)
    - Critical losses migrated to Tier 2

    Tier 1: Core prediction loss (always on)
    Tier 2: Essential losses (VQ, IB, RSSM, geometry, strange loop)
    Tier 3: Auxiliary losses (off by default)
    """

    # === TIER 1: Core Prediction (ALWAYS ON) ===
    prediction_weight: float = 1.0

    # === TIER 2: Essential Losses ===

    # -- E8/VQ Codebook Training --
    # IMPROVED (Dec 29, 2025): Add warmup to prevent early divergence
    e8_commitment_weight: float = 0.05  # Reduced from 0.1 for stability
    e8_commitment_warmup_steps: int = 2000  # Disable for first 2000 steps
    e8_commitment_ema_decay: float = 0.99  # EMA for smoother targets

    # -- Information Bottleneck --
    ib_beta: float = 0.01  # Conservative compression
    ib_free_bits: float = 1.0  # DreamerV3 standard
    ib_kl_weight: float = 0.01

    # -- RSSM Dynamics --
    rssm_kl_weight: float = 0.1  # Dynamics learning
    rssm_dynamics_weight: float = 0.5
    rssm_representation_weight: float = 0.1
    rssm_reconstruction_weight: float = 0.0  # Use main prediction instead
    rssm_reward_weight: float = 0.0  # No reward signal yet
    rssm_continue_weight: float = 0.0  # No episode boundaries

    # -- Sequence IB (decoder training) --
    # NOTE (Dec 28, 2025): Kept conservative weights for stability.
    # Future optimization: consider gradient-balanced multi-task learning.
    seq_ib_recon_weight: float = 0.1
    seq_ib_kl_weight: float = 0.01

    # -- Strange Loop (CRITICAL for Kagami identity) --
    # MIGRATED TO TIER 2 (Dec 22, 2025)
    loop_closure_weight: float = 0.01  # μ_self convergence - essential for Kagami

    # -- Fano Synergy (CRITICAL for colony coordination) --
    # MIGRATED TO TIER 2 (Dec 22, 2025)
    fano_synergy_weight: float = 0.01  # 7 colonies must interact via Fano lines

    # -- H-JEPA Prediction (CRITICAL for world model) --
    # MIGRATED TO TIER 2 (Dec 22, 2025)
    h_jepa_pred_weight: float = 0.05  # Multi-horizon prediction

    # -- Stability Regularization (IMPORTANT) --
    # MIGRATED TO TIER 2 (Dec 22, 2025)
    stability_weight: float = 0.01  # Prevents gradient explosion

    # === TIER 3: Auxiliary Losses (MOSTLY DISABLED BY DEFAULT) ===

    # Geometric (enabled for geometric curriculum)
    gauge_equivariance_weight: float = 0.0
    manifold_curvature_weight: float = 0.01  # Enabled for geometric structure

    # Chaos/catastrophe
    catastrophe_weight: float = 0.0
    chaos_entropy_weight: float = 0.0

    # Self-reference (enable after loop_closure stable)
    recognition_weight: float = 0.0
    loop_strength_weight: float = 0.0

    # H-JEPA KL (enable after h_jepa_pred stable)
    h_jepa_kl_weight: float = 0.0

    # Intrinsic motivation
    empowerment_weight: float = 0.0
    active_inference_weight: float = 0.0

    # Regularization
    moe_load_balance_weight: float = 0.0
    kan_regularization_weight: float = 0.0
    bidirectional_hierarchy_weight: float = 0.0

    # Matryoshka
    matryoshka_weight: float = 0.0

    # Memory
    memory_retrieval_weight: float = 0.0
    memory_commitment_weight: float = 0.0
    memory_entropy_weight: float = 0.0
    memory_energy_weight: float = 0.0

    # TIC
    tic_success_weight: float = 0.0
    tic_postcondition_weight: float = 0.0
    tic_safety_weight: float = 0.0
    tic_dynamics_weight: float = 0.0

    # Adaptive E8 - disabled
    adaptive_e8_rate_weight: float = 0.0
    adaptive_e8_target_depth: float = 8.0
    adaptive_e8_smoothness_weight: float = 0.0

    # Gated Fano - disabled
    fano_gate_l1_weight: float = 0.0
    fano_gate_coherence_weight: float = 0.0

    # CBF - disabled (was causing issues)
    cbf_aware_scaling: bool = False  # DISABLED
    cbf_safety_sensitivity: float = 0.0
    cbf_aux_loss_weight: float = 0.0

    # === REMOVED FEATURES ===
    # GradNorm - REMOVED (caused gradient conflicts)
    # gradnorm_alpha: REMOVED
    # gradnorm_lr: REMOVED

    # Wasserstein IB - REMOVED (use simple KL)
    # sinkhorn_epsilon: REMOVED
    # sinkhorn_iterations: REMOVED

    # IB scheduling - SIMPLIFIED (constant beta)
    ib_beta_schedule: str = "constant"
    ib_beta_min: float = 0.01
    ib_beta_max: float = 0.1
    ib_warmup_steps: int = 0  # No warmup - start at target

    # FSD - disabled
    fsd_weight: float = 0.0
    fsd_batch_size: int = 32

    # Gradient control - keep gradient clipping
    max_gradient_norm: float = 1.0

    # Calibration - disabled (not needed for core training)
    track_calibration: bool = False
    calibration_num_bins: int = 15
    calibration_temperature_lr: float = 0.01

    # === UNCERTAINTY WEIGHTING (Kendall 2017) ===
    # Dec 30, 2025: Learns optimal loss weights automatically
    enable_uncertainty_weighting: bool = True


@dataclass
class LossOutput:
    """Structured output from loss computation."""

    total: torch.Tensor
    components: dict[str, torch.Tensor] = field(default_factory=dict[str, Any])
    metrics: dict[str, float] = field(default_factory=dict[str, Any])

    def backward(self, retain_graph: bool = False) -> None:
        """Convenience method for backward pass."""
        self.total.backward(retain_graph=retain_graph)

    def to_dict(self) -> dict[str, float]:
        """Convert to dict[str, Any] of floats for logging."""
        result = {"total": self.total.item()}
        for k, v in self.components.items():
            result[k] = v.item() if isinstance(v, torch.Tensor) else float(v)
        result.update(self.metrics)
        return result


def _to_tensor(value: Any, device: torch.device) -> torch.Tensor:
    """Convert any value to tensor on device."""
    if isinstance(value, torch.Tensor):
        return value.to(device)
    return torch.tensor(float(value), device=device)


class UnifiedLossModule(nn.Module):
    """Unified loss computation for KagamiWorldModel.

    ARCHITECTURAL REDESIGN (Dec 22, 2025):
    =====================================
    SIMPLIFIED for stable gradient flow:
    - Fixed weights (no GradNorm)
    - No CBF-aware scaling
    - Simple KL (no Wasserstein)
    - 3-tier loss hierarchy

    IMPROVED (Dec 29, 2025):
    - E8 commitment warmup to prevent early divergence
    - Step tracking for warmup scheduling

    Usage:
        loss_module = UnifiedLossModule(config)
        loss_output = loss_module(output, target, metrics, core_state)
        loss_output.backward()
    """

    def __init__(self, config: LossConfig | None = None) -> None:
        super().__init__()
        self.config = config or LossConfig()

        # Step counter for warmup scheduling (Dec 29, 2025)
        self._step_counter: int = 0

        self.geometric = GeometricLossComputer(self.config)
        self.dynamic = DynamicLossComputer(self.config)
        self.self_reference = SelfReferenceLossComputer(self.config)
        self.regularization = RegularizationLossComputer(self.config)

        # === UNCERTAINTY WEIGHTING (Kendall 2017) ===
        # Dec 30, 2025: Learns optimal loss weights automatically
        # L = Σ_i [ (1/2σ²) L_i + (1/2) log(σ²) ]
        self.uncertainty_loss: UncertaintyWeightedLoss | None = None
        if self.config.enable_uncertainty_weighting:
            # Initialize with Tier 1 + Tier 2 loss names
            self.uncertainty_loss = UncertaintyWeightedLoss(
                task_names=[
                    "prediction",  # Tier 1
                    "e8_commitment",  # Tier 2
                    "ib_kl",  # Tier 2
                    "rssm_kl",  # Tier 2
                    "seq_ib_recon",  # Tier 2
                    "seq_ib_kl",  # Tier 2
                    "loop_closure",  # Tier 2
                    "fano_synergy",  # Tier 2
                    "h_jepa_pred",  # Tier 2
                    "stability",  # Tier 2
                ],
                init_log_var=0.0,  # σ=1 initially → equal weights
            )
            logger.info("UncertaintyWeightedLoss ENABLED (Kendall 2017)")

        logger.info(
            "UnifiedLossModule initialized (TIERED - Dec 22, 2025)\n"
            f"  Tier 1: prediction={self.config.prediction_weight}\n"
            f"  Tier 2: e8_commitment={self.config.e8_commitment_weight}, "
            f"rssm_kl={self.config.rssm_kl_weight}, "
            f"loop_closure={self.config.loop_closure_weight}, "
            f"fano_synergy={self.config.fano_synergy_weight}, "
            f"h_jepa={self.config.h_jepa_pred_weight}, "
            f"stability={self.config.stability_weight}\n"
            f"  Uncertainty weighting: {self.config.enable_uncertainty_weighting}"
        )

    def forward(
        self,
        output: torch.Tensor,
        target: torch.Tensor,
        metrics: dict[str, Any],
        core_state: Any | None = None,
        colony_octonions: torch.Tensor | None = None,
        hierarchy_levels: dict[str, torch.Tensor] | None = None,
        safety_margin: float | None = None,  # Kept for API compat, ignored
    ) -> LossOutput:
        """Compute losses with tiered architecture.

        TIER 1: Core prediction loss (always computed)
        TIER 2: Essential losses (VQ, IB, RSSM)
        TIER 3: Auxiliary losses (computed only if weight > 0)

        Args:
            output: Model output [B, S, D]
            target: Target tensor [B, S, D]
            metrics: Metrics dict[str, Any] from forward pass
            core_state: Optional CoreState for geometric losses
            colony_octonions: Optional [B, 7, 8] for Fano synergy
            hierarchy_levels: Optional dict[str, Any] for Matryoshka loss
            safety_margin: IGNORED (CBF-aware scaling disabled)

        Returns:
            LossOutput with total loss and all components
        """
        device = output.device
        components: dict[str, torch.Tensor] = {}

        # Increment step counter (Dec 29, 2025)
        self._step_counter += 1

        # Compute losses by tier
        self._compute_tier1_losses(output, target, components)
        self._compute_tier2_losses(metrics, core_state, colony_octonions, device, components)
        self._compute_tier3_losses(metrics, output, core_state, device, components)

        # Sum all components (with uncertainty weighting if enabled)
        total = self._compute_total_loss(components, device)

        # Fill missing components with zeros
        self._fill_missing_components(components, device)

        # Build metrics dict[str, Any]
        loss_metrics: dict[str, Any] = {
            "ib_beta": self.config.ib_beta,
            "loss_step": self._step_counter,
        }

        # Add learned uncertainty weights if available (Dec 30, 2025)
        if hasattr(self, "_last_learned_weights") and self._last_learned_weights is not None:
            loss_metrics["uncertainty_weighting_enabled"] = True
            for task_name, weight in self._last_learned_weights.items():
                loss_metrics[f"uncertainty_weight/{task_name}"] = weight
        else:
            loss_metrics["uncertainty_weighting_enabled"] = False

        return LossOutput(
            total=total,
            components=components,
            metrics=loss_metrics,
        )

    def _compute_tier1_losses(
        self, output: torch.Tensor, target: torch.Tensor, components: dict[str, torch.Tensor]
    ) -> None:
        """Compute TIER 1: Core prediction loss (always computed)."""
        components["prediction"] = (
            symlog_squared_loss(output, target) * self.config.prediction_weight
        )

    def _compute_tier2_losses(
        self,
        metrics: dict[str, Any],
        core_state: Any | None,
        colony_octonions: torch.Tensor | None,
        device: torch.device,
        components: dict[str, torch.Tensor],
    ) -> None:
        """Compute TIER 2: Essential losses (VQ, IB, RSSM, strange loop, Fano, H-JEPA)."""
        self._compute_e8_commitment_loss(core_state, components, metrics, device, colony_octonions)
        self._compute_ib_losses(metrics, device, components)
        self._compute_rssm_losses(metrics, device, components)
        self._compute_fano_synergy_loss(core_state, colony_octonions, components)
        self._compute_loop_closure_loss(metrics, device, components)
        self._compute_h_jepa_loss(metrics, device, components)
        self._compute_stability_loss(components, device)

    def _compute_e8_commitment_loss(
        self,
        core_state: Any | None,
        components: dict[str, torch.Tensor],
        metrics: dict[str, Any],
        device: torch.device,
        colony_octonions: torch.Tensor | None,
    ) -> None:
        """Compute E8 commitment loss for VQ codebook training.

        IMPROVED (Dec 29, 2025):
        - Warmup period to prevent early divergence
        - Gradual weight ramp-up after warmup
        """
        if self.config.e8_commitment_weight > 0 and core_state is not None:
            if core_state.s7_phase is not None and core_state.e8_code is not None:
                e8_indices = (
                    core_state.e8_index
                    if core_state.e8_index is not None
                    else torch.zeros_like(core_state.s7_phase[..., 0]).long()
                )

                # Compute raw commitment loss
                raw_commitment = self.geometric.e8_commitment_loss(
                    core_state.s7_phase,
                    core_state.e8_code,
                    e8_indices,
                )

                # ═══════════════════════════════════════════════════════════════════════
                # FIX (Dec 29, 2025): More gradual E8 commitment ramp-up
                # Research shows VQ training is sensitive to sudden loss changes.
                # Use cosine ramp over 4x warmup period for smoother transition.
                # ═══════════════════════════════════════════════════════════════════════
                warmup_steps = self.config.e8_commitment_warmup_steps
                ramp_duration = warmup_steps * 4  # 4x longer ramp for stability

                if self._step_counter < warmup_steps:
                    # During warmup: zero weight (let encoder stabilize first)
                    components["e8_commitment"] = torch.tensor(0.0, device=device)
                elif self._step_counter < warmup_steps + ramp_duration:
                    # Gradual ramp: cosine schedule from 0 to full weight
                    # Cosine is smoother than linear, reducing training shock
                    import math

                    ramp_progress = (self._step_counter - warmup_steps) / ramp_duration
                    # Cosine ramp: 0 → 1 smoothly (starts slow, ends slow)
                    cosine_factor = 0.5 * (1.0 - math.cos(math.pi * ramp_progress))
                    ramp_weight = cosine_factor * self.config.e8_commitment_weight

                    # Scale the loss (it's already weighted inside geometric.e8_commitment_loss)
                    base_weight = self.config.e8_commitment_weight
                    if base_weight > 0:
                        unweighted = raw_commitment / base_weight
                        components["e8_commitment"] = unweighted * ramp_weight
                    else:
                        components["e8_commitment"] = raw_commitment
                else:
                    # Full weight (after warmup + ramp)
                    components["e8_commitment"] = raw_commitment

    def _compute_ib_losses(
        self,
        metrics: dict[str, Any],
        device: torch.device,
        components: dict[str, torch.Tensor],
    ) -> None:
        """Compute Information Bottleneck losses."""
        # Information Bottleneck KL (simple, no Wasserstein)
        if self.config.ib_kl_weight > 0:
            ib_kl = metrics.get("ib_kl_loss", metrics.get("seq_ib_kl_loss"))
            if ib_kl is not None:
                ib_kl_tensor = _to_tensor(ib_kl, device)
                # Gradient-preserving free bits (Dec 28, 2025)
                # torch.maximum blocks gradients when KL < free_bits!
                # Use softplus-based floor instead
                free_bits = torch.tensor(self.config.ib_free_bits, device=device)
                scale = 0.5  # Controls softness
                ib_kl_soft = ib_kl_tensor + free_bits * scale * F.softplus(
                    (free_bits - ib_kl_tensor) / free_bits
                )
                components["ib_kl"] = ib_kl_soft * self.config.ib_kl_weight * self.config.ib_beta

        # Sequence IB reconstruction (trains decoder)
        if self.config.seq_ib_recon_weight > 0:
            seq_ib_recon = metrics.get("seq_ib_reconstruction_loss")
            if seq_ib_recon is not None:
                components["seq_ib_recon"] = (
                    _to_tensor(seq_ib_recon, device) * self.config.seq_ib_recon_weight
                )

        # Sequence IB KL
        if self.config.seq_ib_kl_weight > 0:
            seq_ib_kl = metrics.get("seq_ib_kl_loss")
            if seq_ib_kl is not None:
                components["seq_ib_kl"] = (
                    _to_tensor(seq_ib_kl, device) * self.config.seq_ib_kl_weight
                )

    def _compute_rssm_losses(
        self,
        metrics: dict[str, Any],
        device: torch.device,
        components: dict[str, torch.Tensor],
    ) -> None:
        """Compute RSSM dynamics losses."""
        # RSSM KL (for dynamics learning)
        if self.config.rssm_kl_weight > 0:
            rssm_kl = metrics.get("rssm_kl_divergence")
            if rssm_kl is not None:
                components["rssm_kl"] = _to_tensor(rssm_kl, device) * self.config.rssm_kl_weight

    def _compute_fano_synergy_loss(
        self,
        core_state: Any | None,
        colony_octonions: torch.Tensor | None,
        components: dict[str, torch.Tensor],
    ) -> None:
        """Compute Fano synergy loss for colony coordination."""
        if self.config.fano_synergy_weight > 0:
            if colony_octonions is not None:
                components["fano_synergy"] = self.geometric.fano_synergy_loss(colony_octonions)
            elif (
                core_state is not None
                and hasattr(core_state, "domain_activations")
                and core_state.domain_activations is not None
            ):
                components["fano_synergy"] = self.geometric.fano_synergy_loss(
                    core_state.domain_activations
                )
            elif core_state is not None and core_state.s7_phase is not None:
                # Use S7 phase as proxy for colony activations
                # S7 phase is [B, S, 7] - average over sequence to get [B, 7]
                s7 = core_state.s7_phase
                B = s7.shape[0]
                # Average over sequence dimension for colony coherence
                s7_mean = s7.mean(dim=1) if s7.dim() == 3 else s7  # [B, 7]

                # Create pseudo-octonions [B, 7, 8]: [1, s7_i] for each of 7 colonies
                # The 7 S7 components become 7 octonions, one per Fano colony
                pseudo_oct = torch.zeros(B, 7, 8, device=s7.device)
                pseudo_oct[:, :, 0] = 1.0  # Real part = 1 for all colonies
                for i in range(7):
                    # Colony i gets the i-th S7 component as its imaginary direction
                    pseudo_oct[:, i, 1 + i] = s7_mean[:, i]

                components["fano_synergy"] = self.geometric.fano_synergy_loss(pseudo_oct)

    def _compute_loop_closure_loss(
        self,
        metrics: dict[str, Any],
        device: torch.device,
        components: dict[str, torch.Tensor],
    ) -> None:
        """Compute strange loop closure loss for Kagami identity."""
        if self.config.loop_closure_weight > 0:
            loop_closure = metrics.get("loop_closure_loss")
            if loop_closure is not None:
                components["loop_closure"] = (
                    _to_tensor(loop_closure, device) * self.config.loop_closure_weight
                )

    def _compute_h_jepa_loss(
        self,
        metrics: dict[str, Any],
        device: torch.device,
        components: dict[str, torch.Tensor],
    ) -> None:
        """Compute H-JEPA prediction loss for world model."""
        if self.config.h_jepa_pred_weight > 0:
            h_jepa_pred = metrics.get("h_jepa_pred_loss")
            if h_jepa_pred is not None:
                components["h_jepa_pred"] = (
                    _to_tensor(h_jepa_pred, device) * self.config.h_jepa_pred_weight
                )
            else:
                # Check for alternative metric names
                h_jepa_predictions = metrics.get("h_jepa_predictions")
                h_jepa_targets = metrics.get("h_jepa_target_predictions")
                if h_jepa_predictions is not None and h_jepa_targets is not None:
                    # Compute prediction loss manually
                    h_jepa_loss = torch.tensor(0.0, device=device)
                    count = 0
                    for key in h_jepa_predictions:
                        pred = h_jepa_predictions[key]
                        target = h_jepa_targets[key].detach()
                        h_jepa_loss = h_jepa_loss + (pred - target).pow(2).mean()
                        count += 1
                    if count > 0:
                        components["h_jepa_pred"] = (
                            h_jepa_loss / count
                        ) * self.config.h_jepa_pred_weight

    def _compute_stability_loss(
        self,
        components: dict[str, torch.Tensor],
        device: torch.device,
    ) -> None:
        """Compute stability regularization loss."""
        if self.config.stability_weight > 0:
            if hasattr(self, "_output") and self._output is not None:
                output = self._output
                if output.shape[-1] > 1:  # type: ignore[index]
                    grad_mag = (output[..., 1:] - output[..., :-1]).norm(dim=-1).mean()  # type: ignore[index]
                    components["stability"] = grad_mag * self.config.stability_weight

    def _compute_tier3_losses(
        self,
        metrics: dict[str, Any],
        output: torch.Tensor,
        core_state: Any | None,
        device: torch.device,
        components: dict[str, torch.Tensor],
    ) -> None:
        """Compute TIER 3: Auxiliary losses (computed only if weight > 0)."""
        # Geometric: Manifold curvature
        if self.config.manifold_curvature_weight > 0 and core_state is not None:
            if core_state.shell_residual is not None and core_state.s7_phase is not None:
                components["manifold_curvature"] = self.geometric.manifold_curvature_loss(
                    core_state.shell_residual,
                    core_state.s7_phase,
                )

        # Dynamic: Chaos/catastrophe
        if self.config.catastrophe_weight > 0 or self.config.chaos_entropy_weight > 0:
            chaos_losses = self.dynamic.chaos_catastrophe_loss(metrics, output, device)
            components.update(chaos_losses)

        # Self-reference (recognition and loop_strength)
        if self.config.recognition_weight > 0 or self.config.loop_strength_weight > 0:
            self_ref_losses = self.self_reference.compute(metrics, device)
            # Only add the enabled ones
            if self.config.recognition_weight > 0 and "recognition" in self_ref_losses:
                components["recognition"] = self_ref_losses["recognition"]
            if self.config.loop_strength_weight > 0 and "loop_strength" in self_ref_losses:
                components["loop_strength"] = self_ref_losses["loop_strength"]

        # Regularization
        if self.config.moe_load_balance_weight > 0 or self.config.kan_regularization_weight > 0:
            reg_losses = self.regularization.compute(metrics, device)
            components.update(reg_losses)

    def _compute_total_loss(
        self, components: dict[str, torch.Tensor], device: torch.device
    ) -> torch.Tensor:
        """Compute total loss with optional uncertainty weighting.

        Dec 30, 2025: If uncertainty weighting is enabled (Kendall 2017),
        learns optimal loss weights automatically via:
            L = Σ_i [ (1/2σ²) L_i + (1/2) log(σ²) ]

        Otherwise, falls back to simple sum of components.
        """
        if self.uncertainty_loss is not None:
            # === UNCERTAINTY-WEIGHTED LOSS (Kendall 2017) ===
            # Filter to only the losses that uncertainty_loss knows about
            known_losses = {}
            for name, value in components.items():
                if name in self.uncertainty_loss.task_to_idx:
                    if isinstance(value, torch.Tensor) and torch.isfinite(value):
                        known_losses[name] = value
                    elif not isinstance(value, torch.Tensor):
                        known_losses[name] = torch.tensor(float(value), device=device)

            if known_losses:
                total, _weighted, weights = self.uncertainty_loss(known_losses)

                # Store learned weights for logging
                self._last_learned_weights = weights

                # Add any unknown losses (Tier 3) directly
                for name, value in components.items():
                    if name not in self.uncertainty_loss.task_to_idx:
                        if isinstance(value, torch.Tensor) and torch.isfinite(value):
                            total = total + value

                return total

        # === FALLBACK: Simple sum (if uncertainty weighting disabled or no losses) ===
        total = torch.tensor(0.0, device=device)
        for loss_tensor in components.values():
            if isinstance(loss_tensor, torch.Tensor) and torch.isfinite(loss_tensor):
                total = total + loss_tensor
            elif not isinstance(loss_tensor, torch.Tensor):
                total = total + torch.tensor(float(loss_tensor), device=device)
        return total

    def _fill_missing_components(
        self, components: dict[str, torch.Tensor], device: torch.device
    ) -> None:
        """Fill missing components with zeros for consistent logging."""
        all_component_names = [
            # Tier 1
            "prediction",
            # Tier 2
            "e8_commitment",
            "ib_kl",
            "rssm_kl",
            "seq_ib_recon",
            "seq_ib_kl",
            "loop_closure",
            "fano_synergy",
            "h_jepa_pred",
            "stability",
            # Tier 3
            "manifold_curvature",
            "catastrophe",
            "chaos_entropy",
            "recognition",
            "loop_strength",
            "moe_load_balance",
            "kan_regularization",
        ]
        for name in all_component_names:
            if name not in components:
                components[name] = torch.tensor(0.0, device=device)


def create_loss_module(
    e8_commitment: float = 0.1,
    fano_synergy: float = 0.01,  # Tier 2: colony coordination
    rssm_kl: float = 0.1,
    loop_closure: float = 0.01,  # Tier 2: strange loop
    h_jepa_pred: float = 0.05,  # Tier 2: multi-horizon prediction
    stability: float = 0.01,  # Tier 2: gradient regularization
    **kwargs: Any,
) -> UnifiedLossModule:
    """Factory for creating loss module with custom weights.

    Args:
        e8_commitment: E8 lattice commitment weight
        fano_synergy: Fano synergy weight (Tier 2)
        rssm_kl: RSSM KL divergence weight
        loop_closure: Strange loop closure weight (Tier 2)
        h_jepa_pred: H-JEPA prediction weight (Tier 2)
        stability: Stability regularization weight (Tier 2)
        **kwargs: Additional config overrides

    Returns:
        Configured UnifiedLossModule
    """
    config = LossConfig(
        e8_commitment_weight=e8_commitment,
        fano_synergy_weight=fano_synergy,
        rssm_kl_weight=rssm_kl,
        loop_closure_weight=loop_closure,
        h_jepa_pred_weight=h_jepa_pred,
        stability_weight=stability,
    )

    # Apply any additional overrides
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)

    return UnifiedLossModule(config)


__all__ = [
    "LossConfig",
    "LossOutput",
    "UncertaintyWeightedLoss",
    "UnifiedLossModule",
    "create_loss_module",
]
