"""Symbolic Reasoning System.

Provides formal reasoning capabilities:
1. Z3 SMT Solver - constraint solving, formal verification
2. Prolog Engine - logic programming, rule-based inference
3. Lean Integration - theorem proving (future)

Created: November 2, 2025
"""

from kagami.core.reasoning.symbolic.prolog_engine import (
    KnowledgeBase,
    PrologEngine,
    solve_graph_reachability,
    solve_kinship_problem,
)
from kagami.core.reasoning.symbolic.tic_verifier import TICVerifier
from kagami.core.reasoning.symbolic.z3_solver import (
    Z3ConstraintSolver,
    solve_constraint_problem,
)

__all__ = [
    "KnowledgeBase",
    # Prolog Engine
    "PrologEngine",
    # TIC Verification
    "TICVerifier",
    # Z3 SMT Solver
    "Z3ConstraintSolver",
    "solve_constraint_problem",
    "solve_graph_reachability",
    "solve_kinship_problem",
]
