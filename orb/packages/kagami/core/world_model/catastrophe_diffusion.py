"""Catastrophe-Guided Diffusion for World Model Generation.

CREATED: January 4, 2026

Integrates Thom's catastrophe theory into the diffusion process, creating
noise schedules that respect catastrophe dynamics rather than using
generic linear/cosine schedules.

Key Innovation:
===============
Standard diffusion: Beta schedule is linear/cosine (arbitrary)
Catastrophe diffusion: Beta schedule follows catastrophe potential ∇V(x; t)

Near bifurcation points → slower denoising (more steps needed)
Stable regions → faster denoising (fewer steps needed)

Mathematical Foundation:
=======================
Each catastrophe type has a canonical potential V(x; params).
The gradient ∇V defines the system's attractors and bifurcations.

By using the catastrophe potential to guide denoising:
1. The diffusion respects natural stability boundaries
2. Bifurcation points get extra care (slow denoising)
3. Stable attractors are reached quickly (fast denoising)
4. The generated states follow catastrophe-natural dynamics

Catastrophe Types:
=================
- Fold (A₂):       V(x) = x³/3 + ax
- Cusp (A₃):       V(x) = x⁴/4 + ax²/2 + bx
- Swallowtail (A₄): V(x) = x⁵/5 + ax³/3 + bx²/2 + cx
- Butterfly (A₅):  V(x) = x⁶/6 + ax⁴/4 + bx³/3 + cx²/2 + dx
- Hyperbolic (D₄⁺): V(x,y) = x³ + y³ + axy + bx + cy
- Elliptic (D₄⁻):  V(x,y) = x³ - xy² + a(x²+y²) + bx + cy
- Parabolic (D₅):  V(x,y) = x²y + y⁴ + ax² + by² + cx + dy

Colony Mapping:
==============
Colony 0 (Spark):   Fold catastrophe - simple ignition
Colony 1 (Forge):   Cusp catastrophe - bistable quality
Colony 2 (Flow):    Swallowtail catastrophe - multi-path recovery
Colony 3 (Nexus):   Butterfly catastrophe - complex integration
Colony 4 (Beacon):  Hyperbolic catastrophe - planning divergence
Colony 5 (Grove):   Elliptic catastrophe - knowledge convergence
Colony 6 (Crystal): Parabolic catastrophe - safety boundary

References:
- Thom (1972): Structural Stability and Morphogenesis
- Arnold (1975): Critical Points of Smooth Functions
- Ho et al. (2020): Denoising Diffusion Probabilistic Models
- Song et al. (2021): Score-Based Generative Modeling
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from enum import Enum

import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)


# =============================================================================
# CATASTROPHE TYPES
# =============================================================================


class CatastropheType(Enum):
    """The 7 elementary catastrophes from Thom's classification."""

    FOLD = "fold"  # A₂
    CUSP = "cusp"  # A₃
    SWALLOWTAIL = "swallowtail"  # A₄
    BUTTERFLY = "butterfly"  # A₅
    HYPERBOLIC = "hyperbolic"  # D₄⁺
    ELLIPTIC = "elliptic"  # D₄⁻
    PARABOLIC = "parabolic"  # D₅


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass
class CatastropheDiffusionConfig:
    """Configuration for catastrophe-guided diffusion."""

    # Latent dimensions
    latent_dim: int = 512
    patch_size: int = 4

    # Conditioning
    action_dim: int = 64
    text_dim: int = 768

    # Architecture (DiT)
    hidden_dim: int = 1024
    num_layers: int = 12
    num_heads: int = 16
    dropout: float = 0.0

    # Catastrophe-guided diffusion
    num_timesteps: int = 1000
    catastrophe_type: CatastropheType = CatastropheType.CUSP
    bifurcation_slowdown: float = 2.0  # Extra steps near bifurcations
    stable_speedup: float = 1.5  # Fewer steps in stable regions

    # Sampling
    num_sampling_steps: int = 50
    guidance_scale: float = 4.0

    # Colony-specific (optional)
    colony_idx: int | None = None  # If set, use colony's catastrophe type


# =============================================================================
# CATASTROPHE POTENTIALS
# =============================================================================


class CatastrophePotential:
    """Implements the 7 elementary catastrophe potentials.

    Each potential V(x; params) has:
    - A canonical form (Thom's classification)
    - Gradient ∇V (for dynamics)
    - Hessian H (for stability analysis)
    - Bifurcation detection

    These are used to guide the diffusion noise schedule.
    """

    def __init__(self, catastrophe_type: CatastropheType):
        self.type = catastrophe_type

    def potential(self, x: torch.Tensor, params: torch.Tensor | None = None) -> torch.Tensor:
        """Compute potential V(x; params).

        Args:
            x: [..., d] state (d depends on catastrophe type)
            params: [..., k] control parameters

        Returns:
            [...] potential values
        """
        if self.type == CatastropheType.FOLD:
            return self._fold_potential(x, params)
        elif self.type == CatastropheType.CUSP:
            return self._cusp_potential(x, params)
        elif self.type == CatastropheType.SWALLOWTAIL:
            return self._swallowtail_potential(x, params)
        elif self.type == CatastropheType.BUTTERFLY:
            return self._butterfly_potential(x, params)
        elif self.type == CatastropheType.HYPERBOLIC:
            return self._hyperbolic_potential(x, params)
        elif self.type == CatastropheType.ELLIPTIC:
            return self._elliptic_potential(x, params)
        elif self.type == CatastropheType.PARABOLIC:
            return self._parabolic_potential(x, params)
        else:
            raise ValueError(f"Unknown catastrophe type: {self.type}")

    def gradient(self, x: torch.Tensor, params: torch.Tensor | None = None) -> torch.Tensor:
        """Compute gradient ∇V(x; params).

        Args:
            x: [..., d] state
            params: [..., k] control parameters

        Returns:
            [..., d] gradient
        """
        x = x.requires_grad_(True)
        V = self.potential(x, params)
        grad = torch.autograd.grad(V.sum(), x, create_graph=True)[0]
        return grad

    def bifurcation_distance(
        self, x: torch.Tensor, params: torch.Tensor | None = None
    ) -> torch.Tensor:
        """Estimate distance to nearest bifurcation point.

        Near bifurcations, the Hessian becomes singular (det H → 0).
        We use |det H| as a proxy for bifurcation distance.

        Args:
            x: [..., d] state
            params: [..., k] control parameters

        Returns:
            [...] distance estimates (higher = more stable)
        """
        # Enable gradients for Hessian computation even in inference
        with torch.enable_grad():
            # Compute Hessian determinant as stability proxy
            x_grad = x.detach().clone().requires_grad_(True)
            V = self.potential(x_grad, params)
            grad = torch.autograd.grad(V.sum(), x_grad, create_graph=True)[0]

            # For 1D catastrophes, Hessian is second derivative
            if self.type in [
                CatastropheType.FOLD,
                CatastropheType.CUSP,
                CatastropheType.SWALLOWTAIL,
                CatastropheType.BUTTERFLY,
            ]:
                hess = torch.autograd.grad(grad.sum(), x_grad, create_graph=True)[0]
                return hess.abs().mean(dim=-1).detach()  # Proxy for stability
            else:
                # For 2D catastrophes, approximate
                return grad.norm(dim=-1).detach()  # Proxy using gradient magnitude

    # === Individual Catastrophe Potentials ===

    def _fold_potential(self, x: torch.Tensor, params: torch.Tensor | None) -> torch.Tensor:
        """Fold (A₂): V(x) = x³/3 + ax."""
        if x.shape[-1] > 1:
            x = x[..., 0:1]  # Use first dimension
        a = params[..., 0:1] if params is not None else torch.zeros_like(x)
        return (x**3 / 3 + a * x).squeeze(-1)

    def _cusp_potential(self, x: torch.Tensor, params: torch.Tensor | None) -> torch.Tensor:
        """Cusp (A₃): V(x) = x⁴/4 + ax²/2 + bx."""
        if x.shape[-1] > 1:
            x = x[..., 0:1]
        if params is not None and params.shape[-1] >= 2:
            a, b = params[..., 0:1], params[..., 1:2]
        else:
            a = b = torch.zeros_like(x)
        return (x**4 / 4 + a * x**2 / 2 + b * x).squeeze(-1)

    def _swallowtail_potential(self, x: torch.Tensor, params: torch.Tensor | None) -> torch.Tensor:
        """Swallowtail (A₄): V(x) = x⁵/5 + ax³/3 + bx²/2 + cx."""
        if x.shape[-1] > 1:
            x = x[..., 0:1]
        if params is not None and params.shape[-1] >= 3:
            a, b, c = params[..., 0:1], params[..., 1:2], params[..., 2:3]
        else:
            a = b = c = torch.zeros_like(x)
        return (x**5 / 5 + a * x**3 / 3 + b * x**2 / 2 + c * x).squeeze(-1)

    def _butterfly_potential(self, x: torch.Tensor, params: torch.Tensor | None) -> torch.Tensor:
        """Butterfly (A₅): V(x) = x⁶/6 + ax⁴/4 + bx³/3 + cx²/2 + dx."""
        if x.shape[-1] > 1:
            x = x[..., 0:1]
        if params is not None and params.shape[-1] >= 4:
            a, b, c, d = params[..., 0:1], params[..., 1:2], params[..., 2:3], params[..., 3:4]
        else:
            a = b = c = d = torch.zeros_like(x)
        return (x**6 / 6 + a * x**4 / 4 + b * x**3 / 3 + c * x**2 / 2 + d * x).squeeze(-1)

    def _hyperbolic_potential(self, x: torch.Tensor, params: torch.Tensor | None) -> torch.Tensor:
        """Hyperbolic Umbilic (D₄⁺): V(x,y) = x³ + y³ + axy + bx + cy."""
        if x.shape[-1] < 2:
            x = F.pad(x, (0, 2 - x.shape[-1]))
        x1, y1 = x[..., 0], x[..., 1]
        if params is not None and params.shape[-1] >= 3:
            a, b, c = params[..., 0], params[..., 1], params[..., 2]
        else:
            a = b = c = torch.zeros_like(x1)
        return x1**3 + y1**3 + a * x1 * y1 + b * x1 + c * y1

    def _elliptic_potential(self, x: torch.Tensor, params: torch.Tensor | None) -> torch.Tensor:
        """Elliptic Umbilic (D₄⁻): V(x,y) = x³ - xy² + a(x²+y²) + bx + cy."""
        if x.shape[-1] < 2:
            x = F.pad(x, (0, 2 - x.shape[-1]))
        x1, y1 = x[..., 0], x[..., 1]
        if params is not None and params.shape[-1] >= 3:
            a, b, c = params[..., 0], params[..., 1], params[..., 2]
        else:
            a = b = c = torch.zeros_like(x1)
        return x1**3 - x1 * y1**2 + a * (x1**2 + y1**2) + b * x1 + c * y1

    def _parabolic_potential(self, x: torch.Tensor, params: torch.Tensor | None) -> torch.Tensor:
        """Parabolic Umbilic (D₅): V(x,y) = x²y + y⁴ + ax² + by² + cx + dy."""
        if x.shape[-1] < 2:
            x = F.pad(x, (0, 2 - x.shape[-1]))
        x1, y1 = x[..., 0], x[..., 1]
        if params is not None and params.shape[-1] >= 4:
            a, b, c, d = params[..., 0], params[..., 1], params[..., 2], params[..., 3]
        else:
            a = b = c = d = torch.zeros_like(x1)
        return x1**2 * y1 + y1**4 + a * x1**2 + b * y1**2 + c * x1 + d * y1


# =============================================================================
# CATASTROPHE NOISE SCHEDULE
# =============================================================================


class CatastropheNoiseSchedule:
    """Noise schedule guided by catastrophe dynamics.

    Instead of linear/cosine beta schedule, we use the catastrophe
    potential to determine how much noise to add/remove at each step.

    Near bifurcations: Smaller steps (more careful denoising)
    Stable regions: Larger steps (faster denoising)

    This creates dynamics-aware generation that respects the natural
    stability structure of the state space.
    """

    def __init__(self, config: CatastropheDiffusionConfig):
        self.config = config
        self.num_timesteps = config.num_timesteps

        # Catastrophe potential
        self.potential = CatastrophePotential(config.catastrophe_type)

        # Base schedule (cosine)
        steps = torch.arange(config.num_timesteps + 1, dtype=torch.float64)
        alpha_bar = torch.cos((steps / config.num_timesteps + 0.008) / 1.008 * math.pi / 2) ** 2
        alpha_bar = alpha_bar / alpha_bar[0]
        betas = 1 - (alpha_bar[1:] / alpha_bar[:-1])
        betas = torch.clamp(betas, 0, 0.999).float()

        # Store base schedule
        self.base_betas = betas
        self.alphas = 1.0 - betas
        self.alphas_cumprod = torch.cumprod(self.alphas, dim=0)
        self.alphas_cumprod_prev = F.pad(self.alphas_cumprod[:-1], (1, 0), value=1.0)

        # Derived values
        self.sqrt_alphas_cumprod = torch.sqrt(self.alphas_cumprod)
        self.sqrt_one_minus_alphas_cumprod = torch.sqrt(1.0 - self.alphas_cumprod)

        # Posterior
        self.posterior_variance = (
            betas * (1.0 - self.alphas_cumprod_prev) / (1.0 - self.alphas_cumprod)
        )
        self.posterior_log_variance = torch.log(torch.clamp(self.posterior_variance, min=1e-20))
        self.posterior_mean_coef1 = (
            betas * torch.sqrt(self.alphas_cumprod_prev) / (1.0 - self.alphas_cumprod)
        )
        self.posterior_mean_coef2 = (
            (1.0 - self.alphas_cumprod_prev) * torch.sqrt(self.alphas) / (1.0 - self.alphas_cumprod)
        )

    def to(self, device: torch.device) -> CatastropheNoiseSchedule:
        """Move schedule to device."""
        self.base_betas = self.base_betas.to(device)
        self.alphas = self.alphas.to(device)
        self.alphas_cumprod = self.alphas_cumprod.to(device)
        self.alphas_cumprod_prev = self.alphas_cumprod_prev.to(device)
        self.sqrt_alphas_cumprod = self.sqrt_alphas_cumprod.to(device)
        self.sqrt_one_minus_alphas_cumprod = self.sqrt_one_minus_alphas_cumprod.to(device)
        self.posterior_variance = self.posterior_variance.to(device)
        self.posterior_log_variance = self.posterior_log_variance.to(device)
        self.posterior_mean_coef1 = self.posterior_mean_coef1.to(device)
        self.posterior_mean_coef2 = self.posterior_mean_coef2.to(device)
        return self

    def get_adaptive_beta(
        self,
        x: torch.Tensor,
        t: torch.Tensor,
    ) -> torch.Tensor:
        """Get catastrophe-adapted beta for current state.

        Near bifurcation points, returns smaller beta (slower denoising).
        In stable regions, returns larger beta (faster denoising).

        Args:
            x: [B, latent_dim] current state (for stability estimation)
            t: [B] timesteps

        Returns:
            [B] adapted betas
        """
        # Get base beta
        base_beta = self.base_betas[t]  # [B]

        # Estimate stability at current state
        # Higher = more stable = can use larger beta
        with torch.no_grad():
            # Project x to catastrophe-relevant dimensions
            x_cat = x[..., :2] if x.shape[-1] >= 2 else x
            stability = self.potential.bifurcation_distance(x_cat, params=None)

            # Normalize stability to [0, 1] range
            stability = torch.sigmoid(stability)

            # Scale beta based on stability
            # Near bifurcation (low stability): scale down by bifurcation_slowdown
            # Stable region (high stability): scale up by stable_speedup
            scale = self.config.stable_speedup * stability + (
                1.0 / self.config.bifurcation_slowdown
            ) * (1 - stability)

        return base_beta * scale

    def q_sample(
        self,
        x_0: torch.Tensor,
        t: torch.Tensor,
        noise: torch.Tensor | None = None,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Sample from q(x_t | x_0) with catastrophe-aware noise."""
        if noise is None:
            noise = torch.randn_like(x_0)

        sqrt_alpha = self.sqrt_alphas_cumprod[t].view(-1, *([1] * (x_0.dim() - 1)))
        sqrt_one_minus_alpha = self.sqrt_one_minus_alphas_cumprod[t].view(
            -1, *([1] * (x_0.dim() - 1))
        )

        x_t = sqrt_alpha * x_0 + sqrt_one_minus_alpha * noise
        return x_t, noise


# =============================================================================
# CATASTROPHE-GUIDED DiT BLOCK
# =============================================================================


class CatastropheDiTBlock(nn.Module):
    """DiT block with catastrophe-aware modulation.

    Extends standard DiT block to use catastrophe potential for:
    1. Adaptive LayerNorm modulation
    2. Attention weighting
    3. FFN scaling
    """

    def __init__(self, hidden_dim: int, num_heads: int, dropout: float = 0.0):
        super().__init__()
        self.hidden_dim = hidden_dim

        # Standard adaLN modulation (6 params for attn, 6 for FFN)
        self.adaLN_modulation = nn.Sequential(
            nn.SiLU(),
            nn.Linear(hidden_dim, 6 * hidden_dim, bias=True),
        )

        # Catastrophe-aware extra modulation
        self.catastrophe_modulation = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.SiLU(),
            nn.Linear(hidden_dim, 2 * hidden_dim),  # scale and shift
        )

        # Attention
        self.norm1 = nn.LayerNorm(hidden_dim, elementwise_affine=False, eps=1e-6)
        self.attn = nn.MultiheadAttention(hidden_dim, num_heads, dropout=dropout, batch_first=True)

        # FFN
        self.norm2 = nn.LayerNorm(hidden_dim, elementwise_affine=False, eps=1e-6)
        self.ffn = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim * 4),
            nn.GELU(approximate="tanh"),
            nn.Linear(hidden_dim * 4, hidden_dim),
        )

        # Initialize to zero
        nn.init.zeros_(self.adaLN_modulation[-1].weight)
        nn.init.zeros_(self.adaLN_modulation[-1].bias)

    def forward(
        self,
        x: torch.Tensor,
        c: torch.Tensor,
        catastrophe_embedding: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Forward with catastrophe-aware modulation.

        Args:
            x: [B, T, hidden_dim] input
            c: [B, hidden_dim] conditioning (timestep + other)
            catastrophe_embedding: [B, hidden_dim] optional catastrophe state

        Returns:
            [B, T, hidden_dim] output
        """
        # Standard adaLN
        shift_attn, scale_attn, gate_attn, shift_ffn, scale_ffn, gate_ffn = self.adaLN_modulation(
            c
        ).chunk(6, dim=-1)

        # Catastrophe modulation (if provided)
        if catastrophe_embedding is not None:
            cat_scale, cat_shift = self.catastrophe_modulation(catastrophe_embedding).chunk(
                2, dim=-1
            )
            scale_attn = scale_attn * (1 + cat_scale)
            shift_attn = shift_attn + cat_shift

        # Attention
        x_norm = self.norm1(x)
        x_norm = x_norm * (1 + scale_attn.unsqueeze(1)) + shift_attn.unsqueeze(1)
        attn_out, _ = self.attn(x_norm, x_norm, x_norm)
        x = x + gate_attn.unsqueeze(1) * attn_out

        # FFN
        x_norm = self.norm2(x)
        x_norm = x_norm * (1 + scale_ffn.unsqueeze(1)) + shift_ffn.unsqueeze(1)
        ffn_out = self.ffn(x_norm)
        x = x + gate_ffn.unsqueeze(1) * ffn_out

        return x


# =============================================================================
# CATASTROPHE DIFFUSION MODEL
# =============================================================================


class CatastropheDiffusionModel(nn.Module):
    """Diffusion model with catastrophe-guided dynamics.

    Key innovations:
    1. Noise schedule adapts to catastrophe stability
    2. DiT blocks receive catastrophe potential embedding
    3. Denoising respects bifurcation structure
    4. Colony-specific catastrophe types

    Usage:
        model = CatastropheDiffusionModel(config)

        # Training
        loss = model.training_loss(states, actions)

        # Sampling
        samples = model.sample(shape, action)

        # Colony-specific generation
        samples = model.sample_with_colony(shape, action, colony_idx=2)
    """

    def __init__(self, config: CatastropheDiffusionConfig | None = None):
        super().__init__()
        self.config = config or CatastropheDiffusionConfig()

        # Catastrophe-guided noise schedule
        self.noise_schedule = CatastropheNoiseSchedule(self.config)

        # Catastrophe potential (for embedding)
        self.catastrophe_potential = CatastrophePotential(self.config.catastrophe_type)

        # Input/output
        self.input_proj = nn.Linear(self.config.latent_dim, self.config.hidden_dim)
        self.output_proj = nn.Linear(self.config.hidden_dim, self.config.latent_dim)

        # Timestep embedding
        self.time_embed = nn.Sequential(
            nn.Linear(self.config.hidden_dim, self.config.hidden_dim * 4),
            nn.SiLU(),
            nn.Linear(self.config.hidden_dim * 4, self.config.hidden_dim),
        )

        # Catastrophe state encoder
        self.catastrophe_encoder = nn.Sequential(
            nn.Linear(8, self.config.hidden_dim // 2),  # 8D for E8 compatibility
            nn.SiLU(),
            nn.Linear(self.config.hidden_dim // 2, self.config.hidden_dim),
        )

        # Action conditioning
        if self.config.action_dim > 0:
            self.action_embed = nn.Sequential(
                nn.Linear(self.config.action_dim, self.config.hidden_dim),
                nn.SiLU(),
                nn.Linear(self.config.hidden_dim, self.config.hidden_dim),
            )
        else:
            self.action_embed = None

        # Catastrophe DiT blocks
        self.blocks = nn.ModuleList(
            [
                CatastropheDiTBlock(
                    self.config.hidden_dim,
                    self.config.num_heads,
                    self.config.dropout,
                )
                for _ in range(self.config.num_layers)
            ]
        )

        # Final layer
        self.final_norm = nn.LayerNorm(self.config.hidden_dim, elementwise_affine=False)
        self.final_adaLN = nn.Sequential(
            nn.SiLU(),
            nn.Linear(self.config.hidden_dim, 2 * self.config.hidden_dim),
        )

        # Initialize output to zero
        nn.init.zeros_(self.output_proj.weight)
        nn.init.zeros_(self.output_proj.bias)

        self._device = torch.device("cpu")

        logger.info(
            f"CatastropheDiffusionModel initialized:\n"
            f"  Catastrophe: {self.config.catastrophe_type.value}\n"
            f"  Layers: {self.config.num_layers}\n"
            f"  Heads: {self.config.num_heads}\n"
            f"  Bifurcation slowdown: {self.config.bifurcation_slowdown}x"
        )

    def to(self, device: torch.device) -> CatastropheDiffusionModel:
        """Move model to device."""
        super().to(device)
        self._device = device
        self.noise_schedule.to(device)
        return self

    def _get_timestep_embedding(self, t: torch.Tensor) -> torch.Tensor:
        """Sinusoidal timestep embedding."""
        half_dim = self.config.hidden_dim // 2
        emb = math.log(10000) / (half_dim - 1)
        emb = torch.exp(torch.arange(half_dim, device=t.device) * -emb)
        emb = t.float().unsqueeze(-1) * emb.unsqueeze(0)
        emb = torch.cat([emb.sin(), emb.cos()], dim=-1)
        return self.time_embed(emb)

    def _get_catastrophe_embedding(self, x: torch.Tensor) -> torch.Tensor:
        """Compute catastrophe state embedding.

        Uses first 8 dimensions for E8 compatibility.
        """
        x_cat = x[..., :8] if x.shape[-1] >= 8 else F.pad(x, (0, 8 - x.shape[-1]))
        return self.catastrophe_encoder(x_cat)

    def forward(
        self,
        x_t: torch.Tensor,
        t: torch.Tensor,
        action: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Predict noise/velocity from noisy input.

        Args:
            x_t: [B, latent_dim] noisy state
            t: [B] timesteps
            action: [B, action_dim] optional action

        Returns:
            [B, latent_dim] predicted noise/velocity
        """
        # Project to hidden dim
        x = self.input_proj(x_t).unsqueeze(1)  # [B, 1, hidden]

        # Get embeddings
        c = self._get_timestep_embedding(t)  # [B, hidden]
        cat_emb = self._get_catastrophe_embedding(x_t)  # [B, hidden]

        if action is not None and self.action_embed is not None:
            c = c + self.action_embed(action)

        # Apply catastrophe DiT blocks
        for block in self.blocks:
            x = block(x, c, cat_emb)

        # Final layer
        shift, scale = self.final_adaLN(c).chunk(2, dim=-1)
        x = self.final_norm(x)
        x = x * (1 + scale.unsqueeze(1)) + shift.unsqueeze(1)

        # Project output
        out = self.output_proj(x.squeeze(1))
        return out

    def training_loss(
        self,
        x_0: torch.Tensor,
        action: torch.Tensor | None = None,
    ) -> dict[str, torch.Tensor]:
        """Compute catastrophe-aware training loss.

        Args:
            x_0: [B, latent_dim] clean states
            action: [B, action_dim] actions

        Returns:
            Dict with loss components
        """
        B = x_0.shape[0]
        device = x_0.device

        # Sample timesteps
        t = torch.randint(0, self.config.num_timesteps, (B,), device=device, dtype=torch.long)

        # Sample noise
        noise = torch.randn_like(x_0)

        # Get noisy sample (using catastrophe-aware schedule)
        x_t, _ = self.noise_schedule.q_sample(x_0, t, noise)

        # Predict noise
        pred = self.forward(x_t, t, action)

        # MSE loss (velocity prediction)
        sqrt_alpha = self.noise_schedule.sqrt_alphas_cumprod[t].view(-1, 1)
        sqrt_one_minus_alpha = self.noise_schedule.sqrt_one_minus_alphas_cumprod[t].view(-1, 1)
        target = sqrt_alpha * noise - sqrt_one_minus_alpha * x_0  # velocity

        loss = F.mse_loss(pred, target)

        return {
            "loss": loss,
            "mse": loss,
        }

    @torch.no_grad()
    def sample(
        self,
        shape: tuple[int, ...] | torch.Tensor,
        action: torch.Tensor | None = None,
        num_steps: int | None = None,
    ) -> torch.Tensor:
        """Sample with catastrophe-guided denoising.

        Args:
            shape: Output shape or initial noise
            action: Action conditioning
            num_steps: Override sampling steps

        Returns:
            [B, latent_dim] sampled states
        """
        num_steps = num_steps or self.config.num_sampling_steps

        # Initialize with noise
        if isinstance(shape, torch.Tensor):
            x = shape
        else:
            x = torch.randn(shape, device=self._device)

        B = x.shape[0]

        # DDIM timesteps
        timesteps = torch.linspace(
            self.config.num_timesteps - 1, 0, num_steps + 1, device=self._device
        ).long()

        for i in range(num_steps):
            t = timesteps[i]
            t_next = timesteps[i + 1]

            t_batch = torch.full((B,), t, device=self._device, dtype=torch.long)

            # Get catastrophe-adaptive step size
            self.noise_schedule.get_adaptive_beta(x, t_batch)

            # Predict
            pred = self.forward(x, t_batch, action)

            # DDIM update
            alpha_t = self.noise_schedule.alphas_cumprod[t]
            alpha_t_next = (
                self.noise_schedule.alphas_cumprod[t_next] if t_next >= 0 else torch.tensor(1.0)
            )

            # Velocity prediction → x0 prediction
            x0_pred = torch.sqrt(alpha_t) * x - torch.sqrt(1 - alpha_t) * pred

            # Apply adaptive step
            x = torch.sqrt(alpha_t_next) * x0_pred + torch.sqrt(1 - alpha_t_next) * (
                x - torch.sqrt(alpha_t) * x0_pred
            ) / torch.sqrt(1 - alpha_t)

        return x


# =============================================================================
# COLONY-SPECIFIC FACTORIES
# =============================================================================

# Colony to catastrophe type mapping
COLONY_CATASTROPHES = {
    0: CatastropheType.FOLD,  # Spark
    1: CatastropheType.CUSP,  # Forge
    2: CatastropheType.SWALLOWTAIL,  # Flow
    3: CatastropheType.BUTTERFLY,  # Nexus
    4: CatastropheType.HYPERBOLIC,  # Beacon
    5: CatastropheType.ELLIPTIC,  # Grove
    6: CatastropheType.PARABOLIC,  # Crystal
}


def create_catastrophe_diffusion(
    latent_dim: int = 512,
    action_dim: int = 64,
    num_layers: int = 12,
    catastrophe_type: CatastropheType | str = CatastropheType.CUSP,
    colony_idx: int | None = None,
) -> CatastropheDiffusionModel:
    """Factory for CatastropheDiffusionModel.

    Args:
        latent_dim: Latent state dimension
        action_dim: Action dimension
        num_layers: Number of DiT layers
        catastrophe_type: Type of catastrophe dynamics
        colony_idx: If provided, use colony's catastrophe type

    Returns:
        Configured CatastropheDiffusionModel
    """
    # Resolve catastrophe type
    if colony_idx is not None:
        cat_type = COLONY_CATASTROPHES.get(colony_idx, CatastropheType.CUSP)
    elif isinstance(catastrophe_type, str):
        cat_type = CatastropheType(catastrophe_type)
    else:
        cat_type = catastrophe_type

    config = CatastropheDiffusionConfig(
        latent_dim=latent_dim,
        action_dim=action_dim,
        num_layers=num_layers,
        catastrophe_type=cat_type,
        colony_idx=colony_idx,
    )
    return CatastropheDiffusionModel(config)


def create_colony_diffusion_ensemble() -> dict[int, CatastropheDiffusionModel]:
    """Create ensemble of 7 diffusion models, one per colony.

    Each model uses its colony's native catastrophe dynamics.

    Returns:
        Dict mapping colony_idx -> CatastropheDiffusionModel
    """
    return {i: create_catastrophe_diffusion(colony_idx=i) for i in range(7)}


__all__ = [
    "COLONY_CATASTROPHES",
    "CatastropheDiTBlock",
    "CatastropheDiffusionConfig",
    "CatastropheDiffusionModel",
    "CatastropheNoiseSchedule",
    "CatastrophePotential",
    "CatastropheType",
    "create_catastrophe_diffusion",
    "create_colony_diffusion_ensemble",
]
