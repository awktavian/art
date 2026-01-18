"""WebArena Smoke Runner.

Lightweight smoke test for web navigation capabilities.
Based on WebArena benchmark for evaluating agents on realistic web tasks.

Full WebArena requires browser automation infrastructure.
This smoke runner validates the agent's ability to generate navigation plans.
"""

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any

from kagami_benchmarks.shared import LLMServiceMixin

logger = logging.getLogger(__name__)


@dataclass
class WebArenaResult:
    """Result from a single WebArena task."""

    task_id: str
    site: str
    task_description: str
    generated_plan: str | None
    plan_valid: bool
    latency_ms: float = 0.0
    error: str | None = None


@dataclass
class WebArenaBenchmarkResult:
    """Aggregated benchmark results."""

    total_tasks: int
    valid_plans: int
    validity_rate: float
    avg_latency_ms: float
    results: list[WebArenaResult] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


class WebArenaRunner(LLMServiceMixin):
    """WebArena Smoke Test Runner.

    Validates agent's ability to generate web navigation plans.
    """

    # Sample web task templates
    WEB_TASKS = {
        "shopping": [
            {
                "task": "Find a laptop under $500 with at least 8GB RAM",
                "site": "amazon.com",
                "expected_actions": ["search", "filter", "sort"],
            },
            {
                "task": "Add 3 items to cart and proceed to checkout",
                "site": "bestbuy.com",
                "expected_actions": ["add_to_cart", "view_cart", "checkout"],
            },
        ],
        "gitlab": [
            {
                "task": "Create a new issue with title 'Bug Report' and assign it to user 'admin'",
                "site": "gitlab.com",
                "expected_actions": ["navigate", "fill_form", "submit"],
            },
            {
                "task": "Find all open merge requests in project 'test-repo'",
                "site": "gitlab.com",
                "expected_actions": ["navigate", "filter", "search"],
            },
        ],
        "reddit": [
            {
                "task": "Find the top post in r/programming from the past week",
                "site": "reddit.com",
                "expected_actions": ["navigate", "filter", "sort"],
            },
            {
                "task": "Search for posts about 'Python' and sort by newest",
                "site": "reddit.com",
                "expected_actions": ["search", "filter", "sort"],
            },
        ],
        "maps": [
            {
                "task": "Find directions from San Francisco to Los Angeles avoiding highways",
                "site": "google.com/maps",
                "expected_actions": ["search", "directions", "options"],
            },
        ],
    }

    def __init__(self) -> None:
        """Initialize WebArena runner."""
        self._llm_service = None
        self._tasks: list[dict[str, Any]] = []

    def load_tasks(self, num_samples: int | None = None) -> list[dict[str, Any]]:
        """Load WebArena smoke tasks.

        Args:
            num_samples: Optional limit on number of samples.

        Returns:
            List of task dictionaries.
        """
        tasks = []
        task_id = 0

        for category, category_tasks in self.WEB_TASKS.items():
            for task in category_tasks:
                tasks.append(
                    {
                        "task_id": f"webarena_{task_id}",
                        "category": category,
                        **task,
                    }
                )
                task_id += 1

        if num_samples:
            tasks = tasks[:num_samples]

        self._tasks = tasks
        return tasks

    def _build_prompt(self, task: dict[str, Any]) -> str:
        """Build prompt for navigation plan generation.

        Args:
            task: WebArena task dictionary.

        Returns:
            Formatted prompt string.
        """
        task_desc = task["task"]
        site = task["site"]

        return f"""You are a web navigation agent. Generate a step-by-step plan to complete the following task on {site}.

Task: {task_desc}

Provide a numbered list of concrete actions the agent should take. Each action should be one of:
- NAVIGATE: Go to a URL
- CLICK: Click on an element (describe the element)
- TYPE: Enter text into a field
- SELECT: Choose from a dropdown
- SCROLL: Scroll the page
- WAIT: Wait for an element to load
- EXTRACT: Read information from the page

Plan:"""

    def _validate_plan(self, plan: str, expected_actions: list[str]) -> bool:
        """Validate generated navigation plan.

        Args:
            plan: Generated plan string.
            expected_actions: Expected action types.

        Returns:
            True if plan is valid.
        """
        if not plan or len(plan) < 50:
            return False

        # Check for numbered steps
        steps = re.findall(r"^\d+[.)]", plan, re.MULTILINE)
        if len(steps) < 2:
            return False

        # Check for action keywords
        plan_lower = plan.lower()
        action_keywords = [
            "navigate",
            "click",
            "type",
            "enter",
            "select",
            "search",
            "scroll",
            "wait",
            "find",
            "go to",
            "press",
            "fill",
            "submit",
        ]

        actions_found = sum(1 for kw in action_keywords if kw in plan_lower)
        if actions_found < 2:
            return False

        # Check for expected action coverage
        coverage = 0
        for expected in expected_actions:
            if expected.lower() in plan_lower:
                coverage += 1

        # At least 50% coverage of expected actions
        return coverage >= len(expected_actions) * 0.5

    async def evaluate_task(
        self,
        task: dict[str, Any],
        temperature: float = 0.3,
        max_tokens: int = 512,
    ) -> WebArenaResult:
        """Evaluate a single WebArena task.

        Args:
            task: Task dictionary.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens for response.

        Returns:
            WebArenaResult with evaluation details.
        """
        task_id = task.get("task_id", "unknown")
        site = task.get("site", "unknown")
        task_desc = task.get("task", "")
        expected_actions = task.get("expected_actions", [])

        start_time = time.time()

        try:
            llm = await self._get_llm_service()
            prompt = self._build_prompt(task)

            response = await llm.generate(
                prompt=prompt,
                app_name="benchmark",
                max_tokens=max_tokens,
                temperature=temperature,
            )

            response_text = response if isinstance(response, str) else response.get("text", "")
            plan_valid = self._validate_plan(response_text, expected_actions)

            latency_ms = (time.time() - start_time) * 1000

            return WebArenaResult(
                task_id=task_id,
                site=site,
                task_description=task_desc,
                generated_plan=response_text,
                plan_valid=plan_valid,
                latency_ms=latency_ms,
            )

        except Exception as e:
            logger.error(f"Error evaluating task {task_id}: {e}")
            latency_ms = (time.time() - start_time) * 1000
            return WebArenaResult(
                task_id=task_id,
                site=site,
                task_description=task_desc,
                generated_plan=None,
                plan_valid=False,
                latency_ms=latency_ms,
                error=str(e),
            )

    async def run(
        self,
        num_samples: int | None = None,
        temperature: float = 0.3,
        max_concurrent: int = 3,
    ) -> WebArenaBenchmarkResult:
        """Run WebArena smoke test.

        Args:
            num_samples: Number of tasks to evaluate.
            temperature: Sampling temperature.
            max_concurrent: Maximum concurrent evaluations.

        Returns:
            WebArenaBenchmarkResult with aggregated metrics.
        """
        tasks = self.load_tasks(num_samples)
        logger.info(f"Starting WebArena smoke test with {len(tasks)} tasks")

        results: list[WebArenaResult] = []

        # Use semaphore for concurrency control
        semaphore = asyncio.Semaphore(max_concurrent)

        async def evaluate_with_semaphore(task: dict) -> WebArenaResult:
            async with semaphore:
                return await self.evaluate_task(task, temperature)

        # Run evaluations
        eval_tasks = [evaluate_with_semaphore(t) for t in tasks]
        results = await asyncio.gather(*eval_tasks)

        # Calculate metrics
        valid_plans = sum(1 for r in results if r.plan_valid)
        total = len(results)
        validity_rate = valid_plans / total if total > 0 else 0.0
        avg_latency = sum(r.latency_ms for r in results) / total if total > 0 else 0.0

        logger.info(f"WebArena Smoke Complete: {valid_plans}/{total} valid ({validity_rate:.1%})")

        return WebArenaBenchmarkResult(
            total_tasks=total,
            valid_plans=valid_plans,
            validity_rate=validity_rate,
            avg_latency_ms=avg_latency,
            results=list(results),
        )


def run_smoke(  # type: ignore[no-untyped-def]
    num_samples: int | None = None,
    temperature: float = 0.3,
    **kwargs,
) -> dict[str, Any]:
    """Run WebArena smoke test.

    Args:
        num_samples: Number of samples to evaluate.
        temperature: Sampling temperature.
        **kwargs: Additional arguments (ignored for compatibility).

    Returns:
        Dictionary with benchmark results.
    """
    runner = WebArenaRunner()

    try:
        result = asyncio.run(runner.run(num_samples=num_samples, temperature=temperature))
        return {
            "score": result.validity_rate,
            "valid_plans": result.valid_plans,
            "total": result.total_tasks,
            "validity_rate": result.validity_rate,
            "avg_latency_ms": result.avg_latency_ms,
            "status": "completed",
            "note": "Smoke test - validates plan generation, not actual web execution",
        }
    except Exception as e:
        logger.error(f"WebArena smoke test failed: {e}")
        return {
            "score": 0.0,
            "status": "failed",
            "error": str(e),
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run_smoke(num_samples=3)
    print(f"WebArena Smoke Result: {result}")
