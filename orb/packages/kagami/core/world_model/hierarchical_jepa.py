"""Hierarchical JEPA (H-JEPA) - E8 Nucleus-Native Temporal Prediction.

LeCun (2022): "JEPA-1 extracts low-level representations and performs short-term
predictions. JEPA-2 takes the representations from JEPA-1 and extracts higher-level
representations with which longer-term predictions can be performed."

OPTIMIZED ARCHITECTURE (December 7, 2025):
==========================================

The key insight: E8 residual levels from SemanticResidualE8 ALREADY provide
the representation hierarchy. Using this directly eliminates redundant encoders.

    Level 0: All L E8 levels → Detailed prediction (horizon 1-5 steps)
    Level 1: First L//2 E8 levels → Medium abstraction (horizon 5-20 steps)
    Level 2: First 1-2 E8 levels → High abstraction (horizon 20-100 steps)

Architecture:
    ┌─────────────────────────────────────────────────────────────────┐
    │                 E8-NATIVE HIERARCHICAL JEPA                     │
    │  ┌─────────────────────────────────────────────────────────────┐│
    │  │  INPUT: E8 nucleus sequence [B, L, 8] from hourglass        ││
    │  │                                                              ││
    │  │  Level 2: e8_seq[:, :1, :] → Abstract predictor (horizon 100)││
    │  │  Level 1: e8_seq[:, :L//2, :] → Medium predictor (horizon 20)││
    │  │  Level 0: e8_seq[:, :, :] → Detailed predictor (horizon 5)   ││
    │  │                                                              ││
    │  │  Each predictor: Transformer → latent z → predicted E8      ││
    │  └─────────────────────────────────────────────────────────────┘│
    └─────────────────────────────────────────────────────────────────┘

Benefits vs Legacy:
- No redundant encoders (saves ~500k params)
- Direct gradient flow to nucleus
- Consistent representation hierarchy
- Better long-horizon planning via E8 coarsening

Created: December 6, 2025
Optimized: December 7, 2025 - E8 nucleus-native rewrite
Reference: LeCun (2022) Section 4.6 "Hierarchical JEPA (H-JEPA)"
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass
class E8JEPALevelConfig:
    """Configuration for one H-JEPA level (E8-native)."""

    e8_levels_to_use: int  # How many E8 levels to use (1=most abstract, L=detailed)
    prediction_horizon: int  # Steps to predict ahead
    hidden_dim: int = 128
    n_heads: int = 4
    latent_dim: int = 16  # Latent variable dimension
    dropout: float = 0.1
    use_g2_projection: bool = False  # G₂ irrep tower for planning hierarchy


@dataclass
class E8JEPAConfig:
    """Configuration for E8-Native Hierarchical JEPA."""

    # E8 nucleus dimensions
    e8_dim: int = 8  # Per-level E8 dimension
    max_e8_levels: int = 8  # Max E8 residual levels from nucleus

    # Level configurations (from detailed to abstract)
    levels: list[E8JEPALevelConfig] = field(
        default_factory=lambda: [
            E8JEPALevelConfig(
                e8_levels_to_use=8,  # All levels = detailed
                prediction_horizon=5,
                hidden_dim=128,
                use_g2_projection=False,  # No G₂ for tactile level
            ),
            E8JEPALevelConfig(
                e8_levels_to_use=4,  # Half levels = medium
                prediction_horizon=20,
                hidden_dim=96,
                use_g2_projection=True,  # G₂ irrep for planning level
            ),
            E8JEPALevelConfig(
                e8_levels_to_use=1,  # 1 level = most abstract
                prediction_horizon=100,
                hidden_dim=64,
                use_g2_projection=False,  # Direct for strategy level
            ),
        ]
    )

    # Training
    ema_decay: float = 0.996  # EMA for target predictor
    latent_regularization: float = 0.01

    # VICReg regularization
    use_vicreg: bool = True
    vicreg_sim_weight: float = 25.0
    vicreg_var_weight: float = 25.0
    vicreg_cov_weight: float = 1.0
    vicreg_loss_weight: float = 0.1  # Weight of VICReg in total loss


# =============================================================================
# JEPA MASKING AND REGULARIZATION
# =============================================================================


class JEPAMaskGenerator(nn.Module):
    """Multi-block masking for self-supervised JEPA training."""

    def __init__(self, num_target_blocks: int = 4, mask_ratio: float = 0.75):
        super().__init__()
        self.num_target_blocks = num_target_blocks
        self.mask_ratio = mask_ratio

    def generate_masks(
        self, seq_len: int, batch_size: int
    ) -> tuple[torch.Tensor, list[list[torch.Tensor]]]:
        """Generate context mask and target block masks.

        Args:
            seq_len: Sequence length
            batch_size: Batch size

        Returns:
            context_masks: [B, seq_len] bool mask (True = visible)
            target_masks: List[List[torch.Tensor]] - per-batch list[Any] of block masks
        """
        # Context: visible tokens (1 - mask_ratio)
        num_visible = int(seq_len * (1 - self.mask_ratio))

        context_masks = []
        target_masks = []

        for _ in range(batch_size):
            # Random visible indices for context
            perm = torch.randperm(seq_len)
            visible_idx = perm[:num_visible]
            context_mask = torch.zeros(seq_len, dtype=torch.bool)
            context_mask[visible_idx] = True
            context_masks.append(context_mask)

            # Generate target blocks from masked region
            masked_idx = perm[num_visible:]
            block_size = len(masked_idx) // self.num_target_blocks
            blocks = []
            for i in range(self.num_target_blocks):
                block = masked_idx[i * block_size : (i + 1) * block_size]
                block_mask = torch.zeros(seq_len, dtype=torch.bool)
                block_mask[block] = True
                blocks.append(block_mask)
            target_masks.append(blocks)

        return torch.stack(context_masks), target_masks


class VICRegLoss(nn.Module):
    """VICReg regularization for JEPA (variance, invariance, covariance)."""

    def __init__(self, sim_weight: float = 25.0, var_weight: float = 25.0, cov_weight: float = 1.0):
        super().__init__()
        self.sim_weight = sim_weight
        self.var_weight = var_weight
        self.cov_weight = cov_weight

    def forward(self, z1: torch.Tensor, z2: torch.Tensor) -> torch.Tensor:
        """Compute VICReg loss between two representations.

        Args:
            z1: [B, D] representation 1
            z2: [B, D] representation 2

        Returns:
            Total VICReg loss
        """
        # Invariance loss (MSE between representations)
        sim_loss = F.mse_loss(z1, z2)

        # Variance loss (keep std above threshold)
        std_z1 = torch.sqrt(z1.var(dim=0) + 1e-4)
        std_z2 = torch.sqrt(z2.var(dim=0) + 1e-4)
        var_loss = torch.mean(F.relu(1 - std_z1)) + torch.mean(F.relu(1 - std_z2))

        # Covariance loss (decorrelate dimensions)
        z1_centered = z1 - z1.mean(dim=0)
        z2_centered = z2 - z2.mean(dim=0)
        cov_z1 = (z1_centered.T @ z1_centered) / (z1.shape[0] - 1)
        cov_z2 = (z2_centered.T @ z2_centered) / (z2.shape[0] - 1)
        # Off-diagonal elements
        cov_loss = self._off_diagonal(cov_z1).pow(2).sum() / z1.shape[1]
        cov_loss += self._off_diagonal(cov_z2).pow(2).sum() / z2.shape[1]

        return self.sim_weight * sim_loss + self.var_weight * var_loss + self.cov_weight * cov_loss

    def _off_diagonal(self, x: torch.Tensor) -> torch.Tensor:
        """Extract off-diagonal elements from square matrix."""
        n = x.shape[0]
        return x.flatten()[:-1].view(n - 1, n + 1)[:, 1:].flatten()


# =============================================================================
# E8-NATIVE JEPA LEVEL
# =============================================================================


class E8JEPALevel(nn.Module):
    """Single H-JEPA level operating on E8 nucleus sequence.

    NO redundant encoder - uses E8 nucleus directly.
    Abstraction controlled by how many E8 levels to use.

    G₂ PROJECTION (Dec 27, 2025):
    For planning level, uses G₂ irrep tower to leverage exceptional hierarchy:
    - 7⊗7 = 1⊕7⊕14⊕27 tensor decomposition
    - Provides equivariant transformation respecting octonion structure
    - Enhances medium-horizon prediction with algebraic constraints
    """

    def __init__(
        self,
        level_idx: int,
        config: E8JEPALevelConfig,
        e8_dim: int = 8,
    ):
        super().__init__()
        self.level_idx = level_idx
        self.config = config
        self.e8_dim = e8_dim

        # Input dimension = e8_dim * levels used
        input_dim = e8_dim * config.e8_levels_to_use

        # G₂ PROJECTION (Dec 27, 2025): Optional exceptional hierarchy projection
        self.use_g2_projection = config.use_g2_projection
        if self.use_g2_projection:
            try:
                from kagami_math.g2_irrep_tower import G2IrrepProjection

                # Project 7D imaginary octonion through G₂ irreps (7→49→7)
                self.g2_projector = G2IrrepProjection(
                    input_dim=7,  # Imaginary octonion dimensions
                    irreps="7,14,27",  # G₂ irrep decomposition
                    output_dim=7,
                )
                # Adjust input projection to work with G₂ output
                self.g2_input_proj = nn.Linear(input_dim, input_dim)
                logger.info(f"E8JEPALevel {level_idx}: G₂ projection ENABLED for planning")
            except ImportError as e:
                logger.warning(f"G₂ projection unavailable ({e}), disabled for level {level_idx}")
                self.use_g2_projection = False
                self.g2_projector = None
                self.g2_input_proj = None  # type: ignore[assignment]
        else:
            self.g2_projector = None
            self.g2_input_proj = None  # type: ignore[assignment]

        # Context aggregator (replaces separate encoder)
        # Lightweight transformer to aggregate E8 sequence
        self.context_norm = nn.LayerNorm(input_dim)
        self.context_attn = nn.MultiheadAttention(
            embed_dim=input_dim,
            num_heads=config.n_heads,
            dropout=config.dropout,
            batch_first=True,
        )

        # Latent prior: predicts distribution over latent variable
        self.latent_prior = nn.Sequential(
            nn.Linear(input_dim, config.hidden_dim),
            nn.GELU(),
            nn.Linear(config.hidden_dim, config.latent_dim * 2),  # mean, logvar
        )
        self.latent_dim = config.latent_dim

        # Predictor: context + latent → future E8
        self.predictor = nn.Sequential(
            nn.Linear(input_dim + config.latent_dim, config.hidden_dim),
            nn.LayerNorm(config.hidden_dim),
            nn.GELU(),
            nn.Linear(config.hidden_dim, config.hidden_dim),
            nn.GELU(),
            nn.Linear(config.hidden_dim, input_dim),
        )

        # Target predictor (EMA updated, no grad)
        self.target_predictor = nn.Sequential(
            nn.Linear(input_dim + config.latent_dim, config.hidden_dim),
            nn.LayerNorm(config.hidden_dim),
            nn.GELU(),
            nn.Linear(config.hidden_dim, config.hidden_dim),
            nn.GELU(),
            nn.Linear(config.hidden_dim, input_dim),
        )

        # Initialize target as copy of online
        for p_online, p_target in zip(
            self.predictor.parameters(),
            self.target_predictor.parameters(),
            strict=False,
        ):
            p_target.data.copy_(p_online.data)
            p_target.requires_grad = False

        g2_status = "G₂=ON" if self.use_g2_projection else "G₂=OFF"
        logger.debug(
            f"E8JEPALevel {level_idx}: uses {config.e8_levels_to_use} E8 levels, "
            f"horizon={config.prediction_horizon}, {g2_status}"
        )

    def extract_levels(self, e8_seq: torch.Tensor) -> torch.Tensor:
        """Extract relevant E8 levels for this abstraction.

        Args:
            e8_seq: [B, L, 8] E8 nucleus sequence (L levels)

        Returns:
            [B, e8_levels_to_use * 8] flattened E8 representation
        """
        B, L, D = e8_seq.shape
        levels_to_use = min(self.config.e8_levels_to_use, L)

        # Use first N levels (coarsest to finest progression)
        selected = e8_seq[:, :levels_to_use, :]  # [B, N, 8]

        # Pad if nucleus has fewer levels than expected
        if levels_to_use < self.config.e8_levels_to_use:
            padding = torch.zeros(
                B,
                self.config.e8_levels_to_use - levels_to_use,
                D,
                device=e8_seq.device,
                dtype=e8_seq.dtype,
            )
            selected = torch.cat([selected, padding], dim=1)

        # G₂ PROJECTION (Dec 27, 2025): Apply exceptional hierarchy for planning level
        # Process imaginary octonion dimensions through G₂ irrep tower
        if self.use_g2_projection and self.g2_projector is not None:
            # Extract imaginary part (indices 1-7) from each level
            N = selected.shape[1]
            imag_parts = selected[:, :, 1:8]  # [B, N, 7]
            # Apply G₂ projection to each level
            projected = []
            for i in range(N):
                g2_out = self.g2_projector(imag_parts[:, i, :])  # [B, 7]
                # Reconstruct with real part (first dim)
                real_part = selected[:, i, 0:1]  # [B, 1]
                full_oct = torch.cat([real_part, g2_out], dim=-1)  # [B, 8]
                projected.append(full_oct)
            selected = torch.stack(projected, dim=1)  # [B, N, 8]
            # Apply learned mixing after G₂ transform
            selected_flat = selected.view(B, -1)
            selected_flat = self.g2_input_proj(selected_flat)
            return selected_flat

        return selected.view(B, -1)  # [B, N*8]

    def aggregate_context(self, z: torch.Tensor) -> torch.Tensor:
        """Aggregate temporal context via self-attention.

        Args:
            z: [B, T, D] sequence of representations

        Returns:
            [B, D] aggregated context (mean pooled)
        """
        if z.dim() == 2:
            return z  # Already [B, D]

        # Numerical hardening: prevent NaNs/Infs and mixed-precision overflow from
        # contaminating LayerNorm/attention gradients.
        #
        # Why clamp aggressively?
        # - On some backends, attention/normalization may run in fp16/bf16.
        # - fp16 variance computations can overflow even for "moderate" magnitudes.
        # - This guard is a safety rail for early training instability.
        z = torch.nan_to_num(z, nan=0.0, posinf=0.0, neginf=0.0)
        z = z.clamp(-200.0, 200.0)

        # FIX (Dec 13, 2025): Always exercise context_attn for gradient flow
        # Even with T=1, run through LayerNorm + attention to train parameters.
        # Self-attention on single token is identity + learned bias, which is useful.
        # MPS stability: MultiheadAttention backward can produce NaN gradients on some
        # Apple GPU / torch versions. Prefer a simple, fully stable residual mixing
        # path on MPS while still training LayerNorm parameters.
        if z.device.type == "mps":
            # EXTRA HARDENING: avoid fused LayerNorm backward instability on MPS.
            # Implement LayerNorm explicitly in float32 (stable mean/var reductions),
            # then apply learnable affine (weight/bias). This keeps gradients finite.
            z32 = z.float()
            mean = z32.mean(dim=-1, keepdim=True)
            var = (z32 - mean).pow(2).mean(dim=-1, keepdim=True)
            inv_std = torch.rsqrt(var + float(self.context_norm.eps))
            z_norm32 = (z32 - mean) * inv_std
            w32 = self.context_norm.weight.float()
            b32 = self.context_norm.bias.float()
            z_norm = (z_norm32 * w32 + b32).to(z.dtype)
            z_out = z + 0.1 * z_norm
            z_out = torch.nan_to_num(z_out, nan=0.0, posinf=0.0, neginf=0.0)
            return z_out.mean(dim=1)  # [B, D]

        z_norm = self.context_norm(z)
        z_attn, _ = self.context_attn(z_norm, z_norm, z_norm)
        # Extra guard: if attention produces NaNs/Infs, sanitize to keep gradients finite.
        z_attn = torch.nan_to_num(z_attn, nan=0.0, posinf=0.0, neginf=0.0)
        z_out = z + z_attn  # Residual
        z_out = torch.nan_to_num(z_out, nan=0.0, posinf=0.0, neginf=0.0)

        # Mean pool over time (for T=1, this is just squeeze)
        return z_out.mean(dim=1)  # [B, D]

    def sample_latent(
        self,
        z: torch.Tensor,
        deterministic: bool = False,
    ) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
        """Sample latent variable from prior.

        Args:
            z: [B, D] context representation
            deterministic: If True, use mean (no sampling)

        Returns:
            latent: [B, latent_dim] sampled latent
            info: Dict with mean, logvar, kl_loss
        """
        # Guard against NaN input
        if torch.isnan(z).any():
            device = z.device
            latent = torch.zeros(z.shape[0], self.latent_dim, device=device)
            return latent, {
                "mean": latent,
                "logvar": torch.zeros_like(latent),
                "kl_loss": torch.tensor(0.0, device=device),
            }

        params = self.latent_prior(z)
        mean = params[..., : self.latent_dim]
        logvar = params[..., self.latent_dim :]
        logvar = logvar.clamp(-10, 2)  # Stability

        if deterministic:
            latent = mean
        else:
            std = torch.exp(0.5 * logvar)
            eps = torch.randn_like(std)
            latent = mean + eps * std

        # KL divergence from standard normal (with numerical stability)
        # KL = -0.5 * sum(1 + log(sigma^2) - mu^2 - sigma^2)
        mean_sq = mean.pow(2).clamp(max=100)  # Prevent overflow
        kl_per_dim = -0.5 * (1 + logvar - mean_sq - logvar.exp())
        kl_loss = kl_per_dim.mean()

        # Final NaN guard
        if torch.isnan(kl_loss):
            kl_loss = torch.tensor(0.0, device=z.device)

        return latent, {"mean": mean, "logvar": logvar, "kl_loss": kl_loss}

    def predict_future(
        self,
        z_context: torch.Tensor,
        latent: torch.Tensor,
    ) -> torch.Tensor:
        """Predict future E8 representation.

        Args:
            z_context: [B, D] current context
            latent: [B, latent_dim] latent variable

        Returns:
            [B, D] predicted future E8 representation
        """
        x = torch.cat([z_context, latent], dim=-1)
        return self.predictor(x)

    def predict_multiple_blocks(
        self,
        context_repr: torch.Tensor,
        target_positions: list[torch.Tensor],
    ) -> list[torch.Tensor]:
        """Predict representations for multiple target blocks (I-JEPA style).

        Args:
            context_repr: [B, D] context representation
            target_positions: List of position masks for each target block

        Returns:
            List of [B, D] predicted representations for each target block
        """
        predictions = []
        for _positions in target_positions:
            # Sample latent for each target block
            latent, _ = self.sample_latent(context_repr, deterministic=False)
            # Predict target block representation
            pred = self.predict_future(context_repr, latent)
            predictions.append(pred)
        return predictions

    def update_target_predictor(self, decay: float) -> None:
        """EMA update target predictor."""
        with torch.no_grad():
            for p_online, p_target in zip(
                self.predictor.parameters(),
                self.target_predictor.parameters(),
                strict=False,
            ):
                p_target.data.mul_(decay).add_(p_online.data, alpha=1 - decay)

    def forward(
        self,
        e8_seq: torch.Tensor,
        e8_seq_future: torch.Tensor | None = None,
        deterministic: bool = False,
    ) -> dict[str, Any]:
        """Forward pass for one level.

        Args:
            e8_seq: [B, L, 8] or [B, T, L, 8] E8 nucleus sequence
            e8_seq_future: Future E8 sequence (for training)
            deterministic: Use deterministic latent

        Returns:
            Dict with representations, predictions, losses
        """
        # Handle temporal batches [B, T, L, 8] by extracting per-timestep features
        # then aggregating across T via self-attention.
        if e8_seq.dim() == 4:
            B, T, L, D8 = e8_seq.shape
            e8_seq_flat = e8_seq.view(B * T, L, D8)
            z_current_flat = self.extract_levels(e8_seq_flat)  # [B*T, D]
            z_current_seq = z_current_flat.view(B, T, -1)  # [B, T, D]
            z_context = self.aggregate_context(z_current_seq)  # [B, D]
        else:
            # Non-temporal input: [B, L, 8]
            z_current = self.extract_levels(e8_seq)  # [B, D]
            z_context = self.aggregate_context(z_current)  # [B, D]

        # Sample latent
        latent, latent_info = self.sample_latent(z_context, deterministic)

        # Predict future
        z_pred = self.predict_future(z_context, latent)

        result = {
            "z_context": z_context,
            "z_pred": z_pred,
            "latent": latent,
            "kl_loss": latent_info["kl_loss"],
            "e8_levels_used": self.config.e8_levels_to_use,
        }

        # Training loss if future provided
        if e8_seq_future is not None:
            if e8_seq_future.dim() == 4:
                B2, T2, L2, D2 = e8_seq_future.shape
                e8_seq_future_flat = e8_seq_future.view(B2 * T2, L2, D2)
                z_future_flat = self.extract_levels(e8_seq_future_flat)  # [B2*T2, D]
                z_future_seq = z_future_flat.view(B2, T2, -1)  # [B2, T2, D]
                z_future_context = self.aggregate_context(z_future_seq)  # [B2, D]
            else:
                z_future = self.extract_levels(e8_seq_future)  # [B, D]
                z_future_context = self.aggregate_context(z_future)  # [B, D]

            # Prediction loss (MSE in E8 space) with NaN guard
            if not torch.isnan(z_pred).any() and not torch.isnan(z_future_context).any():
                pred_loss = F.mse_loss(z_pred, z_future_context.detach())
                if not torch.isnan(pred_loss):
                    result["pred_loss"] = pred_loss
                else:
                    result["pred_loss"] = torch.tensor(0.0, device=e8_seq.device)
            else:
                result["pred_loss"] = torch.tensor(0.0, device=e8_seq.device)
            result["z_target"] = z_future_context

        return result


# =============================================================================
# E8-NATIVE HIERARCHICAL JEPA
# =============================================================================


class HierarchicalJEPA(nn.Module):
    """E8 Nucleus-Native Hierarchical JEPA.

    Uses E8 residual levels directly for abstraction hierarchy.
    No redundant encoders - gradient flows directly to nucleus.

    LeCun: "The ability to represent sequences of world states at several levels
    of abstraction is essential to intelligent behavior."

    Usage:
        hjepa = HierarchicalJEPA()

        # Forward with E8 nucleus sequence from hourglass
        e8_seq = hourglass.encode(x)['nucleus_sequence']  # [B, L, 8]
        result = hjepa(e8_seq, e8_seq_future)
        loss = result["total_loss"]

        # Inference: get abstraction at level
        abstract = hjepa.get_abstraction_at_level(e8_seq, level=2)
    """

    def __init__(self, config: E8JEPAConfig | None = None):
        super().__init__()
        self.config = config or E8JEPAConfig()

        # Create E8-native levels
        self.levels = nn.ModuleList()
        for i, level_config in enumerate(self.config.levels):
            level = E8JEPALevel(
                level_idx=i,
                config=level_config,
                e8_dim=self.config.e8_dim,
            )
            self.levels.append(level)

        # VICReg regularization (optional)
        if self.config.use_vicreg:
            self.vicreg_loss = VICRegLoss(
                sim_weight=self.config.vicreg_sim_weight,
                var_weight=self.config.vicreg_var_weight,
                cov_weight=self.config.vicreg_cov_weight,
            )
        else:
            self.vicreg_loss = None  # type: ignore[assignment]

        logger.info(
            f"HierarchicalJEPA (E8-native): {len(self.levels)} levels, "
            f"e8_levels_used={[l.config.e8_levels_to_use for l in self.levels]}, "  # type: ignore[union-attr]
            f"horizons={[l.config.prediction_horizon for l in self.levels]}, "  # type: ignore[union-attr]
            f"vicreg={'enabled' if self.config.use_vicreg else 'disabled'}"
        )

    def forward(
        self,
        e8_seq: torch.Tensor,
        e8_seq_future: torch.Tensor | None = None,
        deterministic: bool = False,
    ) -> dict[str, Any]:
        """Forward pass through all levels.

        Args:
            e8_seq: [B, L, 8] E8 nucleus sequence
            e8_seq_future: [B, L, 8] future E8 sequence (for training)
            deterministic: Use deterministic latents

        Returns:
            Dict with per-level results and total loss
        """
        results = {"levels": []}  # type: ignore[var-annotated]
        total_pred_loss = torch.tensor(0.0, device=e8_seq.device)
        total_kl_loss = torch.tensor(0.0, device=e8_seq.device)
        total_vicreg_loss = torch.tensor(0.0, device=e8_seq.device)

        for level in self.levels:
            level_result = level(
                e8_seq,
                e8_seq_future,
                deterministic=deterministic,
            )
            results["levels"].append(level_result)

            # Accumulate losses
            if "pred_loss" in level_result:
                total_pred_loss = total_pred_loss + level_result["pred_loss"]
            total_kl_loss = total_kl_loss + level_result["kl_loss"]

            # VICReg loss (prevent representation collapse)
            if (
                self.vicreg_loss is not None
                and "z_pred" in level_result
                and "z_target" in level_result
            ):
                vicreg = self.vicreg_loss(level_result["z_pred"], level_result["z_target"])
                total_vicreg_loss = total_vicreg_loss + vicreg

        # Total loss
        results["pred_loss"] = total_pred_loss  # type: ignore[assignment]
        results["kl_loss"] = total_kl_loss * self.config.latent_regularization  # type: ignore[assignment]
        results["vicreg_loss"] = total_vicreg_loss * self.config.vicreg_loss_weight  # type: ignore[assignment]
        results["total_loss"] = results["pred_loss"] + results["kl_loss"] + results["vicreg_loss"]

        return results

    def predict_hierarchy(
        self,
        e8_seq: torch.Tensor,
    ) -> dict[str, torch.Tensor]:
        """Predict at all hierarchy levels.

        Args:
            e8_seq: [B, L, 8] E8 nucleus sequence

        Returns:
            Dict with predictions at each level
        """
        self.eval()
        with torch.no_grad():
            result = self.forward(e8_seq, deterministic=True)

        predictions = {}
        for i, level_result in enumerate(result["levels"]):
            predictions[f"level_{i}_pred"] = level_result["z_pred"]
            predictions[f"level_{i}_context"] = level_result["z_context"]

        return predictions

    def update_target_predictors(self) -> None:
        """Update all target predictors with EMA."""
        for level in self.levels:
            level.update_target_predictor(self.config.ema_decay)  # type: ignore[operator]

    def get_abstraction_at_level(
        self,
        e8_seq: torch.Tensor,
        level: int,
    ) -> torch.Tensor:
        """Get representation at specific abstraction level.

        Args:
            e8_seq: [B, L, 8] E8 nucleus sequence
            level: Which level (0=detailed, higher=abstract)

        Returns:
            [B, D] encoding at that level
        """
        if level >= len(self.levels):
            level = len(self.levels) - 1

        result = self.levels[level](e8_seq, deterministic=True)
        return result["z_context"]


# =============================================================================
# SINGLETON ACCESS
# =============================================================================

_hierarchical_jepa: HierarchicalJEPA | None = None


def get_hierarchical_jepa(
    config: E8JEPAConfig | None = None,
) -> HierarchicalJEPA:
    """Get or create global HierarchicalJEPA.

    Args:
        config: E8JEPAConfig configuration (optional)

    Returns:
        Global HierarchicalJEPA instance
    """
    global _hierarchical_jepa

    # Recreate if config differs (check e8_dim as proxy)
    if _hierarchical_jepa is not None and config is not None:
        if _hierarchical_jepa.config.e8_dim != config.e8_dim:
            logger.info("Recreating H-JEPA: config changed")
            _hierarchical_jepa = None

    if _hierarchical_jepa is None:
        _hierarchical_jepa = HierarchicalJEPA(config)
        logger.info(
            f"Created global HierarchicalJEPA (E8-native, levels={len(_hierarchical_jepa.levels)})"
        )
    return _hierarchical_jepa


def reset_hierarchical_jepa() -> None:
    """Reset global H-JEPA (for testing)."""
    global _hierarchical_jepa
    _hierarchical_jepa = None


def create_hierarchical_jepa(
    n_levels: int = 3,
    max_e8_levels: int = 8,
) -> HierarchicalJEPA:
    """Create H-JEPA configured for K OS world model.

    Args:
        n_levels: Number of hierarchy levels
        max_e8_levels: Max E8 residual levels available

    Returns:
        Configured HierarchicalJEPA
    """
    # Configure levels with decreasing E8 detail
    level_configs = []
    horizons = [5, 20, 50, 100][:n_levels]
    e8_levels_used = [max_e8_levels, max_e8_levels // 2, 2, 1][:n_levels]

    for i in range(n_levels):
        level_configs.append(
            E8JEPALevelConfig(
                e8_levels_to_use=max(1, e8_levels_used[i]),
                prediction_horizon=horizons[i],
                hidden_dim=128 - i * 16,  # Simpler nets at higher abstraction
            )
        )

    config = E8JEPAConfig(
        e8_dim=8,
        max_e8_levels=max_e8_levels,
        levels=level_configs,
    )
    return HierarchicalJEPA(config)
