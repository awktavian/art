# SPDX-License-Identifier: MIT
"""Active Inference Benchmarks for K OS.

Validates the core Active Inference components:
- Expected Free Energy (EFE) computation
- World model prediction accuracy
- Policy selection via G(π) minimization
- Belief updating and learning

These benchmarks test the theoretical foundations of K OS.
"""

from kagami_benchmarks.active_inference.efe_benchmark import (
    EFEBenchmarkResult,
    run_efe_benchmark,
)
from kagami_benchmarks.active_inference.world_model_benchmark import (
    WorldModelBenchmarkResult,
    run_world_model_benchmark,
)

__all__ = [
    "EFEBenchmarkResult",
    "WorldModelBenchmarkResult",
    "run_efe_benchmark",
    "run_world_model_benchmark",
]
