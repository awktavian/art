"""Symbiote Bridge - Theory of Mind integration for ambient computing.

Extracted from controller.py (January 2026) to isolate Symbiote/ToM
integration from the main orchestrator.

The SymbioteBridge handles:
- User presence observation via Theory of Mind
- Intent inference for proactive assistance
- Anticipated needs prediction
- Social context awareness
"""

from __future__ import annotations

import logging
from typing import Any

from kagami.core.ambient.data_types import PresenceLevel, PresenceState

logger = logging.getLogger(__name__)


class SymbioteBridge:
    """Bridge between ambient computing and Symbiote Theory of Mind.

    Enables presence-aware intent inference and proactive assistance
    based on user state modeling.

    References:
    - arxiv 2508.00401 (ToM in AI systems)
    - arxiv 2502.14171 (Intent prediction)
    - arxiv 2311.03150 (Proactive assistance)
    """

    def __init__(self):
        """Initialize symbiote bridge."""
        self._symbiote: Any = None

    def set_symbiote(self, symbiote: Any) -> None:
        """Connect Symbiote module.

        Args:
            symbiote: SymbioteModule instance
        """
        self._symbiote = symbiote
        if symbiote is not None:
            logger.info("Symbiote connected to Ambient Controller")

    @property
    def is_connected(self) -> bool:
        """Check if symbiote is connected."""
        return self._symbiote is not None

    async def observe_user_presence(
        self,
        user_id: str,
        presence: PresenceState,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Observe user presence and update their model via Symbiote.

        Presence changes are key signals for Theory of Mind:
        - User arriving -> anticipate needs
        - User leaving -> remember context for return
        - User focusing -> reduce interruptions
        - User stressed -> adapt ambient to calm

        Args:
            user_id: User identifier
            presence: Current presence state
            context: Additional context

        Returns:
            Dict with social context and predictions, or None
        """
        if self._symbiote is None:
            return None

        try:
            # Import AgentType dynamically to avoid circular imports
            from kagami.core.symbiote import AgentType

            # Build presence context
            presence_context = {
                "presence_level": presence.level.value,
                "confidence": presence.confidence,
                "activity_type": presence.activity_type,
                "location": presence.location,
                **(context or {}),
            }

            # Observe via Symbiote
            result = self._symbiote.observe_agent_action(
                agent_id=user_id,
                action=f"presence_{presence.level.value}",
                context=presence_context,
                agent_type=AgentType.USER,
            )

            # Log if proactive assistance is suggested
            if result and result.get("should_assist", False):
                logger.info(
                    f"Symbiote suggests proactive assistance for {user_id}: "
                    f"{result.get('suggested_action', 'unknown')}"
                )

            return result

        except Exception as e:
            logger.debug(f"Symbiote presence observation failed: {e}")
            return None

    async def get_intent_inference(self, user_id: str) -> dict[str, Any]:
        """Get Symbiote's current inference about user intent.

        Args:
            user_id: User identifier

        Returns:
            Dict with inferred intent, confidence, and suggestions
        """
        if self._symbiote is None:
            return {
                "has_symbiote": False,
                "inferred_intent": None,
                "confidence": 0.0,
            }

        try:
            return self._symbiote.get_intent_inference(user_id)
        except Exception as e:
            logger.debug(f"Intent inference failed: {e}")
            return {"has_symbiote": True, "error": str(e)}

    async def should_proactively_assist(
        self,
        user_id: str,
        presence: PresenceState | None = None,
    ) -> tuple[bool, str | None]:
        """Check if system should proactively assist user.

        Uses Symbiote's Theory of Mind to determine if:
        - User needs help but hasn't asked
        - Context suggests upcoming need
        - Ambient cues indicate opportunity

        Args:
            user_id: User to check
            presence: Current presence state (optional)

        Returns:
            (should_assist, reason)
        """
        if self._symbiote is None:
            return False, None

        try:
            # Get social context
            social_context = self._symbiote.get_social_context()

            # Check if clarification is needed
            if social_context.get("clarification_needed", False):
                return True, "ambiguous_intent"

            # Check anticipated needs
            anticipated = self._symbiote.anticipate_needs(user_id, {})
            if anticipated and len(anticipated) > 0:
                top_need = anticipated[0]
                if top_need.get("confidence", 0) > 0.7:
                    return True, f"anticipated_need:{top_need.get('need_type', 'unknown')}"

            # Check presence-based assistance
            if presence is not None:
                if presence.level == PresenceLevel.ENGAGED:
                    # User is engaged - check if they're stuck
                    inference = self._symbiote.get_intent_inference(user_id)
                    if inference.get("stuck_probability", 0) > 0.6:
                        return True, "user_appears_stuck"

            return False, None

        except Exception as e:
            logger.debug(f"Proactive assistance check failed: {e}")
            return False, None
