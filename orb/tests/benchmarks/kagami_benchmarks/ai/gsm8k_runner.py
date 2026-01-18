"""GSM8K Benchmark Runner.

Grade-school math problems benchmark for evaluating mathematical reasoning.

Dataset: 8.5K linguistically diverse grade school math word problems.
Metric: Accuracy (exact match of final numerical answer).
"""

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from kagami_benchmarks.shared import JSONProblemsMixin, LLMServiceMixin

logger = logging.getLogger(__name__)


@dataclass
class GSM8KResult:
    """Result from a single GSM8K problem."""

    question_id: str
    question: str
    expected_answer: str
    model_answer: str | None
    is_correct: bool
    reasoning: str | None = None
    latency_ms: float = 0.0
    error: str | None = None


@dataclass
class GSM8KBenchmarkResult:
    """Aggregated benchmark results."""

    total_problems: int
    correct: int
    accuracy: float
    avg_latency_ms: float
    results: list[GSM8KResult] = field(default_factory=list)
    model_name: str = ""
    timestamp: float = field(default_factory=time.time)


class GSM8KRunner(LLMServiceMixin, JSONProblemsMixin):
    """GSM8K Benchmark Runner.

    Uses chain-of-thought prompting for mathematical reasoning.
    """

    def __init__(
        self,
        data_path: str | Path | None = None,
        use_cot: bool = True,
    ) -> None:
        """Initialize GSM8K runner.

        Args:
            data_path: Path to GSM8K dataset JSON/JSONL file.
            use_cot: Whether to use chain-of-thought prompting.
        """
        self.data_path = Path(data_path) if data_path else None
        self.use_cot = use_cot
        self._llm_service = None
        self._problems: list[dict[str, Any]] = []

    def _get_sample_problems(self) -> list[dict[str, Any]]:
        """Get sample GSM8K-style problems for testing."""
        return [
            {
                "question": "Janet's ducks lay 16 eggs per day. She eats three for breakfast every morning and bakes muffins for her friends every day with four. She sells the remainder at the farmers' market daily for $2 per fresh duck egg. How much in dollars does she make every day at the farmers' market?",
                "answer": "Janet sells 16 - 3 - 4 = <<16-3-4=9>>9 duck eggs a day.\nShe makes 9 * 2 = $<<9*2=18>>18 every day at the farmer's market.\n#### 18",
            },
            {
                "question": "A robe takes 2 bolts of blue fiber and half that much white fiber. How many bolts in total does it take?",
                "answer": "It takes 2/2=<<2/2=1>>1 bolt of white fiber\nSo the total amount of fiber is 2+1=<<2+1=3>>3 bolts\n#### 3",
            },
            {
                "question": "Josh decides to try flipping a house. He buys a house for $80,000 and then puts in $50,000 in repairs. This increased the value of the house by 150%. How much profit did he make?",
                "answer": "The cost of the house and repairs came out to 80,000+50,000=$<<80000+50000=130000>>130,000\nHe increased the value of the house by 80,000*1.5=<<80000*1.5=120000>>120,000\nSo the new value of the house is 120,000+80,000=$<<120000+80000=200000>>200,000\nSo he made a profit of 200,000-130,000=$<<200000-130000=70000>>70,000\n#### 70000",
            },
            {
                "question": "James decides to run 3 sprints 3 times a week. He runs 60 meters each sprint. How many total meters does he run a week?",
                "answer": "He sprints 3*3=<<3*3=9>>9 times\nSo he runs 9*60=<<9*60=540>>540 meters\n#### 540",
            },
            {
                "question": "Every day, Wendi feeds each of her chickens three cups of mixed chicken feed, containing seeds, mealworms and vegetables to help keep them healthy. She gives the chickens their feed in three separate meals. In the morning, she gives her flock of chickens 15 cups of feed. In the afternoon, she gives her chickens another 25 cups of feed. How many cups of feed does she need to give her chickens in the final meal of the day if the size of Wendi's flock is 20 chickens?",
                "answer": "If each chicken eats 3 cups of feed per day, then for 20 chickens they would need 3*20=<<3*20=60>>60 cups of feed per day.\nIf she feeds the flock 15 cups of feed in the morning, and 25 cups in the afternoon, then the final meal would require 60-15-25=<<60-15-25=20>>20 cups of chicken feed.\n#### 20",
            },
        ]

    def _build_prompt(self, question: str) -> str:
        """Build prompt for GSM8K problem.

        Args:
            question: The math word problem.

        Returns:
            Formatted prompt string.
        """
        if self.use_cot:
            return f"""Solve the following math problem step by step. Show your reasoning, then give the final numerical answer after "#### ".

Question: {question}

Let me solve this step by step:"""
        else:
            return f"""Solve this math problem and give only the final numerical answer:

Question: {question}

Answer:"""

    def _extract_answer(self, response: str) -> str | None:
        """Extract numerical answer from model response.

        Args:
            response: Model's full response.

        Returns:
            Extracted numerical answer or None.
        """
        # Try to find answer after ####
        match = re.search(r"####\s*(-?[\d,]+\.?\d*)", response)
        if match:
            return match.group(1).replace(",", "")

        # Try to find the last number in the response
        numbers = re.findall(r"-?[\d,]+\.?\d*", response)
        if numbers:
            # Filter out very small numbers that are likely intermediate calculations
            valid_numbers = [
                n.replace(",", "")
                for n in numbers
                if len(n.replace(",", "").replace(".", "")) <= 15
            ]
            if valid_numbers:
                return valid_numbers[-1]  # type: ignore[no-any-return]

        return None

    def _extract_expected_answer(self, answer_str: str) -> str:
        """Extract expected answer from GSM8K answer format.

        Args:
            answer_str: Full answer string with reasoning.

        Returns:
            Numerical answer.
        """
        match = re.search(r"####\s*(-?[\d,]+\.?\d*)", answer_str)
        if match:
            return match.group(1).replace(",", "")
        return answer_str.strip()

    def _compare_answers(self, expected: str, actual: str | None) -> bool:
        """Compare expected and actual answers.

        Args:
            expected: Expected numerical answer.
            actual: Model's answer.

        Returns:
            True if answers match.
        """
        if actual is None:
            return False

        try:
            exp_val = float(expected.replace(",", ""))
            act_val = float(actual.replace(",", ""))
            # Allow small floating point tolerance
            return abs(exp_val - act_val) < 0.01
        except ValueError:
            return expected.strip() == actual.strip()

    async def evaluate_problem(
        self,
        problem: dict[str, Any],
        problem_id: str,
        temperature: float = 0.0,
        max_tokens: int = 512,
    ) -> GSM8KResult:
        """Evaluate a single GSM8K problem.

        Args:
            problem: Problem dictionary with 'question' and 'answer'.
            problem_id: Unique identifier for the problem.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens for response.

        Returns:
            GSM8KResult with evaluation details.
        """
        question = problem["question"]
        expected = self._extract_expected_answer(problem["answer"])

        start_time = time.time()

        try:
            llm = await self._get_llm_service()
            prompt = self._build_prompt(question)

            response = await llm.generate(
                prompt=prompt,
                app_name="benchmark",
                max_tokens=max_tokens,
                temperature=temperature,
            )

            response_text = response if isinstance(response, str) else response.get("text", "")
            model_answer = self._extract_answer(response_text)
            is_correct = self._compare_answers(expected, model_answer)

            latency_ms = (time.time() - start_time) * 1000

            return GSM8KResult(
                question_id=problem_id,
                question=question,
                expected_answer=expected,
                model_answer=model_answer,
                is_correct=is_correct,
                reasoning=response_text,
                latency_ms=latency_ms,
            )

        except Exception as e:
            logger.error(f"Error evaluating problem {problem_id}: {e}")
            latency_ms = (time.time() - start_time) * 1000
            return GSM8KResult(
                question_id=problem_id,
                question=question,
                expected_answer=expected,
                model_answer=None,
                is_correct=False,
                latency_ms=latency_ms,
                error=str(e),
            )

    async def run(
        self,
        num_samples: int = 100,
        temperature: float = 0.0,
        max_concurrent: int = 5,
    ) -> GSM8KBenchmarkResult:
        """Run GSM8K benchmark.

        Args:
            num_samples: Number of problems to evaluate.
            temperature: Sampling temperature.
            max_concurrent: Maximum concurrent evaluations.

        Returns:
            GSM8KBenchmarkResult with aggregated metrics.
        """
        logger.info(f"Starting GSM8K benchmark with {num_samples} samples")

        problems = self.load_problems(num_samples)
        results: list[GSM8KResult] = []

        # Use semaphore for concurrency control
        semaphore = asyncio.Semaphore(max_concurrent)

        async def evaluate_with_semaphore(prob: dict, idx: int) -> GSM8KResult:
            async with semaphore:
                return await self.evaluate_problem(prob, f"gsm8k_{idx}", temperature)

        # Run evaluations
        tasks = [evaluate_with_semaphore(p, i) for i, p in enumerate(problems)]
        results = await asyncio.gather(*tasks)

        # Calculate metrics
        correct = sum(1 for r in results if r.is_correct)
        total = len(results)
        accuracy = correct / total if total > 0 else 0.0
        avg_latency = sum(r.latency_ms for r in results) / total if total > 0 else 0.0

        logger.info(f"GSM8K Benchmark Complete: {correct}/{total} correct ({accuracy:.1%})")

        return GSM8KBenchmarkResult(
            total_problems=total,
            correct=correct,
            accuracy=accuracy,
            avg_latency_ms=avg_latency,
            results=list(results),
        )


def run_gsm8k(
    num_samples: int = 100,
    temperature: float = 0.0,
    use_orchestrator: bool = False,
    data_path: str | None = None,
) -> dict[str, Any]:
    """Run GSM8K benchmark.

    Args:
        num_samples: Number of samples to evaluate.
        temperature: Sampling temperature.
        use_orchestrator: Whether to use K OS orchestrator (future enhancement).
        data_path: Optional path to GSM8K dataset.

    Returns:
        Dictionary with benchmark results.
    """
    # Future: K OS orchestrator integration (use_orchestrator param reserved)
    _ = use_orchestrator

    runner = GSM8KRunner(data_path=data_path, use_cot=True)

    try:
        result = asyncio.run(runner.run(num_samples=num_samples, temperature=temperature))
        return {
            "score": result.accuracy,
            "correct": result.correct,
            "total": result.total_problems,
            "avg_latency_ms": result.avg_latency_ms,
            "status": "completed",
            "details": [
                {
                    "id": r.question_id,
                    "correct": r.is_correct,
                    "expected": r.expected_answer,
                    "actual": r.model_answer,
                }
                for r in result.results
            ],
        }
    except Exception as e:
        logger.error(f"GSM8K benchmark failed: {e}")
        return {
            "score": 0.0,
            "samples": num_samples,
            "status": "failed",
            "error": str(e),
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run_gsm8k(num_samples=5)
    print(f"GSM8K Result: {result}")
