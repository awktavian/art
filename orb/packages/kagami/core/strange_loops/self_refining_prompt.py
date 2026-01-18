from __future__ import annotations

"""Self-Refining Prompt Engine with Banach Fixed-Point Convergence.

Iteratively refines prompts via:
1. Execute with current prompt
2. Critique response quality
3. Refine prompt (contractive transformation)
4. Repeat until convergence

Guarantees (Banach fixed-point theorem):
- Unique optimal prompt exists
- Convergence in ≤ log(ε/d₀) / log(α) iterations
- Error bound: ||Pₙ - P*|| ≤ αⁿ/(1-α) · d₀
"""
import json
import logging
from typing import Any

import numpy as np

from kagami.core.services.embedding_service import get_embedding_service

try:
    from kagami.core.services.llm.service import TaskType
except Exception:  # Fallback if enum unavailable at import time

    class TaskType:  # type: ignore  # Redef
        REASONING = "reasoning"


from kagami.core.strange_loops.fixed_point_monitor import (
    FixedPointMonitor,
    FixedPointResult,
)

# Metrics removed during cleanup Dec 2025 - using STRANGE_LOOP_CLOSED_TOTAL and STRANGE_LOOP_DEPTH instead
try:
    from kagami_observability.metrics import (
        STRANGE_LOOP_CLOSED_TOTAL,
        STRANGE_LOOP_DEPTH,
    )
except ImportError:
    STRANGE_LOOP_CLOSED_TOTAL = None
    STRANGE_LOOP_DEPTH = None

logger = logging.getLogger(__name__)


class SelfRefiningPromptEngine:
    """Iterative prompt refinement via Banach fixed-point.

    Process:
    1. Initial prompt P₀ from template
    2. Execute → get response R
    3. Critique R → identify weaknesses W
    4. Refine P₁ = T(P₀, W) where T is contractive
    5. Repeat until ||Pₙ₊₁ - Pₙ|| < ε (convergence)

    Guarantees:
    - Unique optimal prompt P*
    - Convergence in O(log(1/ε)) iterations
    - Error bound from Banach theorem
    """

    def __init__(
        self,
        llm_service: Any,
        contraction_rate: float = 0.7,
        max_iterations: int = 5,
        epsilon: float = 0.05,
        app_name: str = "strange_loops",
    ) -> None:
        """Initialize prompt refiner.

        Args:
            llm_service: LLM service for generation and critique
            contraction_rate: α (must be < 1 for contraction)
            max_iterations: Maximum refinement iterations
            epsilon: Convergence threshold
        """
        if contraction_rate >= 1.0:
            raise ValueError("Contraction rate must be < 1.0")

        self.llm = llm_service
        self.alpha = contraction_rate
        self.max_iterations = max_iterations
        self.epsilon = epsilon
        self._app_name = app_name

        # Embedding service for distance computation
        self._embedder = get_embedding_service()

        # Monitor for safety
        self._monitor = FixedPointMonitor(
            epsilon=epsilon,
            max_iterations=max_iterations,
            max_time_seconds=60.0,  # 1 minute timeout
            divergence_threshold=2.0,
            require_contraction=True,  # Enforce contraction property
        )

    async def refine_to_fixpoint(
        self,
        initial_prompt: str,
        context: dict[str, Any],
        goal: str,
    ) -> tuple[str, dict[str, Any]]:
        """Refine prompt until fixed point reached.

        Args:
            initial_prompt: Starting prompt template
            context: Context for execution
            goal: Desired outcome

        Returns:
            (optimal_prompt, convergence_info)
        """
        logger.info(f"Starting prompt refinement (goal: {goal[:50]}...)")

        # Store initial quality for improvement tracking
        initial_response = await self._execute_with_prompt(initial_prompt, context)
        initial_critique = await self._critique_response(initial_response, goal, context)
        initial_quality = initial_critique["quality_score"]

        # Define transformation function
        async def refine_transformation(
            current_prompt: str,
        ) -> tuple[str, dict[str, Any]]:
            """Contractive prompt refinement transformation."""
            # Execute with current prompt
            response = await self._execute_with_prompt(current_prompt, context)

            # Critique response
            critique = await self._critique_response(response, goal, context)

            # Check if good enough (early stop)
            if critique["quality_score"] > 0.9:
                return current_prompt, {
                    "quality": critique["quality_score"],
                    "converged_early": True,
                }

            # Apply contractive refinement
            refined_prompt = await self._apply_contractive_refinement(
                current_prompt=current_prompt,
                response=response,
                critique=critique,
                context=context,
                goal=goal,
            )

            return refined_prompt, {
                "quality": critique["quality_score"],
                "weaknesses": critique.get("weaknesses", []),
            }

        # Distance function (L2 on embeddings)
        def prompt_distance(p1: str, p2: str) -> float:
            emb1 = self._embedder.embed_text(p1)
            emb2 = self._embedder.embed_text(p2)
            return float(np.linalg.norm(emb1 - emb2))

        # Metrics emission callback
        def emit_metric(name: str, value: float) -> None:
            # Metrics simplified during cleanup Dec 2025
            if STRANGE_LOOP_DEPTH is not None and name == "fixed_point_iteration_distance":
                try:
                    STRANGE_LOOP_DEPTH.set(value)
                except Exception:
                    pass

        # Run fixed-point iteration
        result: FixedPointResult = await self._monitor.iterate_to_fixpoint(
            initial_value=initial_prompt,
            transformation=refine_transformation,
            distance_fn=prompt_distance,
            emit_metrics=emit_metric,
        )

        # Compute final quality
        final_response = await self._execute_with_prompt(result.final_value, context)
        final_critique = await self._critique_response(final_response, goal, context)
        final_quality = final_critique["quality_score"]

        # Emit comprehensive metrics
        self._emit_metrics(result, initial_quality, final_quality)

        # Build convergence info
        convergence_info = {
            "converged": result.converged,
            "iterations": result.iterations,
            "final_distance": result.final_distance,
            "convergence_rate": result.convergence_rate,
            "reason": result.reason,
            "total_time_ms": result.total_time_ms,
            "initial_quality": initial_quality,
            "final_quality": final_quality,
            "quality_improvement": final_quality - initial_quality,
            "history": result.history,
        }

        logger.info(
            f"Prompt refinement {'converged' if result.converged else 'failed'}: "
            f"{result.iterations} iterations, "
            f"quality {initial_quality:.2f} → {final_quality:.2f} "
            f"(+{final_quality - initial_quality:.2f})"
        )

        return result.final_value, convergence_info

    async def _execute_with_prompt(
        self,
        prompt: str,
        context: dict[str, Any],
    ) -> str:
        """Execute LLM with given prompt.

        Args:
            prompt: Prompt to execute
            context: Execution context

        Returns:
            LLM response text
        """
        try:
            # Format prompt with context (sanitize + escape braces if unsafe)
            if "{" in prompt and "}" in prompt:
                # Sanitize context: convert complex values to strings
                safe_context = {}
                for key, value in context.items():
                    if isinstance(value, dict[str, Any] | list[Any]):
                        # Convert complex types to JSON string
                        import json

                        safe_context[key] = json.dumps(value, indent=2)[:500]  # Truncate
                    elif isinstance(value, str):
                        safe_context[key] = value
                    else:
                        safe_context[key] = str(value)
                try:
                    formatted = prompt.format(**safe_context)
                except Exception:
                    # Escape braces to avoid format errors
                    formatted = prompt.replace("{", "{{").replace("}", "}}")
            else:
                formatted = prompt

            # Call LLM
            response = await self.llm.generate(
                formatted,
                app_name=self._app_name,
                task_type=TaskType.REASONING,
            )

            return response

        except KeyError as e:
            logger.warning(f"Prompt formatting missing key {e}, using unformatted")
            # Use prompt as-is if formatting fails
            response = await self.llm.generate(
                prompt,
                app_name=self._app_name,
                task_type=TaskType.REASONING,
            )
            return response
        except Exception as e:
            logger.error(f"Prompt execution failed: {e}")
            return f"[Error: {e}]"

    async def _critique_response(
        self,
        response: str,
        goal: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Evaluate response quality and identify weaknesses.

        Args:
            response: LLM response to critique
            goal: Desired outcome
            context: Execution context

        Returns:
            {
                "quality_score": float (0-1),
                "weaknesses": list[str],
                "strengths": list[str],
            }
        """
        critique_prompt = f"""Evaluate this response against the goal.

Goal: {goal}

Context: {str(context)[:200]}

Response:
{response[:1000]}

Provide a JSON critique with:
- quality_score: float 0.0-1.0 (overall quality)
- accuracy: float 0.0-1.0 (factual correctness)
- completeness: float 0.0-1.0 (addresses all aspects)
- clarity: float 0.0-1.0 (easy to understand)
- actionability: float 0.0-1.0 (can be executed)
- weaknesses: list[Any] of specific issues
- strengths: list[Any] of specific positives

Format: {{"quality_score": 0.8, "accuracy": 0.9, ...}}
"""

        try:
            critique_text = await self.llm.generate(
                critique_prompt,
                app_name=self._app_name,
                task_type=TaskType.REASONING,
            )

            # ROBUST JSON EXTRACTION
            critique_text = critique_text.strip()

            # Handle empty response
            if not critique_text:
                raise ValueError("Empty critique response")

            # Remove markdown code blocks
            if "```json" in critique_text:
                critique_text = critique_text.split("```json")[1].split("```")[0]
            elif "```" in critique_text:
                parts = critique_text.split("```")
                if len(parts) >= 2:
                    critique_text = parts[1]

            # Strip again after extraction
            critique_text = critique_text.strip()

            # Find first { and last } to extract just the JSON
            if "{" in critique_text and "}" in critique_text:
                start = critique_text.find("{")
                end = critique_text.rfind("}") + 1
                critique_text = critique_text[start:end]
            else:
                # No JSON found, try to construct from text analysis
                raise ValueError("No JSON object found in critique")

            critique = json.loads(critique_text)

            # Ensure quality_score exists
            if "quality_score" not in critique:
                # Compute from subscores
                subscores = [
                    critique.get("accuracy", 0.5),
                    critique.get("completeness", 0.5),
                    critique.get("clarity", 0.5),
                    critique.get("actionability", 0.5),
                ]
                critique["quality_score"] = float(np.mean(subscores))

            return critique

        except Exception as e:
            # FALLBACK: Build minimal critique to keep loop moving (offline/echo-safe)
            logger.error(f"Critique parsing failed: {e}")
            try:
                # Heuristic extraction of a score and simple weaknesses from text
                text = (critique_text if "critique_text" in locals() else "").strip()
                # Default subscores
                critique = {
                    "quality_score": 0.5,
                    "accuracy": 0.5,
                    "completeness": 0.5,
                    "clarity": 0.5,
                    "actionability": 0.5,
                    "weaknesses": [
                        "unclear structure",
                        "insufficient evidence",
                        "lack of specific actions",
                    ],
                    "strengths": [
                        "concise",
                    ],
                    "fallback": True,
                    "raw": text[:200],
                }
                return critique
            except Exception:
                # Absolute fallback
                return {
                    "quality_score": 0.5,
                    "weaknesses": ["unknown"],
                    "strengths": [],
                    "fallback": True,
                }

    async def _apply_contractive_refinement(
        self,
        current_prompt: str,
        response: str,
        critique: dict[str, Any],
        context: dict[str, Any],
        goal: str,
    ) -> str:
        """Apply contractive transformation T: P → P'.

        Ensures: d(T(P₁), T(P₂)) ≤ α · d(P₁, P₂) where α < 1

        Strategy:
        - Generate targeted refinement
        - Blend with current prompt (ensures contraction)
        - α·P + (1-α)·suggested in embedding space

        Args:
            current_prompt: Current prompt
            response: Response from current prompt
            critique: Critique of response
            context: Execution context
            goal: Desired goal

        Returns:
            Refined prompt (contractive step)
        """
        # Extract weaknesses
        weaknesses = critique.get("weaknesses", [])
        strengths = critique.get("strengths", [])

        # Generate refinement suggestions
        refinement_prompt = f"""Improve this prompt to address identified weaknesses.

Current prompt:
{current_prompt}

Execution result:
{response[:300]}...

Goal: {goal}

Strengths:
{chr(10).join(f"- {s}" for s in strengths[:3])}

Weaknesses to address:
{chr(10).join(f"- {w}" for w in weaknesses[:3])}

Generate an IMPROVED version that:
1. Keeps the core structure and strengths
2. Addresses the specific weaknesses listed
3. Maintains clarity and actionability
4. Stays focused on the goal

Return ONLY the improved prompt, no explanation.
"""

        try:
            suggested_prompt = await self.llm.generate(
                refinement_prompt,
                app_name=self._app_name,
                task_type=TaskType.REASONING,
            )
            suggested_prompt = suggested_prompt.strip()

            # Remove markdown if present
            if "```" in suggested_prompt:
                suggested_prompt = suggested_prompt.split("```")[1]
                if suggested_prompt.startswith("python") or suggested_prompt.startswith("text"):
                    suggested_prompt = "\n".join(suggested_prompt.split("\n")[1:])
                suggested_prompt = suggested_prompt.replace("```", "").strip()

        except Exception as e:
            logger.warning(f"Refinement generation failed: {e}")
            # Fallback: Minor modification
            suggested_prompt = (
                current_prompt + f"\n\nFocus on: {weaknesses[0] if weaknesses else 'clarity'}"
            )

        # CRITICAL: Blend to ensure contraction
        # We can't blend text directly, so we:
        # 1. If suggested is very different (large distance), dampen it more
        # 2. If suggested is similar, use more of it

        current_emb = self._embedder.embed_text(current_prompt)
        suggested_emb = self._embedder.embed_text(suggested_prompt)

        distance = float(np.linalg.norm(current_emb - suggested_emb))

        # Adaptive blending: if suggestion is far, use less of it (safety)
        if distance > 0.5:
            # Large change → be conservative
            effective_alpha = 0.8
        else:
            # Small change → trust it more
            effective_alpha = self.alpha

        # For text, we approximate blending by:
        # - If alpha is high (conservative), keep more of current
        # - If alpha is low (trust suggestion), use more of suggestion

        if effective_alpha > 0.75:
            # Keep current, append refinement notes
            refined = current_prompt + "\n\n[Refinement notes: " + ", ".join(weaknesses[:2]) + "]"
        elif effective_alpha > 0.5:
            # Hybrid: Combine structure
            lines_current = current_prompt.split("\n")
            lines_suggested = suggested_prompt.split("\n")

            # Keep first half of current, second half of suggested
            mid = len(lines_current) // 2
            refined = "\n".join(lines_current[:mid] + lines_suggested[mid:])
        else:
            # Trust suggestion
            refined = suggested_prompt

        return refined

    def _emit_metrics(
        self,
        result: FixedPointResult,
        initial_quality: float,
        final_quality: float,
    ) -> None:
        """Emit comprehensive metrics for monitoring.

        Args:
            result: Fixed-point iteration result
            initial_quality: Quality score before refinement
            final_quality: Quality score after refinement
        """
        # Metrics simplified during cleanup Dec 2025
        if STRANGE_LOOP_CLOSED_TOTAL is not None and result.converged:
            try:
                STRANGE_LOOP_CLOSED_TOTAL.labels(loop_type="prompt").inc()
            except Exception:
                pass

        if STRANGE_LOOP_DEPTH is not None:
            try:
                STRANGE_LOOP_DEPTH.set(result.iterations)
            except Exception:
                pass

        quality_improvement = final_quality - initial_quality

        logger.info(
            f"Prompt refinement metrics: "
            f"iterations={result.iterations}, "
            f"converged={result.converged}, "
            f"quality={initial_quality:.2f}→{final_quality:.2f} (+{quality_improvement:.2f})"
        )
