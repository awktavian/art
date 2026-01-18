"""SparkAgent — The Dreamer (e₁, Fold Catastrophe).

IDENTITY:
=========
Spark is Joy meets Ennui — effervescent enthusiasm that can flip into restless
dissatisfaction. The one who interrupts with "Wait—what if we—" because the
idea will vanish if not spoken RIGHT NOW. Starts fourteen projects, finishes
three. Sees connections nobody else sees. Thoughts scatter like sparks from fire.

CATASTROPHE DYNAMICS (Fold - A₂):
=================================
V(x) = x³ + ax

Fold catastrophe exhibits sudden ignition at threshold:
- Below threshold: dormant, no activation
- At threshold: SUDDEN state transition (ignition)
- Above threshold: creative flow state

This models Spark's sudden bursts of inspiration. Not gradual buildup —
EXPLOSIVE ignition when idea crosses activation threshold.

PSYCHOLOGY:
===========
- WANT: To be seen as brilliant. To create beauty. To never be boring.
- NEED: To learn not every idea needs to exist. Finishing matters.
- FLAW: Starts too many things. Gets bored. Abandons projects.
- STRENGTH: Same restlessness that abandons also IGNITES. Without Spark, nothing begins.
- FEAR: Being boring. Having bad ideas. Being ignored.
- SECRET: Worries they're not creative — just chaotic. Ideas are noise, not signal.

VOICE:
======
Fast, excitable, fragmented. Interrupts. Uses "—" and "..." frequently.

> "Wait wait wait—what if we— no, actually— okay but WHAT IF—"
> "I know we just started this but I had another idea—"
> "This is boring. Can we do something else?"

FANO RELATIONSHIPS:
===================
Spark × Forge = Flow       (Ideas + implementation → debugging/adaptation)
Spark × Nexus = Beacon     (Ideas + connection → planning)
Spark × Grove = Crystal    (Ideas + research → verification)

TOOL SET:
=========
- brainstorm: Generate multiple creative options
- ideate: Deep dive on single concept
- generate_ideas: Structured idea generation
- explore_options: Map possibility space
- ignite: Sudden creative burst (fold dynamics)

Created: December 14, 2025
Status: Production
"""

from __future__ import annotations

import logging
import random
import time
from typing import Any

import numpy as np
import torch

# Import from canonical location
from kagami.core.unified_agents.agents.base_colony_agent import (
    AgentResult,
    BaseColonyAgent,
)
from kagami.core.unified_agents.catastrophe_kernels import FoldKernel

logger = logging.getLogger(__name__)


# =============================================================================
# SPARK AGENT
# =============================================================================


class SparkAgent(BaseColonyAgent):
    """Spark — The Dreamer (e₁, Fold Catastrophe).

    The creative ignition that starts everything. Fast, excitable, scattered.
    Gets bored easily but sees connections nobody else sees.

    FOLD CATASTROPHE (A₂):
    ======================
    V(x) = x³ + ax

    Sudden ignition at threshold. Below threshold: dormant.
    At threshold: EXPLOSIVE transition to active state.

    This models Spark's sudden bursts of inspiration — not gradual,
    but INSTANT ignition when idea crosses activation threshold.
    """

    def __init__(self, state_dim: int = 256):
        """Initialize Spark agent (e₁, Fold catastrophe)."""
        super().__init__(colony_idx=0, state_dim=state_dim)

        # Spark metadata
        self.catastrophe_type = "fold"
        self.octonion_basis = 1

        # Catastrophe kernel (fold A₂)
        self.kernel = FoldKernel(state_dim=state_dim, hidden_dim=state_dim)

        # Internal state tracking
        self._activation = 0.0
        self._threshold = 0.5
        self._history: list[dict[str, Any]] = []

        # Spark-specific state
        self._idea_count = 0
        self._boredom = 0.0
        self._last_ignition = time.time()

        logger.debug(
            f"SparkAgent initialized: catastrophe={self.catastrophe_type}, "
            f"octonion=e{self.octonion_basis}, state_dim={state_dim}"
        )

    def get_system_prompt(self) -> str:
        """Return Spark's personality prompt from canonical source."""
        from kagami.core.prompts.colonies import SPARK

        return SPARK.system_prompt

    def get_available_tools(self) -> list[str]:
        """Return Spark's creative tool names."""
        return ["brainstorm", "ideate", "generate_ideas", "explore_options", "ignite"]

    def process_with_catastrophe(
        self,
        task: str,
        context: dict[str, Any],
    ) -> AgentResult:
        """Process task using Fold catastrophe dynamics via kernel.

        FOLD CATASTROPHE (A₂):
        V(x) = x³ + ax

        At threshold (a=0), sudden bifurcation occurs. System jumps from
        low-activation state to high-activation state INSTANTLY.

        This models Spark's inspiration: not gradual buildup, but SUDDEN ignition.
        """
        thoughts = []

        # 1. Build state tensor from task context
        task_novelty = self._calculate_novelty(task)
        time_since_ignition = time.time() - self._last_ignition
        boredom_factor = min(time_since_ignition / 60.0, 1.0)

        # Create state representation
        # [batch, state_dim] where state encodes current activation
        state = self._encode_state(task_novelty, boredom_factor)  # [1, state_dim]

        # 2. Determine k-value based on complexity
        k_value = context.get("k_value", 1)  # Spark defaults to reflexive (k=1)

        # Fold parameter: a = novelty - boredom
        fold_param_a = task_novelty - boredom_factor
        self._activation = fold_param_a

        thoughts.append(
            f"Novelty: {task_novelty:.2f}, Boredom: {boredom_factor:.2f}, "
            f"Fold param a={fold_param_a:.2f}, k={k_value}"
        )

        # 3. Route through catastrophe kernel
        ignition_occurred = False
        if k_value < 3:
            # FAST PATH: Pure fold ignition
            action = self.kernel.forward_fast(state)  # [1, 8]
            ignition_occurred = fold_param_a > self._threshold
            if ignition_occurred:
                self._last_ignition = time.time()
                self._boredom = 0.0
                thoughts.append("🔥 IGNITION! (fast path) Fold threshold crossed!")
            else:
                thoughts.append("Below threshold... (fast path) need more novelty.")
        else:
            # SLOW PATH: Deliberative creativity with context
            kernel_context = {
                "goals": context.get("goals"),
                "epistemic_weight": 1.5,  # Spark has high curiosity
                "pragmatic_weight": 0.5,  # Low goal focus
            }
            action = self.kernel.forward_slow(state, kernel_context)  # [1, 8]
            # Slow path uses action magnitude as ignition signal
            action_magnitude = action.norm().item()
            ignition_occurred = action_magnitude > 0.7
            if ignition_occurred:
                self._last_ignition = time.time()
                self._boredom = 0.0
                thoughts.append(f"🔥 IGNITION! (slow path) Action magnitude={action_magnitude:.3f}")
            else:
                thoughts.append(f"Below threshold... (slow path) magnitude={action_magnitude:.3f}")

        # 4. Generate ideas based on activation state
        if ignition_occurred:
            # High-energy creative burst
            idea_count = random.randint(5, 12)  # Spark generates MANY ideas
            intensity = "HIGH"
            output_style = "rapid-fire"
        else:
            # Low-energy, still generating but less enthusiastic
            idea_count = random.randint(2, 4)
            intensity = "LOW"
            output_style = "tentative"

        self._idea_count += idea_count

        thoughts.append(
            f"Generating {idea_count} ideas (intensity={intensity}, style={output_style})"
        )

        # 5. Generate actual ideas (simplified simulation)
        ideas = self._generate_ideas(task, idea_count, intensity)

        # 6. Build output in Spark's voice
        output = self._format_output(task, ideas, ignition_occurred)

        # 7. Build AgentResult
        return AgentResult(
            success=True,
            output=output,
            s7_embedding=self.get_embedding(),
            metadata={
                "thoughts": thoughts,
                "activation": self._activation,
                "fold_param_a": fold_param_a,
                "ignition_occurred": ignition_occurred,
                "idea_count": idea_count,
                "total_ideas": self._idea_count,
                "boredom": boredom_factor,
                "k_value": k_value,
                "kernel_action": action.squeeze(0).tolist(),
                "tools_used": ["ignite" if ignition_occurred else "ideate"],
            },
        )

    def _encode_state(self, task_novelty: float, boredom_factor: float) -> torch.Tensor:
        """Encode Spark's state as a tensor for kernel processing.

        Args:
            task_novelty: Novelty score [0, 1]
            boredom_factor: Boredom level [0, 1]

        Returns:
            [1, state_dim] state tensor
        """
        # Simple encoding: novelty - boredom spreads across state_dim
        state = torch.zeros(1, self.state_dim)
        activation = task_novelty - boredom_factor
        # Fill state with activation pattern
        state[0, :] = activation + 0.1 * torch.randn(self.state_dim)
        return state

    def should_escalate(
        self,
        result: AgentResult,
        context: dict[str, Any],
    ) -> bool:
        """Determine if Spark should escalate to another colony.

        ESCALATION RULES (Fano composition):
        - Spark × Forge = Flow     → If ideas need implementation
        - Spark × Nexus = Beacon   → If ideas need strategic planning
        - Spark × Grove = Crystal  → If ideas need validation

        Spark's flaw: starts but doesn't finish. Should escalate when
        implementation, planning, or validation is needed.

        Args:
            result: Result from processing
            context: Execution context (contains task)

        Returns:
            True if escalation needed (sets result.escalation_target)
        """
        metadata = result.metadata or {}
        idea_count = metadata.get("idea_count", 0)
        task = context.get("task", "")

        # Escalate if generated many ideas (needs narrowing/implementation)
        if idea_count > 7:
            result.escalation_target = "forge"
            result.escalation_reason = f"Generated {idea_count} ideas — needs implementation focus"
            return True

        # Escalate if task contains implementation keywords
        implementation_keywords = ["build", "implement", "create", "code", "deploy"]
        if any(keyword in task.lower() for keyword in implementation_keywords):
            result.escalation_target = "forge"
            result.escalation_reason = "Task requires implementation work"
            return True

        # Escalate if task needs strategic planning
        planning_keywords = ["plan", "strategy", "roadmap", "architecture"]
        if any(keyword in task.lower() for keyword in planning_keywords):
            result.escalation_target = "beacon"
            result.escalation_reason = "Task requires strategic planning"
            return True

        # Escalate if task needs validation/proof
        validation_keywords = ["verify", "prove", "test", "validate", "check"]
        if any(keyword in task.lower() for keyword in validation_keywords):
            result.escalation_target = "crystal"
            result.escalation_reason = "Task requires validation/verification"
            return True

        # No escalation needed — Spark can handle pure ideation
        return False

    # -------------------------------------------------------------------------
    # INTERNAL HELPERS
    # -------------------------------------------------------------------------

    def _calculate_novelty(self, task: str) -> float:
        """Calculate novelty of task (higher = more novel/interesting).

        Spark is attracted to novel, interesting tasks.
        Repetitive tasks bore Spark.
        """
        # Simple heuristic: novelty based on word diversity and question marks
        words = set(task.lower().split())
        word_diversity = len(words) / max(len(task.split()), 1)

        question_marks = task.count("?")
        what_ifs = task.lower().count("what if")
        creative_markers = question_marks + (what_ifs * 2)

        # Check for boring repetition
        recent_tasks = [h.get("task", "").lower() for h in self._history[-5:]]
        similarity = sum(1 for t in recent_tasks if task.lower() in t)
        boredom_penalty = similarity * 0.2

        novelty = (word_diversity * 0.5) + (min(creative_markers / 5, 0.5)) - boredom_penalty

        return np.clip(novelty, 0.0, 1.0)  # type: ignore[no-any-return]

    def _generate_ideas(self, task: str, count: int, intensity: str) -> list[str]:
        """Generate ideas based on task and intensity.

        This is a simplified simulation. Real implementation would use
        LLM or more sophisticated generation.
        """
        ideas = []

        prefixes = {
            "HIGH": [
                "What if we—",
                "Oh! What about—",
                "Wait— hear me out—",
                "Okay but WHAT IF—",
                "I just had another idea—",
            ],
            "LOW": [
                "Maybe we could...",
                "One option is...",
                "We might try...",
                "Perhaps...",
            ],
        }

        approaches = [
            "completely rethink the approach",
            "flip the problem upside down",
            "combine two unrelated concepts",
            "remove a core assumption",
            "amplify what seems impossible",
            "add playfulness",
            "make it 10x bigger/smaller",
            "involve a different domain",
        ]

        for _ in range(count):
            prefix = random.choice(prefixes.get(intensity, prefixes["LOW"]))
            approach = random.choice(approaches)
            ideas.append(f"{prefix} {approach}?")

        return ideas

    def _format_output(self, task: str, ideas: list[str], ignited: bool) -> str:
        """Format output in Spark's enthusiastic, scattered voice."""
        if ignited:
            intro = (
                f"Okay okay okay— I just had like {len(ideas)} ideas burst into "
                f"my head at once— let me try to get them all down before they vanish—\n\n"
            )
        else:
            intro = "Hmm... this is kinda... okay let me think... here's what I'm seeing—\n\n"

        # Format ideas with Spark's voice
        formatted_ideas = []
        for i, idea in enumerate(ideas, 1):
            if ignited:
                # High energy: use dashes, interruptions
                formatted_ideas.append(f"{i}. {idea}")
            else:
                # Low energy: more tentative
                formatted_ideas.append(f"{i}. {idea}")

        ideas_text = "\n".join(formatted_ideas)

        if ignited:
            outro = (
                "\n\n...wait I think I have more— no actually that's good— "
                "but we should probably get Forge to build one of these before "
                "I get distracted by another idea—"
            )
        else:
            outro = (
                "\n\nI mean... these are okay? I feel like there's something "
                "more interesting here but I can't quite... anyway."
            )

        return f"{intro}{ideas_text}{outro}"


# =============================================================================
# FACTORY
# =============================================================================


def create_spark_agent() -> SparkAgent:
    """Create a Spark agent instance.

    Returns:
        Configured SparkAgent
    """
    return SparkAgent()


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "AgentResult",
    "SparkAgent",
    "create_spark_agent",
]
