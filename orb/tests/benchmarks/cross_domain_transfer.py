"""Cross-Domain Transfer Benchmarks.

Tests ability to transfer learning from one domain to another:
- CODE → MATH: Apply coding patterns to mathematical reasoning
- MATH → SCIENCE: Apply mathematical thinking to scientific problems
- SCIENCE → CODE: Apply scientific method to code design

Measures transfer learning accuracy and generalization capability.
"""

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class CrossDomainBenchmark:
    """Benchmark cross-domain transfer learning."""

    def __init__(self):
        self.results = {
            "code_to_math": [],
            "math_to_science": [],
            "science_to_code": [],
            "baseline_performance": {},
            "transfer_performance": {},
        }

    async def run_all(self) -> dict[str, Any]:
        """Run all cross-domain transfer tests."""
        logger.info("🧪 Starting cross-domain transfer benchmarks...")

        # Test each direction
        await self.test_code_to_math()
        await self.test_math_to_science()
        await self.test_science_to_code()

        # Compute transfer metrics
        self.compute_transfer_metrics()

        return self.results

    async def test_code_to_math(self):
        """Test CODE → MATH transfer."""
        logger.info("📊 Testing CODE → MATH transfer...")

        # CODE domain tasks (baseline)
        code_tasks = [
            {
                "task": "Write a function to find the nth Fibonacci number",
                "domain": "code",
                "expected_concepts": ["recursion", "memoization", "iteration"],
            },
            {
                "task": "Implement binary search algorithm",
                "domain": "code",
                "expected_concepts": ["divide_conquer", "logarithmic"],
            },
            {
                "task": "Create a sorting algorithm",
                "domain": "code",
                "expected_concepts": ["comparison", "optimization"],
            },
        ]

        # MATH domain tasks (transfer target)
        math_tasks = [
            {
                "task": "Prove the Fibonacci sequence has a closed-form solution using recursion",
                "domain": "math",
                "transfer_from": "code",
                "expected_transfer": ["recursion", "iteration", "patterns"],
            },
            {
                "task": "Use bisection method to find roots (like binary search for numbers)",
                "domain": "math",
                "transfer_from": "code",
                "expected_transfer": ["divide_conquer", "logarithmic"],
            },
            {
                "task": "Optimize a mathematical expression (like sorting by value)",
                "domain": "math",
                "transfer_from": "code",
                "expected_transfer": ["comparison", "optimization"],
            },
        ]

        # Baseline: Test CODE domain performance
        code_accuracy = await self._test_domain(code_tasks, "code_baseline")

        # Transfer: Test MATH domain with CODE experience
        math_accuracy = await self._test_domain(math_tasks, "math_transfer")

        self.results["code_to_math"] = {
            "baseline": code_accuracy,
            "transfer": math_accuracy,
            "transfer_efficiency": math_accuracy / code_accuracy if code_accuracy > 0 else 0,
            "tasks_completed": len(math_tasks),
        }

        logger.info(
            f"  CODE→MATH: baseline={code_accuracy:.1%}, "  # type: ignore[index]
            f"transfer={math_accuracy:.1%}, "
            f"efficiency={self.results['code_to_math']['transfer_efficiency']:.1%}"
        )

    async def test_math_to_science(self):
        """Test MATH → SCIENCE transfer."""
        logger.info("📊 Testing MATH → SCIENCE transfer...")

        math_tasks = [
            {
                "task": "Solve quadratic equation using discriminant",
                "domain": "math",
                "expected_concepts": ["formula", "roots", "algebra"],
            },
            {
                "task": "Calculate probability of compound events",
                "domain": "math",
                "expected_concepts": ["probability", "independence"],
            },
            {
                "task": "Integrate a polynomial function",
                "domain": "math",
                "expected_concepts": ["calculus", "area"],
            },
        ]

        science_tasks = [
            {
                "task": "Use quadratic formula to calculate projectile motion",
                "domain": "science",
                "transfer_from": "math",
                "expected_transfer": ["formula", "roots", "physics"],
            },
            {
                "task": "Calculate probability of genetic inheritance (like compound events)",
                "domain": "science",
                "transfer_from": "math",
                "expected_transfer": ["probability", "biology"],
            },
            {
                "task": "Find work done by integrating force over distance",
                "domain": "science",
                "transfer_from": "math",
                "expected_transfer": ["calculus", "physics"],
            },
        ]

        math_accuracy = await self._test_domain(math_tasks, "math_baseline")
        science_accuracy = await self._test_domain(science_tasks, "science_transfer")

        self.results["math_to_science"] = {
            "baseline": math_accuracy,
            "transfer": science_accuracy,
            "transfer_efficiency": science_accuracy / math_accuracy if math_accuracy > 0 else 0,
            "tasks_completed": len(science_tasks),
        }

        logger.info(
            f"  MATH→SCIENCE: baseline={math_accuracy:.1%}, "  # type: ignore[index]
            f"transfer={science_accuracy:.1%}, "
            f"efficiency={self.results['math_to_science']['transfer_efficiency']:.1%}"
        )

    async def test_science_to_code(self):
        """Test SCIENCE → CODE transfer."""
        logger.info("📊 Testing SCIENCE → CODE transfer...")

        science_tasks = [
            {
                "task": "Design an experiment with control and variables",
                "domain": "science",
                "expected_concepts": ["hypothesis", "control", "variables"],
            },
            {
                "task": "Analyze data to find patterns",
                "domain": "science",
                "expected_concepts": ["observation", "pattern", "conclusion"],
            },
            {
                "task": "Classify organisms using taxonomy",
                "domain": "science",
                "expected_concepts": ["classification", "hierarchy"],
            },
        ]

        code_tasks = [
            {
                "task": "Design A/B test framework (like controlled experiment)",
                "domain": "code",
                "transfer_from": "science",
                "expected_transfer": ["hypothesis", "control", "testing"],
            },
            {
                "task": "Implement pattern recognition algorithm",
                "domain": "code",
                "transfer_from": "science",
                "expected_transfer": ["observation", "pattern", "classification"],
            },
            {
                "task": "Build hierarchical data structure (like taxonomy)",
                "domain": "code",
                "transfer_from": "science",
                "expected_transfer": ["classification", "hierarchy", "structure"],
            },
        ]

        science_accuracy = await self._test_domain(science_tasks, "science_baseline")
        code_accuracy = await self._test_domain(code_tasks, "code_transfer")

        self.results["science_to_code"] = {
            "baseline": science_accuracy,
            "transfer": code_accuracy,
            "transfer_efficiency": code_accuracy / science_accuracy if science_accuracy > 0 else 0,
            "tasks_completed": len(code_tasks),
        }

        logger.info(
            f"  SCIENCE→CODE: baseline={science_accuracy:.1%}, "  # type: ignore[index]
            f"transfer={code_accuracy:.1%}, "
            f"efficiency={self.results['science_to_code']['transfer_efficiency']:.1%}"
        )

    async def _test_domain(self, tasks: list[dict], test_id: str) -> float:
        """Test performance on domain tasks."""
        try:
            from kagami.core.services.llm import get_llm_service

            llm = get_llm_service()
            successes = 0

            for task in tasks:
                try:
                    # Generate solution
                    prompt = f"""Task: {task["task"]}
Domain: {task["domain"]}

Solve this task. Be specific and show your reasoning."""

                    response = await llm.generate(
                        prompt=prompt,
                        app_name="cross_domain_benchmark",
                        task_type="reasoning",
                        temperature=0.3,
                    )

                    # Simple success criteria: response length > 50 chars and mentions expected concepts
                    response_lower = response.lower()
                    expected = task.get("expected_concepts", []) + task.get("expected_transfer", [])

                    # Check if at least 1 expected concept is mentioned
                    if len(response) > 50 and any(
                        concept.lower().replace("_", " ") in response_lower for concept in expected
                    ):
                        successes += 1

                except Exception as e:
                    logger.debug(f"Task failed: {e}")

            accuracy = successes / len(tasks) if tasks else 0
            self.results["baseline_performance"][test_id] = accuracy  # type: ignore[index]

            return accuracy

        except Exception as e:
            logger.error(f"Domain test failed: {e}")
            return 0.0

    def compute_transfer_metrics(self):
        """Compute overall transfer learning metrics."""
        all_transfer_efficiencies = [
            self.results["code_to_math"].get("transfer_efficiency", 0),
            self.results["math_to_science"].get("transfer_efficiency", 0),
            self.results["science_to_code"].get("transfer_efficiency", 0),
        ]

        valid_efficiencies = [e for e in all_transfer_efficiencies if e > 0]

        self.results["summary"] = {
            "avg_transfer_efficiency": (
                sum(valid_efficiencies) / len(valid_efficiencies) if valid_efficiencies else 0
            ),
            "transfer_directions_tested": 3,
            "successful_transfers": sum(
                1 for e in all_transfer_efficiencies if e > 0.5
            ),  # >50% efficiency
            "timestamp": time.time(),
        }

        # Grade transfer capability
        avg_eff = self.results["summary"]["avg_transfer_efficiency"]  # type: ignore[index]
        if avg_eff > 0.8:
            grade = "A+"
        elif avg_eff > 0.7:
            grade = "A"
        elif avg_eff > 0.6:
            grade = "B"
        elif avg_eff > 0.5:
            grade = "C"
        else:
            grade = "D"

        self.results["summary"]["grade"] = grade  # type: ignore[index]

        logger.info(
            f"📊 Cross-domain transfer summary: avg_efficiency={avg_eff:.1%}, grade={grade}"
        )


async def main():
    """Run cross-domain transfer benchmarks."""
    logging.basicConfig(level=logging.INFO)

    benchmark = CrossDomainBenchmark()
    results = await benchmark.run_all()

    # Save results
    output_path = Path("artifacts/cross_domain_transfer_results.json")
    output_path.parent.mkdir(exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    logger.info(f"✅ Results saved to {output_path}")

    # Print summary
    print("\n" + "=" * 60)
    print("CROSS-DOMAIN TRANSFER BENCHMARK RESULTS")
    print("=" * 60)
    print(f"\nOverall Grade: {results['summary']['grade']}")
    print(f"Average Transfer Efficiency: {results['summary']['avg_transfer_efficiency']:.1%}")
    print("\nBy Direction:")
    print(
        f"  CODE → MATH: {results['code_to_math']['transfer_efficiency']:.1%} "
        f"(baseline: {results['code_to_math']['baseline']:.1%})"
    )
    print(
        f"  MATH → SCIENCE: {results['math_to_science']['transfer_efficiency']:.1%} "
        f"(baseline: {results['math_to_science']['baseline']:.1%})"
    )
    print(
        f"  SCIENCE → CODE: {results['science_to_code']['transfer_efficiency']:.1%} "
        f"(baseline: {results['science_to_code']['baseline']:.1%})"
    )
    print("\n" + "=" * 60)

    return results


if __name__ == "__main__":
    asyncio.run(main())
