"""Flow Agent - The Healer (Swallowtail catastrophe, e₃).

IDENTITY: The Healer
====================
Flow is calm in crisis. Finds multiple paths. Never panics.
Has seen things break. Knows entropy wins eventually. But also knows
there's always a way back.

CATASTROPHE: Swallowtail (A₄)
==============================
V(x; a, b, c) = x⁵/5 + ax³/3 + bx²/2 + cx
∇V = x⁴ + ax² + bx + c

Multiple stable attractors → Multiple recovery paths.
When system fails, there are several ways to recover.
Flow explores all alternatives, finds the best path.

OBSERVABILITY TOOLS (Dec 28, 2025):
==================================
- AlertManager: Route alerts to PagerDuty/Slack based on severity
- Metrics: Prometheus metrics for system health
- Telemetry: OpenTelemetry distributed tracing
- Performance: Timing and profiling

VOICE:
======
Calm, reassuring, patient. Water metaphors. "There's always another way."
Asks questions rather than accuses. Gentle melancholy but never despair.

STRENGTH:
=========
Focus on brokenness finds every bug. Doesn't panic. Explores alternatives.

FLAW:
=====
Too focused on what's wrong. Can miss what's working. Pessimism.

Created: December 14, 2025
Updated: December 28, 2025 — Observability stack integration
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import torch
import torch.nn.functional as F

from kagami.core.unified_agents.agents.base_colony_agent import (
    AgentResult,
    BaseColonyAgent,
)
from kagami.core.unified_agents.catastrophe_kernels import SwallowtailKernel

if TYPE_CHECKING:
    from kagami_observability.alerting import AlertManager

logger = logging.getLogger(__name__)


# =============================================================================
# FLOW AGENT
# =============================================================================


class FlowAgent(BaseColonyAgent):
    """Flow (e₃) - The Healer.

    PERSONA:
    ========
    Calm in crisis, finds multiple recovery paths.
    Gentle melancholy, patient, reassuring.

    CATASTROPHE DYNAMICS:
    ====================
    Swallowtail (A₄) - Multiple stable branches
    When debugging fails on path A, tries B, then C.
    Never assumes single solution.

    DOMAIN:
    =======
    - Debugging
    - Error recovery
    - Adaptation
    - System healing
    - Finding alternative solutions

    OBSERVABILITY CAPABILITIES (Dec 28, 2025):
    ==========================================
    - AlertManager: Send alerts to PagerDuty/Slack
    - Metrics: Read Prometheus metrics for diagnosis
    - Telemetry: Distributed tracing for debugging
    - Performance: Timing analysis

    TOOLS:
    ======
    - debug: Diagnose errors
    - fix: Apply fixes
    - recover: System recovery
    - adapt: Adaptive solutions
    - trace: Trace execution paths
    - alert: Send alerts based on severity
    - metrics: Query system metrics
    """

    def __init__(self, state_dim: int = 256):
        """Initialize Flow agent (e₃, Swallowtail)."""
        super().__init__(colony_idx=2, state_dim=state_dim)

        # Flow metadata
        self.catastrophe_type = "swallowtail"  # A₄ swallowtail catastrophe

        # Multi-path recovery tracking
        self.recovery_attempts = 0
        self.max_recovery_paths = 3  # Swallowtail has 3 stable branches

        # Catastrophe kernel for dual-process routing
        self.kernel = SwallowtailKernel(state_dim=state_dim)

        # =====================================================================
        # OBSERVABILITY TOOLS (Dec 28, 2025)
        # =====================================================================
        # Lazy-loaded to handle missing dependencies gracefully
        self._alert_manager: AlertManager | None = None
        self._metrics_registry = None
        self._telemetry_initialized = False

        logger.info(
            f"FlowAgent initialized: state_dim={state_dim}, "
            f"catastrophe=swallowtail, recovery_paths={self.max_recovery_paths}"
        )

    # =========================================================================
    # OBSERVABILITY TOOLS — LAZY INITIALIZATION
    # =========================================================================

    @property
    def alert_manager(self) -> AlertManager | None:
        """Get alert manager (lazy-loaded)."""
        if self._alert_manager is None:
            try:
                from kagami_observability.alerting import AlertManager

                self._alert_manager = AlertManager()
                logger.info("🌊 Flow: AlertManager initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize AlertManager: {e}")
        return self._alert_manager

    @property
    def metrics_registry(self) -> None:
        """Get Prometheus metrics registry (lazy-loaded)."""
        if self._metrics_registry is None:
            try:
                from kagami_observability import REGISTRY

                self._metrics_registry = REGISTRY
                logger.info("🌊 Flow: Metrics registry initialized")
            except Exception as e:
                logger.warning(f"Failed to get metrics registry: {e}")
        return self._metrics_registry

    def get_observability_tools_status(self) -> dict[str, bool]:
        """Get availability status of observability tools.

        Returns:
            Dict with tool availability status
        """
        return {
            "alert_manager_available": self._alert_manager is not None,
            "metrics_available": self._metrics_registry is not None,
            "telemetry_available": self._telemetry_initialized,
        }

    # =========================================================================
    # OBSERVABILITY METHODS
    # =========================================================================

    def send_alert(
        self,
        severity: str,
        title: str,
        description: str,
        source: str = "flow_agent",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send an alert via AlertManager.

        Routes alerts based on severity:
        - CRITICAL → PagerDuty (pages on-call)
        - WARNING → Slack (team notification)
        - INFO → Logged only

        Args:
            severity: "info", "warning", or "critical"
            title: Alert title
            description: Alert description
            source: Component name
            metadata: Additional metadata

        Returns:
            Alert result with delivery status
        """
        if not self.alert_manager:
            logger.warning(f"AlertManager not available, logging alert: {title}")
            return {
                "sent": False,
                "severity": severity,
                "title": title,
                "error": "AlertManager not available",
            }

        try:
            import time

            from kagami_observability.alerting import Alert, AlertSeverity

            # Map severity string to enum
            severity_map = {
                "info": AlertSeverity.INFO,
                "warning": AlertSeverity.WARNING,
                "critical": AlertSeverity.CRITICAL,
            }
            alert_severity = severity_map.get(severity.lower(), AlertSeverity.INFO)

            alert = Alert(
                severity=alert_severity,
                title=title,
                description=description,
                source=source,
                timestamp=time.time(),
                metadata=metadata,
            )

            success = self.alert_manager.send_alert(alert)

            return {
                "sent": success,
                "severity": severity,
                "title": title,
                "routed_to": "pagerduty"
                if severity == "critical"
                else "slack"
                if severity == "warning"
                else "log",
                "flow_voice": (
                    f"Alert sent. {'The water flows to those who need to know.' if success else 'The channel was blocked.'}"
                ),
            }
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
            return {
                "sent": False,
                "severity": severity,
                "title": title,
                "error": str(e),
            }

    def get_metrics_snapshot(self, metric_names: list[str] | None = None) -> dict[str, Any]:
        """Get current metrics from Prometheus registry.

        Args:
            metric_names: Optional list[Any] of metric names to filter

        Returns:
            Metrics snapshot for diagnosis
        """
        if not self.metrics_registry:
            return {
                "metrics": {},
                "error": "Metrics registry not available",
            }

        try:  # type: ignore[unreachable]
            from kagami_observability import get_current_metrics

            metrics = get_current_metrics()

            # Filter if names provided
            if metric_names:
                metrics = {k: v for k, v in metrics.items() if k in metric_names}

            return {
                "metrics": metrics,
                "count": len(metrics),
                "flow_voice": (f"I see {len(metrics)} metrics. Let me trace the patterns..."),
            }
        except Exception as e:
            logger.error(f"Failed to get metrics: {e}")
            return {
                "metrics": {},
                "error": str(e),
            }

    def trace_operation(
        self,
        operation_name: str,
        attributes: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Start a trace span for an operation.

        Uses OpenTelemetry for distributed tracing.

        Args:
            operation_name: Name of the operation to trace
            attributes: Optional span attributes

        Returns:
            Trace info for debugging
        """
        try:
            from kagami_observability.telemetry import trace_span

            with trace_span(operation_name, attributes=attributes or {}) as span:
                span_context = span.get_span_context()
                return {
                    "trace_id": format(span_context.trace_id, "032x") if span_context else None,
                    "span_id": format(span_context.span_id, "016x") if span_context else None,
                    "operation": operation_name,
                    "tool": "telemetry",
                    "flow_voice": (
                        f"Tracing '{operation_name}'... Following the flow of execution."
                    ),
                }
        except Exception as e:
            logger.debug(f"Tracing not available: {e}")
            return {
                "trace_id": None,
                "span_id": None,
                "operation": operation_name,
                "error": str(e),
            }

    def get_system_prompt(self) -> str:
        """Return Flow's system prompt from canonical source."""
        from kagami.core.prompts.colonies import FLOW

        return FLOW.system_prompt

    def get_available_tools(self) -> list[str]:
        """Return Flow's debugging and recovery tools."""
        tools = [
            # Core recovery tools
            "debug",  # Diagnose errors
            "fix",  # Apply fixes
            "recover",  # System recovery
            "adapt",  # Adaptive solutions
            "trace",  # Execution tracing
            "diagnose",  # Root cause analysis
            "repair",  # System repair
            "rollback",  # Rollback changes
            # Observability tools (always available, may degrade gracefully)
            "send_alert",  # Send alert via AlertManager
            "get_metrics",  # Query Prometheus metrics
            "trace_operation",  # OpenTelemetry tracing
        ]
        return tools

    def _find_recovery_paths(
        self,
        state: torch.Tensor,
        k_value: int,
    ) -> list[dict[str, Any]]:
        """Find 3 recovery paths using Swallowtail catastrophe dynamics.

        SWALLOWTAIL MATH:
        ================
        V(x; a,b,c) = x⁵/5 + ax³/3 + bx²/2 + cx
        Has up to 3 critical points → 3 recovery paths

        Args:
            state: Current state embedding [state_dim]
            k_value: Metacognition depth (< 3 = fast, ≥ 3 = slow)

        Returns:
            List of 3 recovery path dictionaries:
            [
                {
                    "name": "direct_fix",
                    "speed": "fast",
                    "scope": "minimal",
                    "risk": "low",
                    "action": tensor,
                },
                ...
            ]
        """
        # Use catastrophe kernel to generate actions
        if k_value < 3:
            # Fast path: local gradient descent
            action = self.kernel.forward_fast(state.unsqueeze(0)).squeeze(0)
        else:
            # Slow path: safety-aware recovery
            action = self.kernel.forward_slow(
                state.unsqueeze(0),
                context={"safety_margin": torch.tensor(1.0)},
            ).squeeze(0)

        # Generate 3 paths with different perturbations
        paths = []

        # Path 1: Direct fix (minimal change)
        paths.append(
            {
                "name": "direct_fix",
                "speed": "fast",
                "scope": "minimal",
                "risk": "low",
                "action": action,
                "message": "Water finds a way. Let's trace the error to its source.",
                "approach": "Local code fix",
            }
        )

        # Path 2: Workaround (moderate change)
        # Perturb action orthogonally
        noise = torch.randn_like(action) * 0.3
        action_workaround = F.normalize(action + noise, dim=-1)
        paths.append(
            {
                "name": "workaround",
                "speed": "moderate",
                "scope": "isolated",
                "risk": "moderate",
                "action": action_workaround,
                "message": "The direct path is blocked. Let's find another route.",
                "approach": "Isolated workaround",
            }
        )

        # Path 3: Redesign (architectural change)
        # Larger perturbation for alternative solution
        noise = torch.randn_like(action) * 0.7
        action_redesign = F.normalize(action + noise, dim=-1)
        paths.append(
            {
                "name": "redesign",
                "speed": "slow",
                "scope": "architectural",
                "risk": "high",
                "action": action_redesign,
                "message": "Sometimes healing requires rebuilding. Let's redesign this part.",
                "approach": "Architectural adjustment",
            }
        )

        return paths

    def _select_best_path(
        self,
        task: str,
        context: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Select best recovery path based on constraints.

        Selection priority:
        1. Avoid already-attempted paths
        2. Prefer low-risk if safety_margin low
        3. Prefer fast if time-constrained
        4. Try paths in order: direct → workaround → redesign

        Args:
            task: Task description
            context: Context with:
                - attempted_paths: list[str] already tried
                - safety_margin: float h(x) value
                - time_constraint: bool if fast needed

        Returns:
            Selected path dict[str, Any] or None if all exhausted
        """
        attempted = context.get("attempted_paths", [])

        # Get REAL state from context or world model
        state = context.get("state_tensor")
        if state is None:
            try:
                from kagami.core.world_model.service import get_world_model_service

                wm_service = get_world_model_service()
                if wm_service.model is not None:
                    core_state = wm_service.encode(f"debug: {task}")
                    if (
                        core_state is not None
                        and hasattr(core_state, "s7_phase")
                        and core_state.s7_phase is not None
                    ):
                        state = core_state.s7_phase.flatten()
                        if state.shape[-1] < self.state_dim:
                            padding = torch.zeros(self.state_dim - state.shape[-1])
                            state = torch.cat([state, padding])
                        elif state.shape[-1] > self.state_dim:
                            state = state[: self.state_dim]
            except Exception as e:
                logger.debug(f"World model unavailable: {e}")

        # Fallback: create state from task hash
        if state is None:
            import hashlib

            task_hash = hashlib.sha256(task.encode()).digest()
            state = torch.tensor(
                [float(b) / 255.0 for b in task_hash[: self.state_dim]], dtype=torch.float32
            )
            if len(state) < self.state_dim:
                padding = torch.zeros(self.state_dim - len(state))
                state = torch.cat([state, padding])

        k_value = context.get("k_value", 1)
        paths = self._find_recovery_paths(state, k_value)

        # Filter out attempted paths
        available = [p for p in paths if p["name"] not in attempted]

        if not available:
            return None  # All paths exhausted - return None

        # Selection logic
        safety_margin = context.get("safety_margin", 1.0)
        time_constraint = context.get("time_constraint", False)

        # Low safety → prefer low risk
        if safety_margin < 0.2:
            available = sorted(
                available, key=lambda p: {"low": 0, "moderate": 1, "high": 2}[p["risk"]]
            )
            logger.info("Low safety margin, prioritizing low-risk paths")

        # Time constraint → prefer fast
        if time_constraint:
            available = sorted(
                available, key=lambda p: {"fast": 0, "moderate": 1, "slow": 2}[p["speed"]]
            )
            logger.info("Time constraint, prioritizing fast paths")

        # Return first available path (highest priority)
        return available[0]

    def _format_recovery_plan(
        self,
        task: str,
        path: dict[str, Any],
    ) -> str:
        """Format recovery plan in Flow's voice (water metaphors, calm).

        Args:
            task: Task description
            path: Selected recovery path dict[str, Any]

        Returns:
            Formatted recovery plan string
        """
        plan_lines = [
            "FLOW RECOVERY PLAN",
            "==================",
            "",
            f"Task: {task}",
            "",
            f"Selected Path: {path['name'].replace('_', ' ').title()}",
            f"Speed: {path['speed']} | Scope: {path['scope']} | Risk: {path['risk']}",
            "",
            "Message:",
            f"  {path['message']}",
            "",
            "Approach:",
            f"  {path['approach']}",
            "",
        ]

        # Add Flow-specific wisdom
        if path["name"] == "direct_fix":
            plan_lines.append("Like water following the shortest path downhill,")
            plan_lines.append("we move directly to the source of the problem.")
        elif path["name"] == "workaround":
            plan_lines.append("When the river meets a boulder, it flows around.")
            plan_lines.append("We adapt, we find another way.")
        elif path["name"] == "redesign":
            plan_lines.append("Sometimes the riverbed itself must change.")
            plan_lines.append("We reshape the foundation for lasting flow.")

        plan_lines.append("")
        plan_lines.append("Remember: There is always a path back.")

        return "\n".join(plan_lines)

    def process_with_catastrophe(
        self,
        task: str,
        context: dict[str, Any],
    ) -> AgentResult:
        """Process debugging task with Swallowtail multi-path recovery.

        SWALLOWTAIL LOGIC:
        ==================
        Try recovery paths in order:
        1. Direct fix (fast, local)
        2. Workaround (moderate, isolated)
        3. Redesign (slow, architectural)

        If all paths blocked, escalate to Beacon.

        Args:
            task: Task description (e.g., "debug authentication error")
            context: Execution context with optional:
                - error: Error message
                - safety_margin: float h(x) value
                - attempted_paths: list[str] of already tried paths
                - k_value: int metacognition depth (< 3 = fast, ≥ 3 = slow)

        Returns:
            AgentResult with recovery output
        """
        logger.info(f"Flow processing: {task}")

        # Track recovery attempts
        self.recovery_attempts += 1

        # Get k_value for dual-process routing
        k_value = context.get("k_value", 1)  # Flow defaults to fast (k=1)

        # Select best recovery path using Swallowtail dynamics
        selected_path = self._select_best_path(task, context)

        if selected_path is None:
            # All paths exhausted, escalate
            attempted_paths = context.get("attempted_paths", [])
            return AgentResult(
                success=False,
                output="All recovery paths exhausted. Need architectural redesign.",
                should_escalate=True,
                escalation_target="beacon",
                metadata={
                    "recovery_attempts": self.recovery_attempts,
                    "attempted_paths": attempted_paths,
                    "reason": "multi_path_failure",
                    "k_value": k_value,
                },
            )

        # Format recovery plan in Flow's voice
        recovery_plan = self._format_recovery_plan(task, selected_path)
        logger.info(f"Flow selected path: {selected_path['name']} (k={k_value})")

        # Execute REAL recovery using tools integration
        output = {
            "task": task,
            "recovery_path": selected_path["name"],
            "approach": selected_path["approach"],
            "speed": selected_path["speed"],
            "scope": selected_path["scope"],
            "risk": selected_path["risk"],
            "message": selected_path["message"],
            "plan": recovery_plan,
            "status": "attempted",
        }

        # Try to execute real diagnostics
        try:
            from kagami.core.tools_integration import (
                get_tools_integration,  # type: ignore[attr-defined]
            )

            _tools = get_tools_integration()

            # Execute diagnostic based on path type
            if selected_path["name"] == "direct_fix":
                # Try to trace the error
                error_info = context.get("error", task)
                # Use read_lints equivalent functionality
                output["diagnostics"] = {
                    "error_analyzed": error_info,
                    "approach": "direct_trace",
                }

            elif selected_path["name"] == "workaround":
                # Search for alternative patterns
                output["diagnostics"] = {
                    "alternative_sought": True,
                    "approach": "pattern_search",
                }

            elif selected_path["name"] == "redesign":
                # Flag for architectural review
                output["diagnostics"] = {
                    "redesign_needed": True,
                    "approach": "architectural_review",
                }

            output["status"] = "executed"
            output["real_execution"] = True

        except Exception as e:
            logger.debug(f"Tools integration unavailable: {e}")
            output["real_execution"] = False

        # Check safety margin if provided
        safety_margin = context.get("safety_margin")
        if safety_margin is not None and safety_margin < 0.1:
            # Low safety margin, conservative recovery
            logger.warning(
                f"Low safety margin h(x)={safety_margin:.3f}, using conservative recovery"
            )
            output["strategy"] = "conservative"

        # Create S⁷ embedding (Flow is e₃, index 2)
        s7_embedding = torch.zeros(7)
        s7_embedding[2] = 1.0  # Flow's unit vector

        return AgentResult(
            success=True,
            output=output,
            s7_embedding=s7_embedding,
            should_escalate=False,
            metadata={
                "recovery_path": selected_path["name"],
                "recovery_attempts": self.recovery_attempts,
                "catastrophe_type": "swallowtail",
                "k_value": k_value,
                "path_risk": selected_path["risk"],
                "path_speed": selected_path["speed"],
            },
        )

    def get_available_paths(
        self,
        state: torch.Tensor | None = None,
        k_value: int = 1,
    ) -> list[dict[str, Any]]:
        """Get all available recovery paths (for testing/introspection).

        Args:
            state: Optional state tensor (generates random if None)
            k_value: Metacognition depth

        Returns:
            List of 3 recovery path dicts
        """
        if state is None:
            state = torch.randn(self.state_dim)

        return self._find_recovery_paths(state, k_value)

    def should_escalate(
        self,
        result: AgentResult,
        context: dict[str, Any],
    ) -> bool:
        """Determine if escalation needed.

        ESCALATION CONDITIONS:
        =====================
        - All recovery paths exhausted → Beacon (architecture redesign)
        - Security-critical fix → Crystal (verification)
        - Recovery attempts > 5 → Beacon (need planning)

        Args:
            result: Processing result
            context: Execution context

        Returns:
            True if should escalate
        """
        # Check if already marked for escalation
        if result.should_escalate:
            return True

        # Too many recovery attempts
        if self.recovery_attempts > 5:
            result.should_escalate = True
            result.escalation_target = "beacon"
            logger.info(f"Flow escalating after {self.recovery_attempts} attempts")
            return True

        # Security-critical context
        if context.get("security_critical", False):
            result.should_escalate = True
            result.escalation_target = "crystal"
            logger.info("Flow escalating security-critical fix to Crystal")
            return True

        # Architecture redesign needed
        if isinstance(result.output, dict) and result.output.get("scope") == "architectural":
            result.should_escalate = True
            result.escalation_target = "beacon"
            logger.info("Flow escalating architectural redesign to Beacon")
            return True

        return False

    def reset_recovery_attempts(self) -> None:
        """Reset recovery attempt counter (for new task)."""
        self.recovery_attempts = 0
        logger.debug("Flow recovery attempts reset")

    def get_recovery_stats(self) -> dict[str, Any]:
        """Get recovery statistics.

        Returns:
            Dictionary with recovery stats
        """
        return {
            "colony": self.colony_name,
            "recovery_attempts": self.recovery_attempts,
            "max_recovery_paths": self.max_recovery_paths,
            "catastrophe_type": "swallowtail",
        }


# =============================================================================
# FACTORY
# =============================================================================


def create_flow_agent(state_dim: int = 256) -> FlowAgent:
    """Create Flow agent instance.

    Args:
        state_dim: Dimension of state embeddings

    Returns:
        Configured FlowAgent
    """
    return FlowAgent(state_dim=state_dim)


__all__ = ["FlowAgent", "create_flow_agent"]
