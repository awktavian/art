"""Optimized Performance Benchmark: Test All Optimizations.

Compares baseline vs. optimized training to measure improvements:
- Mixed precision (FP16/BF16)
- Gradient checkpointing
- Torch compile
- Fused optimizer
- Gradient accumulation

Target improvements:
- 2-3× throughput via mixed precision
- 1.5-2× speedup via torch.compile
- 20-40% memory reduction via gradient checkpointing
"""

import gc
import json
import os
import time

import psutil
import torch

from kagami.core.world_model.kagami_world_model import KagamiWorldModelFactory
from kagami.core.world_model.optimized_training import create_optimized_trainer


def get_device():
    """Get best available device."""
    if torch.cuda.is_available():
        return "cuda"
    elif torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def measure_memory() -> float:
    """Get current memory usage in MB."""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024


def benchmark_configuration(
    dimensions: list[int],
    batch_size: int,
    num_steps: int,
    device: str,
    use_mixed_precision: bool = False,
    use_gradient_checkpointing: bool = False,
    gradient_accumulation_steps: int = 1,
    compile_model: bool = False,
    use_fused_optimizer: bool = True,
) -> dict:
    """Benchmark a specific configuration.

    Args:
        dimensions: Layer dimensions
        batch_size: Batch size
        num_steps: Number of training steps
        device: Device to use
        use_mixed_precision: Enable FP16
        use_gradient_checkpointing: Enable gradient checkpointing
        gradient_accumulation_steps: Gradient accumulation
        compile_model: Use torch.compile
        use_fused_optimizer: Use fused AdamW

    Returns:
        Performance metrics
    """
    print(f"\n{'=' * 60}")
    print(f"Config: {len(dimensions)} layers, batch={batch_size}, device={device}")
    print(f"  Mixed precision: {use_mixed_precision}")
    print(f"  Gradient checkpointing: {use_gradient_checkpointing}")
    print(f"  Gradient accumulation: {gradient_accumulation_steps}")
    print(f"  Torch compile: {compile_model}")
    print(f"  Fused optimizer: {use_fused_optimizer}")
    print(f"{'=' * 60}")

    # Create model
    brain = KagamiWorldModelFactory.create(
        preset="research",
    )
    brain = brain.to(device)

    # Count parameters
    total_params = sum(p.numel() for p in brain.parameters())
    trainable_params = sum(p.numel() for p in brain.parameters() if p.requires_grad)

    print(f"Model: {total_params:,} total params, {trainable_params:,} trainable")

    # Create optimized trainer
    trainer = create_optimized_trainer(
        model=brain,
        learning_rate=1e-3,
        device=device,
        use_mixed_precision=use_mixed_precision,
        gradient_accumulation_steps=gradient_accumulation_steps,
        use_fused_optimizer=use_fused_optimizer,
        compile_model=compile_model,
    )

    # Warmup
    print("Warming up...")
    mem_before_warmup = measure_memory()

    for _ in range(5):
        x = torch.randn(batch_size, 10, dimensions[0], device=device)
        target = torch.randn(batch_size, 10, dimensions[-1], device=device)
        try:
            trainer.training_step(x, target)
        except Exception as e:
            print(f"  Error during warmup: {e}")
            return {"error": str(e)}

    mem_after_warmup = measure_memory()

    # Benchmark
    print(f"Benchmarking {num_steps} steps...")
    times = []
    mem_start = measure_memory()

    try:
        start_total = time.perf_counter()

        for step in range(num_steps):
            x = torch.randn(batch_size, 10, dimensions[0], device=device)
            target = torch.randn(batch_size, 10, dimensions[-1], device=device)

            step_start = time.perf_counter()
            trainer.training_step(x, target)
            step_end = time.perf_counter()

            times.append(step_end - step_start)

            if (step + 1) % 10 == 0:
                avg_time = sum(times[-10:]) / 10 * 1000
                throughput = batch_size / (sum(times[-10:]) / 10)
                print(
                    f"  Step {step + 1}/{num_steps}: {avg_time:.2f} ms/step, {throughput:.1f} samples/sec"
                )

        end_total = time.perf_counter()

    except Exception as e:
        print(f"  Error during benchmark: {e}")
        return {"error": str(e)}

    mem_end = measure_memory()

    # Calculate stats
    total_time = end_total - start_total
    avg_time_per_step = sum(times) / len(times)
    std_time = (sum((t - avg_time_per_step) ** 2 for t in times) / len(times)) ** 0.5

    # Account for gradient accumulation in throughput
    effective_batch_size = batch_size * gradient_accumulation_steps
    samples_processed = num_steps * effective_batch_size
    throughput = samples_processed / total_time
    steps_per_sec = num_steps / total_time

    results = {
        "dimensions": dimensions,
        "num_layers": len(dimensions),
        "batch_size": batch_size,
        "effective_batch_size": effective_batch_size,
        "num_steps": num_steps,
        "device": device,
        "total_params": total_params,
        "trainable_params": trainable_params,
        "mixed_precision": use_mixed_precision,
        "gradient_checkpointing": use_gradient_checkpointing,
        "gradient_accumulation": gradient_accumulation_steps,
        "compile_model": compile_model,
        "fused_optimizer": use_fused_optimizer,
        "total_time_sec": total_time,
        "avg_time_per_step_ms": avg_time_per_step * 1000,
        "std_time_per_step_ms": std_time * 1000,
        "min_time_ms": min(times) * 1000,
        "max_time_ms": max(times) * 1000,
        "samples_per_sec": throughput,
        "steps_per_sec": steps_per_sec,
        "memory_delta_mb": mem_end - mem_start,
        "warmup_memory_delta_mb": mem_after_warmup - mem_before_warmup,
    }

    print("\nResults:")
    print(
        f"  Avg time/step: {results['avg_time_per_step_ms']:.2f} ± {results['std_time_per_step_ms']:.2f} ms"
    )
    print(f"  Throughput: {results['samples_per_sec']:.1f} samples/sec")
    print(f"  Steps/sec: {results['steps_per_sec']:.2f}")
    print(f"  Memory delta: {results['memory_delta_mb']:.1f} MB")

    # Cleanup
    del brain, trainer
    gc.collect()
    if device == "cuda":
        torch.cuda.empty_cache()
    elif device == "mps":
        torch.mps.empty_cache()

    return results


def benchmark_optimizations():
    """Benchmark baseline vs. all optimization strategies."""
    device = get_device()
    print(f"\n{'#' * 70}")
    print("# OPTIMIZED PERFORMANCE BENCHMARK")
    print(f"# Device: {device}")
    print(f"{'#' * 70}")

    # Test configurations
    dimensions = [32, 64, 128, 256, 512, 1024]  # 6-layer (optimal)
    batch_size = 128  # Use larger batch for better throughput
    num_steps = 30  # Fewer steps due to torch.compile overhead

    results = {
        "device": device,
        "system": {
            "cpu_cores": psutil.cpu_count(logical=False),
            "cpu_threads": psutil.cpu_count(),
            "ram_gb": psutil.virtual_memory().total / 1024**3,
            "pytorch_version": torch.__version__,
        },
        "configurations": [],
    }

    # Configuration matrix
    # Note: Mixed precision disabled for MPS (not fully supported)
    use_mixed_precision = device == "cuda"

    configs = [
        {
            "name": "baseline",
            "mixed_precision": False,
            "gradient_checkpointing": False,
            "gradient_accumulation": 1,
            "compile": False,
        },
        {
            "name": "gradient_checkpointing",
            "mixed_precision": False,
            "gradient_checkpointing": True,
            "gradient_accumulation": 1,
            "compile": False,
        },
        {
            "name": "all_optimizations",
            "mixed_precision": use_mixed_precision,
            "gradient_checkpointing": True,
            "gradient_accumulation": 1,
            "compile": False,  # Skip compile due to long warmup
        },
    ]

    # Add mixed precision test only for CUDA
    if use_mixed_precision:
        configs.insert(
            1,
            {
                "name": "mixed_precision",
                "mixed_precision": True,
                "gradient_checkpointing": False,
                "gradient_accumulation": 1,
                "compile": False,
            },
        )

    baseline_throughput = None

    for config in configs:
        print(f"\n\n{'=' * 70}")
        print(f"TESTING: {config['name']}")
        print(f"{'=' * 70}")

        result = benchmark_configuration(
            dimensions=dimensions,
            batch_size=batch_size,
            num_steps=num_steps,
            device=device,
            use_mixed_precision=config["mixed_precision"],
            use_gradient_checkpointing=config["gradient_checkpointing"],
            gradient_accumulation_steps=config["gradient_accumulation"],
            compile_model=config["compile"],
        )

        if "error" not in result:
            result["config_name"] = config["name"]
            results["configurations"].append(result)

            # Track baseline for comparison
            if config["name"] == "baseline":
                baseline_throughput = result["samples_per_sec"]

            # Calculate speedup
            if baseline_throughput:
                speedup = result["samples_per_sec"] / baseline_throughput
                result["speedup_vs_baseline"] = speedup
                print(f"  Speedup vs baseline: {speedup:.2f}×")

    # Save results
    with open("optimized_performance_results.json", "w") as f:
        json.dump(results, f, indent=2)

    # Print summary
    print(f"\n\n{'#' * 70}")
    print("# SUMMARY: OPTIMIZED PERFORMANCE")
    print(f"{'#' * 70}\n")

    print(f"Device: {device}")
    print(
        f"System: {results['system']['cpu_cores']} cores, {results['system']['ram_gb']:.0f} GB RAM\n"
    )

    print(
        f"{'Configuration':<30} {'Samples/sec':<15} {'ms/step':<10} {'Speedup':<10} {'Memory':<10}"
    )
    print(f"{'-' * 80}")

    for config_result in results["configurations"]:
        if "error" not in config_result:
            speedup = config_result.get("speedup_vs_baseline", 1.0)
            print(
                f"{config_result['config_name']:<30} "
                f"{config_result['samples_per_sec']:<15.1f} "
                f"{config_result['avg_time_per_step_ms']:<10.2f} "
                f"{speedup:<10.2f}× "
                f"{config_result['memory_delta_mb']:<10.1f} MB"
            )

    # Find best configuration
    max_throughput = 0
    best_config = None

    for config_result in results["configurations"]:
        if "error" not in config_result and config_result["samples_per_sec"] > max_throughput:
            max_throughput = config_result["samples_per_sec"]
            best_config = config_result["config_name"]

    print(f"\n{'-' * 80}")
    print(f"BEST CONFIGURATION: {best_config}")
    print(f"  Maximum throughput: {max_throughput:.1f} samples/sec")
    if baseline_throughput:
        print(f"  Total speedup: {max_throughput / baseline_throughput:.2f}×")
    print(f"{'-' * 80}")

    print(f"\n{'#' * 70}")
    print("Results saved to: optimized_performance_results.json")
    print(f"{'#' * 70}\n")

    return results


if __name__ == "__main__":
    results = benchmark_optimizations()
