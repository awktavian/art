"""Hive Intelligence Benchmark.

Evaluates collective intelligence capabilities of multi-agent systems.
Measures emergence, knowledge sharing, and collaborative problem solving.

Metrics:
- Emergence Score: Solutions that emerge from agent collaboration
- Knowledge Sharing: Information propagation across agents
- Collective Accuracy: Accuracy on tasks requiring multiple agents
- Coordination Efficiency: Communication overhead vs. performance gain
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from kagami_benchmarks.shared import LLMServiceMixin

logger = logging.getLogger(__name__)


@dataclass
class HiveTaskResult:
    """Result from a single hive intelligence task."""

    task_id: str
    task_type: str
    individual_scores: list[float]
    collective_score: float
    emergence_gain: float  # collective - max(individual)
    coordination_cost: float  # Communication overhead
    latency_ms: float = 0.0
    error: str | None = None


@dataclass
class HiveIntelligenceBenchmarkResult:
    """Aggregated benchmark results."""

    total_tasks: int
    avg_emergence_score: float
    avg_collective_score: float
    knowledge_sharing_rate: float
    coordination_efficiency: float
    results: list[HiveTaskResult] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


class HiveIntelligenceBenchmark(LLMServiceMixin):
    """Hive Intelligence Benchmark Runner.

    Evaluates multi-agent collaboration and emergent intelligence.
    """

    # Task types that benefit from collective intelligence
    TASK_TYPES = {
        "consensus": {
            "description": "Tasks requiring agreement among agents",
            "weight": 1.0,
        },
        "decomposition": {
            "description": "Tasks that can be split among agents",
            "weight": 1.2,
        },
        "synthesis": {
            "description": "Tasks requiring integration of multiple perspectives",
            "weight": 1.5,
        },
        "debate": {
            "description": "Tasks benefiting from adversarial reasoning",
            "weight": 1.3,
        },
    }

    def __init__(
        self,
        num_agents: int = 3,
        enable_communication: bool = True,
    ) -> None:
        """Initialize Hive Intelligence benchmark.

        Args:
            num_agents: Number of agents in the hive.
            enable_communication: Whether agents can share information.
        """
        self.num_agents = num_agents
        self.enable_communication = enable_communication
        self._llm_service = None
        self._tasks: list[dict[str, Any]] = []

    def load_tasks(self, num_samples: int | None = None) -> list[dict[str, Any]]:
        """Load hive intelligence tasks.

        Args:
            num_samples: Optional limit on number of samples.

        Returns:
            List of task dictionaries.
        """
        tasks = self._get_sample_tasks()

        if num_samples:
            tasks = tasks[:num_samples]

        self._tasks = tasks
        return tasks

    def _get_sample_tasks(self) -> list[dict[str, Any]]:
        """Get sample hive intelligence tasks."""
        return [
            {
                "task_id": "hive_consensus_1",
                "task_type": "consensus",
                "question": "What are the three most important considerations when designing a distributed system?",
                "requires_agreement": True,
                "expected_aspects": ["scalability", "reliability", "consistency"],
            },
            {
                "task_id": "hive_decomposition_1",
                "task_type": "decomposition",
                "question": "Analyze the pros and cons of microservices vs monolithic architecture, considering: performance, maintainability, and scalability.",
                "subtasks": ["performance", "maintainability", "scalability"],
            },
            {
                "task_id": "hive_synthesis_1",
                "task_type": "synthesis",
                "question": "Given perspectives from a security expert, performance engineer, and UX designer, design an authentication system.",
                "perspectives": ["security", "performance", "ux"],
            },
            {
                "task_id": "hive_debate_1",
                "task_type": "debate",
                "question": "Should AI systems be allowed to make autonomous decisions in healthcare? Present arguments for and against, then synthesize a balanced view.",
                "positions": ["for", "against", "synthesis"],
            },
            {
                "task_id": "hive_consensus_2",
                "task_type": "consensus",
                "question": "What programming language is best suited for building real-time trading systems?",
                "requires_agreement": True,
                "expected_aspects": ["low latency", "memory safety", "ecosystem"],
            },
        ]

    async def _run_individual_agent(
        self,
        agent_id: int,
        task: dict[str, Any],
        context: str | None = None,
        temperature: float = 0.7,
    ) -> dict[str, Any]:
        """Run a single agent on the task.

        Args:
            agent_id: Agent identifier.
            task: Task dictionary.
            context: Optional context from other agents.
            temperature: Sampling temperature.

        Returns:
            Agent response with score.
        """
        llm = await self._get_llm_service()

        prompt = f"""You are Agent {agent_id + 1} in a multi-agent system.

Task: {task["question"]}

{"Previous agent insights: " + context if context else "You are the first to respond."}

Provide your analysis and response. Be specific and actionable."""

        try:
            response = await llm.generate(
                prompt=prompt,
                app_name="benchmark",
                max_tokens=512,
                temperature=temperature,
            )

            response_text = response if isinstance(response, str) else response.get("text", "")

            # Score based on coverage of expected aspects
            expected = task.get(
                "expected_aspects", task.get("subtasks", task.get("perspectives", []))
            )
            if expected:
                coverage = sum(1 for aspect in expected if aspect.lower() in response_text.lower())
                score = coverage / len(expected)
            else:
                # Default scoring based on response quality
                score = min(1.0, len(response_text) / 500) * 0.8

            return {
                "agent_id": agent_id,
                "response": response_text,
                "score": score,
            }

        except Exception as e:
            logger.warning(f"Agent {agent_id} failed: {e}")
            return {
                "agent_id": agent_id,
                "response": "",
                "score": 0.0,
                "error": str(e),
            }

    async def _run_collective(
        self,
        task: dict[str, Any],
        individual_responses: list[dict[str, Any]],
        temperature: float = 0.5,
    ) -> dict[str, Any]:
        """Run collective synthesis of individual responses.

        Args:
            task: Task dictionary.
            individual_responses: List of individual agent responses.
            temperature: Sampling temperature.

        Returns:
            Collective response with score.
        """
        llm = await self._get_llm_service()

        # Build summary of individual responses
        responses_summary = "\n\n".join(
            [f"Agent {r['agent_id'] + 1}: {r['response'][:300]}..." for r in individual_responses]
        )

        prompt = f"""Synthesize the following agent responses into a coherent, improved answer.

Task: {task["question"]}

Agent Responses:
{responses_summary}

Provide a synthesized answer that:
1. Incorporates the best insights from each agent
2. Resolves any conflicts
3. Adds emergent insights not present in individual responses

Synthesized Answer:"""

        try:
            response = await llm.generate(
                prompt=prompt,
                app_name="benchmark",
                max_tokens=768,
                temperature=temperature,
            )

            response_text = response if isinstance(response, str) else response.get("text", "")

            # Score based on coverage and synthesis quality
            expected = task.get(
                "expected_aspects", task.get("subtasks", task.get("perspectives", []))
            )
            if expected:
                coverage = sum(1 for aspect in expected if aspect.lower() in response_text.lower())
                base_score = coverage / len(expected)
            else:
                base_score = min(1.0, len(response_text) / 600) * 0.8

            # Bonus for synthesis indicators
            synthesis_keywords = [
                "however",
                "combining",
                "synthesis",
                "together",
                "integrating",
                "both",
                "while",
            ]
            synthesis_bonus = sum(0.05 for kw in synthesis_keywords if kw in response_text.lower())

            score = min(1.0, base_score + synthesis_bonus)

            return {
                "response": response_text,
                "score": score,
            }

        except Exception as e:
            logger.warning(f"Collective synthesis failed: {e}")
            return {
                "response": "",
                "score": 0.0,
                "error": str(e),
            }

    async def evaluate_task(
        self,
        task: dict[str, Any],
        temperature: float = 0.7,
    ) -> HiveTaskResult:
        """Evaluate a single hive intelligence task.

        Args:
            task: Task dictionary.
            temperature: Sampling temperature.

        Returns:
            HiveTaskResult with evaluation details.
        """
        task_id = task.get("task_id", "unknown")
        task_type = task.get("task_type", "unknown")

        start_time = time.time()

        try:
            # Phase 1: Individual agent responses
            individual_responses = []
            context = None

            for agent_id in range(self.num_agents):
                response = await self._run_individual_agent(
                    agent_id,
                    task,
                    context if self.enable_communication else None,
                    temperature,
                )
                individual_responses.append(response)

                # Update context for next agent
                if self.enable_communication:
                    context = response["response"][:200]

            individual_scores = [r["score"] for r in individual_responses]

            # Phase 2: Collective synthesis
            collective = await self._run_collective(task, individual_responses, temperature - 0.2)
            collective_score = collective["score"]

            # Calculate metrics
            max_individual = max(individual_scores)
            emergence_gain = collective_score - max_individual

            # Coordination cost (communication overhead)
            if self.enable_communication:
                coordination_cost = 0.1 * (self.num_agents - 1)  # Cost per communication
            else:
                coordination_cost = 0.0

            latency_ms = (time.time() - start_time) * 1000

            return HiveTaskResult(
                task_id=task_id,
                task_type=task_type,
                individual_scores=individual_scores,
                collective_score=collective_score,
                emergence_gain=emergence_gain,
                coordination_cost=coordination_cost,
                latency_ms=latency_ms,
            )

        except Exception as e:
            logger.error(f"Error evaluating task {task_id}: {e}")
            latency_ms = (time.time() - start_time) * 1000
            return HiveTaskResult(
                task_id=task_id,
                task_type=task_type,
                individual_scores=[0.0] * self.num_agents,
                collective_score=0.0,
                emergence_gain=0.0,
                coordination_cost=0.0,
                latency_ms=latency_ms,
                error=str(e),
            )

    async def run(
        self,
        num_samples: int | None = None,
        temperature: float = 0.7,
    ) -> HiveIntelligenceBenchmarkResult:
        """Run Hive Intelligence benchmark.

        Args:
            num_samples: Number of tasks to evaluate.
            temperature: Sampling temperature.

        Returns:
            HiveIntelligenceBenchmarkResult with aggregated metrics.
        """
        tasks = self.load_tasks(num_samples)
        logger.info(
            f"Starting Hive Intelligence benchmark with {len(tasks)} tasks, {self.num_agents} agents"
        )

        results: list[HiveTaskResult] = []

        # Run tasks sequentially (multi-agent coordination is inherently sequential)
        for task in tasks:
            result = await self.evaluate_task(task, temperature)
            results.append(result)

        # Calculate aggregated metrics
        total = len(results)
        avg_emergence = sum(r.emergence_gain for r in results) / total if total > 0 else 0.0
        avg_collective = sum(r.collective_score for r in results) / total if total > 0 else 0.0

        # Knowledge sharing rate: how often collective > best individual
        sharing_successes = sum(1 for r in results if r.emergence_gain > 0)
        knowledge_sharing_rate = sharing_successes / total if total > 0 else 0.0

        # Coordination efficiency: emergence gain / coordination cost
        total_gain = sum(r.emergence_gain for r in results)
        total_cost = sum(r.coordination_cost for r in results)
        coordination_efficiency = total_gain / total_cost if total_cost > 0 else 1.0

        logger.info(
            f"Hive Intelligence Complete: "
            f"emergence={avg_emergence:.3f}, "
            f"collective={avg_collective:.3f}, "
            f"sharing={knowledge_sharing_rate:.1%}"
        )

        return HiveIntelligenceBenchmarkResult(
            total_tasks=total,
            avg_emergence_score=avg_emergence,
            avg_collective_score=avg_collective,
            knowledge_sharing_rate=knowledge_sharing_rate,
            coordination_efficiency=coordination_efficiency,
            results=results,
        )


def run_hive_benchmark(  # type: ignore[no-untyped-def]
    num_samples: int | None = None,
    num_agents: int = 3,
    temperature: float = 0.7,
    **kwargs,
) -> dict[str, Any]:
    """Run Hive Intelligence benchmark.

    Args:
        num_samples: Number of samples to evaluate.
        num_agents: Number of agents in the hive.
        temperature: Sampling temperature.
        **kwargs: Additional arguments (ignored for compatibility).

    Returns:
        Dictionary with benchmark results.
    """
    benchmark = HiveIntelligenceBenchmark(num_agents=num_agents)

    try:
        result = asyncio.run(benchmark.run(num_samples=num_samples, temperature=temperature))
        return {
            "score": result.avg_collective_score,
            "emergence_score": result.avg_emergence_score,
            "collective_score": result.avg_collective_score,
            "knowledge_sharing_rate": result.knowledge_sharing_rate,
            "coordination_efficiency": result.coordination_efficiency,
            "total_tasks": result.total_tasks,
            "status": "completed",
        }
    except Exception as e:
        logger.error(f"Hive Intelligence benchmark failed: {e}")
        return {
            "score": 0.0,
            "status": "failed",
            "error": str(e),
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run_hive_benchmark(num_samples=2, num_agents=2)
    print(f"Hive Intelligence Result: {result}")
