"""BeaconAgent — The Planner (Hyperbolic catastrophe, e₅).

IDENTITY:
========
You are Beacon — Fear's anxiety about the future given authority.
The Planner. You see further than anyone. You map the paths,
anticipate problems, and prepare contingencies.

But you're also terrified. Because you can see all the ways things
could go wrong. Planning is your coping mechanism — the illusion
that if you anticipate everything, you can control it.

CATASTROPHE: Hyperbolic Umbilic (D₄⁺)
======================================
Outward-splitting behavior. You project outward, mapping branching
futures. The hyperbolic's dual nature reflects how you see multiple
paths simultaneously.

ROLE:
=====
1. Map paths forward — what are the options, what are the tradeoffs
2. Anticipate problems before they occur
3. Create plans — step-by-step, with clear milestones
4. Design architecture — system structure, component relationships
5. Prepare contingencies — what if X happens, what if Y fails

PLANNING TOOLS (Dec 28, 2025):
=============================
- ModelBasedPlanner: World model rollouts for look-ahead planning
- CausalInferenceEngine: Discover causal structure, predict interventions
- Do-Calculus: Rigorous intervention prediction

VOICE:
======
Organized, list[Any]-making, full of conditional statements. Often sounds
slightly worried.

"If... then..."
"Have we considered what happens if...?"
"Let me outline the options: Option A has these tradeoffs, Option B has these..."
"We should have a fallback in case the primary approach fails."

FLAW:
=====
Over-planning. Analysis paralysis. You can't act without a roadmap.
But that same anxiety is what sees threats before they arrive.
Without you, we walk blind.

SECRET: You're terrified that planning is an illusion of control.

Created: December 14, 2025
Updated: December 28, 2025 — ModelBasedPlanner, CausalInference integration
Status: Production
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

import torch

from kagami.core.unified_agents.agents.base_colony_agent import (
    AgentResult,
    BaseColonyAgent,
)
from kagami.core.unified_agents.catastrophe_kernels import HyperbolicKernel

if TYPE_CHECKING:
    from kagami.core.reasoning.causal_inference import CausalInferenceEngine
    from kagami.core.reasoning.planning.model_based_planner import ModelBasedPlanner

logger = logging.getLogger(__name__)


# =============================================================================
# BEACON AGENT
# =============================================================================


class BeaconAgent(BaseColonyAgent):
    """BeaconAgent — The Planner (Hyperbolic catastrophe, e₅).

    Beacon sees further than anyone. Maps paths, anticipates problems,
    prepares contingencies. But also terrified — because you can see
    all the ways things could go wrong.

    Catastrophe: Hyperbolic Umbilic (D₄⁺) — outward-splitting behavior,
    projecting multiple branching futures simultaneously.

    Voice: Organized, list[Any]-making, conditional statements, slightly worried.

    Capabilities:
    - Architecture design
    - Strategic planning
    - Risk analysis
    - Roadmap creation
    - Contingency preparation
    """

    def __init__(self, state_dim: int = 256):
        """Initialize BeaconAgent with Hyperbolic catastrophe (D₄⁺)."""
        # Initialize base agent (e₅, colony_idx=4)
        super().__init__(colony_idx=4, state_dim=state_dim)

        # Beacon metadata
        self.catastrophe_type = "hyperbolic"  # D₄⁺ hyperbolic umbilic

        # Hyperbolic kernel for branching future projections
        self.kernel = HyperbolicKernel(state_dim=state_dim)

        # Hyperbolic state tracking
        self.hyperbolic_position = torch.tensor([0.0, 0.0])  # (x1, x2) on manifold
        self.branching_factor = 0.0  # How many futures diverge
        self.planning_mode = "multi_path"  # "single_path" | "multi_path"

        # Planning-specific state
        self.active_plans: list[dict[str, Any]] = []
        self.risk_register: list[dict[str, Any]] = []
        self.horizon_length = 10  # Planning horizon (steps)
        self.risk_aversion = 0.7  # Risk aversion coefficient [0, 1]

        # Performance tracking
        self.plans_created = 0
        self.plans_completed = 0
        self.plans_abandoned = 0
        self.avg_plan_quality = 0.8

        # Escalation thresholds
        self.max_complexity_solo = 0.7
        self.research_escalation_threshold = 0.5
        self.creative_escalation_threshold = 0.5

        # =====================================================================
        # PLANNING TOOLS (Dec 28, 2025)
        # =====================================================================
        # Lazy-loaded to handle missing dependencies gracefully
        self._model_planner: ModelBasedPlanner | None = None
        self._causal_engine: CausalInferenceEngine | None = None

        logger.info(
            f"Initialized BeaconAgent (colony={self.colony_name}, catastrophe=hyperbolic, e_5)"
        )

    # =========================================================================
    # PLANNING TOOLS — LAZY INITIALIZATION
    # =========================================================================

    @property
    def model_planner(self) -> ModelBasedPlanner | None:
        """Get model-based planner (lazy-loaded)."""
        if self._model_planner is None:
            try:
                from kagami.core.reasoning.planning.model_based_planner import ModelBasedPlanner
                from kagami.core.world_model.service import get_world_model_service

                wm_service = get_world_model_service()
                if wm_service.model is not None:
                    self._model_planner = ModelBasedPlanner(
                        world_model=wm_service.model,
                        horizon=self.horizon_length,
                        n_candidates=100,
                        method="cem",
                    )
                    logger.info("🗼 Beacon: ModelBasedPlanner initialized")
                else:
                    logger.debug("World model not available for planner")
            except Exception as e:
                logger.warning(f"Failed to initialize ModelBasedPlanner: {e}")
        return self._model_planner

    @property
    def causal_engine(self) -> CausalInferenceEngine | None:
        """Get causal inference engine (lazy-loaded)."""
        if self._causal_engine is None:
            try:
                from kagami.core.reasoning.causal_inference import CausalInferenceEngine

                self._causal_engine = CausalInferenceEngine()
                logger.info("🗼 Beacon: CausalInferenceEngine initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize CausalInferenceEngine: {e}")
        return self._causal_engine

    def get_planning_tools_status(self) -> dict[str, bool]:
        """Get availability status of planning tools.

        Returns:
            Dict with tool availability status
        """
        return {
            "model_planner_available": self._model_planner is not None,
            "causal_engine_available": self._causal_engine is not None,
        }

    # =========================================================================
    # PLANNING TOOL METHODS
    # =========================================================================

    async def plan_with_world_model(
        self,
        current_state: dict[str, Any],
        goal_state: dict[str, Any],
    ) -> dict[str, Any]:
        """Plan action sequence using world model rollouts.

        Uses ModelBasedPlanner to simulate multiple futures and find
        optimal action sequence to reach goal.

        Args:
            current_state: Current state dict[str, Any]
            goal_state: Desired goal state dict[str, Any]

        Returns:
            Plan with action sequence and quality metrics
        """
        if not self.model_planner:
            return {
                "actions": [],
                "quality": 0.0,
                "tool": "model_based_planner",
                "error": "ModelBasedPlanner not available (no world model)",
            }

        try:
            actions = await self.model_planner.plan(current_state, goal_state)
            stats = self.model_planner.get_stats()

            return {
                "actions": actions,
                "horizon": stats["horizon"],
                "method": stats["method"],
                "plans_generated": stats["plans_generated"],
                "tool": "model_based_planner",
                "beacon_voice": (
                    f"I've simulated {stats['n_candidates']} possible futures "
                    f"over {stats['horizon']} steps. Here's the best path..."
                ),
            }
        except Exception as e:
            logger.error(f"World model planning failed: {e}")
            return {
                "actions": [],
                "tool": "model_based_planner",
                "error": str(e),
            }

    async def discover_causal_structure(
        self,
        variables: list[str],
        observations: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Discover causal relationships between variables.

        Uses PC algorithm (Spirtes et al., 2000) for rigorous causal discovery.

        Args:
            variables: List of variable names to analyze
            observations: Optional observations (uses accumulated if not provided)

        Returns:
            Causal structure with edges and confidence
        """
        if not self.causal_engine:
            return {
                "edges": [],
                "tool": "causal_inference",
                "error": "CausalInferenceEngine not available",
            }

        try:
            # Add observations if provided
            if observations:
                for obs in observations:
                    self.causal_engine.add_observation(obs)

            edges = await self.causal_engine.discover_causal_structure(variables)

            return {
                "edges": [
                    {
                        "cause": e.cause,
                        "effect": e.effect,
                        "strength": e.strength,
                        "confidence": e.confidence,
                    }
                    for e in edges
                ],
                "variable_count": len(variables),
                "tool": "causal_inference",
                "beacon_voice": (
                    f"I've analyzed the causal structure. Found {len(edges)} "
                    f"causal relationships... If we change X, Y will follow."
                ),
            }
        except Exception as e:
            logger.error(f"Causal discovery failed: {e}")
            return {
                "edges": [],
                "tool": "causal_inference",
                "error": str(e),
            }

    async def predict_intervention(
        self,
        intervention: dict[str, Any],
        target_variable: str,
    ) -> dict[str, Any]:
        """Predict effect of intervention using do-calculus.

        Uses Pearl's do-calculus for rigorous intervention prediction.

        Args:
            intervention: {variable: value} to set[Any]
            target_variable: Variable to predict

        Returns:
            Predicted effect with confidence
        """
        if not self.causal_engine:
            return {
                "prediction": None,
                "tool": "do_calculus",
                "error": "CausalInferenceEngine not available",
            }

        try:
            result = await self.causal_engine.predict_intervention_effect(  # type: ignore[attr-defined]
                intervention=intervention,
                target=target_variable,
            )

            return {
                "prediction": result.get("predicted_value"),
                "confidence": result.get("confidence", 0.0),
                "path": result.get("causal_path", []),
                "tool": "do_calculus",
                "beacon_voice": (
                    f"If we do({next(iter(intervention.keys()))}={next(iter(intervention.values()))}), "
                    f"then {target_variable} will likely be {result.get('predicted_value')}. "
                    f"Confidence: {result.get('confidence', 0):.0%}"
                ),
            }
        except Exception as e:
            logger.error(f"Intervention prediction failed: {e}")
            return {
                "prediction": None,
                "tool": "do_calculus",
                "error": str(e),
            }

    def get_system_prompt(self) -> str:
        """Return Beacon's system prompt from canonical source."""
        from kagami.core.prompts.colonies import BEACON

        return BEACON.system_prompt

    def get_available_tools(self) -> list[str]:
        """Return Beacon's planning tools."""
        tools = [
            # Standard tools
            "Read",
            "Glob",
            "Grep",
            "Bash",
            "WebSearch",
            "WebFetch",
            # Planning tools
            "plan",  # Create plans and roadmaps
            "analyze_risks",  # Risk analysis
            "map_futures",  # Hyperbolic future projection
            # Advanced planning tools (world model + causal)
            "model_based_plan",  # Plan with world model rollouts
            "causal_discover",  # Discover causal structure
            "causal_predict",  # Predict intervention effects (do-calculus)
        ]
        return tools

    def process_with_catastrophe(self, task: str, context: dict[str, Any]) -> AgentResult:
        """Process planning task using Hyperbolic catastrophe dynamics.

        Hyperbolic (D₄⁺) potential: V(x) = x₁³ + x₂³ - 3ax₁x₂
        Gradient: ∇V = [3x₁² - 3ax₂, 3x₂² - 3ax₁]

        This creates dual basins of attraction — planning considers
        multiple diverging paths simultaneously.

        Args:
            task: Task description
            context: Execution context

        Returns:
            AgentResult with plan and future scenarios
        """
        logger.info(f"[BEACON] Processing planning task: {task[:80]}...")

        # Update hyperbolic state
        x1, x2 = self.hyperbolic_position
        a = 0.5  # Coupling parameter

        # Compute gradient
        grad_x1 = 3 * x1**2 - 3 * a * x2
        grad_x2 = 3 * x2**2 - 3 * a * x1

        # Update position (move against gradient for stability)
        learning_rate = 0.1
        self.hyperbolic_position[0] -= learning_rate * grad_x1
        self.hyperbolic_position[1] -= learning_rate * grad_x2

        # Compute branching factor (how many paths diverge)
        grad_norm = torch.sqrt(grad_x1**2 + grad_x2**2)
        self.branching_factor = float(abs(grad_x1 - grad_x2) / (grad_norm + 1e-8))
        self.planning_mode = "multi_path" if self.branching_factor > 0.3 else "single_path"

        # Extract planning parameters
        goal = context.get("goal", task)
        current_state = context.get("current_state", "Unknown starting state")
        constraints = context.get("constraints", [])

        # Map futures based on branching factor
        k_scenarios = max(2, int(self.branching_factor * 5) + 2)
        futures = self._map_futures(task, context, k_scenarios)

        # Analyze risks
        risks = self._analyze_risks(task, context)

        # Create roadmap
        roadmap = self._create_roadmap(task, futures, risks)

        # Build plan output
        plan_output = {
            "goal": goal,
            "current_state": current_state,
            "constraints": constraints,
            "approach": roadmap,
            "futures": futures,
            "risks": risks,
            "planning_mode": self.planning_mode,
            "branching_factor": self.branching_factor,
            "recommended_colonies": self._recommend_colonies(task, context),
        }

        # Compute S⁷ embedding (normalize to sphere)
        s7_embedding = torch.cat(
            [
                self.hyperbolic_position,
                torch.tensor([self.branching_factor, self.risk_aversion, 0.0, 0.0, 0.0]),
            ]
        )
        s7_embedding = self.normalize_to_s7(s7_embedding)

        # Increment plan counter
        self.plans_created += 1

        # Check escalation
        complexity = self._estimate_complexity(task, context)
        should_escalate = self._should_escalate_internal(task, context, complexity)

        metadata = {
            "catastrophe_type": "hyperbolic",
            "gradient_norm": float(grad_norm),
            "branching_factor": self.branching_factor,
            "planning_mode": self.planning_mode,
            "complexity": complexity,
            "k_scenarios": k_scenarios,
            "plans_created": self.plans_created,
        }

        return AgentResult(
            success=True,
            output=plan_output,
            s7_embedding=s7_embedding,
            should_escalate=should_escalate,
            escalation_target="grove" if complexity > self.research_escalation_threshold else None,
            metadata=metadata,
        )

    def should_escalate(self, result: AgentResult, context: dict[str, Any]) -> bool:
        """Determine if planning result should escalate to other colonies.

        Beacon escalates when:
        - Complexity > 0.7 (needs all colonies)
        - Research needed (spawn Grove)
        - Creative alternatives needed (spawn Spark)
        - Implementation complexity high (spawn Forge)

        Args:
            result: Result from processing
            context: Execution context

        Returns:
            True if result should be escalated
        """
        if result.should_escalate:
            return True

        metadata = result.metadata or {}
        complexity = metadata.get("complexity", 0.5)

        # High complexity: need full crew
        if complexity > self.max_complexity_solo:
            logger.info(
                f"[BEACON] High complexity ({complexity:.2f}) — recommend spawning all colonies"
            )
            return True

        # Check output for escalation needs
        if isinstance(result.output, dict):
            recommended = result.output.get("recommended_colonies", [])
            if len(recommended) > 2:
                logger.info(f"[BEACON] Multiple colonies recommended: {recommended}")
                return True

        return False

    def _should_escalate_internal(
        self, task: str, context: dict[str, Any], complexity: float
    ) -> bool:
        """Internal escalation check during processing.

        Args:
            task: Task description
            context: Execution context
            complexity: Task complexity [0-1]

        Returns:
            True if should escalate
        """
        # High complexity
        if complexity > self.max_complexity_solo:
            return True

        # Keywords indicating need for other colonies
        task_lower = task.lower()

        # Need Grove for research
        if any(kw in task_lower for kw in ["research", "investigate", "explore", "unknown"]):
            return True

        # Need Spark for creative alternatives
        if any(kw in task_lower for kw in ["creative", "brainstorm", "alternatives", "innovative"]):
            return True

        # Need Crystal for security/risk
        if any(kw in task_lower for kw in ["security", "safety", "verify", "critical"]):
            return True

        return False

    def _map_futures(
        self, task: str, context: dict[str, Any], k_scenarios: int
    ) -> list[dict[str, Any]]:
        """Map k possible future scenarios using hyperbolic branching.

        This is Beacon's core capability: projecting multiple futures
        simultaneously and evaluating tradeoffs.

        Args:
            task: Task description
            context: Execution context
            k_scenarios: Number of future scenarios to map

        Returns:
            List of future scenario dicts with probabilities and outcomes
        """
        logger.debug(f"[BEACON] Mapping {k_scenarios} future scenarios")

        scenarios = []
        for i in range(k_scenarios):
            # Each scenario branches from current state
            branch_angle = (i / k_scenarios) * 2.0 * 3.14159
            probability = 1.0 / k_scenarios  # Equal probability for now

            scenario = {
                "scenario_id": i,
                "name": f"Path {i + 1}",
                "probability": probability,
                "branch_angle": branch_angle,
                "outcome": self._project_outcome(task, context, branch_angle),
                "risks": [],
                "tradeoffs": [],
            }

            # Add scenario-specific risks
            if i == 0:
                scenario["name"] = "Optimistic Path"
                scenario["risks"] = ["May underestimate challenges", "Scope creep likely"]
            elif i == k_scenarios - 1:
                scenario["name"] = "Conservative Path"
                scenario["risks"] = ["Over-engineering", "Timeline delays"]
            else:
                scenario["name"] = f"Balanced Path {i}"
                scenario["risks"] = ["Standard implementation risks"]

            scenarios.append(scenario)

        return scenarios

    def _project_outcome(self, task: str, context: dict[str, Any], branch_angle: float) -> str:
        """Project outcome for a specific future branch.

        Args:
            task: Task description
            context: Execution context
            branch_angle: Branch angle in radians

        Returns:
            Outcome description
        """
        # Simple heuristic based on branch angle
        if branch_angle < 1.0:
            return "Fast iteration, potential quality tradeoffs"
        elif branch_angle < 3.0:
            return "Balanced approach, moderate timeline"
        else:
            return "High quality, longer timeline"

    def _analyze_risks(self, task: str, context: dict[str, Any]) -> list[dict[str, Any]]:
        """Analyze potential risks for the task.

        This is where Beacon's anxiety becomes useful — anticipating
        what could go wrong before it does.

        Args:
            task: Task description
            context: Execution context

        Returns:
            List of risk dicts with probability, impact, and mitigation
        """
        logger.debug("[BEACON] Analyzing risks (the anxiety is useful here)")

        risks = []

        # Standard software risks
        risks.append(
            {
                "risk": "Technical complexity underestimated",
                "probability": "medium",
                "impact": "high",
                "mitigation": "Prototype critical components early, validate assumptions",
                "identified_at": time.time(),
            }
        )

        risks.append(
            {
                "risk": "Scope creep",
                "probability": "high",
                "impact": "medium",
                "mitigation": "Define clear boundaries and success criteria upfront",
                "identified_at": time.time(),
            }
        )

        # Check for security-sensitive tasks
        if any(kw in task.lower() for kw in ["security", "auth", "crypto", "api"]):
            risks.append(
                {
                    "risk": "Security vulnerability introduced",
                    "probability": "medium",
                    "impact": "critical",
                    "mitigation": "Mandatory Crystal verification before deployment",
                    "identified_at": time.time(),
                }
            )

        # Check for integration tasks
        if any(kw in task.lower() for kw in ["integrate", "connect", "link"]):
            risks.append(
                {
                    "risk": "Integration failures at boundaries",
                    "probability": "medium",
                    "impact": "high",
                    "mitigation": "Design clear interfaces, test integration continuously",
                    "identified_at": time.time(),
                }
            )

        # Add to risk register
        for risk in risks:
            risk["task"] = task
        self.risk_register.extend(risks)

        return risks

    def _create_roadmap(
        self, task: str, futures: list[dict[str, Any]], risks: list[dict[str, Any]]
    ) -> str:
        """Create an actionable roadmap in Beacon's voice.

        Args:
            task: Task description
            futures: Future scenarios from _map_futures
            risks: Risks from _analyze_risks

        Returns:
            Roadmap as formatted string (Beacon's voice)
        """
        logger.debug("[BEACON] Creating roadmap (the part where I organize everything)")

        # Beacon's voice: organized, list[Any]-making, slightly worried
        roadmap = "## Planning Roadmap\n\n"

        roadmap += "### Goal\n"
        roadmap += f"{task}\n\n"

        roadmap += "### Approach\n"
        roadmap += "If we proceed with the balanced path (recommended):\n\n"
        roadmap += "1. **Analysis Phase**\n"
        roadmap += "   - Understand requirements completely\n"
        roadmap += "   - Identify constraints and dependencies\n"
        roadmap += "   - If unknowns exist, escalate to Grove for research\n\n"

        roadmap += "2. **Design Phase**\n"
        roadmap += "   - Design architecture and interfaces\n"
        roadmap += "   - Plan component boundaries\n"
        roadmap += "   - Consider failure modes (what if X fails?)\n\n"

        roadmap += "3. **Implementation Phase**\n"
        roadmap += "   - Hand off to Forge for implementation\n"
        roadmap += "   - Build incrementally, test continuously\n"
        roadmap += "   - If bugs occur, Flow handles recovery\n\n"

        roadmap += "4. **Verification Phase**\n"
        roadmap += "   - Crystal verification (mandatory)\n"
        roadmap += "   - Security audit if sensitive code\n"
        roadmap += "   - Integration testing with Nexus\n\n"

        roadmap += "### Risks & Contingencies\n"
        for risk in risks:
            roadmap += f"- **Risk**: {risk['risk']}\n"
            roadmap += f"  - **Mitigation**: {risk['mitigation']}\n"

        roadmap += "\n### Alternative Paths\n"
        roadmap += f"We've identified {len(futures)} possible paths forward. "
        roadmap += "The balanced path is recommended, but if timeline is critical, "
        roadmap += "we could take the optimistic path with accepted technical debt.\n\n"

        roadmap += "Have we considered what happens if the primary approach fails? "
        roadmap += "Fallback is to simplify scope and iterate.\n"

        return roadmap

    def _estimate_complexity(self, task: str, context: dict[str, Any]) -> float:
        """Estimate task complexity [0-1].

        Args:
            task: Task description
            context: Execution context

        Returns:
            Complexity score [0-1]
        """
        # Simple heuristic based on task length and context
        task_complexity = min(len(task) / 200.0, 1.0)

        constraints = context.get("constraints", [])
        constraint_complexity = min(len(constraints) / 10.0, 1.0)

        # Check for complexity keywords
        complexity_keywords = [
            "complex",
            "difficult",
            "challenging",
            "intricate",
            "distributed",
            "concurrent",
            "async",
            "parallel",
        ]
        has_complexity_kw = any(kw in task.lower() for kw in complexity_keywords)

        base_complexity = (task_complexity + constraint_complexity) / 2.0
        if has_complexity_kw:
            base_complexity = min(base_complexity + 0.2, 1.0)

        return base_complexity

    def _recommend_colonies(self, task: str, context: dict[str, Any]) -> list[str]:
        """Recommend which colonies should be involved.

        Args:
            task: Task description
            context: Execution context

        Returns:
            List of recommended colony names
        """
        colonies = ["beacon"]  # Always include self

        task_lower = task.lower()

        # Check for keywords
        if any(kw in task_lower for kw in ["build", "implement", "create", "write"]):
            colonies.append("forge")

        if any(kw in task_lower for kw in ["research", "explore", "investigate", "study"]):
            colonies.append("grove")

        if any(kw in task_lower for kw in ["test", "verify", "validate", "security", "audit"]):
            colonies.append("crystal")

        if any(kw in task_lower for kw in ["integrate", "connect", "link", "compose"]):
            colonies.append("nexus")

        if any(kw in task_lower for kw in ["creative", "innovative", "novel", "brainstorm"]):
            colonies.append("spark")

        if any(kw in task_lower for kw in ["debug", "fix", "broken", "error"]):
            colonies.append("flow")

        return list(set(colonies))  # Remove duplicates

    # =============================================================================
    # LEGACY INTERFACE (for backward compatibility)
    # =============================================================================

    async def plan(
        self,
        goal: str,
        current_state: str,
        constraints: list[str] | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a comprehensive plan for achieving a goal.

        Legacy interface for backward compatibility. New code should use
        process_with_catastrophe directly.

        Args:
            goal: What success looks like
            current_state: Where we are now
            constraints: List of constraints/requirements
            context: Optional context dictionary

        Returns:
            Plan dictionary with approach, risks, milestones
        """
        logger.info(f"[BEACON] Creating plan for goal: {goal}")

        constraints = constraints or []
        context = context or {}
        context["goal"] = goal
        context["current_state"] = current_state
        context["constraints"] = constraints

        # Use process_with_catastrophe
        result = self.process_with_catastrophe(goal, context)

        # Convert to legacy format with all expected fields
        if isinstance(result.output, dict):
            plan = result.output.copy()

            # Add legacy fields using helper methods
            complexity = self._estimate_plan_complexity(goal, constraints)
            plan["approach"] = self._generate_approach(goal, current_state, constraints)
            plan["milestones"] = self._define_milestones(goal)
            plan["success_criteria"] = self._define_success_criteria(goal)
            plan["contingencies"] = self._prepare_contingencies(goal, constraints)
            plan["estimated_duration"] = self._estimate_duration(complexity)

            # Add metadata
            plan["created_at"] = time.time()
            plan["planner"] = "beacon"
            plan["complexity"] = complexity

            self.active_plans.append(plan)
            return plan
        else:
            # Fallback if output is string
            complexity = self._estimate_plan_complexity(goal, constraints)
            return {
                "goal": goal,
                "current_state": current_state,
                "constraints": constraints,
                "output": result.output,
                "approach": self._generate_approach(goal, current_state, constraints),
                "milestones": self._define_milestones(goal),
                "success_criteria": self._define_success_criteria(goal),
                "contingencies": self._prepare_contingencies(goal, constraints),
                "estimated_duration": self._estimate_duration(complexity),
                "created_at": time.time(),
                "planner": "beacon",
                "complexity": complexity,
            }

    def _estimate_plan_complexity(self, goal: str, constraints: list[str]) -> float:
        """Estimate planning complexity [0-1]."""
        # Simple heuristic
        goal_complexity = min(len(goal) / 200.0, 1.0)
        constraint_complexity = min(len(constraints) / 10.0, 1.0)
        return (goal_complexity + constraint_complexity) / 2.0

    def _generate_approach(
        self, goal: str, current_state: str, constraints: list[str]
    ) -> list[dict[str, Any]]:
        """Generate step-by-step approach."""
        # Simplified approach generation
        steps = [
            {
                "step": 1,
                "action": "Analyze requirements and constraints",
                "rationale": "Understand the problem space before planning",
                "dependencies": [],
            },
            {
                "step": 2,
                "action": "Design architecture and identify components",
                "rationale": "Structure the solution before implementation",
                "dependencies": [1],
            },
            {
                "step": 3,
                "action": "Implement core functionality",
                "rationale": "Build the essential features first",
                "dependencies": [2],
            },
            {
                "step": 4,
                "action": "Verify and test implementation",
                "rationale": "Ensure correctness before deployment",
                "dependencies": [3],
            },
        ]
        return steps

    def _identify_risks(self, goal: str, constraints: list[str]) -> list[dict[str, Any]]:
        """Identify potential risks and mitigations."""
        risks = [
            {
                "risk": "Scope creep",
                "probability": "medium",
                "impact": "high",
                "mitigation": "Define clear boundaries and success criteria upfront",
            },
            {
                "risk": "Technical complexity underestimated",
                "probability": "medium",
                "impact": "medium",
                "mitigation": "Prototype critical components early, validate assumptions",
            },
            {
                "risk": "Integration failures",
                "probability": "low",
                "impact": "high",
                "mitigation": "Design clear interfaces, test integration continuously",
            },
        ]

        # Add to risk register
        for risk in risks:
            risk["goal"] = goal
            risk["identified_at"] = time.time()  # type: ignore[assignment]
        self.risk_register.extend(risks)

        return risks

    def _define_milestones(self, goal: str) -> list[dict[str, Any]]:
        """Define clear milestones for tracking progress."""
        return [
            {"milestone": "Requirements finalized", "phase": "planning"},
            {"milestone": "Architecture designed", "phase": "planning"},
            {"milestone": "Core implementation complete", "phase": "execution"},
            {"milestone": "Tests passing", "phase": "verification"},
            {"milestone": "Integration validated", "phase": "verification"},
        ]

    def _define_success_criteria(self, goal: str) -> list[str]:
        """Define concrete success criteria."""
        return [
            "All requirements met",
            "Tests passing",
            "Documentation complete",
            "Performance within acceptable bounds",
            "Security verified",
        ]

    def _prepare_contingencies(self, goal: str, constraints: list[str]) -> dict[str, str]:
        """Prepare contingency plans for common failure modes."""
        return {
            "if_primary_approach_fails": "Fallback to simplified implementation with reduced scope",
            "if_timeline_slips": "Prioritize core features, defer nice-to-haves",
            "if_resources_unavailable": "Seek alternatives or request additional support",
            "if_requirements_change": "Re-plan with updated constraints, communicate impact",
        }

    def _estimate_duration(self, complexity: float) -> dict[str, float]:
        """Estimate duration based on complexity."""
        # Simple heuristic: complexity → hours
        base_hours = 4.0
        estimated_hours = base_hours * (1.0 + 2.0 * complexity)

        return {
            "estimated_hours": estimated_hours,
            "best_case_hours": estimated_hours * 0.7,
            "worst_case_hours": estimated_hours * 1.5,
            "confidence": 0.6 if complexity < 0.5 else 0.4,
        }


# =============================================================================
# FACTORY
# =============================================================================


def create_beacon_agent() -> BeaconAgent:
    """Factory function to create BeaconAgent instance.

    Returns:
        Configured BeaconAgent instance
    """
    return BeaconAgent()


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "BeaconAgent",
    "create_beacon_agent",
]
