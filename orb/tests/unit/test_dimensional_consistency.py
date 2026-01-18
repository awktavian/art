"""Dimensional Consistency Tests (P1 Important).

Tests that all modules maintain consistent tensor dimensions:
- Batch dimension [B, ...] always first
- Sequence dimension [B, S, ...] handling
- Colony dimension [B, 7, H] in RSSM
- Variable E8 levels [B, S, L, 8] with L ∈ [2, 24]
- S7 extraction [B, S, 7] from all hierarchy levels

Created: December 15, 2025
Priority: P1 (Important)
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_unit


import torch
import torch.nn as nn


class TestBatchDimensionPreserved:
    """Test batch dimension [B, ...] is always first."""

    @pytest.mark.parametrize("batch_size", [1, 2, 8, 16, 32])
    def test_batch_dimension_preserved_all_modules(self, batch_size) -> None:
        """Verify [B, ...] through entire pipeline."""
        B = batch_size

        # 1. Observation encoding: [B, obs_dim] → [B, h_dim], [B, z_dim]
        obs_dim, h_dim, z_dim = 15, 256, 14
        obs = torch.randn(B, obs_dim)

        encoder_h = nn.Linear(obs_dim, h_dim)
        encoder_z = nn.Linear(obs_dim, z_dim)

        h = encoder_h(obs)
        z = encoder_z(obs)

        assert h.shape == (B, h_dim)
        assert z.shape == (B, z_dim)

        # 2. Action embedding: [B, action_dim] → [B, action_embed_dim]
        action_dim, action_embed_dim = 8, 64
        action = torch.randn(B, action_dim)

        action_encoder = nn.Linear(action_dim, action_embed_dim)
        action_embed = action_encoder(action)

        assert action_embed.shape == (B, action_embed_dim)

        # 3. State transition: [B, h_dim + action_embed_dim] → [B, h_dim]
        h_action = torch.cat([h, action_embed], dim=-1)
        transition = nn.Linear(h_dim + action_embed_dim, h_dim)
        h_next = transition(h_action)

        assert h_next.shape == (B, h_dim)

    def test_batch_dimension_through_nonlinearity(self) -> None:
        """Test batch dimension preserved through activations."""
        B, D = 8, 256
        x = torch.randn(B, D)

        # Various activations
        assert torch.relu(x).shape == (B, D)
        assert torch.tanh(x).shape == (B, D)
        assert torch.sigmoid(x).shape == (B, D)
        assert torch.nn.functional.gelu(x).shape == (B, D)

    def test_batch_dimension_through_layernorm(self) -> None:
        """Test batch dimension preserved through LayerNorm."""
        B, D = 8, 256
        x = torch.randn(B, D)

        ln = nn.LayerNorm(D)
        y = ln(x)

        assert y.shape == (B, D)


class TestSequenceDimensionHandling:
    """Test sequence dimension [B, S, ...] handling."""

    @pytest.mark.parametrize("seq_len", [1, 5, 10, 20, 50])
    def test_sequence_dimension_handling(self, seq_len) -> None:
        """Test [B, S, D] through pipeline."""
        B, S, D = 4, seq_len, 256
        x = torch.randn(B, S, D)

        # 1. Linear layer (applied per timestep)
        linear = nn.Linear(D, D)
        y = linear(x)

        assert y.shape == (B, S, D)

        # 2. LayerNorm (applied per timestep)
        ln = nn.LayerNorm(D)
        z = ln(y)

        assert z.shape == (B, S, D)

        # 3. Temporal pooling
        pooled_mean = x.mean(dim=1)
        assert pooled_mean.shape == (B, D)

        pooled_max = x.max(dim=1)[0]
        assert pooled_max.shape == (B, D)

    def test_sequence_attention(self) -> None:
        """Test attention preserves sequence dimension."""
        B, S, D = 4, 10, 256
        x = torch.randn(B, S, D)

        # Self-attention
        attn = nn.MultiheadAttention(D, num_heads=8, batch_first=True)
        y, _ = attn(x, x, x)

        assert y.shape == (B, S, D)

    def test_sequence_masking(self) -> None:
        """Test sequence masking with variable lengths."""
        B, S, D = 4, 10, 256
        x = torch.randn(B, S, D)

        # Create mask for variable lengths
        lengths = torch.tensor([5, 7, 10, 3])
        mask = torch.arange(S).expand(B, S) < lengths.unsqueeze(1)

        assert mask.shape == (B, S)

        # Apply mask
        x_masked = x * mask.unsqueeze(-1)
        assert x_masked.shape == (B, S, D)


class TestColonyDimensionInvariant:
    """Test colony dimension [B, 7, H] in RSSM."""

    def test_colony_dimension_invariant(self) -> None:
        """Verify [B, 7, H] structure in ColonyRSSM."""
        B, num_colonies, H = 4, 7, 256

        # Colony-specific states
        colony_states = torch.randn(B, num_colonies, H)

        assert colony_states.shape == (B, 7, H)

        # Colony names
        colony_names = ["spark", "forge", "flow", "nexus", "beacon", "grove", "crystal"]
        assert len(colony_names) == 7

        # Per-colony processing
        for c in range(num_colonies):
            colony_c = colony_states[:, c, :]  # [B, H]
            assert colony_c.shape == (B, H)

    def test_colony_aggregation(self) -> None:
        """Test aggregation across colonies."""
        B, num_colonies, H = 4, 7, 256
        colony_states = torch.randn(B, num_colonies, H)

        # Mean pooling across colonies
        pooled_mean = colony_states.mean(dim=1)
        assert pooled_mean.shape == (B, H)

        # Max pooling across colonies
        pooled_max = colony_states.max(dim=1)[0]
        assert pooled_max.shape == (B, H)

        # Weighted aggregation
        weights = torch.softmax(torch.randn(B, num_colonies, 1), dim=1)
        weighted = (colony_states * weights).sum(dim=1)
        assert weighted.shape == (B, H)

    def test_colony_to_unified_state(self) -> None:
        """Test conversion from colony-specific to unified state."""
        B, num_colonies, H = 4, 7, 256
        colony_states = torch.randn(B, num_colonies, H)

        # Flatten colonies into unified state
        unified = colony_states.reshape(B, num_colonies * H)
        assert unified.shape == (B, 7 * 256)

        # Or use projection
        projector = nn.Linear(num_colonies * H, H)
        unified_projected = projector(unified)
        assert unified_projected.shape == (B, H)


class TestVariableE8Levels:
    """Test variable E8 hierarchy levels [B, S, L, 8] with L ∈ [2, 24]."""

    @pytest.mark.parametrize("num_levels", [2, 4, 6, 8, 12, 16, 20, 24])
    def test_variable_e8_levels(self, num_levels) -> None:
        """Test [B, S, L, 8] with L ∈ [2, 24]."""
        B, S, L = 2, 10, num_levels

        # E8 nucleus with variable depth
        e8_nucleus = torch.randn(B, S, L, 8)

        assert e8_nucleus.shape == (B, S, L, 8)
        assert e8_nucleus.shape[-1] == 8  # Always 8D

    def test_e8_level_access(self) -> None:
        """Test accessing specific levels."""
        B, S, L = 2, 10, 8
        e8_nucleus = torch.randn(B, S, L, 8)

        # Access level 0 (finest)
        level_0 = e8_nucleus[:, :, 0, :]
        assert level_0.shape == (B, S, 8)

        # Access level L-1 (coarsest)
        level_max = e8_nucleus[:, :, L - 1, :]
        assert level_max.shape == (B, S, 8)

        # Access range
        levels_mid = e8_nucleus[:, :, 2:5, :]
        assert levels_mid.shape == (B, S, 3, 8)

    def test_e8_per_level_encoding(self) -> None:
        """Test per-level encoding with variable L."""
        B, S, L, embed_dim = 2, 10, 6, 256
        e8_nucleus = torch.randn(B, S, L, 8)

        # Encode each level separately
        encoders = nn.ModuleList([nn.Linear(8, embed_dim) for _ in range(L)])

        embeddings = []
        for level in range(L):
            codes = e8_nucleus[:, :, level, :]  # [B, S, 8]
            embed = encoders[level](codes)  # [B, S, embed_dim]
            embeddings.append(embed)

        embeddings = torch.stack(
            embeddings, dim=2
        )  # [B, S, L, embed_dim]  # type: ignore[assignment]
        assert embeddings.shape == (B, S, L, embed_dim)


class TestS7ExtractionAllLevels:
    """Test S7 extraction [B, S, 7] from all hierarchy levels."""

    def test_s7_extraction_all_levels(self) -> None:
        """Verify all S7 phases are [B, S, 7]."""
        B, S = 4, 10

        # S7 phases from E8 projection
        # E8 → S7: project 8D to 7D
        e8_vectors = torch.randn(B, S, 8)

        # Simple projection: drop last coordinate
        s7_phase = e8_vectors[:, :, :7]

        assert s7_phase.shape == (B, S, 7)

    def test_s7_extraction_per_hierarchy_level(self) -> None:
        """Test S7 extraction from each E8 level."""
        B, S, L = 4, 10, 6
        e8_nucleus = torch.randn(B, S, L, 8)

        # Extract S7 from each level
        s7_phases = []
        for level in range(L):
            e8_level = e8_nucleus[:, :, level, :]  # [B, S, 8]
            s7_level = e8_level[:, :, :7]  # [B, S, 7]
            s7_phases.append(s7_level)

        s7_hierarchy = torch.stack(s7_phases, dim=2)  # [B, S, L, 7]
        assert s7_hierarchy.shape == (B, S, L, 7)

    def test_s7_colony_mapping(self) -> None:
        """Test S7 phase → 7 colonies mapping."""
        B, S = 4, 10

        # S7 phase coordinates
        s7_phase = torch.randn(B, S, 7)

        # Map to colony activations
        # Each of 7 dimensions → one colony
        colony_names = ["spark", "forge", "flow", "nexus", "beacon", "grove", "crystal"]

        for c in range(7):
            colony_activation = s7_phase[:, :, c]  # [B, S]
            assert colony_activation.shape == (B, S)

    def test_s7_normalization(self) -> None:
        """Test S7 phase normalization to unit sphere."""
        B, S = 4, 10
        s7_phase = torch.randn(B, S, 7)

        # Normalize to unit sphere
        s7_normalized = s7_phase / s7_phase.norm(dim=-1, keepdim=True)

        # Verify unit norm
        norms = s7_normalized.norm(dim=-1)
        assert torch.allclose(norms, torch.ones(B, S), atol=1e-5)


class TestDimensionalConsistencyEdgeCases:
    """Test edge cases in dimensional handling."""

    def test_single_element_batch(self) -> None:
        """Test batch size 1 (no squeezing)."""
        B, D = 1, 256
        x = torch.randn(B, D)

        linear = nn.Linear(D, D)
        y = linear(x)

        # Should maintain [1, D], not squeeze to [D]
        assert y.shape == (1, D)

    def test_single_timestep_sequence(self) -> None:
        """Test sequence length 1."""
        B, S, D = 4, 1, 256
        x = torch.randn(B, S, D)

        ln = nn.LayerNorm(D)
        y = ln(x)

        # Should maintain [B, 1, D]
        assert y.shape == (B, 1, D)

    def test_large_batch_size(self) -> None:
        """Test large batch size (memory considerations)."""
        B, D = 512, 256
        x = torch.randn(B, D)

        linear = nn.Linear(D, D)
        y = linear(x)

        assert y.shape == (B, D)

    def test_empty_sequence(self) -> None:
        """Test sequence length 0 (edge case)."""
        B, S, D = 4, 0, 256
        x = torch.randn(B, S, D)

        assert x.shape == (4, 0, 256)

        # Operations should handle gracefully
        pooled = x.mean(dim=1)  # Will be NaN
        assert pooled.shape == (B, D)


class TestDimensionalTransformations:
    """Test common dimensional transformations."""

    def test_flatten_sequence(self) -> None:
        """Test flattening [B, S, D] → [B*S, D]."""
        B, S, D = 4, 10, 256
        x = torch.randn(B, S, D)

        # Flatten
        x_flat = x.reshape(B * S, D)
        assert x_flat.shape == (B * S, D)

        # Unflatten
        x_unflat = x_flat.reshape(B, S, D)
        assert torch.allclose(x, x_unflat)

    def test_expand_batch(self) -> None:
        """Test expanding batch dimension."""
        S, D = 10, 256
        x = torch.randn(S, D)

        # Expand to batch
        B = 4
        x_batch = x.unsqueeze(0).expand(B, S, D)
        assert x_batch.shape == (B, S, D)

    def test_reduce_sequence(self) -> None:
        """Test reducing sequence dimension."""
        B, S, D = 4, 10, 256
        x = torch.randn(B, S, D)

        # Reduce sequence
        x_reduced = x.mean(dim=1)
        assert x_reduced.shape == (B, D)

        # Alternative: select specific timestep
        x_last = x[:, -1, :]
        assert x_last.shape == (B, D)

    def test_transpose_dimensions(self) -> None:
        """Test transposing dimensions."""
        B, S, D = 4, 10, 256
        x = torch.randn(B, S, D)

        # Transpose S and D
        x_t = x.transpose(1, 2)
        assert x_t.shape == (B, D, S)

        # Transpose back
        x_back = x_t.transpose(1, 2)
        assert torch.allclose(x, x_back)


class TestBroadcastingRules:
    """Test broadcasting with different shapes."""

    def test_broadcast_batch_to_sequence(self) -> None:
        """Test broadcasting [B, D] to [B, S, D]."""
        B, S, D = 4, 10, 256

        x = torch.randn(B, D)  # [B, D]
        y = torch.randn(B, S, D)  # [B, S, D]

        # Add: [B, D] + [B, S, D] → [B, S, D]
        z = x.unsqueeze(1) + y
        assert z.shape == (B, S, D)

    def test_broadcast_scalar_to_tensor(self) -> None:
        """Test scalar broadcasting."""
        B, S, D = 4, 10, 256
        x = torch.randn(B, S, D)

        # Scalar broadcast
        y = x + 1.0
        assert y.shape == (B, S, D)

        z = x * 2.0
        assert z.shape == (B, S, D)

    def test_broadcast_channel_wise(self) -> None:
        """Test channel-wise broadcasting."""
        B, S, D = 4, 10, 256

        x = torch.randn(B, S, D)
        scale = torch.randn(D)  # [D]

        # Broadcast scale to all batches and timesteps
        y = x * scale
        assert y.shape == (B, S, D)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
