"""Crystal Verification Module — Formal Verification Infrastructure.

Provides unified interface to formal verification tools:
- Z3 SMT Solver: Constraint satisfaction, invariant proofs
- Prolog Engine: Logic programming, graph reasoning
- TIC Verifier: Typed Intent Calculus proofs

Created: December 28, 2025
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class VerificationResult:
    """Result of a verification operation."""

    verified: bool
    tool: str
    proof_time_ms: float = 0.0
    counter_example: str | None = None
    details: dict[str, Any] = field(default_factory=dict[str, Any])
    crystal_verdict: str = ""

    def __post_init__(self) -> None:
        if not self.crystal_verdict:
            self.crystal_verdict = f"{'PROVED' if self.verified else 'DISPROVED'} via {self.tool}"


def run_verification(
    pre: str,
    post: str,
    variables: dict[str, str],
    tool: str = "z3",
) -> VerificationResult:
    """Run formal verification on pre/post conditions.

    Uses Z3 SMT solver to prove: Pre => Post

    Args:
        pre: Pre-condition (e.g., "x > 0")
        post: Post-condition (e.g., "y == x * 2")
        variables: Variable definitions {"x": "int", "y": "int"}
        tool: Verification tool ("z3", "prolog", "tic")

    Returns:
        VerificationResult with proof or counterexample

    Example:
        result = run_verification(
            pre="x > 0",
            post="x * 2 > 0",
            variables={"x": "int"}
        )
        assert result.verified
    """
    import time

    start = time.perf_counter()

    if tool == "z3":
        result = _verify_with_z3(pre, post, variables)
    elif tool == "prolog":
        result = _verify_with_prolog(pre, post, variables)
    else:
        result = VerificationResult(
            verified=False,
            tool=tool,
            details={"error": f"Unknown tool: {tool}"},
        )

    result.proof_time_ms = (time.perf_counter() - start) * 1000
    return result


def verify_invariant(
    pre_condition: str,
    post_condition: str,
    variables: dict[str, str],
) -> VerificationResult:
    """Verify an API invariant using Z3.

    Alias for run_verification with z3 tool.

    Args:
        pre_condition: Pre-condition
        post_condition: Post-condition
        variables: Variable definitions

    Returns:
        VerificationResult
    """
    return run_verification(pre_condition, post_condition, variables, tool="z3")


def verify_reachability(
    edges: list[tuple[str, str]],
    from_node: str,
    to_node: str,
) -> VerificationResult:
    """Verify graph reachability using Prolog.

    Uses logic programming to prove path existence.

    Args:
        edges: List of (from, to) edges
        from_node: Source node
        to_node: Target node

    Returns:
        VerificationResult with reachability proof
    """
    import time

    start = time.perf_counter()

    try:
        from kagami.core.reasoning.symbolic.prolog_engine import KnowledgeBase

        kb = KnowledgeBase()
        for src, dst in edges:
            kb.add_edge(src, dst)

        reachable = kb.is_reachable(from_node, to_node)

        return VerificationResult(
            verified=reachable,
            tool="prolog",
            proof_time_ms=(time.perf_counter() - start) * 1000,
            details={
                "from": from_node,
                "to": to_node,
                "edge_count": len(edges),
            },
            crystal_verdict=(
                f"PROVED: {to_node} is reachable from {from_node}."
                if reachable
                else f"DISPROVED: No path exists from {from_node} to {to_node}."
            ),
        )
    except Exception as e:
        logger.error(f"Prolog reachability failed: {e}")
        return VerificationResult(
            verified=False,
            tool="prolog",
            proof_time_ms=(time.perf_counter() - start) * 1000,
            details={"error": str(e)},
        )


def _verify_with_z3(
    pre: str,
    post: str,
    variables: dict[str, str],
) -> VerificationResult:
    """Verify using Z3 SMT solver."""
    try:
        from kagami.core.reasoning.symbolic.z3_solver import Z3ConstraintSolver

        solver = Z3ConstraintSolver()
        result = solver.verify_api_invariant(
            pre_condition=pre,
            post_condition=post,
            variables=variables,
        )

        return VerificationResult(
            verified=result.get("verified", False),
            tool="z3",
            counter_example=result.get("counterexample"),
            details=result,
            crystal_verdict=(
                "Invariant PROVED. The evidence supports the claim."
                if result.get("verified")
                else f"Invariant FAILED. Counterexample: {result.get('counterexample', 'unknown')}"
            ),
        )
    except Exception as e:
        logger.error(f"Z3 verification failed: {e}")
        return VerificationResult(
            verified=False,
            tool="z3",
            details={"error": str(e)},
        )


def _verify_with_prolog(
    pre: str,
    post: str,
    variables: dict[str, str],
) -> VerificationResult:
    """Verify using Prolog logic programming."""
    # Prolog verification for logical rules
    # This is a placeholder - Prolog is better for graph/logic queries
    return VerificationResult(
        verified=False,
        tool="prolog",
        details={"error": "Prolog better suited for graph reachability queries"},
    )


__all__ = [
    "VerificationResult",
    "run_verification",
    "verify_invariant",
    "verify_reachability",
]
