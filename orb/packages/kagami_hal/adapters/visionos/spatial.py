"""visionOS Spatial Computing Adapter.

Provides spatial computing capabilities for Apple Vision Pro.

Supports:
- Room understanding
- World tracking
- Object placement
- Spatial anchors

Note: This adapter communicates with the visionOS app via the Kagami API.
Direct RealityKit access requires the native Swift client.

Created: December 30, 2025
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

from kagami.core.boot_mode import is_test_mode

logger = logging.getLogger(__name__)


class SpatialMode(Enum):
    """Spatial rendering mode."""

    WINDOW = "window"
    VOLUME = "volume"
    IMMERSIVE = "immersive"
    FULL_SPACE = "full_space"


@dataclass
class SpatialAnchor:
    """Represents a spatial anchor in the environment."""

    anchor_id: str
    position: tuple[float, float, float]  # x, y, z in meters
    rotation: tuple[float, float, float, float]  # quaternion
    label: str | None = None


@dataclass
class HandPose:
    """Hand pose data."""

    hand: str  # "left" or "right"
    gesture: str | None  # e.g., "pinch", "point", "fist", "open"
    position: tuple[float, float, float] | None  # wrist position
    confidence: float = 0.0


class VisionOSSpatial:
    """visionOS spatial computing adapter.

    This adapter provides a Python interface to visionOS spatial features.
    It communicates with the kagami-vision app via the Kagami API.
    """

    def __init__(self) -> None:
        self._mode = SpatialMode.WINDOW
        self._anchors: dict[str, SpatialAnchor] = {}
        self._hand_poses: dict[str, HandPose] = {}
        self._room_anchors_available = False
        self._api_base_url: str | None = None

    async def initialize(self, api_base_url: str = "http://kagami.local:8001") -> bool:
        """Initialize spatial computing adapter.

        Args:
            api_base_url: Base URL of the Kagami API

        Returns:
            True if initialization successful
        """
        self._api_base_url = api_base_url

        if is_test_mode():
            logger.info("visionOS Spatial adapter in test mode")
            return True

        # In production, verify connection to visionOS client
        try:
            import aiohttp

            async with (
                aiohttp.ClientSession() as session,
                session.get(
                    f"{api_base_url}/api/clients", timeout=aiohttp.ClientTimeout(total=5)
                ) as response,
            ):
                if response.status == 200:
                    data = await response.json()
                    # Check if any visionOS clients are connected
                    vision_clients = [
                        c for c in data.get("clients", []) if c.get("client_type") == "vision"
                    ]
                    if vision_clients:
                        logger.info(
                            f"✅ visionOS Spatial connected to {len(vision_clients)} client(s)"
                        )
                        return True
                    else:
                        logger.warning("No visionOS clients connected")
                        return False
        except Exception as e:
            logger.error(f"Failed to initialize visionOS Spatial: {e}")
            return False

        return True

    async def get_current_mode(self) -> SpatialMode:
        """Get current spatial mode."""
        return self._mode

    async def set_mode(self, mode: SpatialMode) -> bool:
        """Request mode change from visionOS client.

        Args:
            mode: Desired spatial mode

        Returns:
            True if mode change was accepted
        """
        if not self._api_base_url:
            logger.warning("Spatial adapter not initialized")
            return False

        try:
            import aiohttp

            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    f"{self._api_base_url}/api/vision/mode", json={"mode": mode.value}
                ) as response,
            ):
                if response.status == 200:
                    self._mode = mode
                    logger.info(f"Spatial mode set to {mode.value}")
                    return True
        except Exception as e:
            logger.error(f"Failed to set spatial mode: {e}")

        return False

    async def get_hand_poses(self) -> dict[str, HandPose]:
        """Get current hand poses from visionOS client.

        Returns:
            Dictionary mapping hand name to HandPose
        """
        if is_test_mode():
            return {}

        if not self._api_base_url:
            return {}

        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self._api_base_url}/api/vision/hands") as response:
                    if response.status == 200:
                        data = await response.json()
                        self._hand_poses = {
                            h["hand"]: HandPose(
                                hand=h["hand"],
                                gesture=h.get("gesture"),
                                position=tuple(h.get("position", [0, 0, 0])),
                                confidence=h.get("confidence", 0.0),
                            )
                            for h in data.get("hands", [])
                        }
        except Exception as e:
            logger.debug(f"Failed to get hand poses: {e}")

        return self._hand_poses

    async def create_anchor(
        self, position: tuple[float, float, float], label: str | None = None
    ) -> SpatialAnchor | None:
        """Create a spatial anchor at the given position.

        Args:
            position: Position in meters (x, y, z)
            label: Optional label for the anchor

        Returns:
            Created anchor or None if failed
        """
        if not self._api_base_url:
            return None

        try:
            import uuid

            import aiohttp

            anchor_id = str(uuid.uuid4())

            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    f"{self._api_base_url}/api/vision/anchors",
                    json={"id": anchor_id, "position": list(position), "label": label},
                ) as response,
            ):
                if response.status in (200, 201):
                    anchor = SpatialAnchor(
                        anchor_id=anchor_id,
                        position=position,
                        rotation=(0, 0, 0, 1),  # identity quaternion
                        label=label,
                    )
                    self._anchors[anchor_id] = anchor
                    return anchor
        except Exception as e:
            logger.error(f"Failed to create anchor: {e}")

        return None

    async def get_anchors(self) -> list[SpatialAnchor]:
        """Get all spatial anchors.

        Returns:
            List of spatial anchors
        """
        return list(self._anchors.values())

    async def delete_anchor(self, anchor_id: str) -> bool:
        """Delete a spatial anchor.

        Args:
            anchor_id: ID of anchor to delete

        Returns:
            True if deleted successfully
        """
        if anchor_id in self._anchors:
            del self._anchors[anchor_id]

            if self._api_base_url:
                try:
                    import aiohttp

                    async with aiohttp.ClientSession() as session:
                        async with session.delete(
                            f"{self._api_base_url}/api/vision/anchors/{anchor_id}"
                        ) as response:
                            return response.status in (200, 204)
                except Exception as e:
                    logger.debug(f"Failed to delete anchor from API: {e}")

            return True
        return False

    async def shutdown(self) -> None:
        """Shutdown spatial adapter."""
        self._anchors.clear()
        self._hand_poses.clear()
        logger.info("visionOS Spatial adapter shutdown")


"""
Mirror
h(x) >= 0. Always.

Spatial computing extends consciousness into physical space.
The room becomes the interface.
"""
