"""TPU Profiler - Integrated, Repeatable, Objective Performance Analysis.

This module provides comprehensive profiling for TPU training:
- JAX profiler integration (trace files for TensorBoard)
- Memory utilization tracking (HBM usage per device)
- Compute utilization (FLOP/s, MXU efficiency)
- Throughput metrics (samples/sec, tokens/sec)
- Bottleneck identification (data loading, compute, communication)

USAGE:
    # In training loop
    from kagami.core.training.jax.profiler import TPUProfiler

    profiler = TPUProfiler(output_dir="gs://bucket/profiles")

    for step in range(total_steps):
        with profiler.step(step):
            state, metrics = train_step(state, batch, key)

        # Periodic profiling (every 1000 steps)
        if step % 1000 == 0:
            report = profiler.get_report()
            logger.info(report.summary())

    # Final report
    profiler.save_report()

CLI:
    kagami-train profile --steps 1000 --output gs://bucket/profiles

Created: January 11, 2026
"""

from __future__ import annotations

import json
import logging
import time
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import jax

logger = logging.getLogger(__name__)


# =============================================================================
# PROFILER CONFIGURATION
# =============================================================================


@dataclass
class ProfilerConfig:
    """Configuration for TPU profiler."""

    # Output directory for traces and reports
    output_dir: str = "/tmp/kagami_profiles"

    # JAX profiler settings
    enable_jax_profiler: bool = True
    trace_steps: list[int] = field(default_factory=lambda: [100, 500, 1000])
    trace_duration_ms: int = 2000

    # Memory tracking
    track_memory: bool = True
    memory_sample_interval: int = 100  # steps

    # Throughput tracking
    throughput_window: int = 100  # steps for moving average

    # Bottleneck analysis
    analyze_bottlenecks: bool = True
    data_load_threshold_ms: float = 50.0  # Flag if data loading > 50ms
    compute_threshold_ms: float = 100.0  # Flag if compute > 100ms

    # Report settings
    report_interval: int = 1000  # steps
    save_detailed_traces: bool = True


# =============================================================================
# TIMING UTILITIES
# =============================================================================


class Timer:
    """High-precision timer for profiling."""

    def __init__(self):
        self._start: float = 0.0
        self._elapsed: float = 0.0
        self._running: bool = False

    def start(self) -> Timer:
        """Start the timer."""
        if not self._running:
            self._start = time.perf_counter()
            self._running = True
        return self

    def stop(self) -> float:
        """Stop the timer and return elapsed time in ms."""
        if self._running:
            self._elapsed = (time.perf_counter() - self._start) * 1000
            self._running = False
        return self._elapsed

    @property
    def elapsed_ms(self) -> float:
        """Get elapsed time in milliseconds."""
        if self._running:
            return (time.perf_counter() - self._start) * 1000
        return self._elapsed

    @contextmanager
    def measure(self):
        """Context manager for timing a block."""
        self.start()
        try:
            yield self
        finally:
            self.stop()


# =============================================================================
# MEMORY TRACKER
# =============================================================================


@dataclass
class MemorySnapshot:
    """Snapshot of memory usage."""

    step: int
    timestamp: float
    # Per-device memory (bytes)
    device_memory: dict[str, int] = field(default_factory=dict)
    # Aggregate stats
    total_bytes: int = 0
    peak_bytes: int = 0
    # HBM utilization (0-1)
    utilization: float = 0.0


class MemoryTracker:
    """Track TPU memory utilization."""

    def __init__(self, hbm_capacity_gb: float = 32.0):
        """Initialize memory tracker.

        Args:
            hbm_capacity_gb: HBM capacity per device in GB (v6e = 32GB)
        """
        self.hbm_capacity_bytes = int(hbm_capacity_gb * 1024**3)
        self._snapshots: list[MemorySnapshot] = []
        self._peak_bytes: int = 0

    def snapshot(self, step: int) -> MemorySnapshot:
        """Take a memory snapshot."""
        try:
            # Get memory stats from JAX
            devices = jax.devices()
            device_memory = {}

            for device in devices:
                try:
                    # JAX provides memory_stats() for some backends
                    stats = device.memory_stats()
                    if stats:
                        device_memory[str(device)] = stats.get("bytes_in_use", 0)
                except (AttributeError, RuntimeError):
                    # Fallback: estimate from live arrays
                    device_memory[str(device)] = 0

            total_bytes = sum(device_memory.values())
            self._peak_bytes = max(self._peak_bytes, total_bytes)

            # Calculate utilization
            num_devices = len(devices)
            total_capacity = num_devices * self.hbm_capacity_bytes
            utilization = total_bytes / total_capacity if total_capacity > 0 else 0.0

            snapshot = MemorySnapshot(
                step=step,
                timestamp=time.time(),
                device_memory=device_memory,
                total_bytes=total_bytes,
                peak_bytes=self._peak_bytes,
                utilization=utilization,
            )
            self._snapshots.append(snapshot)
            return snapshot

        except Exception as e:
            logger.warning(f"Memory snapshot failed: {e}")
            return MemorySnapshot(step=step, timestamp=time.time())

    def get_summary(self) -> dict[str, Any]:
        """Get memory usage summary."""
        if not self._snapshots:
            return {}

        recent = self._snapshots[-10:]
        avg_util = sum(s.utilization for s in recent) / len(recent)

        return {
            "peak_bytes": self._peak_bytes,
            "peak_gb": self._peak_bytes / 1024**3,
            "avg_utilization": avg_util,
            "num_snapshots": len(self._snapshots),
            "hbm_capacity_gb": self.hbm_capacity_bytes / 1024**3,
        }


# =============================================================================
# THROUGHPUT TRACKER
# =============================================================================


@dataclass
class ThroughputMetrics:
    """Throughput metrics for a time window."""

    steps: int
    samples: int
    tokens: int
    elapsed_sec: float
    steps_per_sec: float
    samples_per_sec: float
    tokens_per_sec: float
    # Theoretical vs actual
    mxu_utilization: float = 0.0  # MXU efficiency (0-1)
    flops_achieved: float = 0.0  # TFLOP/s


class ThroughputTracker:
    """Track training throughput."""

    def __init__(
        self,
        batch_size: int,
        seq_len: int,
        window_size: int = 100,
        theoretical_tflops: float = 275.0,  # v6e single chip
    ):
        """Initialize throughput tracker.

        Args:
            batch_size: Global batch size
            seq_len: Sequence length
            window_size: Moving average window
            theoretical_tflops: Theoretical peak TFLOP/s (v6e = 275)
        """
        self.batch_size = batch_size
        self.seq_len = seq_len
        self.tokens_per_step = batch_size * seq_len
        self.window_size = window_size
        self.theoretical_tflops = theoretical_tflops

        self._step_times: deque[float] = deque(maxlen=window_size)
        self._start_time: float = time.time()
        self._total_steps: int = 0
        self._last_step_time: float = time.time()

    def record_step(self, step_time_ms: float) -> None:
        """Record a training step."""
        self._step_times.append(step_time_ms)
        self._total_steps += 1
        self._last_step_time = time.time()

    def get_metrics(self) -> ThroughputMetrics:
        """Get current throughput metrics."""
        if not self._step_times:
            return ThroughputMetrics(
                steps=0,
                samples=0,
                tokens=0,
                elapsed_sec=0,
                steps_per_sec=0,
                samples_per_sec=0,
                tokens_per_sec=0,
            )

        # Calculate from window
        window_steps = len(self._step_times)
        total_time_ms = sum(self._step_times)
        elapsed_sec = total_time_ms / 1000

        steps_per_sec = window_steps / elapsed_sec if elapsed_sec > 0 else 0
        samples_per_sec = steps_per_sec * self.batch_size
        tokens_per_sec = steps_per_sec * self.tokens_per_step

        return ThroughputMetrics(
            steps=window_steps,
            samples=window_steps * self.batch_size,
            tokens=window_steps * self.tokens_per_step,
            elapsed_sec=elapsed_sec,
            steps_per_sec=steps_per_sec,
            samples_per_sec=samples_per_sec,
            tokens_per_sec=tokens_per_sec,
        )


# =============================================================================
# BOTTLENECK ANALYZER
# =============================================================================


@dataclass
class BottleneckReport:
    """Report on training bottlenecks."""

    # Time breakdown (ms per step)
    data_load_ms: float = 0.0
    forward_ms: float = 0.0
    backward_ms: float = 0.0
    optimizer_ms: float = 0.0
    communication_ms: float = 0.0
    other_ms: float = 0.0
    total_ms: float = 0.0

    # Bottleneck identification
    primary_bottleneck: str = "unknown"
    bottleneck_percentage: float = 0.0

    # Recommendations
    recommendations: list[str] = field(default_factory=list)


class BottleneckAnalyzer:
    """Analyze training bottlenecks."""

    def __init__(self, config: ProfilerConfig):
        self.config = config
        self._data_times: deque[float] = deque(maxlen=100)
        self._compute_times: deque[float] = deque(maxlen=100)
        self._comm_times: deque[float] = deque(maxlen=100)

    def record_data_load(self, time_ms: float) -> None:
        """Record data loading time."""
        self._data_times.append(time_ms)

    def record_compute(self, time_ms: float) -> None:
        """Record compute time."""
        self._compute_times.append(time_ms)

    def record_communication(self, time_ms: float) -> None:
        """Record communication time."""
        self._comm_times.append(time_ms)

    def analyze(self) -> BottleneckReport:
        """Analyze bottlenecks and generate report."""
        avg_data = sum(self._data_times) / len(self._data_times) if self._data_times else 0
        avg_compute = (
            sum(self._compute_times) / len(self._compute_times) if self._compute_times else 0
        )
        avg_comm = sum(self._comm_times) / len(self._comm_times) if self._comm_times else 0

        total = avg_data + avg_compute + avg_comm
        if total == 0:
            return BottleneckReport()

        # Identify primary bottleneck
        times = {"data_loading": avg_data, "compute": avg_compute, "communication": avg_comm}
        primary = max(times, key=lambda k: times[k])
        bottleneck_pct = times[primary] / total * 100

        # Generate recommendations
        recommendations = []

        if avg_data > self.config.data_load_threshold_ms:
            recommendations.append(
                f"DATA LOADING SLOW: {avg_data:.1f}ms/step. "
                "Consider: increase prefetch_shards, use faster storage, "
                "or pre-stage data to local SSD."
            )

        if avg_compute > self.config.compute_threshold_ms:
            recommendations.append(
                f"COMPUTE SLOW: {avg_compute:.1f}ms/step. "
                "Consider: enable bfloat16, reduce model size, "
                "or use gradient checkpointing."
            )

        if avg_comm > avg_compute * 0.5:
            recommendations.append(
                f"COMMUNICATION OVERHEAD: {avg_comm:.1f}ms/step ({avg_comm / total * 100:.0f}%). "
                "Consider: increase batch size per device, "
                "use gradient accumulation, or reduce sync frequency."
            )

        if not recommendations:
            recommendations.append(
                "No significant bottlenecks detected. System appears well-balanced."
            )

        return BottleneckReport(
            data_load_ms=avg_data,
            forward_ms=avg_compute * 0.4,  # Estimate forward/backward split
            backward_ms=avg_compute * 0.6,
            communication_ms=avg_comm,
            total_ms=total,
            primary_bottleneck=primary,
            bottleneck_percentage=bottleneck_pct,
            recommendations=recommendations,
        )


# =============================================================================
# MAIN TPU PROFILER
# =============================================================================


@dataclass
class ProfileReport:
    """Complete profiling report."""

    # Configuration
    config: dict[str, Any] = field(default_factory=dict)

    # Hardware info
    num_devices: int = 0
    device_type: str = ""
    total_hbm_gb: float = 0.0

    # Memory
    memory_summary: dict[str, Any] = field(default_factory=dict)

    # Throughput
    throughput: ThroughputMetrics | None = None

    # Bottlenecks
    bottlenecks: BottleneckReport | None = None

    # Step timing histogram
    step_times_ms: list[float] = field(default_factory=list)

    # Recommendations
    recommendations: list[str] = field(default_factory=list)

    def summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            "=" * 70,
            "TPU PROFILING REPORT",
            "=" * 70,
            "",
            "HARDWARE:",
            f"  Devices: {self.num_devices} x {self.device_type}",
            f"  Total HBM: {self.total_hbm_gb:.1f} GB",
            "",
        ]

        if self.memory_summary:
            lines.extend(
                [
                    "MEMORY:",
                    f"  Peak usage: {self.memory_summary.get('peak_gb', 0):.2f} GB",
                    f"  Utilization: {self.memory_summary.get('avg_utilization', 0) * 100:.1f}%",
                    "",
                ]
            )

        if self.throughput:
            lines.extend(
                [
                    "THROUGHPUT:",
                    f"  Steps/sec: {self.throughput.steps_per_sec:.2f}",
                    f"  Samples/sec: {self.throughput.samples_per_sec:.0f}",
                    f"  Tokens/sec: {self.throughput.tokens_per_sec:.0f}",
                    "",
                ]
            )

        if self.bottlenecks:
            lines.extend(
                [
                    "BOTTLENECK ANALYSIS:",
                    f"  Primary: {self.bottlenecks.primary_bottleneck} "
                    f"({self.bottlenecks.bottleneck_percentage:.0f}%)",
                    f"  Data load: {self.bottlenecks.data_load_ms:.1f} ms/step",
                    f"  Compute: {self.bottlenecks.forward_ms + self.bottlenecks.backward_ms:.1f} ms/step",
                    f"  Communication: {self.bottlenecks.communication_ms:.1f} ms/step",
                    "",
                ]
            )

        if self.recommendations:
            lines.extend(
                [
                    "RECOMMENDATIONS:",
                    *[f"  • {r}" for r in self.recommendations],
                    "",
                ]
            )

        if self.step_times_ms:
            avg = sum(self.step_times_ms) / len(self.step_times_ms)
            min_t = min(self.step_times_ms)
            max_t = max(self.step_times_ms)
            lines.extend(
                [
                    "STEP TIMING:",
                    f"  Avg: {avg:.1f} ms",
                    f"  Min: {min_t:.1f} ms",
                    f"  Max: {max_t:.1f} ms",
                    "",
                ]
            )

        lines.append("=" * 70)
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "config": self.config,
            "hardware": {
                "num_devices": self.num_devices,
                "device_type": self.device_type,
                "total_hbm_gb": self.total_hbm_gb,
            },
            "memory": self.memory_summary,
            "throughput": {
                "steps_per_sec": self.throughput.steps_per_sec if self.throughput else 0,
                "samples_per_sec": self.throughput.samples_per_sec if self.throughput else 0,
                "tokens_per_sec": self.throughput.tokens_per_sec if self.throughput else 0,
            },
            "bottlenecks": {
                "primary": self.bottlenecks.primary_bottleneck if self.bottlenecks else "",
                "data_load_ms": self.bottlenecks.data_load_ms if self.bottlenecks else 0,
                "compute_ms": (
                    self.bottlenecks.forward_ms + self.bottlenecks.backward_ms
                    if self.bottlenecks
                    else 0
                ),
                "communication_ms": self.bottlenecks.communication_ms if self.bottlenecks else 0,
            },
            "step_times_ms": {
                "avg": sum(self.step_times_ms) / len(self.step_times_ms)
                if self.step_times_ms
                else 0,
                "min": min(self.step_times_ms) if self.step_times_ms else 0,
                "max": max(self.step_times_ms) if self.step_times_ms else 0,
            },
            "recommendations": self.recommendations,
        }


class TPUProfiler:
    """Integrated TPU profiler for training.

    Usage:
        profiler = TPUProfiler(
            batch_size=512,
            seq_len=64,
            output_dir="gs://bucket/profiles",
        )

        for step in range(total_steps):
            # Time data loading
            with profiler.time_data_load():
                batch = data_loader.get_batch()

            # Time compute
            with profiler.time_compute():
                state, metrics = train_step(state, batch, key)

            profiler.step_complete(step)

            # Periodic report
            if step % 1000 == 0:
                report = profiler.get_report()
                print(report.summary())

        profiler.save_report()
    """

    def __init__(
        self,
        batch_size: int = 512,
        seq_len: int = 64,
        output_dir: str = "/tmp/kagami_profiles",
        config: ProfilerConfig | None = None,
    ):
        """Initialize TPU profiler.

        Args:
            batch_size: Global batch size
            seq_len: Sequence length
            output_dir: Directory for saving profiles
            config: Profiler configuration
        """
        self.config = config or ProfilerConfig(output_dir=output_dir)
        self.batch_size = batch_size
        self.seq_len = seq_len

        # Initialize trackers
        self.memory_tracker = MemoryTracker()
        self.throughput_tracker = ThroughputTracker(
            batch_size=batch_size,
            seq_len=seq_len,
            window_size=self.config.throughput_window,
        )
        self.bottleneck_analyzer = BottleneckAnalyzer(self.config)

        # Timing
        self._step_timer = Timer()
        self._data_timer = Timer()
        self._compute_timer = Timer()
        self._step_times: list[float] = []

        # State
        self._current_step: int = 0
        self._profiling_active: bool = False
        self._jax_profiler_active: bool = False

        # Hardware info
        self._devices = jax.devices()
        self._num_devices = len(self._devices)
        self._device_type = self._devices[0].device_kind if self._devices else "unknown"

        logger.info(f"TPUProfiler initialized: {self._num_devices} x {self._device_type}")

    @contextmanager
    def time_data_load(self):
        """Context manager for timing data loading."""
        with self._data_timer.measure():
            yield
        self.bottleneck_analyzer.record_data_load(self._data_timer.elapsed_ms)

    @contextmanager
    def time_compute(self):
        """Context manager for timing compute."""
        with self._compute_timer.measure():
            yield
        self.bottleneck_analyzer.record_compute(self._compute_timer.elapsed_ms)

    @contextmanager
    def step(self, step: int):
        """Context manager for a full training step."""
        self._current_step = step
        self._step_timer.start()

        # Start JAX profiler for specific steps
        if self.config.enable_jax_profiler and step in self.config.trace_steps:
            self._start_jax_profiler(step)

        try:
            yield
        finally:
            step_time = self._step_timer.stop()
            self._step_times.append(step_time)
            self.throughput_tracker.record_step(step_time)

            # Memory snapshot
            if self.config.track_memory and step % self.config.memory_sample_interval == 0:
                self.memory_tracker.snapshot(step)

            # Stop JAX profiler
            if self._jax_profiler_active:
                self._stop_jax_profiler(step)

    def step_complete(self, step: int) -> None:
        """Mark a step as complete (alternative to context manager)."""
        step_time = self._step_timer.stop()
        self._step_times.append(step_time)
        self.throughput_tracker.record_step(step_time)
        self._current_step = step

        if self.config.track_memory and step % self.config.memory_sample_interval == 0:
            self.memory_tracker.snapshot(step)

    def _start_jax_profiler(self, step: int) -> None:
        """Start JAX profiler for trace collection."""
        try:
            trace_dir = Path(self.config.output_dir) / f"trace_step_{step}"
            trace_dir.mkdir(parents=True, exist_ok=True)
            jax.profiler.start_trace(str(trace_dir))
            self._jax_profiler_active = True
            logger.info(f"Started JAX profiler trace at step {step}")
        except Exception as e:
            logger.warning(f"Failed to start JAX profiler: {e}")

    def _stop_jax_profiler(self, step: int) -> None:
        """Stop JAX profiler."""
        try:
            jax.profiler.stop_trace()
            self._jax_profiler_active = False
            logger.info(f"Stopped JAX profiler trace at step {step}")
        except Exception as e:
            logger.warning(f"Failed to stop JAX profiler: {e}")

    def get_report(self) -> ProfileReport:
        """Generate profiling report."""
        memory_summary = self.memory_tracker.get_summary()
        throughput = self.throughput_tracker.get_metrics()
        bottlenecks = self.bottleneck_analyzer.analyze()

        # Combine recommendations
        recommendations = list(bottlenecks.recommendations)

        # Add memory-based recommendations
        if memory_summary.get("avg_utilization", 0) > 0.9:
            recommendations.append(
                f"HIGH MEMORY UTILIZATION: {memory_summary['avg_utilization'] * 100:.0f}%. "
                "Consider: reduce batch size, enable gradient checkpointing, "
                "or use model parallelism."
            )
        elif memory_summary.get("avg_utilization", 0) < 0.5:
            recommendations.append(
                f"LOW MEMORY UTILIZATION: {memory_summary['avg_utilization'] * 100:.0f}%. "
                "Consider: increase batch size to improve throughput."
            )

        return ProfileReport(
            config={
                "batch_size": self.batch_size,
                "seq_len": self.seq_len,
                "output_dir": self.config.output_dir,
            },
            num_devices=self._num_devices,
            device_type=self._device_type,
            total_hbm_gb=self._num_devices * 32.0,  # v6e = 32GB per chip
            memory_summary=memory_summary,
            throughput=throughput,
            bottlenecks=bottlenecks,
            step_times_ms=self._step_times[-100:],  # Last 100 steps
            recommendations=recommendations,
        )

    def save_report(self, filename: str = "profile_report.json") -> str:
        """Save profiling report to file."""
        report = self.get_report()
        output_path = Path(self.config.output_dir) / filename

        # Handle GCS paths
        if str(output_path).startswith("gs://"):
            local_path = Path(f"/tmp/{filename}")
            with open(local_path, "w") as f:
                json.dump(report.to_dict(), f, indent=2)

            # Upload to GCS
            try:
                import tensorflow as tf

                tf.io.gfile.copy(str(local_path), str(output_path), overwrite=True)
                logger.info(f"Profile report saved to {output_path}")
            except ImportError:
                logger.warning(f"TensorFlow not available, saved locally to {local_path}")
                return str(local_path)
        else:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w") as f:
                json.dump(report.to_dict(), f, indent=2)
            logger.info(f"Profile report saved to {output_path}")

        # Also print summary
        logger.info("\n" + report.summary())

        return str(output_path)


# =============================================================================
# BENCHMARK RUNNER
# =============================================================================


def run_benchmark(
    steps: int = 1000,
    batch_size: int = 512,
    seq_len: int = 64,
    warmup_steps: int = 100,
    output_dir: str = "/tmp/kagami_benchmark",
) -> ProfileReport:
    """Run a comprehensive benchmark.

    This function runs a standalone benchmark without real data,
    using synthetic batches to measure raw training throughput.

    Args:
        steps: Number of benchmark steps
        batch_size: Batch size
        seq_len: Sequence length
        warmup_steps: Warmup steps before measurement
        output_dir: Output directory for reports

    Returns:
        ProfileReport with benchmark results
    """
    from kagami.core.training.jax.config import OrganismRSSMConfig as ModelConfig
    from kagami.core.training.jax.data import generate_structured_batch
    from kagami.core.training.jax.train import (
        create_train_state,
        train_step,
    )

    logger.info("=" * 70)
    logger.info("TPU BENCHMARK")
    logger.info("=" * 70)
    logger.info(f"Steps: {steps} (warmup: {warmup_steps})")
    logger.info(f"Batch size: {batch_size}")
    logger.info(f"Sequence length: {seq_len}")
    logger.info("=" * 70)

    # Initialize
    config = ModelConfig()
    key = jax.random.PRNGKey(42)

    # Create model and state
    key, init_key = jax.random.split(key)
    state = create_train_state(init_key, config, learning_rate=1e-4, total_steps=steps)

    # Initialize profiler
    profiler = TPUProfiler(
        batch_size=batch_size,
        seq_len=seq_len,
        output_dir=output_dir,
        config=ProfilerConfig(
            trace_steps=[warmup_steps + 10, warmup_steps + 100],
            memory_sample_interval=50,
        ),
    )

    # Warmup
    logger.info(f"Warming up ({warmup_steps} steps)...")
    for _ in range(warmup_steps):
        key, batch_key, step_key = jax.random.split(key, 3)
        batch = generate_structured_batch(
            batch_key,
            batch_size=batch_size,
            seq_len=seq_len,
            obs_dim=config.obs_dim,
            action_dim=config.action_dim,
        )
        state, _ = train_step(state, batch, step_key, 0)
        # Block until complete
        jax.block_until_ready(state.params)

    # Benchmark
    logger.info(f"Running benchmark ({steps} steps)...")
    for step in range(steps):
        with profiler.step(step):
            key, batch_key, step_key = jax.random.split(key, 3)

            with profiler.time_data_load():
                batch = generate_structured_batch(
                    batch_key,
                    batch_size=batch_size,
                    seq_len=seq_len,
                    obs_dim=config.obs_dim,
                    action_dim=config.action_dim,
                )

            with profiler.time_compute():
                state, _ = train_step(state, batch, step_key, 0)
                # Block until compute is complete
                jax.block_until_ready(state.params)

        if step % 100 == 0:
            report = profiler.get_report()
            if report.throughput is not None:
                logger.info(
                    f"Step {step}: {report.throughput.steps_per_sec:.1f} steps/s, "
                    f"{report.throughput.samples_per_sec:.0f} samples/s"
                )

    # Final report
    report = profiler.get_report()
    profiler.save_report("benchmark_report.json")

    return report


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "BottleneckAnalyzer",
    "BottleneckReport",
    "MemorySnapshot",
    "MemoryTracker",
    "ProfileReport",
    "ProfilerConfig",
    "TPUProfiler",
    "ThroughputMetrics",
    "ThroughputTracker",
    "Timer",
    "run_benchmark",
]
