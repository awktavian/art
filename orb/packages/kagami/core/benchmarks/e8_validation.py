"""E8 Quantization Benchmark Infrastructure.

Comprehensive benchmark harness for comparing E8 lattice quantization against
standard quantization baselines (INT8, INT4, FP16). Used to validate that
E8 lattice quantization provides better reconstruction quality per bit.

Background — E8 Lattice:
    The E8 lattice is the unique even unimodular lattice in 8 dimensions.
    It achieves the densest known sphere packing in 8D (kissing number = 240).
    For quantization, this means E8 lattice points can represent values
    with lower average error than uniform grids at the same bit rate.

Quantization Methods Compared:
    1. E8 Residual Lattice: Project to nearest E8 lattice point
    2. INT8 Uniform: Scale + round to [-128, 127]
    3. INT4 Uniform: Scale + round to [-8, 7]
    4. FP16 Half Precision: IEEE 754 half-precision float

Metrics Collected:
    - Compression: ratio (e.g., 4x for INT8), bits per parameter
    - Quality: MSE, MAE, PSNR (dB)
    - Performance: encode/decode latency (P50, P95, P99)
    - Resources: peak/average memory usage

Output Formats:
    - JSON: Machine-readable results for CI/CD
    - Markdown: Human-readable report with tables

Architecture:
    E8BenchmarkConfig (settings)
        └── E8BenchmarkHarness (runner)
                └── E8BenchmarkResult (output)
                        └── QuantizationMetrics (per-method)

Example:
    >>> config = E8BenchmarkConfig(num_samples=1000)
    >>> harness = E8BenchmarkHarness(config)
    >>> results = harness.run_all_benchmarks()
    >>> print(results.get_best_method('reconstruction_mse'))
    'E8 Residual Lattice'  # Usually wins on quality

See Also:
    - kagami_math.e8_lattice_quantizer: Actual E8 implementation
    - https://en.wikipedia.org/wiki/E8_lattice: Mathematical background
"""

from __future__ import annotations

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================
import json  # Results serialization
import time  # Latency measurement
from dataclasses import dataclass, field  # Clean data structures
from pathlib import Path  # Cross-platform file paths
from typing import Any  # Type hints

# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================
import numpy as np  # Percentile calculations
import torch  # Tensor operations

# =============================================================================
# E8 LATTICE QUANTIZER IMPORT
# =============================================================================
# Try to import optimized E8 implementation from kagami_math.
# Falls back to rounded approximation if not available.
try:
    from kagami_math.e8_lattice_quantizer import e8_to_half_step_ints, nearest_e8
except ImportError:
    # Fallback: simple rounding (not true E8, just for testing)
    def nearest_e8(x: torch.Tensor) -> torch.Tensor:
        """Fallback E8 nearest point (rounded approximation).

        WARNING: This is NOT true E8 quantization, just rounding.
        Install kagami_math for the real implementation.
        """
        return torch.round(x)

    def e8_to_half_step_ints(y: torch.Tensor) -> torch.Tensor:
        """Fallback half-step integer conversion.

        WARNING: This is NOT true E8 encoding, just for testing.
        Install kagami_math for the real implementation.
        """
        return torch.round(y * 2.0).to(torch.int64)


# =============================================================================
# QUANTIZATION METRICS
# =============================================================================
# Dataclass capturing all metrics for a single quantization method.


@dataclass
class QuantizationMetrics:
    """Complete metrics for a single quantization method.

    Captures compression efficiency, reconstruction quality, and
    performance characteristics for comparison across methods.

    Attributes:
        method: Human-readable method name (e.g., "E8 Residual Lattice").
        compression_ratio: FP32 bits / quantized bits (higher = better).
        bits_per_param: Storage bits per parameter (lower = better).
        reconstruction_mse: Mean squared error (lower = better).
        reconstruction_mae: Mean absolute error (lower = better).
        psnr_db: Peak signal-to-noise ratio in dB (higher = better).
        encode_latency_p50: 50th percentile encode time in ms.
        encode_latency_p95: 95th percentile encode time in ms.
        encode_latency_p99: 99th percentile encode time in ms.
        decode_latency_p50: 50th percentile decode time in ms.
        decode_latency_p95: 95th percentile decode time in ms.
        decode_latency_p99: 99th percentile decode time in ms.
        peak_memory_mb: Peak memory usage during operation.
        avg_memory_mb: Average memory usage during operation.
        num_samples: Number of test samples used.
        input_shape: Shape of input tensors tested.

    Example:
        >>> metrics = QuantizationMetrics(
        ...     method="INT8 Uniform",
        ...     compression_ratio=4.0,
        ...     bits_per_param=8.0,
        ...     reconstruction_mse=0.0001,
        ...     reconstruction_mae=0.008,
        ... )
    """

    method: str  # Method name for display
    compression_ratio: float  # FP32 bits / quantized bits
    bits_per_param: float  # Storage cost per weight
    reconstruction_mse: float  # Mean squared error
    reconstruction_mae: float  # Mean absolute error
    psnr_db: float = 0.0  # Signal-to-noise ratio (dB)
    encode_latency_p50: float = 0.0  # 50th percentile encode (ms)
    encode_latency_p95: float = 0.0  # 95th percentile encode (ms)
    encode_latency_p99: float = 0.0  # 99th percentile encode (ms)
    decode_latency_p50: float = 0.0  # 50th percentile decode (ms)
    decode_latency_p95: float = 0.0  # 95th percentile decode (ms)
    decode_latency_p99: float = 0.0  # 99th percentile decode (ms)
    peak_memory_mb: float = 0.0  # Peak memory (MB)
    avg_memory_mb: float = 0.0  # Average memory (MB)
    num_samples: int = 0  # Test sample count
    input_shape: tuple[int, ...] = ()  # Input tensor shape

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dict with all metrics fields.
        """
        return {
            "method": self.method,
            "compression_ratio": self.compression_ratio,
            "bits_per_param": self.bits_per_param,
            "reconstruction_mse": self.reconstruction_mse,
            "reconstruction_mae": self.reconstruction_mae,
            "psnr_db": self.psnr_db,
            "encode_latency_p50": self.encode_latency_p50,
            "encode_latency_p95": self.encode_latency_p95,
            "encode_latency_p99": self.encode_latency_p99,
            "decode_latency_p50": self.decode_latency_p50,
            "decode_latency_p95": self.decode_latency_p95,
            "decode_latency_p99": self.decode_latency_p99,
            "peak_memory_mb": self.peak_memory_mb,
            "avg_memory_mb": self.avg_memory_mb,
            "num_samples": self.num_samples,
            "input_shape": list(self.input_shape),
        }


# =============================================================================
# BENCHMARK CONFIGURATION
# =============================================================================
# Settings for benchmark runs — sample count, iterations, output paths.


@dataclass
class E8BenchmarkConfig:
    """Configuration for E8 benchmark harness.

    Controls test data generation, benchmark iterations, and output.

    Attributes:
        input_shape: Shape of test tensors. Default (1, 8) for E8 alignment.
        num_samples: Number of random test samples to generate.
        warmup_iterations: JIT warmup iterations (not measured).
        benchmark_iterations: Measured iterations for latency stats.
        seed: Random seed for reproducibility.
        output_dir: Directory for JSON/Markdown output (None = no save).
        save_json: Whether to save JSON results.
        save_markdown: Whether to save Markdown report.
        e8_max_levels: Max quantization levels for E8 (affects bits).

    Example:
        >>> config = E8BenchmarkConfig(
        ...     num_samples=10000,
        ...     benchmark_iterations=500,
        ...     output_dir=Path("./benchmark_results"),
        ... )
    """

    input_shape: tuple[int, ...] = (1, 8)  # E8 needs 8D vectors
    num_samples: int = 1000  # Number of test samples
    warmup_iterations: int = 10  # JIT warmup (not measured)
    benchmark_iterations: int = 100  # Measured iterations
    seed: int = 42  # Random seed for reproducibility
    output_dir: Path | None = None  # Output directory (None = no save)
    save_json: bool = True  # Save JSON results
    save_markdown: bool = True  # Save Markdown report
    e8_max_levels: int = 16  # E8 quantization levels

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dict with all config fields.
        """
        return {
            "input_shape": list(self.input_shape),
            "num_samples": self.num_samples,
            "warmup_iterations": self.warmup_iterations,
            "benchmark_iterations": self.benchmark_iterations,
            "seed": self.seed,
            "output_dir": str(self.output_dir) if self.output_dir else None,
            "save_json": self.save_json,
            "save_markdown": self.save_markdown,
            "e8_max_levels": self.e8_max_levels,
        }


# =============================================================================
# BENCHMARK RESULTS
# =============================================================================
# Container for all benchmark results with export methods.


@dataclass
class E8BenchmarkResult:
    """Results container for E8 benchmark run.

    Holds metrics for all quantization methods tested, with utilities
    for finding best method, JSON export, and Markdown report generation.

    Attributes:
        config: Configuration used for this run.
        device: PyTorch device (cpu or cuda:N).
        metrics: Dict mapping method name to QuantizationMetrics.
        timestamp: ISO format timestamp of run.

    Example:
        >>> result = E8BenchmarkResult(config, device="cuda:0")
        >>> result.add_metric("INT8", int8_metrics)
        >>> result.add_metric("E8", e8_metrics)
        >>> print(result.get_best_method("reconstruction_mse"))
        'E8'
    """

    config: E8BenchmarkConfig  # Config used for this run
    device: str  # PyTorch device string
    metrics: dict[str, QuantizationMetrics] = field(default_factory=dict)  # Results
    timestamp: str = ""  # ISO timestamp

    def __post_init__(self) -> None:
        """Initialize timestamp if not provided."""
        if not self.timestamp:
            import datetime

            self.timestamp = datetime.datetime.now().isoformat()

    def add_metric(self, name: str, metric: QuantizationMetrics) -> None:
        """Add a metric result for a quantization method.

        Args:
            name: Method name (e.g., "E8 Residual Lattice").
            metric: Complete metrics for the method.
        """
        self.metrics[name] = metric

    def get_best_method(self, metric_name: str) -> str:
        """Get the method with the best value for a specific metric.

        Automatically handles metric direction:
        - Higher is better: compression_ratio, psnr_db
        - Lower is better: mse, mae, latencies, memory

        Args:
            metric_name: Attribute name from QuantizationMetrics.

        Returns:
            Name of the method with best value, or empty string.
        """
        higher_is_better = {"compression_ratio", "psnr_db"}
        lower_is_better = {
            "reconstruction_mse",
            "reconstruction_mae",
            "bits_per_param",
            "encode_latency_p50",
            "encode_latency_p95",
            "encode_latency_p99",
            "decode_latency_p50",
            "decode_latency_p95",
            "decode_latency_p99",
            "peak_memory_mb",
            "avg_memory_mb",
        }

        best_method = None
        best_value = None

        for method, metric in self.metrics.items():
            value = getattr(metric, metric_name)
            if (
                best_value is None
                or (metric_name in higher_is_better and value > best_value)
                or (metric_name in lower_is_better and value < best_value)
            ):
                best_value = value
                best_method = method

        return best_method or ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Complete results dict with config, device, timestamp, metrics.
        """
        return {
            "config": self.config.to_dict(),
            "device": self.device,
            "timestamp": self.timestamp,
            "metrics": {name: m.to_dict() for name, m in self.metrics.items()},
        }

    def to_markdown(self) -> str:
        """Generate human-readable Markdown report.

        Creates a formatted report with tables for compression metrics,
        latency metrics, and memory usage, plus a summary of best methods.

        Returns:
            Markdown-formatted string suitable for README or docs.
        """
        # Build markdown report header with run metadata
        lines = [
            "# E8 Quantization Benchmark Results",
            "",
            f"**Timestamp:** {self.timestamp}",
            f"**Device:** {self.device}",
            f"**Samples:** {self.config.num_samples}",
            f"**Input Shape:** {self.config.input_shape}",
            "",
            "## Compression Metrics",
            "",
            # Table header for compression/quality metrics
            "| Method | Compression Ratio | Bits/Param | MSE | MAE |",
            "|--------|-------------------|------------|-----|-----|",
        ]

        # Add compression metrics row for each method
        for name, m in self.metrics.items():
            lines.append(
                f"| {name} | {m.compression_ratio:.2f}x | {m.bits_per_param:.2f} | "
                f"{m.reconstruction_mse:.6f} | {m.reconstruction_mae:.6f} |"
            )

        # Latency metrics section (P50/P95/P99 percentiles)
        lines.extend(
            [
                "",
                "## Latency Metrics (ms)",
                "",
                # Wide table header for encode/decode latencies
                "| Method | Encode P50 | Encode P95 | Encode P99 | Decode P50 | Decode P95 | Decode P99 |",
                "|--------|------------|------------|------------|------------|------------|------------|",
            ]
        )

        # Add latency metrics row for each method
        for name, m in self.metrics.items():
            lines.append(
                f"| {name} | {m.encode_latency_p50:.3f} | {m.encode_latency_p95:.3f} | "
                f"{m.encode_latency_p99:.3f} | {m.decode_latency_p50:.3f} | "
                f"{m.decode_latency_p95:.3f} | {m.decode_latency_p99:.3f} |"
            )

        # Memory usage section (peak and average)
        lines.extend(
            [
                "",
                "## Memory Usage (MB)",
                "",
                # Simple table for memory metrics
                "| Method | Peak Memory | Avg Memory |",
                "|--------|-------------|------------|",
            ]
        )

        # Add memory usage row for each method
        for name, m in self.metrics.items():
            lines.append(f"| {name} | {m.peak_memory_mb:.2f} | {m.avg_memory_mb:.2f} |")

        # Summary section — highlights best method for each category.
        # Useful for quick comparison without reading all tables.
        lines.extend(
            [
                "",
                "## Summary",
                "",
                # Best method for each key metric (auto-determined by direction)
                f"**Best Compression:** {self.get_best_method('compression_ratio')}",
                f"**Best Reconstruction:** {self.get_best_method('reconstruction_mse')}",
                f"**Fastest Encode:** {self.get_best_method('encode_latency_p50')}",
                f"**Fastest Decode:** {self.get_best_method('decode_latency_p50')}",
            ]
        )

        # Join all lines into final markdown string
        return "\n".join(lines)


# =============================================================================
# BENCHMARK HARNESS
# =============================================================================
# Main class that runs all benchmarks and collects results.


class E8BenchmarkHarness:
    """Benchmark harness for E8 quantization comparison.

    Runs benchmarks for E8 lattice, INT8, INT4, and FP16 quantization,
    collecting metrics for compression ratio, reconstruction quality,
    and encode/decode latency.

    Attributes:
        config: Benchmark configuration.
        device: PyTorch device (auto-detected, prefers CUDA).
        result: Results container populated by benchmarks.

    Example:
        >>> harness = E8BenchmarkHarness(E8BenchmarkConfig())
        >>> results = harness.run_all_benchmarks()
        >>> print(results.to_markdown())
    """

    def __init__(self, config: E8BenchmarkConfig) -> None:
        """Initialize benchmark harness.

        Args:
            config: Benchmark configuration settings.
        """
        self.config = config
        # Auto-detect device (CUDA if available)
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.result = E8BenchmarkResult(config=config, device=str(self.device))

        # Set random seeds for reproducibility
        torch.manual_seed(config.seed)
        np.random.seed(config.seed)

    def generate_test_data(self) -> torch.Tensor:
        """Generate random test data for benchmarking.

        Creates normally distributed tensors with the configured shape.

        Returns:
            Tensor of shape (num_samples, *input_shape[1:]).
        """
        torch.manual_seed(self.config.seed)  # Ensure reproducibility
        shape = (self.config.num_samples, *self.config.input_shape[1:])
        data = torch.randn(shape, dtype=torch.float32, device=self.device)
        return data

    def _measure_latencies(
        self, fn: Any, data: torch.Tensor, iterations: int
    ) -> tuple[float, float, float]:
        """Measure encode/decode latencies with percentile stats.

        Runs the function multiple times and calculates P50/P95/P99.

        Args:
            fn: Function to benchmark.
            data: Input tensor.
            iterations: Number of iterations.

        Returns:
            Tuple of (p50_ms, p95_ms, p99_ms).
        """
        # Collect latency samples for each iteration
        latencies = []
        for _ in range(iterations):
            # High-resolution timer for precise measurement
            start = time.perf_counter()
            fn(data)
            # Synchronize GPU if using CUDA (ensures operation completed)
            torch.cuda.synchronize() if torch.cuda.is_available() else None
            latencies.append((time.perf_counter() - start) * 1000)  # Convert to ms

        # Sort for percentile calculation
        latencies = sorted(latencies)
        # Calculate P50 (median), P95, P99 percentiles
        p50 = latencies[int(len(latencies) * 0.50)]  # Median latency
        p95 = latencies[int(len(latencies) * 0.95)]  # 95th percentile
        p99 = latencies[min(int(len(latencies) * 0.99), len(latencies) - 1)]  # 99th
        return p50, p95, p99

    def benchmark_e8(self, data: torch.Tensor) -> QuantizationMetrics:
        """Benchmark E8 lattice quantization.

        E8 lattice provides optimal 8D sphere packing. For quantization,
        this means each 8-element vector is mapped to the nearest E8
        lattice point, achieving lower reconstruction error per bit
        than uniform quantization.

        Args:
            data: Input tensor (should have last dim = 8 for E8).

        Returns:
            QuantizationMetrics with all E8 benchmark results.
        """
        # Warmup JIT/GPU — not measured
        for _ in range(self.config.warmup_iterations):
            nearest_e8(data)

        # Encode latencies
        encode_p50, encode_p95, encode_p99 = self._measure_latencies(
            nearest_e8, data, self.config.benchmark_iterations
        )

        # Quantize
        quantized = nearest_e8(data)

        # Decode latencies (E8 decode is identity for float representation)
        def decode(x: torch.Tensor) -> torch.Tensor:
            return x  # Already float

        decode_p50, decode_p95, decode_p99 = self._measure_latencies(
            decode, quantized, self.config.benchmark_iterations
        )

        # =================================================================
        # RECONSTRUCTION QUALITY METRICS
        # =================================================================
        # Calculate how well the quantized values reconstruct the original.
        # Lower MSE/MAE = better quality. Higher PSNR = better quality.
        mse = ((data - quantized) ** 2).mean().item()  # Mean squared error
        mae = (data - quantized).abs().mean().item()  # Mean absolute error
        # PSNR: Peak signal-to-noise ratio (assumes signal in [0,1] range)
        psnr = 10 * np.log10(1.0 / (mse + 1e-10)) if mse > 0 else float("inf")

        # =================================================================
        # COMPRESSION METRICS
        # =================================================================
        # E8 lattice points can be encoded efficiently using hierarchical
        # indexing. This is a conservative estimate based on max levels.
        bits_per_param = 8.0 * self.config.e8_max_levels / 8  # Approximate
        # Compression ratio: FP32 bits / quantized bits
        compression_ratio = 32.0 / bits_per_param if bits_per_param > 0 else 1.0

        # Return complete metrics for E8 quantization
        return QuantizationMetrics(
            method="E8 Residual Lattice",
            compression_ratio=compression_ratio,
            bits_per_param=bits_per_param,
            reconstruction_mse=mse,
            reconstruction_mae=mae,
            psnr_db=psnr,
            encode_latency_p50=encode_p50,
            encode_latency_p95=encode_p95,
            encode_latency_p99=encode_p99,
            decode_latency_p50=decode_p50,
            decode_latency_p95=decode_p95,
            decode_latency_p99=decode_p99,
            peak_memory_mb=0.0,  # Memory profiling not implemented yet
            avg_memory_mb=0.0,  # Would need psutil integration
            num_samples=self.config.num_samples,
            input_shape=self.config.input_shape,
        )

    def benchmark_int8(self, data: torch.Tensor) -> QuantizationMetrics:
        """Benchmark INT8 uniform quantization.

        Standard INT8 quantization: scale to [-128, 127] range.
        Achieves 4x compression (FP32 → INT8). Industry standard
        for model quantization with good quality/size tradeoff.

        Args:
            data: Input tensor (any shape).

        Returns:
            QuantizationMetrics with all INT8 benchmark results.
        """

        def encode(x: torch.Tensor) -> torch.Tensor:
            """Encode FP32 tensor to INT8 with per-tensor scale."""
            # Calculate scale to fit values into [-128, 127]
            scale = x.abs().max() / 127.0
            # Clamp to INT8 range and convert dtype
            return torch.clamp(torch.round(x / scale), -128, 127).to(torch.int8), scale

        def decode(encoded: tuple[torch.Tensor, float]) -> torch.Tensor:
            """Decode INT8 back to float using stored scale."""
            q, scale = encoded
            return q.float() * scale  # Multiply by scale to reconstruct

        # Warmup JIT/GPU — iterations not included in measurement
        for _ in range(self.config.warmup_iterations):
            encode(data)

        # Measure encode latencies (P50/P95/P99)
        encode_p50, encode_p95, encode_p99 = self._measure_latencies(
            encode, data, self.config.benchmark_iterations
        )

        # Perform quantization for decode testing
        quantized, scale = encode(data)
        reconstructed = decode((quantized, scale))

        # Measure decode latencies (P50/P95/P99)
        decode_p50, decode_p95, decode_p99 = self._measure_latencies(
            lambda x: decode((x, scale)), quantized, self.config.benchmark_iterations
        )

        # Calculate reconstruction quality metrics
        mse = ((data - reconstructed) ** 2).mean().item()  # MSE
        mae = (data - reconstructed).abs().mean().item()  # MAE
        psnr = 10 * np.log10(1.0 / (mse + 1e-10)) if mse > 0 else float("inf")  # PSNR

        return QuantizationMetrics(
            method="INT8 Uniform",
            compression_ratio=4.0,  # FP32 (32 bits) / INT8 (8 bits)
            bits_per_param=8.0,
            reconstruction_mse=mse,
            reconstruction_mae=mae,
            psnr_db=psnr,
            encode_latency_p50=encode_p50,
            encode_latency_p95=encode_p95,
            encode_latency_p99=encode_p99,
            decode_latency_p50=decode_p50,
            decode_latency_p95=decode_p95,
            decode_latency_p99=decode_p99,
            peak_memory_mb=0.0,
            avg_memory_mb=0.0,
            num_samples=self.config.num_samples,
            input_shape=self.config.input_shape,
        )

    def benchmark_int4(self, data: torch.Tensor) -> QuantizationMetrics:
        """Benchmark INT4 uniform quantization.

        Aggressive INT4 quantization: scale to [-8, 7] range.
        Achieves 8x compression (FP32 → INT4) at cost of accuracy.

        Args:
            data: Input tensor (any shape).

        Returns:
            QuantizationMetrics with all INT4 benchmark results.
        """

        def encode(x: torch.Tensor) -> torch.Tensor:
            # Scale to 4-bit range [-8, 7]
            scale = x.abs().max() / 7.0
            return torch.clamp(torch.round(x / scale), -8, 7).to(torch.int8), scale

        def decode(encoded: tuple[torch.Tensor, float]) -> torch.Tensor:
            q, scale = encoded
            return q.float() * scale

        # Warmup
        for _ in range(self.config.warmup_iterations):
            encode(data)

        # Encode latencies
        encode_p50, encode_p95, encode_p99 = self._measure_latencies(
            encode, data, self.config.benchmark_iterations
        )

        # Quantize
        quantized, scale = encode(data)
        reconstructed = decode((quantized, scale))

        # Decode latencies
        decode_p50, decode_p95, decode_p99 = self._measure_latencies(
            lambda x: decode((x, scale)), quantized, self.config.benchmark_iterations
        )

        mse = ((data - reconstructed) ** 2).mean().item()
        mae = (data - reconstructed).abs().mean().item()
        psnr = 10 * np.log10(1.0 / (mse + 1e-10)) if mse > 0 else float("inf")

        return QuantizationMetrics(
            method="INT4 Uniform",
            compression_ratio=8.0,  # FP32 (32 bits) / INT4 (4 bits)
            bits_per_param=4.0,
            reconstruction_mse=mse,
            reconstruction_mae=mae,
            psnr_db=psnr,
            encode_latency_p50=encode_p50,
            encode_latency_p95=encode_p95,
            encode_latency_p99=encode_p99,
            decode_latency_p50=decode_p50,
            decode_latency_p95=decode_p95,
            decode_latency_p99=decode_p99,
            peak_memory_mb=0.0,
            avg_memory_mb=0.0,
            num_samples=self.config.num_samples,
            input_shape=self.config.input_shape,
        )

    def benchmark_fp16(self, data: torch.Tensor) -> QuantizationMetrics:
        """Benchmark FP16 half precision.

        IEEE 754 half-precision float: 1 sign, 5 exponent, 10 mantissa.
        Achieves 2x compression (FP32 → FP16) with minimal error.

        Args:
            data: Input tensor (any shape).

        Returns:
            QuantizationMetrics with all FP16 benchmark results.
        """

        def encode(x: torch.Tensor) -> torch.Tensor:
            return x.half()  # Convert to half precision

        def decode(x: torch.Tensor) -> torch.Tensor:
            return x.float()

        # Warmup
        for _ in range(self.config.warmup_iterations):
            encode(data)

        # Encode latencies
        encode_p50, encode_p95, encode_p99 = self._measure_latencies(
            encode, data, self.config.benchmark_iterations
        )

        # Quantize
        quantized = encode(data)
        reconstructed = decode(quantized)

        # Decode latencies
        decode_p50, decode_p95, decode_p99 = self._measure_latencies(
            decode, quantized, self.config.benchmark_iterations
        )

        mse = ((data - reconstructed) ** 2).mean().item()
        mae = (data - reconstructed).abs().mean().item()
        psnr = 10 * np.log10(1.0 / (mse + 1e-10)) if mse > 0 else float("inf")

        return QuantizationMetrics(
            method="FP16 Half Precision",
            compression_ratio=2.0,  # FP32 (32 bits) / FP16 (16 bits)
            bits_per_param=16.0,
            reconstruction_mse=mse,
            reconstruction_mae=mae,
            psnr_db=psnr,
            encode_latency_p50=encode_p50,
            encode_latency_p95=encode_p95,
            encode_latency_p99=encode_p99,
            decode_latency_p50=decode_p50,
            decode_latency_p95=decode_p95,
            decode_latency_p99=decode_p99,
            peak_memory_mb=0.0,
            avg_memory_mb=0.0,
            num_samples=self.config.num_samples,
            input_shape=self.config.input_shape,
        )

    def run_all_benchmarks(self) -> E8BenchmarkResult:
        """Run all quantization benchmarks and return complete results.

        Benchmarks E8, INT8, INT4, and FP16 quantization methods,
        collecting compression ratio, reconstruction error, and latency
        metrics. Optionally saves JSON and Markdown reports.

        Returns:
            E8BenchmarkResult with metrics for all methods.

        Example:
            >>> harness = E8BenchmarkHarness(config)
            >>> results = harness.run_all_benchmarks()
            >>> best = results.get_best_method("reconstruction_mse")
        """
        # Generate test data (random normal, reproducible via seed)
        data = self.generate_test_data()

        # Run all benchmarks and collect metrics
        self.result.add_metric("E8 Residual Lattice", self.benchmark_e8(data))
        self.result.add_metric("INT8 Uniform", self.benchmark_int8(data))
        self.result.add_metric("INT4 Uniform", self.benchmark_int4(data))
        self.result.add_metric("FP16 Half Precision", self.benchmark_fp16(data))

        # Save results
        if self.config.output_dir:
            self.config.output_dir.mkdir(parents=True, exist_ok=True)

            if self.config.save_json:
                json_path = self.config.output_dir / "results.json"
                with open(json_path, "w") as f:
                    json.dump(self.result.to_dict(), f, indent=2)

            if self.config.save_markdown:
                md_path = self.config.output_dir / "report.md"
                with open(md_path, "w") as f:
                    f.write(self.result.to_markdown())

        return self.result
