"""MBPP Benchmark Runner.

Mostly Basic Python Programming benchmark for evaluating code generation
on simple Python programming tasks.

Dataset: 974 crowd-sourced Python programming problems.
Metric: Pass@k (functional correctness via unit tests).
"""

import asyncio
import logging
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from kagami_benchmarks.shared import CodeProblemsRunnerBase

logger = logging.getLogger(__name__)


@dataclass
class MBPPResult:
    """Result from a single MBPP problem."""

    task_id: str
    description: str
    generated_code: str | None
    test_passed: bool
    execution_output: str | None = None
    latency_ms: float = 0.0
    error: str | None = None


@dataclass
class MBPPBenchmarkResult:
    """Aggregated benchmark results."""

    total_problems: int
    passed: int
    pass_at_1: float
    avg_latency_ms: float
    results: list[MBPPResult] = field(default_factory=list)
    model_name: str = ""
    timestamp: float = field(default_factory=time.time)


class MBPPRunner(CodeProblemsRunnerBase):
    """MBPP Benchmark Runner.

    Evaluates Python code generation on basic programming tasks.
    """

    def _get_sample_problems(self) -> list[dict[str, Any]]:
        """Get sample MBPP-style problems for testing."""
        return [
            {
                "task_id": 1,
                "text": "Write a function to find the minimum cost path to reach (m, n) from (0, 0) for the given cost matrix.",
                "code": "R = 3\nC = 3\ndef min_cost(cost, m, n):\n\ttc = [[0 for x in range(C)] for x in range(R)]\n\ttc[0][0] = cost[0][0]\n\tfor i in range(1, m+1):\n\t\ttc[i][0] = tc[i-1][0] + cost[i][0]\n\tfor j in range(1, n+1):\n\t\ttc[0][j] = tc[0][j-1] + cost[0][j]\n\tfor i in range(1, m+1):\n\t\tfor j in range(1, n+1):\n\t\t\ttc[i][j] = min(tc[i-1][j-1], tc[i-1][j], tc[i][j-1]) + cost[i][j]\n\treturn tc[m][n]",
                "test_list": [
                    "assert min_cost([[1, 2, 3], [4, 8, 2], [1, 5, 3]], 2, 2) == 8",
                    "assert min_cost([[2, 3, 4], [5, 9, 3], [2, 6, 4]], 2, 2) == 12",
                    "assert min_cost([[3, 4, 5], [6, 10, 4], [3, 7, 5]], 2, 2) == 16",
                ],
            },
            {
                "task_id": 2,
                "text": "Write a function to find the similar elements from the given two tuple lists.",
                "code": "def similar_elements(test_tup1, test_tup2):\n\tres = tuple(set(test_tup1) & set(test_tup2))\n\treturn res",
                "test_list": [
                    "assert similar_elements((3, 4, 5, 6),(5, 7, 4, 10)) == (4, 5)",
                    "assert similar_elements((1, 2, 3, 4),(5, 4, 3, 7)) == (3, 4)",
                    "assert similar_elements((11, 12, 14, 13),(17, 15, 14, 13)) == (13, 14)",
                ],
            },
            {
                "task_id": 3,
                "text": "Write a python function to identify non-prime numbers.",
                "code": "import math\ndef is_not_prime(n):\n\tresult = False\n\tfor i in range(2, int(math.sqrt(n)) + 1):\n\t\tif n % i == 0:\n\t\t\tresult = True\n\treturn result",
                "test_list": [
                    "assert is_not_prime(2) == False",
                    "assert is_not_prime(10) == True",
                    "assert is_not_prime(35) == True",
                ],
            },
            {
                "task_id": 4,
                "text": "Write a function to find the largest integers from a given list of numbers using heap queue algorithm.",
                "code": "import heapq as hq\ndef heap_queue_largest(nums, n):\n\tlargest_nums = hq.nlargest(n, nums)\n\treturn largest_nums",
                "test_list": [
                    "assert heap_queue_largest([25, 35, 22, 85, 14, 65, 75, 22, 58], 3) == [85, 75, 65]",
                    "assert heap_queue_largest([25, 35, 22, 85, 14, 65, 75, 22, 58], 2) == [85, 75]",
                    "assert heap_queue_largest([25, 35, 22, 85, 14, 65, 75, 22, 58], 5) == [85, 75, 65, 58, 35]",
                ],
            },
            {
                "task_id": 5,
                "text": "Write a function to check whether the given number is even or not using bitwise operator.",
                "code": "def is_Even(n):\n\tif n & 1:\n\t\treturn False\n\telse:\n\t\treturn True",
                "test_list": [
                    "assert is_Even(1) == False",
                    "assert is_Even(2) == True",
                    "assert is_Even(3) == False",
                ],
            },
        ]

    def _build_prompt(self, problem: dict[str, Any]) -> str:
        """Build prompt for code generation.

        Args:
            problem: MBPP problem dictionary.

        Returns:
            Formatted prompt string.
        """
        description = problem["text"]
        # Include one test case as example
        test_cases = problem.get("test_list", [])
        example = test_cases[0] if test_cases else ""

        return f"""Write a Python function based on the following description.

Description: {description}

Example test case:
{example}

Write only the Python code, no explanations:"""

    def _extract_code(self, response: str) -> str:
        """Extract generated code from model response.

        Args:
            response: Model's full response.

        Returns:
            Extracted code.
        """
        # Try to extract code block
        code_match = re.search(r"```python\n(.*?)```", response, re.DOTALL)
        if code_match:
            return code_match.group(1).strip()

        code_match = re.search(r"```\n(.*?)```", response, re.DOTALL)
        if code_match:
            return code_match.group(1).strip()

        # Look for function definition
        lines = response.split("\n")
        code_lines = []
        in_code = False

        for line in lines:
            # Start capturing at import or def
            if line.strip().startswith(("import ", "from ", "def ")):
                in_code = True

            if in_code:
                code_lines.append(line)

        if code_lines:
            return "\n".join(code_lines)

        return response.strip()

    def _execute_code(
        self,
        generated_code: str,
        test_cases: list[str],
    ) -> tuple[bool, str]:
        """Execute generated code against test cases.

        Args:
            generated_code: Generated function code.
            test_cases: List of assertion test cases.

        Returns:
            Tuple of (passed, output).
        """
        # Build test file
        test_code = "\n".join(test_cases)
        test_file_content = f"""{generated_code}

{test_code}
print("All tests passed!")
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(test_file_content)
            temp_path = f.name

        try:
            result = subprocess.run(
                ["python", temp_path],
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )

            if result.returncode == 0:
                return True, result.stdout
            else:
                return False, f"STDERR: {result.stderr}\nSTDOUT: {result.stdout}"

        except subprocess.TimeoutExpired:
            return False, "Execution timed out"
        except Exception as e:
            return False, f"Execution error: {e}"
        finally:
            Path(temp_path).unlink(missing_ok=True)

    async def evaluate_problem(
        self,
        problem: dict[str, Any],
        temperature: float = 0.0,
        max_tokens: int = 512,
    ) -> MBPPResult:
        """Evaluate a single MBPP problem.

        Args:
            problem: Problem dictionary.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens for response.

        Returns:
            MBPPResult with evaluation details.
        """
        task_id = str(problem.get("task_id", "unknown"))
        description = problem["text"]
        test_cases = problem.get("test_list", [])

        start_time = time.time()

        try:
            llm = await self._get_llm_service()
            prompt = self._build_prompt(problem)

            response = await llm.generate(
                prompt=prompt,
                app_name="benchmark",
                max_tokens=max_tokens,
                temperature=temperature,
            )

            response_text = response if isinstance(response, str) else response.get("text", "")
            generated_code = self._extract_code(response_text)

            # Execute and test
            passed, output = self._execute_code(generated_code, test_cases)

            latency_ms = (time.time() - start_time) * 1000

            return MBPPResult(
                task_id=task_id,
                description=description,
                generated_code=generated_code,
                test_passed=passed,
                execution_output=output,
                latency_ms=latency_ms,
            )

        except Exception as e:
            logger.error(f"Error evaluating problem {task_id}: {e}")
            latency_ms = (time.time() - start_time) * 1000
            return MBPPResult(
                task_id=task_id,
                description=description,
                generated_code=None,
                test_passed=False,
                latency_ms=latency_ms,
                error=str(e),
            )

    async def run(
        self,
        num_samples: int | None = None,
        temperature: float = 0.0,
        max_concurrent: int = 3,
    ) -> MBPPBenchmarkResult:
        """Run MBPP benchmark.

        Args:
            num_samples: Number of problems to evaluate.
            temperature: Sampling temperature.
            max_concurrent: Maximum concurrent evaluations.

        Returns:
            MBPPBenchmarkResult with aggregated metrics.
        """
        problems = self.load_problems(num_samples)
        logger.info(f"Starting MBPP benchmark with {len(problems)} problems")

        results: list[MBPPResult] = []

        # Use semaphore for concurrency control
        semaphore = asyncio.Semaphore(max_concurrent)

        async def evaluate_with_semaphore(prob: dict) -> MBPPResult:
            async with semaphore:
                return await self.evaluate_problem(prob, temperature)

        # Run evaluations
        tasks = [evaluate_with_semaphore(p) for p in problems]
        results = await asyncio.gather(*tasks)

        # Calculate metrics
        passed = sum(1 for r in results if r.test_passed)
        total = len(results)
        pass_at_1 = passed / total if total > 0 else 0.0
        avg_latency = sum(r.latency_ms for r in results) / total if total > 0 else 0.0

        logger.info(f"MBPP Benchmark Complete: {passed}/{total} passed ({pass_at_1:.1%})")

        return MBPPBenchmarkResult(
            total_problems=total,
            passed=passed,
            pass_at_1=pass_at_1,
            avg_latency_ms=avg_latency,
            results=list(results),
        )


def run_mbpp(  # type: ignore[no-untyped-def]
    num_samples: int | None = None,
    temperature: float = 0.0,
    data_path: str | None = None,
    **kwargs,
) -> dict[str, Any]:
    """Run MBPP benchmark.

    Args:
        num_samples: Number of samples to evaluate.
        temperature: Sampling temperature.
        data_path: Optional path to MBPP dataset.
        **kwargs: Additional arguments (ignored for compatibility).

    Returns:
        Dictionary with benchmark results.
    """
    runner = MBPPRunner(data_path=data_path)

    try:
        result = asyncio.run(runner.run(num_samples=num_samples, temperature=temperature))
        return {
            "score": result.pass_at_1,
            "passed": result.passed,
            "total": result.total_problems,
            "pass_at_1": result.pass_at_1,
            "avg_latency_ms": result.avg_latency_ms,
            "status": "completed",
        }
    except Exception as e:
        logger.error(f"MBPP benchmark failed: {e}")
        return {
            "score": 0.0,
            "status": "failed",
            "error": str(e),
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run_mbpp(num_samples=3)
    print(f"MBPP Result: {result}")
