"""Prediction and dynamic losses.

This module provides losses for dynamic components:
- RSSM (Recurrent State Space Model)
- Chaos and catastrophe dynamics
- Self-reference (strange loops)
- Regularization (MoE, KAN)

Created: December 15, 2025 (refactored from unified_loss.py)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami.core.world_model.losses.composed import LossConfig

import torch
import torch.nn as nn
import torch.nn.functional as F


def _to_tensor(value: Any, device: torch.device) -> torch.Tensor:
    """Convert any value to tensor on device."""
    if isinstance(value, torch.Tensor):
        return value.to(device)
    return torch.tensor(float(value), device=device)


class DynamicLossComputer(nn.Module):
    """Computes losses for dynamic components (RSSM, Chaos, Catastrophe)."""

    def __init__(self, config: LossConfig) -> None:
        super().__init__()
        self.config = config

    def rssm_loss(
        self,
        metrics: dict[str, Any],
        device: torch.device,
    ) -> dict[str, torch.Tensor]:
        """Compute all RSSM losses from metrics dict[str, Any] (DreamerV3-style).

        DreamerV3 uses:
        - L_dyn = max(1, KL(sg(posterior) || prior)) * βdyn
        - L_rep = max(1, KL(posterior || sg(prior))) * βrep

        With free bits = 1.0 nat to prevent posterior collapse.
        """
        losses = {}

        # DreamerV3 KL split (preferred): dyn/rep separately
        # FIX (Dec 22, 2025): RSSM already applies free_bits internally via
        # balanced_kl_loss_categorical(free_bits=3.0). Do NOT double-apply here.
        kl_dyn = metrics.get("rssm_kl_dyn")
        kl_rep = metrics.get("rssm_kl_rep")

        if kl_dyn is not None or kl_rep is not None:
            kl_dyn_t = _to_tensor(kl_dyn or 0.0, device)
            kl_rep_t = _to_tensor(kl_rep or 0.0, device)
            # No torch.maximum - RSSM handles free_bits internally

            # Expose components for logging/weighting
            losses["rssm_kl_dyn"] = kl_dyn_t * self.config.rssm_dynamics_weight
            losses["rssm_kl_rep"] = kl_rep_t * self.config.rssm_representation_weight

            # Keep backward-compatible combined key
            losses["rssm_kl"] = (
                losses["rssm_kl_dyn"] + losses["rssm_kl_rep"]
            ) * self.config.rssm_kl_weight
        else:
            # Fallback: single KL (legacy)
            # FIX (Dec 22, 2025): Don't double-apply free_bits - RSSM already handles it
            # internally via balanced_kl_loss_categorical(free_bits=3.0)
            kl = metrics.get("rssm_kl_divergence", 0.0)
            kl_tensor = _to_tensor(kl, device)
            # Only apply free_bits floor if KL is exactly 0 (no RSSM present)
            if kl_tensor.item() == 0.0:
                free_bits_floor = torch.tensor(float(self.config.ib_free_bits), device=device)
                kl_tensor = free_bits_floor
            losses["rssm_kl"] = kl_tensor * self.config.rssm_kl_weight

        # Reconstruction (symlog is applied at prediction level)
        recon = metrics.get("rssm_reconstruction_loss", 0.0)
        losses["rssm_reconstruction"] = (
            _to_tensor(recon, device) * self.config.rssm_reconstruction_weight
        )

        # Reward prediction
        reward = metrics.get("rssm_reward_loss", 0.0)
        losses["rssm_reward"] = _to_tensor(reward, device) * self.config.rssm_reward_weight

        # Continue prediction
        cont = metrics.get("rssm_continue_loss", 0.0)
        losses["rssm_continue"] = _to_tensor(cont, device) * self.config.rssm_continue_weight

        return losses

    def chaos_catastrophe_loss(
        self,
        metrics: dict[str, Any],
        output: torch.Tensor,
        device: torch.device,
    ) -> dict[str, torch.Tensor]:
        """Compute chaos and catastrophe losses.

        FIX (Dec 5, 2025): Changed from fixed Lorenz Lyapunov to output-based
        chaos metric. The Lorenz system at σ=10, ρ=28, β=8/3 has λ ≈ 0.9 always,
        which made the loss explode trying to reach λ = 0.05.

        New approach: Use output variance as proxy for chaos. Target moderate
        variance (not too ordered, not too chaotic).
        """
        losses = {}

        # Catastrophe risk
        cat_risk = metrics.get("catastrophe_risk_tensor", metrics.get("catastrophe_risk"))
        if cat_risk is not None:
            # Keep gradient if caller provided a tensor.
            cat_risk_t = (
                cat_risk
                if isinstance(cat_risk, torch.Tensor)
                else torch.tensor(float(cat_risk), device=device)
            )
            losses["catastrophe"] = cat_risk_t * self.config.catastrophe_weight
        else:
            losses["catastrophe"] = torch.tensor(0.0, device=device)

        # Stability (gradient magnitude regularization)
        if output.shape[-1] > 1:
            grad_mag = (output[..., 1:] - output[..., :-1]).norm(dim=-1).mean()
            losses["stability"] = grad_mag * self.config.stability_weight
        else:
            losses["stability"] = torch.tensor(0.0, device=device)

        # Edge-of-chaos loss: Use OUTPUT-BASED metrics instead of fixed Lorenz
        # Target: moderate variance (not collapsed, not exploding)
        # This is differentiable and trainable!
        if output.numel() > 1:
            # Compute output variance as chaos proxy
            output_var = output.var()

            # Target variance range: [0.5, 2.0] (edge of chaos)
            # Below 0.5 = too ordered (collapsed), above 2.0 = too chaotic
            target_var = 1.0
            var_margin = 0.5

            # Soft hinge loss: penalize being outside [target - margin, target + margin]
            below_penalty = F.relu(target_var - var_margin - output_var)
            above_penalty = F.relu(output_var - target_var - var_margin)
            chaos_loss = (below_penalty + above_penalty).pow(2)

            losses["chaos_entropy"] = chaos_loss * self.config.chaos_entropy_weight
        else:
            losses["chaos_entropy"] = torch.tensor(0.0, device=device)

        # Still log Lyapunov for monitoring (but don't use for loss)
        # The Lyapunov from Lorenz is informational only
        edge_metrics = metrics.get("edge_of_chaos", {})
        if edge_metrics:
            lyapunov = edge_metrics.get("lyapunov") or edge_metrics.get("lyapunov_exponent", 0.0)
            if isinstance(lyapunov, int | float):
                # Store for monitoring but don't affect loss
                metrics["_monitored_lyapunov"] = lyapunov

        return losses


class SelfReferenceLossComputer(nn.Module):
    """Computes strange loop self-reference losses."""

    def __init__(self, config: LossConfig) -> None:
        super().__init__()
        self.config = config

    def compute(
        self,
        metrics: dict[str, Any],
        device: torch.device,
    ) -> dict[str, torch.Tensor]:
        """Compute all self-reference losses."""
        losses = {}

        # Loop closure (output ≈ input through observation)
        loop_closure = metrics.get("loop_closure_loss")
        if loop_closure is not None:
            losses["loop_closure"] = (
                _to_tensor(loop_closure, device) * self.config.loop_closure_weight
            )
        else:
            losses["loop_closure"] = torch.tensor(0.0, device=device)

        # Self-recognition (recognition score → 1)
        recognition = metrics.get("recognition_loss")
        if recognition is not None:
            losses["recognition"] = _to_tensor(recognition, device) * self.config.recognition_weight
        else:
            losses["recognition"] = torch.tensor(0.0, device=device)

        # Loop strength (feedback loop active)
        loop_strength = metrics.get("loop_strength_loss")
        if loop_strength is not None:
            losses["loop_strength"] = (
                _to_tensor(loop_strength, device) * self.config.loop_strength_weight
            )
        else:
            losses["loop_strength"] = torch.tensor(0.0, device=device)

        return losses


class RegularizationLossComputer(nn.Module):
    """Computes regularization losses (MoE, KAN, etc.)."""

    def __init__(self, config: LossConfig) -> None:
        super().__init__()
        self.config = config

    def compute(
        self,
        metrics: dict[str, Any],
        device: torch.device,
    ) -> dict[str, torch.Tensor]:
        """Compute all regularization losses."""
        losses = {}

        # MoE load balance
        moe_loss = metrics.get("total_moe_loss", 0.0)
        losses["moe_load_balance"] = (
            _to_tensor(moe_loss, device) * self.config.moe_load_balance_weight
        )

        # KAN spline regularization
        kan_loss = metrics.get("total_kan_loss", 0.0)
        losses["kan_regularization"] = (
            _to_tensor(kan_loss, device) * self.config.kan_regularization_weight
        )

        return losses


__all__ = [
    "DynamicLossComputer",
    "RegularizationLossComputer",
    "SelfReferenceLossComputer",
]
