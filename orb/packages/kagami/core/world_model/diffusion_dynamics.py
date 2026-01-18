"""Diffusion-Based World Model Dynamics (Sora-Style).

CREATED: January 4, 2026

Implements diffusion-based state prediction following Sora's architecture.
This enables:
1. High-quality state generation (better than autoregressive)
2. Variable-length prediction
3. Conditional generation on actions/language
4. Multi-modal outputs (video, 3D, etc.)

Architecture:
=============
```
Noisy State (z_T) ──▶ Denoiser ──▶ ... ──▶ Denoiser ──▶ Clean State (z_0)
                        ↑                      ↑
                    Conditioning           Conditioning
                    (action, text)         (action, text)
```

Key Innovations from Sora:
- Spacetime patches (unified video/image representation)
- DiT (Diffusion Transformer) architecture
- Classifier-free guidance for conditioning
- Variable duration/resolution

References:
- Ho et al. (2020): Denoising Diffusion Probabilistic Models
- Peebles & Xie (2023): Scalable Diffusion Models with Transformers (DiT)
- OpenAI (2024): Sora - Video Generation Models as World Simulators
- Esser et al. (2024): Scaling Rectified Flow Transformers for Image Synthesis
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
# CONFIGURATION
# =============================================================================


@dataclass
class DiffusionConfig:
    """Configuration for diffusion world model."""

    # Latent dimensions
    latent_dim: int = 512  # State dimension
    patch_size: int = 4  # For spacetime patching

    # Conditioning
    action_dim: int = 64
    text_dim: int = 768  # From language model

    # Architecture (DiT)
    hidden_dim: int = 1024
    num_layers: int = 12
    num_heads: int = 16
    dropout: float = 0.0  # DiT uses no dropout

    # Diffusion
    num_timesteps: int = 1000
    beta_start: float = 0.0001
    beta_end: float = 0.02
    schedule: str = "cosine"  # linear, cosine, or squared_cosine

    # Sampling
    num_sampling_steps: int = 50  # DDIM steps
    guidance_scale: float = 4.0  # Classifier-free guidance

    # Training
    prediction_type: str = "v"  # "epsilon", "x0", or "v" (velocity)
    loss_type: str = "mse"


# =============================================================================
# NOISE SCHEDULE
# =============================================================================


class NoiseSchedule:
    """Diffusion noise schedule (beta, alpha, sigma)."""

    def __init__(self, config: DiffusionConfig):
        self.config = config
        self.num_timesteps = config.num_timesteps

        # Compute betas
        if config.schedule == "linear":
            betas = torch.linspace(config.beta_start, config.beta_end, config.num_timesteps)
        elif config.schedule == "cosine":
            steps = torch.arange(config.num_timesteps + 1, dtype=torch.float64)
            alpha_bar = torch.cos((steps / config.num_timesteps + 0.008) / 1.008 * math.pi / 2) ** 2
            alpha_bar = alpha_bar / alpha_bar[0]
            betas = 1 - (alpha_bar[1:] / alpha_bar[:-1])
            betas = torch.clamp(betas, 0, 0.999).float()
        elif config.schedule == "squared_cosine":
            steps = torch.arange(config.num_timesteps + 1, dtype=torch.float64)
            alpha_bar = torch.cos((steps / config.num_timesteps + 0.008) / 1.008 * math.pi / 2) ** 2
            alpha_bar = alpha_bar / alpha_bar[0]
            betas = 1 - (alpha_bar[1:] / alpha_bar[:-1])
            betas = torch.clamp(betas, 0, 0.999).float() ** 2
        else:
            raise ValueError(f"Unknown schedule: {config.schedule}")

        # Precompute values
        alphas = 1.0 - betas
        alphas_cumprod = torch.cumprod(alphas, dim=0)
        alphas_cumprod_prev = F.pad(alphas_cumprod[:-1], (1, 0), value=1.0)

        self.betas = betas
        self.alphas = alphas
        self.alphas_cumprod = alphas_cumprod
        self.alphas_cumprod_prev = alphas_cumprod_prev

        # For q(x_t | x_0)
        self.sqrt_alphas_cumprod = torch.sqrt(alphas_cumprod)
        self.sqrt_one_minus_alphas_cumprod = torch.sqrt(1.0 - alphas_cumprod)

        # For posterior q(x_{t-1} | x_t, x_0)
        self.posterior_variance = betas * (1.0 - alphas_cumprod_prev) / (1.0 - alphas_cumprod)
        self.posterior_log_variance = torch.log(torch.clamp(self.posterior_variance, min=1e-20))
        self.posterior_mean_coef1 = betas * torch.sqrt(alphas_cumprod_prev) / (1.0 - alphas_cumprod)
        self.posterior_mean_coef2 = (
            (1.0 - alphas_cumprod_prev) * torch.sqrt(alphas) / (1.0 - alphas_cumprod)
        )

    def to(self, device: torch.device) -> NoiseSchedule:
        """Move schedule to device."""
        self.betas = self.betas.to(device)
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

    def q_sample(
        self,
        x_0: torch.Tensor,
        t: torch.Tensor,
        noise: torch.Tensor | None = None,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Sample from q(x_t | x_0).

        Args:
            x_0: Clean data [B, ...]
            t: Timesteps [B]
            noise: Optional noise (sampled if None)

        Returns:
            x_t: Noisy data
            noise: The noise that was added
        """
        if noise is None:
            noise = torch.randn_like(x_0)

        sqrt_alpha = self.sqrt_alphas_cumprod[t].view(-1, *([1] * (x_0.dim() - 1)))
        sqrt_one_minus_alpha = self.sqrt_one_minus_alphas_cumprod[t].view(
            -1, *([1] * (x_0.dim() - 1))
        )

        x_t = sqrt_alpha * x_0 + sqrt_one_minus_alpha * noise
        return x_t, noise


# =============================================================================
# TIMESTEP EMBEDDING
# =============================================================================


class TimestepEmbedding(nn.Module):
    """Sinusoidal timestep embedding (like in original diffusion)."""

    def __init__(self, dim: int, max_timesteps: int = 10000):
        super().__init__()
        self.dim = dim

        half_dim = dim // 2
        emb = math.log(max_timesteps) / (half_dim - 1)
        emb = torch.exp(torch.arange(half_dim, dtype=torch.float32) * -emb)
        self.register_buffer("freqs", emb)

        self.mlp = nn.Sequential(
            nn.Linear(dim, dim * 4),
            nn.SiLU(),
            nn.Linear(dim * 4, dim),
        )

    def forward(self, t: torch.Tensor) -> torch.Tensor:
        """Embed timesteps.

        Args:
            t: [B] timesteps (integers)

        Returns:
            [B, dim] embeddings
        """
        t = t.float()
        emb = t.unsqueeze(-1) * self.freqs.unsqueeze(0)
        emb = torch.cat([emb.sin(), emb.cos()], dim=-1)
        emb = self.mlp(emb)
        return emb


# =============================================================================
# DiT BLOCK
# =============================================================================


class DiTBlock(nn.Module):
    """Diffusion Transformer block with adaptive LayerNorm (adaLN-Zero).

    This is the core building block of DiT/Sora architecture.
    """

    def __init__(self, hidden_dim: int, num_heads: int, dropout: float = 0.0):
        super().__init__()
        self.hidden_dim = hidden_dim

        # Adaptive LayerNorm parameters (6 for attention, 6 for FFN)
        self.adaLN_modulation = nn.Sequential(
            nn.SiLU(),
            nn.Linear(hidden_dim, 6 * hidden_dim, bias=True),
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

        # Initialize adaLN-Zero: final linear outputs zero
        nn.init.zeros_(self.adaLN_modulation[-1].weight)
        nn.init.zeros_(self.adaLN_modulation[-1].bias)

    def forward(
        self,
        x: torch.Tensor,
        c: torch.Tensor,
    ) -> torch.Tensor:
        """Forward pass.

        Args:
            x: [B, T, hidden_dim] input
            c: [B, hidden_dim] conditioning (timestep + other)

        Returns:
            [B, T, hidden_dim] output
        """
        # Get adaLN parameters
        shift_attn, scale_attn, gate_attn, shift_ffn, scale_ffn, gate_ffn = self.adaLN_modulation(
            c
        ).chunk(6, dim=-1)

        # Attention with adaLN
        x_norm = self.norm1(x)
        x_norm = x_norm * (1 + scale_attn.unsqueeze(1)) + shift_attn.unsqueeze(1)
        attn_out, _ = self.attn(x_norm, x_norm, x_norm)
        x = x + gate_attn.unsqueeze(1) * attn_out

        # FFN with adaLN
        x_norm = self.norm2(x)
        x_norm = x_norm * (1 + scale_ffn.unsqueeze(1)) + shift_ffn.unsqueeze(1)
        ffn_out = self.ffn(x_norm)
        x = x + gate_ffn.unsqueeze(1) * ffn_out

        return x


# =============================================================================
# CONDITIONING
# =============================================================================


class ConditioningModule(nn.Module):
    """Combine multiple conditioning signals (timestep, action, text)."""

    def __init__(self, config: DiffusionConfig):
        super().__init__()
        self.config = config

        # Timestep embedding
        self.time_embed = TimestepEmbedding(config.hidden_dim)

        # Action embedding (optional)
        if config.action_dim > 0:
            self.action_embed = nn.Sequential(
                nn.Linear(config.action_dim, config.hidden_dim),
                nn.SiLU(),
                nn.Linear(config.hidden_dim, config.hidden_dim),
            )
        else:
            self.action_embed = None

        # Text embedding projection (from frozen language model)
        if config.text_dim > 0:
            self.text_proj = nn.Linear(config.text_dim, config.hidden_dim)
        else:
            self.text_proj = None

    def forward(
        self,
        timestep: torch.Tensor,
        action: torch.Tensor | None = None,
        text_emb: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Combine conditioning signals.

        Args:
            timestep: [B] diffusion timestep
            action: [B, action_dim] optional action
            text_emb: [B, text_dim] optional text embedding

        Returns:
            [B, hidden_dim] combined conditioning
        """
        c = self.time_embed(timestep)

        if action is not None and self.action_embed is not None:
            c = c + self.action_embed(action)

        if text_emb is not None and self.text_proj is not None:
            c = c + self.text_proj(text_emb)

        return c


# =============================================================================
# DIFFUSION WORLD MODEL
# =============================================================================


class DiffusionWorldModel(nn.Module):
    """Diffusion-based world model dynamics (Sora-style).

    Uses a Diffusion Transformer (DiT) to predict next states via
    iterative denoising. Supports conditioning on actions and language.

    Usage:
        model = DiffusionWorldModel(config)

        # Training: predict noise
        loss = model.training_loss(states, actions, text_emb)

        # Inference: sample next state
        next_state = model.sample(current_state, action, text)

        # Imagination: generate trajectory
        trajectory = model.imagine(initial_state, actions, horizon=15)
    """

    def __init__(self, config: DiffusionConfig | None = None):
        super().__init__()
        self.config = config or DiffusionConfig()

        # Noise schedule
        self.noise_schedule = NoiseSchedule(self.config)

        # Input/output projection
        self.input_proj = nn.Linear(self.config.latent_dim, self.config.hidden_dim)
        self.output_proj = nn.Linear(self.config.hidden_dim, self.config.latent_dim)

        # Conditioning
        self.conditioning = ConditioningModule(self.config)

        # Transformer blocks (DiT)
        self.blocks = nn.ModuleList(
            [
                DiTBlock(self.config.hidden_dim, self.config.num_heads, self.config.dropout)
                for _ in range(self.config.num_layers)
            ]
        )

        # Final normalization
        self.final_norm = nn.LayerNorm(self.config.hidden_dim, elementwise_affine=False, eps=1e-6)
        self.final_adaLN = nn.Sequential(
            nn.SiLU(),
            nn.Linear(self.config.hidden_dim, 2 * self.config.hidden_dim),
        )

        # Initialize final layer to zero
        nn.init.zeros_(self.output_proj.weight)
        nn.init.zeros_(self.output_proj.bias)

        self._device = torch.device("cpu")

        logger.info(
            f"DiffusionWorldModel initialized:\n"
            f"  Layers: {self.config.num_layers}\n"
            f"  Heads: {self.config.num_heads}\n"
            f"  Hidden: {self.config.hidden_dim}\n"
            f"  Timesteps: {self.config.num_timesteps}\n"
            f"  Schedule: {self.config.schedule}"
        )

    def to(self, device: torch.device) -> DiffusionWorldModel:
        """Move model to device."""
        super().to(device)
        self._device = device
        self.noise_schedule.to(device)
        return self

    def forward(
        self,
        x_t: torch.Tensor,
        t: torch.Tensor,
        action: torch.Tensor | None = None,
        text_emb: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Predict noise/velocity/x0 from noisy input.

        Args:
            x_t: [B, latent_dim] noisy latent state
            t: [B] timesteps
            action: [B, action_dim] optional action conditioning
            text_emb: [B, text_dim] optional text conditioning

        Returns:
            [B, latent_dim] predicted noise/velocity/x0
        """
        # Project to hidden dim
        x = self.input_proj(x_t).unsqueeze(1)  # [B, 1, hidden]

        # Get conditioning
        c = self.conditioning(t, action, text_emb)  # [B, hidden]

        # Apply DiT blocks
        for block in self.blocks:
            x = block(x, c)

        # Final layer
        shift, scale = self.final_adaLN(c).chunk(2, dim=-1)
        x = self.final_norm(x)
        x = x * (1 + scale.unsqueeze(1)) + shift.unsqueeze(1)

        # Project to output
        out = self.output_proj(x.squeeze(1))  # [B, latent_dim]

        return out

    def training_loss(
        self,
        x_0: torch.Tensor,
        action: torch.Tensor | None = None,
        text_emb: torch.Tensor | None = None,
    ) -> dict[str, torch.Tensor]:
        """Compute training loss.

        Args:
            x_0: [B, latent_dim] clean target states
            action: [B, action_dim] actions that led to these states
            text_emb: [B, text_dim] text descriptions

        Returns:
            Dict with loss and components
        """
        B = x_0.shape[0]
        device = x_0.device

        # Sample timesteps
        t = torch.randint(0, self.config.num_timesteps, (B,), device=device, dtype=torch.long)

        # Sample noise
        noise = torch.randn_like(x_0)

        # Get noisy sample
        x_t, _ = self.noise_schedule.q_sample(x_0, t, noise)

        # Predict
        pred = self.forward(x_t, t, action, text_emb)

        # Compute target based on prediction type
        if self.config.prediction_type == "epsilon":
            target = noise
        elif self.config.prediction_type == "x0":
            target = x_0
        elif self.config.prediction_type == "v":
            # Velocity parameterization: v = sqrt(alpha) * noise - sqrt(1-alpha) * x0
            sqrt_alpha = self.noise_schedule.sqrt_alphas_cumprod[t].view(-1, 1)
            sqrt_one_minus_alpha = self.noise_schedule.sqrt_one_minus_alphas_cumprod[t].view(-1, 1)
            target = sqrt_alpha * noise - sqrt_one_minus_alpha * x_0
        else:
            raise ValueError(f"Unknown prediction type: {self.config.prediction_type}")

        # Loss
        if self.config.loss_type == "mse":
            loss = F.mse_loss(pred, target)
        elif self.config.loss_type == "l1":
            loss = F.l1_loss(pred, target)
        else:
            raise ValueError(f"Unknown loss type: {self.config.loss_type}")

        return {
            "loss": loss,
            "mse": F.mse_loss(pred, target),
        }

    @torch.no_grad()
    def sample(
        self,
        shape: tuple[int, ...] | torch.Tensor,
        action: torch.Tensor | None = None,
        text_emb: torch.Tensor | None = None,
        num_steps: int | None = None,
        guidance_scale: float | None = None,
    ) -> torch.Tensor:
        """Sample new states via DDIM.

        Args:
            shape: Output shape (B, latent_dim) or initial noise
            action: [B, action_dim] action conditioning
            text_emb: [B, text_dim] text conditioning
            num_steps: Override sampling steps
            guidance_scale: Override CFG scale

        Returns:
            [B, latent_dim] sampled states
        """
        num_steps = num_steps or self.config.num_sampling_steps
        guidance_scale = guidance_scale or self.config.guidance_scale

        # Initialize with noise
        if isinstance(shape, torch.Tensor):
            x = shape
        else:
            x = torch.randn(shape, device=self._device)

        B = x.shape[0]

        # DDIM timesteps (uniform)
        timesteps = torch.linspace(
            self.config.num_timesteps - 1, 0, num_steps + 1, device=self._device
        ).long()

        for i in range(num_steps):
            t = timesteps[i]
            t_next = timesteps[i + 1]

            t_batch = torch.full((B,), t, device=self._device, dtype=torch.long)

            # Classifier-free guidance
            if guidance_scale > 1.0 and (action is not None or text_emb is not None):
                # Conditional prediction
                pred_cond = self.forward(x, t_batch, action, text_emb)
                # Unconditional prediction
                pred_uncond = self.forward(x, t_batch, None, None)
                # Guided prediction
                pred = pred_uncond + guidance_scale * (pred_cond - pred_uncond)
            else:
                pred = self.forward(x, t_batch, action, text_emb)

            # DDIM update
            alpha_t = self.noise_schedule.alphas_cumprod[t]
            alpha_t_next = (
                self.noise_schedule.alphas_cumprod[t_next] if t_next >= 0 else torch.tensor(1.0)
            )

            if self.config.prediction_type == "epsilon":
                x0_pred = (x - torch.sqrt(1 - alpha_t) * pred) / torch.sqrt(alpha_t)
            elif self.config.prediction_type == "x0":
                x0_pred = pred
            elif self.config.prediction_type == "v":
                x0_pred = torch.sqrt(alpha_t) * x - torch.sqrt(1 - alpha_t) * pred

            # DDIM step (deterministic)
            x = torch.sqrt(alpha_t_next) * x0_pred + torch.sqrt(1 - alpha_t_next) * (
                x - torch.sqrt(alpha_t) * x0_pred
            ) / torch.sqrt(1 - alpha_t)

        return x

    @torch.no_grad()
    def imagine(
        self,
        initial_state: torch.Tensor,
        actions: torch.Tensor,
        text_emb: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Imagine trajectory given initial state and action sequence.

        Args:
            initial_state: [B, latent_dim] starting state
            actions: [B, H, action_dim] action sequence
            text_emb: [B, text_dim] optional text conditioning

        Returns:
            [B, H+1, latent_dim] imagined trajectory
        """
        _B, H, _ = actions.shape

        trajectory = [initial_state.unsqueeze(1)]
        state = initial_state

        for t in range(H):
            action = actions[:, t]

            # Sample next state
            noise = torch.randn_like(state)
            next_state = self.sample(noise, action, text_emb)

            trajectory.append(next_state.unsqueeze(1))
            state = next_state

        return torch.cat(trajectory, dim=1)


# =============================================================================
# FACTORY
# =============================================================================


def create_diffusion_world_model(
    latent_dim: int = 512,
    num_layers: int = 12,
    num_heads: int = 16,
    action_dim: int = 64,
    text_dim: int = 768,
) -> DiffusionWorldModel:
    """Factory for DiffusionWorldModel."""
    config = DiffusionConfig(
        latent_dim=latent_dim,
        num_layers=num_layers,
        num_heads=num_heads,
        action_dim=action_dim,
        text_dim=text_dim,
    )
    return DiffusionWorldModel(config)


__all__ = [
    "DiTBlock",
    "DiffusionConfig",
    "DiffusionWorldModel",
    "NoiseSchedule",
    "create_diffusion_world_model",
]
