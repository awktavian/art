"""JAX Generation Module — Full Video and Audio Generation.

This module provides GENERATION capabilities (not just encoding):
1. Autoregressive video generation (frame-by-frame from world model)
2. Audio generation (latents → waveform via neural vocoder)
3. Text generation (from world model state)

Architecture:
=============
```
World Model (RSSM) State
         │
         ├──────────────────────────────────────────────────────┐
         │                                                      │
         ▼                                                      ▼
┌─────────────────────┐                               ┌─────────────────────┐
│ Video Dynamics      │                               │ Audio Decoder       │
│ (Autoregressive)    │                               │ (HiFi-GAN style)    │
│                     │                               │                     │
│ h_t + a_t → z_{t+1} │                               │ z_audio → waveform  │
│ z_{t+1} → frame     │                               │                     │
└─────────────────────┘                               └─────────────────────┘
         │                                                      │
         ▼                                                      ▼
   Generated Video                                        Generated Audio
   [B, T, H, W, C]                                        [B, samples]
```

References:
- Genie 2/3: Autoregressive world models (DeepMind 2024-2025)
- HiFi-GAN: High-fidelity neural vocoder (Kong et al. 2020)
- SoundStream: Neural audio codec (Zeghidour et al. 2021)
- WaveNet: Autoregressive audio (van den Oord et al. 2016)

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
class VideoGeneratorConfig:
    """Configuration for video generation."""

    # Latent dimensions
    latent_dim: int = 512
    hidden_dim: int = 512

    # Frame dimensions
    frame_height: int = 224
    frame_width: int = 224
    frame_channels: int = 3

    # Temporal
    patch_size: int = 16
    temporal_patch: int = 4

    # Dynamics model
    num_dynamics_layers: int = 6
    num_heads: int = 8

    # Action conditioning
    action_dim: int = 256  # Latent action dimension
    action_vocab_size: int = 256

    # Generation
    temperature: float = 1.0
    top_k: int = 0  # 0 = disabled
    top_p: float = 0.9  # Nucleus sampling

    # Decoder
    decoder_dim: int = 512
    decoder_layers: int = 6


@dataclass(frozen=True)
class AudioGeneratorConfig:
    """Configuration for audio generation (HiFi-GAN style)."""

    # Input
    latent_dim: int = 512
    mel_channels: int = 128

    # Generator architecture
    upsample_rates: tuple[int, ...] = (8, 8, 2, 2)  # Total: 256x
    upsample_kernel_sizes: tuple[int, ...] = (16, 16, 4, 4)
    upsample_initial_channel: int = 512

    # Residual blocks
    resblock_kernel_sizes: tuple[int, ...] = (3, 7, 11)
    resblock_dilation_sizes: tuple[tuple[int, ...], ...] = (
        (1, 3, 5),
        (1, 3, 5),
        (1, 3, 5),
    )

    # Output
    sample_rate: int = 16000
    hop_length: int = 160  # Must match encoder

    # Training
    segment_length: int = 8192


@dataclass(frozen=True)
class GenerationConfig:
    """Unified generation configuration."""

    video_config: VideoGeneratorConfig = None
    audio_config: AudioGeneratorConfig = None

    # World model integration
    rssm_hidden_dim: int = 384
    num_colonies: int = 7

    # Generation settings
    max_video_frames: int = 64
    max_audio_seconds: float = 10.0

    def __post_init__(self):
        if self.video_config is None:
            object.__setattr__(self, "video_config", VideoGeneratorConfig())
        if self.audio_config is None:
            object.__setattr__(self, "audio_config", AudioGeneratorConfig())


# =============================================================================
# OUTPUT TYPES
# =============================================================================


class VideoGenerationOutput(NamedTuple):
    """Output from video generation."""

    frames: jnp.ndarray  # [B, T, H, W, C] generated video
    latents: jnp.ndarray  # [B, T, D] frame latents
    actions: jnp.ndarray  # [B, T-1] action indices used


class AudioGenerationOutput(NamedTuple):
    """Output from audio generation."""

    waveform: jnp.ndarray  # [B, samples] generated audio
    spectrogram: jnp.ndarray  # [B, T, mel_channels] mel spectrogram


class GenerationOutput(NamedTuple):
    """Combined generation output."""

    video: VideoGenerationOutput | None
    audio: AudioGenerationOutput | None


# =============================================================================
# VIDEO DYNAMICS MODEL
# =============================================================================


class VideoDynamicsModel(nn.Module):
    """Autoregressive dynamics model for video generation.

    Predicts the next frame latent given:
    - Current frame latent z_t
    - Action a_t
    - World model hidden state h_t

    This enables controllable video generation.
    """

    config: VideoGeneratorConfig

    @nn.compact
    def __call__(
        self,
        z_t: jnp.ndarray,
        action: jnp.ndarray,
        h_t: jnp.ndarray | None = None,
        training: bool = True,
    ) -> jnp.ndarray:
        """Predict next frame latent.

        Args:
            z_t: [B, D] current frame latent
            action: [B, action_dim] or [B] action indices
            h_t: [B, D] optional world model hidden state
            training: Whether in training mode

        Returns:
            z_next: [B, D] predicted next frame latent
        """
        cfg = self.config
        _B = z_t.shape[0]  # Batch size (for documentation)

        # Process action (embed if discrete)
        if action.ndim == 1 or action.shape[-1] == 1:
            # Discrete action - embed
            action_emb = nn.Embed(
                num_embeddings=cfg.action_vocab_size,
                features=cfg.action_dim,
                name="action_embed",
            )(action.astype(jnp.int32).reshape(-1))
        else:
            # Continuous action - project
            action_emb = nn.Dense(cfg.action_dim, name="action_proj")(action)

        # Combine inputs
        if h_t is not None:
            h_proj = nn.Dense(cfg.hidden_dim, name="h_proj")(h_t)
            combined = jnp.concatenate([z_t, action_emb, h_proj], axis=-1)
        else:
            combined = jnp.concatenate([z_t, action_emb], axis=-1)

        # Initial projection
        x = nn.Dense(cfg.hidden_dim, name="input_proj")(combined)
        x = nn.LayerNorm(name="input_ln")(x)

        # Transformer layers for dynamics
        for i in range(cfg.num_dynamics_layers):
            # Self-attention (single token, so it's just a nonlinearity + mixing)
            x_norm = nn.LayerNorm(name=f"ln1_{i}")(x)

            # MLP instead of attention for single token
            h = nn.Dense(cfg.hidden_dim * 4, name=f"mlp1_{i}")(x_norm)
            h = jax.nn.gelu(h)
            h = nn.Dense(cfg.hidden_dim, name=f"mlp2_{i}")(h)
            if training:
                h = nn.Dropout(rate=0.1)(h, deterministic=False)
            x = x + h

        # Output projection
        x = nn.LayerNorm(name="output_ln")(x)
        z_next = nn.Dense(cfg.latent_dim, name="output_proj")(x)

        return z_next


class VideoFrameDecoder(nn.Module):
    """Decodes latent to video frame.

    Takes a latent vector and produces a full-resolution frame.
    Uses a transformer decoder with learned queries.
    """

    config: VideoGeneratorConfig

    @nn.compact
    def __call__(
        self,
        z: jnp.ndarray,
        training: bool = True,
    ) -> jnp.ndarray:
        """Decode latent to frame.

        Args:
            z: [B, D] frame latent
            training: Whether in training mode

        Returns:
            frame: [B, H, W, C] decoded frame
        """
        cfg = self.config
        B = z.shape[0]

        # Calculate spatial dimensions
        H_patches = cfg.frame_height // cfg.patch_size
        W_patches = cfg.frame_width // cfg.patch_size
        num_patches = H_patches * W_patches

        # Learned patch queries
        queries = self.param(
            "patch_queries",
            nn.initializers.normal(0.02),
            (1, num_patches, cfg.decoder_dim),
        )
        queries = jnp.broadcast_to(queries, (B, num_patches, cfg.decoder_dim))

        # Add positional encoding
        pos_h = self.param(
            "pos_h", nn.initializers.normal(0.02), (1, H_patches, 1, cfg.decoder_dim)
        )
        pos_w = self.param(
            "pos_w", nn.initializers.normal(0.02), (1, 1, W_patches, cfg.decoder_dim)
        )
        pos_enc = (pos_h + pos_w).reshape(1, num_patches, cfg.decoder_dim)
        queries = queries + pos_enc

        # Project latent for cross-attention
        z_proj = nn.Dense(cfg.decoder_dim, name="z_proj")(z)[:, None, :]  # [B, 1, D]

        # Decoder transformer
        x = queries
        for i in range(cfg.decoder_layers):
            # Self-attention
            x_norm = nn.LayerNorm(name=f"dec_ln1_{i}")(x)
            attn = nn.MultiHeadDotProductAttention(
                num_heads=cfg.num_heads,
                qkv_features=cfg.decoder_dim,
                deterministic=not training,
                name=f"dec_self_attn_{i}",
            )(x_norm, x_norm)
            x = x + attn

            # Cross-attention to latent
            x_norm = nn.LayerNorm(name=f"dec_ln2_{i}")(x)
            cross_attn = nn.MultiHeadDotProductAttention(
                num_heads=cfg.num_heads,
                qkv_features=cfg.decoder_dim,
                deterministic=not training,
                name=f"dec_cross_attn_{i}",
            )(x_norm, z_proj)
            x = x + cross_attn

            # FFN
            x_norm = nn.LayerNorm(name=f"dec_ln3_{i}")(x)
            ffn = nn.Dense(cfg.decoder_dim * 4, name=f"dec_ffn1_{i}")(x_norm)
            ffn = jax.nn.gelu(ffn)
            ffn = nn.Dense(cfg.decoder_dim, name=f"dec_ffn2_{i}")(ffn)
            x = x + ffn

        # Final projection to pixels
        x = nn.LayerNorm(name="dec_ln_final")(x)
        patch_pixels = cfg.patch_size * cfg.patch_size * cfg.frame_channels
        x = nn.Dense(patch_pixels, name="to_pixels")(x)

        # Reshape to image
        x = x.reshape(B, H_patches, W_patches, cfg.patch_size, cfg.patch_size, cfg.frame_channels)
        x = x.transpose(0, 1, 3, 2, 4, 5)  # [B, H', p, W', p, C]
        frame = x.reshape(B, cfg.frame_height, cfg.frame_width, cfg.frame_channels)

        # Sigmoid to [0, 1]
        frame = jax.nn.sigmoid(frame)

        return frame


class VideoGenerator(nn.Module):
    """Complete video generation module.

    Generates video frames autoregressively:
    1. Start from initial latent z_0
    2. Predict z_{t+1} using dynamics model
    3. Decode z_{t+1} to frame
    4. Repeat for desired length
    """

    config: VideoGeneratorConfig

    def setup(self):
        self.dynamics = VideoDynamicsModel(self.config)
        self.decoder = VideoFrameDecoder(self.config)

    def __call__(
        self,
        z_init: jnp.ndarray,
        actions: jnp.ndarray,
        h_sequence: jnp.ndarray | None = None,
        training: bool = True,
    ) -> VideoGenerationOutput:
        """Generate video from initial latent and actions.

        Args:
            z_init: [B, D] initial frame latent
            actions: [B, T-1] or [B, T-1, action_dim] actions
            h_sequence: [B, T, D] optional world model hidden states
            training: Whether in training mode

        Returns:
            VideoGenerationOutput
        """
        _B = z_init.shape[0]  # Batch size (for documentation)
        T = actions.shape[1] + 1  # T frames from T-1 actions

        # Generate frames autoregressively
        latents = [z_init]
        z_t = z_init

        for t in range(T - 1):
            action_t = actions[:, t]
            h_t = h_sequence[:, t] if h_sequence is not None else None

            z_next = self.dynamics(z_t, action_t, h_t, training=training)
            latents.append(z_next)
            z_t = z_next

        # Stack latents
        latents = jnp.stack(latents, axis=1)  # [B, T, D]

        # Decode all frames
        frames = []
        for t in range(T):
            frame = self.decoder(latents[:, t], training=training)
            frames.append(frame)

        frames = jnp.stack(frames, axis=1)  # [B, T, H, W, C]

        return VideoGenerationOutput(
            frames=frames,
            latents=latents,
            actions=actions,
        )

    def generate_single_frame(
        self,
        z: jnp.ndarray,
        training: bool = False,
    ) -> jnp.ndarray:
        """Decode single frame from latent."""
        return self.decoder(z, training=training)

    def step(
        self,
        z_t: jnp.ndarray,
        action: jnp.ndarray,
        h_t: jnp.ndarray | None = None,
    ) -> jnp.ndarray:
        """Single dynamics step (for inference)."""
        return self.dynamics(z_t, action, h_t, training=False)


# =============================================================================
# AUDIO GENERATOR (HiFi-GAN Style)
# =============================================================================


class ResBlock(nn.Module):
    """Residual block for HiFi-GAN generator."""

    channels: int
    kernel_size: int = 3
    dilation: tuple[int, ...] = (1, 3, 5)

    @nn.compact
    def __call__(self, x: jnp.ndarray) -> jnp.ndarray:
        """Apply residual block with multiple dilations."""
        for d in self.dilation:
            residual = x
            x = nn.leaky_relu(x, negative_slope=0.1)
            x = nn.Conv(
                features=self.channels,
                kernel_size=(self.kernel_size,),
                kernel_dilation=(d,),
                padding="SAME",
            )(x)
            x = nn.leaky_relu(x, negative_slope=0.1)
            x = nn.Conv(
                features=self.channels,
                kernel_size=(self.kernel_size,),
                padding="SAME",
            )(x)
            x = x + residual
        return x


class AudioDecoder(nn.Module):
    """HiFi-GAN style audio decoder.

    Converts mel spectrogram (or latent) to raw waveform.
    Uses transposed convolutions for upsampling with residual blocks.
    """

    config: AudioGeneratorConfig

    @nn.compact
    def __call__(
        self,
        x: jnp.ndarray,
        training: bool = True,
    ) -> jnp.ndarray:
        """Decode to waveform.

        Args:
            x: [B, T, mel_channels] mel spectrogram or [B, T, D] latents
            training: Whether in training mode

        Returns:
            waveform: [B, samples] audio waveform
        """
        cfg = self.config

        # Initial projection
        x = nn.Conv(
            features=cfg.upsample_initial_channel,
            kernel_size=(7,),
            padding="SAME",
            name="pre_conv",
        )(x)

        # Upsample blocks
        channels = cfg.upsample_initial_channel
        for i, (rate, kernel) in enumerate(
            zip(cfg.upsample_rates, cfg.upsample_kernel_sizes, strict=False)
        ):
            channels = channels // 2

            x = nn.leaky_relu(x, negative_slope=0.1)
            x = nn.ConvTranspose(
                features=channels,
                kernel_size=(kernel,),
                strides=(rate,),
                padding="SAME",
                name=f"upsample_{i}",
            )(x)

            # Residual blocks with different kernel sizes and dilations
            xs = None
            for j, (k, d) in enumerate(
                zip(cfg.resblock_kernel_sizes, cfg.resblock_dilation_sizes, strict=False)
            ):
                if xs is None:
                    xs = ResBlock(channels, k, d, name=f"resblock_{i}_{j}")(x)
                else:
                    xs = xs + ResBlock(channels, k, d, name=f"resblock_{i}_{j}")(x)
            x = xs / len(cfg.resblock_kernel_sizes)

        # Final conv to waveform
        x = nn.leaky_relu(x, negative_slope=0.1)
        x = nn.Conv(
            features=1,
            kernel_size=(7,),
            padding="SAME",
            name="post_conv",
        )(x)
        x = jnp.tanh(x)

        # Squeeze channel dimension
        waveform = x.squeeze(-1)  # [B, samples]

        return waveform


class AudioGenerator(nn.Module):
    """Complete audio generation module.

    Can generate audio from:
    1. Mel spectrogram (vocoder mode)
    2. Latent vectors (generative mode)
    3. World model hidden states
    """

    config: AudioGeneratorConfig

    def setup(self):
        self.decoder = AudioDecoder(self.config)
        self.latent_to_mel = nn.Dense(self.config.mel_channels, name="latent_to_mel")

    def __call__(
        self,
        x: jnp.ndarray,
        mode: str = "mel",
        training: bool = True,
    ) -> AudioGenerationOutput:
        """Generate audio.

        Args:
            x: Input tensor
               - If mode="mel": [B, T, mel_channels] mel spectrogram
               - If mode="latent": [B, T, D] latent sequence
            mode: "mel" or "latent"
            training: Whether in training mode

        Returns:
            AudioGenerationOutput
        """
        if mode == "latent":
            # Convert latent to mel-like representation
            spectrogram = self.latent_to_mel(x)
        else:
            spectrogram = x

        # Decode to waveform
        waveform = self.decoder(spectrogram, training=training)

        return AudioGenerationOutput(
            waveform=waveform,
            spectrogram=spectrogram,
        )

    def from_mel(
        self,
        mel: jnp.ndarray,
        training: bool = False,
    ) -> jnp.ndarray:
        """Vocode mel spectrogram to waveform."""
        return self.decoder(mel, training=training)

    def from_latent(
        self,
        latent: jnp.ndarray,
        training: bool = False,
    ) -> jnp.ndarray:
        """Generate waveform from latent."""
        mel = self.latent_to_mel(latent)
        return self.decoder(mel, training=training)


# =============================================================================
# UNIFIED GENERATOR
# =============================================================================


class UnifiedGenerator(nn.Module):
    """Unified video and audio generator.

    Integrates with world model for full generative capabilities:
    - Generate video frames from world model predictions
    - Generate audio from world model states
    - Controllable via actions
    """

    config: GenerationConfig

    def setup(self):
        self.video_generator = VideoGenerator(self.config.video_config)
        self.audio_generator = AudioGenerator(self.config.audio_config)

        # Project from world model hidden states
        self.h_to_video_latent = nn.Dense(
            self.config.video_config.latent_dim,
            name="h_to_video",
        )
        self.h_to_audio_latent = nn.Dense(
            self.config.audio_config.latent_dim,
            name="h_to_audio",
        )

    def generate_video(
        self,
        h_sequence: jnp.ndarray,
        actions: jnp.ndarray,
        training: bool = False,
    ) -> VideoGenerationOutput:
        """Generate video from world model hidden states.

        Args:
            h_sequence: [B, T, D] world model hidden states
            actions: [B, T-1] or [B, T-1, action_dim] actions
            training: Whether in training mode

        Returns:
            VideoGenerationOutput
        """
        # Project to video latent space
        z_init = self.h_to_video_latent(h_sequence[:, 0])

        return self.video_generator(z_init, actions, h_sequence, training=training)

    def generate_audio(
        self,
        h_sequence: jnp.ndarray,
        training: bool = False,
    ) -> AudioGenerationOutput:
        """Generate audio from world model hidden states.

        Args:
            h_sequence: [B, T, D] world model hidden states
            training: Whether in training mode

        Returns:
            AudioGenerationOutput
        """
        # Project to audio latent space
        audio_latent = self.h_to_audio_latent(h_sequence)

        return self.audio_generator(audio_latent, mode="latent", training=training)

    def generate_both(
        self,
        h_sequence: jnp.ndarray,
        actions: jnp.ndarray,
        training: bool = False,
    ) -> GenerationOutput:
        """Generate both video and audio.

        Args:
            h_sequence: [B, T, D] world model hidden states
            actions: [B, T-1] action sequence
            training: Whether in training mode

        Returns:
            GenerationOutput with video and audio
        """
        video_output = self.generate_video(h_sequence, actions, training=training)
        audio_output = self.generate_audio(h_sequence, training=training)

        return GenerationOutput(video=video_output, audio=audio_output)


# =============================================================================
# GENERATION LOSSES
# =============================================================================


def compute_video_generation_loss(
    output: VideoGenerationOutput,
    target_frames: jnp.ndarray,
    config: VideoGeneratorConfig,
) -> tuple[jnp.ndarray, dict[str, jnp.ndarray]]:
    """Compute video generation loss.

    Args:
        output: VideoGenerationOutput
        target_frames: [B, T, H, W, C] ground truth frames
        config: VideoGeneratorConfig

    Returns:
        loss: Scalar loss
        metrics: Dict of metrics
    """
    # L1 + L2 reconstruction
    l1_loss = jnp.mean(jnp.abs(output.frames - target_frames))
    l2_loss = jnp.mean((output.frames - target_frames) ** 2)

    # Perceptual loss would go here (requires pretrained encoder)

    total_loss = l1_loss + 0.5 * l2_loss

    metrics = {
        "video_gen_l1": l1_loss,
        "video_gen_l2": l2_loss,
        "video_gen_total": total_loss,
    }

    return total_loss, metrics


def compute_audio_generation_loss(
    output: AudioGenerationOutput,
    target_waveform: jnp.ndarray,
    target_mel: jnp.ndarray,
    config: AudioGeneratorConfig,
) -> tuple[jnp.ndarray, dict[str, jnp.ndarray]]:
    """Compute audio generation loss.

    HiFi-GAN uses:
    - L1 mel spectrogram loss
    - Multi-scale discriminator (not implemented here)
    - Feature matching loss (not implemented here)

    Args:
        output: AudioGenerationOutput
        target_waveform: [B, samples] ground truth waveform
        target_mel: [B, T, mel] ground truth mel spectrogram
        config: AudioGeneratorConfig

    Returns:
        loss: Scalar loss
        metrics: Dict of metrics
    """
    # Waveform L1
    waveform_l1 = jnp.mean(jnp.abs(output.waveform - target_waveform))

    # Mel spectrogram L1
    mel_l1 = jnp.mean(jnp.abs(output.spectrogram - target_mel))

    total_loss = waveform_l1 + 45 * mel_l1  # HiFi-GAN weighting

    metrics = {
        "audio_gen_waveform_l1": waveform_l1,
        "audio_gen_mel_l1": mel_l1,
        "audio_gen_total": total_loss,
    }

    return total_loss, metrics


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================


def create_video_generator(
    config: VideoGeneratorConfig | None = None,
) -> VideoGenerator:
    """Create video generator."""
    if config is None:
        config = VideoGeneratorConfig()
    return VideoGenerator(config)


def create_audio_generator(
    config: AudioGeneratorConfig | None = None,
) -> AudioGenerator:
    """Create audio generator."""
    if config is None:
        config = AudioGeneratorConfig()
    return AudioGenerator(config)


def create_unified_generator(
    config: GenerationConfig | None = None,
) -> UnifiedGenerator:
    """Create unified generator."""
    if config is None:
        config = GenerationConfig()
    return UnifiedGenerator(config)


__all__ = [
    # Configs
    "VideoGeneratorConfig",
    "AudioGeneratorConfig",
    "GenerationConfig",
    # Outputs
    "VideoGenerationOutput",
    "AudioGenerationOutput",
    "GenerationOutput",
    # Video
    "VideoDynamicsModel",
    "VideoFrameDecoder",
    "VideoGenerator",
    # Audio
    "ResBlock",
    "AudioDecoder",
    "AudioGenerator",
    # Unified
    "UnifiedGenerator",
    # Losses
    "compute_video_generation_loss",
    "compute_audio_generation_loss",
    # Factories
    "create_video_generator",
    "create_audio_generator",
    "create_unified_generator",
]
