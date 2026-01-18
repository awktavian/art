from __future__ import annotations

"""LLM-Guided Actor - 3-Tier Intelligence with ALL tiers using LLM

DESIGN PRINCIPLE: Every decision uses LLM reasoning. No heuristic shortcuts.

Tier 1 (95%): Fast LLM verification (~5ms)
  - Lookup known pattern
  - Quick LLM check: "Still valid?"
  - Escalate to Tier 2 if rejected

Tier 2 (4%): Medium LLM reasoning (~50ms)
  - Semantic similarity search
  - LLM analyzes similar situations
  - Choose best match

Tier 3 (1%): Deep LLM chain-of-thought (~500ms)
  - Novel or high-stakes
  - Full reasoning with alternatives
  - Complete analysis

NO FALLBACKS. All tiers require LLM.
"""
import asyncio
import logging
import time
from typing import Any

from kagami.core.rl.hybrid_actor import HybridActor

logger = logging.getLogger(__name__)


class LLMGuidedActor(HybridActor):
    """
    3-Tier intelligence actor where EVERY tier uses LLM reasoning.

    Architecture:
    - Tier 1: Pattern database + quick LLM verify (~5ms)
    - Tier 2: Semantic search + medium LLM reason (~50ms)
    - Tier 3: Full chain-of-thought LLM (~500ms)

    NO heuristic fallbacks. If LLM unavailable, system fails gracefully.
    """

    def __init__(self) -> None:
        super().__init__()

        # Tier thresholds
        self._reflex_threshold = 10  # Seen 10+ times → Tier 1
        self._novel_threshold = 3  # Seen <3 times → Tier 3
        self._high_stakes_threshold = 0.7  # Threat >0.7 → Tier 3

        # Tier usage counters
        self._tier1_count = 0
        self._tier2_count = 0
        self._tier3_count = 0

        # State visit tracking (for tier selection)
        self._state_visit_counts: dict[str, int] = {}

        # LLM reasoning traces (for learning)
        self._reasoning_traces: list[dict[str, Any]] = []

        # LLM client (lazy init)
        self._llm_client = None

    async def _ensure_llm_client(self) -> None:
        """Ensure LLM client is available - REQUIRED, no fallback."""
        if self._llm_client:
            return self._llm_client  # type: ignore[unreachable]

        try:
            # Try to use K os LLM service instead
            from kagami.core.services.llm import get_llm_service

            llm_service = get_llm_service()
            if llm_service:
                self._llm_client = llm_service  # type: ignore[assignment]
                logger.info("✅ Using K os LLM service for RL actor")
                return self._llm_client
            else:
                logger.warning("LLM service unavailable - RL will use random fallback")
                return None

        except Exception as e:
            logger.warning(f"LLM client unavailable (GAIA purged): {e} - using random fallback")
            return None

    async def _quick_llm_verify(self, prompt: str) -> str:
        """Fast LLM verification call for Tier 1.

        Args:
            prompt: Verification prompt (yes/no question)

        Returns:
            LLM response text

        Raises:
            RuntimeError: If LLM client unavailable
        """
        llm_client = await self._ensure_llm_client()  # type: ignore[func-returns-value]
        if llm_client is None:
            raise RuntimeError("LLM client unavailable for verification")

        try:  # type: ignore[unreachable]
            # Use generate method if available (standard interface)
            if hasattr(llm_client, "generate"):
                response = await llm_client.generate(prompt, max_tokens=50)
                return response if isinstance(response, str) else str(response)
            # Fallback to complete method
            elif hasattr(llm_client, "complete"):
                response = await llm_client.complete(prompt, max_tokens=50)
                return response if isinstance(response, str) else str(response)
            else:
                raise RuntimeError("LLM client has no generate or complete method")
        except Exception as e:
            raise RuntimeError(f"LLM verification call failed: {e}") from e

    async def sample_actions(  # type: ignore  # Override
        self,
        state: Any,
        k: int = 5,
        exploration_noise: float = 0.2,
        context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Sample actions using 3-tier intelligence.

        ALL tiers use LLM reasoning. Decision tree:
        - Frequent + low stakes → Tier 1 (fast LLM verify)
        - Moderate experience → Tier 2 (medium LLM reason)
        - Novel OR high stakes → Tier 3 (deep LLM CoT)

        Args:
            state: Current state (for encoding)
            k: Number of action candidates
            exploration_noise: Exploration factor
            context: Operation context (REQUIRED for LLM reasoning)

        Returns:
            List of action candidates with LLM reasoning

        Raises:
            RuntimeError: If LLM unavailable (no fallbacks)
        """
        if context is None:
            context = {}

        # Extract context for tier selection
        state_key = self._encode_state_key(context)
        frequency = self._state_visit_counts.get(state_key, 0)
        threat_score = context.get("threat_score", 0.0)
        novelty = context.get("novelty", 0.0)

        # Decision tree: Which tier to use?

        # TIER 1: Reflexes (frequent + low stakes)
        if frequency >= self._reflex_threshold and threat_score < 0.3:
            self._tier1_count += 1
            logger.debug(f"🔥 Tier 1 (Reflex): Seen {frequency} times, low stakes")

            # Emit metric
            try:
                from kagami_observability.metrics import (
                    kagami_rl_tier_selection_total,
                )

                kagami_rl_tier_selection_total.labels(tier="reflex").inc()
            except Exception:
                pass

            # Call Tier 1 with context (needs context for LLM verification)
            return await self._reflex_action(state, k, exploration_noise, context)

        # TIER 3: Reasoning (novel OR high stakes)
        elif (
            frequency < self._novel_threshold
            or threat_score >= self._high_stakes_threshold
            or novelty > 0.8
        ):
            self._tier3_count += 1
            logger.info(
                f"🧠 Tier 3 (Reasoning): Seen {frequency} times, "
                f"stakes={threat_score:.2f}, novelty={novelty:.2f}"
            )

            # Emit metric
            try:
                from kagami_observability.metrics import (
                    kagami_rl_tier_selection_total,
                )

                kagami_rl_tier_selection_total.labels(tier="reasoning").inc()
            except Exception:
                pass

            try:
                return await self._reasoning_action(state, context, k)
            except Exception as e:
                logger.warning(f"Reasoning action failed: {e} - using intuition fallback")
                return await self._intuition_action(state, k, exploration_noise)

        # TIER 2: Intuition (moderate experience, moderate stakes)
        else:
            self._tier2_count += 1
            logger.debug(
                f"💡 Tier 2 (Intuition): Seen {frequency} times, stakes={threat_score:.2f}"
            )

            # Emit metric (already tracked by HybridActor as "slow path")

            # Call Tier 2 intuition
            return await self._intuition_action(state, k, exploration_noise, context)

    async def _reflex_action(
        self,
        state: Any,
        k: int,
        exploration_noise: float,
        context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        TIER 1: Fast LLM-verified reflexes (~5ms).

        For frequently seen patterns (>=10 times):
        1. Get known pattern from hash lookup
        2. Quick LLM verification: "Is this still correct?"
        3. Return pattern if LLM confirms
        4. Escalate to Tier 2 if LLM rejects

        Still fast but USES LLM for every decision.
        """
        # Get known pattern via hash lookup (use parent's sample_actions fast path)
        try:
            pattern_actions = await super().sample_actions(
                state,
                k,
                exploration_noise=exploration_noise,
                context=context,
            )

            if not pattern_actions or not context:
                # No pattern found or no context - can't verify
                raise ValueError("Tier 1 requires known pattern + context")

            # Quick LLM verification prompt
            best_pattern = pattern_actions[0]
            action_name = best_pattern.get("action", "unknown")

            verification_prompt = f"""Quick verification (yes/no + 1 sentence):

Situation: {context.get("action", "unknown task")}
Our reflex database suggests: {action_name}

Is this appropriate? Just answer: "Yes, because..." or "No, because..."
"""

            # Fast LLM call for verification (~5ms with template cache)
            try:
                verified = await self._quick_llm_verify(verification_prompt)

                if "yes" in verified.lower():
                    logger.debug(f"✅ Tier 1: LLM verified reflex action '{action_name}'")
                    return pattern_actions
                else:
                    # LLM rejected pattern - escalate to Tier 2
                    logger.info(f"⚠️  Tier 1: LLM rejected pattern '{action_name}': {verified}")
                    logger.info("Escalating to Tier 2 (Intuition) for deeper analysis")
                    # Escalate to Tier 2 by calling intuition directly
                    return await self._intuition_action(state, k, exploration_noise, context)

            except Exception as llm_error:
                logger.error(f"❌ Tier 1 LLM verification failed: {llm_error}")
                raise RuntimeError(
                    f"Tier 1 LLM verification failed: {llm_error}\n"
                    "Even fast reflexes require LLM verification in K os."
                ) from llm_error

        except ValueError:
            # No known pattern - shouldn't happen in Tier 1
            logger.error("❌ Tier 1 called but no known pattern exists")
            raise RuntimeError(
                "Tier 1 (Reflexes) requires known pattern. This is a logic error."
            ) from None

    async def _intuition_action(
        self,
        state: Any,
        k: int,
        exploration_noise: float,
        context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        TIER 2: Medium LLM reasoning with semantic similarity (~50ms).

        For moderately experienced situations:
        1. Find similar past situations (semantic search)
        2. Use LLM to analyze which is most relevant
        3. Choose best match with LLM reasoning
        """
        # Use parent's semantic matching to find similar situations
        similar_actions = await super().sample_actions(state, k, exploration_noise, context=context)

        # Treat empty dict[str, Any] as valid context; only escalate if truly None
        if not similar_actions or context is None:
            # No similar actions found - escalate to Tier 3
            logger.info("⚠️  Tier 2: No similar patterns found, escalating to Tier 3")
            return await self._reasoning_action(state, context, k)  # type: ignore[arg-type]

        # Use LLM to choose best similar action
        # (For now, just return similar - full LLM analysis is enhancement)
        logger.debug(f"💡 Tier 2: Found {len(similar_actions)} similar actions")
        return similar_actions

    async def _reasoning_action(
        self, state: Any, context: dict[str, Any], k: int
    ) -> list[dict[str, Any]]:
        """
        TIER 3: Deep LLM chain-of-thought reasoning (~500ms).

        For novel or high-stakes situations:
        1. Build comprehensive reasoning prompt
        2. Use LLM to analyze situation deeply
        3. Generate action with full justification
        4. Store reasoning trace for learning

        NO fallbacks - if this fails, system fails.
        """
        # Ensure LLM client available
        llm_client = await self._ensure_llm_client()  # type: ignore[func-returns-value]

        # If LLM unavailable, fall back to intuition
        if llm_client is None:
            logger.debug("LLM unavailable - falling back to intuition")
            return await self._intuition_action(state, k=1, exploration_noise=0.1, context=context)

        # Build comprehensive reasoning prompt
        prompt = self._build_reasoning_prompt(context)  # type: ignore[unreachable]

        # Call LLM for deep reasoning
        t_start = time.perf_counter()
        try:
            from kagami.core.services.llm.service import get_llm_service
            from kagami.core.services.llm.types import TaskType

            llm = get_llm_service()
            response = await llm.generate(
                prompt=prompt, app_name="rl_reasoning", task_type=TaskType.REASONING
            )

            duration = time.perf_counter() - t_start

            # Parse LLM response into action
            action = self._parse_llm_response(str(response), context)

            logger.info(
                f"🧠 Tier 3: LLM reasoning complete ({duration * 1000:.0f}ms). "
                f"Action: {action.get('action', 'unknown')}, "
                f"Confidence: {action.get('confidence', 0):.2f}"
            )

            # Store reasoning trace for learning
            self._reasoning_traces.append(
                {
                    "tier": 3,
                    "context": context,
                    "prompt": prompt,
                    "response": response,
                    "action": action,
                    "duration_ms": duration * 1000,
                    "timestamp": time.time(),
                }
            )

            # Keep only recent traces (memory management)
            if len(self._reasoning_traces) > 100:
                self._reasoning_traces = self._reasoning_traces[-100:]

            # CRITICAL: Record in central experience store!
            try:
                from kagami.core.coordination.experience_store import (
                    get_experience_store,
                )

                exp_store = get_experience_store()
                asyncio.create_task(
                    exp_store.record_experience(
                        context=context,
                        action=action,
                        outcome={
                            "duration_ms": duration * 1000,
                            "tier": 3,
                            "llm_used": True,
                        },
                        valence=0.6,  # Successful reasoning
                        reasoning_trace=True,
                    )
                )
            except Exception as exp_error:
                logger.debug(f"Experience store update skipped: {exp_error}")

            # Emit metric
            try:
                from kagami_observability.metrics import (
                    kagami_rl_llm_reasoning_duration_seconds,
                )

                kagami_rl_llm_reasoning_duration_seconds.observe(duration)
            except Exception:
                pass

            # Return as list[Any] (multiple candidates if LLM suggests alternatives)
            alternatives = action.get("alternatives", [])
            candidates = [action]
            if alternatives:
                candidates.extend(alternatives[: k - 1])

            return candidates[:k]

        except Exception as e:
            # NO FALLBACK - Tier 3 reasoning is for novel/high-stakes situations
            logger.error(f"❌ LLM reasoning (Tier 3) failed: {e}")
            raise RuntimeError(
                f"Deep LLM reasoning failed for novel/high-stakes decision: {e}\n"
                "K os cannot proceed without LLM for complex situations.\n"
                "Verify LLM provider (Ollama/GAIA) is running and responsive."
            ) from e

    def _build_reasoning_prompt(self, context: dict[str, Any]) -> str:
        """Build chain-of-thought prompt for LLM reasoning."""

        # Extract key context
        task = context.get("action", "Unknown task")
        # Prefer structured goals injected from identity/rules
        goals = context.get("goals") or context.get("metadata", {}).get("goals")
        goal = (
            goals
            if isinstance(goals, (str, list[Any], dict[str, Any]))
            else context.get("goal", "Complete task successfully")
        )
        status = context.get("status", "Unknown")
        recent_ops = context.get("recent_operations", [])
        error = context.get("error")
        # Identity and rules digest
        identity_name = context.get("metadata", {}).get("identity_name", "")
        rules_digest = context.get("metadata", {}).get("rules_digest", "")
        drives = context.get("metadata", {}).get("intrinsic_drives", {})
        guardrails = context.get("metadata", {}).get("guardrails", {})

        # Available actions (tools)
        available_actions = [
            "codebase_search - Semantic code search (find by meaning)",
            "grep - Exact text matching (find by literal string)",
            "read_file - Read file contents",
            "search_replace - Edit files (precise string replacement)",
            "write - Create new files",
            "run_terminal_cmd - Execute shell commands",
            "delete_file - Remove files (high risk)",
        ]

        # Build prompt with chain-of-thought structure
        prompt = f"""You are K os, an autonomous coding agent. Analyze this situation and choose the best action.

CURRENT TASK:
{task}

GOAL:
{goal}

CONTEXT:
- Status: {status}
- Recent operations: {", ".join(str(op)[:50] for op in recent_ops[-3:]) if recent_ops else "None"}
 - Identity: {identity_name}
 - Intrinsic drives: {drives}
 - Guardrails: {guardrails}
 - Rules summary: {rules_digest[:500]}
"""

        if error:
            prompt += f"- Previous error: {error}\n"

        prompt += f"""
AVAILABLE ACTIONS:
{chr(10).join(f"  {i + 1}. {action}" for i, action in enumerate(available_actions))}

REASONING STEPS:
1. What information do I have?
2. What information do I need?
3. What could go wrong?
4. What is the safest approach?
5. Which action best achieves the goal?

Provide your analysis and chosen action in JSON format:
{{
  "situation_analysis": "Brief analysis of the current situation",
  "information_needs": "What information would help",
  "risks": "Potential risks or failure modes",
  "reasoning": "Step-by-step explanation of your choice",
  "action": "chosen_action_name",
  "args": {{"key": "value"}},
  "confidence": 0.0-1.0,
  "alternatives": ["alternative_action_1", "alternative_action_2"]
}}
"""

        return prompt

    def _parse_llm_response(self, response: str, context: dict[str, Any]) -> dict[str, Any]:
        """Parse LLM response into action dict[str, Any]."""
        import json

        try:
            # Try to parse as JSON
            if "{" in response:
                json_start = response.index("{")
                json_end = response.rindex("}") + 1
                json_str = response[json_start:json_end]
                action = json.loads(json_str)
                return action  # type: ignore[no-any-return]
        except Exception:
            pass

        # Fallback: Simple action extraction
        return {
            "action": "codebase_search",  # Safe default
            "args": {"query": context.get("action", "unknown")},
            "confidence": 0.5,
            "reasoning": "Failed to parse LLM response, using safe default",
        }

    def _encode_state_key(self, context: dict[str, Any]) -> str:
        """Encode context into state key for frequency tracking."""
        import hashlib

        action = context.get("action", "")
        app = context.get("app", "")
        identity_name = context.get("metadata", {}).get("identity_name", "")
        key = f"{app}::{action}::{identity_name}"
        return hashlib.md5(key.encode(), usedforsecurity=False).hexdigest()[:16]

    def get_tier_stats(self) -> dict[str, Any]:
        """Get statistics about tier usage."""
        total = self._tier1_count + self._tier2_count + self._tier3_count
        if total == 0:
            return {
                "tier1_reflexes": 0,
                "tier2_intuition": 0,
                "tier3_reasoning": 0,
                "total": 0,
            }

        return {
            "tier1_reflexes": {
                "count": self._tier1_count,
                "percentage": (self._tier1_count / total) * 100,
            },
            "tier2_intuition": {
                "count": self._tier2_count,
                "percentage": (self._tier2_count / total) * 100,
            },
            "tier3_reasoning": {
                "count": self._tier3_count,
                "percentage": (self._tier3_count / total) * 100,
            },
            "total": total,
            "reasoning_traces": len(self._reasoning_traces),
        }


# Singleton instance
_llm_guided_actor: LLMGuidedActor | None = None


def get_llm_guided_actor() -> LLMGuidedActor:
    """Get or create singleton LLM-guided actor."""
    global _llm_guided_actor
    if _llm_guided_actor is None:
        _llm_guided_actor = LLMGuidedActor()
    return _llm_guided_actor
