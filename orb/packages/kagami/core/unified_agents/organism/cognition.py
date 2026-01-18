"""Cognition Module - World model integration, consciousness, belief updates.

Responsibilities:
- World model querying and prediction
- Colony routing predictions from world model
- Consciousness integration bridge
- Symbiote (Theory of Mind) integration
- Executive control (LeCun configurator)
"""

from __future__ import annotations

import hashlib
import logging
from typing import TYPE_CHECKING, Any

from .base import lazy_import_torch

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class CognitionMixin:
    """Mixin providing cognition/world model capabilities for UnifiedOrganism."""

    # These attributes are set by the main UnifiedOrganism class
    _symbiote_module: Any
    _cost_module: Any
    _colonies: dict[str, Any]
    config: Any

    def set_symbiote_module(self, module: Any) -> None:
        """Connect Symbiote module for Theory of Mind capabilities.

        NEXUS BRIDGE: Agent observation -> Social awareness -> Better routing.

        The Symbiote Module enables:
        1. User intent inference (predict what user wants)
        2. Clarification suggestions (ask the right questions)
        3. Social surprise in EFE (cooperative action selection)
        4. Social safety in CBF (prevent manipulation)

        Args:
            module: SymbioteModule instance (typed as Any to avoid circular import)
        """
        self._symbiote_module = module

        # Wire to Nexus colony if available (uses set_symbiote to avoid log spam)
        nexus = self._colonies.get("nexus")
        if nexus is not None and hasattr(nexus, "set_symbiote"):
            nexus.set_symbiote(module)
        elif nexus is not None and hasattr(nexus, "_symbiote"):
            # Fallback for older NexusAgent versions
            nexus._symbiote = module

        logger.info("Symbiote Module connected. I can now model others' minds.")

    def get_symbiote_module(self) -> Any | None:
        """Get the connected Symbiote module.

        Returns:
            SymbioteModule if connected, else None
        """
        return self._symbiote_module

    def observe_user_action(
        self,
        user_id: str,
        action: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Observe a user action via Symbiote.

        Convenience method that routes to SymbioteModule.observe_agent_action.
        Called by API layer to track user interactions.

        Args:
            user_id: User identifier
            action: Action performed (e.g., "submitted query", "clicked approve")
            context: Additional context about the action

        Returns:
            Dict with observation results (intent, predictions, anomalies)
        """
        if self._symbiote_module is None:
            return None

        try:
            # Import AgentType dynamically to avoid circular imports
            from kagami.core.symbiote import AgentType

            return self._symbiote_module.observe_agent_action(
                agent_id=user_id,
                action=action,
                context=context,
                agent_type=AgentType.USER,
            )
        except (ImportError, AttributeError) as e:
            logger.debug(f"Symbiote observation failed: {e}")
            return None

    def get_social_context(self) -> dict[str, Any]:
        """Get current social context for routing decisions.

        Aggregates information from SymbioteModule about:
        - Active agents being modeled
        - Intent confidence levels
        - Whether clarification is needed

        Returns:
            Dict with social context (or defaults if Symbiote unavailable)
        """
        if self._symbiote_module is None:
            return {
                "has_symbiote": False,
                "has_active_agents": False,
                "social_complexity": 0.0,
                "clarification_needed": False,
            }

        context = self._symbiote_module.get_social_context()
        context["has_symbiote"] = True
        return context

    def _get_executive(self) -> Any:
        """Lazy load executive control.

        OPTIMIZATION (Dec 16, 2025): Import executive module only when needed.
        """
        if not hasattr(self, "_executive") or self._executive is None:
            from kagami.core.executive import get_executive_control

            self._executive = get_executive_control()
        return self._executive

    def _get_cost_module(self) -> Any:
        """Lazy load cost module.

        LECUN INTEGRATION (Dec 20, 2025): Load cost module for action evaluation.
        Cost module combines intrinsic cost (IC - immutable safety) and
        trainable critic (TC - learned value prediction).

        Returns:
            UnifiedCostModule instance
        """
        if self._cost_module is None:
            from kagami.core.rl.unified_cost_module import get_cost_module

            self._cost_module = get_cost_module()
            logger.debug("Cost evaluation ready")
        return self._cost_module

    def _embed_intent(self, intent: str) -> Any:
        """Embed intent string into task embedding space.

        Uses simple hash-based encoding for now. Can upgrade to LLM embeddings later.

        Args:
            intent: Intent action string (e.g., "research.web", "build.feature")

        Returns:
            [1, 512] task embedding tensor
        """
        torch = lazy_import_torch()

        # Hash intent to fixed-size bytes
        intent_hash = hashlib.sha256(intent.encode()).digest()

        # Convert to normalized float tensor
        embedding = torch.tensor(
            [float(b) / 255.0 for b in intent_hash],
            dtype=torch.float32,
            device=self.config.device,
        )

        # Pad or truncate to 512 dims
        if len(embedding) < 512:
            padding = torch.zeros(512 - len(embedding), device=self.config.device)
            embedding = torch.cat([embedding, padding])
        else:
            embedding = embedding[:512]

        return embedding.unsqueeze(0)  # Add batch dimension

    async def configure_for_task(
        self,
        task_embedding: Any,
        task_type: str = "general",
        task_description: str = "",
    ) -> Any:
        """Configure organism for a task using executive control.

        LeCun: "The configurator primes the perception system to extract
        the relevant information from the percept for the task at hand."

        Args:
            task_embedding: Semantic task embedding
            task_type: Type of task
            task_description: Text description

        Returns:
            TaskConfiguration for all modules
        """
        executive = self._get_executive()
        return await executive.configure_for_task(
            task_embedding=task_embedding,
            task_type=task_type,
            task_description=task_description,
        )

    async def _query_world_model_for_intent(
        self,
        intent: str,
        params: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Query world model for colony routing prediction.

        NEXUS BRIDGE: Connects world model predictions to routing decisions.

        The world model predicts which colony is best suited for this intent
        based on:
        - Historical intent -> colony -> outcome patterns
        - Current organism state (colony workloads, health)
        - Task complexity signals

        Args:
            intent: Intent to execute
            params: Intent parameters
            context: Execution context

        Returns:
            Prediction dict with colony_idx, colony_name, confidence, or None
        """
        try:
            from kagami.core.world_model.service import get_world_model_service

            service = get_world_model_service()
            if service.model is None:
                return None

            # Construct observation from intent + params + context
            observation = {
                "intent": intent,
                "params": params,
                "context": context,
                "organism_state": {
                    "colony_health": self.homeostasis.colony_health,
                    "total_population": self.stats.total_population,
                    "active_colonies": self.stats.active_colonies,
                },
            }

            # Query world model for next-state prediction
            prediction = service.predict(
                observation=observation,
                action={"type": "route_intent", "intent": intent},
                horizon=1,
            )

            if prediction is None:
                return None

            # Extract colony recommendation from prediction
            return self._extract_colony_from_prediction(prediction)

        except (ImportError, AttributeError, RuntimeError) as e:
            logger.debug(f"World model query failed: {e}")
            return None

    def _extract_colony_from_prediction(
        self,
        prediction: Any,
    ) -> dict[str, Any] | None:
        """Extract colony recommendation from world model prediction.

        Args:
            prediction: World model prediction output

        Returns:
            Colony hint dict or None
        """
        try:
            from kagami.core.unified_agents.geometric_worker import COLONY_NAMES

            # If prediction has explicit colony field
            if hasattr(prediction, "recommended_colony"):
                colony_idx = int(prediction.recommended_colony)
                return {
                    "colony_idx": colony_idx,
                    "colony_name": COLONY_NAMES[colony_idx],
                    "confidence": getattr(prediction, "confidence", 0.5),
                    "source": "world_model",
                }

            # Extract from latent state
            if hasattr(prediction, "state") and prediction.state is not None:
                state_tensor = prediction.state
                torch = lazy_import_torch()
                if isinstance(state_tensor, torch.Tensor) and state_tensor.numel() >= 7:
                    # Use first 7 dims as colony activation probabilities
                    colony_activations = state_tensor.flatten()[:7]
                    best_colony_idx = int(torch.argmax(colony_activations).item())

                    confidence = float(torch.softmax(colony_activations, dim=0)[best_colony_idx])

                    return {
                        "colony_idx": best_colony_idx,
                        "colony_name": COLONY_NAMES[best_colony_idx],
                        "confidence": confidence,
                        "source": "world_model_state",
                    }

            return None

        except (AttributeError, ValueError, IndexError) as e:
            logger.debug(f"Colony extraction from prediction failed: {e}")
            return None


__all__ = ["CognitionMixin"]
