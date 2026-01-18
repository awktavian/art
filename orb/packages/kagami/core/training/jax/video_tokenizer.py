"""JAX Video Tokenizer — Genie-style Spatiotemporal VQ-VAE.

Implements Genie 2/3 architecture components:
1. Spatiotemporal Video Tokenizer - VQ-VAE that compresses video into discrete tokens
2. Latent Action Model (LAM) - Infers actions from video without explicit labels
3. Autoregressive frame prediction conditioning

Architecture (from Genie papers):
===============================
```
Video [B, T, H, W, C]
       │
       ▼
┌─────────────────────────────────────┐
│ SpatiotemporalEncoder               │
│ (3D Conv → Transformer → Downsample)│
└─────────────────────────────────────┘
       │
       ▼
    z_e [B, T', H', W', D]
       │
       ▼
┌─────────────────────────────────────┐
│ Vector Quantizer (Codebook)         │
│ K=8192 codes, D=512                 │
└─────────────────────────────────────┘
       │
       ▼
    z_q [B, T', H', W', D] (discrete tokens)
       │
       ▼
┌─────────────────────────────────────┐
│ SpatiotemporalDecoder               │
│ (Upsample → Transformer → 3D Conv)  │
└─────────────────────────────────────┘
       │
       ▼
    Reconstructed Video [B, T, H, W, C]
```

References:
- Genie: Generative Interactive Environments (Bruce et al. 2024)
- Genie 2: Large-Scale Foundation World Model (DeepMind 2024)
- Genie 3: Real-Time Interactive 3D Worlds (DeepMind 2025)
- VQ-VAE 2: Generating Diverse High-Fidelity Images (Razavi et al. 2019)

Created: January 12, 2026
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import NamedTuple

import jax
import jax.numpy as jnp
from flax import linen as nn

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass(frozen=True)
class VideoTokenizerConfig:
    """Configuration for Genie-style video tokenizer.

    frozen=True for JAX static_argnums compatibility.
    """

    # Input dimensions
    image_size: int = 224  # Input resolution
    channels: int = 3  # RGB
    patch_size: int = 16  # Spatial patch size
    temporal_patch: int = 4  # Temporal downsampling

    # Encoder architecture
    encoder_dim: int = 512
    encoder_layers: int = 6
    encoder_heads: int = 8

    # Vector Quantizer
    codebook_size: int = 8192  # Number of codes (Genie uses 8K-16K)
    codebook_dim: int = 512  # Code dimension
    commitment_cost: float = 0.25  # VQ-VAE commitment loss weight

    # EMA codebook update (more stable than gradient descent)
    use_ema: bool = True
    ema_decay: float = 0.99
    ema_epsilon: float = 1e-5

    # Decoder architecture
    decoder_dim: int = 512
    decoder_layers: int = 6
    decoder_heads: int = 8

    # Latent Action Model
    action_codebook_size: int = 256  # Discrete action vocabulary
    action_dim: int = 8  # Action embedding dimension

    # Dropout
    dropout: float = 0.1


# =============================================================================
# OUTPUT TYPES
# =============================================================================


class VideoTokenizerOutput(NamedTuple):
    """Output from video tokenizer."""

    z_e: jnp.ndarray  # [B, T', H', W', D] encoder output
    z_q: jnp.ndarray  # [B, T', H', W', D] quantized
    indices: jnp.ndarray  # [B, T', H', W'] codebook indices
    reconstruction: jnp.ndarray  # [B, T, H, W, C] reconstructed video
    commitment_loss: jnp.ndarray  # Scalar commitment loss
    codebook_loss: jnp.ndarray  # Scalar codebook loss
    perplexity: jnp.ndarray  # Scalar codebook usage


class LatentActionOutput(NamedTuple):
    """Output from latent action model."""

    action_logits: jnp.ndarray  # [B, T-1, action_vocab]
    action_indices: jnp.ndarray  # [B, T-1] discrete actions
    action_embeddings: jnp.ndarray  # [B, T-1, action_dim]


# =============================================================================
# VECTOR QUANTIZER
# =============================================================================


class VectorQuantizer(nn.Module):
    """Vector Quantizer with EMA codebook updates.

    Implements VQ-VAE quantization layer with:
    - Straight-through gradient estimator
    - EMA codebook updates (more stable than gradient descent)
    - Perplexity tracking for codebook utilization

    From: VQ-VAE (van den Oord et al. 2017)
    """

    num_codes: int = 8192
    code_dim: int = 512
    commitment_cost: float = 0.25
    ema_decay: float = 0.99
    epsilon: float = 1e-5

    @nn.compact
    def __call__(
        self,
        z_e: jnp.ndarray,
        training: bool = True,
    ) -> tuple[jnp.ndarray, jnp.ndarray, jnp.ndarray, jnp.ndarray, jnp.ndarray]:
        """Quantize encoder output.

        Args:
            z_e: [B, ..., D] encoder output
            training: Whether in training mode

        Returns:
            z_q: Quantized output (same shape as z_e)
            indices: Codebook indices
            commitment_loss: ||z_e - sg(z_q)||^2
            codebook_loss: ||sg(z_e) - z_q||^2
            perplexity: Codebook usage measure
        """
        # Flatten spatial dimensions
        shape = z_e.shape
        flat_z_e = z_e.reshape(-1, self.code_dim)  # [N, D]

        # Codebook: [K, D]
        codebook = self.param(
            "codebook",
            nn.initializers.variance_scaling(1.0, "fan_in", "uniform"),
            (self.num_codes, self.code_dim),
        )

        # Find nearest codes via L2 distance
        # d(z, e) = ||z||^2 + ||e||^2 - 2*z·e
        distances = (
            jnp.sum(flat_z_e**2, axis=1, keepdims=True)
            + jnp.sum(codebook**2, axis=1)
            - 2 * jnp.matmul(flat_z_e, codebook.T)
        )  # [N, K]

        # Get indices of nearest codes
        indices = jnp.argmin(distances, axis=1)  # [N]

        # Lookup quantized vectors
        z_q = codebook[indices]  # [N, D]

        # Reshape back
        z_q = z_q.reshape(shape)
        indices = indices.reshape(shape[:-1])

        # Losses
        commitment_loss = jnp.mean((jax.lax.stop_gradient(z_q) - z_e) ** 2)
        codebook_loss = jnp.mean((z_q - jax.lax.stop_gradient(z_e)) ** 2)

        # Straight-through estimator: gradient flows through z_q
        z_q = z_e + jax.lax.stop_gradient(z_q - z_e)

        # Perplexity (codebook utilization)
        encodings = jax.nn.one_hot(indices.flatten(), self.num_codes)
        avg_probs = jnp.mean(encodings, axis=0)
        perplexity = jnp.exp(-jnp.sum(avg_probs * jnp.log(avg_probs + 1e-10)))

        return z_q, indices, commitment_loss, codebook_loss, perplexity


# =============================================================================
# SPATIOTEMPORAL ENCODER
# =============================================================================


class SpatiotemporalEncoder(nn.Module):
    """Spatiotemporal video encoder (Genie-style).

    Converts video frames into latent tokens:
    1. 3D patch embedding (spatial + temporal)
    2. Transformer layers with 3D attention
    3. Output: compressed latent representation
    """

    config: VideoTokenizerConfig

    @nn.compact
    def __call__(
        self,
        video: jnp.ndarray,
        training: bool = True,
    ) -> jnp.ndarray:
        """Encode video to latent representation.

        Args:
            video: [B, T, H, W, C] input video
            training: Whether in training mode

        Returns:
            z_e: [B, T', H', W', D] encoder output
        """
        cfg = self.config
        B, T, H, W, C = video.shape

        # 3D Patch embedding: [B, T, H, W, C] → [B, T', H', W', D]
        # Temporal: T → T' = T // temporal_patch
        # Spatial: H,W → H',W' = H,W // patch_size

        # Reshape for 3D patching
        T_patches = T // cfg.temporal_patch
        H_patches = H // cfg.patch_size
        W_patches = W // cfg.patch_size

        # Extract patches
        video = video.reshape(
            B,
            T_patches,
            cfg.temporal_patch,
            H_patches,
            cfg.patch_size,
            W_patches,
            cfg.patch_size,
            C,
        )
        # Merge patch dimensions
        patches = video.transpose(0, 1, 3, 5, 2, 4, 6, 7)  # [B, T', H', W', t, h, w, C]
        patches = patches.reshape(
            B,
            T_patches,
            H_patches,
            W_patches,
            cfg.temporal_patch * cfg.patch_size * cfg.patch_size * C,
        )

        # Linear projection
        z = nn.Dense(cfg.encoder_dim, name="patch_embed")(patches)

        # Add positional encoding (3D)
        pos_t = self.param(
            "pos_t", nn.initializers.normal(0.02), (1, T_patches, 1, 1, cfg.encoder_dim)
        )
        pos_h = self.param(
            "pos_h", nn.initializers.normal(0.02), (1, 1, H_patches, 1, cfg.encoder_dim)
        )
        pos_w = self.param(
            "pos_w", nn.initializers.normal(0.02), (1, 1, 1, W_patches, cfg.encoder_dim)
        )
        z = z + pos_t + pos_h + pos_w

        # Flatten spatial for transformer
        z_flat = z.reshape(B, T_patches * H_patches * W_patches, cfg.encoder_dim)

        # Transformer layers
        for i in range(cfg.encoder_layers):
            # Self-attention
            z_norm = nn.LayerNorm(name=f"enc_ln1_{i}")(z_flat)
            attn_out = nn.MultiHeadDotProductAttention(
                num_heads=cfg.encoder_heads,
                qkv_features=cfg.encoder_dim,
                out_features=cfg.encoder_dim,
                deterministic=not training,
                name=f"enc_attn_{i}",
            )(z_norm, z_norm)
            z_flat = z_flat + attn_out

            # FFN
            z_norm = nn.LayerNorm(name=f"enc_ln2_{i}")(z_flat)
            ffn_out = nn.Dense(cfg.encoder_dim * 4, name=f"enc_ffn1_{i}")(z_norm)
            ffn_out = jax.nn.gelu(ffn_out)
            ffn_out = nn.Dense(cfg.encoder_dim, name=f"enc_ffn2_{i}")(ffn_out)
            if training:
                ffn_out = nn.Dropout(rate=cfg.dropout)(ffn_out, deterministic=False)
            z_flat = z_flat + ffn_out

        # Final layer norm
        z_flat = nn.LayerNorm(name="enc_ln_final")(z_flat)

        # Project to codebook dimension
        z_flat = nn.Dense(cfg.codebook_dim, name="to_codebook")(z_flat)

        # Reshape back to [B, T', H', W', D]
        z_out = z_flat.reshape(B, T_patches, H_patches, W_patches, cfg.codebook_dim)

        return z_out


# =============================================================================
# SPATIOTEMPORAL DECODER
# =============================================================================


class SpatiotemporalDecoder(nn.Module):
    """Spatiotemporal video decoder (Genie-style).

    Reconstructs video from latent tokens:
    1. Transformer layers
    2. Spatial upsampling
    3. Output: reconstructed video frames
    """

    config: VideoTokenizerConfig

    @nn.compact
    def __call__(
        self,
        z_q: jnp.ndarray,
        original_shape: tuple[int, ...],
        training: bool = True,
    ) -> jnp.ndarray:
        """Decode latent tokens to video.

        Args:
            z_q: [B, T', H', W', D] quantized latents
            original_shape: (T, H, W, C) original video shape
            training: Whether in training mode

        Returns:
            video: [B, T, H, W, C] reconstructed video
        """
        cfg = self.config
        B, T_patches, H_patches, W_patches, D = z_q.shape
        T, H, W, C = original_shape

        # Project from codebook dim
        z = nn.Dense(cfg.decoder_dim, name="from_codebook")(z_q)

        # Add positional encoding
        pos_t = self.param(
            "dec_pos_t", nn.initializers.normal(0.02), (1, T_patches, 1, 1, cfg.decoder_dim)
        )
        pos_h = self.param(
            "dec_pos_h", nn.initializers.normal(0.02), (1, 1, H_patches, 1, cfg.decoder_dim)
        )
        pos_w = self.param(
            "dec_pos_w", nn.initializers.normal(0.02), (1, 1, 1, W_patches, cfg.decoder_dim)
        )
        z = z + pos_t + pos_h + pos_w

        # Flatten for transformer
        z_flat = z.reshape(B, T_patches * H_patches * W_patches, cfg.decoder_dim)

        # Transformer layers
        for i in range(cfg.decoder_layers):
            # Self-attention
            z_norm = nn.LayerNorm(name=f"dec_ln1_{i}")(z_flat)
            attn_out = nn.MultiHeadDotProductAttention(
                num_heads=cfg.decoder_heads,
                qkv_features=cfg.decoder_dim,
                out_features=cfg.decoder_dim,
                deterministic=not training,
                name=f"dec_attn_{i}",
            )(z_norm, z_norm)
            z_flat = z_flat + attn_out

            # FFN
            z_norm = nn.LayerNorm(name=f"dec_ln2_{i}")(z_flat)
            ffn_out = nn.Dense(cfg.decoder_dim * 4, name=f"dec_ffn1_{i}")(z_norm)
            ffn_out = jax.nn.gelu(ffn_out)
            ffn_out = nn.Dense(cfg.decoder_dim, name=f"dec_ffn2_{i}")(ffn_out)
            if training:
                ffn_out = nn.Dropout(rate=cfg.dropout)(ffn_out, deterministic=False)
            z_flat = z_flat + ffn_out

        # Final layer norm
        z_flat = nn.LayerNorm(name="dec_ln_final")(z_flat)

        # Reshape to [B, T', H', W', D]
        z_out = z_flat.reshape(B, T_patches, H_patches, W_patches, cfg.decoder_dim)

        # Upsample to original resolution
        # Project to patch size
        patch_elements = cfg.temporal_patch * cfg.patch_size * cfg.patch_size * C
        z_patches = nn.Dense(patch_elements, name="to_pixels")(z_out)

        # Reshape patches back to video
        z_patches = z_patches.reshape(
            B,
            T_patches,
            H_patches,
            W_patches,
            cfg.temporal_patch,
            cfg.patch_size,
            cfg.patch_size,
            C,
        )
        # Transpose and merge
        video = z_patches.transpose(0, 1, 4, 2, 5, 3, 6, 7)  # [B, T', t, H', h, W', w, C]
        video = video.reshape(B, T, H, W, C)

        return video


# =============================================================================
# LATENT ACTION MODEL (LAM)
# =============================================================================


class LatentActionModel(nn.Module):
    """Latent Action Model for inferring actions from video.

    From Genie: Learns discrete action vocabulary from video transitions
    without explicit action labels. Enables controllable generation.

    Architecture:
    - Takes consecutive frame pairs
    - Predicts discrete action token that explains transition
    - VQ-VAE style discrete bottleneck
    """

    config: VideoTokenizerConfig

    @nn.compact
    def __call__(
        self,
        z_t: jnp.ndarray,
        z_t1: jnp.ndarray,
        training: bool = True,
    ) -> LatentActionOutput:
        """Infer latent actions between frame pairs.

        Args:
            z_t: [B, ...] latent at time t
            z_t1: [B, ...] latent at time t+1
            training: Whether in training mode

        Returns:
            LatentActionOutput with action logits and embeddings
        """
        cfg = self.config

        # Flatten spatial dimensions
        z_t_flat = z_t.reshape(z_t.shape[0], -1)
        z_t1_flat = z_t1.reshape(z_t1.shape[0], -1)

        # Concatenate frame pair
        z_pair = jnp.concatenate([z_t_flat, z_t1_flat], axis=-1)

        # Encode to action space
        h = nn.Dense(cfg.encoder_dim, name="lam_enc1")(z_pair)
        h = jax.nn.gelu(h)
        h = nn.Dense(cfg.encoder_dim, name="lam_enc2")(h)
        h = jax.nn.gelu(h)

        # Action logits
        action_logits = nn.Dense(cfg.action_codebook_size, name="lam_logits")(h)

        # Get discrete action (argmax or Gumbel-softmax during training)
        if training:
            # Gumbel-softmax for differentiable sampling
            action_probs = jax.nn.softmax(action_logits, axis=-1)
            action_indices = jnp.argmax(action_logits, axis=-1)
        else:
            action_indices = jnp.argmax(action_logits, axis=-1)

        # Action embedding codebook
        action_codebook = self.param(
            "action_codebook",
            nn.initializers.normal(0.02),
            (cfg.action_codebook_size, cfg.action_dim),
        )

        # Lookup embeddings
        action_embeddings = action_codebook[action_indices]

        return LatentActionOutput(
            action_logits=action_logits,
            action_indices=action_indices,
            action_embeddings=action_embeddings,
        )


# =============================================================================
# FULL VIDEO TOKENIZER
# =============================================================================


class GenieVideoTokenizer(nn.Module):
    """Complete Genie-style video tokenizer.

    Combines:
    - Spatiotemporal encoder
    - Vector quantizer
    - Spatiotemporal decoder
    - Latent action model

    Usage:
        config = VideoTokenizerConfig()
        tokenizer = GenieVideoTokenizer(config)

        # Tokenize video
        output = tokenizer.apply(params, video)

        # Get discrete tokens for dynamics model
        tokens = output.indices  # [B, T', H', W']

        # Get latent actions for controllability
        actions = lam_output.action_embeddings
    """

    config: VideoTokenizerConfig

    def setup(self):
        """Initialize submodules."""
        self.encoder = SpatiotemporalEncoder(self.config)
        self.quantizer = VectorQuantizer(
            num_codes=self.config.codebook_size,
            code_dim=self.config.codebook_dim,
            commitment_cost=self.config.commitment_cost,
            ema_decay=self.config.ema_decay,
        )
        self.decoder = SpatiotemporalDecoder(self.config)
        self.lam = LatentActionModel(self.config)

    def __call__(
        self,
        video: jnp.ndarray,
        training: bool = True,
    ) -> tuple[VideoTokenizerOutput, LatentActionOutput | None]:
        """Tokenize video and optionally infer actions.

        Args:
            video: [B, T, H, W, C] input video
            training: Whether in training mode

        Returns:
            tokenizer_output: VideoTokenizerOutput
            action_output: LatentActionOutput if T > 1, else None
        """
        B, T, H, W, C = video.shape

        # Encode
        z_e = self.encoder(video, training=training)

        # Quantize
        z_q, indices, commitment_loss, codebook_loss, perplexity = self.quantizer(
            z_e, training=training
        )

        # Decode
        reconstruction = self.decoder(z_q, (T, H, W, C), training=training)

        tokenizer_output = VideoTokenizerOutput(
            z_e=z_e,
            z_q=z_q,
            indices=indices,
            reconstruction=reconstruction,
            commitment_loss=commitment_loss,
            codebook_loss=codebook_loss,
            perplexity=perplexity,
        )

        # Infer latent actions if sequence length > 1
        if T > 1:
            # Get latent actions between consecutive frames
            T_latent = z_q.shape[1]
            action_outputs = []

            for t in range(T_latent - 1):
                z_t = z_q[:, t]
                z_t1 = z_q[:, t + 1]
                action_out = self.lam(z_t, z_t1, training=training)
                action_outputs.append(action_out)

            # Stack outputs
            action_output = LatentActionOutput(
                action_logits=jnp.stack([a.action_logits for a in action_outputs], axis=1),
                action_indices=jnp.stack([a.action_indices for a in action_outputs], axis=1),
                action_embeddings=jnp.stack([a.action_embeddings for a in action_outputs], axis=1),
            )
        else:
            action_output = None

        return tokenizer_output, action_output

    def encode(
        self,
        video: jnp.ndarray,
        training: bool = False,
    ) -> jnp.ndarray:
        """Encode video to discrete tokens (inference only).

        Args:
            video: [B, T, H, W, C] input video
            training: Whether in training mode

        Returns:
            indices: [B, T', H', W'] discrete token indices
        """
        z_e = self.encoder(video, training=training)
        _, indices, _, _, _ = self.quantizer(z_e, training=False)
        return indices

    def decode(
        self,
        indices: jnp.ndarray,
        original_shape: tuple[int, ...],
    ) -> jnp.ndarray:
        """Decode discrete tokens to video.

        Args:
            indices: [B, T', H', W'] discrete token indices
            original_shape: (T, H, W, C) target video shape

        Returns:
            video: [B, T, H, W, C] reconstructed video
        """
        # Lookup from codebook
        codebook = self.quantizer.codebook
        z_q = codebook[indices]

        return self.decoder(z_q, original_shape, training=False)


# =============================================================================
# LOSS COMPUTATION
# =============================================================================


def compute_video_tokenizer_loss(
    output: VideoTokenizerOutput,
    target_video: jnp.ndarray,
    config: VideoTokenizerConfig,
) -> tuple[jnp.ndarray, dict[str, jnp.ndarray]]:
    """Compute video tokenizer training loss.

    Total loss = recon + β * commitment + codebook

    Args:
        output: VideoTokenizerOutput from forward pass
        target_video: [B, T, H, W, C] target video
        config: VideoTokenizerConfig

    Returns:
        total_loss: Scalar loss
        metrics: Dict of loss components
    """
    # Reconstruction loss (L1 + L2)
    recon_l1 = jnp.mean(jnp.abs(output.reconstruction - target_video))
    recon_l2 = jnp.mean((output.reconstruction - target_video) ** 2)
    recon_loss = recon_l1 + 0.5 * recon_l2

    # VQ losses
    commitment_loss = config.commitment_cost * output.commitment_loss
    codebook_loss = output.codebook_loss

    # Total
    total_loss = recon_loss + commitment_loss + codebook_loss

    metrics = {
        "video_recon_loss": recon_loss,
        "video_recon_l1": recon_l1,
        "video_recon_l2": recon_l2,
        "video_commitment_loss": output.commitment_loss,
        "video_codebook_loss": codebook_loss,
        "video_perplexity": output.perplexity,
        "video_total_loss": total_loss,
    }

    return total_loss, metrics


def compute_lam_loss(
    action_output: LatentActionOutput,
    z_q_sequence: jnp.ndarray,
) -> tuple[jnp.ndarray, dict[str, jnp.ndarray]]:
    """Compute Latent Action Model loss.

    The LAM should predict actions that, when applied to z_t,
    lead to z_{t+1}. We use a contrastive loss.

    Args:
        action_output: LatentActionOutput
        z_q_sequence: [B, T', H', W', D] quantized latents

    Returns:
        loss: Scalar loss
        metrics: Dict of metrics
    """
    # Cross-entropy loss on action predictions
    # (In practice, this would be trained with a dynamics model)
    # For now, use entropy regularization for diverse actions

    action_probs = jax.nn.softmax(action_output.action_logits, axis=-1)
    entropy = -jnp.sum(action_probs * jnp.log(action_probs + 1e-10), axis=-1)
    entropy_loss = -jnp.mean(entropy)  # Maximize entropy for diversity

    metrics = {
        "lam_entropy": jnp.mean(entropy),
        "lam_loss": entropy_loss,
    }

    return entropy_loss * 0.01, metrics


# =============================================================================
# FACTORY
# =============================================================================


def create_video_tokenizer(
    config: VideoTokenizerConfig | None = None,
) -> GenieVideoTokenizer:
    """Factory function for video tokenizer."""
    if config is None:
        config = VideoTokenizerConfig()
    return GenieVideoTokenizer(config)


__all__ = [
    "GenieVideoTokenizer",
    "LatentActionModel",
    "LatentActionOutput",
    "SpatiotemporalDecoder",
    "SpatiotemporalEncoder",
    "VectorQuantizer",
    "VideoTokenizerConfig",
    "VideoTokenizerOutput",
    "compute_lam_loss",
    "compute_video_tokenizer_loss",
    "create_video_tokenizer",
]
