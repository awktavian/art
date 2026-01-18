"""G₂-Invariant Pooling and Feature Extraction.

Implements pooling layers that are guaranteed to be G₂-invariant using:
- Norm: ||x|| (scalar invariant)
- Triple products: φ(x, y, z) using associative 3-form
- Quadruple products: ψ(x, y, z, w) using coassociative 4-form
- Cross product norms: ||x × y||

These features are G₂-invariant by construction (proven mathematically).

References:
    - Bryant (2006): "Some Remarks on G₂-Structures"
    - K os research: docs/math.md
"""

from __future__ import annotations

from typing import cast

import torch
import torch.nn as nn

# Lazy import to avoid circular dependency with kagami.core.config
_G2PhiPsi = None


def _get_g2_phi_psi():
    """Lazy import of G2PhiPsi to break circular dependency."""
    global _G2PhiPsi
    if _G2PhiPsi is None:
        import importlib

        _G2PhiPsi = importlib.import_module(
            "kagami.core.world_model.equivariance.g2_exact"
        ).G2PhiPsi
    return _G2PhiPsi


class G2InvariantPooling(nn.Module):
    """Pool octonion features using G₂-invariant quantities.

    Extracts features that are guaranteed to be invariant under G₂ transformations:
    1. Norm ||x||
    2. Inner products ⟨x, y⟩
    3. Triple products φ(x, y, z)
    4. Cross product norms ||x × y||

    These pooling operations preserve G₂ structure and provide equivariant features.
    """

    def __init__(
        self,
        include_triple_products: bool = True,
        include_cross_norms: bool = True,
    ) -> None:
        """Initialize G₂-invariant pooling.

        Args:
            include_triple_products: Include φ(·, ·, ·) features (more expressive but slower)
            include_cross_norms: Include ||x × y|| features
        """
        super().__init__()
        self.include_triple_products = include_triple_products
        self.include_cross_norms = include_cross_norms

        # G₂ structures (φ, ψ, cross product) - lazy import to avoid circular dependency
        self.g2_struct = _get_g2_phi_psi()()

    def forward(
        self,
        x: torch.Tensor,
        y: torch.Tensor | None = None,
        z: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Extract G₂-invariant features from octonion vectors.

        Args:
            x: Primary vector [..., 7] in Im(𝕆)
            y: Optional second vector [..., 7]
            z: Optional third vector [..., 7]

        Returns:
            Invariant features [..., num_features]
        """
        features = []

        # 1. Norm of x (always included)
        norm_x = torch.norm(x, dim=-1, keepdim=True)
        features.append(norm_x)

        if y is not None:
            # 2. Inner product ⟨x, y⟩
            inner_xy = torch.sum(x * y, dim=-1, keepdim=True)
            features.append(inner_xy)

            # 3. Norm of y
            norm_y = torch.norm(y, dim=-1, keepdim=True)
            features.append(norm_y)

            if self.include_cross_norms:
                # 4. Cross product norm ||x × y||
                cross_xy = self.g2_struct.cross(x, y)
                norm_cross = torch.norm(cross_xy, dim=-1, keepdim=True)
                features.append(norm_cross)

            if z is not None:
                # 5. Inner product ⟨x, z⟩
                inner_xz = torch.sum(x * z, dim=-1, keepdim=True)
                features.append(inner_xz)

                # 6. Inner product ⟨y, z⟩
                inner_yz = torch.sum(y * z, dim=-1, keepdim=True)
                features.append(inner_yz)

                # 7. Norm of z
                norm_z = torch.norm(z, dim=-1, keepdim=True)
                features.append(norm_z)

                if self.include_triple_products:
                    # 8. Triple product φ(x, y, z) - EXACT G₂ invariant!
                    # This is the associative 3-form evaluation
                    # Shape: [..., 7] x [..., 7] x [..., 7] → [..., 1]

                    # φ(x, y, z) = sum over all indices φ_ijk x_i y_j z_k
                    # Use einsum for efficiency
                    phi_xyz = torch.einsum("ijk,...i,...j,...k->...", self.g2_struct.phi, x, y, z)
                    features.append(phi_xyz.unsqueeze(-1))

                    # 9. φ(x, x, y) - captures x-direction structure
                    phi_xxy = torch.einsum("ijk,...i,...j,...k->...", self.g2_struct.phi, x, x, y)
                    features.append(phi_xxy.unsqueeze(-1))

                    # 10. φ(y, y, z) - captures y-direction structure
                    phi_yyz = torch.einsum("ijk,...i,...j,...k->...", self.g2_struct.phi, y, y, z)
                    features.append(phi_yyz.unsqueeze(-1))

        # Concatenate all invariant features
        invariants = torch.cat(features, dim=-1)

        return invariants


class G2InvariantFeatureExtractor(nn.Module):
    """Extract rich G₂-invariant features from octonion sequences.

    Takes a sequence of octonion vectors and extracts invariant features
    by considering pairs and triplets within the sequence.
    """

    def __init__(
        self,
        num_neighbors: int = 3,
        output_dim: int = 64,
        include_triple_products: bool = True,
    ) -> None:
        """Initialize feature extractor.

        Args:
            num_neighbors: Number of neighbors to consider for each point
            output_dim: Output feature dimension
            include_triple_products: Include expensive φ(·, ·, ·) features
        """
        super().__init__()
        self.num_neighbors = num_neighbors
        self.include_triple_products = include_triple_products

        # Invariant pooling
        self.pooling = G2InvariantPooling(
            include_triple_products=include_triple_products,
            include_cross_norms=True,
        )

        # MLP to process invariant features - will be created on first forward
        self.feature_mlp: nn.Sequential | None = None
        self.output_dim = output_dim
        self._mlp_hidden = 128

    def _estimate_num_features(self) -> int:
        """Estimate number of invariant features produced."""
        # Use a conservative upper bound that accounts for variation
        # Base: norm (1)
        # Per neighbor pair: norm + inner + cross_norm = 4
        # Per neighbor triplet with phi: +3
        # Multiply by 2x for conservative estimate (boundary effects)

        n = 1  # Self norm
        n += 4 * self.num_neighbors * 2  # Pairwise features (conservative)

        if self.include_triple_products:
            n += 3 * self.num_neighbors * 2  # Triple products (conservative)

        # Round up to nearest 32 for efficiency
        n = ((n + 31) // 32) * 32

        return n

    def forward(self, x_seq: torch.Tensor) -> torch.Tensor:
        """Extract G₂-invariant features from octonion sequence.

        Args:
            x_seq: Sequence of octonion vectors [batch, seq_len, 7]

        Returns:
            Invariant features [batch, seq_len, output_dim]
        """
        _batch_size, seq_len, _ = x_seq.shape

        # Extract invariants for each position
        invariant_features = []

        for i in range(seq_len):
            x_i = x_seq[:, i, :]  # [batch, 7]

            # Gather neighbors
            neighbors = []
            for offset in range(1, self.num_neighbors + 1):
                # Previous neighbor
                if i - offset >= 0:
                    neighbors.append(x_seq[:, i - offset, :])
                # Next neighbor
                if i + offset < seq_len:
                    neighbors.append(x_seq[:, i + offset, :])

            # Extract invariants for this position
            pos_invariants = []

            # Self norm
            self_inv = self.pooling(x_i)
            pos_invariants.append(self_inv)

            # Pairwise and triple invariants with neighbors
            for j, neighbor in enumerate(neighbors):
                # Include third neighbor for triple products if available
                z_neighbor = neighbors[j + 1] if j + 1 < len(neighbors) else None

                inv = self.pooling(x_i, neighbor, z_neighbor)
                pos_invariants.append(inv)

            # Concatenate and process
            pos_features = torch.cat(pos_invariants, dim=-1)
            invariant_features.append(pos_features)

        # Pad features to same size (neighbors vary at boundaries)
        max_features = max(f.shape[-1] for f in invariant_features)
        padded_features = []
        for f in invariant_features:
            if f.shape[-1] < max_features:
                padding = torch.zeros(
                    *f.shape[:-1], max_features - f.shape[-1], device=f.device, dtype=f.dtype
                )
                f = torch.cat([f, padding], dim=-1)
            padded_features.append(f)

        # Stack all positions
        invariants = torch.stack(padded_features, dim=1)  # [batch, seq_len, n_features]

        # Create MLP on first forward (now we know actual feature dimension)
        if self.feature_mlp is None:
            actual_features = invariants.shape[-1]
            self.feature_mlp = nn.Sequential(
                nn.Linear(actual_features, self._mlp_hidden),
                nn.LayerNorm(self._mlp_hidden),
                nn.GELU(),
                nn.Dropout(0.1),
                nn.Linear(self._mlp_hidden, self.output_dim),
            ).to(invariants.device)

        # Process through MLP (None check for type safety)
        if self.feature_mlp is None:
            raise RuntimeError("Feature MLP should be initialized but is None")
        features = self.feature_mlp(invariants)

        return cast(torch.Tensor, features)


class G2InvariantAttentionPooling(nn.Module):
    """Attention-based pooling using G₂-invariant similarity.

    Instead of learned query/key/value, uses G₂-invariant quantities
    to compute attention weights. This guarantees G₂ equivariance.
    """

    def __init__(
        self,
        temperature: float = 1.0,
    ) -> None:
        """Initialize invariant attention pooling.

        Args:
            temperature: Temperature for softmax attention
        """
        super().__init__()
        self.temperature = temperature
        self.g2_struct = _get_g2_phi_psi()()

    def forward(
        self,
        x_seq: torch.Tensor,
        query: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Pool sequence using G₂-invariant attention.

        Args:
            x_seq: Sequence [batch, seq_len, 7] in Im(𝕆)
            query: Optional query vector [batch, 7]. If None, use mean.

        Returns:
            Pooled vector [batch, 7]
        """
        _batch_size, _seq_len, _ = x_seq.shape

        # Default query: mean vector
        if query is None:
            query = torch.mean(x_seq, dim=1)  # [batch, 7]

        # Compute G₂-invariant similarities
        # Use inner product as similarity (G₂-invariant)
        similarities = torch.sum(
            query.unsqueeze(1) * x_seq,  # [batch, 1, 7] * [batch, seq_len, 7]
            dim=-1,  # → [batch, seq_len]
        )

        # Softmax to get attention weights
        attention_weights = torch.softmax(similarities / self.temperature, dim=-1)

        # Weighted sum (G₂-equivariant operation)
        pooled = torch.sum(
            attention_weights.unsqueeze(-1) * x_seq,  # [batch, seq_len, 1] * [batch, seq_len, 7]
            dim=1,  # → [batch, 7]
        )

        # Normalize back to S⁷
        pooled = pooled / torch.norm(pooled, dim=-1, keepdim=True).clamp_min(1e-8)

        return cast(torch.Tensor, pooled)
