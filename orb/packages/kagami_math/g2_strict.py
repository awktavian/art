# ruff: noqa: N812
"""Strict G2-invariant/equivariant octonion layers.

Design goals:
- Attention scores are G2-invariant scalars (built from inner products and phi-triples)
- Attention outputs are G2-equivariant vectors (in R^7 imaginary part)
- Feedforward uses only octonion multiplication and invariant scalars

Implementation notes:
- G2 acts trivially on the real axis and as automorphisms on Im(O) = R^7
- We treat per-head octonions as (real, imag7) and apply group action to imag7
"""

from __future__ import annotations

import importlib
from typing import cast

import torch
import torch.nn as nn
import torch.nn.functional as F

# Lazy import to avoid circular dependency with kagami.core.config
_g2_exact_cache = None


def _get_g2_exact_projectors():
    """Lazy import of G2ExactProjectors to break circular dependency."""
    global _g2_exact_cache
    if _g2_exact_cache is None:
        _g2_exact_cache = importlib.import_module(
            "kagami.core.world_model.equivariance.g2_exact"
        ).G2ExactProjectors
    return _g2_exact_cache


# Lazy import wrappers to avoid circular dependency with octonion module.
# CANONICAL LOCATION: kagami.math.octonions.algebra.OctonionManifold
# These wrappers exist solely for circular import avoidance in this module.
_octonion_manifold_cache = None


def _get_octonion_manifold() -> None:
    """Lazy import of OctonionManifold to avoid circular imports."""
    global _octonion_manifold_cache
    if _octonion_manifold_cache is None:
        # Package is kagami_math, not kagami.math
        _oct = importlib.import_module("kagami_math.octonions")
        _octonion_manifold_cache = _oct.OctonionManifold()
    return _octonion_manifold_cache  # type: ignore[no-any-return]


def _cayley_dickson_mul(o1: torch.Tensor, o2: torch.Tensor) -> torch.Tensor:
    """Wrapper for Cayley-Dickson multiplication with lazy import.

    CANONICAL: kagami.math.octonions.algebra.OctonionManifold.multiply_8d
    This wrapper handles both 7D (pure imaginary) and 8D (full) octonions.
    """
    manifold = _get_octonion_manifold()  # type: ignore[func-returns-value]
    if o1.shape[-1] == 8 and o2.shape[-1] == 8:
        return cast(torch.Tensor, manifold.multiply_8d(o1, o2))
    elif o1.shape[-1] == 7 and o2.shape[-1] == 7:
        return cast(torch.Tensor, manifold.multiply(o1, o2))
    else:
        raise ValueError(f"Expected 7D or 8D octonions, got {o1.shape[-1]}D and {o2.shape[-1]}D")


def _unit_normalize(o: torch.Tensor) -> torch.Tensor:
    """Wrapper for unit normalization with lazy import.

    CANONICAL: kagami.math.octonions.algebra.OctonionManifold.project_to_s7
    """
    manifold = _get_octonion_manifold()  # type: ignore[func-returns-value]
    return cast(torch.Tensor, manifold.project_to_s7(o))


def _split_real_imag(o: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    # o: [..., 8] → (real [..., 1], imag [..., 7])
    return o[..., :1], o[..., 1:]


def _join_real_imag(real: torch.Tensor, imag: torch.Tensor) -> torch.Tensor:
    return torch.cat([real, imag], dim=-1)


class G2InvariantAttention(nn.Module):
    """Attention using G₂-invariant scoring and equivariant combination.

    Optimized for FlashAttention (SDPA).

    Architecture:
    - Standard head: A1 = softmax(Q @ K.T)
    - Twisted head: A2 = softmax(Q @ (K x V).T) (implicit in mixing)

    Instead of full MLP on invariants (O(N²)), we use a linear combination of
    canonical invariants to form a composite Key:
      K_mix = w1*K + w2*(K x V)

    Then Attention(Q, K_mix, V) approximates the G2-invariant attention.
    This allows using O(N²) optimized kernels (FlashAttention).
    """

    def __init__(
        self,
        num_heads: int,
        attn_drop: float = 0.0,
        proj_drop: float = 0.0,
        sparse_topk: int = 0,
        use_sparse_oct: bool = True,
        sparse_oct_mode: str = "soft",
        sparse_oct_topk: int = 4,
    ) -> None:
        super().__init__()
        self.num_heads = num_heads
        self.oct_dim = 8
        self.total_dim = num_heads * self.oct_dim
        self.attn_drop = attn_drop  # Scalar for SDPA
        self.proj_drop = nn.Dropout(proj_drop)
        self.sparse_topk = int(max(0, sparse_topk))
        self.use_sparse_oct = use_sparse_oct

        # Lazy import to avoid circular dependency with kagami.core.config
        self.g2 = _get_g2_exact_projectors()()

        # Optional sparse octonion activation
        if use_sparse_oct:
            SparseOctonionActivation = importlib.import_module(
                "kagami.core.world_model.layers.sparse_octonion"
            ).SparseOctonionActivation

            self.sparse_oct_activation = SparseOctonionActivation(
                mode=sparse_oct_mode,
                top_k=sparse_oct_topk,
                learn_gates=True,
            )
        else:
            self.sparse_oct_activation = None

        # Learnable mixing weights for invariants
        # w_k: weight for standard alignment <q, k>
        # w_twist: weight for twisted alignment <q, k x v>
        self.invariant_mix = nn.Parameter(torch.randn(num_heads, 2))

        # Head-wise learned scalars for output mixing
        self.alpha = nn.Parameter(torch.ones(num_heads))  # weight for sum(a * v_j)
        self.beta = nn.Parameter(torch.zeros(num_heads))  # weight for sum(a * (q x k))

    def forward(
        self,
        o: torch.Tensor,
        mask: torch.Tensor | None = None,
        return_attention: bool = False,
    ) -> tuple[torch.Tensor, torch.Tensor | None] | torch.Tensor:
        """o: [B, N, H*8] → returns same shape, G₂-equvariant across imag part."""
        orig_dtype = o.dtype
        compute_dtype = (
            torch.float32 if orig_dtype in (torch.float16, torch.bfloat16) else orig_dtype
        )
        if compute_dtype != orig_dtype:
            o = o.to(compute_dtype)
        B, N, D = o.shape
        H = self.num_heads
        assert D == H * 8, f"Expected last dim {H * 8}, got {D}"

        # Work in [B, H, N, 8] layout for efficient matmul
        o_heads = o.view(B, N, H, 8).permute(0, 2, 1, 3)  # [B, H, N, 8]

        # Optional sparse octonion activation (gate imaginary units)
        if self.use_sparse_oct and self.sparse_oct_activation is not None:
            # Sparse activation expects flat input usually, assume we adapt or skip for now
            pass

        real, imag = _split_real_imag(o_heads)  # [B, H, N, 1], [B, H, N, 7]

        # q, k, v use imag part
        q = imag  # [B, H, N, 7]
        k = imag
        v = imag

        # 1. Construct Mixed Key for Flash G2 Attention
        # K_twist = K x V (Elementwise cross product per position, O(N))
        # Note: self.g2.cross expects [..., 7]. It works on [B, H, N, 7].
        k_cross_v = self.g2.cross(k, v)  # [B, H, N, 7]

        # Mix keys based on learned weights
        # weights: [H, 2] -> view as [1, H, 1, 1] for broadcasting
        w = F.softmax(self.invariant_mix, dim=-1)
        w_k = w[:, 0].view(1, H, 1, 1)
        w_twist = w[:, 1].view(1, H, 1, 1)

        k_mix = w_k * k + w_twist * k_cross_v  # [B, H, N, 7]

        # 2. Run SDPA (FlashAttention compatible)
        # scaled_dot_product_attention(q, k, v) computes Softmax(Q @ K.T / sqrt(d)) @ V
        # Dimensions: [B, H, N, 7]
        # Mask handling: SDPA expects mask broadcastable to [B, H, N, N]

        # Prepare mask if needed
        sdpa_mask = None
        if mask is not None:
            # mask is usually [B, N, N]
            sdpa_mask = mask.unsqueeze(1)  # [B, 1, N, N]

        # Run attention to get V-weighted output
        # y_v = Σ softmax(q . k_mix) * v
        y_v = F.scaled_dot_product_attention(
            q, k_mix, v, attn_mask=sdpa_mask, dropout_p=self.attn_drop if self.training else 0.0
        )  # [B, H, N, 7]

        # 3. Compute Twisted Output
        # We need y_x = q x (Σ softmax(q . k_mix) * k)
        # This requires pooling K with the SAME attention weights.
        # SDPA doesn't return weights in optimized path, so we run SDPA again with V=K
        # This is cheap compared to materializing N^2 scores
        k_pooled = F.scaled_dot_product_attention(
            q, k_mix, k, attn_mask=sdpa_mask, dropout_p=self.attn_drop if self.training else 0.0
        )  # [B, H, N, 7]

        y_x = self.g2.cross(q, k_pooled)  # [B, H, N, 7]

        # 4. Combine outputs
        alpha = torch.sigmoid(self.alpha).view(1, H, 1, 1)
        beta = torch.tanh(self.beta).view(1, H, 1, 1)
        imag_out = alpha * y_v + beta * y_x  # [B, H, N, 7]

        # Recompose octonions and project per head to S⁷
        o_out = _join_real_imag(real, imag_out)  # [B, H, N, 8]

        # Permute back to [B, N, H, 8] and flatten
        o_out = o_out.permute(0, 2, 1, 3).contiguous()
        o_out = _unit_normalize(o_out)
        o_out = o_out.view(B, N, H * 8)

        o_out = self.proj_drop(o_out)

        if return_attention:
            # Warning: Returning attention weights requires eager mode SDPA usually,
            # or explicit score computation which breaks Flash.
            # We return None or approximate if Flash is used.
            # For backward compatibility, we'll just return None for weights if using optimized path.
            return o_out, None

        # Convert back to original dtype if needed
        if compute_dtype != orig_dtype and orig_dtype == torch.float16:
            o_out = o_out.to(orig_dtype)

        return o_out  # type: ignore[no-any-return]


class G2StrictAttention(G2InvariantAttention):
    """Alias for G2InvariantAttention for backwards compatibility.

    The strict G2-invariant attention mechanism is implemented in G2InvariantAttention.
    This alias maintains API compatibility with existing code.
    """


class G2EquivariantFeedForward(nn.Module):
    """Strict G2-equivariant FFN using only octonion multiplication and scalars.

    For each head we compute:
      update = a(o)*o + b(o)*(o*o) + c(o)*(o*(o*o))
    where a,b,c are G2-invariant scalars derived from (real, ||imag||).
    """

    def __init__(self, num_heads: int, dropout: float = 0.0) -> None:
        super().__init__()
        self.num_heads = num_heads
        self.oct_dim = 8
        self.total_dim = num_heads * self.oct_dim
        self.dropout = nn.Dropout(dropout)

        # Scalar MLP maps per-head invariants [real, norm_imag] -> [a, b, c]
        self.scalar_mlp = nn.Sequential(nn.Linear(2, 32), nn.GELU(), nn.Linear(32, 3))

        # Residual mixing
        self.residual_alpha = nn.Parameter(torch.tensor(0.25))

    def forward(self, o: torch.Tensor) -> torch.Tensor:
        B, N, D = o.shape
        H = self.num_heads
        assert D == H * 8

        o_res = o
        o_heads = o.view(B, N, H, 8)
        real, imag = _split_real_imag(o_heads)

        # Invariants per head
        r = real.squeeze(-1)  # [B, N, H]
        n = torch.norm(imag, dim=-1)  # [B, N, H]
        inv = torch.stack([r, n], dim=-1)  # [B, N, H, 2]
        scalars = self.scalar_mlp(inv)  # [B, N, H, 3]
        a, b, c = torch.unbind(scalars, dim=-1)

        # Compute equivariant polynomial in o via octonion multiplication
        o1 = o_heads  # [B, N, H, 8]
        o2 = _cayley_dickson_mul(o1, o1)  # o⊙o
        o3 = _cayley_dickson_mul(o1, o2)  # o⊙(o⊙o)

        upd = a.unsqueeze(-1) * o1 + b.unsqueeze(-1) * o2 + c.unsqueeze(-1) * o3
        upd = _unit_normalize(upd)

        upd = upd.view(B, N, H * 8)
        lam = torch.sigmoid(self.residual_alpha)
        out = (1 - lam) * o_res + lam * upd
        return cast(torch.Tensor, self.dropout(out))  # External lib
