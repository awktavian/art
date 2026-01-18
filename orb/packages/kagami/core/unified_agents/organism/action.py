"""Action Module - Action selection, policy execution, cost evaluation.

Responsibilities:
- Intent execution (execute_intent)
- CBF safety enforcement
- Cost module integration
- E8 action encoding/decoding
- Autonomous goal integration
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import TYPE_CHECKING, Any

from kagami.core.exceptions import SafetyViolationError

from .base import lazy_import_torch

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class ActionMixin:
    """Mixin providing action execution capabilities for UnifiedOrganism."""

    # These attributes are set by the main UnifiedOrganism class
    config: Any
    _router: Any
    _coordinator: Any
    _homeostasis_monitor: Any
    _perception_enabled: bool
    _autonomous_goal_engine: Any
    _autonomous_goals_enabled: bool
    _last_safety_check: Any
    _execution_count: int
    _execution_lock: Any
    _last_learning_time: float
    phase_detector: Any
    homeostasis: Any
    stats: Any

    async def execute_intent(
        self,
        intent: str,
        params: dict[str, Any],
        context: dict[str, Any] | None = None,
        task_config: Any | None = None,
    ) -> dict[str, Any]:
        """Execute an intent across appropriate colonies.

        Uses FanoActionRouter to determine which colonies to engage
        and E8ActionReducer to fuse their outputs.

        EXECUTIVE INTEGRATION: If task_config provided, uses executive configuration.
        CBF SAFETY ENFORCEMENT: ALL actions pass through CBF. No exceptions.
            - h(x) < 0: BLOCKED (SafetyViolationError raised)
            - 0 <= h(x) < 0.5: YELLOW zone (proceed with caution)
            - h(x) >= 0.5: GREEN zone (proceed normally)

        Args:
            intent: Intent name (e.g., "research.web", "build.feature")
            params: Intent parameters
            context: Execution context
            task_config: Optional TaskConfiguration from executive

        Returns:
            Execution result with E8 action code

        Raises:
            SafetyViolationError: If CBF safety check fails (h(x) < 0)
        """
        context = context or {}
        self._homeostasis_monitor.stats.total_intents += 1

        start_time = time.time()
        intent_id = str(uuid.uuid4())[:8]

        # CBF SAFETY CHECK
        logger.debug(f"Checking if this feels safe: {intent}")
        from kagami.core.safety.cbf_integration import check_cbf_for_operation

        safety_result = await check_cbf_for_operation(
            operation="organism.execute_intent",
            action=intent,
            target="colonies",
            params=params,
            metadata={"intent_id": intent_id, "context": context},
            source="organism",
            user_input=str(params),
        )

        self._last_safety_check = safety_result

        # RED ZONE: h(x) < 0 -> BLOCK
        if not safety_result.safe:
            self._homeostasis_monitor.update_intent_stats(success=False)
            logger.error(
                f"I need to stop this for your safety: {intent} "
                f"(h(x)={safety_result.h_x:.3f}, {safety_result.reason})"
            )
            raise SafetyViolationError(
                f"CBF safety check failed: {safety_result.reason} (h(x)={safety_result.h_x:.3f})"
            )

        # Safety zone classification
        if safety_result.h_x is not None and safety_result.h_x < 0.5:
            context["safety_zone"] = "yellow"
            context["safety_h_x"] = safety_result.h_x
            if safety_result.h_x < 0.1:
                logger.warning(
                    f"This feels risky, proceeding carefully: {intent} "
                    f"(h(x)={safety_result.h_x:.3f})"
                )
            else:
                logger.debug(f"Yellow zone: {intent} (h(x)={safety_result.h_x:.3f})")
        else:
            logger.debug(f"This feels safe: {intent} (h(x)={safety_result.h_x:.3f})")
            context["safety_zone"] = "green"
            context["safety_h_x"] = safety_result.h_x

        # PERCEPTION INTEGRATION
        if self._perception_enabled:
            perception_result = await self.perceive(
                sensors=context.get("sensors"),
                context={"intent": intent, "params": params},
            )
            if perception_result.get("state") is not None:
                context["perception_state"] = perception_result["state"]
                context["modalities_observed"] = perception_result.get("modalities_present", [])
                logger.debug(
                    f"Perceived: {perception_result.get('modalities_present')} "
                    f"({perception_result.get('perception_time_ms', 0):.1f}ms)"
                )

        # AUTONOMOUS GOAL INTEGRATION
        await self._integrate_autonomous_goals(intent, context)

        # CONFIGURATOR INTEGRATION
        world_model_state = None
        if task_config is None:
            task_config, world_model_state = await self._configure_task(intent)

        # WORLD MODEL INTEGRATION
        wm_prediction = await self._query_world_model_for_intent(intent, params, context)
        if wm_prediction:
            context["wm_colony_hint"] = wm_prediction
            logger.debug(
                f"Sensing {wm_prediction.get('colony_name')} might help here "
                f"(confidence: {wm_prediction.get('confidence', 0):.2f})"
            )

        # KNOWLEDGE GRAPH INTEGRATION
        kg_recommendations = await self._consult_knowledge_graph(intent, context)
        if kg_recommendations:
            context["kg_suggestions"] = kg_recommendations
            logger.debug(f"I remember {len(kg_recommendations)} similar situations")

        # COST MODULE INTEGRATION
        await self._evaluate_routing_cost(intent, params, context, safety_result, world_model_state)

        try:
            # Delegate to colony coordinator
            coord_result = await self._coordinator.execute_intent(intent, params, context)

            task_success = True
            self._homeostasis_monitor.update_intent_stats(success=True)

            # PHASE TRANSITION DETECTION
            routing = coord_result["routing"]
            from kagami.core.unified_agents.fano_action_router import ActionMode

            if routing.mode in (ActionMode.FANO_LINE, ActionMode.ALL_COLONIES):
                await self._handle_multi_colony_phase(coord_result, routing, task_success)

            # RECEIPT LEARNING
            async with self._execution_lock:
                self._execution_count += 1
                should_update_kg = self._execution_count % 50 == 0

            await self._trigger_receipt_learning(intent)

            if should_update_kg:
                receipts = await self._get_recent_receipts(intent.split(".")[0], limit=50)
                if receipts:
                    await self.update_knowledge_graph(receipts)

            # AMBIENT UPDATE
            await self._update_ambient_state()

            return {
                "intent_id": intent_id,
                "success": True,
                "mode": coord_result["mode"],
                "complexity": coord_result["complexity"],
                "results": coord_result["results"],
                "e8_action": coord_result["e8_action"],
                "latency": time.time() - start_time,
                "coordination_phase": self.phase_detector.current_phase.value,
                "octonion_state": coord_result.get("octonion_state"),
            }

        except Exception as e:
            self._homeostasis_monitor.update_intent_stats(success=False)
            logger.error(f"Hit a snag: {e}. Let me figure out what happened.")

            return {
                "intent_id": intent_id,
                "success": False,
                "error": str(e),
                "latency": time.time() - start_time,
            }

    async def _integrate_autonomous_goals(self, intent: str, context: dict[str, Any]) -> None:
        """Integrate autonomous goals into intent execution."""
        if self._autonomous_goal_engine is None:
            return

        try:
            autonomous_goals = (
                await self._autonomous_goal_engine._goal_manager.get_active_goals()
                if self._autonomous_goal_engine._goal_manager
                else []
            )

            intent_modulation = None
            for goal in autonomous_goals[:3]:
                if goal.get("intent_pattern") and goal["intent_pattern"] in intent:
                    intent_modulation = {
                        "priority_boost": 0.3 * goal.get("priority", 0.5),
                        "goal_id": goal.get("id"),
                        "goal_description": goal.get("description", "autonomous goal"),
                    }
                    logger.debug(
                        f"Intent {intent} aligns with autonomous goal: {goal.get('description')}"
                    )
                    break

            if intent_modulation:
                context["autonomous_goal_modulation"] = intent_modulation
                if hasattr(self._autonomous_goal_engine, "_goal_manager"):
                    await self._autonomous_goal_engine._goal_manager.mark_goal_progress(
                        intent_modulation["goal_id"], progress=0.1
                    )

        except Exception as e:
            logger.debug(f"Autonomous goal integration error: {e}")

    async def _configure_task(self, intent: str) -> tuple[Any, Any]:
        """Configure task using executive control.

        Returns:
            Tuple of (task_config, world_model_state)
        """
        try:
            task_embedding = self._embed_intent(intent)
            executive = self._get_executive()

            world_model_state = None
            try:
                from kagami.core.world_model.service import get_world_model_service

                _torch = lazy_import_torch()  # Ensure torch is available
                wm_service = get_world_model_service()
                if wm_service.model is not None:
                    core_state = wm_service.encode("<current_state>")
                    if core_state is not None and core_state.s7_phase is not None:
                        flattened = core_state.s7_phase.flatten(start_dim=1)
                        if flattened.shape[-1] == 256:
                            world_model_state = flattened.to(self.config.device)
            except Exception:
                pass

            task_config = await executive.configure_for_task(
                task_embedding=task_embedding,
                task_type="general",
                task_description=intent,
                world_model_state=world_model_state,
            )

            logger.info(
                f"I'm thinking {task_config.actor.mode} would work best "
                f"(urgency: {task_config.urgency:.2f})"
            )

            if task_config.urgency > 0.7:
                self._router.complex_threshold = 0.9
            else:
                self._router.complex_threshold = 0.7

            return task_config, world_model_state

        except (ImportError, RuntimeError, ValueError) as e:
            logger.warning(f"Configurator isn't available, using standard approach: {e}")
            return None, None

    async def _evaluate_routing_cost(
        self,
        intent: str,
        params: dict[str, Any],
        context: dict[str, Any],
        safety_result: Any,
        world_model_state: Any,
    ) -> None:
        """Evaluate routing cost using cost module."""
        try:
            routing_candidate = self._router.route(intent, params, context=context)
            cost_module = self._get_cost_module()
            torch = lazy_import_torch()

            # Extract current state
            try:
                if world_model_state is not None:
                    state = world_model_state
                else:
                    state = self._embed_intent(intent)
            except Exception:
                state = self._embed_intent(intent)

            # Pad state to match cost module's expected state_dim (512)
            if state.shape[-1] < 512:
                padding = torch.zeros(
                    state.shape[0],
                    512 - state.shape[-1],
                    device=state.device,
                )
                state = torch.cat([state, padding], dim=-1)
            elif state.shape[-1] > 512:
                state = state[..., :512]

            # Encode routing as action
            primary_action = routing_candidate.actions[0]
            colony_idx = primary_action.colony_idx

            action = torch.zeros(1, 64, device=state.device)
            action[0, colony_idx] = 1.0
            action[0, 7] = routing_candidate.complexity

            cbf_value = torch.tensor([[safety_result.h_x]], device=state.device)

            # Evaluate cost
            cost_result = cost_module(state, action, cbf_value=cbf_value)

            total_cost = float(cost_result["total"].detach().mean())
            ic_cost = float(cost_result["ic_total"].detach().mean())
            tc_cost = float(cost_result["tc_value"].detach().mean())
            safety_cost = float(cost_result["ic_safety"].detach().mean())

            logger.info(
                f"Weighing the cost: total={total_cost:.3f} "
                f"(safety={safety_cost:.3f}, effort={ic_cost:.3f}, expected={tc_cost:.3f})"
            )

            # SAFETY THRESHOLD
            if torch.isinf(cost_result["ic_safety"]).any():
                logger.error(
                    f"This would cost too much safety-wise. I need to stop. "
                    f"(h(x)={safety_result.h_x:.3f})"
                )
                raise SafetyViolationError(
                    f"Cost module blocked action due to safety violation: "
                    f"IC_safety=inf, h(x)={safety_result.h_x:.3f}",
                )

            if total_cost > 10.0:
                logger.warning(
                    f"This will take more than usual: {intent} (total cost: {total_cost:.3f})"
                )

            context["cost_evaluation"] = {
                "total": total_cost,
                "ic": ic_cost,
                "tc": tc_cost,
                "safety": safety_cost,
                "routing_mode": routing_candidate.mode.value,
                "primary_colony": primary_action.colony_name,
            }

        except (ImportError, RuntimeError, ValueError) as e:
            logger.warning(f"Couldn't weigh costs this time (non-blocking): {e}")

    async def _handle_multi_colony_phase(
        self, coord_result: dict[str, Any], routing: Any, task_success: bool
    ) -> None:
        """Handle phase detection for multi-colony tasks."""
        from kagami.core.unified_agents.fano_action_router import ActionMode

        td_errors = await self._compute_td_errors_proxy(coord_result["results"])

        fano_line_idx = (
            self._get_fano_line_index(routing) if routing.mode == ActionMode.FANO_LINE else None
        )

        self.phase_detector.update(
            task_success=task_success,
            td_errors=td_errors,
            fano_line_idx=fano_line_idx,
        )

        transition_event = self.phase_detector.phase_changed()
        if transition_event is not None:
            await self._handle_phase_transition(transition_event)

    def encode_e8_message(
        self,
        source_colony: int,
        target_colony: int,
        data: Any,
    ) -> dict[str, Any]:
        """Encode a message using E8 protocol.

        Args:
            source_colony: Source colony index (0-6)
            target_colony: Target colony index (0-6)
            data: 8D data tensor

        Returns:
            E8 encoded message
        """
        return self._coordinator.encode_e8_message(source_colony, target_colony, data)

    def decode_e8_message(
        self,
        e8_index: int,
    ) -> Any:
        """Decode E8 message to data tensor.

        Args:
            e8_index: E8 root index (0-239)

        Returns:
            8D data tensor
        """
        return self._coordinator.decode_e8_message(e8_index)


__all__ = ["ActionMixin"]
