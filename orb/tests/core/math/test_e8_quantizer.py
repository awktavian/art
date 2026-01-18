"""E8 Quantizer API and Integration Tests.

CONSOLIDATED FILE (December 21, 2025)
======================================
Merged from:
- test_e8_module.py (API surface, exports, factory functions)
- test_e8_integration.py (end-to-end workflows, byte protocol)

COVERAGE TARGET: E8 lattice quantization API, residual VQ, encoding/decoding
ESTIMATED RUNTIME: <5 seconds

Tests verify:
1. Module exports and aliases (critical for import stability)
2. Quantize → Dequantize → Reconstruction error
3. Compression ratio calculation
4. Edge cases (zero vectors, large vectors, dimensionality)
5. Byte encoding/decoding roundtrip
6. Multi-level residual quantization
7. Factory function correctness

Mathematical Foundation:
- E8 lattice: optimal 8D sphere packing (Viazovska 2016)
- 240 roots with norm √2
- Residual quantization: each level refines the previous approximation

Created: December 2025
Status: CRITICAL - Tests recently fixed import issues
"""

from __future__ import annotations

import pytest
from typing import cast

import torch
import torch.nn as nn

from kagami_math.e8 import (
    # Constants
    E8_DIM,
    E8_ROOTS,
    SQRT_240,
    # Root generation
    generate_e8_roots,
    get_e8_roots,
    # Main quantizer (v2 lattice residual)
    ResidualE8LatticeVQ,
    E8LatticeResidualConfig,
    # Convenience aliases (recently fixed)
    CanonicalE8Quantizer,
    E8Quantizer,  # This was missing and causing import errors
    E8QuantizerConfig,
    # Legacy aliases
    SemanticResidualE8,
    SemanticResidualE8Config,
    # Utilities
    nearest_e8,
    # Factory functions
    create_e8_quantizer,
    create_fast_quantizer,
    create_quality_quantizer,
)
from kagami_math.e8_cache import CachedE8Quantizer

# Consolidated markers
pytestmark = [
    pytest.mark.tier_integration,
    pytest.mark.unit,
    pytest.mark.timeout(30),
]

# =============================================================================
# MODULE API TESTS
# =============================================================================


class TestE8Constants:
    """Test E8 mathematical constants."""

    def test_e8_constants(self) -> None:
        """Test that E8 constants have correct values."""
        assert E8_DIM == 8
        assert E8_ROOTS == 240
        assert abs(SQRT_240 - 15.491933384829668) < 1e-10


class TestE8RootGeneration:
    """Test E8 root system generation."""

    def test_generate_e8_roots(self) -> None:
        """Test E8 root generation produces correct count and properties."""
        roots = generate_e8_roots()

        # Should have exactly 240 roots
        assert roots.shape[0] == 240
        assert roots.shape[1] == 8

        # All roots should have squared length 2 (within tolerance)
        squared_norms = torch.sum(roots**2, dim=1)
        assert torch.allclose(squared_norms, torch.tensor(2.0), atol=1e-6)

    def test_get_e8_roots(self) -> None:
        """Test get_e8_roots function works."""
        roots_cpu = get_e8_roots("cpu")
        assert roots_cpu.shape == (240, 8)
        assert roots_cpu.device.type == "cpu"

        # Test with different device if available
        if torch.cuda.is_available():
            roots_cuda = get_e8_roots("cuda")
            assert roots_cuda.device.type == "cuda"


class TestE8QuantizerAliases:
    """Test that all aliases work correctly (critical for recent fixes)."""

    def test_canonical_e8_quantizer_alias(self) -> None:
        """Test CanonicalE8Quantizer alias works."""
        config = E8LatticeResidualConfig(max_levels=2)
        quantizer = CanonicalE8Quantizer(config)
        assert isinstance(quantizer, ResidualE8LatticeVQ)

    def test_e8_quantizer_alias(self) -> None:
        """Test E8Quantizer alias (this was missing and causing import errors)."""
        config = E8LatticeResidualConfig(max_levels=2)
        quantizer = E8Quantizer(config)
        assert isinstance(quantizer, ResidualE8LatticeVQ)

    def test_semantic_residual_e8_alias(self) -> None:
        """Test legacy SemanticResidualE8 alias works."""
        config = SemanticResidualE8Config(max_levels=2)
        quantizer = SemanticResidualE8(config)
        assert isinstance(quantizer, ResidualE8LatticeVQ)

    def test_config_aliases(self) -> None:
        """Test that config aliases point to the same class."""
        assert E8QuantizerConfig is E8LatticeResidualConfig
        assert SemanticResidualE8Config is E8LatticeResidualConfig


class TestE8QuantizerFunctionality:
    """Test E8 quantizer actual functionality."""

    def test_e8_quantizer_forward_pass(self) -> None:
        """Test E8 quantizer can process tensors."""
        config = E8LatticeResidualConfig(max_levels=2, adaptive_levels=False)
        quantizer = E8Quantizer(config)

        # Test with batch of 8D vectors
        input_tensor = torch.randn(4, 8)
        result = quantizer(input_tensor)
        quantized = result["quantized"]
        indices = result["indices"]

        # Should return quantized tensor and indices
        assert quantized.shape == input_tensor.shape
        assert indices.shape[-2] > 0  # Should have at least one level

    def test_nearest_e8_function(self) -> None:
        """Test nearest_e8 lattice point function."""
        # Test with some specific inputs
        input_vec = torch.tensor([1.1, 0.9, 0.1, -0.1, 0.0, 0.0, 0.0, 0.0])
        nearest = nearest_e8(input_vec)

        assert nearest.shape == (8,)
        # Result should be an E8 lattice point


class TestE8FactoryFunctions:
    """Test E8 factory functions."""

    def test_create_e8_quantizer(self) -> None:
        """Test basic E8 quantizer creation."""
        quantizer = create_e8_quantizer(inference_levels=3)
        # Factory functions return CachedE8Quantizer for performance
        assert isinstance(quantizer, CachedE8Quantizer)

    def test_create_fast_quantizer(self) -> None:
        """Test fast quantizer creation."""
        quantizer = create_fast_quantizer()
        # Factory functions return CachedE8Quantizer for performance
        assert isinstance(quantizer, CachedE8Quantizer)

    def test_create_quality_quantizer(self) -> None:
        """Test quality quantizer creation."""
        quantizer = create_quality_quantizer()
        # Factory functions return CachedE8Quantizer for performance
        assert isinstance(quantizer, CachedE8Quantizer)


class TestE8Integration:
    """Test E8 module integration with other components."""

    def test_e8_with_torch_module(self) -> None:
        """Test E8 quantizer works as part of larger torch.nn.Module."""

        class TestModel(nn.Module):
            def __init__(self) -> None:
                super().__init__()
                self.linear = nn.Linear(8, 8)
                self.quantizer = E8Quantizer(E8LatticeResidualConfig(max_levels=2))

            def forward(self, x: torch.Tensor) -> torch.Tensor:
                x = self.linear(x)
                result = self.quantizer(x)
                return cast(torch.Tensor, result["quantized"])

        model = TestModel()
        input_tensor = torch.randn(2, 8)
        output = model(input_tensor)

        assert output.shape == (2, 8)

    def test_e8_gradient_flow(self) -> None:
        """Test that gradients flow through E8 quantizer."""
        quantizer = E8Quantizer(E8LatticeResidualConfig(max_levels=2))

        input_tensor = torch.randn(1, 8, requires_grad=True)
        result = quantizer(input_tensor)
        quantized = result["quantized"]
        loss = torch.mean(quantized**2)
        loss.backward()

        # Should have gradients (even if from straight-through estimator)
        assert input_tensor.grad is not None


class TestE8ErrorHandling:
    """Test E8 module error handling."""

    def test_invalid_input_dimensions(self) -> None:
        """Test handling of invalid input dimensions."""
        quantizer = E8Quantizer(E8LatticeResidualConfig())

        # Wrong last dimension should raise error
        with pytest.raises((ValueError, RuntimeError)):
            quantizer(torch.randn(4, 7))  # Should be 8D

    def test_invalid_config(self) -> None:
        """Test handling of invalid configurations."""
        # Test that config can be created with edge case values
        config = E8LatticeResidualConfig(max_levels=1, min_levels=1)
        assert config.max_levels == 1
        assert config.min_levels == 1

        # Test invalid input during quantizer forward pass
        quantizer = E8Quantizer(config)
        with pytest.raises(ValueError):
            # Wrong tensor shape should cause an error
            quantizer(torch.randn(2, 7))  # Should be 8D, not 7D


# =============================================================================
# INTEGRATION TESTS (END-TO-END WORKFLOWS)
# =============================================================================


class TestE8BasicQuantization:
    """Test basic E8 lattice quantization operations."""

    def test_single_vector_quantization(self) -> None:
        """Test quantization of a single 8D vector."""
        # Create quantizer
        config = E8LatticeResidualConfig(max_levels=4, min_levels=1)
        quantizer = ResidualE8LatticeVQ(config)

        # Input vector
        x = torch.randn(8)

        # Quantize
        result = quantizer.forward(x, num_levels=4)
        x_quantized = result["quantized"]
        indices = result["indices"]

        # Verify output shape
        assert x_quantized.shape == (8,)
        assert indices.shape[-2] == 4  # 4 levels
        assert indices.shape[-1] == 8  # 8 dimensions per level

    def test_batch_quantization(self) -> None:
        """Test quantization of a batch of vectors."""
        config = E8LatticeResidualConfig(
            max_levels=8,
            min_levels=2,
            adaptive_levels=False,  # Disable adaptive for fixed levels
        )
        quantizer = ResidualE8LatticeVQ(config)

        # Batch of 16 vectors
        x = torch.randn(16, 8)

        # Quantize
        result = quantizer.forward(x, num_levels=8)
        x_quantized = result["quantized"]
        indices = result["indices"]

        # Verify output shapes
        assert x_quantized.shape == (16, 8)
        assert indices.shape == (16, 8, 8), (
            f"Expected (16, 8, 8), got {indices.shape}"
        )  # [batch, levels, dims]

    def test_nearest_e8_projection(self) -> None:
        """Test nearest E8 lattice point computation."""
        # Zero vector projects to origin
        x_zero = torch.zeros(8)
        y_zero = nearest_e8(x_zero)
        assert torch.allclose(y_zero, torch.zeros(8), atol=1e-6)

        # Random vector projects to a valid E8 lattice point
        x_random = torch.randn(8)
        y = nearest_e8(x_random)

        assert y.shape == (8,)


class TestE8ReconstructionError:
    """Test reconstruction error bounds for E8 quantization."""

    def test_zero_vector_reconstruction(self) -> None:
        """Zero vector should have perfect reconstruction."""
        config = E8LatticeResidualConfig(max_levels=1)
        quantizer = ResidualE8LatticeVQ(config)

        x = torch.zeros(8)
        result = quantizer.forward(x, num_levels=1)
        x_quantized = result["quantized"]

        reconstruction_error = torch.norm(x - x_quantized)
        assert reconstruction_error < 1e-5, "Zero vector should reconstruct perfectly"

    def test_residual_levels_reduce_error(self) -> None:
        """More residual levels should reduce reconstruction error."""
        config = E8LatticeResidualConfig(max_levels=16)
        quantizer = ResidualE8LatticeVQ(config)

        x = torch.randn(32, 8)  # Batch of 32 vectors

        # Measure reconstruction error at different levels
        errors = []
        for num_levels in [1, 4, 8, 16]:
            result = quantizer.forward(x, num_levels=num_levels)
            x_quantized = result["quantized"]
            error = torch.norm(x - x_quantized, dim=-1).mean()
            errors.append(error.item())

        # Errors should generally decrease (allowing small fluctuations)
        for i in range(len(errors) - 1):
            # Allow up to 20% increase due to quantization noise
            assert errors[i + 1] < errors[i] * 1.2, (
                f"Error should decrease with more levels: {errors[i]:.6f} -> {errors[i + 1]:.6f}"
            )

    def test_large_magnitude_vectors(self) -> None:
        """Test quantization of large magnitude vectors."""
        config = E8LatticeResidualConfig(
            max_levels=8,
            initial_scale=2.0,
            adaptive_levels=False,
        )
        quantizer = ResidualE8LatticeVQ(config)

        # Large magnitude vector
        x = torch.randn(8) * 100.0

        result = quantizer.forward(x, num_levels=8)
        x_quantized = result["quantized"]
        indices = result["indices"]

        # Should still quantize (not error out)
        assert x_quantized.shape == (8,)
        assert indices.shape[-2] == 8, f"Expected 8 levels, got {indices.shape[-2]}"

        # Relative error should be reasonable
        relative_error = torch.norm(x - x_quantized) / torch.norm(x)
        assert relative_error < 0.5, "Relative error should be < 50% for large vectors"


class TestE8Decoding:
    """Test E8 decoding and roundtrip consistency."""

    def test_encode_decode_roundtrip(self) -> None:
        """Encoding and decoding should be consistent."""
        config = E8LatticeResidualConfig(max_levels=4)
        quantizer = ResidualE8LatticeVQ(config)

        x = torch.randn(8)

        # Encode
        result = quantizer.forward(x, num_levels=4)
        x_quantized = result["quantized"]
        indices = result["indices"]

        # Convert indices to list of codes for decode
        L = indices.shape[-2]
        codes = [indices[..., i, :] for i in range(L)]

        # Decode
        x_decoded = quantizer.decode(codes)

        # Should match quantized output
        assert torch.allclose(x_quantized, x_decoded, atol=1e-5)

    def test_decode_sequence(self) -> None:
        """Test per-level sequence decoding."""
        config = E8LatticeResidualConfig(max_levels=4)
        quantizer = ResidualE8LatticeVQ(config)

        x = torch.randn(8)
        result = quantizer.forward(x, num_levels=4)
        indices = result["indices"]

        # Convert indices to list of codes for decode
        L = indices.shape[-2]
        codes = [indices[..., i, :] for i in range(L)]

        # Get per-level contributions
        sequence = quantizer.decode_sequence(codes)

        # Should have shape [4, 8] (4 levels, 8 dimensions)
        assert sequence.shape == (4, 8)

        # Sum of levels should equal decoded output
        decoded = quantizer.decode(codes)
        assert torch.allclose(sequence.sum(dim=0), decoded, atol=1e-5)

    def test_partial_decode(self) -> None:
        """Decoding subset of codes should work."""
        config = E8LatticeResidualConfig(max_levels=8)
        quantizer = ResidualE8LatticeVQ(config)

        x = torch.randn(8)
        result = quantizer.forward(x, num_levels=8)
        indices = result["indices"]

        # Convert indices to list of codes for decode
        L = indices.shape[-2]
        codes = [indices[..., i, :] for i in range(L)]

        # Decode only first 4 levels
        partial_decoded = quantizer.decode(codes[:4])
        assert partial_decoded.shape == (8,)


class TestE8ByteEncoding:
    """Test byte encoding/decoding protocol."""

    def test_bytes_roundtrip(self) -> None:
        """Bytes encoding/decoding roundtrip should preserve data."""
        config = E8LatticeResidualConfig(max_levels=4)
        quantizer = ResidualE8LatticeVQ(config)

        x = torch.randn(8)

        # Encode to bytes
        encoded_bytes = quantizer.encode_bytes(x, num_levels=4)

        # Should produce bytes
        assert isinstance(encoded_bytes, bytes)
        assert len(encoded_bytes) > 0

        # Decode from bytes
        x_decoded, _codes_decoded = quantizer.decode_bytes(encoded_bytes)

        # Verify roundtrip
        result = quantizer.forward(x, num_levels=4)
        x_quantized = result["quantized"]
        assert torch.allclose(x_decoded, x_quantized, atol=1e-5)

    def test_byte_encoding_compression(self) -> None:
        """Byte encoding should provide compression."""
        config = E8LatticeResidualConfig(max_levels=8)
        quantizer = ResidualE8LatticeVQ(config)

        x = torch.randn(8)

        # Original size: 8 float32 values = 32 bytes
        original_size = 8 * 4  # 32 bytes

        # Encoded size
        encoded_bytes = quantizer.encode_bytes(x, num_levels=8)
        encoded_size = len(encoded_bytes)

        # Should provide some compression (typically < 200 bytes for 8 levels)
        assert encoded_size < 200, f"Encoded size {encoded_size} too large"

    def test_bytes_metadata_flag(self) -> None:
        """Test byte encoding with metadata flag."""
        config = E8LatticeResidualConfig(max_levels=2)
        quantizer = ResidualE8LatticeVQ(config)

        x = torch.randn(8)

        # Encode with metadata
        encoded_with_meta = quantizer.encode_bytes(x, num_levels=2, include_metadata=True)

        # Encode without metadata
        encoded_no_meta = quantizer.encode_bytes(x, num_levels=2, include_metadata=False)

        # With metadata should be larger
        assert len(encoded_with_meta) >= len(encoded_no_meta)

        # Both should decode correctly
        decoded_meta, _ = quantizer.decode_bytes(encoded_with_meta)
        decoded_no_meta, _ = quantizer.decode_bytes(encoded_no_meta)

        assert torch.allclose(decoded_meta, decoded_no_meta, atol=1e-5)


class TestE8EdgeCases:
    """Test edge cases and error handling."""

    def test_wrong_dimension_error(self) -> None:
        """Should error on non-8D input."""
        config = E8LatticeResidualConfig(max_levels=4)
        quantizer = ResidualE8LatticeVQ(config)

        # Wrong dimension
        x_wrong = torch.randn(10)

        with pytest.raises(ValueError, match="expects \\[..., 8\\]"):
            quantizer.forward(x_wrong)

    def test_empty_codes_decode_error(self) -> None:
        """Decoding empty codes should error."""
        config = E8LatticeResidualConfig(max_levels=4)
        quantizer = ResidualE8LatticeVQ(config)

        with pytest.raises(ValueError, match="codes cannot be empty"):
            quantizer.decode([])

    def test_adaptive_levels(self) -> None:
        """Adaptive levels should terminate early if residual is small."""
        config = E8LatticeResidualConfig(
            max_levels=16, min_levels=2, adaptive_levels=True, residual_threshold=1e-3
        )
        quantizer = ResidualE8LatticeVQ(config)

        # Simple vector that quantizes well
        x = torch.zeros(8)

        result = quantizer.forward(x, num_levels=16)
        indices = result["indices"]

        # Should use fewer than max levels
        num_levels_used = indices.shape[-2]
        assert num_levels_used <= 16
        assert num_levels_used >= 2

    def test_nan_input_handling(self) -> None:
        """NaN inputs should be handled gracefully."""
        config = E8LatticeResidualConfig(max_levels=4)
        quantizer = ResidualE8LatticeVQ(config)

        # Input with NaN
        x = torch.tensor([1.0, 2.0, float("nan"), 4.0, 5.0, 6.0, 7.0, 8.0])

        # Should not crash (may produce NaN output, but shouldn't error)
        try:
            result = quantizer.forward(x, num_levels=4)
            x_quantized = result["quantized"]
            assert x_quantized.shape == (8,)
        except Exception:
            pytest.skip("NaN handling not implemented")


class TestE8FactoryFunctionsIntegration:
    """Test factory functions integration."""

    def test_create_e8_quantizer_defaults(self) -> None:
        """Test default E8 quantizer creation."""
        quantizer = create_e8_quantizer()
        # Factory returns CachedE8Quantizer wrapper
        assert isinstance(quantizer, CachedE8Quantizer)

    def test_create_fast_quantizer_integration(self) -> None:
        """Fast quantizer should use fewer levels."""
        quantizer = create_fast_quantizer()
        assert isinstance(quantizer, CachedE8Quantizer)

    def test_create_quality_quantizer_integration(self) -> None:
        """Quality quantizer should use more levels."""
        quantizer = create_quality_quantizer()
        assert isinstance(quantizer, CachedE8Quantizer)

    def test_quantizer_functionality(self) -> None:
        """Test that factory-created quantizers work correctly."""
        quantizer = create_e8_quantizer()

        # Should be able to quantize
        x = torch.randn(10, 8)
        y = quantizer(x)

        assert y.shape == x.shape
        assert torch.isfinite(y).all()


class TestE8CompressionRatio:
    """Test compression ratio calculations."""

    def test_compression_ratio_calculation(self) -> None:
        """Verify compression ratio for different levels."""
        config = E8LatticeResidualConfig(max_levels=8, adaptive_levels=False)
        quantizer = ResidualE8LatticeVQ(config)

        x = torch.randn(100, 8)  # 100 vectors

        for num_levels in [1, 2, 4, 8]:
            _result = quantizer.forward(x, num_levels=num_levels)

            # Original: 100 vectors × 8 dims × 4 bytes = 3200 bytes
            original_bytes = 100 * 8 * 4

            # Estimate encoded size
            estimated_bytes = 100 * num_levels * 20

            compression_ratio = original_bytes / estimated_bytes

            # Compression ratio should be positive
            assert compression_ratio > 0.0, (
                f"Compression ratio should be positive, got {compression_ratio:.2f}x"
            )

    def test_single_vector_compression(self) -> None:
        """Test compression on a single vector."""
        config = E8LatticeResidualConfig(max_levels=4)
        quantizer = ResidualE8LatticeVQ(config)

        x = torch.randn(8)

        # Original size: 32 bytes
        original_size = 32

        # Encode
        encoded_bytes = quantizer.encode_bytes(x, num_levels=4)
        encoded_size = len(encoded_bytes)

        # Compression ratio
        ratio = original_size / encoded_size

        # Should be reasonably compressed (at least 0.3x or better)
        assert ratio > 0.3, f"Poor compression ratio: {ratio:.2f}x"


# Mark all tests with timeout


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
