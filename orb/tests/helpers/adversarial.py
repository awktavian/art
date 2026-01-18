"""Adversarial Testing Suite.

Generates adversarial inputs to test robustness.
"""

from __future__ import annotations

import logging
import random
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class AdversarialTester:
    """Generates adversarial test cases."""

    def __init__(self, seed: int = 42) -> None:
        """Initialize adversarial tester.

        Args:
            seed: Random seed for reproducible test generation.
        """
        random.seed(seed)
        self._test_results: list[dict[str, Any]] = []

    async def test_robustness(
        self, target_func: Callable, valid_inputs: list[Any], num_tests: int = 100
    ) -> dict[str, Any]:
        """Test function robustness with adversarial inputs.

        Args:
            target_func: Function to test
            valid_inputs: List of valid inputs
            num_tests: Number of adversarial tests

        Returns:
            Test results dict
        """
        errors: list[dict[str, str]] = []
        results: dict[str, Any] = {
            "total_tests": num_tests,
            "passed": 0,
            "failed": 0,
            "errors": errors,
        }

        for _i in range(num_tests):
            # Generate adversarial input
            adversarial = self._generate_adversarial(valid_inputs)

            try:
                # Test should either pass or fail gracefully
                await target_func(adversarial)
                results["passed"] += 1
            except Exception as e:
                # Check if error is handled gracefully
                if "validation" in str(e).lower() or "invalid" in str(e).lower():
                    results["passed"] += 1  # Graceful failure
                else:
                    results["failed"] += 1
                    errors.append({"input": str(adversarial)[:100], "error": str(e)[:200]})

        self._test_results.append(results)
        return results

    def _generate_adversarial(self, valid_inputs: list[Any]) -> Any:
        """Generate adversarial input from valid examples."""
        if not valid_inputs:
            return None

        base = random.choice(valid_inputs)

        # Apply random mutation
        mutation = random.choice(
            [self._mutate_type, self._mutate_structure, self._mutate_values, self._mutate_extremes]
        )

        return mutation(base)

    def _mutate_type(self, value: Any) -> Any:
        """Mutate type (dict → list, str → int, etc.)."""
        if isinstance(value, dict):
            return list(value.items())
        elif isinstance(value, list):
            return {f"key_{i}": v for i, v in enumerate(value)}
        elif isinstance(value, str):
            try:
                return int(value)
            except (ValueError, TypeError):
                return 12345
        elif isinstance(value, (int, float)):
            return str(value)
        return value

    def _mutate_structure(self, value: Any) -> Any:
        """Mutate structure (add/remove fields)."""
        if isinstance(value, dict):
            mutated = value.copy()
            # Remove random key
            if mutated and random.random() > 0.5:
                key = random.choice(list(mutated.keys()))
                del mutated[key]
            # Add random key
            if random.random() > 0.5:
                mutated[f"random_{random.randint(0, 999)}"] = "injected"
            return mutated
        elif isinstance(value, list):
            mutated = value.copy()  # type: ignore[assignment]
            if mutated and random.random() > 0.5:
                mutated.pop(random.randint(0, len(mutated) - 1))
            return mutated
        return value

    def _mutate_values(self, value: Any) -> Any:
        """Mutate values (None, empty, huge, etc.)."""
        mutations: Any = [None, "", [], {}, 0, -1, 999999, "x" * 10000]
        return random.choice(mutations)

    def _mutate_extremes(self, value: Any) -> Any:
        """Mutate to extreme values."""
        if isinstance(value, (int, float)):
            return random.choice(
                [
                    float("inf"),
                    float("-inf"),
                    float("nan"),
                    2**63 - 1,
                    -(2**63),
                    0,
                    -1,
                    1e-100,
                    1e100,
                ]
            )
        elif isinstance(value, str):
            return random.choice(
                [
                    "",
                    "x" * 1000000,  # 1MB string
                    "\x00" * 100,  # Null bytes
                    "🔥" * 1000,  # Unicode
                ]
            )
        return value

    def get_results(self) -> dict[str, Any]:
        """Get aggregated test results."""
        if not self._test_results:
            return {}

        total_passed = sum(r["passed"] for r in self._test_results)
        total_failed = sum(r["failed"] for r in self._test_results)
        total_tests = sum(r["total_tests"] for r in self._test_results)

        return {
            "total_tests": total_tests,
            "passed": total_passed,
            "failed": total_failed,
            "pass_rate": total_passed / total_tests if total_tests > 0 else 0,
            "robustness_score": total_passed / total_tests if total_tests > 0 else 0,
        }
