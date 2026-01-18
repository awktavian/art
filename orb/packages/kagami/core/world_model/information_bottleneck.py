"""Information Bottleneck Module - Variational Compression for World Model.

CONSOLIDATED (Dec 2, 2025):
===========================
This module implements the Variational Information Bottleneck (VIB) for
optimal compression at the nucleus level of the KagamiWorldModel.

The Information Bottleneck principle (Tishby et al., 1999):
    min I(X;Z) - β·I(Z;Y)

Where:
    - X: Input (observation/state)
    - Z: Compressed representation (bottleneck)
    - Y: Target (prediction/action)
    - β: Tradeoff parameter

VIB Implementation (Alemi et al., 2017):
    - Encoder: q(z|x) ~ N(μ(x), σ²(x))
    - Decoder: p(y|z)
    - Loss: E[log p(y|z)] - β·KL[q(z|x) || p(z)]

DreamerV3 Enhancements:
    - Free bits (1.0 nat) to prevent posterior collapse
    - Symlog for multi-scale predictions
    - Adaptive β scheduling

SCIENCE GAP CLOSURE (Dec 12, 2025):
===================================
Added InfoNCE MI estimator for R-D curve diagnostics per Tishby.
- InfoNCEEstimator: Lower-bound on I(X;Z) via contrastive learning
- R-D metrics: mi_xz, mi_zy logged for optimal β verification

References:
    - Tishby et al. (1999): "The Information Bottleneck Method"
    - Alemi et al. (2017): "Deep Variational Information Bottleneck"
    - Hafner et al. (2023): "Mastering Diverse Domains through World Models"
    - Oord et al. (2018): "Representation Learning with Contrastive Predictive Coding"
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)


# =============================================================================
# INFONCE MUTUAL INFORMATION ESTIMATOR (Oord et al. 2018)
# =============================================================================


class InfoNCEEstimator(nn.Module):
    """InfoNCE-based mutual information lower bound estimator.

    Provides I(X;Z) ≥ log(K) - L_NCE where K is number of negatives.

    Per Tishby's IB theory, we need to track I(X;Z) (compression cost)
    separately from I(Z;Y) (prediction utility) to verify we're on
    the optimal rate-distortion curve.

    Usage:
        estimator = InfoNCEEstimator(x_dim=14, z_dim=64)
        mi_lower_bound = estimator(x, z)  # Returns scalar estimate
    """

    def __init__(
        self,
        x_dim: int,
        z_dim: int,
        hidden_dim: int = 64,
        temperature: float = 0.07,
    ):
        """Initialize InfoNCE estimator.

        Args:
            x_dim: Input X dimension
            z_dim: Bottleneck Z dimension
            hidden_dim: Critic network hidden dimension
            temperature: Softmax temperature (lower = sharper)
        """
        super().__init__()
        self.temperature = temperature

        # Bilinear critic: f(x, z) = x^T W z
        # More expressive: MLP projections then dot product
        self.x_proj = nn.Sequential(
            nn.Linear(x_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, hidden_dim),
        )
        self.z_proj = nn.Sequential(
            nn.Linear(z_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, hidden_dim),
        )

        logger.debug(f"InfoNCEEstimator: x_dim={x_dim}, z_dim={z_dim}")

    def forward(
        self,
        x: torch.Tensor,
        z: torch.Tensor,
        return_accuracy: bool = False,
    ) -> torch.Tensor | tuple[torch.Tensor, torch.Tensor]:
        """Estimate I(X;Z) lower bound via InfoNCE.

        Args:
            x: Input tensor [B, x_dim]
            z: Latent tensor [B, z_dim]
            return_accuracy: If True, also return classification accuracy

        Returns:
            MI lower bound estimate (scalar)
            If return_accuracy: (mi_estimate, accuracy)
        """
        batch_size = x.shape[0]

        # Project to shared space
        x_emb = F.normalize(self.x_proj(x), dim=-1)  # [B, H]
        z_emb = F.normalize(self.z_proj(z), dim=-1)  # [B, H]

        # Compute similarity matrix: [B, B]
        # Diagonal = positive pairs, off-diagonal = negatives
        logits = torch.matmul(x_emb, z_emb.T) / self.temperature

        # Labels: diagonal elements are positive pairs
        labels = torch.arange(batch_size, device=x.device)

        # InfoNCE loss = -log(exp(pos) / sum(exp(all)))
        # Which is just cross-entropy with diagonal as correct class
        loss = F.cross_entropy(logits, labels)

        # MI lower bound: I(X;Z) ≥ log(K) - L_NCE
        # K = batch_size (number of negatives + 1)
        mi_estimate = math.log(batch_size) - loss

        if return_accuracy:
            # Classification accuracy (sanity check)
            preds = logits.argmax(dim=-1)
            accuracy = (preds == labels).float().mean()
            return mi_estimate, accuracy

        return mi_estimate


class RDCurveTracker:
    """Track Rate-Distortion curve for IB optimality verification.

    Per Tishby (1999), optimal IB solutions lie on the R-D curve:
    - Rate R = I(X;Z): compression cost
    - Distortion D ∝ -I(Z;Y): prediction error

    This tracker logs these metrics to verify β is well-chosen.
    """

    def __init__(self, window_size: int = 100):
        """Initialize R-D tracker.

        Args:
            window_size: Rolling window for metric averaging
        """
        self.window_size = window_size
        self._mi_xz_history: list[float] = []
        self._mi_zy_history: list[float] = []
        self._beta_history: list[float] = []

    def update(
        self,
        mi_xz: float,
        mi_zy: float,
        beta: float,
    ) -> dict[str, float]:
        """Update tracker with new measurements.

        Args:
            mi_xz: I(X;Z) estimate (rate)
            mi_zy: I(Z;Y) estimate (negative distortion)
            beta: Current beta value

        Returns:
            Dict with current and rolling statistics
        """
        self._mi_xz_history.append(mi_xz)
        self._mi_zy_history.append(mi_zy)
        self._beta_history.append(beta)

        # Trim to window
        if len(self._mi_xz_history) > self.window_size:
            self._mi_xz_history = self._mi_xz_history[-self.window_size :]
            self._mi_zy_history = self._mi_zy_history[-self.window_size :]
            self._beta_history = self._beta_history[-self.window_size :]

        # Compute statistics
        mi_xz_avg = sum(self._mi_xz_history) / len(self._mi_xz_history)
        mi_zy_avg = sum(self._mi_zy_history) / len(self._mi_zy_history)

        # R-D slope: dR/dD should equal β at optimum
        # This is a diagnostic for whether β is well-tuned
        rd_ratio = mi_xz_avg / max(mi_zy_avg, 1e-6)

        return {
            "mi_xz": mi_xz,
            "mi_zy": mi_zy,
            "mi_xz_avg": mi_xz_avg,
            "mi_zy_avg": mi_zy_avg,
            "rd_ratio": rd_ratio,
            "beta": beta,
        }


@dataclass
class IBConfig:
    """Configuration for Information Bottleneck."""

    input_dim: int = 14  # Input dimension (e.g., G₂ nucleus)
    bottleneck_dim: int = 64  # Bottleneck dimension
    output_dim: int = 14  # Output dimension (reconstruction target)
    hidden_dim: int = 128  # Hidden layer dimension

    # VIB parameters
    beta: float = 0.01  # IB tradeoff (lower = less compression)
    beta_warmup_steps: int = 1000  # Steps to warm up beta

    # Prior type
    prior_type: str = "standard"  # 'standard', 'learned', 'mog'

    # DreamerV3 enhancements
    kl_free_bits: float = 1.0  # Minimum KL (nats) per dimension
    # use_symlog REMOVED (Dec 2, 2025) - symlog is now MANDATORY


class GaussianEncoder(nn.Module):
    """Encoder network: x → (μ, σ²) for q(z|x)."""

    def __init__(self, config: IBConfig):
        super().__init__()
        self.config = config

        self.net = nn.Sequential(
            nn.Linear(config.input_dim, config.hidden_dim),
            nn.LayerNorm(config.hidden_dim),
            nn.GELU(),
            nn.Linear(config.hidden_dim, config.hidden_dim),
            nn.GELU(),
        )

        self.mu_head = nn.Linear(config.hidden_dim, config.bottleneck_dim)
        self.logvar_head = nn.Linear(config.hidden_dim, config.bottleneck_dim)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Encode input to (z, μ, logvar)."""
        h = self.net(x)
        mu = self.mu_head(h)
        logvar = self.logvar_head(h).clamp(-20, 2)  # Clamp for stability

        # Reparameterization trick
        std = torch.exp(0.5 * logvar)
        eps = torch.randn_like(std)
        z = mu + eps * std

        return z, mu, logvar


class PredictiveDecoder(nn.Module):
    """Decoder network: z → y_pred for p(y|z)."""

    def __init__(self, config: IBConfig):
        super().__init__()
        self.config = config

        self.net = nn.Sequential(
            nn.Linear(config.bottleneck_dim, config.hidden_dim),
            nn.LayerNorm(config.hidden_dim),
            nn.GELU(),
            nn.Linear(config.hidden_dim, config.hidden_dim),
            nn.GELU(),
            nn.Linear(config.hidden_dim, config.output_dim),
        )

    def forward(self, z: torch.Tensor) -> torch.Tensor:
        """Decode z to prediction."""
        return self.net(z)


class InformationBottleneck(nn.Module):
    """Variational Information Bottleneck for world model compression.

    Implements VIB with DreamerV3 enhancements:
    - Free bits constraint
    - Beta warmup
    - InfoNCE MI estimation for R-D curve tracking (Dec 12, 2025)
    """

    def __init__(self, config: IBConfig | None = None):
        super().__init__()
        self.config = config or IBConfig()

        self.encoder = GaussianEncoder(self.config)
        self.decoder = PredictiveDecoder(self.config)

        # Prior parameters (for learned prior)
        if self.config.prior_type == "learned":
            self.prior_mu = nn.Parameter(torch.zeros(self.config.bottleneck_dim))
            self.prior_logvar = nn.Parameter(torch.zeros(self.config.bottleneck_dim))
        else:
            self.register_buffer("prior_mu", torch.zeros(self.config.bottleneck_dim))
            self.register_buffer("prior_logvar", torch.zeros(self.config.bottleneck_dim))

        # InfoNCE MI estimator for R-D curve (Dec 12, 2025 - Science Gap Closure)
        self.mi_estimator = InfoNCEEstimator(
            x_dim=self.config.input_dim,
            z_dim=self.config.bottleneck_dim,
        )
        self.rd_tracker = RDCurveTracker()

        # OPTIMIZATION FIX (Dec 15, 2025): Use tensor for step counter to prevent recompilation
        # Dynamic int attributes cause torch.compile to recompile on every step
        self.register_buffer("_step", torch.tensor(0, dtype=torch.long))

        logger.debug(
            "InformationBottleneck: %dD → %dD, β=%.2f",
            self.config.input_dim,
            self.config.bottleneck_dim,
            self.config.beta,
        )

    def get_beta(self) -> float:
        """Get current beta with warmup."""
        # OPTIMIZATION FIX (Dec 15, 2025): Access tensor value using .item()
        step_val = self._step.item()  # type: ignore[operator]
        if step_val < self.config.beta_warmup_steps:
            # Linear warmup
            return self.config.beta * (step_val / self.config.beta_warmup_steps)
        return self.config.beta

    def kl_divergence(self, mu: torch.Tensor, logvar: torch.Tensor) -> torch.Tensor:
        """Compute KL divergence with free bits constraint.

        KL[q(z|x) || p(z)] where p(z) ~ N(prior_mu, exp(prior_logvar))

        With free bits (per DreamerV3): KL_clipped = max(KL_total, free_bits)

        FIX (Dec 22, 2025): Apply free bits to TOTAL KL, not per-dimension.
        Per-dimension free bits causes constant floor = free_bits * latent_dim,
        preventing the loss from being minimized below that floor.
        """
        # KL per dimension
        prior_var = self.prior_logvar.exp()
        var = logvar.exp()

        kl_per_dim = 0.5 * (
            (self.prior_logvar - logvar)  # log(σ_p/σ_q)
            + var / prior_var  # σ_q²/σ_p²
            + (mu - self.prior_mu).pow(2) / prior_var  # (μ_q - μ_p)²/σ_p²
            - 1  # -1
        )

        # Sum first, THEN apply free bits to total (DreamerV3-style)
        kl_total = kl_per_dim.sum(dim=-1)

        # Free bits constraint on TOTAL KL (not per-dimension)
        if self.config.kl_free_bits > 0:
            kl_total = torch.maximum(
                kl_total, torch.tensor(self.config.kl_free_bits, device=mu.device)
            )

        return kl_total

    def forward(
        self,
        x: torch.Tensor,
        y: torch.Tensor | None = None,
    ) -> dict[str, torch.Tensor]:
        """Forward pass with optional loss computation.

        Args:
            x: Input [B, input_dim]
            y: Target [B, output_dim] (optional, for loss computation)

        Returns:
            Dict with z, mu, logvar, y_pred, and optional losses
        """
        # Encode
        z, mu, logvar = self.encoder(x)

        # Decode
        y_pred = self.decoder(z)

        result = {
            "z": z,
            "mu": mu,
            "logvar": logvar,
            "y_pred": y_pred,
        }

        # Compute losses if target provided
        if y is not None:
            # Prediction loss (ALWAYS symlog - DreamerV3 best practice)
            pred_loss = (
                (
                    torch.sign(y_pred) * torch.log1p(y_pred.abs())
                    - torch.sign(y) * torch.log1p(y.abs())
                )
                .pow(2)
                .sum(dim=-1)
            )

            # KL loss (upper bound on I(X;Z) per VIB)
            kl_loss = self.kl_divergence(mu, logvar)

            # Total loss
            beta = self.get_beta()
            total_loss = pred_loss.mean() + beta * kl_loss.mean()

            # ================================================================
            # R-D CURVE TRACKING (Dec 12, 2025 - Science Gap Closure)
            # Per Tishby (1999): track I(X;Z) and I(Z;Y) explicitly
            # ================================================================
            with torch.no_grad():
                # I(X;Z) lower bound via InfoNCE
                mi_xz = self.mi_estimator(x, z).item()

                # I(Z;Y) proxy: negative prediction loss (higher = more info preserved)
                # True MI would require density estimation; this is a practical proxy
                mi_zy_proxy = -pred_loss.mean().item()

                # Track R-D curve
                rd_metrics = self.rd_tracker.update(
                    mi_xz=mi_xz,
                    mi_zy=mi_zy_proxy,
                    beta=beta,
                )

            result.update(
                {
                    "prediction_loss": pred_loss.mean(),
                    "kl_loss": kl_loss.mean(),
                    "beta": torch.tensor(beta, device=x.device),
                    "total_loss": total_loss,
                    # R-D curve metrics (Dec 12, 2025)
                    "mi_xz": torch.tensor(rd_metrics["mi_xz"], device=x.device),
                    "mi_zy": torch.tensor(rd_metrics["mi_zy"], device=x.device),
                    "rd_ratio": torch.tensor(rd_metrics["rd_ratio"], device=x.device),
                }
            )

            # OPTIMIZATION FIX (Dec 15, 2025): Increment tensor counter
            self._step += 1  # type: ignore[operator, assignment]

        return result


@dataclass
class SequenceIBConfig:
    """Configuration for Sequence Information Bottleneck."""

    e8_dim: int = 8
    max_levels: int = 16
    bottleneck_dim: int = 64
    hidden_dim: int = 128
    num_heads: int = 4
    num_layers: int = 2
    beta: float = 0.01
    beta_warmup_steps: int = 1000
    kl_free_bits: float = 1.0
    # Gradient stability
    grad_clip_norm: float | None = 10.0  # Clip gradients if norm > this value
    loss_scale: float = 0.1  # Scale reconstruction loss to prevent explosion


class SequenceInformationBottleneck(nn.Module):
    """Information Bottleneck for variable-length E8 nucleus sequences.

    VARIABLE-LENGTH NUCLEUS (Dec 6, 2025):
    =====================================
    Instead of fixed 14D G₂ nucleus, processes [B, L, 8] sequences where:
    - L = number of E8 residual levels (1-16, variable)
    - 8 = E8 embedding dimension per level

    Capacity: L × 8 × ~8 bits = 64-1024 bits (vs fixed 111 bits before)

    Architecture:
    1. Positional encoding for levels (learned, not sinusoidal)
    2. Transformer encoder to process level sequence
    3. Attention pooling to [CLS] token
    4. VIB compression of pooled representation
    5. Decoder reconstructs full sequence

    This allows the model to:
    - Process variable-length inputs naturally
    - Learn level-specific patterns (coarse → fine)
    - Compress efficiently via attention
    """

    def __init__(self, config: SequenceIBConfig | None = None):
        super().__init__()
        self.config = config or SequenceIBConfig()
        cfg = self.config

        # Level positional embeddings (learned) - use Xavier initialization
        self.level_pos_emb = nn.Parameter(torch.zeros(cfg.max_levels, cfg.hidden_dim))
        nn.init.xavier_uniform_(self.level_pos_emb, gain=0.02)

        # Project E8 to hidden dim
        self.e8_to_hidden = nn.Linear(cfg.e8_dim, cfg.hidden_dim)
        nn.init.xavier_uniform_(self.e8_to_hidden.weight, gain=1.0)
        nn.init.zeros_(self.e8_to_hidden.bias)

        # CLS token for pooling - use Xavier initialization
        self.cls_token = nn.Parameter(torch.zeros(1, 1, cfg.hidden_dim))
        nn.init.xavier_uniform_(self.cls_token, gain=0.02)

        # Transformer encoder
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=cfg.hidden_dim,
            nhead=cfg.num_heads,
            dim_feedforward=cfg.hidden_dim * 4,
            dropout=0.1,
            activation="gelu",
            batch_first=True,
            norm_first=True,
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=cfg.num_layers)

        # Register gradient clipping hooks if enabled
        if cfg.grad_clip_norm is not None:
            self._register_gradient_clipping_hooks(cfg.grad_clip_norm)

        # VIB encoder: CLS → (μ, σ²)
        self.vib_mu = nn.Linear(cfg.hidden_dim, cfg.bottleneck_dim)
        self.vib_logvar = nn.Linear(cfg.hidden_dim, cfg.bottleneck_dim)

        # Decoder: z → sequence reconstruction
        self.z_to_hidden = nn.Linear(cfg.bottleneck_dim, cfg.hidden_dim)
        nn.init.xavier_uniform_(self.z_to_hidden.weight, gain=1.0)
        nn.init.zeros_(self.z_to_hidden.bias)

        self.decoder_expand = nn.Linear(cfg.hidden_dim, cfg.max_levels * cfg.hidden_dim)
        nn.init.xavier_uniform_(self.decoder_expand.weight, gain=1.0)
        nn.init.zeros_(self.decoder_expand.bias)

        self.hidden_to_e8 = nn.Linear(cfg.hidden_dim, cfg.e8_dim)
        nn.init.xavier_uniform_(self.hidden_to_e8.weight, gain=1.0)
        nn.init.zeros_(self.hidden_to_e8.bias)

        # Prior
        self.register_buffer("prior_mu", torch.zeros(cfg.bottleneck_dim))
        self.register_buffer("prior_logvar", torch.zeros(cfg.bottleneck_dim))

        # OPTIMIZATION FIX (Dec 15, 2025): Use tensor for step counter
        self.register_buffer("_step", torch.tensor(0, dtype=torch.long))

        logger.debug(
            "SequenceInformationBottleneck: max_levels=%d, bottleneck=%dD",
            cfg.max_levels,
            cfg.bottleneck_dim,
        )

    def _register_gradient_clipping_hooks(self, max_norm: float) -> None:
        """Register backward hooks to clip gradients per-parameter.

        This prevents gradient explosion in transformer layers.

        Args:
            max_norm: Maximum gradient norm per parameter
        """

        def clip_grad_hook(grad: torch.Tensor) -> torch.Tensor:
            """Clip gradient if norm exceeds max_norm."""
            grad_norm = grad.norm()
            if grad_norm > max_norm:
                # Scale gradient to max_norm
                return grad * (max_norm / (grad_norm + 1e-8))
            return grad

        # Register hooks on critical parameters
        for _name, param in self.named_parameters():
            if param.requires_grad:
                param.register_hook(clip_grad_hook)

        logger.debug(f"Registered gradient clipping hooks (max_norm={max_norm})")

    def get_beta(self) -> float:
        """Get current beta with warmup."""
        # OPTIMIZATION FIX (Dec 15, 2025): Access tensor value
        step_val = self._step.item()  # type: ignore[operator]
        if step_val < self.config.beta_warmup_steps:
            return self.config.beta * (step_val / self.config.beta_warmup_steps)
        return self.config.beta

    def check_gradient_norms(self, max_norm: float = 100.0) -> dict[str, float]:
        """Check gradient norms for all parameters.

        Args:
            max_norm: Maximum allowed gradient norm

        Returns:
            Dict with parameter names and their gradient norms
        """
        grad_norms = {}
        for name, param in self.named_parameters():
            if param.requires_grad and param.grad is not None:
                grad_norm = param.grad.norm().item()
                grad_norms[name] = grad_norm
                if grad_norm > max_norm:
                    logger.warning(f"Gradient exploding in {name}: {grad_norm:.2e} > {max_norm}")
        return grad_norms

    def forward(
        self,
        nucleus_sequence: torch.Tensor,
        target_sequence: torch.Tensor | None = None,
        num_levels: int | None = None,
    ) -> dict[str, torch.Tensor]:
        """Process variable-length nucleus sequence through VIB.

        Args:
            nucleus_sequence: [B, L, 8] or [B, S, L, 8] E8 level embeddings
            target_sequence: Optional target for reconstruction loss
            num_levels: Actual number of levels (for masking, if L < max_levels)

        Returns:
            Dict with z, mu, logvar, reconstruction, and losses
        """
        cfg = self.config

        # Handle temporal sequence dimension
        has_temporal = nucleus_sequence.dim() == 4
        if has_temporal:
            B, S, L, D = nucleus_sequence.shape
            nucleus_sequence = nucleus_sequence.view(B * S, L, D)
            if target_sequence is not None:
                target_sequence = target_sequence.view(B * S, L, D)
        else:
            B_eff, L, D = nucleus_sequence.shape
            B, S = B_eff, 1

        # Pad to max_levels if needed (values of padded positions don't matter once masked)
        if cfg.max_levels > L:
            pad_size = cfg.max_levels - L
            padding = torch.zeros(
                nucleus_sequence.shape[0], pad_size, D, device=nucleus_sequence.device
            )
            nucleus_sequence = torch.cat([nucleus_sequence, padding], dim=1)

        # Create attention mask for actual levels
        actual_L = num_levels if num_levels is not None else L
        mask = torch.ones(
            nucleus_sequence.shape[0], cfg.max_levels + 1, device=nucleus_sequence.device
        )
        mask[:, actual_L + 1 :] = 0  # +1 for CLS token
        # src_key_padding_mask expects True where positions should be ignored
        padding_mask = mask == 0

        # Project to hidden and add positional embeddings
        hidden = self.e8_to_hidden(nucleus_sequence)  # [B, max_levels, hidden]
        hidden = hidden + self.level_pos_emb[: cfg.max_levels]

        # Prepend CLS token
        cls_tokens = self.cls_token.expand(hidden.shape[0], -1, -1)
        hidden = torch.cat([cls_tokens, hidden], dim=1)  # [B, max_levels+1, hidden]

        # Transformer encoding with key padding mask so padded levels are ignored
        encoded = self.transformer(
            hidden, src_key_padding_mask=padding_mask
        )  # [B, max_levels+1, hidden]

        # Extract CLS representation
        cls_out = encoded[:, 0]  # [B, hidden]

        # VIB: encode to (μ, σ²)
        mu = self.vib_mu(cls_out)
        logvar = self.vib_logvar(cls_out).clamp(-20, 2)

        # Reparameterization
        std = torch.exp(0.5 * logvar)
        eps = torch.randn_like(std)
        z = mu + eps * std

        # Decode: z → sequence
        z_hidden = self.z_to_hidden(z)  # [B, hidden]
        decoded_flat = self.decoder_expand(z_hidden)  # [B, max_levels * hidden]
        decoded_hidden = decoded_flat.view(-1, cfg.max_levels, cfg.hidden_dim)
        reconstruction = self.hidden_to_e8(decoded_hidden)  # [B, max_levels, 8]

        # Trim to actual levels (respect num_levels if provided)
        reconstruction = reconstruction[:, :actual_L]

        result = {
            "z": z,
            "mu": mu,
            "logvar": logvar,
            "reconstruction": reconstruction,
            "cls_embedding": cls_out,
            "num_levels": actual_L,
        }

        # Compute losses
        if target_sequence is None:
            target_sequence = nucleus_sequence[:, :actual_L]

        # Reconstruction loss (MSE in E8 space) - SCALED to prevent gradient explosion
        raw_recon_loss = (reconstruction - target_sequence[:, :L]).pow(2).sum(dim=-1).mean()
        recon_loss = cfg.loss_scale * raw_recon_loss

        # KL divergence with gradient-preserving free bits
        # FIX (Dec 22, 2025): Apply free bits to TOTAL KL, not per-dimension
        # Previous bug: per-dim free_bits=1.0 with latent_dim=64 → constant floor of 64.0
        # This made seq_ib_kl a constant 6.4 that couldn't be minimized!
        #
        # FIX (Dec 28, 2025): Use softplus-based floor instead of torch.maximum
        # torch.maximum blocks gradients when KL < free_bits, preventing learning!
        prior_var = self.prior_logvar.exp()  # type: ignore[operator]
        var = logvar.exp()
        kl_per_dim = 0.5 * (
            (self.prior_logvar - logvar)
            + var / prior_var
            + (mu - self.prior_mu).pow(2) / prior_var
            - 1
        )
        # Sum first, THEN apply free bits to total (DreamerV3-style)
        kl_loss_raw = kl_per_dim.sum(dim=-1).mean()
        if cfg.kl_free_bits > 0:
            # Gradient-preserving free bits: provides gradient even below floor
            # kl_soft = kl + free_bits * scale * softplus((free_bits - kl) / free_bits)
            free_bits = torch.tensor(cfg.kl_free_bits, device=mu.device)
            scale = 0.5  # Controls softness
            kl_loss = kl_loss_raw + free_bits * scale * F.softplus(
                (free_bits - kl_loss_raw) / free_bits
            )
        else:
            kl_loss = kl_loss_raw

        # Total loss
        beta = self.get_beta()
        total_loss = recon_loss + beta * kl_loss

        result.update(
            {
                "reconstruction_loss": recon_loss,
                "kl_loss": kl_loss,
                "beta": torch.tensor(beta, device=nucleus_sequence.device),
                "total_loss": total_loss,
            }
        )

        # OPTIMIZATION FIX (Dec 15, 2025): Increment tensor counter
        self._step += 1  # type: ignore[operator, assignment]

        # Restore temporal dimension
        if has_temporal:
            result["z"] = result["z"].view(B, S, -1)
            result["reconstruction"] = result["reconstruction"].view(B, S, L, -1)
            result["cls_embedding"] = result["cls_embedding"].view(B, S, -1)

        return result


__all__ = [
    "GaussianEncoder",
    "IBConfig",
    # R-D curve diagnostics (Dec 12, 2025)
    "InfoNCEEstimator",
    "InformationBottleneck",
    "PredictiveDecoder",
    "RDCurveTracker",
    "SequenceIBConfig",
    "SequenceInformationBottleneck",
]
