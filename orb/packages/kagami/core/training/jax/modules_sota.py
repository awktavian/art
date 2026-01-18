"""SOTA Modules for OrganismRSSM.

Implements research-backed components:
- Multi-Head Latent Attention (MLA) from DeepSeek V3
- Mamba-2 State Space with SSD
- SwiGLU activation (Llama 3)
- RMSNorm (faster than LayerNorm)
- Rotary Position Embeddings (RoPE)
- Grouped Query Attention (GQA)

These can be drop-in replacements for standard components.

Created: January 9, 2026
"""

from __future__ import annotations

import math

import jax
import jax.numpy as jnp
from flax import linen as nn

# =============================================================================
# RMSNORM (Faster than LayerNorm)
# =============================================================================


class RMSNorm(nn.Module):
    """Root Mean Square Layer Normalization.

    Faster than LayerNorm (no mean subtraction).
    Used in Llama 3, Gemma 2, DeepSeek V3.

    Paper: https://arxiv.org/abs/1910.07467
    """

    dim: int
    eps: float = 1e-5

    @nn.compact
    def __call__(self, x: jnp.ndarray) -> jnp.ndarray:
        """Apply RMSNorm.

        Args:
            x: Input tensor [..., dim]

        Returns:
            Normalized tensor [..., dim]
        """
        weight = self.param("weight", nn.initializers.ones, (self.dim,))

        # RMS normalization
        variance = jnp.mean(x**2, axis=-1, keepdims=True)
        x_normed = x * jax.lax.rsqrt(variance + self.eps)

        return x_normed * weight


# =============================================================================
# ROTARY POSITION EMBEDDING (RoPE)
# =============================================================================


def precompute_freqs_cis(
    dim: int,
    max_seq_len: int,
    theta: float = 500000.0,
) -> tuple[jnp.ndarray, jnp.ndarray]:
    """Precompute rotary embedding frequencies.

    Args:
        dim: Head dimension (must be even)
        max_seq_len: Maximum sequence length
        theta: RoPE theta (500000 for Llama 3 extended context)

    Returns:
        cos, sin tensors of shape [max_seq_len, dim//2]
    """
    freqs = 1.0 / (theta ** (jnp.arange(0, dim, 2).astype(jnp.float32) / dim))
    t = jnp.arange(max_seq_len)
    freqs = jnp.outer(t, freqs)

    cos = jnp.cos(freqs)
    sin = jnp.sin(freqs)

    return cos, sin


def apply_rotary_emb(
    xq: jnp.ndarray,
    xk: jnp.ndarray,
    cos: jnp.ndarray,
    sin: jnp.ndarray,
) -> tuple[jnp.ndarray, jnp.ndarray]:
    """Apply rotary embeddings to query and key tensors.

    Args:
        xq: Query tensor [B, T, H, D]
        xk: Key tensor [B, T, H, D]
        cos: Cosine frequencies [T, D//2]
        sin: Sine frequencies [T, D//2]

    Returns:
        Rotated query and key tensors
    """
    # Reshape for rotation
    xq_r = xq.reshape(*xq.shape[:-1], -1, 2)
    xk_r = xk.reshape(*xk.shape[:-1], -1, 2)

    # Complex multiplication (x * e^(iθ))
    xq_out = jnp.stack(
        [
            xq_r[..., 0] * cos - xq_r[..., 1] * sin,
            xq_r[..., 1] * cos + xq_r[..., 0] * sin,
        ],
        axis=-1,
    ).reshape(xq.shape)

    xk_out = jnp.stack(
        [
            xk_r[..., 0] * cos - xk_r[..., 1] * sin,
            xk_r[..., 1] * cos + xk_r[..., 0] * sin,
        ],
        axis=-1,
    ).reshape(xk.shape)

    return xq_out, xk_out


# =============================================================================
# SWIGLU ACTIVATION (Llama 3)
# =============================================================================


class SwiGLU(nn.Module):
    """SwiGLU activation with gated linear unit.

    SwiGLU(x) = (xW₁) ⊙ SiLU(xW₂)

    Used in Llama 3, PaLM, and most modern LLMs.
    Better than ReLU/GELU for language modeling.

    Paper: https://arxiv.org/abs/2002.05202
    """

    hidden_dim: int
    intermediate_dim: int

    @nn.compact
    def __call__(self, x: jnp.ndarray) -> jnp.ndarray:
        """Apply SwiGLU.

        Args:
            x: Input tensor [..., hidden_dim]

        Returns:
            Output tensor [..., hidden_dim]
        """
        # Gate and up projections
        gate = nn.Dense(self.intermediate_dim, use_bias=False, name="gate_proj")(x)
        up = nn.Dense(self.intermediate_dim, use_bias=False, name="up_proj")(x)

        # SwiGLU activation
        hidden = nn.silu(gate) * up

        # Down projection
        output = nn.Dense(self.hidden_dim, use_bias=False, name="down_proj")(hidden)

        return output


# =============================================================================
# GROUPED QUERY ATTENTION (GQA)
# =============================================================================


class GroupedQueryAttention(nn.Module):
    """Grouped Query Attention (Llama 3 / Gemma 2).

    Groups queries share the same K/V heads.
    Reduces KV cache by num_heads/num_kv_heads.

    Paper: https://arxiv.org/abs/2305.13245
    """

    hidden_dim: int
    num_heads: int = 16
    num_kv_heads: int = 4  # GQA groups
    head_dim: int = 48
    dropout: float = 0.0
    rope_theta: float = 500000.0
    max_seq_len: int = 32768

    @nn.compact
    def __call__(
        self,
        x: jnp.ndarray,
        mask: jnp.ndarray | None = None,
        deterministic: bool = True,
    ) -> jnp.ndarray:
        """Apply GQA attention.

        Args:
            x: Input tensor [B, T, D]
            mask: Attention mask [B, 1, T, T]
            deterministic: Disable dropout if True

        Returns:
            Output tensor [B, T, D]
        """
        B, T, _ = x.shape

        # Number of query heads per KV head
        num_heads_per_kv = self.num_heads // self.num_kv_heads

        # Projections
        q = nn.Dense(self.num_heads * self.head_dim, use_bias=False, name="q_proj")(x)
        k = nn.Dense(self.num_kv_heads * self.head_dim, use_bias=False, name="k_proj")(x)
        v = nn.Dense(self.num_kv_heads * self.head_dim, use_bias=False, name="v_proj")(x)

        # Reshape
        q = q.reshape(B, T, self.num_heads, self.head_dim)
        k = k.reshape(B, T, self.num_kv_heads, self.head_dim)
        v = v.reshape(B, T, self.num_kv_heads, self.head_dim)

        # RoPE
        cos, sin = precompute_freqs_cis(self.head_dim, T, self.rope_theta)
        q, k = apply_rotary_emb(q, k, cos, sin)

        # Expand KV heads for GQA
        k = jnp.repeat(k, num_heads_per_kv, axis=2)
        v = jnp.repeat(v, num_heads_per_kv, axis=2)

        # Attention
        q = q.transpose(0, 2, 1, 3)  # [B, H, T, D]
        k = k.transpose(0, 2, 1, 3)
        v = v.transpose(0, 2, 1, 3)

        scale = 1.0 / math.sqrt(self.head_dim)
        attn_weights = jnp.einsum("bhqd,bhkd->bhqk", q, k) * scale

        if mask is not None:
            attn_weights = jnp.where(mask, attn_weights, -1e9)

        attn_weights = jax.nn.softmax(attn_weights, axis=-1)

        if not deterministic and self.dropout > 0:
            attn_weights = nn.Dropout(self.dropout)(attn_weights, deterministic=deterministic)

        attn_output = jnp.einsum("bhqk,bhkd->bhqd", attn_weights, v)
        attn_output = attn_output.transpose(0, 2, 1, 3).reshape(B, T, -1)

        # Output projection
        output = nn.Dense(self.hidden_dim, use_bias=False, name="o_proj")(attn_output)

        return output


# =============================================================================
# MULTI-HEAD LATENT ATTENTION (MLA) - DeepSeek V3
# =============================================================================


class MultiHeadLatentAttention(nn.Module):
    """Multi-Head Latent Attention from DeepSeek V3.

    Compresses KV into low-rank latent space:
    - 4x memory reduction during inference
    - Maintains attention quality

    Source: DeepSeek V3 Technical Report
    """

    hidden_dim: int
    num_heads: int = 16
    head_dim: int = 48
    latent_dim: int = 256  # Compressed KV dimension
    num_latent_heads: int = 8  # Heads in latent space
    dropout: float = 0.0

    @nn.compact
    def __call__(
        self,
        x: jnp.ndarray,
        mask: jnp.ndarray | None = None,
        deterministic: bool = True,
    ) -> jnp.ndarray:
        """Apply MLA attention.

        Args:
            x: Input tensor [B, T, D]
            mask: Attention mask [B, 1, T, T]
            deterministic: Disable dropout if True

        Returns:
            Output tensor [B, T, D]
        """
        B, T, _ = x.shape

        # Query projection (full dimension)
        q = nn.Dense(self.num_heads * self.head_dim, use_bias=False, name="q_proj")(x)
        q = q.reshape(B, T, self.num_heads, self.head_dim)

        # KV compression to latent space
        kv_latent = nn.Dense(self.latent_dim, use_bias=False, name="kv_compress")(x)
        kv_latent = RMSNorm(self.latent_dim, name="kv_norm")(kv_latent)

        # Decompress to K and V
        k = nn.Dense(self.num_latent_heads * self.head_dim, use_bias=False, name="k_decompress")(
            kv_latent
        )
        v = nn.Dense(self.num_latent_heads * self.head_dim, use_bias=False, name="v_decompress")(
            kv_latent
        )

        k = k.reshape(B, T, self.num_latent_heads, self.head_dim)
        v = v.reshape(B, T, self.num_latent_heads, self.head_dim)

        # Expand latent heads to match query heads
        heads_per_latent = self.num_heads // self.num_latent_heads
        k = jnp.repeat(k, heads_per_latent, axis=2)
        v = jnp.repeat(v, heads_per_latent, axis=2)

        # Standard attention computation
        q = q.transpose(0, 2, 1, 3)  # [B, H, T, D]
        k = k.transpose(0, 2, 1, 3)
        v = v.transpose(0, 2, 1, 3)

        scale = 1.0 / math.sqrt(self.head_dim)
        attn_weights = jnp.einsum("bhqd,bhkd->bhqk", q, k) * scale

        if mask is not None:
            attn_weights = jnp.where(mask, attn_weights, -1e9)

        attn_weights = jax.nn.softmax(attn_weights, axis=-1)

        if not deterministic and self.dropout > 0:
            attn_weights = nn.Dropout(self.dropout)(attn_weights, deterministic=deterministic)

        attn_output = jnp.einsum("bhqk,bhkd->bhqd", attn_weights, v)
        attn_output = attn_output.transpose(0, 2, 1, 3).reshape(B, T, -1)

        # Output projection
        output = nn.Dense(self.hidden_dim, use_bias=False, name="o_proj")(attn_output)

        return output


# =============================================================================
# MAMBA-2 SELECTIVE STATE SPACE
# =============================================================================


class Mamba2Block(nn.Module):
    """Mamba-2 block with Structured State Space Duality (SSD).

    O(n) complexity vs O(n²) for attention.
    Excellent for long sequences.

    Source: https://arxiv.org/abs/2405.21060
    """

    hidden_dim: int
    state_dim: int = 64
    expand_factor: int = 2
    conv_kernel_size: int = 4
    dt_min: float = 0.001
    dt_max: float = 0.1

    @nn.compact
    def __call__(
        self,
        x: jnp.ndarray,
        deterministic: bool = True,
    ) -> jnp.ndarray:
        """Apply Mamba-2 block.

        Args:
            x: Input tensor [B, T, D]
            deterministic: Unused (for API compatibility)

        Returns:
            Output tensor [B, T, D]
        """
        B, _T, D = x.shape
        expand_dim = D * self.expand_factor

        # Input projection (expand)
        x_proj = nn.Dense(expand_dim * 2, use_bias=False, name="in_proj")(x)
        x_z = x_proj[..., :expand_dim]
        z = x_proj[..., expand_dim:]

        # 1D convolution
        x_conv = nn.Conv(
            features=expand_dim,
            kernel_size=(self.conv_kernel_size,),
            feature_group_count=expand_dim,
            padding="SAME",
            name="conv1d",
        )(x_z.transpose(0, 2, 1)).transpose(0, 2, 1)
        x_conv = nn.silu(x_conv)

        # SSM parameters
        dt = nn.Dense(expand_dim, use_bias=True, name="dt_proj")(x_conv)
        dt = jax.nn.softplus(dt)  # Ensure positive
        dt = jnp.clip(dt, self.dt_min, self.dt_max)

        B_param = nn.Dense(self.state_dim, use_bias=False, name="B_proj")(x_conv)
        C_param = nn.Dense(self.state_dim, use_bias=False, name="C_proj")(x_conv)

        # Discretized A (diagonal, learned)
        A_log = self.param(
            "A_log",
            lambda rng, shape: -jnp.ones(shape) * jnp.log(jnp.arange(1, shape[0] + 1)),
            (self.state_dim,),
        )
        A = -jnp.exp(A_log)

        # SSM scan (simplified)
        # Full implementation would use associative scan for parallelism
        def ssm_step(h, inputs):
            x_t, dt_t, B_t, C_t = inputs
            # Discretize
            dA = jnp.exp(dt_t[..., None] * A)
            dB = dt_t[..., None] * B_t[..., None, :]
            # Update state
            h_new = dA * h + dB * x_t[..., None]
            # Output
            y_t = jnp.sum(h_new * C_t[..., None, :], axis=-1)
            return h_new, y_t

        # Initialize state
        h0 = jnp.zeros((B, expand_dim, self.state_dim))

        # Scan over sequence
        inputs = (
            x_conv.transpose(1, 0, 2),
            dt.transpose(1, 0, 2),
            B_param.transpose(1, 0, 2),
            C_param.transpose(1, 0, 2),
        )
        _, y = jax.lax.scan(ssm_step, h0, inputs)
        y = y.transpose(1, 0, 2)  # [B, T, expand_dim]

        # Gate and output
        y = y * nn.silu(z)
        output = nn.Dense(D, use_bias=False, name="out_proj")(y)

        return output


# =============================================================================
# HYBRID TRANSFORMER-SSM LAYER
# =============================================================================


class HybridLayer(nn.Module):
    """Hybrid layer combining attention and SSM.

    Interleaves attention and Mamba blocks for optimal
    performance on both local and global patterns.

    Pattern: Every 4th layer is attention, rest are SSM.
    """

    hidden_dim: int
    num_heads: int = 16
    num_kv_heads: int = 4
    head_dim: int = 48
    state_dim: int = 64
    intermediate_dim: int = 2048
    use_attention: bool = True  # If False, use SSM
    dropout: float = 0.0

    @nn.compact
    def __call__(
        self,
        x: jnp.ndarray,
        mask: jnp.ndarray | None = None,
        deterministic: bool = True,
    ) -> jnp.ndarray:
        """Apply hybrid layer.

        Args:
            x: Input tensor [B, T, D]
            mask: Attention mask (only used for attention layers)
            deterministic: Disable dropout if True

        Returns:
            Output tensor [B, T, D]
        """
        # Pre-norm
        normed = RMSNorm(self.hidden_dim, name="input_norm")(x)

        # Attention or SSM
        if self.use_attention:
            attn_out = GroupedQueryAttention(
                hidden_dim=self.hidden_dim,
                num_heads=self.num_heads,
                num_kv_heads=self.num_kv_heads,
                head_dim=self.head_dim,
                dropout=self.dropout,
                name="attention",
            )(normed, mask=mask, deterministic=deterministic)
        else:
            attn_out = Mamba2Block(
                hidden_dim=self.hidden_dim,
                state_dim=self.state_dim,
                name="mamba",
            )(normed, deterministic=deterministic)

        # Residual
        x = x + attn_out

        # Post-norm + FFN
        normed = RMSNorm(self.hidden_dim, name="ffn_norm")(x)
        ffn_out = SwiGLU(
            hidden_dim=self.hidden_dim,
            intermediate_dim=self.intermediate_dim,
            name="ffn",
        )(normed)

        # Residual
        x = x + ffn_out

        return x


# =============================================================================
# EXPORTS
# =============================================================================


__all__ = [
    "GroupedQueryAttention",
    "HybridLayer",
    "Mamba2Block",
    "MultiHeadLatentAttention",
    "RMSNorm",
    "SwiGLU",
    "apply_rotary_emb",
    "precompute_freqs_cis",
]
