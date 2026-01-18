"""HumanEval Benchmark Runner.

Code generation benchmark using handwritten Python programming problems.

Dataset: 164 hand-crafted Python programming problems.
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
class HumanEvalResult:
    """Result from a single HumanEval problem."""

    task_id: str
    prompt: str
    expected_signature: str
    generated_code: str | None
    test_passed: bool
    execution_output: str | None = None
    latency_ms: float = 0.0
    error: str | None = None


@dataclass
class HumanEvalBenchmarkResult:
    """Aggregated benchmark results."""

    total_problems: int
    passed: int
    pass_at_1: float
    avg_latency_ms: float
    results: list[HumanEvalResult] = field(default_factory=list)
    model_name: str = ""
    timestamp: float = field(default_factory=time.time)


class HumanEvalRunner(CodeProblemsRunnerBase):
    """HumanEval Benchmark Runner.

    Evaluates code generation via functional correctness.
    """

    def _get_sample_problems(self) -> list[dict[str, Any]]:
        """Get sample HumanEval-style problems for testing."""
        return [
            {
                "task_id": "HumanEval/0",
                "prompt": 'from typing import List\n\n\ndef has_close_elements(numbers: List[float], threshold: float) -> bool:\n    """ Check if in given list of numbers, are any two numbers closer to each other than\n    given threshold.\n    >>> has_close_elements([1.0, 2.0, 3.0], 0.5)\n    False\n    >>> has_close_elements([1.0, 2.8, 3.0, 4.0, 5.0, 2.0], 0.3)\n    True\n    """\n',
                "canonical_solution": "    for idx, elem in enumerate(numbers):\n        for idx2, elem2 in enumerate(numbers):\n            if idx != idx2:\n                distance = abs(elem - elem2)\n                if distance < threshold:\n                    return True\n\n    return False\n",
                "test": "def check(candidate):\n    assert candidate([1.0, 2.0, 3.9, 4.0, 5.0, 2.2], 0.3) == True\n    assert candidate([1.0, 2.0, 3.9, 4.0, 5.0, 2.2], 0.05) == False\n    assert candidate([1.0, 2.0, 5.9, 4.0, 5.0], 0.95) == True\n    assert candidate([1.0, 2.0, 5.9, 4.0, 5.0], 0.8) == False\n    assert candidate([1.0, 2.0, 3.0, 4.0, 5.0, 2.0], 0.1) == True\n    assert candidate([1.1, 2.2, 3.1, 4.1, 5.1], 1.0) == True\n    assert candidate([1.1, 2.2, 3.1, 4.1, 5.1], 0.5) == False\n\n",
                "entry_point": "has_close_elements",
            },
            {
                "task_id": "HumanEval/1",
                "prompt": "from typing import List\n\n\ndef separate_paren_groups(paren_string: str) -> List[str]:\n    \"\"\" Input to this function is a string containing multiple groups of nested parentheses. Your goal is to\n    separate those group into separate strings and return the list of those.\n    Separate groups are balanced (each open brace is properly closed) and not nested within each other\n    Ignore any spaces in the input string.\n    >>> separate_paren_groups('( ) (( )) (( )( ))')\n    ['()', '(())', '(()())']\n    \"\"\"\n",
                "canonical_solution": "    result = []\n    current_string = []\n    current_depth = 0\n\n    for c in paren_string:\n        if c == '(':\n            current_depth += 1\n            current_string.append(c)\n        elif c == ')':\n            current_depth -= 1\n            current_string.append(c)\n\n            if current_depth == 0:\n                result.append(''.join(current_string))\n                current_string.clear()\n\n    return result\n",
                "test": "def check(candidate):\n    assert candidate('(()()) ((())) () ((())()())') == [\n        '(()())', '((()))', '()', '((())()())'\n    ]\n    assert candidate('() (()) ((())) (((())))') == [\n        '()', '(())', '((()))', '(((())))'\n    ]\n    assert candidate('(()(()))') == ['(()(()))']\n    assert candidate('( ) (( )) (( )( ))') == ['()', '(())', '(()())']\n\n",
                "entry_point": "separate_paren_groups",
            },
            {
                "task_id": "HumanEval/2",
                "prompt": '\n\ndef truncate_number(number: float) -> float:\n    """ Given a positive floating point number, it can be decomposed into\n    and integer part (largest integer smaller than given number) and decimals\n    (leftover part always smaller than 1).\n\n    Return the decimal part of the number.\n    >>> truncate_number(3.5)\n    0.5\n    """\n',
                "canonical_solution": "    return number % 1.0\n",
                "test": "def check(candidate):\n    assert candidate(3.5) == 0.5\n    assert abs(candidate(1.25) - 0.25) < 1e-6\n    assert abs(candidate(123.0) - 0.0) < 1e-6\n\n",
                "entry_point": "truncate_number",
            },
            {
                "task_id": "HumanEval/3",
                "prompt": 'from typing import List\n\n\ndef below_threshold(l: List[int], t: int) -> bool:\n    """Return True if all numbers in the list l are below threshold t.\n    >>> below_threshold([1, 2, 4, 10], 100)\n    True\n    >>> below_threshold([1, 20, 4, 10], 5)\n    False\n    """\n',
                "canonical_solution": "    for e in l:\n        if e >= t:\n            return False\n    return True\n",
                "test": "def check(candidate):\n    assert candidate([1, 2, 4, 10], 100)\n    assert not candidate([1, 20, 4, 10], 5)\n    assert candidate([1, 20, 4, 10], 21)\n    assert candidate([1, 20, 4, 10], 22)\n    assert candidate([1, 8, 4, 10], 11)\n    assert not candidate([1, 8, 4, 10], 10)\n\n",
                "entry_point": "below_threshold",
            },
            {
                "task_id": "HumanEval/4",
                "prompt": 'from typing import List\n\n\ndef mean_absolute_deviation(numbers: List[float]) -> float:\n    """ For a given list of input numbers, calculate Mean Absolute Deviation\n    around the mean of this dataset.\n    Mean Absolute Deviation is the average absolute difference between each\n    element and a centerpoint (mean in this case):\n    MAD = average | x - x_mean |\n    >>> mean_absolute_deviation([1.0, 2.0, 3.0, 4.0])\n    1.0\n    """\n',
                "canonical_solution": "    mean = sum(numbers) / len(numbers)\n    return sum(abs(x - mean) for x in numbers) / len(numbers)\n",
                "test": "def check(candidate):\n    assert abs(candidate([1.0, 2.0, 3.0]) - 2.0/3.0) < 1e-6\n    assert abs(candidate([1.0, 2.0, 3.0, 4.0]) - 1.0) < 1e-6\n    assert abs(candidate([1.0, 2.0, 3.0, 4.0, 5.0]) - 6.0/5.0) < 1e-6\n\n",
                "entry_point": "mean_absolute_deviation",
            },
        ]

    def _build_prompt(self, problem: dict[str, Any]) -> str:
        """Build prompt for code generation.

        Args:
            problem: HumanEval problem dictionary.

        Returns:
            Formatted prompt string.
        """
        prompt = problem["prompt"]
        return f"""Complete the following Python function. Only output the function body, no explanations.

{prompt}"""

    def _extract_code(self, response: str, entry_point: str) -> str:
        """Extract generated code from model response.

        Args:
            response: Model's full response.
            entry_point: Function name to look for.

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
        in_function = False
        indent_level = 0

        for line in lines:
            if f"def {entry_point}" in line:
                in_function = True
                code_lines.append(line)
                # Get base indent
                indent_level = len(line) - len(line.lstrip())
                continue

            if in_function:
                # Check if we're still in the function
                stripped = line.strip()
                if (
                    stripped
                    and not line.startswith(" " * (indent_level + 1))
                    and not stripped.startswith("#")
                ):
                    # Check if this is a new top-level definition
                    if stripped.startswith("def ") or stripped.startswith("class "):
                        break
                code_lines.append(line)

        if code_lines:
            return "\n".join(code_lines)

        # Return cleaned response as fallback
        return response.strip()

    def _execute_code(
        self,
        prompt: str,
        generated_code: str,
        test_code: str,
        entry_point: str,
    ) -> tuple[bool, str]:
        """Execute generated code against test cases.

        Args:
            prompt: Original function prompt (includes signature).
            generated_code: Generated function body.
            test_code: Test assertions.
            entry_point: Function name.

        Returns:
            Tuple of (passed, output).
        """
        # Combine prompt with generated code
        if f"def {entry_point}" in generated_code:
            # Generated code includes full function
            full_code = generated_code
        else:
            # Assume generated code is just the body
            full_code = prompt + generated_code

        # Build test file
        test_file_content = f"""{full_code}

{test_code}

check({entry_point})
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
    ) -> HumanEvalResult:
        """Evaluate a single HumanEval problem.

        Args:
            problem: Problem dictionary.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens for response.

        Returns:
            HumanEvalResult with evaluation details.
        """
        task_id = problem["task_id"]
        prompt = problem["prompt"]
        test_code = problem["test"]
        entry_point = problem["entry_point"]

        start_time = time.time()

        try:
            llm = await self._get_llm_service()
            llm_prompt = self._build_prompt(problem)

            response = await llm.generate(
                prompt=llm_prompt,
                app_name="benchmark",
                max_tokens=max_tokens,
                temperature=temperature,
            )

            response_text = response if isinstance(response, str) else response.get("text", "")
            generated_code = self._extract_code(response_text, entry_point)

            # Execute and test
            passed, output = self._execute_code(prompt, generated_code, test_code, entry_point)

            latency_ms = (time.time() - start_time) * 1000

            return HumanEvalResult(
                task_id=task_id,
                prompt=prompt,
                expected_signature=entry_point,
                generated_code=generated_code,
                test_passed=passed,
                execution_output=output,
                latency_ms=latency_ms,
            )

        except Exception as e:
            logger.error(f"Error evaluating problem {task_id}: {e}")
            latency_ms = (time.time() - start_time) * 1000
            return HumanEvalResult(
                task_id=task_id,
                prompt=prompt,
                expected_signature=entry_point,
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
    ) -> HumanEvalBenchmarkResult:
        """Run HumanEval benchmark.

        Args:
            num_samples: Number of problems to evaluate (None = all).
            temperature: Sampling temperature.
            max_concurrent: Maximum concurrent evaluations.

        Returns:
            HumanEvalBenchmarkResult with aggregated metrics.
        """
        problems = self.load_problems(num_samples)
        logger.info(f"Starting HumanEval benchmark with {len(problems)} problems")

        results: list[HumanEvalResult] = []

        # Use semaphore for concurrency control
        semaphore = asyncio.Semaphore(max_concurrent)

        async def evaluate_with_semaphore(prob: dict) -> HumanEvalResult:
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

        logger.info(f"HumanEval Benchmark Complete: {passed}/{total} passed ({pass_at_1:.1%})")

        return HumanEvalBenchmarkResult(
            total_problems=total,
            passed=passed,
            pass_at_1=pass_at_1,
            avg_latency_ms=avg_latency,
            results=list(results),
        )


def run_humaneval(  # type: ignore[no-untyped-def]
    num_samples: int | None = None,
    temperature: float = 0.0,
    data_path: str | None = None,
    **kwargs,
) -> dict[str, Any]:
    """Run HumanEval benchmark.

    Args:
        num_samples: Number of samples to evaluate (None = all).
        temperature: Sampling temperature.
        data_path: Optional path to HumanEval dataset.
        **kwargs: Additional arguments (ignored for compatibility).

    Returns:
        Dictionary with benchmark results.
    """
    runner = HumanEvalRunner(data_path=data_path)

    try:
        result = asyncio.run(runner.run(num_samples=num_samples, temperature=temperature))
        return {
            "score": result.pass_at_1,
            "passed": result.passed,
            "total": result.total_problems,
            "pass_at_1": result.pass_at_1,
            "avg_latency_ms": result.avg_latency_ms,
            "status": "completed",
            "details": [
                {
                    "task_id": r.task_id,
                    "passed": r.test_passed,
                    "error": r.error,
                }
                for r in result.results
            ],
        }
    except Exception as e:
        logger.error(f"HumanEval benchmark failed: {e}")
        return {
            "score": 0.0,
            "status": "failed",
            "error": str(e),
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run_humaneval(num_samples=3)
    print(f"HumanEval Result: {result}")
