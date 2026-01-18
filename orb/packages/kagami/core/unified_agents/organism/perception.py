"""Perception Module - Sensory processing and observation encoding.

Responsibilities:
- Unified perception API (perceive method)
- Perception module management
- Multimodal sensory processing
- LeCun architecture: "The perception module estimates the current state"
"""

from __future__ import annotations

import logging
import time as time_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class PerceptionMixin:
    """Mixin providing perception capabilities for UnifiedOrganism."""

    # These attributes are set by the main UnifiedOrganism class
    _perception_module: Any
    _perception_enabled: bool

    def set_perception_module(self, module: Any) -> None:
        """Connect perception module for unified sensory processing.

        LECUN ARCHITECTURE: "The perception module estimates the current state
        of the world from sensory signals."

        Args:
            module: PerceptionModule instance
        """
        self._perception_module = module
        logger.info("Perception module connected. I can now observe.")

    def get_perception_module(self) -> Any | None:
        """Get or create the perception module.

        Lazy loads PerceptionModule if not already initialized.

        Returns:
            PerceptionModule instance
        """
        if self._perception_module is None and self._perception_enabled:
            try:
                from kagami.core.perception.perception_module import get_perception_module

                self._perception_module = get_perception_module()
                logger.info("Perception module initialized (lazy)")
            except ImportError as e:
                logger.debug(f"Perception module unavailable: {e}")
                self._perception_enabled = False

        return self._perception_module

    async def perceive(
        self,
        sensors: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Unified perception API.

        Processes sensory input through the perception module and returns
        a unified perceptual state that can inform routing decisions.

        LECUN INTEGRATION: Observation -> Perception -> World Model -> Routing

        Args:
            sensors: Dict with optional keys:
                - 'image': [B, C, H, W] images
                - 'audio': [B, T] audio waveform
                - 'text': List[str] text
                - 'proprio': [B, proprio_dim] internal state
            context: Additional context for perception

        Returns:
            Dict with:
                - 'state': [B, state_dim] unified perceptual state
                - 'modalities_present': list of modalities that had input
                - 'perception_time_ms': processing time
        """
        start = time_module.time()
        context = context or {}
        sensors = sensors or {}

        # Get or initialize perception module
        perception = self.get_perception_module()
        if perception is None:
            return {
                "state": None,
                "modalities_present": [],
                "perception_time_ms": 0,
                "perception_enabled": False,
            }

        # Track which modalities are present
        modalities_present = []
        if sensors.get("image") is not None:
            modalities_present.append("vision")
        if sensors.get("audio") is not None:
            modalities_present.append("audio")
        if sensors.get("text") is not None:
            modalities_present.append("text")
        if sensors.get("proprio") is not None:
            modalities_present.append("proprio")

        # If no sensors provided, use text context as default modality
        if not sensors and context:
            # Convert context to text description for perception
            import json

            context_text = json.dumps(context, default=str)[:1000]
            sensors = {"text": [context_text]}
            modalities_present = ["text"]

        # Run perception
        try:
            state = perception.perceive(sensors)
            perception_time_ms = (time_module.time() - start) * 1000

            return {
                "state": state,
                "modalities_present": modalities_present,
                "perception_time_ms": perception_time_ms,
                "perception_enabled": True,
            }
        except Exception as e:
            logger.debug(f"Perception failed: {e}")
            return {
                "state": None,
                "modalities_present": modalities_present,
                "perception_time_ms": (time_module.time() - start) * 1000,
                "perception_enabled": True,
                "error": str(e),
            }


__all__ = ["PerceptionMixin"]
