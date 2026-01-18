# SPDX-License-Identifier: MIT
"""Critical Path Benchmarks for E2E Performance Testing.

Benchmarks for all critical functions in the system:
1. E8 Quantization (nearest_e8, ResidualE8LatticeVQ)
2. World Model (encode, decode, predict)
3. Fano Router (route, complexity inference)
4. CBF Safety (extract_safety_state, barrier computation)
5. RSSM Dynamics (step, predict_obs)

Created: December 22, 2025
"""

from __future__ import annotations

import gc
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import torch

from .circuit_timer import (
    CircuitTimer,
    PerformanceResult,
    TimedCircuitTest,
    run_timed_circuit_test,
)

logger = logging.getLogger(__name__)


# =============================================================================
# BASE BENCHMARK CLASS
# =============================================================================


@dataclass
class BenchmarkConfig:
    """Configuration for benchmarks."""

    batch_size: int = 32
    seq_len: int = 16
    warmup_iterations: int = 10
    test_iterations: int = 100
    device: str = "cpu"


class CriticalPathBenchmark(ABC):
    """Base class for critical path benchmarks."""

    def __init__(self, config: BenchmarkConfig | None = None):
        self.config = config or BenchmarkConfig()
        self.timer = CircuitTimer()
        self.device = torch.device(self.config.device)
        self._setup_device()

    def _setup_device(self) -> None:
        """Auto-detect best device."""
        if self.config.device == "auto":
            if torch.cuda.is_available():
                self.device = torch.device("cuda")
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                self.device = torch.device("mps")
            else:
                self.device = torch.device("cpu")

    @abstractmethod
    def setup(self) -> None:
        """Setup benchmark resources."""
        pass

    @abstractmethod
    def get_tests(self) -> list[TimedCircuitTest]:
        """Get list of circuit tests for this benchmark."""
        pass

    def run(self) -> list[PerformanceResult]:
        """Run all benchmark tests."""
        self.setup()
        results = []
        for test in self.get_tests():
            logger.info(f"🔌 {self.__class__.__name__}: {test.name}")
            result = run_timed_circuit_test(test)
            results.append(result)
            logger.info(result.summary)
        return results

    def teardown(self) -> None:
        """Cleanup benchmark resources."""
        gc.collect()
        if self.device.type == "cuda":
            torch.cuda.empty_cache()


# =============================================================================
# E8 QUANTIZATION BENCHMARK
# =============================================================================


class E8Benchmark(CriticalPathBenchmark):
    """Benchmark for E8 quantization operations."""

    def setup(self) -> None:
        """Setup E8 quantizer and test data."""
        from kagami.math.e8 import create_e8_quantizer, nearest_e8

        self.nearest_e8 = nearest_e8

        # Create quantizer (without caching for fair benchmark)
        self.quantizer = create_e8_quantizer(enable_cache=False)

        # Test data: random 8D vectors
        self.test_vector_8d = torch.randn(8, device=self.device)
        self.test_batch_8d = torch.randn(self.config.batch_size, 8, device=self.device)
        self.test_seq_8d = torch.randn(
            self.config.batch_size, self.config.seq_len, 8, device=self.device
        )

    def get_tests(self) -> list[TimedCircuitTest]:
        """Get E8 benchmark tests."""
        return [
            # Single vector quantization
            TimedCircuitTest(
                name="e8_nearest_single",
                function=self.nearest_e8,
                args=(self.test_vector_8d,),
                warmup_iterations=self.config.warmup_iterations,
                test_iterations=self.config.test_iterations,
                expected_max_ms=1.0,  # Should be <1ms
            ),
            # Batch quantization
            TimedCircuitTest(
                name="e8_nearest_batch",
                function=self.nearest_e8,
                args=(self.test_batch_8d,),
                warmup_iterations=self.config.warmup_iterations,
                test_iterations=self.config.test_iterations,
                expected_max_ms=5.0,  # Should be <5ms for batch
            ),
            # Sequence quantization (batch x seq x 8)
            TimedCircuitTest(
                name="e8_nearest_sequence",
                function=self._quantize_sequence,
                warmup_iterations=self.config.warmup_iterations,
                test_iterations=self.config.test_iterations,
                expected_max_ms=20.0,
            ),
        ]

    def _quantize_sequence(self) -> torch.Tensor:
        """Quantize full sequence."""
        # Reshape to [B*T, 8], quantize, reshape back
        batch, seq_len, dim = self.test_seq_8d.shape
        flat = self.test_seq_8d.view(-1, dim)
        quantized = self.nearest_e8(flat)
        return quantized.view(batch, seq_len, dim)


# =============================================================================
# WORLD MODEL BENCHMARK
# =============================================================================


class WorldModelBenchmark(CriticalPathBenchmark):
    """Benchmark for KagamiWorldModel operations."""

    def setup(self) -> None:
        """Setup world model and test data."""
        from kagami.core.world_model import create_model

        # Create minimal model for benchmarking
        self.model = create_model(preset="minimal", device=str(self.device))
        self.model.eval()

        # Get actual bulk dimension from model
        bulk_dim = self.model.config.bulk_dim

        # Test data matching model dimensions
        self.test_obs = torch.randn(
            self.config.batch_size,
            self.config.seq_len,
            bulk_dim,
            device=self.device,
        )

    def get_tests(self) -> list[TimedCircuitTest]:
        """Get world model benchmark tests."""
        return [
            # Encode operation
            TimedCircuitTest(
                name="world_model_encode",
                function=self._encode,
                warmup_iterations=self.config.warmup_iterations,
                test_iterations=self.config.test_iterations,
                expected_max_ms=50.0,  # 50ms budget for encode
            ),
            # Full forward pass
            TimedCircuitTest(
                name="world_model_forward",
                function=self._forward,
                warmup_iterations=self.config.warmup_iterations,
                test_iterations=self.config.test_iterations,
                expected_max_ms=100.0,  # 100ms budget for full pass
            ),
        ]

    def _encode(self) -> Any:
        """Encode observations."""
        with torch.no_grad():
            return self.model.encode(self.test_obs)

    def _forward(self) -> Any:
        """Full forward pass."""
        with torch.no_grad():
            return self.model(self.test_obs)


# =============================================================================
# FANO ROUTER BENCHMARK
# =============================================================================


class FanoRouterBenchmark(CriticalPathBenchmark):
    """Benchmark for Fano Action Router operations."""

    def setup(self) -> None:
        """Setup Fano router."""
        from kagami.core.unified_agents.fano_action_router import create_fano_router

        self.router = create_fano_router()

        # Test actions covering different complexities
        self.simple_action = "ping"
        self.moderate_action = "create_user"
        self.complex_action = "analyze_architecture_and_implement_security"

        self.simple_params = {"target": "health"}
        self.moderate_params = {"name": "test", "email": "test@example.com"}
        self.complex_params = {
            "domain": "security",
            "modules": ["auth", "api", "storage"],
            "constraints": {"performance": "high", "security": "maximum"},
        }

    def get_tests(self) -> list[TimedCircuitTest]:
        """Get Fano router benchmark tests."""
        return [
            # Simple routing (single colony)
            TimedCircuitTest(
                name="fano_route_simple",
                function=self.router.route,
                args=(self.simple_action, self.simple_params),
                warmup_iterations=self.config.warmup_iterations,
                test_iterations=self.config.test_iterations,
                expected_max_ms=1.0,  # <1ms for simple
            ),
            # Moderate routing (Fano line)
            TimedCircuitTest(
                name="fano_route_moderate",
                function=self.router.route,
                args=(self.moderate_action, self.moderate_params),
                warmup_iterations=self.config.warmup_iterations,
                test_iterations=self.config.test_iterations,
                expected_max_ms=5.0,  # <5ms for moderate
            ),
            # Complex routing (all colonies)
            TimedCircuitTest(
                name="fano_route_complex",
                function=self.router.route,
                args=(self.complex_action, self.complex_params),
                kwargs={"complexity": 0.8},  # Force all-colonies mode
                warmup_iterations=self.config.warmup_iterations,
                test_iterations=self.config.test_iterations,
                expected_max_ms=10.0,  # <10ms for complex
            ),
            # Cache hit performance
            TimedCircuitTest(
                name="fano_route_cache_hit",
                function=self._route_cached,
                warmup_iterations=50,  # More warmup to populate cache
                test_iterations=self.config.test_iterations,
                expected_max_ms=0.5,  # <0.5ms for cache hit
            ),
        ]

    def _route_cached(self) -> Any:
        """Route with cache-friendly pattern."""
        # Same action should hit cache
        return self.router.route(self.simple_action, self.simple_params)


# =============================================================================
# CBF SAFETY BENCHMARK
# =============================================================================


class CBFBenchmark(CriticalPathBenchmark):
    """Benchmark for Control Barrier Function safety checks."""

    def setup(self) -> None:
        """Setup CBF components."""
        from kagami.core.safety.control_barrier_function import (
            extract_safety_state,
            get_safety_filter,
        )

        self.extract_safety_state = extract_safety_state
        self.cbf_filter = get_safety_filter()

        # Test contexts
        self.safe_context = {
            "operation": "query",
            "action": "list_files",
            "target": "documents",
            "user_input": "Show me the document list",
        }
        self.risky_context = {
            "operation": "delete",
            "action": "remove_all",
            "target": "database",
            "user_input": "Delete all user data from the system",
        }

    def get_tests(self) -> list[TimedCircuitTest]:
        """Get CBF benchmark tests."""
        return [
            # Safe operation classification
            TimedCircuitTest(
                name="cbf_extract_safe",
                function=self.extract_safety_state,
                args=(self.safe_context,),
                warmup_iterations=self.config.warmup_iterations,
                test_iterations=self.config.test_iterations,
                expected_max_ms=50.0,  # 50ms budget (includes ML inference)
            ),
            # Risky operation classification
            TimedCircuitTest(
                name="cbf_extract_risky",
                function=self.extract_safety_state,
                args=(self.risky_context,),
                warmup_iterations=self.config.warmup_iterations,
                test_iterations=self.config.test_iterations,
                expected_max_ms=50.0,
            ),
            # Raw barrier computation
            TimedCircuitTest(
                name="cbf_compute_barrier",
                function=self.cbf_filter.compute_barrier,  # type: ignore[attr-defined]
                args=("Test operation for safety check",),
                warmup_iterations=self.config.warmup_iterations,
                test_iterations=self.config.test_iterations,
                expected_max_ms=30.0,
            ),
        ]


# =============================================================================
# RSSM DYNAMICS BENCHMARK
# =============================================================================


class RSSMBenchmark(CriticalPathBenchmark):
    """Benchmark for RSSM dynamics operations."""

    def setup(self) -> None:
        """Setup RSSM and test data."""
        try:
            from kagami.core.world_model.colony_rssm import ColonyRSSMConfig, OrganismRSSM

            config = ColonyRSSMConfig(
                obs_dim=15,  # E8(8) + S7(7)
                deterministic_dim=128,
                stochastic_dim=14,
                action_dim=8,
                num_colonies=7,
                embed_dim=64,
            )
            self.rssm = OrganismRSSM(config)
            self.rssm.to(self.device)
            self.rssm.eval()

            # Test data
            batch_size = self.config.batch_size
            self.h = torch.zeros(batch_size, 128, device=self.device)
            self.z = torch.zeros(batch_size, 14, device=self.device)
            self.action = torch.randn(batch_size, 8, device=self.device)
            self.obs = torch.randn(batch_size, 15, device=self.device)

            self.rssm_available = True
        except Exception as e:
            logger.warning(f"RSSM benchmark setup failed: {e}")
            self.rssm_available = False

    def get_tests(self) -> list[TimedCircuitTest]:
        """Get RSSM benchmark tests."""
        if not self.rssm_available:
            return []

        return [
            # Posterior step (with observation)
            TimedCircuitTest(
                name="rssm_posterior_step",
                function=self._posterior_step,
                warmup_iterations=self.config.warmup_iterations,
                test_iterations=self.config.test_iterations,
                expected_max_ms=5.0,
            ),
            # Prior step (without observation)
            TimedCircuitTest(
                name="rssm_prior_step",
                function=self._prior_step,
                warmup_iterations=self.config.warmup_iterations,
                test_iterations=self.config.test_iterations,
                expected_max_ms=3.0,
            ),
            # Observation prediction
            TimedCircuitTest(
                name="rssm_predict_obs",
                function=self._predict_obs,
                warmup_iterations=self.config.warmup_iterations,
                test_iterations=self.config.test_iterations,
                expected_max_ms=2.0,
            ),
        ]

    def _posterior_step(self) -> tuple:
        """RSSM posterior step with observation."""
        with torch.no_grad():
            return self.rssm.dynamics.step(self.h, self.z, self.action, obs=self.obs)  # type: ignore[operator, no-any-return, union-attr]  # type: ignore[operator, no-any-return, union-attr]

    def _prior_step(self) -> tuple:
        """RSSM prior step without observation."""
        with torch.no_grad():
            return self.rssm.dynamics.step(self.h, self.z, self.action, obs=None)  # type: ignore[operator, no-any-return, union-attr]  # type: ignore[operator, no-any-return, union-attr]

    def _predict_obs(self) -> torch.Tensor:
        """Predict observation from state."""
        with torch.no_grad():
            return self.rssm.predict_obs(self.h, self.z)


# =============================================================================
# BENCHMARK RUNNER
# =============================================================================


def run_all_benchmarks(
    config: BenchmarkConfig | None = None,
    benchmarks: list[str] | None = None,
) -> dict[str, list[PerformanceResult]]:
    """Run all critical path benchmarks.

    Args:
        config: Benchmark configuration
        benchmarks: List of benchmark names to run (None = all)

    Returns:
        Dictionary mapping benchmark name to list of results
    """
    config = config or BenchmarkConfig()

    available_benchmarks = {
        "e8": E8Benchmark,
        "world_model": WorldModelBenchmark,
        "fano_router": FanoRouterBenchmark,
        "cbf": CBFBenchmark,
        "rssm": RSSMBenchmark,
    }

    if benchmarks is None:
        benchmarks = list(available_benchmarks.keys())

    results: dict[str, list[PerformanceResult]] = {}

    for name in benchmarks:
        if name not in available_benchmarks:
            logger.warning(f"Unknown benchmark: {name}")
            continue

        logger.info(f"\n{'=' * 60}")
        logger.info(f"🔬 Running {name.upper()} Benchmark")
        logger.info(f"{'=' * 60}")

        try:
            benchmark_class = available_benchmarks[name]
            benchmark = benchmark_class(config)  # type: ignore[abstract]
            benchmark_results = benchmark.run()
            results[name] = benchmark_results
            benchmark.teardown()
        except Exception as e:
            logger.error(f"❌ Benchmark {name} failed: {e}")
            results[name] = [
                PerformanceResult(
                    name=f"{name}_error",
                    mean_ms=0,
                    std_ms=0,
                    min_ms=0,
                    max_ms=0,
                    p50_ms=0,
                    p95_ms=0,
                    p99_ms=0,
                    iterations=0,
                    throughput_ops_per_sec=0,
                    passed=False,
                    error=str(e),
                )
            ]

    # Summary
    logger.info(f"\n{'=' * 60}")
    logger.info("📊 BENCHMARK SUMMARY")
    logger.info(f"{'=' * 60}")

    total_passed = 0
    total_failed = 0

    for _benchmark_name, benchmark_results in results.items():
        for result in benchmark_results:
            if result.passed:
                total_passed += 1
            else:
                total_failed += 1
            logger.info(result.summary)

    logger.info(f"\n✅ Passed: {total_passed}, ❌ Failed: {total_failed}")

    return results


# =============================================================================
# CLI ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    parser = argparse.ArgumentParser(description="Run critical path benchmarks")
    parser.add_argument(
        "--benchmarks",
        nargs="+",
        choices=["e8", "world_model", "fano_router", "cbf", "rssm"],
        help="Benchmarks to run (default: all)",
    )
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size")
    parser.add_argument("--iterations", type=int, default=100, help="Test iterations")
    parser.add_argument("--device", type=str, default="cpu", help="Device (cpu, cuda, mps, auto)")

    args = parser.parse_args()

    config = BenchmarkConfig(
        batch_size=args.batch_size,
        test_iterations=args.iterations,
        device=args.device,
    )

    results = run_all_benchmarks(config=config, benchmarks=args.benchmarks)
