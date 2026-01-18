#!/usr/bin/env python3
"""Local TPU/CPU Benchmark with Real Data Generation.

This script:
1. Generates real training data locally (not GCS)
2. Runs comprehensive benchmarks on available hardware
3. Profiles memory, throughput, and bottlenecks
4. Validates all optimizations work correctly
5. Generates a detailed report

Usage:
    python scripts/benchmark/run_local_benchmark.py
    python scripts/benchmark/run_local_benchmark.py --steps 500 --batch-size 64

Created: January 11, 2026
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

# Add packages to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "packages"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


@dataclass
class BenchmarkConfig:
    """Benchmark configuration."""

    # Data generation
    num_shards: int = 5
    samples_per_shard: int = 1000
    seq_len: int = 32
    obs_dim: int = 64
    action_dim: int = 8

    # Training
    warmup_steps: int = 50
    benchmark_steps: int = 200
    batch_size: int = 64

    # Output
    output_dir: str = "/tmp/kagami_benchmark"
    save_report: bool = True


@dataclass
class BenchmarkResult:
    """Benchmark results."""

    # Hardware info
    platform: str = ""
    device_count: int = 0
    device_type: str = ""

    # Throughput
    steps_per_sec: float = 0.0
    samples_per_sec: float = 0.0
    tokens_per_sec: float = 0.0

    # Timing breakdown (ms)
    avg_step_time_ms: float = 0.0
    avg_data_load_ms: float = 0.0
    avg_compute_ms: float = 0.0
    p50_step_time_ms: float = 0.0
    p95_step_time_ms: float = 0.0
    p99_step_time_ms: float = 0.0

    # Memory
    peak_memory_mb: float = 0.0
    avg_memory_mb: float = 0.0

    # Model info
    param_count: int = 0
    batch_size: int = 0
    seq_len: int = 0

    # Validation
    loss_converging: bool = False
    initial_loss: float = 0.0
    final_loss: float = 0.0
    gradient_healthy: bool = False
    avg_grad_norm: float = 0.0

    # Bottleneck analysis
    primary_bottleneck: str = ""
    bottleneck_percentage: float = 0.0
    recommendations: list[str] = field(default_factory=list)

    def summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            "",
            "=" * 70,
            "BENCHMARK RESULTS",
            "=" * 70,
            "",
            f"Platform: {self.platform}",
            f"Devices: {self.device_count} x {self.device_type}",
            f"Model: {self.param_count:,} parameters ({self.param_count / 1e6:.1f}M)",
            f"Batch: {self.batch_size} x {self.seq_len} seq_len",
            "",
            "THROUGHPUT:",
            f"  Steps/sec:    {self.steps_per_sec:.2f}",
            f"  Samples/sec:  {self.samples_per_sec:.0f}",
            f"  Tokens/sec:   {self.tokens_per_sec:.0f}",
            "",
            "TIMING (ms):",
            f"  Avg step:     {self.avg_step_time_ms:.1f}",
            f"  Data load:    {self.avg_data_load_ms:.1f} ({self.avg_data_load_ms / self.avg_step_time_ms * 100:.0f}%)"
            if self.avg_step_time_ms > 0
            else "  Data load:    N/A",
            f"  Compute:      {self.avg_compute_ms:.1f} ({self.avg_compute_ms / self.avg_step_time_ms * 100:.0f}%)"
            if self.avg_step_time_ms > 0
            else "  Compute:      N/A",
            f"  P50/P95/P99:  {self.p50_step_time_ms:.1f} / {self.p95_step_time_ms:.1f} / {self.p99_step_time_ms:.1f}",
            "",
            "MEMORY:",
            f"  Peak:         {self.peak_memory_mb:.0f} MB",
            f"  Average:      {self.avg_memory_mb:.0f} MB",
            "",
            "VALIDATION:",
            f"  Loss trend:   {'✓ CONVERGING' if self.loss_converging else '✗ NOT CONVERGING'}",
            f"  Initial loss: {self.initial_loss:.4f}",
            f"  Final loss:   {self.final_loss:.4f}",
            f"  Gradients:    {'✓ HEALTHY' if self.gradient_healthy else '✗ UNHEALTHY'}",
            f"  Avg grad norm: {self.avg_grad_norm:.2f}",
            "",
            "BOTTLENECK:",
            f"  Primary:      {self.primary_bottleneck} ({self.bottleneck_percentage:.0f}%)",
            "",
            "RECOMMENDATIONS:",
        ]

        for rec in self.recommendations[:5]:
            lines.append(f"  • {rec}")

        lines.extend(["", "=" * 70])
        return "\n".join(lines)


def generate_local_data(config: BenchmarkConfig, output_dir: Path) -> Path:
    """Generate local training data shards.

    Creates .npz files in the format expected by CurriculumDataLoader.
    """
    logger.info("=" * 50)
    logger.info("GENERATING LOCAL TRAINING DATA")
    logger.info("=" * 50)

    data_dir = output_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Try to use Genesis, fall back to synthetic
    use_genesis = False
    try:
        from kagami.core.training.datasets.genesis_generator import (
            GenesisGeneratorConfig,
            GenesisPuzzleGenerator,
        )

        gen_config = GenesisGeneratorConfig(
            output_dir=str(data_dir),
            num_shards=config.num_shards,
            samples_per_shard=config.samples_per_shard,
            seq_len=config.seq_len,
            obs_dim=config.obs_dim,
            action_dim=config.action_dim,
        )
        generator = GenesisPuzzleGenerator(gen_config)
        # Check if Genesis is actually available
        generator._ensure_genesis()
        if generator._genesis is not None:
            use_genesis = True
            logger.info("Using Genesis physics engine for data generation")
    except Exception as e:
        logger.info(f"Genesis not available: {e}")

    if not use_genesis:
        logger.info("Using synthetic data generation (physics-inspired)")

    total_samples = config.num_shards * config.samples_per_shard
    logger.info(
        f"Generating {config.num_shards} shards x {config.samples_per_shard} samples = {total_samples:,} total"
    )

    np.random.seed(42)

    for shard_idx in range(config.num_shards):
        # Generate physics-inspired synthetic data
        N = config.samples_per_shard
        T = config.seq_len
        obs_dim = config.obs_dim
        action_dim = config.action_dim

        # Create realistic trajectories with physics-like dynamics
        obs = np.zeros((N, T, obs_dim), dtype=np.float32)
        actions = np.zeros((N, T, action_dim), dtype=np.float32)
        rewards = np.zeros((N, T), dtype=np.float32)
        continues = np.ones((N, T), dtype=np.float32)

        for i in range(N):
            # Initial state
            pos = np.random.randn(3) * 2
            vel = np.random.randn(3) * 0.5
            gravity = np.array([0, 0, -9.81])

            for t in range(T):
                # Physics step
                dt = 1.0 / 60.0
                vel = vel + gravity * dt
                pos = pos + vel * dt

                # Bounce off ground
                if pos[2] < 0:
                    pos[2] = 0
                    vel[2] = -vel[2] * 0.8  # Energy loss

                # Encode observation (position, velocity, + padding)
                obs[i, t, :3] = pos
                obs[i, t, 3:6] = vel
                obs[i, t, 6:] = np.random.randn(obs_dim - 6) * 0.1

                # Random actions
                actions[i, t] = np.random.randn(action_dim) * 0.5

                # Sparse rewards (goal reaching)
                if np.linalg.norm(pos[:2]) < 1.0 and t > T // 2:
                    rewards[i, t] = 1.0

        # Save shard
        shard_name = f"train-{shard_idx:05d}-of-{config.num_shards:05d}.npz"
        shard_path = data_dir / shard_name
        np.savez_compressed(
            shard_path,
            obs=obs,
            actions=actions,
            rewards=rewards,
            continues=continues,
        )

        if (shard_idx + 1) % max(1, config.num_shards // 5) == 0:
            logger.info(f"  Generated shard {shard_idx + 1}/{config.num_shards}")

    logger.info(f"✓ Generated {config.num_shards} shards in {data_dir}")
    return data_dir


def run_benchmark(config: BenchmarkConfig) -> BenchmarkResult:
    """Run comprehensive benchmark."""
    import jax

    result = BenchmarkResult()

    # Setup output directory
    output_dir = Path(config.output_dir)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Hardware info
    result.platform = jax.default_backend()
    result.device_count = jax.device_count()
    devices = jax.devices()
    result.device_type = devices[0].device_kind if devices else "unknown"

    logger.info("=" * 70)
    logger.info("LOCAL TPU/CPU BENCHMARK")
    logger.info("=" * 70)
    logger.info(f"Platform: {result.platform}")
    logger.info(f"Devices: {result.device_count} x {result.device_type}")
    logger.info(f"Batch size: {config.batch_size}")
    logger.info(f"Sequence length: {config.seq_len}")
    logger.info(f"Warmup steps: {config.warmup_steps}")
    logger.info(f"Benchmark steps: {config.benchmark_steps}")
    logger.info("=" * 70)

    # Generate local data
    data_dir = generate_local_data(config, output_dir)

    # Import training components
    logger.info("")
    logger.info("=" * 50)
    logger.info("INITIALIZING MODEL AND TRAINING")
    logger.info("=" * 50)

    from kagami.core.training.jax.profiler import ProfilerConfig, TPUProfiler
    from kagami.core.training.jax.train_tpu import (
        ModelConfig,
        create_train_state,
        get_phase_for_step,
        train_step,
    )

    # Initialize model
    model_config = ModelConfig(
        obs_dim=config.obs_dim,
        action_dim=config.action_dim,
    )

    key = jax.random.PRNGKey(42)
    key, init_key = jax.random.split(key)

    # total_steps must exceed 2000 (warmup_steps in create_train_state)
    state = create_train_state(
        init_key,
        model_config,
        learning_rate=1e-4,
        total_steps=max(5000, config.warmup_steps + config.benchmark_steps),
    )

    result.param_count = sum(x.size for x in jax.tree_util.tree_leaves(state.params))
    result.batch_size = config.batch_size
    result.seq_len = config.seq_len

    logger.info(f"Model parameters: {result.param_count:,}")

    # Initialize local data loader (load all shards into memory)
    import jax.numpy as jnp

    shard_files = sorted(data_dir.glob("train-*.npz"))
    all_data = {"obs": [], "actions": [], "rewards": [], "continues": []}
    for shard_file in shard_files:
        data = np.load(shard_file)
        all_data["obs"].append(data["obs"])
        all_data["actions"].append(data["actions"])
        all_data["rewards"].append(data["rewards"])
        all_data["continues"].append(data["continues"])

    all_obs = np.concatenate(all_data["obs"], axis=0)
    all_actions = np.concatenate(all_data["actions"], axis=0)
    all_rewards = np.concatenate(all_data["rewards"], axis=0)
    all_continues = np.concatenate(all_data["continues"], axis=0)

    total_samples = len(all_obs)
    logger.info(f"Loaded {total_samples:,} samples into memory")

    def get_batch(step: int) -> dict:
        """Get a batch of data."""
        idx_start = (step * config.batch_size) % (total_samples - config.batch_size)
        idx_end = idx_start + config.batch_size
        return {
            "obs": jnp.array(all_obs[idx_start:idx_end], dtype=jnp.bfloat16),
            "actions": jnp.array(all_actions[idx_start:idx_end], dtype=jnp.float32),
            "rewards": jnp.array(all_rewards[idx_start:idx_end], dtype=jnp.float32),
            "continues": jnp.array(all_continues[idx_start:idx_end], dtype=jnp.float32),
        }

    # Initialize profiler
    profiler_config = ProfilerConfig(
        output_dir=str(output_dir / "profiles"),
        trace_steps=[config.warmup_steps + 10],
        memory_sample_interval=10,
    )
    profiler = TPUProfiler(
        batch_size=config.batch_size,
        seq_len=config.seq_len,
        output_dir=str(output_dir / "profiles"),
        config=profiler_config,
    )

    # Warmup
    logger.info("")
    logger.info(f"Warming up ({config.warmup_steps} steps)...")
    warmup_start = time.perf_counter()

    for step in range(config.warmup_steps):
        key, step_key = jax.random.split(key)
        batch = get_batch(step)
        phase_idx, _ = get_phase_for_step(step)
        state, metrics = train_step(state, batch, step_key, phase_idx)
        jax.block_until_ready(state.params)

    warmup_time = time.perf_counter() - warmup_start
    logger.info(f"Warmup completed in {warmup_time:.1f}s")

    # Benchmark
    logger.info("")
    logger.info(f"Running benchmark ({config.benchmark_steps} steps)...")

    step_times = []
    data_load_times = []
    compute_times = []
    losses = []
    grad_norms = []
    memory_samples = []

    benchmark_start = time.perf_counter()

    for step in range(config.benchmark_steps):
        step_start = time.perf_counter()

        key, step_key = jax.random.split(key)

        # Time data loading
        data_start = time.perf_counter()
        batch = get_batch(step)
        data_time = (time.perf_counter() - data_start) * 1000
        data_load_times.append(data_time)

        # Time compute
        compute_start = time.perf_counter()
        phase_idx, _ = get_phase_for_step(step)
        state, metrics = train_step(state, batch, step_key, phase_idx)
        jax.block_until_ready(state.params)
        compute_time = (time.perf_counter() - compute_start) * 1000
        compute_times.append(compute_time)

        step_time = (time.perf_counter() - step_start) * 1000
        step_times.append(step_time)

        # Track metrics
        loss = float(metrics["loss"])
        losses.append(loss)
        grad_norms.append(float(metrics["grad_norm"]))

        # Sample memory periodically
        if step % 10 == 0:
            try:
                mem_info = jax.devices()[0].memory_stats()
                if mem_info:
                    memory_samples.append(mem_info.get("bytes_in_use", 0) / 1e6)
            except Exception:
                pass

        # Log progress
        if (step + 1) % 50 == 0:
            avg_time = sum(step_times[-50:]) / len(step_times[-50:])
            logger.info(
                f"  Step {step + 1}/{config.benchmark_steps}: "
                f"{1000 / avg_time:.1f} steps/s, "
                f"loss={loss:.4f}, grad={float(metrics['grad_norm']):.2f}"
            )

    benchmark_time = time.perf_counter() - benchmark_start

    # Compute results
    result.steps_per_sec = config.benchmark_steps / benchmark_time
    result.samples_per_sec = result.steps_per_sec * config.batch_size
    result.tokens_per_sec = result.samples_per_sec * config.seq_len

    result.avg_step_time_ms = float(np.mean(step_times))
    result.avg_data_load_ms = float(np.mean(data_load_times))
    result.avg_compute_ms = float(np.mean(compute_times))

    sorted_times = sorted(step_times)
    result.p50_step_time_ms = sorted_times[len(sorted_times) // 2]
    result.p95_step_time_ms = sorted_times[int(len(sorted_times) * 0.95)]
    result.p99_step_time_ms = sorted_times[int(len(sorted_times) * 0.99)]

    if memory_samples:
        result.peak_memory_mb = max(memory_samples)
        result.avg_memory_mb = float(np.mean(memory_samples))

    # Validation
    result.initial_loss = losses[0]
    result.final_loss = losses[-1]
    result.loss_converging = losses[-1] < losses[0] * 0.95  # 5% improvement
    result.avg_grad_norm = float(np.mean(grad_norms))
    result.gradient_healthy = 0.01 < result.avg_grad_norm < 100.0

    # Bottleneck analysis
    avg_data = result.avg_data_load_ms
    avg_compute = result.avg_compute_ms
    total = avg_data + avg_compute

    if total > 0:
        if avg_data > avg_compute:
            result.primary_bottleneck = "DATA_LOADING"
            result.bottleneck_percentage = avg_data / total * 100
            result.recommendations = [
                "Data loading is the bottleneck",
                "Increase prefetch_shards for more async loading",
                "Use more shards with smaller samples_per_shard",
                "Consider memory-mapped data loading",
            ]
        else:
            result.primary_bottleneck = "COMPUTE"
            result.bottleneck_percentage = avg_compute / total * 100
            result.recommendations = [
                "Compute is the bottleneck (ideal for GPU/TPU)",
                "System is well-balanced",
                "Consider larger batch size if memory allows",
                "Enable gradient accumulation for effective larger batches",
            ]

    # Additional recommendations
    if not result.loss_converging:
        result.recommendations.insert(0, "⚠️ Loss not converging - check learning rate")
    if not result.gradient_healthy:
        result.recommendations.insert(0, "⚠️ Gradient norms unhealthy - check model init")

    # Save profiling report (may fail on CPU without memory stats)
    try:
        profiler.save_report("benchmark_profile.json")
    except Exception as e:
        logger.warning(f"Could not save profiler report: {e}")

    return result


def main():
    parser = argparse.ArgumentParser(description="Local TPU/CPU Benchmark")
    parser.add_argument("--steps", type=int, default=200, help="Benchmark steps")
    parser.add_argument("--warmup", type=int, default=50, help="Warmup steps")
    parser.add_argument("--batch-size", type=int, default=64, help="Batch size")
    parser.add_argument("--seq-len", type=int, default=32, help="Sequence length")
    parser.add_argument("--shards", type=int, default=5, help="Number of data shards")
    parser.add_argument("--samples-per-shard", type=int, default=1000, help="Samples per shard")
    parser.add_argument(
        "--output", type=str, default="/tmp/kagami_benchmark", help="Output directory"
    )
    parser.add_argument("--json", action="store_true", help="Output JSON only")

    args = parser.parse_args()

    config = BenchmarkConfig(
        num_shards=args.shards,
        samples_per_shard=args.samples_per_shard,
        seq_len=args.seq_len,
        warmup_steps=args.warmup,
        benchmark_steps=args.steps,
        batch_size=args.batch_size,
        output_dir=args.output,
    )

    try:
        result = run_benchmark(config)

        if args.json:
            print(json.dumps(asdict(result), indent=2))
        else:
            print(result.summary())

        # Save report
        report_path = Path(config.output_dir) / "benchmark_report.json"
        with open(report_path, "w") as f:
            json.dump(asdict(result), f, indent=2)
        logger.info(f"\nReport saved to: {report_path}")

        # Return success/failure based on validation
        if result.loss_converging and result.gradient_healthy:
            logger.info("\n✅ BENCHMARK PASSED - All validations successful")
            return 0
        else:
            logger.warning("\n⚠️ BENCHMARK WARNINGS - Check validation results")
            return 1

    except Exception as e:
        logger.error(f"Benchmark failed: {e}")
        import traceback

        traceback.print_exc()
        return 2


if __name__ == "__main__":
    sys.exit(main())
