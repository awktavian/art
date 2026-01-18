# SPDX-License-Identifier: MIT
"""Performance benchmarking and timed circuit testing module.

This module provides comprehensive performance testing for critical paths:
- E8 quantization latency
- World model encode/decode/predict
- Fano router routing decisions
- CBF safety checks
- RSSM dynamics

Created: December 22, 2025
"""

from .circuit_timer import (
    CircuitTimer,
    PerformanceResult,
    TimedCircuitTest,
    profile_function,
    run_timed_circuit_tests,
    timed,
)
from .critical_path_benchmarks import (
    BenchmarkConfig,
    CBFBenchmark,
    CriticalPathBenchmark,
    E8Benchmark,
    FanoRouterBenchmark,
    RSSMBenchmark,
    WorldModelBenchmark,
    run_all_benchmarks,
)
from .data_flow_optimizer import (
    CopyAnalysis,
    DataFlowOptimizer,
    FlowOptimization,
    OptimizedForwardWrapper,
    TensorCopyTracker,
    analyze_module_data_flow,
    detect_unnecessary_copies,
    generate_optimization_report,
)

__all__ = [
    "BenchmarkConfig",
    "CBFBenchmark",
    "CircuitTimer",
    # Data flow optimization
    "CopyAnalysis",
    "CriticalPathBenchmark",
    "DataFlowOptimizer",
    "E8Benchmark",
    "FanoRouterBenchmark",
    "FlowOptimization",
    "OptimizedForwardWrapper",
    "PerformanceResult",
    "RSSMBenchmark",
    "TensorCopyTracker",
    "TimedCircuitTest",
    "WorldModelBenchmark",
    "analyze_module_data_flow",
    "detect_unnecessary_copies",
    "generate_optimization_report",
    "profile_function",
    "run_all_benchmarks",
    "run_timed_circuit_tests",
    "timed",
]
