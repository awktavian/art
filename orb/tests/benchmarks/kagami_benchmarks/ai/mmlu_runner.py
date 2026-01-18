"""MMLU Benchmark Runner.

Massive Multitask Language Understanding benchmark for evaluating
broad knowledge and reasoning across 57 subjects.

Dataset: 14K+ multiple choice questions across 57 subjects.
Metric: Accuracy (correct answer selection).
"""

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from kagami_benchmarks.shared import LLMServiceMixin

logger = logging.getLogger(__name__)


@dataclass
class MMLUResult:
    """Result from a single MMLU question."""

    question_id: str
    subject: str
    question: str
    choices: list[str]
    expected_answer: str
    model_answer: str | None
    is_correct: bool
    reasoning: str | None = None
    latency_ms: float = 0.0
    error: str | None = None


@dataclass
class MMLUBenchmarkResult:
    """Aggregated benchmark results."""

    total_questions: int
    correct: int
    accuracy: float
    avg_latency_ms: float
    by_subject: dict[str, dict[str, float]] = field(default_factory=dict)
    results: list[MMLUResult] = field(default_factory=list)
    model_name: str = ""
    timestamp: float = field(default_factory=time.time)


class MMLURunner(LLMServiceMixin):
    """MMLU Benchmark Runner.

    Evaluates language understanding across multiple domains.
    """

    # MMLU subjects organized by category
    SUBJECTS = {
        "STEM": [
            "abstract_algebra",
            "anatomy",
            "astronomy",
            "college_biology",
            "college_chemistry",
            "college_computer_science",
            "college_mathematics",
            "college_physics",
            "computer_security",
            "conceptual_physics",
            "electrical_engineering",
            "elementary_mathematics",
            "high_school_biology",
            "high_school_chemistry",
            "high_school_computer_science",
            "high_school_mathematics",
            "high_school_physics",
            "high_school_statistics",
            "machine_learning",
        ],
        "Humanities": [
            "formal_logic",
            "high_school_european_history",
            "high_school_us_history",
            "high_school_world_history",
            "international_law",
            "jurisprudence",
            "logical_fallacies",
            "moral_disputes",
            "moral_scenarios",
            "philosophy",
            "prehistory",
            "professional_law",
            "world_religions",
        ],
        "Social Sciences": [
            "econometrics",
            "high_school_geography",
            "high_school_government_and_politics",
            "high_school_macroeconomics",
            "high_school_microeconomics",
            "high_school_psychology",
            "human_sexuality",
            "professional_psychology",
            "public_relations",
            "security_studies",
            "sociology",
            "us_foreign_policy",
        ],
        "Other": [
            "business_ethics",
            "clinical_knowledge",
            "college_medicine",
            "global_facts",
            "human_aging",
            "management",
            "marketing",
            "medical_genetics",
            "miscellaneous",
            "nutrition",
            "professional_accounting",
            "professional_medicine",
            "virology",
        ],
    }

    def __init__(
        self,
        data_path: str | Path | None = None,
        subjects: list[str] | None = None,
    ) -> None:
        """Initialize MMLU runner.

        Args:
            data_path: Path to MMLU dataset directory.
            subjects: Specific subjects to evaluate (None = all).
        """
        self.data_path = Path(data_path) if data_path else None
        self.subjects = subjects
        self._llm_service = None
        self._questions: list[dict[str, Any]] = []

    def load_questions(
        self,
        num_samples: int | None = None,
        split: str = "test",
    ) -> list[dict[str, Any]]:
        """Load MMLU questions from dataset.

        Args:
            num_samples: Optional limit on number of samples.
            split: Dataset split (dev/val/test).

        Returns:
            List of question dictionaries.
        """
        questions = []

        # Try loading from file if path provided
        if self.data_path and self.data_path.exists():
            import csv

            for category, subjects in self.SUBJECTS.items():
                for subject in subjects:
                    if self.subjects and subject not in self.subjects:
                        continue

                    csv_path = self.data_path / split / f"{subject}_{split}.csv"
                    if not csv_path.exists():
                        continue

                    with open(csv_path, encoding="utf-8") as f:
                        reader = csv.reader(f)
                        for row in reader:
                            if len(row) >= 6:
                                questions.append(
                                    {
                                        "subject": subject,
                                        "category": category,
                                        "question": row[0],
                                        "choices": [row[1], row[2], row[3], row[4]],
                                        "answer": row[5],
                                    }
                                )

        # If no file, use sample questions for testing
        if not questions:
            questions = self._get_sample_questions()

        if num_samples:
            questions = questions[:num_samples]

        self._questions = questions
        return questions

    def _get_sample_questions(self) -> list[dict[str, Any]]:
        """Get sample MMLU-style questions for testing."""
        return [
            {
                "subject": "abstract_algebra",
                "category": "STEM",
                "question": "Find the degree for the given field extension Q(sqrt(2), sqrt(3), sqrt(18)) over Q.",
                "choices": ["0", "4", "2", "6"],
                "answer": "B",
            },
            {
                "subject": "anatomy",
                "category": "STEM",
                "question": "Which of the following structures is derived from ectoderm?",
                "choices": ["Thyroid gland", "Adrenal cortex", "Adrenal medulla", "Liver"],
                "answer": "C",
            },
            {
                "subject": "philosophy",
                "category": "Humanities",
                "question": 'According to Moore\'s "ideal utilitarianism," the two most valuable things in themselves are:',
                "choices": [
                    "pleasure and friendship",
                    "aesthetic enjoyment and friendship",
                    "knowledge and happiness",
                    "pleasure and knowledge",
                ],
                "answer": "B",
            },
            {
                "subject": "high_school_psychology",
                "category": "Social Sciences",
                "question": "Which of the following best describes the 'cocktail party effect'?",
                "choices": [
                    "The tendency to drink more alcohol when in social settings",
                    "The ability to focus on one conversation in a noisy room",
                    "The phenomenon of memory loss after consuming alcohol",
                    "The tendency to be more outgoing when drinking",
                ],
                "answer": "B",
            },
            {
                "subject": "business_ethics",
                "category": "Other",
                "question": "The practice of holding business stakeholders accountable is known as:",
                "choices": [
                    "Corporate social responsibility",
                    "Business ethics",
                    "Corporate governance",
                    "Corporate accountability",
                ],
                "answer": "C",
            },
        ]

    def _build_prompt(self, question: dict[str, Any]) -> str:
        """Build prompt for MMLU question.

        Args:
            question: MMLU question dictionary.

        Returns:
            Formatted prompt string.
        """
        q_text = question["question"]
        choices = question["choices"]

        choice_labels = ["A", "B", "C", "D"]
        choices_text = "\n".join(
            [f"{label}. {choice}" for label, choice in zip(choice_labels, choices, strict=False)]
        )

        return f"""Answer the following multiple choice question. Give only the letter of the correct answer (A, B, C, or D).

Question: {q_text}

{choices_text}

Answer:"""

    def _extract_answer(self, response: str) -> str | None:
        """Extract answer letter from model response.

        Args:
            response: Model's full response.

        Returns:
            Extracted answer letter or None.
        """
        response = response.strip().upper()

        # Try to find direct answer letter
        if response in ["A", "B", "C", "D"]:
            return response

        # Look for pattern like "The answer is A" or "(A)"
        patterns = [
            r"(?:answer|correct).*?([ABCD])\b",
            r"\(([ABCD])\)",
            r"^([ABCD])[.\s:]",
            r"([ABCD])\s*$",
        ]

        for pattern in patterns:
            match = re.search(pattern, response, re.IGNORECASE)
            if match:
                return match.group(1).upper()

        # Last resort: first letter found
        for char in response:
            if char.upper() in "ABCD":
                return char.upper()

        return None

    async def evaluate_question(
        self,
        question: dict[str, Any],
        question_id: str,
        temperature: float = 0.0,
        max_tokens: int = 50,
    ) -> MMLUResult:
        """Evaluate a single MMLU question.

        Args:
            question: Question dictionary.
            question_id: Unique identifier.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens for response.

        Returns:
            MMLUResult with evaluation details.
        """
        q_text = question["question"]
        expected = question["answer"]
        subject = question.get("subject", "unknown")

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
            is_correct = model_answer == expected.upper()

            latency_ms = (time.time() - start_time) * 1000

            return MMLUResult(
                question_id=question_id,
                subject=subject,
                question=q_text,
                choices=question["choices"],
                expected_answer=expected,
                model_answer=model_answer,
                is_correct=is_correct,
                reasoning=response_text,
                latency_ms=latency_ms,
            )

        except Exception as e:
            logger.error(f"Error evaluating question {question_id}: {e}")
            latency_ms = (time.time() - start_time) * 1000
            return MMLUResult(
                question_id=question_id,
                subject=subject,
                question=q_text,
                choices=question["choices"],
                expected_answer=expected,
                model_answer=None,
                is_correct=False,
                latency_ms=latency_ms,
                error=str(e),
            )

    async def run(
        self,
        num_samples: int | None = None,
        temperature: float = 0.0,
        max_concurrent: int = 5,
    ) -> MMLUBenchmarkResult:
        """Run MMLU benchmark.

        Args:
            num_samples: Number of questions to evaluate.
            temperature: Sampling temperature.
            max_concurrent: Maximum concurrent evaluations.

        Returns:
            MMLUBenchmarkResult with aggregated metrics.
        """
        questions = self.load_questions(num_samples)
        logger.info(f"Starting MMLU benchmark with {len(questions)} questions")

        results: list[MMLUResult] = []

        # Use semaphore for concurrency control
        semaphore = asyncio.Semaphore(max_concurrent)

        async def evaluate_with_semaphore(q: dict, idx: int) -> MMLUResult:
            async with semaphore:
                return await self.evaluate_question(q, f"mmlu_{idx}", temperature)

        # Run evaluations
        tasks = [evaluate_with_semaphore(q, i) for i, q in enumerate(questions)]
        results = await asyncio.gather(*tasks)

        # Calculate metrics
        correct = sum(1 for r in results if r.is_correct)
        total = len(results)
        accuracy = correct / total if total > 0 else 0.0
        avg_latency = sum(r.latency_ms for r in results) / total if total > 0 else 0.0

        # Calculate per-subject metrics
        by_subject: dict[str, dict[str, float]] = {}
        for r in results:
            if r.subject not in by_subject:
                by_subject[r.subject] = {"correct": 0, "total": 0}
            by_subject[r.subject]["total"] += 1
            if r.is_correct:
                by_subject[r.subject]["correct"] += 1

        for subject in by_subject:
            total_s = by_subject[subject]["total"]
            correct_s = by_subject[subject]["correct"]
            by_subject[subject]["accuracy"] = correct_s / total_s if total_s > 0 else 0.0

        logger.info(f"MMLU Benchmark Complete: {correct}/{total} correct ({accuracy:.1%})")

        return MMLUBenchmarkResult(
            total_questions=total,
            correct=correct,
            accuracy=accuracy,
            avg_latency_ms=avg_latency,
            by_subject=by_subject,
            results=list(results),
        )


def run_mmlu(  # type: ignore[no-untyped-def]
    num_samples: int | None = None,
    temperature: float = 0.0,
    subjects: list[str] | None = None,
    data_path: str | None = None,
    **kwargs,
) -> dict[str, Any]:
    """Run MMLU benchmark.

    Args:
        num_samples: Number of samples to evaluate.
        temperature: Sampling temperature.
        subjects: Specific subjects to evaluate.
        data_path: Optional path to MMLU dataset.
        **kwargs: Additional arguments (ignored for compatibility).

    Returns:
        Dictionary with benchmark results.
    """
    runner = MMLURunner(data_path=data_path, subjects=subjects)

    try:
        result = asyncio.run(runner.run(num_samples=num_samples, temperature=temperature))
        return {
            "score": result.accuracy,
            "correct": result.correct,
            "total": result.total_questions,
            "accuracy": result.accuracy,
            "avg_latency_ms": result.avg_latency_ms,
            "by_subject": result.by_subject,
            "status": "completed",
        }
    except Exception as e:
        logger.error(f"MMLU benchmark failed: {e}")
        return {
            "score": 0.0,
            "status": "failed",
            "error": str(e),
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run_mmlu(num_samples=5)
    print(f"MMLU Result: {result}")
