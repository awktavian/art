"""visionOS Gaze Tracking Adapter.

Provides eye/gaze tracking capabilities for Apple Vision Pro.

Supports:
- Gaze direction
- Dwell detection
- Attention tracking

Note: Gaze data requires user permission and is privacy-sensitive.
This adapter only receives aggregate/processed gaze data from the
visionOS client, not raw eye tracking data.

Created: December 30, 2025
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from kagami.core.boot_mode import is_test_mode

logger = logging.getLogger(__name__)


@dataclass
class GazeTarget:
    """Represents what the user is looking at."""

    target_type: str  # "ui_element", "spatial_anchor", "world"
    target_id: str | None  # ID of the target if applicable
    direction: tuple[float, float, float]  # normalized gaze direction
    confidence: float  # 0.0-1.0
    dwell_duration_ms: int  # how long user has been looking


GazeCallback = Callable[[GazeTarget], Awaitable[None]]


class VisionOSGaze:
    """visionOS gaze tracking adapter.

    Provides processed gaze information from the visionOS client.
    Raw eye tracking data stays on-device for privacy.
    """

    def __init__(self) -> None:
        self._current_target: GazeTarget | None = None
        self._callbacks: list[GazeCallback] = []
        self._api_base_url: str | None = None
        self._tracking_enabled = False

    async def initialize(self, api_base_url: str = "http://kagami.local:8001") -> bool:
        """Initialize gaze tracking adapter.

        Args:
            api_base_url: Base URL of the Kagami API

        Returns:
            True if initialization successful
        """
        self._api_base_url = api_base_url

        if is_test_mode():
            logger.info("visionOS Gaze adapter in test mode")
            return True

        logger.info("✅ visionOS Gaze adapter initialized")
        return True

    async def start_tracking(self) -> bool:
        """Start receiving gaze updates.

        Returns:
            True if tracking started
        """
        if not self._api_base_url:
            return False

        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self._api_base_url}/api/vision/gaze/start") as response:
                    if response.status == 200:
                        self._tracking_enabled = True
                        logger.info("Gaze tracking started")
                        return True
        except Exception as e:
            logger.error(f"Failed to start gaze tracking: {e}")

        return False

    async def stop_tracking(self) -> None:
        """Stop receiving gaze updates."""
        self._tracking_enabled = False

        if self._api_base_url:
            try:
                import aiohttp

                async with aiohttp.ClientSession() as session:
                    await session.post(f"{self._api_base_url}/api/vision/gaze/stop")
            except Exception as e:
                logger.debug(f"Failed to stop gaze tracking: {e}")

        logger.info("Gaze tracking stopped")

    async def get_current_target(self) -> GazeTarget | None:
        """Get what the user is currently looking at.

        Returns:
            Current gaze target or None
        """
        if not self._tracking_enabled or not self._api_base_url:
            return self._current_target

        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self._api_base_url}/api/vision/gaze/current") as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("target"):
                            self._current_target = GazeTarget(
                                target_type=data["target"].get("type", "world"),
                                target_id=data["target"].get("id"),
                                direction=tuple(data["target"].get("direction", [0, 0, -1])),
                                confidence=data["target"].get("confidence", 0.0),
                                dwell_duration_ms=data["target"].get("dwell_ms", 0),
                            )
        except Exception as e:
            logger.debug(f"Failed to get gaze target: {e}")

        return self._current_target

    async def subscribe(self, callback: GazeCallback) -> None:
        """Subscribe to gaze updates.

        Args:
            callback: Async function to call with gaze updates
        """
        self._callbacks.append(callback)

    async def unsubscribe(self, callback: GazeCallback) -> None:
        """Unsubscribe from gaze updates.

        Args:
            callback: Previously subscribed callback
        """
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    async def is_looking_at(self, target_id: str) -> bool:
        """Check if user is looking at a specific target.

        Args:
            target_id: ID of target to check

        Returns:
            True if user is looking at the target
        """
        target = await self.get_current_target()
        if target and target.target_id == target_id:
            return target.confidence > 0.7
        return False

    async def get_dwell_duration(self) -> int:
        """Get how long user has been looking at current target.

        Returns:
            Duration in milliseconds
        """
        target = await self.get_current_target()
        return target.dwell_duration_ms if target else 0

    async def shutdown(self) -> None:
        """Shutdown gaze tracking."""
        await self.stop_tracking()
        self._callbacks.clear()
        logger.info("visionOS Gaze adapter shutdown")


"""
Mirror
h(x) >= 0. Always.

Where you look is where you are.
Attention is intention.
"""
