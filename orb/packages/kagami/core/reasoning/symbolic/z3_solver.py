"""Z3 SMT Solver Integration for Constraint Solving and Formal Verification.

Enables K os to:
1. Solve constraint satisfaction problems
2. Prove logical properties
3. Verify API invariants
4. Synthesize code satisfying specifications

Based on Microsoft Z3 Theorem Prover.

Created: November 2, 2025
Status: Production-ready
"""
# pyright: reportGeneralTypeIssues=false
# pyright: reportAttributeAccessIssue=false
# Z3 library has incomplete type stubs

from __future__ import annotations

import logging
from typing import Any

from kagami.core.utils.optional_imports import require_package

logger = logging.getLogger(__name__)

z3 = None
try:
    import z3  # type: ignore[no-redef]

    HAS_Z3 = True
except ImportError:
    z3 = None
    HAS_Z3 = False
    logger.debug("z3-solver not available. Install with: pip install z3-solver")


class Z3ConstraintSolver:
    """Solve constraint satisfaction problems using Z3."""

    def __init__(self) -> None:
        """Initialize Z3 solver."""
        z3_module = require_package(  # type: ignore[var-annotated]
            z3,
            "z3-solver",
            "Z3 SMT Solver",
            install_cmd="pip install z3-solver",
            additional_info="Required for constraint solving and formal verification.",
        )

        self.solver = z3_module.Solver()
        logger.info("Z3ConstraintSolver initialized")

    def solve_sudoku(self, grid: list[list[int]]) -> list[list[int]] | None:
        """Solve a Sudoku puzzle using Z3.

        Args:
            grid: 9x9 grid with 0 for empty cells

        Returns:
            Solved grid or None if unsolvable
        """
        # Create 9x9 integer variables
        cells = [[z3.Int(f"cell_{i}_{j}") for j in range(9)] for i in range(9)]  # type: ignore[attr-defined]

        # Add constraints
        solver = z3.Solver()  # type: ignore[attr-defined]

        # Each cell must be 1-9
        for i in range(9):
            for j in range(9):
                solver.add(z3.And(cells[i][j] >= 1, cells[i][j] <= 9))  # type: ignore[attr-defined]

        # Row constraints: all different
        for i in range(9):
            solver.add(z3.Distinct([cells[i][j] for j in range(9)]))  # type: ignore[attr-defined]

        # Column constraints: all different
        for j in range(9):
            solver.add(z3.Distinct([cells[i][j] for i in range(9)]))  # type: ignore[attr-defined]

        # 3x3 box constraints: all different
        for box_i in range(3):
            for box_j in range(3):
                box_cells = [
                    cells[i][j]
                    for i in range(box_i * 3, (box_i + 1) * 3)
                    for j in range(box_j * 3, (box_j + 1) * 3)
                ]
                solver.add(z3.Distinct(box_cells))  # type: ignore[attr-defined]

        # Add given values
        for i in range(9):
            for j in range(9):
                if grid[i][j] != 0:
                    solver.add(cells[i][j] == grid[i][j])

        # Solve
        if solver.check() == z3.sat:  # type: ignore[attr-defined]
            model = solver.model()
            solution = [[model.evaluate(cells[i][j]).as_long() for j in range(9)] for i in range(9)]
            return solution
        else:
            return None

    def solve_scheduling(
        self,
        num_tasks: int,
        durations: list[int],
        dependencies: list[tuple[int, int]],
        max_time: int,
    ) -> dict[str, Any] | None:
        """Solve a task scheduling problem.

        Args:
            num_tasks: Number of tasks
            durations: Duration of each task
            dependencies: List of (task_i, task_j) where i must finish before j starts
            max_time: Maximum total time available

        Returns:
            Schedule dict[str, Any] with start times or None if infeasible
        """
        # Start time for each task
        start_times = [z3.Int(f"start_{i}") for i in range(num_tasks)]  # type: ignore[attr-defined]

        solver = z3.Solver()  # type: ignore[attr-defined]

        # All start times must be non-negative
        for st in start_times:
            solver.add(st >= 0)

        # All tasks must complete within max_time
        for i in range(num_tasks):
            solver.add(start_times[i] + durations[i] <= max_time)

        # Dependency constraints
        for i, j in dependencies:
            # Task i must finish before task j starts
            solver.add(start_times[i] + durations[i] <= start_times[j])

        # Solve
        if solver.check() == z3.sat:  # type: ignore[attr-defined]
            model = solver.model()
            schedule = {
                "start_times": [model.evaluate(start_times[i]).as_long() for i in range(num_tasks)],
                "end_times": [
                    model.evaluate(start_times[i]).as_long() + durations[i]
                    for i in range(num_tasks)
                ],
                "total_time": max(
                    model.evaluate(start_times[i]).as_long() + durations[i]
                    for i in range(num_tasks)
                ),
            }
            return schedule
        else:
            return None

    def verify_api_invariant(
        self, pre_condition: str, post_condition: str, variables: dict[str, str]
    ) -> dict[str, Any]:
        """Verify an API invariant using Z3.

        Args:
            pre_condition: Pre-condition as string (e.g., "x > 0")
            post_condition: Post-condition as string (e.g., "y == x * 2")
            variables: Variable definitions (name -> type)

        Returns:
            Verification result
        """
        solver = z3.Solver()  # type: ignore[attr-defined]

        # Create variables
        z3_vars = {}
        for var_name, var_type in variables.items():
            if var_type == "int":
                z3_vars[var_name] = z3.Int(var_name)  # type: ignore[attr-defined]
            elif var_type == "bool":
                z3_vars[var_name] = z3.Bool(var_name)  # type: ignore[attr-defined]
            elif var_type == "real":
                z3_vars[var_name] = z3.Real(var_name)  # type: ignore[attr-defined]

        # Add pre-condition
        try:
            from kagami.core.security.safe_eval import safe_eval

            pre_cond = safe_eval(pre_condition, z3_vars)
            solver.add(pre_cond)
        except Exception as e:
            return {"verified": False, "error": f"Invalid pre-condition: {e}"}

        # Add negation of post-condition (looking for counterexample)
        try:
            from kagami.core.security.safe_eval import safe_eval

            post_cond = safe_eval(post_condition, z3_vars)
            solver.add(z3.Not(post_cond))  # type: ignore[attr-defined]
        except Exception as e:
            return {"verified": False, "error": f"Invalid post-condition: {e}"}

        # Check if counterexample exists
        result = solver.check()

        if result == z3.unsat:  # type: ignore[attr-defined]
            # No counterexample = invariant holds
            return {"verified": True, "message": "Invariant verified"}
        elif result == z3.sat:  # type: ignore[attr-defined]
            # Counterexample found
            model = solver.model()
            counterexample = {var: model.evaluate(z3_var) for var, z3_var in z3_vars.items()}
            return {
                "verified": False,
                "counterexample": str(counterexample),
                "message": "Invariant does NOT hold",
            }
        else:
            return {"verified": False, "error": "Verification unknown"}

    def synthesize_function(
        self, input_output_examples: list[tuple[dict[str, int], int]], variable_names: list[str]
    ) -> str | None:
        """Synthesize a simple function from input-output examples.

        Args:
            input_output_examples: List of (inputs, output) pairs
            variable_names: Names of input variables

        Returns:
            Synthesized function as string or None
        """
        # This is a simplified version - real synthesis is complex
        # Try linear combination: output = a1*v1 + a2*v2 + ... + c

        num_vars = len(variable_names)
        coeffs = [z3.Int(f"coeff_{i}") for i in range(num_vars)]  # type: ignore[attr-defined]
        constant = z3.Int("constant")  # type: ignore[attr-defined]

        solver = z3.Solver()  # type: ignore[attr-defined]

        # Bound coefficients (reasonable range)
        for coeff in coeffs:
            solver.add(z3.And(coeff >= -10, coeff <= 10))  # type: ignore[attr-defined]
        solver.add(z3.And(constant >= -10, constant <= 10))  # type: ignore[attr-defined]

        # Add constraints from examples
        for inputs, output in input_output_examples:
            expr = sum(coeffs[i] * inputs[var] for i, var in enumerate(variable_names)) + constant
            solver.add(expr == output)

        # Solve
        if solver.check() == z3.sat:  # type: ignore[attr-defined]
            model = solver.model()

            # Build function string
            terms = []
            for i, var in enumerate(variable_names):
                coeff_val = model.evaluate(coeffs[i]).as_long()
                if coeff_val != 0:
                    if coeff_val == 1:
                        terms.append(var)
                    elif coeff_val == -1:
                        terms.append(f"-{var}")
                    else:
                        terms.append(f"{coeff_val}*{var}")

            const_val = model.evaluate(constant).as_long()
            if const_val != 0 or not terms:
                terms.append(str(const_val))

            return " + ".join(terms).replace("+ -", "- ")
        else:
            return None


def solve_constraint_problem(problem_type: str, **kwargs: Any) -> Any:
    """Solve a constraint problem using Z3.

    Args:
        problem_type: Type of problem ("sudoku", "scheduling", etc.)
        **kwargs: Problem-specific parameters

    Returns:
        Solution or None
    """
    if not HAS_Z3:
        logger.error("Z3 not available")
        return None

    solver = Z3ConstraintSolver()

    if problem_type == "sudoku":
        return solver.solve_sudoku(kwargs.get("grid", []))
    elif problem_type == "scheduling":
        return solver.solve_scheduling(
            kwargs.get("num_tasks", 0),
            kwargs.get("durations", []),
            kwargs.get("dependencies", []),
            kwargs.get("max_time", 100),
        )
    else:
        logger.error(f"Unknown problem type: {problem_type}")
        return None


__all__ = ["Z3ConstraintSolver", "solve_constraint_problem"]
