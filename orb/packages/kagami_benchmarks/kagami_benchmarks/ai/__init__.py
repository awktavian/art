# SPDX-License-Identifier: MIT
"""AI/ML Benchmarks for K os.

Individual capability benchmarks:
- HumanEval: Code generation
- MMLU: Multitask language understanding
- GSM8K: Math reasoning
- MBPP: Code generation
- GAIA: General AI assistants
- AgentBench: Multi-task agents
- WebArena: Web navigation
- SWE-bench: Software engineering

Hive intelligence benchmarks:
- Collective intelligence
- Knowledge sharing
- Emergence metrics
"""

from kagami_benchmarks.ai.gsm8k_runner import run_gsm8k
from kagami_benchmarks.ai.hive_intelligence_benchmark import run_hive_benchmark
from kagami_benchmarks.ai.humaneval_runner import run_humaneval
from kagami_benchmarks.ai.master_harness import (
    run_full_benchmark,
    run_hive_only,
    run_individual_only,
)
from kagami_benchmarks.ai.mbpp_runner import run_mbpp
from kagami_benchmarks.ai.mmlu_runner import run_mmlu
from kagami_benchmarks.ai.swebench_runner import run_verified as run_swebench_verified
from kagami_benchmarks.ai.webarena_smoke import run_smoke as run_webarena_smoke

__all__ = [
    # Master harness
    "run_full_benchmark",
    "run_gsm8k",
    # Hive benchmarks
    "run_hive_benchmark",
    "run_hive_only",
    "run_humaneval",
    "run_individual_only",
    "run_mbpp",
    "run_mmlu",
    # Individual benchmarks
    "run_swebench_verified",
    "run_webarena_smoke",
]
