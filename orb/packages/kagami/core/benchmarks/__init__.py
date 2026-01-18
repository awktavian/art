"""Kagami Core Benchmarks Module.

Provides comprehensive benchmark infrastructure for comparing E8 lattice
quantization against standard quantization baselines (INT8, INT4, FP16).

E8 Lattice Quantization:
    The E8 lattice is an 8-dimensional sphere packing with the highest
    known density. It's used for neural network weight quantization
    to achieve better compression with lower reconstruction error.

Why E8?
    - Optimal 8D sphere packing (kissing number = 240)
    - Better reconstruction error per bit than uniform quantization
    - Natural fit for neural network weights (often 8D aligned)
    - Mathematically elegant (connected to exceptional Lie groups)

Benchmark Metrics:
    - Compression ratio: FP32 bits / quantized bits
    - Bits per parameter: Storage cost per weight
    - Reconstruction MSE/MAE: Quantization error
    - PSNR: Signal-to-noise ratio in dB
    - Encode/Decode latency: P50/P95/P99 percentiles
    - Memory usage: Peak and average MB

Components:
    - QuantizationMetrics: Dataclass for all metrics
    - E8BenchmarkConfig: Configuration (shape, iterations, etc.)
    - E8BenchmarkResult: Results container with markdown export
    - E8BenchmarkHarness: Main benchmark runner

Example:
    >>> from kagami.core.benchmarks import E8BenchmarkHarness, E8BenchmarkConfig
    >>>
    >>> config = E8BenchmarkConfig(
    ...     input_shape=(1, 8),
    ...     num_samples=1000,
    ...     benchmark_iterations=100,
    ... )
    >>> harness = E8BenchmarkHarness(config)
    >>> results = harness.run_all_benchmarks()
    >>>
    >>> print(results.to_markdown())  # Generate report

See Also:
    - kagami_math.e8_lattice_quantizer: Core E8 implementation
    - docs/math.md: Mathematical background
"""

from .e8_validation import (
    E8BenchmarkConfig,
    E8BenchmarkHarness,
    E8BenchmarkResult,
    QuantizationMetrics,
)

# =============================================================================
# PUBLIC API
# =============================================================================
# All benchmark classes and dataclasses.

__all__ = [
    # Configuration dataclass
    "E8BenchmarkConfig",
    # Main benchmark harness
    "E8BenchmarkHarness",
    # Results container
    "E8BenchmarkResult",
    # Metrics dataclass
    "QuantizationMetrics",
]
