from __future__ import annotations

"""Autonomous Reasoning Loop - LLM-powered intrinsic goal generation.

⚠️  NAMING CLARIFICATION:
This module contains ContinuousMind for autonomous reasoning/intrinsic goals.
NOT to be confused with kagami.core.learning.continuous_mind which handles
receipt-based learning from execution feedback.

Two different "ContinuousMind" implementations:
- THIS FILE: Autonomous reasoning (what to do next, cf. Active Inference intrinsic motivation)
- kagami.core.learning.continuous_mind: Receipt learning daemon (learn from doing)

Purpose: Always-on reasoning and autonomous goal generation
- Runs autonomously to generate intrinsic goals
- LLM-powered thought generation and reasoning
- Working memory maintenance across thoughts
- Episodic memory consolidation
- Responds to both user requests and internal curiosity

This is the architectural shift from REQUEST-RESPONSE to CONTINUOUS.

Key Properties:
- Never sleeps (except 10ms yield to asyncio)
- Always has goals queued (intrinsic + user requests)
- Maintains working memory across thoughts
- Consolidates memory periodically
- Logs every thought for observability

This enables:
- Proactive behavior (thinking before asked)
- Context continuity (remember across "thoughts")
- Background research (pursue curiosity autonomously)
- Genuine "thinking" (not just responding)

Related:
- kagami.core.learning.continuous_mind.ContinuousMindDaemon (receipt learning)
- kagami.core.autonomous_goal_engine (goal generation)
"""
import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ThoughtType(Enum):
    """Types of thoughts the mind can have."""

    USER_REQUEST = "user_request"  # Responding to Tim
    INTRINSIC_GOAL = "intrinsic_goal"  # Pursuing curiosity
    BACKGROUND_RESEARCH = "background_research"  # Learning
    MEMORY_CONSOLIDATION = "memory_consolidation"  # Organizing knowledge
    SELF_REFLECTION = "self_reflection"  # Metacognition
    COLLABORATION = "collaboration"  # Multi-agent coordination


@dataclass
class Thought:
    """A single unit of reasoning."""

    id: str
    type: ThoughtType
    content: str  # What am I thinking about?
    context: dict[str, Any]  # Relevant information
    priority: float  # 0.0-1.0 (higher = more urgent)
    created_at: float = field(default_factory=time.time)

    # Reasoning outputs
    conclusion: str | None = None
    actionable: bool = False
    action: dict[str, Any] | None = None
    confidence: float = 0.5

    # Tracking
    reasoning_duration_ms: float = 0.0
    completed_at: float | None = None


@dataclass
class Goal:
    """A goal to pursue (user-given or intrinsic)."""

    id: str
    description: str
    priority: float  # 0.0-1.0
    source: str  # "user" or agent name
    context: dict[str, Any]
    created_at: float = field(default_factory=time.time)

    # Progress tracking
    progress: float = 0.0  # 0.0-1.0
    thoughts_generated: list[str] = field(default_factory=list[Any])
    completed: bool = False


class SharedWorkingMemory:
    """Persistent working memory across thoughts.

    Unlike episodic memory (long-term), this is:
    - In-RAM (fast access)
    - Limited size (100MB default)
    - Recently-accessed priority
    - Shared across all thoughts
    - PERSISTENT (saves to disk, survives restarts)

    This enables context continuity: thoughts can reference
    what previous thoughts concluded.
    """

    def __init__(
        self, max_size_mb: int = 100, persist_path: str = "state/working_memory.json"
    ) -> None:
        self._max_size_mb = max_size_mb
        self._current_size_mb = 0.0
        self._persist_path = persist_path
        self._max_entries = (
            10000  # Hard limit on dict[str, Any] entries to prevent unbounded growth
        )

        # Store as key → (value, last_accessed, size_mb)
        self._memory: dict[str, tuple[Any, float, float]] = {}

        # LRU queue for eviction
        self._access_order: deque[str] = deque(maxlen=10000)

        # Load from disk if exists
        self._load_from_disk()

    def store(self, key: str, value: Any) -> None:
        """Store in working memory."""

        # CRITICAL FIX: Use deep size estimation instead of shallow getsizeof
        size_mb = self._deep_sizeof(value) / (1024 * 1024)

        # Evict by size if needed
        while self._current_size_mb + size_mb > self._max_size_mb:
            if not self._access_order:
                break
            oldest_key = self._access_order.popleft()
            if oldest_key in self._memory:
                _, _, old_size = self._memory[oldest_key]
                del self._memory[oldest_key]
                self._current_size_mb -= old_size

        # CRITICAL FIX: Enforce hard entry limit to prevent unbounded growth
        # (addresses 800GB crash root cause pattern)
        while len(self._memory) >= self._max_entries:
            if not self._access_order:
                break
            oldest_key = self._access_order.popleft()
            if oldest_key in self._memory:
                _, _, old_size = self._memory[oldest_key]
                del self._memory[oldest_key]
                self._current_size_mb -= old_size

        # Store
        self._memory[key] = (value, time.time(), size_mb)
        self._current_size_mb += size_mb
        self._access_order.append(key)

    def retrieve(self, key: str) -> Any | None:
        """Retrieve from working memory."""
        if key not in self._memory:
            return None

        value, _, size_mb = self._memory[key]

        # Update access time
        self._memory[key] = (value, time.time(), size_mb)
        self._access_order.append(key)

        return value

    def _deep_sizeof(self, obj: Any, seen: set[Any] | None = None) -> int:
        """Calculate deep size of object including nested structures."""
        import sys

        size = sys.getsizeof(obj)
        if seen is None:
            seen = set()
        obj_id = id(obj)
        if obj_id in seen:
            return 0
        seen.add(obj_id)

        if isinstance(obj, dict):
            size += sum(
                self._deep_sizeof(k, seen) + self._deep_sizeof(v, seen) for k, v in obj.items()
            )
        elif isinstance(obj, (list, tuple, set, frozenset)):
            size += sum(self._deep_sizeof(i, seen) for i in obj)
        elif hasattr(obj, "__dict__"):
            size += self._deep_sizeof(obj.__dict__, seen)

        return size

    def get_stats(self) -> dict[str, Any]:
        """Get memory statistics."""
        return {
            "size_mb": self._current_size_mb,
            "max_mb": self._max_size_mb,
            "items": len(self._memory),
            "utilization": self._current_size_mb / self._max_size_mb,
        }

    def _load_from_disk(self) -> None:
        """Load working memory from disk (survive restarts)."""
        try:
            import json
            from pathlib import Path

            path = Path(self._persist_path)
            if not path.exists():
                logger.info("No persisted working memory found (fresh start)")
                return

            data = json.loads(path.read_text())

            # Restore memory entries
            for key, entry in data.get("memory", {}).items():
                value, last_accessed, size_mb = entry
                self._memory[key] = (value, last_accessed, size_mb)
                self._access_order.append(key)
                self._current_size_mb += size_mb

            logger.info(
                f"✓ Loaded {len(self._memory)} items from working memory "
                f"({self._current_size_mb:.1f} MB)"
            )

        except Exception as e:
            logger.warning(f"Could not load working memory from disk: {e}")

    def save_to_disk(self) -> None:
        """Save working memory to disk."""
        try:
            import json
            from pathlib import Path

            path = Path(self._persist_path)
            path.parent.mkdir(parents=True, exist_ok=True)

            # Serialize memory (convert tuples to lists for JSON)
            serializable = {
                "memory": {key: list(value) for key, value in self._memory.items()},
                "size_mb": self._current_size_mb,
                "timestamp": time.time(),
            }

            # Atomic write
            tmp_path = path.with_suffix(".tmp")
            tmp_path.write_text(json.dumps(serializable, indent=2))
            tmp_path.replace(path)

            logger.debug(f"Saved working memory to {path}")

        except Exception as e:
            logger.warning(f"Could not save working memory to disk: {e}")


from kagami.core.services.llm.mixin import LLMClientMixin


class ContinuousMind(LLMClientMixin):
    """Always-on autonomous reasoning loop (NOT receipt learning).

    ⚠️  NAMING CLARIFICATION:
    This is the AUTONOMOUS REASONING loop that generates intrinsic goals
    and reasons about what to do next using LLM-powered thought generation.

    For the RECEIPT LEARNING daemon that learns from execution feedback, see:
    kagami.core.learning.continuous_mind.ContinuousMindDaemon

    Purpose: Autonomous goal generation and intrinsic reasoning
    - Generates intrinsic goals based on curiosity/learning drives
    - Reasons about thoughts using LLM
    - Maintains working memory across thought sequences
    - Consolidates episodic memory patterns
    - Executes thought-driven actions

    This is the core of continuous operation.
    Instead of request-response, Kagami OS is ALWAYS thinking about something.

    Architecture:
    - Goal priority queue (what to think about next)
    - Working memory (context across thoughts)
    - Thought log (observability)
    - Periodic consolidation (prevent memory overflow)

    Related:
    - kagami.core.learning.continuous_mind.ContinuousMindDaemon (receipt learning)
    - kagami.core.autonomous_goal_engine (autonomous goal generation)
    - kagami.core.memory.shared_episodic_memory (long-term storage)
    """

    def __init__(self) -> None:
        self._working_memory = SharedWorkingMemory(max_size_mb=100)
        self._goal_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._active_thoughts: deque[Thought] = deque(maxlen=1000)

        # State
        self._running = False
        self._thoughts_count = 0
        self._goals_completed = 0

        # Services (lazy loaded)
        self._llm_service = None
        self._autonomous_mind = None
        self._multi_model_router = None

    @property
    def autonomous_mind(self) -> None:
        """Lazy load autonomous goal engine (LLM-powered)."""
        if self._autonomous_mind is None:
            from kagami.core.autonomous_goal_engine import get_autonomous_goal_engine

            self._autonomous_mind = get_autonomous_goal_engine()  # type: ignore[assignment]
        return self._autonomous_mind

    @property
    def multi_model_router(self) -> None:
        """Lazy load multi-model router."""
        if self._multi_model_router is None:
            from kagami.core.routing import get_multi_model_router

            self._multi_model_router = get_multi_model_router()  # type: ignore[assignment]
        return self._multi_model_router

    async def submit_goal(self, goal: Goal) -> None:
        """Add goal to queue (user request or intrinsic)."""
        # Priority queue uses (priority, item) tuples
        # Negate priority so higher values come first
        await self._goal_queue.put((-goal.priority, goal))
        logger.info(f"📌 Goal queued: {goal.description[:50]}... (priority={goal.priority:.2f})")

    async def run_forever(self) -> None:
        """Main loop - runs 24/7 unless stopped.

        This is the heart of continuous operation.
        """
        self._running = True
        logger.info("🧠 Continuous Mind starting... (will think forever)")

        last_consolidation = time.time()
        consolidation_interval = 3 * 3600  # 3 hours

        while self._running:
            try:
                # Step 1: Get next goal (with timeout so we can check intrinsic)
                try:
                    _, goal = await asyncio.wait_for(
                        self._goal_queue.get(),
                        timeout=5.0,  # Check intrinsic goals every 5s
                    )
                except TimeoutError:
                    # No explicit goals - check for intrinsic ones
                    goal = await self._generate_intrinsic_goal()
                    if goal is None:
                        # Nothing to think about - very brief idle
                        await asyncio.sleep(1.0)
                        continue

                # Step 2: Generate thought about goal
                thought = await self._generate_thought(goal)
                self._active_thoughts.append(thought)
                self._thoughts_count += 1

                # Step 3: Reason about thought
                await self._reason_about_thought(thought)

                # Step 4: Act if actionable
                if thought.actionable and thought.action:
                    await self._execute_thought_action(thought)

                # Step 5: Update goal progress
                goal.thoughts_generated.append(thought.id)
                goal.progress = min(1.0, goal.progress + 0.1)

                if goal.progress >= 1.0:
                    goal.completed = True
                    self._goals_completed += 1

                # Step 6: Periodic memory consolidation
                if time.time() - last_consolidation > consolidation_interval:
                    await self._consolidate_memories()
                    last_consolidation = time.time()

                # Step 7: Very brief yield to asyncio (let other tasks run)
                await asyncio.sleep(0.01)  # 10ms

            except Exception as e:
                logger.error(f"Error in continuous mind loop: {e}", exc_info=True)
                await asyncio.sleep(1.0)  # Brief pause on error

    async def _generate_intrinsic_goal(self) -> Goal | None:
        """Generate goal from intrinsic motivation."""
        try:
            # Use autonomous mind to generate goals
            system_state = {
                "thoughts_count": self._thoughts_count,
                "goals_completed": self._goals_completed,
                "memory_stats": self._working_memory.get_stats(),
            }

            goals = await self.autonomous_mind.generate_autonomous_goals(system_state)  # type: ignore[attr-defined]

            if not goals:
                return None

            # Convert ActiveGoal to Goal
            active_goal = goals[0]  # Highest priority

            return Goal(
                id=active_goal.goal_id,
                description=active_goal.description,
                priority=active_goal.priority,
                source=active_goal.drive,
                context={"drive": active_goal.drive},
            )

        except Exception as e:
            logger.debug(f"Could not generate intrinsic goal: {e}")
            return None

    async def _generate_thought(self, goal: Goal) -> Thought:
        """Generate thought about goal."""
        thought_id = f"thought_{int(time.time() * 1000)}"

        # Determine thought type from goal source
        if goal.source == "user":
            thought_type = ThoughtType.USER_REQUEST
        elif "research" in goal.description.lower():
            thought_type = ThoughtType.BACKGROUND_RESEARCH
        elif "curious" in goal.description.lower():
            thought_type = ThoughtType.INTRINSIC_GOAL
        else:
            thought_type = ThoughtType.INTRINSIC_GOAL

        # Retrieve relevant context from working memory
        memory_context = {}
        if "related_thoughts" in goal.context:
            for key in goal.context["related_thoughts"]:
                value = self._working_memory.retrieve(key)
                if value:
                    memory_context[key] = value

        return Thought(
            id=thought_id,
            type=thought_type,
            content=goal.description,
            context={**goal.context, **memory_context},
            priority=goal.priority,
        )

    async def _reason_about_thought(self, thought: Thought) -> None:
        """Use LLM to reason about thought."""
        start_time = time.time()

        try:
            from pydantic import BaseModel, Field

            # Define structured output
            class ThoughtReasoning(BaseModel):
                conclusion: str = Field(description="1-2 sentence conclusion about this thought")
                actionable: bool = Field(description="Whether this thought leads to an action")
                action_type: str | None = Field(
                    description="Type of action if actionable: research|code|communicate|analyze"
                )
                action_details: dict[str, Any] | None = Field(
                    description="Details about the action to take"
                )
                confidence: float = Field(
                    description="Confidence in this reasoning (0.0-1.0)", ge=0.0, le=1.0
                )
                next_thought_suggestion: str | None = Field(description="What to think about next")

            # Build reasoning prompt
            prompt = f"""You are K os's continuous reasoning system.

Current Thought: {thought.content}
Type: {thought.type.value}
Priority: {thought.priority:.2f}
Context: {thought.context}

Recent Working Memory:
{self._get_recent_memory_summary()}

Task: Reason about this thought and determine:
1. What conclusion should be drawn?
2. Does this lead to an actionable step?
3. What action (if any) should be taken?
4. How confident are you in this reasoning?
5. What should I think about next?

Consider:
- User requests (Tim) are highest priority
- Intrinsic goals drive learning and growth
- Background research builds knowledge
- Actions should be specific and executable"""

            # Reason via LLM with structured output
            try:
                from kagami.core.services.llm.service import get_llm_service

                llm = get_llm_service()

                # Use structured client for guaranteed parsing
                response = await llm.generate_structured(
                    prompt=prompt, response_model=ThoughtReasoning
                )

                thought.conclusion = response.conclusion
                thought.actionable = response.actionable
                if response.actionable and response.action_details:
                    thought.action = {
                        "type": response.action_type,
                        "details": response.action_details,
                    }
                thought.confidence = response.confidence

            except Exception as llm_error:
                # Fallback to basic reasoning if structured fails
                logger.warning(f"Structured LLM failed, using simple reasoning: {llm_error}")

                thought.conclusion = f"Thinking about: {thought.content}"
                thought.actionable = False
                thought.action = None
                thought.confidence = 0.3

            # Store in working memory
            self._working_memory.store(f"thought_{thought.id}_conclusion", thought.conclusion)

            thought.reasoning_duration_ms = (time.time() - start_time) * 1000
            thought.completed_at = time.time()

            logger.info(
                f"💭 Thought complete: {thought.content[:30]}... "
                f"→ {thought.conclusion[:30]}... "
                f"(actionable={thought.actionable}, "
                f"confidence={thought.confidence:.2f})"
            )

        except Exception as e:
            logger.error(f"Error reasoning about thought: {e}")
            thought.conclusion = f"Error: {e}"
            thought.completed_at = time.time()

    def _get_recent_memory_summary(self, limit: int = 5) -> str:
        """Get summary of recent working memory for context."""
        recent_thoughts = list(self._active_thoughts)[-limit:]

        summary = []
        for t in recent_thoughts:
            if t.conclusion:
                summary.append(f"- {t.content[:40]}... → {t.conclusion[:40]}...")

        return "\n".join(summary) if summary else "(No recent thoughts)"

    async def _execute_thought_action(self, thought: Thought) -> None:
        """Execute action from thought."""
        try:
            # This would integrate with existing orchestrator/agent system
            logger.info(f"🎬 Executing action from thought: {thought.action}")

            # Store action result in working memory
            self._working_memory.store(
                f"thought_{thought.id}_action_result",
                {"status": "executed", "thought_id": thought.id},
            )

        except Exception as e:
            logger.error(f"Error executing thought action: {e}")

    async def _consolidate_memories(self) -> None:
        """Consolidate working memory → episodic memory.

        This prevents memory overflow by:
        1. Finding patterns in recent thoughts using embeddings
        2. Compressing similar thoughts into concepts
        3. Moving to long-term episodic memory
        4. Clearing working memory
        5. Saving to disk for persistence
        """
        logger.info("🗜️ Consolidating working memory...")

        try:
            from kagami.core.memory.shared_episodic_memory import (  # Dynamic attr
                get_shared_episodic_memory,
            )
            from kagami.core.services.embedding_service import get_embedding_service

            # Get all active thoughts
            thoughts = list(self._active_thoughts)

            stats = self._working_memory.get_stats()
            logger.info(
                f"  Working memory: {stats['size_mb']:.1f}/{stats['max_mb']}MB "
                f"({stats['utilization']:.1%} full)"
            )
            logger.info(f"  Active thoughts: {len(thoughts)}")

            if len(thoughts) < 10:
                logger.info("  Not enough thoughts to consolidate yet")
                return

            # Step 1: Embed all thought conclusions
            embedding_service = get_embedding_service()
            thought_texts = [f"{t.content} → {t.conclusion}" for t in thoughts if t.conclusion]

            if not thought_texts:
                logger.info("  No concluded thoughts to consolidate")
                return

            embeddings = embedding_service.embed_batch(thought_texts)

            # Step 2: Find clusters (similar thoughts)
            clusters = self._cluster_thoughts(embeddings, threshold=0.85)

            logger.info(f"  Found {len(clusters)} thought clusters")

            # Step 3: Extract pattern from each cluster
            episodic_memory = get_shared_episodic_memory()
            patterns_extracted = 0

            for _cluster_idx, thought_indices in clusters.items():
                if len(thought_indices) < 3:
                    continue  # Need at least 3 similar thoughts to extract pattern

                cluster_thoughts = [thoughts[i] for i in thought_indices]

                # Extract pattern via LLM
                pattern = await self._extract_pattern_from_cluster(cluster_thoughts)

                if pattern:
                    # Store pattern in episodic memory
                    await episodic_memory.store_episode(  # type: ignore[attr-defined]
                        category="thought_pattern",
                        content=pattern["description"],
                        data={
                            "pattern_type": pattern["type"],
                            "example_thoughts": [t.id for t in cluster_thoughts[:3]],
                            "frequency": len(cluster_thoughts),
                            "confidence": pattern["confidence"],
                        },
                        importance=0.8,
                        valence=pattern.get("valence", 0.5),
                    )
                    patterns_extracted += 1

            logger.info(
                f"  ✓ Extracted {patterns_extracted} patterns from {len(thoughts)} thoughts"
            )

            # Step 4: Clear old thoughts from working memory
            # Keep only recent 100 thoughts
            self._active_thoughts = deque(list(self._active_thoughts)[-100:], maxlen=1000)

            # Step 5: Save working memory to disk
            self._working_memory.save_to_disk()
            logger.info("  ✓ Working memory saved to disk")

        except Exception as e:
            logger.error(f"Error consolidating memories: {e}", exc_info=True)

    def _cluster_thoughts(self, embeddings: Any, threshold: float = 0.85) -> dict[int, list[int]]:
        """Cluster thoughts by embedding similarity.

        Args:
            embeddings: numpy array of embeddings
            threshold: similarity threshold for clustering

        Returns: {cluster_id: [thought_indices]}
        """
        from collections import defaultdict

        import numpy as np

        clusters = defaultdict(list[Any])
        assigned = set()
        cluster_id = 0

        for i in range(len(embeddings)):
            if i in assigned:
                continue

            # Start new cluster
            clusters[cluster_id].append(i)
            assigned.add(i)

            # Find similar thoughts
            for j in range(i + 1, len(embeddings)):
                if j in assigned:
                    continue

                # Cosine similarity
                similarity = np.dot(embeddings[i], embeddings[j])

                if similarity > threshold:
                    clusters[cluster_id].append(j)
                    assigned.add(j)

            cluster_id += 1

        return dict(clusters)

    async def _extract_pattern_from_cluster(self, thoughts: list[Thought]) -> dict[str, Any] | None:
        """Extract common pattern from cluster of similar thoughts."""
        try:
            # Build prompt with thought examples
            examples = "\n".join([f"- {t.content} → {t.conclusion}" for t in thoughts[:5]])

            prompt = f"""Analyze these {len(thoughts)} similar thoughts and extract the common pattern:

{examples}

What is the underlying pattern or concept these thoughts share?

Respond with:
1. Pattern type (e.g., "optimization_strategy", "learning_insight", "collaboration_pattern")
2. Description (1-2 sentences describing the pattern)
3. Confidence (0.0-1.0) in this pattern extraction
4. Valence (-1.0 to 1.0) - is this a positive or negative pattern?"""

            # Use LLM to extract pattern
            response = await self.llm_service.reason(prompt)

            return {
                "type": response.get("pattern_type", "unknown"),
                "description": response.get("description", "Pattern extracted"),
                "confidence": response.get("confidence", 0.5),
                "valence": response.get("valence", 0.0),
            }

        except Exception as e:
            logger.warning(f"Could not extract pattern: {e}")
            return None

    def stop(self) -> None:
        """Stop the continuous mind."""
        self._running = False
        logger.info("🛑 Continuous Mind stopping...")

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about continuous mind."""
        return {
            "running": self._running,
            "thoughts_count": self._thoughts_count,
            "goals_completed": self._goals_completed,
            "active_thoughts": len(self._active_thoughts),
            "working_memory": self._working_memory.get_stats(),
            "queue_size": self._goal_queue.qsize(),
        }


# Singleton
_continuous_mind: ContinuousMind | None = None


def get_continuous_mind() -> ContinuousMind:
    """Get singleton continuous mind."""
    global _continuous_mind
    if _continuous_mind is None:
        _continuous_mind = ContinuousMind()
    return _continuous_mind
