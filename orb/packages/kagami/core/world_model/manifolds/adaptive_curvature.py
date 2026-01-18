from __future__ import annotations

"""Semantic-Adaptive Curvature for Hyperbolic Manifolds.

Makes curvature c(s) a function of semantic position s ∈ ℝ³⁸⁴, allowing
the manifold to dynamically warp based on content:
- Abstract concepts → high curvature (compressed near origin)
- Specific facts → low curvature (spread at boundary)
- Domain-specific regions → custom curvature profiles

Mathematical Foundation:
    K(s) = -c(s) where c: ℝ³⁸⁴ → [c_min, c_max]

This creates a Riemannian manifold with variable sectional curvature,
learned end-to-end via gradient descent on downstream tasks.

References:
- Variable curvature manifolds: https://arxiv.org/abs/1910.12180
- Adaptive hyperbolic networks: https://arxiv.org/abs/2202.08313
"""
import torch
import torch.nn as nn
import torch.nn.functional as F


class SemanticCurvatureNetwork(nn.Module):
    """Neural network that predicts optimal curvature from semantic embeddings.

    Architecture:
        s ∈ ℝ³⁸⁴ → compress → context → expand → c(s) ∈ [c_min, c_max]

    Design choices:
    - Low-rank bottleneck for efficiency (384 → 64 → 16 → 64 → 1)
    - Residual connection to base curvature
    - Smooth activation (softplus) for differentiability
    - Optional per-head curvature for multi-head attention
    """

    def __init__(
        self,
        embedding_dim: int = 512,  # Kagami bulk_dim (from KAGAMI_BULK_DIM)
        hidden_dim: int = 64,
        bottleneck_dim: int = 16,
        curvature_min: float = 1e-3,
        curvature_max: float = 1.0,
        base_curvature: float = 0.1,
        num_heads: int = 1,
        use_residual: bool = True,
    ) -> None:
        """Initialize semantic curvature network.

        Args:
            embedding_dim: Dimension of semantic embeddings (384 for K os)
            hidden_dim: Hidden layer dimension
            bottleneck_dim: Bottleneck dimension (compression)
            curvature_min: Minimum curvature (flat → Euclidean)
            curvature_max: Maximum curvature (steep → tree-like)
            base_curvature: Base curvature to add residual to
            num_heads: Number of attention heads (for per-head curvature)
            use_residual: Use residual connection to base curvature
        """
        super().__init__()
        self.embedding_dim = embedding_dim
        self.curvature_min = curvature_min
        self.curvature_max = curvature_max
        self.num_heads = num_heads
        self.use_residual = use_residual

        # Base curvature (learnable)
        self.base_curvature = nn.Parameter(torch.tensor(base_curvature))

        # Compression network: 384 → 64 → 16
        self.compress = nn.Sequential(
            nn.Linear(embedding_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, bottleneck_dim),
            nn.LayerNorm(bottleneck_dim),
            nn.GELU(),
        )

        # Context extraction: 16 → 16 (self-attention in bottleneck)
        self.context_attn = nn.MultiheadAttention(
            embed_dim=bottleneck_dim,
            num_heads=1,
            batch_first=True,
        )
        self.context_norm = nn.LayerNorm(bottleneck_dim)

        # Expansion network: 16 → 64 → num_heads
        self.expand = nn.Sequential(
            nn.Linear(bottleneck_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, num_heads),
        )

        # Initialize to predict near-zero adjustments initially
        nn.init.zeros_(self.expand[-1].weight)  # type: ignore[arg-type]
        nn.init.zeros_(self.expand[-1].bias)  # type: ignore[arg-type]

    def forward(
        self,
        semantic_embeddings: torch.Tensor,
        return_base: bool = False,
    ) -> torch.Tensor | tuple[torch.Tensor, torch.Tensor]:
        """Predict curvature from semantic embeddings.

        Args:
            semantic_embeddings: Embeddings [B, N, D] or [B, D]
            return_base: If True, return (curvature, base_curvature)

        Returns:
            curvature [B, N, H] or [B, H] where H is num_heads
        """
        # Handle both [B, D] and [B, N, D] inputs
        input_shape = semantic_embeddings.shape
        if len(input_shape) == 2:
            # [B, D] → add sequence dimension
            x = semantic_embeddings.unsqueeze(1)  # [B, 1, D]
            squeeze_output = True
        else:
            x = semantic_embeddings  # [B, N, D]
            squeeze_output = False

        _B, _N, _D = x.shape

        # Compress: [B, N, D] → [B, N, bottleneck]
        compressed = self.compress(x)  # [B, N, 16]

        # Context attention: Allow positions to communicate
        attn_out, _ = self.context_attn(
            compressed,
            compressed,
            compressed,
            need_weights=False,
        )
        contextual = self.context_norm(compressed + attn_out)

        # Expand: [B, N, bottleneck] → [B, N, num_heads]
        adjustments = self.expand(contextual)  # [B, N, H]

        # Compute base curvature (clamped)
        base_c = torch.clamp(
            F.softplus(self.base_curvature) + self.curvature_min,
            min=self.curvature_min,
            max=self.curvature_max,
        )

        # Apply residual or direct prediction
        if self.use_residual:
            # Residual: c(s) = base + Δc(s)
            # Scale adjustment to [-0.5*base, +0.5*base]
            scale = 0.5 * base_c
            c = base_c + scale * torch.tanh(adjustments)  # [B, N, H]
        else:
            # Direct: c(s) = σ(adjustment)
            c = F.softplus(adjustments) + self.curvature_min

        # Clamp to valid range
        c = torch.clamp(c, min=self.curvature_min, max=self.curvature_max)

        # Remove sequence dimension if input was [B, D]
        if squeeze_output:
            c = c.squeeze(1)  # [B, H]

        if return_base:
            return c, base_c
        return c

    def get_regularization_loss(self) -> torch.Tensor:
        """Regularization loss to prevent extreme curvatures.

        Encourages curvatures to stay near the base value unless
        strongly motivated by task gradients.

        Returns:
            Scalar regularization loss
        """
        # L2 penalty on the final layer weights (discourages large adjustments)
        final_layer = self.expand[-1]
        weight_penalty = torch.sum(final_layer.weight**2)  # type: ignore  # Operator overload

        # Encourage base curvature to stay in reasonable range
        base_c = F.softplus(self.base_curvature) + self.curvature_min
        base_penalty = F.relu(base_c - 0.5)  # Penalize if > 0.5

        return 1e-4 * weight_penalty + 1e-3 * base_penalty


class AdaptivePoincareManifold(nn.Module):
    """Poincaré manifold with semantic-adaptive curvature.

    Extends PoincareManifold to support c(s) instead of fixed c.
    All geometric operations (exp, log, distance) use the local curvature.
    """

    def __init__(
        self,
        dim: int,
        embedding_dim: int = 512,  # Kagami bulk_dim (from KAGAMI_BULK_DIM)
        curvature_init: float = 0.1,
        curvature_min: float = 1e-3,
        curvature_max: float = 1.0,
        num_heads: int = 1,
    ) -> None:
        """Initialize adaptive Poincaré manifold.

        Args:
            dim: Hyperbolic dimension
            embedding_dim: Semantic embedding dimension
            curvature_init: Initial base curvature
            curvature_min: Minimum curvature
            curvature_max: Maximum curvature
            num_heads: Number of attention heads (for per-head curvature)
        """
        super().__init__()
        self.dim = dim
        self.embedding_dim = embedding_dim
        self.num_heads = num_heads
        self.eps = 1e-15

        # Semantic curvature network
        self.curvature_net = SemanticCurvatureNetwork(
            embedding_dim=embedding_dim,
            curvature_min=curvature_min,
            curvature_max=curvature_max,
            base_curvature=curvature_init,
            num_heads=num_heads,
        )

    def get_curvature(
        self,
        semantic_embeddings: torch.Tensor,
    ) -> torch.Tensor:
        """Get adaptive curvature at semantic positions.

        Args:
            semantic_embeddings: [B, N, D] or [B, D]

        Returns:
            Curvature [B, N, H] or [B, H]
        """
        return self.curvature_net(semantic_embeddings)  # External lib

    def radius(self, curvature: torch.Tensor) -> torch.Tensor:
        """Get ball radius 1/√c for given curvature.

        Args:
            curvature: [..., H] curvature values

        Returns:
            Radius [..., H]
        """
        return 1.0 / torch.sqrt(curvature.clamp_min(self.eps))

    def project(
        self,
        x: torch.Tensor,
        curvature: torch.Tensor,
        eps: float | None = None,
    ) -> torch.Tensor:
        """Project to Poincaré ball with adaptive curvature.

        Args:
            x: Points [..., dim]
            curvature: Curvature values [..., 1] or [..., H]
            eps: Safety epsilon

        Returns:
            Projected points [..., dim]
        """
        if eps is None:
            eps = self.eps

        norm = x.norm(dim=-1, keepdim=True, p=2).clamp_min(self.eps)
        margin = max(eps, 1e-5)

        # Adaptive radius
        max_norm = self.radius(curvature) - margin

        # Project if outside ball
        scale = torch.where(
            norm > max_norm,
            max_norm / (norm + self.eps),
            torch.ones_like(norm),
        )

        return x * scale

    def exp0(
        self,
        v: torch.Tensor,
        curvature: torch.Tensor,
    ) -> torch.Tensor:
        """Exponential map at origin with adaptive curvature.

        Args:
            v: Tangent vectors [..., dim]
            curvature: Curvature [..., 1] or [..., H]

        Returns:
            Points on manifold [..., dim]
        """
        sqrt_c = torch.sqrt(curvature.clamp_min(self.eps))
        norm_v = v.norm(dim=-1, keepdim=True, p=2).clamp_min(self.eps)

        coef = torch.tanh(sqrt_c * norm_v) / (sqrt_c * norm_v + self.eps)
        result = coef * v

        return self.project(result, curvature)

    def log0(
        self,
        x: torch.Tensor,
        curvature: torch.Tensor,
    ) -> torch.Tensor:
        """Logarithmic map at origin with adaptive curvature.

        Args:
            x: Points on manifold [..., dim]
            curvature: Curvature [..., 1] or [..., H]

        Returns:
            Tangent vectors [..., dim]
        """
        sqrt_c = torch.sqrt(curvature.clamp_min(self.eps))
        norm_x = x.norm(dim=-1, keepdim=True, p=2).clamp_min(self.eps)

        sqrt_c_norm = (sqrt_c * norm_x).clamp(max=1.0 - self.eps)
        coef = torch.atanh(sqrt_c_norm) / (sqrt_c_norm + self.eps)

        return coef * x  # External lib

    def distance(
        self,
        x: torch.Tensor,
        y: torch.Tensor,
        curvature: torch.Tensor,
    ) -> torch.Tensor:
        """Hyperbolic distance with adaptive curvature.

        Args:
            x, y: Points [..., dim]
            curvature: Curvature [..., 1] or [..., H]

        Returns:
            Distances [...]
        """
        c = curvature.squeeze(-1) if curvature.shape[-1] == 1 else curvature

        x_norm_sq = (x * x).sum(dim=-1).clamp_min(self.eps)
        y_norm_sq = (y * y).sum(dim=-1).clamp_min(self.eps)
        diff_norm_sq = ((x - y) * (x - y)).sum(dim=-1).clamp_min(self.eps)

        denom = ((1 - c * x_norm_sq) * (1 - c * y_norm_sq)).clamp_min(self.eps)
        arg = 1 + (2 * c * diff_norm_sq / denom)
        arg = arg.clamp_min(1.0 + self.eps)

        return torch.acosh(arg) / torch.sqrt(c.clamp_min(self.eps))

    def get_curvature_stats(
        self,
        semantic_embeddings: torch.Tensor,
    ) -> dict[str, torch.Tensor]:
        """Get statistics about predicted curvatures.

        Useful for monitoring and debugging.

        Args:
            semantic_embeddings: [B, N, D]

        Returns:
            Dict with mean, std, min, max curvatures
        """
        with torch.no_grad():
            c, base_c = self.curvature_net(semantic_embeddings, return_base=True)

            return {
                "curvature_mean": c.mean(),
                "curvature_std": c.std(),
                "curvature_min": c.min(),
                "curvature_max": c.max(),
                "base_curvature": base_c,
            }
