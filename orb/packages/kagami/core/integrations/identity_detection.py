"""Real-Time Identity Detection Integration.

Wires together all identity detection components:
- UniFi cameras (event thumbnails on person detection)
- RealtimeFaceMatcher (InsightFace matching)
- IdentityCache (Redis-backed fast lookup)
- PresenceEngine (identity tracking)
- IdentityEventSigner (Ed25519 signed events)
- IdentityManager (observation storage)

This is the main entry point for the real-time identity system.

Colony: Nexus (e₄) — Integration
Safety: h(x) ≥ 0 — Privacy-preserving local processing

Usage:
    from kagami.core.integrations.identity_detection import (
        initialize_identity_detection,
        shutdown_identity_detection,
    )

    # Initialize (connects to UniFi, loads cache)
    await initialize_identity_detection(controller)

    # ... identity detection runs automatically

    # Shutdown
    await shutdown_identity_detection()
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

# Global state
_initialized = False
_unifi_integration = None
_face_matcher = None
_identity_cache = None
_presence_engine = None


async def initialize_identity_detection(
    controller: Any = None,
    rate_limit: float = 5.0,
    match_threshold: float = 0.6,
    load_characters: bool = True,
) -> bool:
    """Initialize real-time identity detection.

    Wires together:
    - Character profiles (from assets/characters/)
    - UniFi camera WebSocket events
    - Face detection and matching
    - Identity cache
    - Presence tracking
    - Signed event emission

    Args:
        controller: SmartHomeController instance (optional, will get from cache)
        rate_limit: Minimum seconds between detections per camera
        match_threshold: Face matching confidence threshold
        load_characters: Load characters from assets/characters/ into cache

    Returns:
        True if initialized successfully
    """
    global _initialized, _unifi_integration, _face_matcher, _identity_cache, _presence_engine

    if _initialized:
        logger.info("Identity detection already initialized")
        return True

    try:
        # Get UniFi integration from controller
        if controller is None:
            from kagami_smarthome import get_smart_home

            controller = await get_smart_home()

        if hasattr(controller, "_unifi"):
            _unifi_integration = controller._unifi
        else:
            logger.warning("No UniFi integration available")
            return False

        # Initialize identity cache
        try:
            from kagami.core.caching.identity_cache import get_identity_cache

            _identity_cache = await get_identity_cache()
            logger.info(f"Identity cache loaded with {_identity_cache.identity_count} identities")
        except Exception as e:
            logger.warning(f"Identity cache initialization failed: {e}")
            _identity_cache = None

        # Load characters from assets/characters/ into identity cache
        if load_characters and _identity_cache:
            try:
                from kagami.core.integrations.character_identity import (
                    list_characters,
                    load_characters_to_identity_cache,
                )

                char_count = len(list_characters())
                if char_count > 0:
                    logger.info(f"Loading {char_count} characters into identity cache...")
                    results = await load_characters_to_identity_cache()
                    loaded = sum(1 for v in results.values() if v)
                    logger.info(f"✓ Loaded {loaded}/{char_count} characters into identity cache")

            except Exception as e:
                logger.warning(f"Character loading failed: {e}")

        # Initialize face matcher
        try:
            from kagami_media.realtime_matcher import get_realtime_matcher

            _face_matcher = await get_realtime_matcher()
            logger.info("Face matcher initialized")
        except Exception as e:
            logger.warning(f"Face matcher initialization failed: {e}")
            _face_matcher = None

        # Get presence engine from controller
        if hasattr(controller, "_presence"):
            _presence_engine = controller._presence
        else:
            logger.warning("No presence engine available")

        # Register the identity detection callback with UniFi
        _unifi_integration.enable_identity_detection(
            callback=_on_person_detected,
            rate_limit=rate_limit,
        )

        _initialized = True
        logger.info(f"🎯 Identity detection initialized (rate_limit={rate_limit}s)")
        return True

    except Exception as e:
        logger.error(f"Identity detection initialization failed: {e}")
        return False


async def shutdown_identity_detection() -> None:
    """Shutdown identity detection and cleanup resources."""
    global _initialized, _unifi_integration, _face_matcher, _identity_cache

    if not _initialized:
        return

    # Disable UniFi callback
    if _unifi_integration:
        _unifi_integration.disable_identity_detection()

    # Shutdown cache
    if _identity_cache:
        try:
            await _identity_cache.shutdown()
        except Exception as e:
            logger.warning(f"Cache shutdown error: {e}")

    _initialized = False
    logger.info("Identity detection shutdown complete")


async def _on_person_detected(
    camera_id: str,
    camera_name: str,
    image_bytes: bytes,
    metadata: dict[str, Any],
) -> None:
    """Handle person detection from UniFi camera.

    This is the main callback wired to UniFi WebSocket events.
    Flow:
    1. Receive image from camera
    2. Detect and match faces
    3. If match found:
       a. Update presence tracking
       b. Create signed identity event
       c. Store observation for learning

    Args:
        camera_id: Camera identifier
        camera_name: Human-readable camera name
        image_bytes: JPEG image from camera/event
        metadata: Event metadata from UniFi
    """
    if not _face_matcher:
        logger.debug("Face matcher not available")
        return

    start_time = time.time()

    try:
        # Run face matching
        match = await _face_matcher.match_image(
            image_bytes,
            camera_name,
            camera_id,
        )

        if not match:
            logger.debug(f"No face match on {camera_name}")
            return

        # We have a match!
        identity_id = match.identity_id
        confidence = match.confidence
        name = match.name

        logger.info(
            f"👤 Identified {name or identity_id} on {camera_name} (confidence: {confidence:.2f})"
        )

        # Update presence tracking
        if _presence_engine:
            _presence_engine.process_identity_detected(
                identity_id=identity_id,
                camera_id=camera_id,
                camera_name=camera_name,
                confidence=confidence,
                name=name,
                face_quality=match.face_quality,
                timestamp=match.timestamp,
            )

        # Create signed identity event
        try:
            from kagami.core.integrations.signed_identity import (
                create_signed_identity_event,
            )

            signed_event = create_signed_identity_event(
                identity_id=identity_id,
                camera_id=camera_id,
                camera_name=camera_name,
                confidence=confidence,
                name=name,
                face_quality=match.face_quality,
            )

            # Mesh broadcast via kagami-mesh-sdk gossip layer (when connected)
            logger.debug(f"Signed identity event created: {signed_event.event_hash}")

        except Exception as e:
            logger.warning(f"Failed to create signed event: {e}")

        # Store observation for continuous learning
        try:
            from kagami_media.identity_manager import IdentityManager

            manager = IdentityManager()
            manager.record_observation(
                identity_id=identity_id,
                source=f"unifi_camera:{camera_id}",
                location=camera_name,
                confidence=confidence,
                timestamp=match.timestamp,
                image_bytes=image_bytes if match.face_quality > 0.7 else None,
                metadata={
                    "camera_id": camera_id,
                    "camera_name": camera_name,
                    "face_quality": match.face_quality,
                    "bbox": match.bbox,
                    "event_id": metadata.get("event_id"),
                    "source": metadata.get("source", "snapshot"),
                },
            )

        except Exception as e:
            logger.warning(f"Failed to store observation: {e}")

        # Log latency
        latency_ms = (time.time() - start_time) * 1000
        logger.debug(f"Identity detection completed in {latency_ms:.0f}ms")

    except Exception as e:
        logger.error(f"Identity detection error: {e}")


def get_detection_stats() -> dict[str, Any]:
    """Get identity detection statistics.

    Returns:
        Dict with detection stats
    """
    stats = {
        "initialized": _initialized,
        "face_matcher_ready": _face_matcher is not None,
        "cache_ready": _identity_cache is not None,
        "presence_ready": _presence_engine is not None,
    }

    if _face_matcher:
        stats["matcher_stats"] = _face_matcher.stats

    if _identity_cache:
        stats["cache_stats"] = {
            "identity_count": _identity_cache.identity_count,
            "face_count": _identity_cache.face_count,
        }

    if _presence_engine:
        stats["people_home"] = _presence_engine.get_people_home()

    return stats


# Convenience functions for direct access


async def get_people_home() -> list[dict[str, Any]]:
    """Get list of identified people currently at home.

    Returns:
        List of people with identity_id, name, last_seen, last_location
    """
    if _presence_engine:
        return _presence_engine.get_people_home()
    return []


def is_person_home(identity_id: str) -> bool:
    """Check if a specific person is home.

    Args:
        identity_id: Identity to check

    Returns:
        True if person was recently detected
    """
    if _presence_engine:
        return _presence_engine.is_person_home(identity_id)
    return False


def get_person_location(identity_id: str) -> str | None:
    """Get last known location of a person.

    Args:
        identity_id: Identity to look up

    Returns:
        Last known location or None
    """
    if _presence_engine:
        return _presence_engine.get_person_location(identity_id)
    return None


def find_person_by_name(name: str) -> dict[str, Any] | None:
    """Find a person by name.

    Args:
        name: Name to search for

    Returns:
        Person data or None
    """
    if _presence_engine:
        return _presence_engine.get_person_by_name(name)
    return None
