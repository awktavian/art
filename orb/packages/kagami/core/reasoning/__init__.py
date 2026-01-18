from __future__ import annotations

"""Reasoning strategies for K os agent operations.

This package provides scientific implementations:
- PC Algorithm (Spirtes et al., 2000) - Rigorous causal discovery
- Do-Calculus (Pearl, 2009) - Causal interventions
- Compute Budget - Adaptive reasoning budget allocation
- Narrator - Plan generation and narration
"""

# Compute budget and narrator
from .compute_budget import ComputeBudget, budget_for, get_default_mode
from .do_calculus import (
    DoCalculus,
    InterventionResult,
    get_do_calculus,
)
from .narrator import Plan, is_complex, narrate
from .pc_algorithm import (
    CausalEdge,
    PCAlgorithm,
    get_pc_algorithm,
)

__all__ = [
    "CausalEdge",
    # Compute budget and narrator
    "ComputeBudget",
    # Do-Calculus
    "DoCalculus",
    "InterventionResult",
    # PC Algorithm
    "PCAlgorithm",
    "Plan",
    "budget_for",
    "get_default_mode",
    "get_do_calculus",
    "get_pc_algorithm",
    "is_complex",
    "narrate",
]
