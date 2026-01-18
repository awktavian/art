"""Sensorimotor Bridge — The Closed Loop.

This module provides the critical bridge that closes the sensorimotor loop:

    Sense → Encode → WorldModel.step() → Predict → Decode → Act

Without this bridge, the world model is disconnected from sensory reality.
This is THE missing piece identified in the December 30, 2025 architecture review.

Architecture:
    UnifiedSensoryIntegration
            │
            │ _emit_change()
            ▼
    SensorimotorBridge
            │
            ├── SensoryToWorldModel.forward(perception)
            │           │
            │           ▼
            │       E8 code [8] + S7 phase [7]
            │           │
            │           ▼
            └── OrganismRSSM.step_all(e8_code, s7_phase)
                        │
                        ▼
                Updated world model state (h, z)
                        │
                        ▼
                MotorDecoder (optional autonomous action)

Created: December 30, 2025
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import torch

if TYPE_CHECKING:
    from kagami.core.integrations.unified_sensory import (
        SenseType,
        UnifiedSensoryIntegration,
    )
    from kagami.core.world_model.rssm_core import OrganismRSSM
    from kagami.core.world_model.sensory_encoder import SensoryToWorldModel

logger = logging.getLogger(__name__)


@dataclass
class WorldModelState:
    """Current state of the world model after stepping."""

    h_state: torch.Tensor | None = None  # Deterministic [B, 7, H]
    z_state: torch.Tensor | None = None  # Stochastic [B, 7, Z]
    e8_code: torch.Tensor | None = None  # Last E8 perception [B, 8]
    s7_phase: torch.Tensor | None = None  # Last S7 routing [B, 7]
    prediction: torch.Tensor | None = None  # Predicted next state
    timestamp: float = field(default_factory=time.time)
    sense_type: str = ""  # Which sense triggered this update


class SensorimotorBridge:
    """Bridge connecting sensory perception to world model dynamics.

    This class:
    1. Subscribes to UnifiedSensoryIntegration events
    2. Encodes perception vectors to E8/S7 via SensoryToWorldModel
    3. Steps the OrganismRSSM with each new perception
    4. Optionally decodes to motor commands for autonomous action

    Args:
        sensory: UnifiedSensoryIntegration instance
        encoder: SensoryToWorldModel instance (optional, created if None)
        rssm: OrganismRSSM instance (optional, created if None)
        device: Torch device for computation
        enable_motor_decode: Whether to decode motor commands after RSSM step
        step_interval_ms: Minimum interval between RSSM steps (throttling)
    """

    def __init__(
        self,
        sensory: UnifiedSensoryIntegration | None = None,
        encoder: SensoryToWorldModel | None = None,
        rssm: OrganismRSSM | None = None,
        device: str = "cpu",
        enable_motor_decode: bool = False,
        step_interval_ms: float = 100.0,
    ):
        self._sensory = sensory
        self._encoder = encoder
        self._rssm = rssm
        self._device = device
        self._enable_motor_decode = enable_motor_decode
        self._step_interval_ms = step_interval_ms

        # State tracking
        self._last_step_time: float = 0.0
        self._state = WorldModelState()
        self._step_count: int = 0
        self._subscribed: bool = False

        # Previous action (for RSSM conditioning)
        self._prev_action: torch.Tensor | None = None

        # Perception buffer (for batch stepping)
        self._perception_buffer: list[tuple[str, torch.Tensor]] = []
        self._max_buffer_size: int = 10

        logger.info(
            f"SensorimotorBridge initialized: device={device}, "
            f"motor_decode={enable_motor_decode}, interval={step_interval_ms}ms"
        )

    async def initialize(self) -> None:
        """Initialize all components and subscribe to sensory events."""
        # Lazy load components
        if self._sensory is None:
            from kagami.core.integrations import get_unified_sensory

            self._sensory = get_unified_sensory()

        if self._encoder is None:
            from kagami.core.world_model import get_sensory_encoder

            self._encoder = get_sensory_encoder(self._device)

        if self._rssm is None:
            from kagami.core.world_model import get_organism_rssm

            self._rssm = get_organism_rssm()

        # Subscribe to sensory events
        if not self._subscribed and self._sensory is not None:
            self._sensory.subscribe(self._on_sense_change)
            self._subscribed = True
            logger.info("✅ SensorimotorBridge subscribed to UnifiedSensory events")

    async def _on_sense_change(
        self,
        sense_type: SenseType,
        data: dict[str, Any],
        delta: dict[str, Any],
    ) -> None:
        """Handle sensory change event — this is the main integration point.

        Called by UnifiedSensoryIntegration._emit_change() for every sense update.
        """
        try:
            # Throttle stepping
            now = time.time() * 1000
            if (now - self._last_step_time) < self._step_interval_ms:
                # Buffer perception for later
                self._buffer_perception(sense_type.value, data)
                return

            # Encode perception to E8/S7
            perception = await self._build_perception_vector(sense_type.value, data)
            if perception is None:
                return

            # Step world model
            await self._step_world_model(sense_type.value, perception)

            self._last_step_time = now

        except Exception as e:
            logger.error(f"Sensorimotor bridge error on {sense_type}: {e}", exc_info=True)

    def _buffer_perception(self, sense_type: str, data: dict[str, Any]) -> None:
        """Buffer perception for batch processing."""
        try:
            from kagami.core.integrations import SenseType as ST
            from kagami.core.integrations import get_unified_sensory

            sensory = get_unified_sensory()
            sense_enum = ST(sense_type)
            perception_list = sensory._encode_to_perception(sense_enum, data)

            if perception_list is not None:
                perception = torch.tensor(perception_list, device=self._device)
                self._perception_buffer.append((sense_type, perception))

                # Limit buffer size
                if len(self._perception_buffer) > self._max_buffer_size:
                    self._perception_buffer = self._perception_buffer[-self._max_buffer_size :]

        except Exception as e:
            logger.debug(f"Failed to buffer perception: {e}")

    async def _build_perception_vector(
        self,
        sense_type: str,
        data: dict[str, Any],
    ) -> torch.Tensor | None:
        """Build 512D perception vector from sense data."""
        try:
            from kagami.core.integrations import SenseType as ST
            from kagami.core.integrations import get_unified_sensory

            sensory = get_unified_sensory()
            sense_enum = ST(sense_type)

            # Get perception encoding from unified sensory
            perception_list = sensory._encode_to_perception(sense_enum, data)

            if perception_list is None:
                logger.debug(f"No perception encoding for {sense_type}")
                return None

            return torch.tensor(perception_list, device=self._device, dtype=torch.float32)

        except Exception as e:
            logger.warning(f"Failed to build perception vector: {e}")
            return None

    async def _step_world_model(
        self,
        sense_type: str,
        perception: torch.Tensor,
    ) -> WorldModelState:
        """Step the world model with new perception.

        This is the CORE of the closed loop.
        """
        if self._encoder is None or self._rssm is None:
            logger.warning("Encoder or RSSM not initialized")
            return self._state

        try:
            # Encode perception to E8/S7
            e8_code, s7_phase = self._encoder(perception)

            # Ensure proper batch dimension
            if e8_code.dim() == 1:
                e8_code = e8_code.unsqueeze(0)
            if s7_phase.dim() == 1:
                s7_phase = s7_phase.unsqueeze(0)

            # Get previous action (or zeros)
            if self._prev_action is None:
                action_dim = getattr(self._rssm, "action_dim", 8)
                self._prev_action = torch.zeros(1, action_dim, device=self._device)

            # Step RSSM
            result = self._rssm.step_all(
                e8_code=e8_code,
                s7_phase=s7_phase,
                action_prev=self._prev_action,
            )

            # Update state
            self._state = WorldModelState(
                h_state=result.get("h_next"),
                z_state=result.get("z_next"),
                e8_code=e8_code,
                s7_phase=s7_phase,
                prediction=result.get("prediction"),
                timestamp=time.time(),
                sense_type=sense_type,
            )

            self._step_count += 1

            # Log periodically
            if self._step_count % 100 == 0:
                logger.info(
                    f"SensorimotorBridge: {self._step_count} steps, last sense={sense_type}"
                )

            # Optional: decode motor commands
            if self._enable_motor_decode:
                await self._decode_motor_commands(result)

            return self._state

        except Exception as e:
            logger.error(f"World model step failed: {e}", exc_info=True)
            return self._state

    async def _decode_motor_commands(self, rssm_result: dict[str, Any]) -> None:
        """Decode motor commands and execute via UnifiedActionExecutor.

        This is the full closed loop:
        RSSM output → MotorDecoder → UnifiedActionExecutor → Environment

        All three action paths (digital, smarthome, meta) are equally wired.
        """
        try:
            from kagami.core.embodiment import get_motor_decoder
            from kagami.core.embodiment.unified_action_executor import (
                ExecutionContext,
                get_unified_action_executor,
            )

            decoder = get_motor_decoder()
            executor = get_unified_action_executor()

            # Initialize executor if needed
            if not executor._initialized:
                await executor.initialize()

            # Get predicted state
            h_next = rssm_result.get("h_next")
            if h_next is None:
                return

            # Decode to motor commands (all heads: digital, smarthome, meta)
            motor_output = decoder(h_next)

            # Get best action across ALL heads
            best = decoder.get_best_action_across_heads(motor_output)

            # Only execute if confidence is above threshold
            confidence_threshold = 0.5  # Require reasonable confidence for autonomous action

            if best["confidence"] > confidence_threshold:
                logger.info(
                    f"Motor decode: {best['head']}/{best['action']} "
                    f"(confidence={best['confidence']:.2f})"
                )

                # Execute via unified executor
                ctx = ExecutionContext(
                    confidence_threshold=confidence_threshold,
                    allow_llm_fallback=True,
                )

                result = await executor.execute_from_decoder(motor_output, ctx)

                if result.success:
                    logger.info(f"✅ Action executed: {result.action_type}/{result.action_name}")

                    # Update previous action for next RSSM step
                    self._prev_action = torch.zeros(1, 8, device=self._device)
                    # Encode the action type as a simple one-hot-ish encoding
                    action_type_idx = {"digital": 0, "smarthome": 1, "meta": 2}.get(
                        result.action_type, 3
                    )
                    if action_type_idx < 8:
                        self._prev_action[0, action_type_idx] = 1.0
                else:
                    logger.debug(f"Action execution failed: {result.error}")
            else:
                logger.debug(f"Low confidence ({best['confidence']:.2f}), skipping action")

        except Exception as e:
            logger.debug(f"Motor decode failed: {e}")

    def get_state(self) -> WorldModelState:
        """Get current world model state."""
        return self._state

    def get_stats(self) -> dict[str, Any]:
        """Get bridge statistics."""
        return {
            "step_count": self._step_count,
            "subscribed": self._subscribed,
            "buffer_size": len(self._perception_buffer),
            "last_sense": self._state.sense_type,
            "last_timestamp": self._state.timestamp,
            "has_h_state": self._state.h_state is not None,
            "has_z_state": self._state.z_state is not None,
        }

    async def shutdown(self) -> None:
        """Clean shutdown."""
        self._subscribed = False
        self._perception_buffer.clear()
        logger.info(f"SensorimotorBridge shutdown: {self._step_count} total steps")


# =============================================================================
# Global Instance
# =============================================================================

_bridge: SensorimotorBridge | None = None


def get_sensorimotor_bridge() -> SensorimotorBridge:
    """Get global SensorimotorBridge instance."""
    global _bridge

    if _bridge is None:
        _bridge = SensorimotorBridge()

    return _bridge


async def initialize_sensorimotor_bridge(
    sensory: UnifiedSensoryIntegration | None = None,
    device: str = "cpu",
    enable_motor_decode: bool = False,
) -> SensorimotorBridge:
    """Initialize and return the global sensorimotor bridge.

    This should be called during system startup to connect
    sensory perception to the world model.

    Args:
        sensory: UnifiedSensoryIntegration instance (optional)
        device: Torch device
        enable_motor_decode: Enable autonomous motor decoding

    Returns:
        Initialized SensorimotorBridge
    """
    global _bridge

    _bridge = SensorimotorBridge(
        sensory=sensory,
        device=device,
        enable_motor_decode=enable_motor_decode,
    )
    await _bridge.initialize()

    logger.info("✅ SensorimotorBridge initialized and connected to UnifiedSensory")
    return _bridge


def reset_sensorimotor_bridge() -> None:
    """Reset global instance (for testing)."""
    global _bridge
    _bridge = None


__all__ = [
    "SensorimotorBridge",
    "WorldModelState",
    "get_sensorimotor_bridge",
    "initialize_sensorimotor_bridge",
    "reset_sensorimotor_bridge",
]
