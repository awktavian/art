"""JAX Multimodal Integration — Unified Video/Audio/Text World Model.

Integrates all modalities into a unified world model architecture:
1. Video: Genie-style spatiotemporal tokenizer
2. Audio: AST-style spectrogram encoder
3. Text: Language-conditioned RSSM
4. Fusion: Cross-modal attention and alignment

Architecture (Genie 3 + Gemini-inspired):
=========================================
```
┌─────────────────────────────────────────────────────────────────┐
│                        INPUT TOWER                              │
├─────────────────┬─────────────────┬─────────────────────────────┤
│   VIDEO         │    AUDIO        │        TEXT                 │
│   [B,T,H,W,C]   │    [B,samples]  │    [B,L]                   │
│       │         │        │        │        │                    │
│       ▼         │        ▼        │        ▼                    │
│  VideoTokenizer │  AudioEncoder   │   TextEncoder               │
│       │         │        │        │        │                    │
│       ▼         │        ▼        │        ▼                    │
│   z_video       │   z_audio       │   z_text                    │
│   [B,T',D]      │   [B,N,D]       │   [B,L,D]                  │
└─────────────────┴─────────────────┴─────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FUSION MODULE                                │
│                                                                  │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │ CrossModalAttention                                      │  │
│   │ - Video attends to Audio                                │  │
│   │ - Video attends to Text                                 │  │
│   │ - Audio attends to Text                                 │  │
│   └─────────────────────────────────────────────────────────┘  │
│                          │                                      │
│                          ▼                                      │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │ Multimodal Transformer                                   │  │
│   │ - Concatenated modality tokens                          │  │
│   │ - Learnable modality embeddings                         │  │
│   └─────────────────────────────────────────────────────────┘  │
│                          │                                      │
│                          ▼                                      │
│                   z_fused [B, M, D]                            │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    WORLD MODEL (RSSM)                          │
│                                                                  │
│   z_fused → OrganismRSSM → h [B, T, 7, D]                     │
│                          │                                      │
│   ┌──────────────────────┴──────────────────────┐              │
│   │         │            │           │          │              │
│   ▼         ▼            ▼           ▼          ▼              │
│  obs_pred reward_pred continue_pred video_pred text_pred      │
└─────────────────────────────────────────────────────────────────┘

References:
- Genie 3: Real-time Interactive 3D Environments (DeepMind 2025)
- Gemini: Multimodal AI (Google 2023)
- Flamingo: Visual Language Model (DeepMind 2022)
- ImageBind: One Embedding Space To Bind Them All (Meta 2023)

Created: January 12, 2026
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, NamedTuple

import jax
import jax.numpy as jnp
from flax import linen as nn

from .audio_encoder import (
    AudioEncoder,
    AudioEncoderConfig,
    AudioEncoderOutput,
    AudioVisualAligner,
    create_mel_filterbank,
)
from .language import LanguageConfig
from .video_tokenizer import (
    GenieVideoTokenizer,
    LatentActionOutput,
    VideoTokenizerConfig,
    VideoTokenizerOutput,
    compute_lam_loss,
    compute_video_tokenizer_loss,
)

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass(frozen=True)
class MultimodalConfig:
    """Configuration for multimodal world model.

    frozen=True for JAX static_argnums compatibility.
    """

    # Modality dimensions
    video_dim: int = 512
    audio_dim: int = 512
    text_dim: int = 768
    fused_dim: int = 512

    # Which modalities to use
    use_video: bool = True
    use_audio: bool = True
    use_text: bool = True

    # Fusion architecture
    num_fusion_layers: int = 4
    num_fusion_heads: int = 8
    fusion_mlp_dim: int = 2048
    fusion_dropout: float = 0.1

    # Cross-modal alignment
    use_contrastive: bool = True
    contrastive_temperature: float = 0.07

    # Video tokenizer config
    video_config: VideoTokenizerConfig = None

    # Audio encoder config
    audio_config: AudioEncoderConfig = None

    # Language config
    language_config: LanguageConfig = None

    # RSSM integration
    rssm_hidden_dim: int = 384
    num_colonies: int = 7

    def __post_init__(self):
        """Initialize sub-configs if not provided."""
        object.__setattr__(self, "video_config", self.video_config or VideoTokenizerConfig())
        object.__setattr__(self, "audio_config", self.audio_config or AudioEncoderConfig())
        object.__setattr__(self, "language_config", self.language_config or LanguageConfig())


# =============================================================================
# OUTPUT TYPES
# =============================================================================


class MultimodalBatch(NamedTuple):
    """Batch of multimodal training data."""

    # Required: continuous observations for RSSM
    obs: jnp.ndarray  # [B, T, obs_dim]
    actions: jnp.ndarray  # [B, T, action_dim]
    rewards: jnp.ndarray  # [B, T]
    continues: jnp.ndarray  # [B, T]

    # Optional: raw modalities
    video: jnp.ndarray | None = None  # [B, T, H, W, C]
    audio: jnp.ndarray | None = None  # [B, samples]
    text_ids: jnp.ndarray | None = None  # [B, L]
    text_mask: jnp.ndarray | None = None  # [B, L]


class MultimodalOutput(NamedTuple):
    """Output from multimodal world model."""

    # RSSM outputs
    h: jnp.ndarray  # [B, T, 7, D] hidden states
    z: jnp.ndarray  # [B, T, 7, D] stochastic states
    obs_pred: jnp.ndarray  # [B, T, obs_dim]
    reward_pred: jnp.ndarray  # [B, T, reward_bins]
    continue_pred: jnp.ndarray  # [B, T, 1]
    kl_balanced: jnp.ndarray  # Scalar
    kl_raw: jnp.ndarray  # Scalar

    # Modality-specific outputs
    video_output: VideoTokenizerOutput | None = None
    audio_output: AudioEncoderOutput | None = None
    action_output: LatentActionOutput | None = None

    # Fused representation
    z_fused: jnp.ndarray | None = None  # [B, M, D]


# =============================================================================
# CROSS-MODAL ATTENTION
# =============================================================================


class CrossModalAttention(nn.Module):
    """Cross-modal attention for multimodal fusion.

    Allows one modality to attend to another for information exchange.
    """

    hidden_dim: int = 512
    num_heads: int = 8
    dropout: float = 0.1

    @nn.compact
    def __call__(
        self,
        query: jnp.ndarray,
        key_value: jnp.ndarray,
        training: bool = True,
    ) -> jnp.ndarray:
        """Apply cross-modal attention.

        Args:
            query: [B, Nq, D] query modality
            key_value: [B, Nkv, D] key-value modality
            training: Whether in training mode

        Returns:
            [B, Nq, D] attended output
        """
        # Pre-norm
        query_norm = nn.LayerNorm(name="query_ln")(query)
        kv_norm = nn.LayerNorm(name="kv_ln")(key_value)

        # Cross-attention
        attended = nn.MultiHeadDotProductAttention(
            num_heads=self.num_heads,
            qkv_features=self.hidden_dim,
            out_features=self.hidden_dim,
            deterministic=not training,
            name="cross_attn",
        )(query_norm, kv_norm)

        if training:
            attended = nn.Dropout(rate=self.dropout)(attended, deterministic=False)

        return query + attended


# =============================================================================
# MULTIMODAL FUSION
# =============================================================================


class MultimodalFusion(nn.Module):
    """Fuses multiple modality embeddings.

    Uses:
    1. Modality-specific projection
    2. Learnable modality embeddings
    3. Cross-modal attention layers
    4. Final transformer for unified representation
    """

    config: MultimodalConfig

    @nn.compact
    def __call__(
        self,
        video_emb: jnp.ndarray | None,
        audio_emb: jnp.ndarray | None,
        text_emb: jnp.ndarray | None,
        training: bool = True,
    ) -> jnp.ndarray:
        """Fuse multimodal embeddings.

        Args:
            video_emb: [B, Nv, Dv] video embeddings
            audio_emb: [B, Na, Da] audio embeddings
            text_emb: [B, Nt, Dt] text embeddings
            training: Whether in training mode

        Returns:
            z_fused: [B, M, D] fused multimodal representation
        """
        cfg = self.config
        B = (
            video_emb if video_emb is not None else audio_emb if audio_emb is not None else text_emb
        ).shape[0]

        modalities = []

        # Project each modality to common dimension
        if video_emb is not None and cfg.use_video:
            video_proj = nn.Dense(cfg.fused_dim, name="video_proj")(video_emb)
            # Add modality embedding
            video_mod_emb = self.param(
                "video_mod_emb",
                nn.initializers.normal(0.02),
                (1, 1, cfg.fused_dim),
            )
            video_proj = video_proj + video_mod_emb
            modalities.append(video_proj)

        if audio_emb is not None and cfg.use_audio:
            audio_proj = nn.Dense(cfg.fused_dim, name="audio_proj")(audio_emb)
            audio_mod_emb = self.param(
                "audio_mod_emb",
                nn.initializers.normal(0.02),
                (1, 1, cfg.fused_dim),
            )
            audio_proj = audio_proj + audio_mod_emb
            modalities.append(audio_proj)

        if text_emb is not None and cfg.use_text:
            text_proj = nn.Dense(cfg.fused_dim, name="text_proj")(text_emb)
            text_mod_emb = self.param(
                "text_mod_emb",
                nn.initializers.normal(0.02),
                (1, 1, cfg.fused_dim),
            )
            text_proj = text_proj + text_mod_emb
            modalities.append(text_proj)

        if len(modalities) == 0:
            raise ValueError("At least one modality must be provided")

        # Concatenate all modalities
        z_concat = jnp.concatenate(modalities, axis=1)  # [B, M, D]

        # Cross-modal attention layers
        if len(modalities) > 1:
            for i in range(cfg.num_fusion_layers):
                # Self-attention over concatenated
                z_norm = nn.LayerNorm(name=f"fusion_ln1_{i}")(z_concat)
                attn_out = nn.MultiHeadDotProductAttention(
                    num_heads=cfg.num_fusion_heads,
                    qkv_features=cfg.fused_dim,
                    out_features=cfg.fused_dim,
                    deterministic=not training,
                    name=f"fusion_attn_{i}",
                )(z_norm, z_norm)
                z_concat = z_concat + attn_out

                # FFN
                z_norm = nn.LayerNorm(name=f"fusion_ln2_{i}")(z_concat)
                ffn = nn.Dense(cfg.fusion_mlp_dim, name=f"fusion_ffn1_{i}")(z_norm)
                ffn = jax.nn.gelu(ffn)
                ffn = nn.Dense(cfg.fused_dim, name=f"fusion_ffn2_{i}")(ffn)
                if training:
                    ffn = nn.Dropout(rate=cfg.fusion_dropout)(ffn, deterministic=False)
                z_concat = z_concat + ffn

        # Final layer norm
        z_fused = nn.LayerNorm(name="fusion_ln_final")(z_concat)

        return z_fused


# =============================================================================
# MULTIMODAL WORLD MODEL
# =============================================================================


class MultimodalWorldModel(nn.Module):
    """Complete multimodal world model.

    Integrates:
    - Video tokenizer (Genie-style)
    - Audio encoder (AST-style)
    - Text encoder (learned)
    - Multimodal fusion
    - OrganismRSSM for world modeling

    This is THE unified multimodal system.
    """

    config: MultimodalConfig
    rssm_config: Any  # OrganismRSSMConfig from rssm.py

    def setup(self):
        """Initialize all submodules."""
        cfg = self.config

        # Modality encoders
        if cfg.use_video:
            self.video_tokenizer = GenieVideoTokenizer(cfg.video_config)

        if cfg.use_audio:
            self.audio_encoder = AudioEncoder(cfg.audio_config)
            self.mel_filterbank = create_mel_filterbank(
                sample_rate=cfg.audio_config.sample_rate,
                n_fft=cfg.audio_config.n_fft,
                n_mels=cfg.audio_config.n_mels,
            )

        if cfg.use_text:
            # Simple text encoder (for TPU efficiency, not a full LLM)
            self.text_encoder = nn.Embed(
                num_embeddings=32000,  # Vocabulary
                features=cfg.text_dim,
                name="text_embed",
            )
            self.text_pos_embed = self.param(
                "text_pos_embed",
                nn.initializers.normal(0.02),
                (1, 512, cfg.text_dim),  # Max 512 tokens
            )

        # Multimodal fusion
        self.fusion = MultimodalFusion(cfg)

        # Project fused representation to RSSM observation space
        self.to_rssm_obs = nn.Dense(
            self.rssm_config.obs_dim,
            name="to_rssm_obs",
        )

        # Audio-visual alignment (optional)
        if cfg.use_contrastive and cfg.use_video and cfg.use_audio:
            self.av_aligner = AudioVisualAligner(
                embed_dim=cfg.fused_dim,
                temperature=cfg.contrastive_temperature,
            )

    def encode_video(
        self,
        video: jnp.ndarray,
        training: bool = True,
    ) -> tuple[jnp.ndarray, VideoTokenizerOutput, LatentActionOutput | None]:
        """Encode video to embeddings.

        Args:
            video: [B, T, H, W, C] input video
            training: Whether in training mode

        Returns:
            embeddings: [B, T', D] video embeddings
            output: VideoTokenizerOutput
            action_output: LatentActionOutput
        """
        tok_output, action_output = self.video_tokenizer(video, training=training)

        # Flatten spatial for RSSM
        B, T, H, W, D = tok_output.z_q.shape
        embeddings = tok_output.z_q.reshape(B, T, H * W, D)
        embeddings = jnp.mean(embeddings, axis=2)  # Pool spatial: [B, T, D]

        return embeddings, tok_output, action_output

    def encode_audio(
        self,
        audio: jnp.ndarray,
        training: bool = True,
    ) -> tuple[jnp.ndarray, AudioEncoderOutput]:
        """Encode audio to embeddings.

        Args:
            audio: [B, samples] raw audio
            training: Whether in training mode

        Returns:
            embeddings: [B, N, D] audio embeddings
            output: AudioEncoderOutput
        """
        output = self.audio_encoder(audio, self.mel_filterbank, training=training)
        return output.embeddings, output

    def encode_text(
        self,
        text_ids: jnp.ndarray,
        text_mask: jnp.ndarray | None = None,
        training: bool = True,
    ) -> jnp.ndarray:
        """Encode text to embeddings.

        Args:
            text_ids: [B, L] token IDs
            text_mask: [B, L] attention mask
            training: Whether in training mode

        Returns:
            embeddings: [B, L, D] text embeddings
        """
        # Embed tokens
        embeddings = self.text_encoder(text_ids)

        # Add positional encoding
        L = text_ids.shape[1]
        embeddings = embeddings + self.text_pos_embed[:, :L, :]

        # Apply mask
        if text_mask is not None:
            embeddings = embeddings * text_mask[:, :, None]

        return embeddings

    def __call__(
        self,
        batch: MultimodalBatch,
        rssm_apply_fn: Any,
        rssm_params: Any,
        key: jax.Array,
        training: bool = True,
    ) -> MultimodalOutput:
        """Forward pass through multimodal world model.

        Args:
            batch: MultimodalBatch with all inputs
            rssm_apply_fn: RSSM apply function
            rssm_params: RSSM parameters
            key: JAX random key
            training: Whether in training mode

        Returns:
            MultimodalOutput
        """
        cfg = self.config

        video_emb = None
        audio_emb = None
        text_emb = None
        video_output = None
        audio_output = None
        action_output = None

        # Encode each available modality
        if batch.video is not None and cfg.use_video:
            video_emb, video_output, action_output = self.encode_video(
                batch.video, training=training
            )

        if batch.audio is not None and cfg.use_audio:
            audio_emb, audio_output = self.encode_audio(batch.audio, training=training)

        if batch.text_ids is not None and cfg.use_text:
            text_emb = self.encode_text(batch.text_ids, batch.text_mask, training=training)

        # Fuse modalities
        z_fused = None
        if any(x is not None for x in [video_emb, audio_emb, text_emb]):
            z_fused = self.fusion(video_emb, audio_emb, text_emb, training=training)

            # Project to RSSM observation space
            # Average over sequence to get single obs per timestep
            z_fused_pooled = jnp.mean(z_fused, axis=1)  # [B, D]

            # Expand to match RSSM temporal dimension
            T = batch.obs.shape[1]
            multimodal_obs = self.to_rssm_obs(z_fused_pooled)  # [B, obs_dim]
            multimodal_obs = jnp.broadcast_to(
                multimodal_obs[:, None, :], (batch.obs.shape[0], T, batch.obs.shape[2])
            )

            # Combine with continuous observations (residual)
            combined_obs = batch.obs + 0.1 * multimodal_obs
        else:
            combined_obs = batch.obs

        # Run through RSSM
        key, rssm_key = jax.random.split(key)
        rssm_output = rssm_apply_fn(
            {"params": rssm_params},
            obs=combined_obs,
            actions=batch.actions,
            rewards=batch.rewards,
            continues=batch.continues,
            key=rssm_key,
            training=training,
        )

        return MultimodalOutput(
            h=rssm_output["h"],
            z=rssm_output["z"],
            obs_pred=rssm_output["obs_pred"],
            reward_pred=rssm_output["reward_pred"],
            continue_pred=rssm_output["continue_pred"],
            kl_balanced=rssm_output["kl_balanced"],
            kl_raw=rssm_output["kl_raw"],
            video_output=video_output,
            audio_output=audio_output,
            action_output=action_output,
            z_fused=z_fused,
        )


# =============================================================================
# MULTIMODAL LOSS COMPUTATION
# =============================================================================


def compute_multimodal_loss(
    output: MultimodalOutput,
    batch: MultimodalBatch,
    config: MultimodalConfig,
    weights: dict[str, float] | None = None,
) -> tuple[jnp.ndarray, dict[str, jnp.ndarray]]:
    """Compute full multimodal training loss.

    Combines:
    - RSSM losses (recon, KL, reward, continue, H-JEPA)
    - Video tokenizer losses (recon, commitment, codebook)
    - Audio encoder losses (commitment)
    - Latent action model losses (entropy)
    - Cross-modal alignment losses (contrastive)

    Args:
        output: MultimodalOutput from forward pass
        batch: MultimodalBatch with targets
        config: MultimodalConfig
        weights: Optional loss weights

    Returns:
        total_loss: Scalar total loss
        metrics: Dict of all loss components
    """
    weights = weights or {
        "recon": 1.0,
        "kl": 0.5,
        "reward": 0.5,
        "continue": 0.1,
        "video": 0.1,
        "audio": 0.05,
        "lam": 0.01,
        "contrastive": 0.1,
    }

    metrics = {}
    total_loss = jnp.array(0.0)

    # ===== RSSM Losses =====

    # Reconstruction
    recon_loss = jnp.mean((output.obs_pred - batch.obs) ** 2)
    total_loss = total_loss + weights["recon"] * recon_loss
    metrics["recon_loss"] = recon_loss

    # KL
    kl_loss = output.kl_balanced
    total_loss = total_loss + weights["kl"] * kl_loss
    metrics["kl_loss"] = kl_loss
    metrics["kl_raw"] = output.kl_raw

    # Reward (if rewards in batch)
    if batch.rewards is not None:
        # TwoHot cross-entropy would go here
        # For now, simplified MSE
        reward_pred_mean = jnp.mean(output.reward_pred, axis=-1)  # Simplify logits
        reward_loss = jnp.mean((reward_pred_mean - batch.rewards) ** 2)
        total_loss = total_loss + weights["reward"] * reward_loss
        metrics["reward_loss"] = reward_loss

    # Continue
    continue_pred = output.continue_pred.squeeze(-1)
    continue_loss = jnp.mean(
        -batch.continues * jnp.log(jax.nn.sigmoid(continue_pred) + 1e-8)
        - (1 - batch.continues) * jnp.log(1 - jax.nn.sigmoid(continue_pred) + 1e-8)
    )
    total_loss = total_loss + weights["continue"] * continue_loss
    metrics["continue_loss"] = continue_loss

    # ===== Video Losses =====

    if output.video_output is not None and batch.video is not None:
        video_loss, video_metrics = compute_video_tokenizer_loss(
            output.video_output, batch.video, config.video_config
        )
        total_loss = total_loss + weights["video"] * video_loss
        metrics.update(video_metrics)

    # ===== Audio Losses =====

    if output.audio_output is not None and output.audio_output.commitment_loss is not None:
        audio_loss = output.audio_output.commitment_loss
        total_loss = total_loss + weights["audio"] * audio_loss
        metrics["audio_commitment_loss"] = audio_loss

    # ===== Latent Action Model Losses =====

    if output.action_output is not None and output.video_output is not None:
        lam_loss, lam_metrics = compute_lam_loss(output.action_output, output.video_output.z_q)
        total_loss = total_loss + weights["lam"] * lam_loss
        metrics.update(lam_metrics)

    # ===== Total =====

    metrics["total_loss"] = total_loss

    return total_loss, metrics


# =============================================================================
# FACTORY
# =============================================================================


def create_multimodal_world_model(
    config: MultimodalConfig | None = None,
    rssm_config: Any = None,
) -> MultimodalWorldModel:
    """Factory function for multimodal world model.

    Args:
        config: MultimodalConfig
        rssm_config: OrganismRSSMConfig

    Returns:
        MultimodalWorldModel instance
    """
    if config is None:
        config = MultimodalConfig()

    if rssm_config is None:
        # Import here to avoid circular
        from .config import OrganismRSSMConfig

        rssm_config = OrganismRSSMConfig()

    return MultimodalWorldModel(config=config, rssm_config=rssm_config)


__all__ = [
    "CrossModalAttention",
    "MultimodalBatch",
    "MultimodalConfig",
    "MultimodalFusion",
    "MultimodalOutput",
    "MultimodalWorldModel",
    "compute_multimodal_loss",
    "create_multimodal_world_model",
]
