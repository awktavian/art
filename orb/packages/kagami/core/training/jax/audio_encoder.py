"""JAX Audio Encoder — Spectrogram-based Audio Understanding.

Implements audio encoding for multimodal world model:
1. Mel-spectrogram extraction (from raw audio)
2. Audio transformer encoder (AST-style)
3. VQ-VAE tokenization for discrete audio tokens
4. Audio-visual alignment for cross-modal learning

Architecture (Inspired by AudioMAE, AST, SoundStream):
======================================================
```
Audio [B, samples]
       │
       ▼
┌─────────────────────────────────────┐
│ Mel-Spectrogram Extraction          │
│ (n_mels=128, hop=160, n_fft=400)   │
└─────────────────────────────────────┘
       │
       ▼
    Spectrogram [B, T, n_mels]
       │
       ▼
┌─────────────────────────────────────┐
│ Patch Embedding (16x16 patches)     │
└─────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│ Audio Transformer (AST)             │
│ 12 layers, 768 dim, 12 heads        │
└─────────────────────────────────────┘
       │
       ▼
    Audio Embeddings [B, N, D]
       │
       ▼
┌─────────────────────────────────────┐
│ Vector Quantizer (optional)         │
│ 1024 codes for discrete tokens     │
└─────────────────────────────────────┘
       │
       ▼
    Discrete Audio Tokens [B, N]
```

References:
- AST: Audio Spectrogram Transformer (Gong et al. 2021)
- AudioMAE: Masked Audio Encoders (Huang et al. 2022)
- SoundStream: End-to-End Neural Audio Codec (Zeghidour et al. 2021)
- Whisper: Robust Speech Recognition (Radford et al. 2022)

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
class AudioEncoderConfig:
    """Configuration for audio encoder.

    frozen=True for JAX static_argnums compatibility.
    """

    # Audio processing
    sample_rate: int = 16000  # Audio sample rate
    n_fft: int = 400  # FFT window size
    hop_length: int = 160  # Hop between windows (10ms at 16kHz)
    n_mels: int = 128  # Number of mel bands

    # Spectrogram settings
    max_audio_length: int = 160000  # 10 seconds at 16kHz
    spec_height: int = 128  # Mel bands
    spec_width: int = 1000  # Time frames (10s / 10ms = 1000)

    # Patch embedding
    patch_height: int = 16  # Frequency patches
    patch_width: int = 16  # Time patches

    # Transformer architecture
    hidden_dim: int = 768
    num_layers: int = 12
    num_heads: int = 12
    mlp_dim: int = 3072
    dropout: float = 0.1

    # Output
    output_dim: int = 512  # Final embedding dimension

    # VQ-VAE tokenization (optional)
    use_vq: bool = True
    codebook_size: int = 1024
    codebook_dim: int = 256
    commitment_cost: float = 0.25


# =============================================================================
# OUTPUT TYPES
# =============================================================================


class AudioEncoderOutput(NamedTuple):
    """Output from audio encoder."""

    embeddings: jnp.ndarray  # [B, N, D] audio embeddings
    pooled: jnp.ndarray  # [B, D] pooled (CLS) embedding
    tokens: jnp.ndarray | None  # [B, N] discrete tokens if VQ enabled
    commitment_loss: jnp.ndarray | None  # VQ commitment loss
    spectrogram: jnp.ndarray  # [B, T, F] mel spectrogram


# =============================================================================
# MEL SPECTROGRAM (JAX-native)
# =============================================================================


def create_mel_filterbank(
    sample_rate: int,
    n_fft: int,
    n_mels: int,
    fmin: float = 0.0,
    fmax: float | None = None,
) -> jnp.ndarray:
    """Create mel filterbank matrix.

    Args:
        sample_rate: Audio sample rate
        n_fft: FFT window size
        n_mels: Number of mel bands
        fmin: Minimum frequency
        fmax: Maximum frequency

    Returns:
        [n_mels, n_fft//2 + 1] filterbank matrix
    """
    if fmax is None:
        fmax = sample_rate / 2

    # Mel scale conversion
    def hz_to_mel(hz):
        return 2595 * jnp.log10(1 + hz / 700)

    def mel_to_hz(mel):
        return 700 * (10 ** (mel / 2595) - 1)

    # Mel points
    mel_min = hz_to_mel(fmin)
    mel_max = hz_to_mel(fmax)
    mel_points = jnp.linspace(mel_min, mel_max, n_mels + 2)
    hz_points = mel_to_hz(mel_points)

    # FFT bins
    n_bins = n_fft // 2 + 1
    fft_freqs = jnp.linspace(0, sample_rate / 2, n_bins)

    # Create filterbank
    filterbank = jnp.zeros((n_mels, n_bins))

    for i in range(n_mels):
        # Triangle filter
        low = hz_points[i]
        center = hz_points[i + 1]
        high = hz_points[i + 2]

        # Rising edge
        rising = (fft_freqs - low) / (center - low + 1e-10)
        rising = jnp.where(fft_freqs < low, 0.0, rising)
        rising = jnp.where(fft_freqs > center, 0.0, rising)

        # Falling edge
        falling = (high - fft_freqs) / (high - center + 1e-10)
        falling = jnp.where(fft_freqs < center, 0.0, falling)
        falling = jnp.where(fft_freqs > high, 0.0, falling)

        filterbank = filterbank.at[i].set(rising + falling)

    return filterbank


def compute_mel_spectrogram(
    audio: jnp.ndarray,
    config: AudioEncoderConfig,
    mel_filterbank: jnp.ndarray,
) -> jnp.ndarray:
    """Compute mel spectrogram from audio.

    Args:
        audio: [B, samples] raw audio
        config: AudioEncoderConfig
        mel_filterbank: [n_mels, n_bins] filterbank

    Returns:
        [B, T, n_mels] mel spectrogram (log scale)
    """
    _B = audio.shape[0]  # Batch size (for documentation)

    # Pad/truncate to fixed length
    target_len = config.max_audio_length
    if audio.shape[1] < target_len:
        audio = jnp.pad(audio, ((0, 0), (0, target_len - audio.shape[1])))
    else:
        audio = audio[:, :target_len]

    # Frame audio
    num_frames = (target_len - config.n_fft) // config.hop_length + 1

    # Create frames using strided indexing
    indices = (
        jnp.arange(config.n_fft)[None, :] + jnp.arange(num_frames)[:, None] * config.hop_length
    )
    frames = audio[:, indices]  # [B, num_frames, n_fft]

    # Apply Hann window
    window = jnp.hanning(config.n_fft)
    frames = frames * window[None, None, :]

    # FFT
    spectrum = jnp.fft.rfft(frames, n=config.n_fft, axis=-1)
    magnitude = jnp.abs(spectrum)  # [B, num_frames, n_bins]

    # Apply mel filterbank
    mel_spec = jnp.einsum("btf,mf->btm", magnitude**2, mel_filterbank)

    # Log scale
    mel_spec = jnp.log(mel_spec + 1e-10)

    # Normalize
    mel_spec = (mel_spec - jnp.mean(mel_spec)) / (jnp.std(mel_spec) + 1e-10)

    return mel_spec  # [B, T, n_mels]


# =============================================================================
# AUDIO TRANSFORMER
# =============================================================================


class AudioPatchEmbed(nn.Module):
    """Patch embedding for audio spectrogram.

    Converts spectrogram to sequence of patch embeddings.
    """

    config: AudioEncoderConfig

    @nn.compact
    def __call__(self, spec: jnp.ndarray) -> jnp.ndarray:
        """Embed spectrogram patches.

        Args:
            spec: [B, T, F] mel spectrogram

        Returns:
            [B, N, D] patch embeddings
        """
        cfg = self.config
        B, T, F = spec.shape

        # Reshape for patch extraction
        # Pad to divisible by patch size
        T_padded = ((T + cfg.patch_width - 1) // cfg.patch_width) * cfg.patch_width
        F_padded = ((F + cfg.patch_height - 1) // cfg.patch_height) * cfg.patch_height

        spec_padded = jnp.zeros((B, T_padded, F_padded))
        spec_padded = spec_padded.at[:, :T, :F].set(spec)

        # Extract patches
        n_patches_t = T_padded // cfg.patch_width
        n_patches_f = F_padded // cfg.patch_height

        spec_patches = spec_padded.reshape(
            B, n_patches_t, cfg.patch_width, n_patches_f, cfg.patch_height
        )
        spec_patches = spec_patches.transpose(0, 1, 3, 2, 4)  # [B, Nt, Nf, Pt, Pf]
        spec_patches = spec_patches.reshape(
            B, n_patches_t * n_patches_f, cfg.patch_width * cfg.patch_height
        )

        # Linear projection
        patches = nn.Dense(cfg.hidden_dim, name="patch_proj")(spec_patches)

        # Add CLS token
        cls_token = self.param(
            "cls_token",
            nn.initializers.normal(0.02),
            (1, 1, cfg.hidden_dim),
        )
        cls_tokens = jnp.broadcast_to(cls_token, (B, 1, cfg.hidden_dim))
        patches = jnp.concatenate([cls_tokens, patches], axis=1)

        # Add positional encoding
        num_patches = n_patches_t * n_patches_f + 1
        pos_embed = self.param(
            "pos_embed",
            nn.initializers.normal(0.02),
            (1, num_patches, cfg.hidden_dim),
        )
        patches = patches + pos_embed

        return patches


class AudioTransformerBlock(nn.Module):
    """Transformer block for audio processing."""

    config: AudioEncoderConfig

    @nn.compact
    def __call__(
        self,
        x: jnp.ndarray,
        training: bool = True,
    ) -> jnp.ndarray:
        """Apply transformer block.

        Args:
            x: [B, N, D] input embeddings
            training: Whether in training mode

        Returns:
            [B, N, D] output embeddings
        """
        cfg = self.config

        # Self-attention
        residual = x
        x = nn.LayerNorm(name="ln1")(x)
        x = nn.MultiHeadDotProductAttention(
            num_heads=cfg.num_heads,
            qkv_features=cfg.hidden_dim,
            out_features=cfg.hidden_dim,
            deterministic=not training,
            name="attn",
        )(x, x)
        if training:
            x = nn.Dropout(rate=cfg.dropout)(x, deterministic=False)
        x = residual + x

        # MLP
        residual = x
        x = nn.LayerNorm(name="ln2")(x)
        x = nn.Dense(cfg.mlp_dim, name="mlp1")(x)
        x = jax.nn.gelu(x)
        if training:
            x = nn.Dropout(rate=cfg.dropout)(x, deterministic=False)
        x = nn.Dense(cfg.hidden_dim, name="mlp2")(x)
        if training:
            x = nn.Dropout(rate=cfg.dropout)(x, deterministic=False)
        x = residual + x

        return x


class AudioTransformer(nn.Module):
    """Audio Spectrogram Transformer (AST-style).

    Processes mel spectrograms through a vision transformer-like architecture.
    """

    config: AudioEncoderConfig

    @nn.compact
    def __call__(
        self,
        spec: jnp.ndarray,
        training: bool = True,
    ) -> tuple[jnp.ndarray, jnp.ndarray]:
        """Process spectrogram through transformer.

        Args:
            spec: [B, T, F] mel spectrogram
            training: Whether in training mode

        Returns:
            embeddings: [B, N, D] all patch embeddings
            pooled: [B, D] CLS token embedding
        """
        cfg = self.config

        # Patch embedding
        x = AudioPatchEmbed(cfg, name="patch_embed")(spec)

        # Transformer blocks
        for i in range(cfg.num_layers):
            x = AudioTransformerBlock(cfg, name=f"block_{i}")(x, training=training)

        # Final layer norm
        x = nn.LayerNorm(name="ln_final")(x)

        # CLS token is pooled output
        pooled = x[:, 0]
        embeddings = x[:, 1:]  # Exclude CLS

        return embeddings, pooled


# =============================================================================
# AUDIO VQ-VAE
# =============================================================================


class AudioVectorQuantizer(nn.Module):
    """Vector quantizer for discrete audio tokens."""

    codebook_size: int = 1024
    codebook_dim: int = 256
    commitment_cost: float = 0.25

    @nn.compact
    def __call__(
        self,
        z_e: jnp.ndarray,
        training: bool = True,
    ) -> tuple[jnp.ndarray, jnp.ndarray, jnp.ndarray]:
        """Quantize audio embeddings.

        Args:
            z_e: [B, N, D] encoder output
            training: Whether in training mode

        Returns:
            z_q: Quantized output
            indices: Codebook indices
            commitment_loss: Commitment loss
        """
        # Codebook
        codebook = self.param(
            "codebook",
            nn.initializers.variance_scaling(1.0, "fan_in", "uniform"),
            (self.codebook_size, self.codebook_dim),
        )

        # Find nearest codes
        flat_z_e = z_e.reshape(-1, self.codebook_dim)

        distances = (
            jnp.sum(flat_z_e**2, axis=1, keepdims=True)
            + jnp.sum(codebook**2, axis=1)
            - 2 * jnp.matmul(flat_z_e, codebook.T)
        )

        indices = jnp.argmin(distances, axis=1)
        z_q = codebook[indices]
        z_q = z_q.reshape(z_e.shape)
        indices = indices.reshape(z_e.shape[:-1])

        # Commitment loss
        commitment_loss = jnp.mean((jax.lax.stop_gradient(z_q) - z_e) ** 2)

        # Straight-through
        z_q = z_e + jax.lax.stop_gradient(z_q - z_e)

        return z_q, indices, commitment_loss


# =============================================================================
# FULL AUDIO ENCODER
# =============================================================================


class AudioEncoder(nn.Module):
    """Complete audio encoder module.

    Converts raw audio to embeddings and optional discrete tokens.

    Usage:
        config = AudioEncoderConfig()
        encoder = AudioEncoder(config)

        # Encode audio
        output = encoder.apply(params, audio, mel_filterbank)

        # Get embeddings for fusion
        audio_emb = output.embeddings  # [B, N, D]

        # Or get discrete tokens
        audio_tokens = output.tokens  # [B, N]
    """

    config: AudioEncoderConfig

    def setup(self):
        """Initialize submodules."""
        self.transformer = AudioTransformer(self.config)
        self.output_proj = nn.Dense(self.config.output_dim, name="output_proj")

        if self.config.use_vq:
            self.pre_vq_proj = nn.Dense(self.config.codebook_dim, name="pre_vq")
            self.vq = AudioVectorQuantizer(
                codebook_size=self.config.codebook_size,
                codebook_dim=self.config.codebook_dim,
                commitment_cost=self.config.commitment_cost,
            )

    def __call__(
        self,
        audio: jnp.ndarray,
        mel_filterbank: jnp.ndarray,
        training: bool = True,
    ) -> AudioEncoderOutput:
        """Encode audio to embeddings.

        Args:
            audio: [B, samples] raw audio
            mel_filterbank: [n_mels, n_bins] precomputed filterbank
            training: Whether in training mode

        Returns:
            AudioEncoderOutput
        """
        cfg = self.config

        # Compute mel spectrogram
        spec = compute_mel_spectrogram(audio, cfg, mel_filterbank)

        # Process through transformer
        embeddings, pooled = self.transformer(spec, training=training)

        # Project to output dimension
        embeddings = self.output_proj(embeddings)
        pooled = self.output_proj(pooled)

        # Optional VQ tokenization
        if cfg.use_vq:
            z_pre_vq = self.pre_vq_proj(embeddings)
            z_q, tokens, commitment_loss = self.vq(z_pre_vq, training=training)
        else:
            tokens = None
            commitment_loss = None

        return AudioEncoderOutput(
            embeddings=embeddings,
            pooled=pooled,
            tokens=tokens,
            commitment_loss=commitment_loss,
            spectrogram=spec,
        )


# =============================================================================
# LOSS COMPUTATION
# =============================================================================


def compute_audio_encoder_loss(
    output: AudioEncoderOutput,
    target_audio: jnp.ndarray,
    config: AudioEncoderConfig,
    mel_filterbank: jnp.ndarray,
) -> tuple[jnp.ndarray, dict[str, jnp.ndarray]]:
    """Compute audio encoder training loss.

    For a VAE-style encoder, we use spectrogram reconstruction.

    Args:
        output: AudioEncoderOutput
        target_audio: [B, samples] target audio
        config: AudioEncoderConfig
        mel_filterbank: [n_mels, n_bins] filterbank

    Returns:
        loss: Scalar loss
        metrics: Dict of loss components
    """
    # Compute target spectrogram (placeholder for reconstruction loss)
    _target_spec = compute_mel_spectrogram(target_audio, config, mel_filterbank)

    # Spectrogram reconstruction loss (from embeddings)
    # In practice, you'd have a decoder here
    # For now, just use VQ commitment loss

    metrics = {
        "audio_commitment_loss": output.commitment_loss if output.commitment_loss else 0.0,
    }

    total_loss = output.commitment_loss if output.commitment_loss else jnp.array(0.0)

    return total_loss, metrics


# =============================================================================
# AUDIO-VISUAL ALIGNMENT
# =============================================================================


class AudioVisualAligner(nn.Module):
    """Aligns audio and visual embeddings for cross-modal learning.

    Uses contrastive learning (CLIP-style) to align audio and video.
    """

    embed_dim: int = 512
    temperature: float = 0.07

    @nn.compact
    def __call__(
        self,
        audio_emb: jnp.ndarray,
        video_emb: jnp.ndarray,
        training: bool = True,
    ) -> tuple[jnp.ndarray, dict[str, jnp.ndarray]]:
        """Compute audio-visual alignment loss.

        Args:
            audio_emb: [B, D] audio embeddings
            video_emb: [B, D] video embeddings
            training: Whether in training mode

        Returns:
            loss: Contrastive alignment loss
            metrics: Dict of metrics
        """
        # Project to shared space
        audio_proj = nn.Dense(self.embed_dim, name="audio_proj")(audio_emb)
        video_proj = nn.Dense(self.embed_dim, name="video_proj")(video_emb)

        # L2 normalize
        audio_proj = audio_proj / (jnp.linalg.norm(audio_proj, axis=-1, keepdims=True) + 1e-8)
        video_proj = video_proj / (jnp.linalg.norm(video_proj, axis=-1, keepdims=True) + 1e-8)

        # Compute similarity matrix
        logits = jnp.matmul(audio_proj, video_proj.T) / self.temperature  # [B, B]

        # Contrastive loss (symmetric)
        B = audio_emb.shape[0]
        labels = jnp.arange(B)

        loss_a2v = jnp.mean(
            -jnp.sum(jax.nn.one_hot(labels, B) * jax.nn.log_softmax(logits, axis=1), axis=1)
        )
        loss_v2a = jnp.mean(
            -jnp.sum(jax.nn.one_hot(labels, B) * jax.nn.log_softmax(logits, axis=0), axis=0)
        )

        loss = (loss_a2v + loss_v2a) / 2

        # Metrics
        a2v_acc = jnp.mean(jnp.argmax(logits, axis=1) == labels)
        v2a_acc = jnp.mean(jnp.argmax(logits, axis=0) == labels)

        metrics = {
            "av_loss": loss,
            "av_a2v_acc": a2v_acc,
            "av_v2a_acc": v2a_acc,
        }

        return loss, metrics


# =============================================================================
# FACTORY
# =============================================================================


def create_audio_encoder(
    config: AudioEncoderConfig | None = None,
) -> tuple[AudioEncoder, jnp.ndarray]:
    """Factory function for audio encoder.

    Returns:
        encoder: AudioEncoder module
        mel_filterbank: Precomputed filterbank matrix
    """
    if config is None:
        config = AudioEncoderConfig()

    # Precompute mel filterbank
    mel_filterbank = create_mel_filterbank(
        sample_rate=config.sample_rate,
        n_fft=config.n_fft,
        n_mels=config.n_mels,
    )

    return AudioEncoder(config), mel_filterbank


__all__ = [
    "AudioEncoder",
    "AudioEncoderConfig",
    "AudioEncoderOutput",
    "AudioPatchEmbed",
    "AudioTransformer",
    "AudioTransformerBlock",
    "AudioVectorQuantizer",
    "AudioVisualAligner",
    "compute_audio_encoder_loss",
    "compute_mel_spectrogram",
    "create_audio_encoder",
    "create_mel_filterbank",
]
