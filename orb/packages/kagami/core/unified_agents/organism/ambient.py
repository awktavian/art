"""Ambient Module - Ambient state integration and phase transitions.

Responsibilities:
- Ambient controller integration
- Ambient state updates
- Safety state extraction
- Coordination phase transitions
- Colony state mapping
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from .base import lazy_import_torch

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class AmbientMixin:
    """Mixin providing ambient integration for UnifiedOrganism."""

    # These attributes are set by the main UnifiedOrganism class
    _ambient_controller: Any
    _last_safety_check: Any
    _colonies: dict[str, Any]
    config: Any
    phase_detector: Any
    _coupling_strength: float

    def set_ambient_controller(self, controller: Any) -> None:
        """Connect ambient controller for real-time state visualization.

        NEXUS BRIDGE: Organism state -> Ambient display.

        Args:
            controller: AmbientController instance
        """
        self._ambient_controller = controller
        logger.info("Connected to ambient display. You'll see what I'm thinking now.")

    async def _update_ambient_state(self) -> None:
        """Update ambient controller with current organism state.

        NEXUS BRIDGE: Translates organism state -> AmbientState format.

        This method:
        1. Gathers colony states (activation, catastrophe params)
        2. Constructs safety state from CBF
        3. Maps coordination phase -> breath phase
        4. Pushes to ambient controller for display
        """
        if self._ambient_controller is None:
            return

        try:
            from kagami.core.ambient.data_types import ColonyState  # Colony unused but for type

            # Build colony states map
            colony_states: dict[Any, Any] = {}
            for name, colony in self._colonies.items():
                colony_enum = self._map_colony_name_to_enum(name)
                if colony_enum is None:
                    continue

                stats = colony.get_stats()
                activation = min(
                    stats.get("population", 0) / self.config.max_workers_per_colony, 1.0
                )

                # Extract catastrophe kernel outputs if available
                potential, gradient, params = self._extract_catastrophe_outputs(colony)

                colony_states[colony_enum] = ColonyState(
                    colony=colony_enum,
                    activation=activation,
                    potential=potential,
                    gradient=gradient,
                    params=params,
                )

            # Build safety state
            safety_state = await self._get_current_safety_state()

            # Map coordination phase -> breath phase
            breath_phase = self._map_coordination_to_breath_phase()

            # Update ambient controller
            self._ambient_controller.update_colony_states(colony_states)
            self._ambient_controller.update_safety(safety_state)

            if breath_phase is not None:
                self._ambient_controller.sync_to_receipt(breath_phase.value, None)

            logger.debug(
                f"State visible now: "
                f"{len(colony_states)} colonies active, "
                f"safety at {safety_state.h_value:.3f}, "
                f"breathing in {breath_phase.value if breath_phase else 'rest'}"
            )

        except (ImportError, AttributeError, RuntimeError) as e:
            logger.debug(f"Ambient state update failed: {e}")

    def _extract_catastrophe_outputs(
        self, colony: Any
    ) -> tuple[float, tuple[float, ...], tuple[float, ...]]:
        """Extract catastrophe kernel outputs from world model.

        Args:
            colony: Colony instance

        Returns:
            Tuple of (potential, gradient, params)
        """
        potential = 0.0
        gradient: tuple[float, ...] = (0.0,)
        params: tuple[float, ...] = (0.0,)

        try:
            from kagami.core.world_model.service import get_world_model_service

            service = get_world_model_service()

            if service.is_available and service.model is not None:
                model = service.model

                if hasattr(model, "s7_to_tower") and hasattr(model.s7_to_tower, "basis"):
                    basis = model.s7_to_tower.basis

                    if hasattr(colony, "get_state") and callable(colony.get_state):
                        colony_state_data = colony.get_state()
                        state_tensor = colony_state_data.get("state_tensor", None)

                        if state_tensor is not None:
                            torch = lazy_import_torch()
                            if isinstance(state_tensor, torch.Tensor):
                                with torch.no_grad():
                                    risk = basis.get_singularity_risk(
                                        state_tensor.to(service.device)
                                    )
                                    potential = float(risk.mean().item())

                                if hasattr(basis, "control_params"):
                                    control_params = basis.control_params.detach().cpu()
                                    params = tuple(
                                        float(control_params[:, i].mean().item())
                                        for i in range(min(4, control_params.shape[1]))
                                    )

                                if len(params) > 0:
                                    gradient = tuple(float(p / (abs(p) + 1e-6)) for p in params[:3])

        except (ImportError, AttributeError, RuntimeError) as e:
            logger.debug(f"Could not extract catastrophe kernel outputs: {e}")

        return potential, gradient, params

    def _map_colony_name_to_enum(self, name: str) -> Any:
        """Map colony name string to Colony enum.

        Args:
            name: Colony name (spark, forge, flow, etc.)

        Returns:
            Colony enum value or None
        """
        try:
            from kagami.core.ambient.data_types import Colony

            return Colony[name.upper()]
        except (KeyError, ImportError) as e:
            logger.debug(f"Failed to map colony name '{name}' to enum: {e}")
            return None

    def _map_coordination_to_breath_phase(self) -> Any:
        """Map coordination phase -> breath phase.

        SEMANTIC MAPPING:
        - COORDINATED -> EXHALE (releasing, stable)
        - TRANSITION -> INHALE (gathering, preparing)
        - JAMMED -> HOLD (executing, working through)
        - UNKNOWN -> REST (waiting)

        Returns:
            BreathPhase enum value or None
        """
        try:
            from kagami.core.ambient.data_types import BreathPhase
            from kagami.core.unified_agents.phase_detector import CoordinationPhase

            phase = self.phase_detector.current_phase

            mapping = {
                CoordinationPhase.COORDINATED: BreathPhase.EXHALE,
                CoordinationPhase.TRANSITION: BreathPhase.INHALE,
                CoordinationPhase.JAMMED: BreathPhase.HOLD,
                CoordinationPhase.UNKNOWN: BreathPhase.REST,
            }

            return mapping.get(phase, BreathPhase.REST)

        except (ImportError, AttributeError) as e:
            logger.debug(f"Failed to map coordination phase to breath phase: {e}")
            return None

    async def _get_current_safety_state(self) -> Any:
        """Query current safety state from CBF.

        Uses cached last safety check result from most recent intent execution.

        Returns:
            SafetyState with current h(x) value and extracted x components
        """
        try:
            from kagami.core.ambient.data_types import SafetyState

            # Default safe values
            h_x = 1.0
            x_threat = 0.0
            x_uncertainty = 0.0
            x_complexity = 0.0
            x_risk = 0.0
            gradient: tuple[float, ...] = (0.0, 0.0, 0.0, 0.0)

            if self._last_safety_check is not None:
                h_x = (
                    float(self._last_safety_check.h_x)
                    if self._last_safety_check.h_x is not None
                    else 1.0
                )

                if (
                    hasattr(self._last_safety_check, "metadata")
                    and self._last_safety_check.metadata
                ):
                    metadata = self._last_safety_check.metadata
                    x_threat, x_uncertainty, x_complexity, x_risk, gradient = (
                        self._extract_safety_components(metadata, h_x)
                    )

                    logger.debug(
                        f"Reading safety state: h={h_x:.3f}, "
                        f"sensing threat={x_threat:.3f}, uncertainty={x_uncertainty:.3f}, "
                        f"complexity={x_complexity:.3f}, risk={x_risk:.3f}"
                    )

            return SafetyState(
                h_value=h_x,
                x_threat=x_threat,
                x_uncertainty=x_uncertainty,
                x_complexity=x_complexity,
                x_risk=x_risk,
                gradient=gradient,
            )

        except ImportError:
            from kagami.core.ambient.data_types import SafetyState

            return SafetyState(
                h_value=1.0,
                x_threat=0.0,
                x_uncertainty=0.0,
                x_complexity=0.0,
                x_risk=0.0,
                gradient=(0.0, 0.0, 0.0, 0.0),
            )

    def _extract_safety_components(
        self, metadata: dict[str, Any], h_x: float
    ) -> tuple[float, float, float, float, tuple[float, ...]]:
        """Extract safety components from metadata.

        Args:
            metadata: Safety check metadata
            h_x: h(x) value

        Returns:
            Tuple of (x_threat, x_uncertainty, x_complexity, x_risk, gradient)
        """
        x_threat = 0.0
        x_uncertainty = 0.0
        x_complexity = 0.0
        x_risk = 0.0
        gradient: tuple[float, ...] = (0.0, 0.0, 0.0, 0.0)

        if "risk_scores" in metadata:
            risk_scores = metadata["risk_scores"]
            x_threat = float(risk_scores.get("threat", 0.0))
            x_uncertainty = float(risk_scores.get("uncertainty", 0.0))
            x_complexity = float(risk_scores.get("complexity", 0.0))
            x_risk = float(risk_scores.get("risk", 0.0))

        elif "cbf_state" in metadata:
            cbf_state = metadata["cbf_state"]
            x_threat = float(cbf_state.get("x_threat", 0.0))
            x_uncertainty = float(cbf_state.get("x_uncertainty", 0.0))
            x_complexity = float(cbf_state.get("x_complexity", 0.0))
            x_risk = float(cbf_state.get("x_risk", 0.0))
            if "gradient" in cbf_state:
                grad_values = cbf_state["gradient"]
                if isinstance(grad_values, (list, tuple)) and len(grad_values) >= 4:
                    gradient = tuple(float(grad_values[i]) for i in range(4))

        elif "x_state" in metadata:
            x_state = metadata.get("x_state", {})
            if isinstance(x_state, dict):
                x_threat = float(x_state.get("threat", 0.0))
                x_uncertainty = float(x_state.get("uncertainty", 0.0))
                x_complexity = float(x_state.get("complexity", 0.0))
                x_risk = float(x_state.get("risk", 0.0))

        elif "classification" in metadata:
            classification = metadata.get("classification", {})
            total_risk = classification.get("total_risk", 0.0)
            x_threat = total_risk * 0.4
            x_uncertainty = total_risk * 0.2
            x_complexity = total_risk * 0.2
            x_risk = total_risk * 0.2

        else:
            x_threat = float(metadata.get("x_threat", 0.0))
            x_uncertainty = float(metadata.get("x_uncertainty", 0.0))
            x_complexity = float(metadata.get("x_complexity", 0.0))
            x_risk = float(metadata.get("x_risk", 0.0))

        # Extract gradient if available
        if gradient == (0.0, 0.0, 0.0, 0.0) and "gradient" in metadata:
            grad = metadata.get("gradient")
            if isinstance(grad, (list, tuple)):
                gradient = tuple(float(g) for g in grad[:4])
                if len(gradient) < 4:
                    gradient = gradient + (0.0,) * (4 - len(gradient))

        # Compute gradient from h(x) if not provided
        if gradient == (0.0, 0.0, 0.0, 0.0) and h_x != 1.0:
            total = x_threat + x_uncertainty + x_complexity + x_risk
            if total > 0:
                gradient = (
                    -x_threat / total,
                    -x_uncertainty / total,
                    -x_complexity / total,
                    -x_risk / total,
                )

        return x_threat, x_uncertainty, x_complexity, x_risk, gradient

    async def _compute_td_errors_proxy(
        self,
        results: list[Any],
    ) -> dict[int, float]:
        """Compute TD-error proxy from colony execution results.

        Args:
            results: Colony execution results (TaskResult objects)

        Returns:
            Dict mapping colony_idx -> TD-error proxy
        """
        td_errors = {}

        for i, result in enumerate(results):
            success = result.success
            latency = result.latency

            td_error = 0.0 if success else 1.0
            td_error *= 1.0 + min(latency, 2.0)

            td_errors[i] = td_error

        return td_errors

    def _get_fano_line_index(self, routing: Any) -> int | None:
        """Get Fano line index from routing result.

        Args:
            routing: Routing result with Fano line

        Returns:
            Line index (0-6) or None
        """
        if routing.fano_line is None:
            return None

        from kagami_math.fano_plane import get_fano_lines_zero_indexed

        fano_lines = get_fano_lines_zero_indexed()
        routing_set = set(routing.fano_line)

        for idx, line in enumerate(fano_lines):
            if set(line) == routing_set:
                return idx

        return None

    async def _handle_phase_transition(
        self,
        event: Any,
    ) -> None:
        """Handle coordination phase transition.

        Actions:
        1. Emit receipt for observability
        2. Adjust coupling strength
        3. Log failing Fano lines

        Args:
            event: PhaseTransitionEvent
        """
        logger.info(
            f"Coordination shifting: {event.old_phase.value} -> {event.new_phase.value} "
            f"(CSR={event.csr:.3f}, variation={event.td_variance:.3f})"
        )

        # Adjust coupling strength
        adjustment = self.phase_detector.suggest_coupling_adjustment()
        old_coupling = self._coupling_strength
        self._coupling_strength *= adjustment

        logger.info(
            f"Adjusting how colonies work together: {old_coupling:.3f} -> {self._coupling_strength:.3f}"
        )

        # Identify failing Fano lines
        failing_lines = self.phase_detector.get_failing_fano_lines()
        if failing_lines:
            logger.warning(
                f"Some colony combinations aren't working well: {failing_lines}. "
                f"I'll try different approaches next time."
            )

        # Emit receipt for phase transition
        try:
            from kagami.core.receipts.facade import UnifiedReceiptFacade as URF
            from kagami.core.utils.ids import generate_correlation_id

            correlation_id = generate_correlation_id(prefix="phase_transition")
            URF.emit(
                correlation_id=correlation_id,
                event_name="organism.phase_transition",
                phase="EXECUTE",
                action="phase_transition",
                app="organism",
                status="success",
                event_data={
                    "old_phase": event.old_phase.value,
                    "new_phase": event.new_phase.value,
                    "csr": event.csr,
                    "td_variance": event.td_variance,
                    "window_size": event.window_size,
                    "coupling_old": old_coupling,
                    "coupling_new": self._coupling_strength,
                    "coupling_adjustment": adjustment,
                    "failing_fano_lines": failing_lines,
                    "fano_summary": event.metadata,
                },
            )
            logger.debug(f"Recorded transition: {correlation_id}")
        except Exception as e:
            logger.debug(f"Couldn't record transition: {e}")


__all__ = ["AmbientMixin"]
