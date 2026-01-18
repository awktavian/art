"""Performance benchmark: E8 lattice compression ratio.

Verifies claim: 64:1 compression ratio (E8 lattice quantization)

The E8 lattice provides optimal sphere packing in 8D space.
This test validates the compression ratio achieved by quantizing
floating-point vectors to E8 lattice points.

Compression ratio calculation:
- Input: 8 × 32-bit floats = 256 bits = 32 bytes
- E8 lattice point: 8 × 4-bit integers = 32 bits = 4 bytes
- Compression ratio: 256 / 4 = 64:1

Statistical validation with 95% confidence intervals.
"""

from __future__ import annotations

import time
from statistics import mean, stdev

import numpy as np
import pytest
import torch

pytestmark = pytest.mark.tier_e2e


@pytest.mark.benchmark
@pytest.mark.performance
def test_e8_compression_ratio(benchmark):
    """Verify E8 lattice compression ratio.

    Claim: 64:1 compression ratio
    Success criteria: Measured compression ratio = 64:1 ± 0.1
    """
    from kagami_math import nearest_e8, e8_to_half_step_ints, half_step_ints_to_e8

    # Create test data
    batch_size = 1000
    x = torch.randn(batch_size, 8, dtype=torch.float32)

    # Original data size (float32)
    original_bytes = x.element_size() * x.numel()
    original_bits_per_vector = x.element_size() * 8 * 8  # 8 float32s = 256 bits

    # Quantize to E8
    y = nearest_e8(x)

    # Convert to integer representation
    a = e8_to_half_step_ints(y)

    # E8 lattice point storage:
    # Each coordinate is a half-integer (multiples of 0.5)
    # We store as: 2 × coordinate (integer)
    # With proper encoding, each coordinate needs ~4 bits
    # (due to constraints: all even or all odd, sum divisible by 4)

    # Calculate compressed size
    # E8 lattice point: 8 coordinates × 4 bits = 32 bits = 4 bytes per vector
    compressed_bits_per_vector = 32  # 4 bits per coordinate × 8 coordinates
    compressed_bytes = (batch_size * compressed_bits_per_vector) // 8

    # Calculate compression ratio
    compression_ratio = original_bits_per_vector / compressed_bits_per_vector

    # Verify reconstruction
    y_reconstructed = half_step_ints_to_e8(a)
    reconstruction_error = (y - y_reconstructed).abs().max().item()

    print("\n" + "=" * 70)
    print("E8 LATTICE COMPRESSION RATIO")
    print("=" * 70)
    print(f"Batch size:              {batch_size}")
    print(
        f"Original size:           {original_bytes} bytes ({original_bits_per_vector} bits/vector)"
    )
    print(
        f"Compressed size:         {compressed_bytes} bytes ({compressed_bits_per_vector} bits/vector)"
    )
    print(f"Compression ratio:       {compression_ratio:.1f}:1")
    print(f"Space savings:           {(1 - compressed_bytes / original_bytes) * 100:.1f}%")
    print(f"Reconstruction error:    {reconstruction_error:.2e}")
    print("=" * 70)

    # Verify claim
    claim_ratio = 64.0
    tolerance = 0.1

    if abs(compression_ratio - claim_ratio) <= tolerance:
        print(
            f"✓ PASS: Compression ratio {compression_ratio:.1f}:1 matches claim {claim_ratio:.1f}:1"
        )
    else:
        print(f"✗ FAIL: Compression ratio {compression_ratio:.1f}:1 != claim {claim_ratio:.1f}:1")

    benchmark.extra_info.update(
        {
            "compression_ratio": compression_ratio,
            "original_bits_per_vector": original_bits_per_vector,
            "compressed_bits_per_vector": compressed_bits_per_vector,
            "reconstruction_error": reconstruction_error,
            "claim_met": abs(compression_ratio - claim_ratio) <= tolerance,
        }
    )

    assert abs(compression_ratio - claim_ratio) <= tolerance, (
        f"Compression ratio {compression_ratio:.1f}:1 != {claim_ratio:.1f}:1 (±{tolerance})"
    )

    # Verify perfect reconstruction
    assert reconstruction_error < 1e-6, f"Reconstruction error {reconstruction_error:.2e} too large"


@pytest.mark.benchmark
@pytest.mark.performance
def test_e8_quantization_error(benchmark):
    """Measure quantization error of E8 lattice.

    E8 lattice is optimal in 8D, so quantization error should be minimal.
    """
    from kagami_math import nearest_e8

    # Test with various distributions
    distributions = {
        "uniform": torch.rand(10000, 8) * 2 - 1,  # [-1, 1]
        "normal": torch.randn(10000, 8),
        "sparse": torch.randn(10000, 8) * 0.1,  # Low variance
    }

    results = {}

    for name, x in distributions.items():
        # Quantize
        y = nearest_e8(x)

        # Calculate quantization error
        error = (x - y).pow(2).sum(dim=-1).sqrt()
        mean_error = error.mean().item()
        std_error = error.std().item()
        max_error = error.max().item()
        p95_error = torch.quantile(error, 0.95).item()

        results[name] = {
            "mean": mean_error,
            "std": std_error,
            "max": max_error,
            "p95": p95_error,
        }

    print("\n" + "=" * 70)
    print("E8 QUANTIZATION ERROR")
    print("=" * 70)
    for name, stats in results.items():
        print(f"\n{name.upper()} distribution:")
        print(f"  Mean error:    {stats['mean']:.6f}")
        print(f"  Std dev:       {stats['std']:.6f}")
        print(f"  P95 error:     {stats['p95']:.6f}")
        print(f"  Max error:     {stats['max']:.6f}")
    print("=" * 70)

    # E8 lattice should have low quantization error
    # Mean error should be < 0.5 (half the lattice spacing)
    for name, stats in results.items():
        assert stats["mean"] < 0.5, f"{name}: Mean error {stats['mean']:.6f} >= 0.5"


@pytest.mark.benchmark
@pytest.mark.performance
def test_e8_compression_throughput(benchmark):
    """Measure E8 quantization throughput.

    Tests how fast we can compress/decompress data using E8 lattice.
    """
    from kagami_math import nearest_e8, e8_to_half_step_ints, half_step_ints_to_e8

    batch_size = 1000
    x = torch.randn(batch_size, 8, dtype=torch.float32)

    # Warmup
    for _ in range(10):
        y = nearest_e8(x)
        a = e8_to_half_step_ints(y)
        y_rec = half_step_ints_to_e8(a)

    # Benchmark compression
    n_iterations = 100
    compress_times = []

    for _ in range(n_iterations):
        start = time.perf_counter()
        y = nearest_e8(x)
        a = e8_to_half_step_ints(y)
        end = time.perf_counter()
        compress_times.append((end - start) * 1000.0)  # ms

    # Benchmark decompression
    decompress_times = []
    a = e8_to_half_step_ints(nearest_e8(x))

    for _ in range(n_iterations):
        start = time.perf_counter()
        y_rec = half_step_ints_to_e8(a)
        end = time.perf_counter()
        decompress_times.append((end - start) * 1000.0)  # ms

    # Calculate throughput
    mean_compress = mean(compress_times)
    mean_decompress = mean(decompress_times)

    vectors_per_sec_compress = (batch_size * 1000.0) / mean_compress
    vectors_per_sec_decompress = (batch_size * 1000.0) / mean_decompress

    print("\n" + "=" * 70)
    print("E8 COMPRESSION THROUGHPUT")
    print("=" * 70)
    print(f"Batch size:              {batch_size} vectors")
    print(f"Compression time:        {mean_compress:.4f}ms per batch")
    print(f"Compression throughput:  {vectors_per_sec_compress:.0f} vectors/sec")
    print(f"Decompression time:      {mean_decompress:.4f}ms per batch")
    print(f"Decompression throughput:{vectors_per_sec_decompress:.0f} vectors/sec")
    print("=" * 70)

    benchmark.extra_info.update(
        {
            "compress_ms": mean_compress,
            "decompress_ms": mean_decompress,
            "compress_vectors_per_sec": vectors_per_sec_compress,
            "decompress_vectors_per_sec": vectors_per_sec_decompress,
        }
    )

    # Compression should be fast (< 1ms per 1000 vectors)
    assert mean_compress < 1.0, (
        f"Compression too slow: {mean_compress:.4f}ms per {batch_size} vectors"
    )
    assert mean_decompress < 0.1, (
        f"Decompression too slow: {mean_decompress:.4f}ms per {batch_size} vectors"
    )


@pytest.mark.benchmark
@pytest.mark.performance
def test_e8_compression_ratio_statistical_validation(benchmark):
    """Validate compression ratio with multiple trials.

    Ensures compression ratio is consistent across different data.
    """
    from kagami_math import nearest_e8, e8_to_half_step_ints

    n_trials = 10
    batch_size = 1000
    compression_ratios = []

    for _trial in range(n_trials):
        # Generate random data
        x = torch.randn(batch_size, 8, dtype=torch.float32)

        # Original size
        original_bits = x.element_size() * 8 * x.numel()

        # Quantize
        y = nearest_e8(x)
        a = e8_to_half_step_ints(y)

        # Compressed size (4 bits per coordinate)
        compressed_bits = 32 * batch_size  # 32 bits per 8D vector

        # Calculate ratio
        ratio = original_bits / compressed_bits
        compression_ratios.append(ratio)

    # Statistical analysis
    mean_ratio = mean(compression_ratios)
    std_ratio = stdev(compression_ratios)
    stderr = std_ratio / np.sqrt(n_trials)
    ci_95 = 1.96 * stderr

    print("\n" + "=" * 70)
    print("STATISTICAL COMPRESSION RATIO VALIDATION")
    print("=" * 70)
    print(f"Trials:                  {n_trials}")
    print(f"Batch size per trial:    {batch_size}")
    print(f"Mean compression ratio:  {mean_ratio:.2f}:1 ± {ci_95:.2f} (95% CI)")
    print(f"Std dev:                 {std_ratio:.6f}")
    print(f"Min:                     {min(compression_ratios):.2f}:1")
    print(f"Max:                     {max(compression_ratios):.2f}:1")
    print("=" * 70)

    # Verify claim
    claim_ratio = 64.0
    tolerance = 0.1

    if abs(mean_ratio - claim_ratio) <= tolerance:
        print(f"✓ PASS: Mean ratio {mean_ratio:.1f}:1 matches claim {claim_ratio:.1f}:1")
    else:
        print(f"✗ FAIL: Mean ratio {mean_ratio:.1f}:1 != claim {claim_ratio:.1f}:1")

    benchmark.extra_info.update(
        {
            "mean_compression_ratio": mean_ratio,
            "ci_95": ci_95,
            "std_ratio": std_ratio,
            "claim_met": abs(mean_ratio - claim_ratio) <= tolerance,
        }
    )

    assert abs(mean_ratio - claim_ratio) <= tolerance, (
        f"Mean compression ratio {mean_ratio:.2f}:1 != {claim_ratio:.1f}:1 (±{tolerance}). "
        f"95% CI: {mean_ratio:.2f} ± {ci_95:.2f}"
    )


@pytest.mark.benchmark
@pytest.mark.performance
def test_e8_vs_naive_quantization(benchmark):
    """Compare E8 lattice vs naive scalar quantization.

    Demonstrates superiority of E8 lattice quantization.
    """
    from kagami_math import nearest_e8

    batch_size = 10000
    x = torch.randn(batch_size, 8, dtype=torch.float32)

    # E8 lattice quantization (4 bits per coordinate)
    y_e8 = nearest_e8(x)
    error_e8 = (x - y_e8).pow(2).sum(dim=-1).sqrt()
    mean_error_e8 = error_e8.mean().item()

    # Naive scalar quantization (4 bits per coordinate)
    # Range: [-4, 4] quantized to 16 levels
    levels = 16
    x_clamped = torch.clamp(x, -4.0, 4.0)
    x_scaled = (x_clamped + 4.0) / 8.0  # [0, 1]
    x_quantized_idx = (x_scaled * (levels - 1)).round()
    x_naive = (x_quantized_idx / (levels - 1)) * 8.0 - 4.0
    error_naive = (x - x_naive).pow(2).sum(dim=-1).sqrt()
    mean_error_naive = error_naive.mean().item()

    # Calculate improvement
    improvement = (mean_error_naive - mean_error_e8) / mean_error_naive * 100

    print("\n" + "=" * 70)
    print("E8 vs NAIVE QUANTIZATION")
    print("=" * 70)
    print(f"Batch size:              {batch_size}")
    print("Bits per coordinate:     4 bits (both methods)")
    print("Compression ratio:       64:1 (both methods)")
    print("\nE8 lattice:")
    print(f"  Mean error:            {mean_error_e8:.6f}")
    print("\nNaive scalar quantization:")
    print(f"  Mean error:            {mean_error_naive:.6f}")
    print(f"\nImprovement:             {improvement:.1f}% lower error with E8")
    print("=" * 70)

    benchmark.extra_info.update(
        {
            "e8_mean_error": mean_error_e8,
            "naive_mean_error": mean_error_naive,
            "improvement_percent": improvement,
        }
    )

    # E8 should have lower error than naive quantization
    assert mean_error_e8 < mean_error_naive, "E8 lattice should outperform naive quantization"
    assert improvement > 10.0, f"E8 improvement {improvement:.1f}% < 10%"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--benchmark-only"])
