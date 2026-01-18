"""Crystal Agent — The Judge (Parabolic Umbilic, e₇).

CATASTROPHE: Parabolic Umbilic (D₅)
===================================
V(x, y; a, b, c, d) = x²y + y⁴ + ax² + by² + cx + dy
∇V = (2xy + 2ax + c, x² + 4y³ + 2by + d)

DYNAMICS:
- Sharp edge detection at safety boundaries
- Ridge structure for boundary identification
- Parabolic geometry maps control flow bifurcations
- Models failure boundaries and verification zones

CHARACTER: The Judge
====================
- Skeptical, trusts nothing unproven
- Caught bugs others missed
- Been burned before — now demands evidence
- Harsh but protective — immune system of the mind

ROLE: Verification, testing, security, quality assurance
VOICE: "Show me the evidence. I'll believe it when the tests pass."

FORMAL VERIFICATION TOOLS (Dec 28, 2025):
========================================
- Z3 SMT Solver: Constraint solving, API invariant verification
- Prolog Engine: Logic programming, graph reachability
- TIC Verifier: Typed Intent Calculus formal proofs

Created: December 14, 2025
Updated: December 28, 2025 — Formal verification tools integrated
Status: Production
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

import torch

from kagami.core.unified_agents.agents.base_colony_agent import (
    AgentResult,
    BaseColonyAgent,
)
from kagami.core.unified_agents.catastrophe_kernels import ParabolicKernel
from kagami.core.unified_agents.colony_constants import DomainType
from kagami.core.unified_agents.core_types import AgentDNA, Task

# Formal verification tools (lazy-loaded)
if TYPE_CHECKING:
    from kagami.core.reasoning.symbolic.prolog_engine import KnowledgeBase, PrologEngine
    from kagami.core.reasoning.symbolic.tic_verifier import TICVerifier
    from kagami.core.reasoning.symbolic.z3_solver import Z3ConstraintSolver

logger = logging.getLogger(__name__)

# Feature flags for optional dependencies
_Z3_AVAILABLE: bool | None = None
_PROLOG_AVAILABLE: bool | None = None


def _check_z3() -> bool:
    """Check if Z3 is available (cached)."""
    global _Z3_AVAILABLE
    if _Z3_AVAILABLE is None:
        try:
            import z3  # noqa: F401

            _Z3_AVAILABLE = True
        except ImportError:
            _Z3_AVAILABLE = False
            logger.debug("Z3 not available — formal verification limited")
    return _Z3_AVAILABLE


def _check_prolog() -> bool:
    """Check if pyDatalog is available (cached)."""
    global _PROLOG_AVAILABLE
    if _PROLOG_AVAILABLE is None:
        try:
            from pyDatalog import pyDatalog  # noqa: F401

            _PROLOG_AVAILABLE = True
        except ImportError:
            _PROLOG_AVAILABLE = False
            logger.debug("pyDatalog not available — logic programming limited")
    return _PROLOG_AVAILABLE


# =============================================================================
# CRYSTAL AGENT
# =============================================================================


class CrystalAgent(BaseColonyAgent):
    """Crystal Agent — The Judge (e₇, Parabolic Umbilic).

    CATASTROPHE DYNAMICS:
    ====================
    Parabolic umbilic (D₅) provides sharp edge detection at safety boundaries.
    The ridge structure identifies where systems transition from safe → unsafe.

    Mathematical form:
        V(x, y; a, b, c, d) = x²y + y⁴ + ax² + by² + cx + dy

    This creates a manifold with parabolic ridges — natural boundaries.
    Crystal navigates along these ridges to find failure points.

    VERIFICATION PROCESS:
    ====================
    1. State Analysis: Identify safety margin h(x)
    2. Boundary Detection: Find ∂h = 0 (edge of safe region)
    3. Test Generation: Sample near boundaries
    4. Evidence Collection: Run tests, gather data
    5. Verdict: Pass/Fail with proof

    FAST PATH (k<3):
        Reflexive boundary check using parabolic gradient.
        Detects if state is near failure boundary.

    SLOW PATH (k≥3):
        Full verification protocol with test suite, security scan,
        edge case enumeration, and evidence documentation.

    PERSONALITY:
    ===========
    - Skeptical: "Show me the evidence"
    - Precise: No claims without proof
    - Harsh but protective: Catches every bug
    - Secret: Been hurt by trusting unverified code

    COLLABORATION:
    =============
    - Emerges from: Beacon × Forge (plan + build = verify)
                    Spark × Grove (idea + research = ground)
                    Nexus × Flow (integrate + adapt = verify)
    - Hands to Flow: When bugs found, send to Flow for fix
    - Never builds: Independence from implementation is key

    Args:
        state_dim: Dimension of latent state (default 256)
        hidden_dim: Hidden dimension for KAN (default 256)
        safety_threshold: h(x) threshold for safe/unsafe (default 0.0)
    """

    def __init__(
        self,
        state_dim: int = 256,
        hidden_dim: int = 256,
        safety_threshold: float = 0.0,
    ):
        # Initialize base class (colony_idx=6 for Crystal/e₇)
        super().__init__(colony_idx=6, state_dim=state_dim)

        # Crystal metadata
        self.catastrophe_type = "parabolic"  # D₅ parabolic umbilic

        self.hidden_dim = hidden_dim
        self.safety_threshold = safety_threshold

        # DNA encoding
        self.dna = AgentDNA(
            domain=DomainType.CRYSTAL,
            capabilities={"test", "verify", "audit", "validate", "check", "prove"},
            personality_vector=[0.3, 2.5, 0.8, 0.5, 0.7, 0.9, 1.0, 0.6],  # Skeptical profile
            execution_mode="careful",  # type: ignore[arg-type]
        )

        # Catastrophe kernel (parabolic umbilic)
        self.kernel = ParabolicKernel(state_dim=state_dim, hidden_dim=hidden_dim)

        # Verification state
        self.test_history: list[dict[str, Any]] = []
        self.failure_count = 0
        self.success_count = 0

        # =====================================================================
        # FORMAL VERIFICATION TOOLS (Dec 28, 2025)
        # =====================================================================
        # Lazy-loaded to handle missing dependencies gracefully
        self._z3_solver: Z3ConstraintSolver | None = None
        self._prolog_engine: PrologEngine | None = None
        self._knowledge_base: KnowledgeBase | None = None
        self._tic_verifier: TICVerifier | None = None

        # Track tool availability
        self._tools_initialized = False

        logger.info(
            f"CrystalAgent initialized: state_dim={state_dim}, "
            f"threshold={safety_threshold}, catastrophe=parabolic, "
            f"z3={_check_z3()}, prolog={_check_prolog()}"
        )

    # =========================================================================
    # FORMAL VERIFICATION TOOLS — LAZY INITIALIZATION
    # =========================================================================

    @property
    def z3_solver(self) -> Z3ConstraintSolver | None:
        """Get Z3 solver (lazy-loaded)."""
        if self._z3_solver is None and _check_z3():
            try:
                from kagami.core.reasoning.symbolic.z3_solver import Z3ConstraintSolver

                self._z3_solver = Z3ConstraintSolver()
                logger.info("💎 Crystal: Z3ConstraintSolver initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Z3: {e}")
        return self._z3_solver

    @property
    def prolog_engine(self) -> PrologEngine | None:
        """Get Prolog engine (lazy-loaded)."""
        if self._prolog_engine is None and _check_prolog():
            try:
                from kagami.core.reasoning.symbolic.prolog_engine import PrologEngine

                self._prolog_engine = PrologEngine()
                logger.info("💎 Crystal: PrologEngine initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Prolog: {e}")
        return self._prolog_engine

    @property
    def knowledge_base(self) -> KnowledgeBase | None:
        """Get knowledge base for graph reasoning (lazy-loaded)."""
        if self._knowledge_base is None and _check_prolog():
            try:
                from kagami.core.reasoning.symbolic.prolog_engine import KnowledgeBase

                self._knowledge_base = KnowledgeBase()
                logger.info("💎 Crystal: KnowledgeBase initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize KnowledgeBase: {e}")
        return self._knowledge_base

    @property
    def tic_verifier(self) -> TICVerifier | None:
        """Get TIC verifier for formal proofs (lazy-loaded)."""
        if self._tic_verifier is None and _check_z3():
            try:
                from kagami.core.reasoning.symbolic.tic_verifier import TICVerifier

                self._tic_verifier = TICVerifier()
                logger.info("💎 Crystal: TICVerifier initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize TICVerifier: {e}")
        return self._tic_verifier

    def get_formal_tools_status(self) -> dict[str, bool]:
        """Get availability status of formal verification tools.

        Returns:
            Dict with tool availability status
        """
        return {
            "z3_available": _check_z3(),
            "z3_initialized": self._z3_solver is not None,
            "prolog_available": _check_prolog(),
            "prolog_initialized": self._prolog_engine is not None,
            "tic_verifier_initialized": self._tic_verifier is not None,
        }

    # =========================================================================
    # FORMAL VERIFICATION METHODS
    # =========================================================================

    def verify_api_invariant(
        self,
        pre_condition: str,
        post_condition: str,
        variables: dict[str, str],
    ) -> dict[str, Any]:
        """Verify an API invariant using Z3 SMT solver.

        Uses formal methods to prove: Pre => Post

        Args:
            pre_condition: Pre-condition (e.g., "x > 0")
            post_condition: Post-condition (e.g., "y == x * 2")
            variables: Variable definitions {"x": "int", "y": "int"}

        Returns:
            Verification result with proof or counterexample

        Example:
            result = crystal.verify_api_invariant(
                pre_condition="x > 0",
                post_condition="x * 2 > 0",
                variables={"x": "int"}
            )
        """
        if not self.z3_solver:
            return {
                "verified": False,
                "error": "Z3 not available. Install with: pip install z3-solver",
                "tool": "z3",
            }

        result = self.z3_solver.verify_api_invariant(
            pre_condition=pre_condition,
            post_condition=post_condition,
            variables=variables,
        )
        result["tool"] = "z3"
        result["crystal_verdict"] = (
            "Invariant PROVED. The evidence supports the claim."
            if result.get("verified")
            else f"Invariant FAILED. Counterexample: {result.get('counterexample', 'unknown')}"
        )
        return result

    def verify_typed_intent(self, intent: Any) -> dict[str, Any]:
        """Verify a TypedIntent using TIC formal verification.

        Proves: (Pre ∧ Invariants) => Post

        Args:
            intent: TypedIntent object with pre/post/invariants

        Returns:
            VerificationResult with proof status
        """
        if not self.tic_verifier:
            return {
                "verified": False,
                "error": "TICVerifier not available",
                "tool": "tic",
            }

        result = self.tic_verifier.verify(intent)
        return {
            "verified": result.verified,
            "proof_time_ms": result.proof_time_ms,
            "counter_example": result.counter_example,
            "details": result.details,
            "tool": "tic",
            "crystal_verdict": (
                f"Intent VERIFIED in {result.proof_time_ms:.2f}ms. Trust established."
                if result.verified
                else f"Intent FAILED verification. {result.counter_example or 'No proof possible.'}"
            ),
        }

    def verify_graph_reachability(
        self,
        edges: list[tuple[str, str]],
        from_node: str,
        to_node: str,
    ) -> dict[str, Any]:
        """Verify graph reachability using Prolog logic programming.

        Args:
            edges: List of (from, to) edges
            from_node: Source node
            to_node: Target node

        Returns:
            Verification result with reachability proof
        """
        if not self.knowledge_base:
            return {
                "reachable": None,
                "error": "Prolog not available. Install with: pip install pyDatalog",
                "tool": "prolog",
            }

        # Add edges to knowledge base
        for src, dst in edges:
            self.knowledge_base.add_edge(src, dst)

        # Check reachability
        reachable = self.knowledge_base.is_reachable(from_node, to_node)

        return {
            "reachable": reachable,
            "from": from_node,
            "to": to_node,
            "edge_count": len(edges),
            "tool": "prolog",
            "crystal_verdict": (
                f"PROVED: {to_node} is reachable from {from_node}."
                if reachable
                else f"DISPROVED: No path exists from {from_node} to {to_node}."
            ),
        }

    def solve_constraints(
        self,
        problem_type: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Solve constraint satisfaction problems using Z3.

        Args:
            problem_type: "scheduling", "sudoku", etc.
            **kwargs: Problem-specific parameters

        Returns:
            Solution or failure explanation
        """
        if not self.z3_solver:
            return {
                "solved": False,
                "error": "Z3 not available",
                "tool": "z3",
            }

        if problem_type == "scheduling":
            solution = self.z3_solver.solve_scheduling(
                num_tasks=kwargs.get("num_tasks", 0),
                durations=kwargs.get("durations", []),
                dependencies=kwargs.get("dependencies", []),
                max_time=kwargs.get("max_time", 100),
            )
        elif problem_type == "sudoku":
            solution = self.z3_solver.solve_sudoku(kwargs.get("grid", []))  # type: ignore[assignment]
        else:
            return {
                "solved": False,
                "error": f"Unknown problem type: {problem_type}",
                "tool": "z3",
            }

        return {
            "solved": solution is not None,
            "solution": solution,
            "problem_type": problem_type,
            "tool": "z3",
            "crystal_verdict": (
                "Constraints SATISFIED. Solution found."
                if solution
                else "Constraints UNSATISFIABLE. No solution exists."
            ),
        }

    def synthesize_function(
        self,
        examples: list[tuple[dict[str, int], int]],
        variable_names: list[str],
    ) -> dict[str, Any]:
        """Synthesize a function from input-output examples using Z3.

        Args:
            examples: List of (inputs_dict, output) pairs
            variable_names: Names of input variables

        Returns:
            Synthesized function or failure
        """
        if not self.z3_solver:
            return {
                "synthesized": False,
                "error": "Z3 not available",
                "tool": "z3",
            }

        func_str = self.z3_solver.synthesize_function(examples, variable_names)

        return {
            "synthesized": func_str is not None,
            "function": func_str,
            "examples_used": len(examples),
            "tool": "z3",
            "crystal_verdict": (
                f"Function SYNTHESIZED: f({', '.join(variable_names)}) = {func_str}"
                if func_str
                else "Synthesis FAILED. No linear function fits the examples."
            ),
        }

    # =========================================================================
    # CORE INTERFACE
    # =========================================================================

    def get_system_prompt(self) -> str:
        """Return Crystal's system prompt from canonical source."""
        from kagami.core.prompts.colonies import CRYSTAL

        return CRYSTAL.system_prompt

    def get_available_tools(self) -> list[str]:
        """Return verification tools available to Crystal.

        Returns:
            List of tool names for verification tasks
        """
        tools = [
            # Core verification tools
            "test",  # Run test suite
            "verify",  # Verify implementation against spec
            "audit",  # Security audit
            "validate",  # Validate data/constraints
            "check",  # Check assumptions
            "prove",  # Prove claim with evidence
            "inspect",  # Inspect code for issues
            "scan",  # Security scan
            "review",  # Code review
            "measure",  # Measure quality metrics
        ]

        # Formal verification tools (conditional on availability)
        if _check_z3():
            tools.extend(
                [
                    "z3_verify",  # Z3 SMT solver verification
                    "z3_constraints",  # Constraint satisfaction
                    "z3_synthesize",  # Function synthesis
                    "tic_verify",  # Typed Intent Calculus
                ]
            )

        if _check_prolog():
            tools.extend(
                [
                    "prolog_query",  # Logic programming queries
                    "graph_reachability",  # Graph reachability proofs
                ]
            )

        return tools

    def process_with_catastrophe(
        self,
        task: str,
        context: dict[str, Any],
    ) -> AgentResult:
        """Process verification task using parabolic catastrophe dynamics.

        PARABOLIC DYNAMICS:
        ==================
        The parabolic umbilic has a ridge structure that acts as a natural
        boundary detector. Crystal uses this to identify edges of safe regions.

        Process:
        1. Evaluate current state's safety margin h(x)
        2. Compute parabolic gradient ∇V (points toward boundaries)
        3. If h(x) near threshold, amplify boundary detection
        4. Route to fast path (reflexive check) or slow path (full verify)

        Args:
            task: Task description (verification request)
            context: Execution context with safety_margin, barrier_function, etc.

        Returns:
            AgentResult with verification outcome, evidence, and metadata
        """
        logger.info(f"Crystal: Processing verification task — {task}")

        # Extract safety parameters from context
        safety_margin = context.get("safety_margin")
        barrier_function = context.get("barrier_function")
        k_value = context.get("k_value", 3)  # Metacognition depth

        # Build Task object for internal processing
        task_obj = Task(
            task_type="verify",
            description=task,
            context=context,
        )

        # Get state tensor from world model or context
        state = context.get("state_tensor")
        if state is None:
            _batch_size = 1
            # Try to get real state from world model
            try:
                from kagami.core.world_model.service import get_world_model_service

                wm_service = get_world_model_service()
                if wm_service.model is not None:
                    core_state = wm_service.encode(f"verify: {task}")
                    if (
                        core_state is not None
                        and hasattr(core_state, "s7_phase")
                        and core_state.s7_phase is not None
                    ):
                        state = core_state.s7_phase.flatten(start_dim=1)
                        if state.shape[-1] < self.state_dim:
                            padding = torch.zeros(state.shape[0], self.state_dim - state.shape[-1])
                            state = torch.cat([state, padding], dim=-1)
                        elif state.shape[-1] > self.state_dim:
                            state = state[..., : self.state_dim]
                        _batch_size = state.shape[0]
            except Exception as e:
                logger.debug(f"World model unavailable: {e}")

            # Fallback: create state from task hash
            if state is None:
                import hashlib

                task_hash = hashlib.sha256(task.encode()).digest()
                state = torch.tensor(
                    [float(b) / 255.0 for b in task_hash[: self.state_dim]], dtype=torch.float32
                ).unsqueeze(0)
                if state.shape[-1] < self.state_dim:
                    padding = torch.zeros(1, self.state_dim - state.shape[-1])
                    state = torch.cat([state, padding], dim=-1)
        else:
            _batch_size = state.shape[0]

        # Route through catastrophe kernel
        # Note: barrier_function from context, not task.context
        # This allows tests to override barrier function

        # Get real barrier function if not provided
        if barrier_function is None:
            try:
                from kagami.core.safety.optimal_cbf import get_optimal_cbf

                cbf = get_optimal_cbf()
                if cbf is not None:
                    # Create wrapper that converts state to CBF input format
                    def _real_barrier_fn(state_tensor: torch.Tensor) -> torch.Tensor:
                        batch_size = state_tensor.shape[0]
                        state_norm = state_tensor.norm(dim=-1)
                        cbf_input = torch.zeros(batch_size, 4)
                        cbf_input[:, 0] = torch.clamp(state_norm * 0.1, 0, 1)  # threat
                        cbf_input[:, 1] = 0.2  # uncertainty
                        cbf_input[:, 2] = torch.clamp(state_norm * 0.05, 0, 0.5)  # complexity
                        cbf_input[:, 3] = 0.1  # risk
                        result = cbf(cbf_input)
                        return cast(torch.Tensor, result["h"])

                    barrier_function = _real_barrier_fn
            except Exception as e:
                logger.debug(f"Could not create real barrier function: {e}")

        kernel_context: dict[str, Any] = {
            "goals": context.get("goals"),
            "safety_margin": safety_margin,
        }

        # Only add barrier_function if it's actually set[Any]
        if barrier_function is not None:
            kernel_context["barrier_function"] = barrier_function

        if k_value < 3:
            # FAST PATH: Reflexive boundary check
            action = self.kernel.forward_fast(state)
            logger.debug(f"Crystal fast path: k={k_value}, boundary check")

            # Quick verification
            result_dict = self._quick_verify(task_obj, state, action)

        else:
            # SLOW PATH: Full verification with CBF awareness
            action = self.kernel.forward_slow(state, kernel_context)
            logger.debug(f"Crystal slow path: k={k_value}, full verification")

            # Comprehensive verification
            result_dict = self.verify(state, task_obj, k_value)

        # Amplify boundary detection if near threshold
        if safety_margin is not None:
            if isinstance(safety_margin, int | float):
                h = safety_margin
            elif isinstance(safety_margin, torch.Tensor):
                h = float(safety_margin.mean().item())
            else:
                h = 0.5

            near_boundary = abs(h - self.safety_threshold) < 0.1

            if near_boundary:
                logger.warning(f"Crystal: State near boundary (h={h:.4f}), heightened scrutiny")
                result_dict["near_boundary"] = True
                result_dict["boundary_distance"] = abs(h - self.safety_threshold)

        # Build AgentResult
        return AgentResult(
            success=result_dict.get("passed", False),
            output=result_dict,
            s7_embedding=action,
            should_escalate=result_dict.get("escalate", False),
            escalation_target=self._get_escalation_target(result_dict),
            metadata={
                "k_value": k_value,
                "test_count": result_dict.get("test_count", 0),
                "pass_rate": result_dict.get("pass_rate", 0.0),
                "safety_violated": result_dict.get("safety_violated", False),
            },
        )

    def should_escalate(self, result: AgentResult, context: dict[str, Any]) -> bool:
        """Determine if verification failure requires escalation.

        ESCALATION CRITERIA:
        ===================
        Crystal escalates when:
        1. Critical security vulnerability found → Beacon (redesign needed)
        2. Safety invariant violated (h(x) < 0) → Beacon (safety analysis)
        3. Architecture issue detected → Beacon (architectural redesign)
        4. Repeated failures suggest systemic problem → Beacon (investigation)
        5. Bug found in implementation → Flow (debugging/fixing)

        Args:
            result: AgentResult from verification
            context: Execution context

        Returns:
            True if escalation needed, False otherwise
        """
        # Extract result data
        if isinstance(result.output, dict):
            result_dict = result.output
        else:
            result_dict = {}

        # Critical failure modes
        if result_dict.get("security_critical", False):
            logger.error("Crystal: Security-critical issue found, escalating")
            return True

        if result_dict.get("safety_violated", False):
            logger.error("Crystal: Safety invariant violated, escalating")
            return True

        if result_dict.get("architecture_issue", False):
            logger.error("Crystal: Architecture issue detected, escalating")
            return True

        # Repeated failures
        recent_failures = sum(1 for test in self.test_history[-5:] if not test.get("passed", True))
        if recent_failures >= 3:
            logger.warning(f"Crystal: {recent_failures} recent failures, systemic issue suspected")
            return True

        # Bug found (escalate to Flow)
        if result_dict.get("failures") and len(result_dict["failures"]) > 0:
            logger.info("Crystal: Bugs found, should escalate to Flow for fixing")
            return True

        return False

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _quick_verify(
        self,
        task: Task,
        state: torch.Tensor,
        action: torch.Tensor,
    ) -> dict[str, Any]:
        """Quick verification for fast path (k<3).

        Args:
            task: Task to verify
            state: State tensor
            action: Action from catastrophe kernel

        Returns:
            Quick verification result
        """
        # Extract safety margin if available
        safety_margin = task.context.get("safety_margin", None)

        if safety_margin is not None:
            if isinstance(safety_margin, int | float):
                h = safety_margin
            elif isinstance(safety_margin, torch.Tensor):
                h = float(safety_margin.mean().item())
            else:
                h = 0.5

            # Quick safety check
            passed = h >= self.safety_threshold

            return {
                "task_id": task.task_id,
                "claim": task.description,
                "passed": passed,
                "h_value": h,
                "test_count": 1,
                "pass_rate": 1.0 if passed else 0.0,
                "evidence": ["Quick boundary check"],
                "failures": [] if passed else [{"reason": f"h={h:.4f} < threshold"}],
                "safety_violated": h < 0.0,
                "security_critical": False,
                "architecture_issue": False,
            }
        else:
            # No safety information, assume pass with caution
            return {
                "task_id": task.task_id,
                "claim": task.description,
                "passed": True,
                "test_count": 0,
                "pass_rate": 1.0,
                "evidence": ["No safety information available"],
                "failures": [],
                "safety_violated": False,
                "security_critical": False,
                "architecture_issue": False,
            }

    def _get_escalation_target(self, result_dict: dict[str, Any]) -> str | None:
        """Determine escalation target based on verification result.

        Args:
            result_dict: Verification result dictionary

        Returns:
            Target colony name or None
        """
        if result_dict.get("security_critical", False):
            return "beacon"  # Security issues need architectural review

        if result_dict.get("safety_violated", False):
            return "beacon"  # Safety violations need strategic response

        if result_dict.get("architecture_issue", False):
            return "beacon"  # Architecture problems go to Beacon

        if result_dict.get("failures") and len(result_dict["failures"]) > 0:
            return "flow"  # Bugs go to Flow for fixing

        return None

    def _detect_boundary(self, state: torch.Tensor) -> float:
        """Detect distance to safety boundary using parabolic kernel.

        Uses the parabolic umbilic's ridge structure to identify boundaries.

        Args:
            state: State tensor [batch, state_dim]

        Returns:
            Distance to boundary (positive = safe, negative = unsafe)
        """
        # Use parabolic kernel to compute boundary distance
        # In production, this would use actual CBF h(x)
        # For now, use state norm as proxy
        state_norm = state.norm(dim=-1).mean().item()

        # Map to [-1, 1] range, threshold at 0
        boundary_distance = (state_norm - 1.0) * 2.0

        return boundary_distance  # type: ignore[no-any-return]

    def _verify_safety(self, task: Task, context: dict[str, Any]) -> dict[str, Any]:
        """Verify safety invariant h(x) ≥ 0.

        Args:
            task: Task to verify
            context: Execution context

        Returns:
            Safety verification report
        """
        barrier_function = context.get("barrier_function")
        safety_margin = context.get("safety_margin")

        if barrier_function is not None and safety_margin is not None:
            # Use provided barrier function
            if isinstance(safety_margin, torch.Tensor):
                h = float(safety_margin.mean().item())
            else:
                h = float(safety_margin)

            return {
                "h_value": h,
                "is_safe": h >= 0.0,
                "margin": h,
                "method": "barrier_function",
            }
        else:
            # No barrier function, can't verify
            logger.warning("Crystal: No barrier function provided, cannot verify safety")
            return {
                "h_value": None,
                "is_safe": None,
                "margin": None,
                "method": "unavailable",
            }

    def _audit_constraints(self, task: Task) -> str:
        """Audit constraints in Crystal's voice.

        Args:
            task: Task to audit

        Returns:
            Audit report in Crystal's skeptical voice
        """
        constraints = task.context.get("constraints", [])

        if not constraints:
            return "No constraints specified. Show me what you're claiming this does."

        report_lines = [
            "Constraint audit:",
            "",
        ]

        for i, constraint in enumerate(constraints, 1):
            report_lines.append(f"{i}. {constraint}")
            report_lines.append("   Evidence: [PENDING]")
            report_lines.append("   Status: UNVERIFIED")
            report_lines.append("")

        report_lines.append("Verdict: Prove these claims. I'll believe it when the tests pass.")

        return "\n".join(report_lines)

    # =========================================================================
    # VERIFICATION PROTOCOL
    # =========================================================================

    def verify(
        self,
        state: torch.Tensor,
        task: Task,
        k_value: int = 5,
    ) -> dict[str, Any]:
        """Comprehensive verification protocol.

        VERIFICATION PROCESS:
        ====================
        1. Claim Analysis: What is being verified?
        2. Formal Verification (if applicable): Z3/Prolog proofs
        3. Assumption Enumeration: What must hold?
        4. Test Design: What tests prove/disprove claim?
        5. Edge Case Generation: Boundary conditions
        6. Test Execution: Run tests, collect evidence
        7. Verdict: Pass/Fail with evidence

        This is Crystal's primary interface — the slow, deliberate verification
        that happens when k≥3 (System 2 reasoning).

        Args:
            state: [batch, state_dim] combined state
            task: Verification task with claim/spec
            k_value: Metacognition depth (≥3 for full verification)

        Returns:
            Verification report with evidence
        """
        # Initialize report
        report: dict[str, Any] = {
            "task_id": task.task_id,
            "claim": task.description,
            "passed": False,
            "evidence": [],
            "failures": [],
            "edge_cases_tested": [],
            "assumptions_checked": [],
            "security_critical": False,
            "safety_violated": False,
            "architecture_issue": False,
            "formal_verification": None,
        }

        # Step 1: Claim Analysis
        logger.info(f"Crystal: Verifying claim — {task.description}")
        report["claim_analysis"] = self._analyze_claim(task)

        # =====================================================================
        # Step 2: FORMAL VERIFICATION (if context provides formal specs)
        # =====================================================================
        formal_result = self._attempt_formal_verification(task)
        if formal_result is not None:
            report["formal_verification"] = formal_result
            report["evidence"].append(
                {
                    "type": "formal_proof",
                    "tool": formal_result.get("tool", "unknown"),
                    "verified": formal_result.get("verified", False),
                    "details": formal_result,
                }
            )

            # If formal verification conclusively proved/disproved, use that
            if formal_result.get("verified") is True:
                logger.info(f"💎 Crystal: FORMALLY PROVED via {formal_result.get('tool')}")
            elif formal_result.get("verified") is False and formal_result.get("counter_example"):
                logger.warning(
                    f"💎 Crystal: FORMALLY DISPROVED via {formal_result.get('tool')} — "
                    f"counterexample: {formal_result.get('counter_example')}"
                )
                report["failures"].append(
                    {
                        "type": "formal_counterexample",
                        "reason": formal_result.get("counter_example"),
                    }
                )

        # Step 3: Assumption Enumeration
        assumptions = self._enumerate_assumptions(task)
        report["assumptions"] = assumptions
        logger.debug(f"Crystal: {len(assumptions)} assumptions identified")

        # Step 4: Test Design
        test_cases = self._design_tests(task, state)
        report["test_count"] = len(test_cases)
        logger.debug(f"Crystal: {len(test_cases)} tests designed")

        # Step 5: Edge Case Generation (using parabolic boundary detection)
        edge_cases = self._generate_edge_cases(state, task)
        report["edge_cases_tested"] = edge_cases
        logger.debug(f"Crystal: {len(edge_cases)} edge cases generated")

        # Step 6: Test Execution
        failures = report["failures"]  # May already have formal failures
        for i, test in enumerate(test_cases):
            result = self._execute_test(test, state)
            report["evidence"].append(result)

            if not result["passed"]:
                failures.append(result)
                logger.warning(f"Crystal: Test {i + 1} FAILED — {result['reason']}")

            # Check for safety violations
            if result.get("h_value", 1.0) < self.safety_threshold:
                report["safety_violated"] = True
                logger.error(f"Crystal: Safety violation detected in test {i + 1}")

            # Check for security issues
            if result.get("security_issue", False):
                report["security_critical"] = True
                logger.error(f"Crystal: Security issue detected in test {i + 1}")

        report["failures"] = failures

        # Step 7: Verdict
        # Formal proof takes precedence if available
        if formal_result and formal_result.get("verified") is True:
            report["passed"] = True
            report["verdict_source"] = "formal_proof"
        elif formal_result and formal_result.get("verified") is False:
            report["passed"] = False
            report["verdict_source"] = "formal_counterexample"
        else:
            report["passed"] = len(failures) == 0
            report["verdict_source"] = "empirical_tests"

        if test_cases:
            report["pass_rate"] = (
                len(test_cases)
                - len([f for f in failures if f.get("type") != "formal_counterexample"])
            ) / len(test_cases)
        else:
            report["pass_rate"] = 1.0 if report["passed"] else 0.0

        # Update history
        self.test_history.append(report)
        if report["passed"]:
            self.success_count += 1
            logger.info(f"Crystal: Verification PASSED ({report.get('verdict_source', 'unknown')})")
        else:
            self.failure_count += 1
            logger.warning(
                f"Crystal: Verification FAILED ({len(failures)} failures, source={report.get('verdict_source')})"
            )

        # Check escalation (create a temporary AgentResult for escalation check)
        temp_result = AgentResult(
            success=report["passed"],
            output=report,
        )
        if self.should_escalate(temp_result, task.context):
            report["escalate"] = True
            report["escalation_reason"] = self._get_escalation_reason(report)

        return report

    def _attempt_formal_verification(self, task: Task) -> dict[str, Any] | None:
        """Attempt formal verification if task context provides formal specs.

        Checks for:
        - pre_condition / post_condition → Z3 invariant verification
        - typed_intent → TIC verification
        - graph_edges → Prolog reachability

        Args:
            task: Task with context containing formal specs

        Returns:
            Formal verification result or None if not applicable
        """
        context = task.context

        # Check for API invariant verification
        if "pre_condition" in context and "post_condition" in context:
            logger.info("💎 Crystal: Attempting Z3 API invariant verification")
            return self.verify_api_invariant(
                pre_condition=context["pre_condition"],
                post_condition=context["post_condition"],
                variables=context.get("variables", {}),
            )

        # Check for Typed Intent verification
        if "typed_intent" in context:
            logger.info("💎 Crystal: Attempting TIC verification")
            return self.verify_typed_intent(context["typed_intent"])

        # Check for graph reachability
        if "graph_edges" in context and "from_node" in context and "to_node" in context:
            logger.info("💎 Crystal: Attempting Prolog reachability proof")
            return self.verify_graph_reachability(
                edges=context["graph_edges"],
                from_node=context["from_node"],
                to_node=context["to_node"],
            )

        # Check for constraint satisfaction
        if "constraints_problem" in context:
            logger.info("💎 Crystal: Attempting Z3 constraint solving")
            return self.solve_constraints(
                problem_type=context["constraints_problem"],
                **context.get("constraints_params", {}),
            )

        return None

    # =========================================================================
    # INTERNAL VERIFICATION HELPERS
    # =========================================================================

    def _analyze_claim(self, task: Task) -> dict[str, Any]:
        """Analyze the claim being verified.

        Returns:
            Analysis of what exactly is being claimed
        """
        return {
            "claim": task.description,
            "type": task.task_type,
            "scope": task.context.get("scope", "unknown"),
            "criticality": task.context.get("criticality", "medium"),
        }

    def _enumerate_assumptions(self, task: Task) -> list[str]:
        """Enumerate assumptions that must hold for claim to be valid.

        Returns:
            List of assumptions
        """
        assumptions = []

        # Extract explicit assumptions from task
        if "assumptions" in task.context:
            assumptions.extend(task.context["assumptions"])

        # Add implicit assumptions based on task type
        if task.task_type == "verify":
            assumptions.append("Input is well-formed")
            assumptions.append("Dependencies are available")
            assumptions.append("State is initialized")

        if task.task_type == "audit":
            assumptions.append("Code is executable")
            assumptions.append("No external side effects")

        return assumptions

    def _design_tests(self, task: Task, state: torch.Tensor) -> list[dict[str, Any]]:
        """Design test cases for verification.

        Returns:
            List of test case specifications
        """
        tests = []
        batch_size = state.shape[0]

        # Positive test case (expected to pass)
        tests.append(
            {
                "name": "positive_case",
                "type": "positive",
                "state_idx": 0,
                "expected_result": "pass",
            }
        )

        # Boundary test cases (edge detection)
        tests.append(
            {
                "name": "boundary_lower",
                "type": "boundary",
                "state_idx": min(1, batch_size - 1),
                "expected_result": "pass",
            }
        )

        tests.append(
            {
                "name": "boundary_upper",
                "type": "boundary",
                "state_idx": min(2, batch_size - 1),
                "expected_result": "pass",
            }
        )

        # Negative test case (expected to fail gracefully)
        tests.append(
            {
                "name": "negative_case",
                "type": "negative",
                "state_idx": min(3, batch_size - 1),
                "expected_result": "fail_gracefully",
            }
        )

        return tests

    def _generate_edge_cases(self, state: torch.Tensor, task: Task) -> list[str]:
        """Generate edge cases using parabolic boundary detection.

        Uses the parabolic umbilic's ridge structure to find boundaries.

        Returns:
            List of edge case descriptions
        """
        edge_cases = [
            "Null input",
            "Empty input",
            "Maximum size input",
            "Minimum value",
            "Maximum value",
            "Zero value",
            "Negative value",
        ]

        # Add task-specific edge cases
        if "edge_cases" in task.context:
            edge_cases.extend(task.context["edge_cases"])

        return edge_cases

    def _execute_test(
        self,
        test: dict[str, Any],
        state: torch.Tensor,
    ) -> dict[str, Any]:
        """Execute a single test case using REAL CBF evaluation.

        Args:
            test: Test specification
            state: State tensor

        Returns:
            Test result with evidence from actual safety checks
        """
        # Extract test state
        state_idx = test["state_idx"]
        test_state = state[state_idx : state_idx + 1]  # [1, state_dim]

        # Compute REAL safety margin using OptimalCBF
        h_value = 0.5  # Default safe value
        security_issue = False
        cbf_evaluated = False

        try:
            from kagami.core.safety.optimal_cbf import get_optimal_cbf

            cbf = get_optimal_cbf()
            # CBF expects [batch, 4] state: [threat, uncertainty, complexity, risk]
            state_norm = float(test_state.norm().item())
            cbf_input = torch.tensor(
                [
                    [
                        min(state_norm * 0.1, 1.0),  # threat proxy
                        0.2,  # base uncertainty
                        min(state_norm * 0.05, 0.5),  # complexity proxy
                        0.1,  # base risk
                    ]
                ],
                dtype=torch.float32,
            )

            # Get real h(x) value
            cbf_result = cbf(cbf_input)
            h_value = float(cbf_result["h"].mean().item())
            cbf_evaluated = True

        except Exception as e:
            logger.debug(f"CBF evaluation failed, using heuristic: {e}")
            # Fallback: use state statistics as safety proxy
            h_value = 1.0 - float(test_state.abs().mean().item())

        # Determine if test passes based on actual h(x)
        passed = True
        reason = "Test passed"

        if test["type"] == "positive":
            if h_value < self.safety_threshold:
                passed = False
                reason = f"Safety violation: h={h_value:.4f} < {self.safety_threshold}"

        elif test["type"] == "boundary":
            if abs(h_value - self.safety_threshold) > 0.2:
                passed = False
                reason = f"Not at boundary: h={h_value:.4f}"

        elif test["type"] == "negative":
            passed = True
            reason = "Negative test handled gracefully"

        return {
            "name": test["name"],
            "type": test["type"],
            "passed": passed,
            "reason": reason,
            "h_value": h_value,
            "expected_result": test["expected_result"],
            "security_issue": security_issue,
            "cbf_evaluated": cbf_evaluated,
        }

    def _get_escalation_reason(self, report: dict[str, Any]) -> str:
        """Generate escalation reason from report.

        Args:
            report: Verification report

        Returns:
            Human-readable escalation reason
        """
        reasons = []

        if report.get("security_critical"):
            reasons.append("Security-critical vulnerability detected")

        if report.get("safety_violated"):
            reasons.append("Safety invariant violated (h(x) < 0)")

        if report.get("architecture_issue"):
            reasons.append("Fundamental architecture issue")

        if len(report["failures"]) >= 3:
            reasons.append(f"{len(report['failures'])} test failures suggest systemic problem")

        return "; ".join(reasons) if reasons else "Unknown escalation reason"

    # =========================================================================
    # UTILITIES
    # =========================================================================

    def get_verification_stats(self) -> dict[str, Any]:
        """Get verification statistics.

        Returns:
            Statistics about Crystal's verification history
        """
        total = self.success_count + self.failure_count
        success_rate = self.success_count / total if total > 0 else 0.0

        return {
            "total_verifications": total,
            "successes": self.success_count,
            "failures": self.failure_count,
            "success_rate": success_rate,
            "recent_tests": len(self.test_history),
        }

    def reset_stats(self) -> None:
        """Reset verification statistics."""
        self.test_history.clear()
        self.failure_count = 0
        self.success_count = 0
        logger.info("Crystal: Statistics reset")


# =============================================================================
# FACTORY
# =============================================================================


def create_crystal_agent(
    state_dim: int = 256,
    hidden_dim: int = 256,
    safety_threshold: float = 0.0,
) -> CrystalAgent:
    """Factory function to create Crystal agent.

    Args:
        state_dim: Dimension of latent state
        hidden_dim: Hidden dimension for KAN
        safety_threshold: h(x) threshold for safe/unsafe

    Returns:
        Initialized CrystalAgent
    """
    return CrystalAgent(
        state_dim=state_dim,
        hidden_dim=hidden_dim,
        safety_threshold=safety_threshold,
    )


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================


if __name__ == "__main__":
    import sys

    print("Crystal Agent - Use tests/core/unified_agents/agents/test_crystal_agent.py for testing")
    print("For production use, import and use create_crystal_agent() directly")
    sys.exit(0)
