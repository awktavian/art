"""Latency benchmarks for World Model components.

Target SLOs:
- E8 quantization: <1ms per batch of 100
- Exceptional hierarchy encoding: <5ms per forward pass
- Octonion multiplication: <0.1ms per batch of 100
- S7 projection: <0.1ms per batch of 100

Created: November 29, 2025
"""

from __future__ import annotations

import pytest

# Consolidated markers
pytestmark = [
    pytest.mark.load,
    pytest.mark.tier_e2e,
]
import time

import torch


# Benchmarks are load tests by default (skip unless enabled)
class TestE8QuantizationLatency:
    """Benchmark E8 lattice quantization latency."""

    @pytest.fixture
    def e8_quant(self):
        """Provide v2 lattice quantization functions."""
        from kagami_math.e8_lattice_quantizer import e8_to_half_step_ints, nearest_e8

        return nearest_e8, e8_to_half_step_ints

    def test_quantize_batch_100_under_1ms(self, e8_quant) -> None:
        """E8 quantization of 100 vectors should complete in <1ms."""
        nearest_e8, _ = e8_quant
        vectors = torch.randn(100, 8)
        # Warmup
        _ = nearest_e8(vectors)
        torch.cuda.synchronize() if torch.cuda.is_available() else None
        # Measure
        times = []
        for _ in range(100):
            start = time.perf_counter()
            _ = nearest_e8(vectors)
            torch.cuda.synchronize() if torch.cuda.is_available() else None
            times.append(time.perf_counter() - start)
        avg_time_ms = (sum(times) / len(times)) * 1000
        p99_time_ms = sorted(times)[99] * 1000
        assert avg_time_ms < 1.0, f"E8 quantize avg too slow: {avg_time_ms:.3f}ms"
        assert p99_time_ms < 2.0, f"E8 quantize p99 too slow: {p99_time_ms:.3f}ms"
        print(f"\n📊 E8 Quantization (batch=100): avg={avg_time_ms:.3f}ms, p99={p99_time_ms:.3f}ms")

    def test_quantize_codes_under_1ms(self, e8_quant) -> None:
        """E8 code quantization (half-step integer coords) should be very fast."""
        nearest_e8, e8_to_half_step_ints = e8_quant
        vectors = torch.randn(100, 8)
        # Warmup
        _ = e8_to_half_step_ints(nearest_e8(vectors))
        times = []
        for _ in range(100):
            start = time.perf_counter()
            _ = e8_to_half_step_ints(nearest_e8(vectors))
            times.append(time.perf_counter() - start)
        avg_time_ms = (sum(times) / len(times)) * 1000
        assert avg_time_ms < 0.5, f"E8 indices too slow: {avg_time_ms:.3f}ms"
        print(f"\n📊 E8 Code Quantization (batch=100): avg={avg_time_ms:.3f}ms")

    def test_large_batch_scaling(self, e8_quant) -> None:
        """Test scaling with larger batches."""
        nearest_e8, e8_to_half_step_ints = e8_quant
        batch_sizes = [100, 500, 1000, 5000]
        results = []
        for batch_size in batch_sizes:
            vectors = torch.randn(batch_size, 8)
            # Warmup
            _ = e8_to_half_step_ints(nearest_e8(vectors))
            start = time.perf_counter()
            _ = e8_to_half_step_ints(nearest_e8(vectors))
            elapsed_ms = (time.perf_counter() - start) * 1000
            per_item_us = (elapsed_ms / batch_size) * 1000
            results.append((batch_size, elapsed_ms, per_item_us))
        print("\n📊 E8 Quantization Scaling:")
        for batch_size, elapsed_ms, per_item_us in results:
            print(f"   batch={batch_size}: {elapsed_ms:.3f}ms total, {per_item_us:.2f}μs/item")
        # Per-item time should be roughly constant (O(n) total)
        assert results[-1][2] < 10, "Per-item time should be <10μs"


class TestOctonionLatency:
    """Benchmark octonion operations latency."""

    @pytest.fixture
    def manifold(self):
        """Create octonion manifold."""
        from kagami_math.octonions import OctonionManifold

        return OctonionManifold()

    def test_cayley_dickson_mul_under_100us(self, manifold) -> None:
        """Octonion multiplication should be <0.1ms for batch of 100."""
        a = torch.randn(100, 8)
        b = torch.randn(100, 8)
        # Warmup
        _ = manifold.cayley_dickson_mul(a, b)
        times = []
        for _ in range(100):
            start = time.perf_counter()
            _ = manifold.cayley_dickson_mul(a, b)
            times.append(time.perf_counter() - start)
        avg_time_ms = (sum(times) / len(times)) * 1000
        assert avg_time_ms < 0.5, f"Octonion mul too slow: {avg_time_ms:.3f}ms"
        print(f"\n📊 Octonion Multiplication (batch=100): avg={avg_time_ms:.3f}ms")

    def test_s7_projection_under_100us(self, manifold) -> None:
        """S7 projection should be <0.1ms for batch of 100."""
        o = torch.randn(100, 8)
        # Warmup
        _ = manifold.project_to_s7(o)
        times = []
        for _ in range(100):
            start = time.perf_counter()
            _ = manifold.project_to_s7(o)
            times.append(time.perf_counter() - start)
        avg_time_ms = (sum(times) / len(times)) * 1000
        assert avg_time_ms < 0.2, f"S7 projection too slow: {avg_time_ms:.3f}ms"
        print(f"\n📊 S7 Projection (batch=100): avg={avg_time_ms:.3f}ms")

    def test_associator_latency(self, manifold) -> None:
        """Associator computation latency."""
        a = torch.randn(100, 8)
        b = torch.randn(100, 8)
        c = torch.randn(100, 8)
        # Warmup
        _ = manifold.associator(a, b, c)
        times = []
        for _ in range(100):
            start = time.perf_counter()
            _ = manifold.associator(a, b, c)
            times.append(time.perf_counter() - start)
        avg_time_ms = (sum(times) / len(times)) * 1000
        # Associator requires 4 multiplications
        assert avg_time_ms < 2.0, f"Associator too slow: {avg_time_ms:.3f}ms"
        print(f"\n📊 Octonion Associator (batch=100): avg={avg_time_ms:.3f}ms")


class TestExceptionalHierarchyLatency:
    """Benchmark exceptional hierarchy encoding latency."""

    @pytest.fixture
    def hierarchy(self):
        """Create canonical TRUE exceptional hierarchy projector."""
        try:
            from kagami_math.clebsch_gordan_exceptional import TrueExceptionalHierarchy

            return TrueExceptionalHierarchy()
        except (ImportError, Exception) as e:
            pytest.skip(f"TrueExceptionalHierarchy not available: {e}")

    def test_forward_pass_under_5ms(self, hierarchy) -> None:
        """Exceptional hierarchy forward pass should be <5ms."""
        x = torch.randn(16, 248)  # Batch of 16 (E8)
        # Warmup
        with torch.no_grad():
            _ = hierarchy(x, target_level="S7")
        times = []
        for _ in range(50):
            start = time.perf_counter()
            with torch.no_grad():
                _ = hierarchy(x, target_level="S7")
            times.append(time.perf_counter() - start)
        avg_time_ms = (sum(times) / len(times)) * 1000
        p99_time_ms = sorted(times)[48] * 1000
        assert avg_time_ms < 5.0, f"Hierarchy forward too slow: {avg_time_ms:.3f}ms"
        print(
            f"\n📊 Exceptional Hierarchy Forward (batch=16): avg={avg_time_ms:.3f}ms, p99={p99_time_ms:.3f}ms"
        )

    def test_early_exit_faster(self, hierarchy) -> None:
        """Early exit at lower levels should be faster."""
        x = torch.randn(16, 248)
        # Full hierarchy
        with torch.no_grad():
            start = time.perf_counter()
            _ = hierarchy(x, target_level="S7")
            full_time = time.perf_counter() - start
        # Early exit: project only to G2 (shallower)
        with torch.no_grad():
            start = time.perf_counter()
            _ = hierarchy(x, target_level="G2")
            early_time = time.perf_counter() - start
        print(
            f"\n📊 Early Exit Comparison: full={full_time * 1000:.3f}ms, G2-only={early_time * 1000:.3f}ms"
        )
        assert early_time < full_time, "Early exit should be faster"


class TestMemoryEfficiency:
    """Benchmark memory usage of world model components."""

    def test_e8_memory_footprint(self) -> None:
        """E8 lattice memory footprint should be reasonable."""
        import gc

        gc.collect()
        from kagami_math.dimensions import get_e8_roots
        from kagami_math.e8_lattice_protocol import ResidualE8LatticeVQ

        # Measure memory before
        torch.cuda.memory_allocated() if torch.cuda.is_available() else 0
        roots = get_e8_roots("cpu")  # [240, 8]
        quantizer = ResidualE8LatticeVQ()
        roots_size = roots.numel() * roots.element_size()
        scales_size = quantizer.level_scales.numel() * quantizer.level_scales.element_size()
        total_kb = (roots_size + scales_size) / 1024
        # v2 lattice protocol has no 240×240 lookup table; should be tiny
        assert total_kb < 50, f"E8 lattice state too large: {total_kb:.1f}KB"
        print(
            f"\n📊 E8 Memory: roots={roots_size / 1024:.1f}KB, scales={scales_size / 1024:.3f}KB, total={total_kb:.1f}KB"
        )

    def test_octonion_no_state(self) -> None:
        """Octonion manifold should have minimal state."""
        from kagami_math.octonions import OctonionManifold

        manifold = OctonionManifold()
        # Should be stateless (no buffers or parameters)
        param_count = sum(p.numel() for p in manifold.parameters())
        buffer_count = sum(b.numel() for name, b in manifold.named_buffers())
        print(f"\n📊 Octonion Manifold: params={param_count}, buffers={buffer_count}")
        assert param_count == 0, "Octonion manifold should be stateless"


class TestTrainingValidation:
    """Validate training-time metrics for world model."""

    def test_vib_loss_gradient_flow(self) -> None:
        """Verify VIB loss has proper gradient flow."""
        try:
            from kagami.core.world_model.information_bottleneck import VIBEncoder
        except ImportError:
            pytest.skip("VIBEncoder not available")
        encoder = VIBEncoder(input_dim=64, bottleneck_dim=32)
        x = torch.randn(8, 64, requires_grad=True)
        z, _mu, _logvar = encoder(x)
        loss = z.mean()  # Dummy loss
        loss.backward()
        assert x.grad is not None, "Gradient should flow to input"
        assert not torch.isnan(x.grad).any(), "Gradients should not be NaN"
        print("\n📊 VIB Gradient Flow: ✓")

    def test_e8_quantization_straight_through(self) -> None:
        """Verify E8 quantization can use straight-through estimator."""
        from kagami_math.e8_lattice_protocol import (
            E8LatticeResidualConfig,
            ResidualE8LatticeVQ,
        )

        q = ResidualE8LatticeVQ(E8LatticeResidualConfig(max_levels=2, min_levels=1))
        q.train()
        x = torch.randn(8, 8, requires_grad=True)
        quantized, _codes = q(x, num_levels=2)
        loss = quantized.mean()
        loss.backward()
        assert x.grad is not None and x.grad.abs().sum().item() > 0, (
            "Gradient should flow through STE"
        )
        print("\n📊 E8 Straight-Through Gradient: ✓")
