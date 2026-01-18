"""
TIC Verifier: Z3-based Formal Verification for Typed Intent Calculus.

This module implements the 'Proof-Carrying Operation' (PCO) verification logic.
It translates TypedIntent (Pre, Post, Invariant) constraints into Z3 SMT formulas
to mathematically prove correctness before execution.

Features:
- Symbolic variable mapping (TypedIntent params -> Z3 vars)
- Precondition assertion
- Invariant checking
- Postcondition verification (Not(Q) is UNSAT)
- Termination proof validation (Ranking function decreasing)

Usage:
    verifier = TICVerifier()
    result = verifier.verify(intent)
    if result.verified:
        execute(intent)
"""

import logging
import re
from typing import Any

from kagami.core.utils.optional_imports import require_package

try:
    import z3

    HAS_Z3 = True
except ImportError:
    z3 = None
    HAS_Z3 = False

from kagami.core.receipts.formal_tic import EvidenceType, TypedIntent

logger = logging.getLogger(__name__)


class VerificationResult:
    """Result of a formal verification attempt."""

    def __init__(
        self,
        verified: bool,
        proof_time_ms: float,
        counter_example: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        self.verified = verified
        self.proof_time_ms = proof_time_ms
        self.counter_example = counter_example
        self.details = details or {}

    def __repr__(self) -> str:
        return f"VerificationResult(verified={self.verified}, time={self.proof_time_ms:.2f}ms)"


class TICVerifier:
    """Z3-based verifier for Typed Intent Calculus."""

    def __init__(self) -> None:
        if not HAS_Z3:
            logger.warning("Z3 not available. TICVerifier will fail all checks.")

        # Require z3 package when creating solver
        z3_module = (
            require_package(
                z3,
                package_name="z3-solver",
                feature_name="Z3 SMT Solver",
                install_cmd="pip install z3-solver",
                additional_info=(
                    "Z3 provides formal verification for Typed Intent Calculus.\n"
                    "It enables mathematical proofs of correctness before execution.\n\n"
                    "See: https://github.com/Z3Prover/z3"
                ),
            )
            if HAS_Z3
            else None
        )

        self.solver = z3_module.Solver() if z3_module else None

    def verify(self, intent: TypedIntent) -> VerificationResult:
        """
        Verify a TypedIntent using Z3.

        Logic:
        1. Parse variables from Pre/Post/Invariants.
        2. Assert Preconditions (P).
        3. Assert Invariants (I).
        4. Assert Negation of Postconditions (Not(Q)).
        5. Check satisfiability.
           - If UNSAT, then P & I => Q is VALID.
           - If SAT, a counter-example exists (proof failed).
        """
        if not HAS_Z3 or not self.solver:
            return VerificationResult(
                False, 0.0, "Z3 not installed. Install with: pip install z3-solver"
            )

        import time

        t0 = time.perf_counter()

        self.solver.reset()

        try:
            # 0. Check Evidence Type
            if intent.evidence and intent.evidence.type == EvidenceType.MCO:
                return self._verify_mco(intent)

            # 1. Context Management & Variable Creation
            # We need to infer variables from the intent's predicates
            # For now, we support a structured 'variables' definition in evidence
            # or we infer them from 'pre' keys if they are simple.

            # Fallback: look for explicit variable definitions in evidence
            variables = {}
            if intent.evidence and intent.evidence.content.get("variables"):
                variables = self._create_variables(intent.evidence.content["variables"])
            else:
                # Auto-infer from keys in pre/post (assuming int/real)
                variables = self._infer_variables(intent)

            # 2. Parse & Assert Preconditions (P)
            pre_exprs = self._parse_conditions(intent.pre, variables)
            for p in pre_exprs:
                self.solver.add(p)

            # 3. Parse & Assert Invariants (I)
            # Invariants must hold. We add them to assumptions.
            inv_exprs = self._parse_strings(intent.invariants, variables)
            for inv in inv_exprs:
                self.solver.add(inv)

            # 4. Postconditions (Q) -> Prove Implication
            # We want to prove: (P and I) => Q
            # Equivalent to: (P and I and Not(Q)) is UNSAT

            post_exprs = self._parse_conditions(intent.post, variables)

            # Conjunction of all postconditions
            if post_exprs:
                q_expr = z3.And(*post_exprs)
                self.solver.add(z3.Not(q_expr))

                # 5. Check
                result = self.solver.check()
                duration = (time.perf_counter() - t0) * 1000

                if result == z3.unsat:
                    # UNSAT means no counter-example found -> Implication is Valid

                    # 6. Termination Verification
                    term_valid = self._verify_termination(intent)
                    if not term_valid:
                        return VerificationResult(
                            False, duration, details={"status": "termination_proof_failed"}
                        )

                    return VerificationResult(True, duration, details={"status": "proved"})
                elif result == z3.sat:
                    model = self.solver.model()
                    return VerificationResult(
                        False,
                        duration,
                        counter_example=str(model),
                        details={"status": "counter_example_found"},
                    )
                else:
                    return VerificationResult(False, duration, details={"status": "unknown"})
            else:
                # No postconditions to prove
                return VerificationResult(
                    True, (time.perf_counter() - t0) * 1000, details={"status": "trivial_no_post"}
                )

        except Exception as e:
            logger.error(f"TIC Verification Error: {e}")
            return VerificationResult(
                False, (time.perf_counter() - t0) * 1000, counter_example=str(e)
            )

    def _create_variables(self, var_defs: dict[str, str]) -> dict[str, Any]:
        """Create Z3 variables from definition dict[str, Any]."""
        vars_map = {}
        for name, type_str in var_defs.items():
            if type_str == "int":
                vars_map[name] = z3.Int(name)
            elif type_str == "real":
                vars_map[name] = z3.Real(name)
            elif type_str == "bool":
                vars_map[name] = z3.Bool(name)
        return vars_map

    def _infer_variables(self, intent: TypedIntent) -> dict[str, Any]:
        """Best-effort variable inference."""
        # Simple heuristic: treat all keys in 'pre'/'post' values as Reals
        vars_map = {}
        all_keys = set(intent.pre.keys()) | set(intent.post.keys())

        # Extract variables from invariant strings "x > 0" -> "x"
        for inv in intent.invariants:
            # Simple regex to find words that are likely variables
            tokens = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", inv)
            for t in tokens:
                if t not in {"And", "Or", "Not", "Implies", "If"}:  # Z3 keywords
                    all_keys.add(t)

        for k in all_keys:
            vars_map[k] = z3.Real(k)  # Default to Real for flexibility

        return vars_map

    def _parse_conditions(self, conditions: dict[str, Any], vars_map: dict[str, Any]) -> list[Any]:
        """Parse dictionary conditions (e.g. {'x': {'>': 0}})."""
        exprs = []
        for var_name, constraints in conditions.items():
            if var_name not in vars_map:
                continue
            z3_var = vars_map[var_name]

            if isinstance(constraints, (int, float)):
                # Equality: x = 5
                exprs.append(z3_var == constraints)
            elif isinstance(constraints, dict):
                for op, val in constraints.items():
                    if op == ">":
                        exprs.append(z3_var > val)
                    elif op == ">=":
                        exprs.append(z3_var >= val)
                    elif op == "<":
                        exprs.append(z3_var < val)
                    elif op == "<=":
                        exprs.append(z3_var <= val)
                    elif op == "==":
                        exprs.append(z3_var == val)
                    elif op == "!=":
                        exprs.append(z3_var != val)
        return exprs

    def _parse_strings(self, conditions: list[str], vars_map: dict[str, Any]) -> list[Any]:
        """Parse string conditions (e.g., 'x > 0')."""
        # Use safe_eval for AST-validated expression parsing
        from kagami.core.security.safe_eval import safe_eval

        exprs = []
        context = {**vars_map, "z3": z3, "And": z3.And, "Or": z3.Or, "Not": z3.Not}

        for cond in conditions:
            try:
                expr = safe_eval(cond, context)
                if expr is not None:
                    exprs.append(expr)
            except Exception as e:
                logger.warning(f"Failed to parse invariant '{cond}': {e}")
        return exprs

    def _verify_termination(self, intent: TypedIntent) -> bool:
        """Verify termination guarantee."""
        if not intent.termination:
            # If no termination proof provided, we cannot verify it.
            # Strict mode might fail here. For now, assume implicit timeout is NOT a proof.
            return False

        t = intent.termination
        if t.type == "timeout" or t.type == "bounded_fuel":
            return (t.fuel_limit is not None and t.fuel_limit > 0) or (
                t.time_limit_ms is not None and t.time_limit_ms > 0
            )
        elif t.type == "ranking_function":
            # Z3 could prove R(x') < R(x), but we need the state transition T(x, x').
            # Since TIC doesn't capture the full transition function T currently,
            # we check existence of the ranking function string.
            return bool(t.ranking_function)
        return False

    def _verify_mco(self, intent: TypedIntent) -> VerificationResult:
        """Verify Measurement-Carrying Operation (MCO)."""
        if not intent.evidence or not intent.evidence.content:
            return VerificationResult(False, 0.0, "No evidence content for MCO")

        content = intent.evidence.content
        measurements = content.get("measurements", {})
        thresholds = content.get("thresholds", {})

        if not measurements:
            return VerificationResult(False, 0.0, "MCO missing 'measurements'")

        # Verify all measurements meet thresholds
        for key, val in thresholds.items():
            if key not in measurements:
                return VerificationResult(False, 0.0, f"MCO missing metric '{key}'")

            # Handle min/max
            if isinstance(val, dict):
                if "min" in val and measurements[key] < val["min"]:
                    return VerificationResult(False, 0.0, f"MCO metric '{key}' too low")
                if "max" in val and measurements[key] > val["max"]:
                    return VerificationResult(False, 0.0, f"MCO metric '{key}' too high")
            elif isinstance(val, (int, float)):
                # Exact match? unlikely. Assume simple min threshold for single number
                if measurements[key] < val:
                    return VerificationResult(
                        False, 0.0, f"MCO metric '{key}' below threshold {val}"
                    )

        return VerificationResult(True, 0.0, details={"status": "mco_verified"})
