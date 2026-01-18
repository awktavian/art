"""Example: Using torch.compile optimization for Kagami world model.

CREATED: December 14, 2025 (Forge, e₂)
PURPOSE: Demonstrate safe torch.compile usage for hot paths

This example shows how to:
1. Enable torch.compile globally
2. Compile hot paths (E8 quantization, octonions, projections)
3. Verify correctness
4. Benchmark speedup
5. Use selective compilation for complex models

SAFETY:
- Feature flag OFF by default (must explicitly enable)
- Graceful fallback if compilation fails
- Numerical correctness verification
- Backward compatible (code works with/without compilation)
"""

import torch
from kagami.core.world_model.compilation import (
    enable_compilation,
    disable_compilation,
    compile_for_inference,
    compile_for_training,
    compile_e8_quantizer,
    warmup_compiled,
    verify_compilation_correctness,
    benchmark_compilation,
)
from kagami_math.e8_lattice_protocol import (
    ResidualE8LatticeVQ,
    E8LatticeResidualConfig,
)
from kagami_math.octonions import octonion_mul


# =============================================================================
# EXAMPLE 1: Enable compilation globally
# =============================================================================


def example_global_enable():
    """Enable torch.compile globally."""
    print("=== Example 1: Global Enable ===")

    # Enable compilation (off by default for safety)
    enable_compilation()
    print("✓ torch.compile ENABLED globally")

    # Disable when done
    disable_compilation()
    print("✓ torch.compile DISABLED")


# =============================================================================
# EXAMPLE 2: Compile E8 quantizer (hot path)
# =============================================================================


def example_compile_e8_quantizer():
    """Compile E8 quantizer for faster inference."""
    print("\n=== Example 2: E8 Quantizer Compilation ===")

    enable_compilation()

    # Create E8 quantizer
    config = E8LatticeResidualConfig(
        max_levels=4,
        min_levels=1,
        initial_scale=2.0,
        adaptive_levels=False,
    )
    quantizer = ResidualE8LatticeVQ(config)

    # Compile for inference (max-autotune for low latency)
    compiled_quantizer = compile_e8_quantizer(quantizer, mode="inference")

    # Test
    x = torch.randn(8, 256, 8)  # [batch, seq, 8D]
    quantized, codes = compiled_quantizer(x, num_levels=4)

    print("✓ Compiled E8 quantizer")
    print(f"  Input shape: {x.shape}")
    print(f"  Output shape: {quantized.shape}")
    print(f"  Num codes: {len(codes)}")

    disable_compilation()


# =============================================================================
# EXAMPLE 3: Compile custom function
# =============================================================================


def example_compile_custom_function():
    """Compile a custom computational function."""
    print("\n=== Example 3: Custom Function Compilation ===")

    enable_compilation()

    # Define a function to compile
    def projection_chain(x: torch.Tensor) -> torch.Tensor:
        """Project E8(248) → E7(133) → E6(78)."""
        # Simplified projection (in reality would use Clebsch-Gordan matrices)
        x = x[..., :133]  # E8 → E7
        x = x[..., :78]  # E7 → E6
        return x

    # Compile for training
    compiled = compile_for_training(projection_chain, dynamic=True)

    # Test
    x = torch.randn(4, 248)
    result = compiled(x)

    print("✓ Compiled projection chain")
    print(f"  Input: {x.shape}")
    print(f"  Output: {result.shape}")

    disable_compilation()


# =============================================================================
# EXAMPLE 4: Verify correctness
# =============================================================================


def example_verify_correctness():
    """Verify compiled function produces same output as original."""
    print("\n=== Example 4: Correctness Verification ===")

    enable_compilation()

    # Original function
    def compute(x: torch.Tensor) -> torch.Tensor:
        return (x.pow(2) + x.sin()).mean(dim=-1)

    # Compile
    compiled = compile_for_inference(compute)

    # Verify
    x = torch.randn(16, 128)
    is_correct = verify_compilation_correctness(compute, compiled, x)

    print(f"✓ Correctness verified: {is_correct}")

    disable_compilation()


# =============================================================================
# EXAMPLE 5: Benchmark speedup
# =============================================================================


def example_benchmark_speedup():
    """Benchmark compiled vs non-compiled performance."""
    print("\n=== Example 5: Benchmark Speedup ===")

    enable_compilation()

    # Create a computationally intensive function
    def expensive_op(x: torch.Tensor) -> torch.Tensor:
        for _ in range(10):
            x = torch.matmul(x, x.transpose(-2, -1))
            x = x.relu()
        return x

    # Compile
    compiled = compile_for_inference(expensive_op)

    # Benchmark
    x = torch.randn(8, 64, 64)
    stats = benchmark_compilation(
        expensive_op,
        compiled,
        x,
        num_iterations=50,
        warmup_iterations=5,
    )

    print("✓ Benchmark complete:")
    print(f"  Original: {stats['original_mean_ms']:.2f} ms")
    print(f"  Compiled: {stats['compiled_mean_ms']:.2f} ms")
    print(f"  Speedup: {stats['speedup']:.2f}x")

    disable_compilation()


# =============================================================================
# EXAMPLE 6: Warmup for production
# =============================================================================


def example_warmup():
    """Warmup a compiled function before production use."""
    print("\n=== Example 6: Warmup ===")

    enable_compilation()

    # Compile
    def forward(x: torch.Tensor) -> torch.Tensor:
        return x.matmul(x.transpose(-2, -1))

    compiled = compile_for_inference(forward)

    # Warmup (first few calls are slow due to compilation)
    x = torch.randn(8, 128, 128)
    warmup_compiled(compiled, x, num_warmup=3)

    print("✓ Warmup complete, ready for fast production inference")

    disable_compilation()


# =============================================================================
# EXAMPLE 7: Compile octonion multiplication (hot path)
# =============================================================================


def example_compile_octonion_mul():
    """Compile octonion multiplication."""
    print("\n=== Example 7: Octonion Multiplication ===")

    enable_compilation()

    # Compile octonion multiplication
    from kagami.core.world_model.compilation import compile_octonion_mul

    compiled_mul = compile_octonion_mul(octonion_mul, mode="training")

    # Test with 7D octonions
    o1 = torch.randn(4, 7)
    o2 = torch.randn(4, 7)
    result = compiled_mul(o1, o2)

    print("✓ Compiled octonion multiplication")
    print(f"  Input shapes: {o1.shape}, {o2.shape}")
    print(f"  Output shape: {result.shape}")

    disable_compilation()


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("torch.compile Optimization Examples for Kagami")
    print("=" * 70)

    example_global_enable()
    example_compile_e8_quantizer()
    example_compile_custom_function()
    example_verify_correctness()
    example_benchmark_speedup()
    example_warmup()
    example_compile_octonion_mul()

    print("\n" + "=" * 70)
    print("All examples complete! ✓")
    print("=" * 70)
    print("\nNext steps:")
    print("1. Set ENABLE_TORCH_COMPILE=true in environment")
    print("2. Profile your training loop to identify hot paths")
    print("3. Compile hot paths with compile_for_training()")
    print("4. Verify correctness with verify_compilation_correctness()")
    print("5. Benchmark speedup with benchmark_compilation()")
    print("\nSafety reminders:")
    print("- Start with selective compilation (one module at a time)")
    print("- Always verify correctness before production use")
    print("- Graceful fallback if compilation fails (automatic)")
    print("- Default is DISABLED for safety")
