"""Unified Sensory Integration - SENSE LAYER of the Predictive Hierarchy.

This module is a facade that re-exports from the sensory subpackage.
The actual implementation is in packages/kagami/core/integrations/sensory/.

ARCHITECTURE:
=============
The sensory system is decomposed into focused modules:
    - sensory/base.py: Core types (SenseType, SenseConfig, CachedSense)
    - sensory/environmental.py: Weather, world state, situation awareness
    - sensory/biometric.py: Sleep, health, Apple Health integration
    - sensory/digital.py: Email, calendar, github, linear, slack, figma
    - sensory/home.py: Presence, locks, climate, security, cameras
    - sensory/vehicle.py: Tesla integration
    - sensory/patterns.py: Pattern learning and prediction
    - sensory/aggregator.py: Main UnifiedSensoryIntegration class

Usage:
    from kagami.core.integrations.unified_sensory import (
        get_unified_sensory,
        initialize_unified_sensory,
        SenseType,
    )
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

# Re-export everything from sensory subpackage
from kagami.core.integrations.sensory import (
    ADAPTIVE_CONFIGS,
    DEFAULT_SENSE_CONFIGS,
    ActivityLevel,
    AdaptiveConfig,
    CachedSense,
    SenseConfig,
    SenseEventCallback,
    SenseType,
    UnifiedSensoryIntegration,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# =============================================================================
# SINGLETON
# =============================================================================


_unified_sensory: UnifiedSensoryIntegration | None = None


def get_unified_sensory() -> UnifiedSensoryIntegration:
    """Get global UnifiedSensoryIntegration instance."""
    global _unified_sensory
    if _unified_sensory is None:
        _unified_sensory = UnifiedSensoryIntegration()
    return _unified_sensory


async def initialize_unified_sensory(
    with_alerts: bool = True,
    with_consciousness: bool = True,
) -> UnifiedSensoryIntegration:
    """Initialize and return the unified sensory integration.

    Connects to both Composio and SmartHome if available.
    Wires AlertHierarchy and OrganismConsciousness if requested.

    Args:
        with_alerts: Wire AlertHierarchy for auto-alerts
        with_consciousness: Wire OrganismConsciousness for perception updates
    """
    sensory = get_unified_sensory()

    if sensory._initialized:
        return sensory

    # Get services
    composio = None
    smart_home = None

    try:
        from kagami.core.services.composio import get_composio_service

        composio = get_composio_service()
    except Exception as e:
        logger.debug(f"Composio not available: {e}")

    try:
        from kagami_smarthome import get_smart_home

        smart_home = await get_smart_home()
    except Exception as e:
        logger.debug(f"SmartHome not available: {e}")

    await sensory.initialize(composio, smart_home)

    # Wire AlertHierarchy
    if with_alerts:
        try:
            from kagami.core.integrations.alert_hierarchy import get_alert_hierarchy

            alert_hierarchy = get_alert_hierarchy()
            sensory.set_alert_hierarchy(alert_hierarchy)
        except Exception as e:
            logger.debug(f"AlertHierarchy not available: {e}")

    # Wire OrganismConsciousness
    if with_consciousness:
        try:
            from kagami.core.unified_agents.unified_organism_state import get_unified_consciousness

            consciousness = get_unified_consciousness()
            sensory.set_consciousness(consciousness)
        except Exception as e:
            logger.debug(f"OrganismConsciousness not available: {e}")

    return sensory


def reset_unified_sensory() -> None:
    """Reset the singleton (for testing)."""
    global _unified_sensory
    if _unified_sensory:
        _unified_sensory._running = False
    _unified_sensory = None


__all__ = [
    "ADAPTIVE_CONFIGS",
    "DEFAULT_SENSE_CONFIGS",
    "ActivityLevel",
    "AdaptiveConfig",
    "CachedSense",
    "SenseConfig",
    "SenseEventCallback",
    "SenseType",
    "UnifiedSensoryIntegration",
    "get_unified_sensory",
    "initialize_unified_sensory",
    "reset_unified_sensory",
]
