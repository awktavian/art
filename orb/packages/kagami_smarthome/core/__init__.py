"""Core controller modules for the Smart Home Controller.

Extracted modules to reduce controller.py from 4000+ LOC to <500 LOC:
- IntegrationManager: Discovery, reconnection, health, failover
- StateManager: Home state, presence, organism state
- IntegrationBase: Abstract base class for all integrations

Created: January 2, 2026
Updated: January 7, 2026 - Removed duplicate SceneOrchestrator (use RoomOrchestrator)
Updated: January 12, 2026 - Added IntegrationBase abstraction
"""

from kagami_smarthome.core.connection_manager import ConnectionManager
from kagami_smarthome.core.device_controller import DeviceController
from kagami_smarthome.core.integration_base import (
    HealthLevel,
    HealthStatus,
    IntegrationBase,
    PollingIntegrationBase,
    WebSocketIntegrationBase,
)
from kagami_smarthome.core.integration_manager import IntegrationManager
from kagami_smarthome.core.performance_optimizer import PerformanceOptimizer
from kagami_smarthome.core.state_manager import StateManager

__all__ = [
    # Base classes
    "HealthLevel",
    "HealthStatus",
    "IntegrationBase",
    "PollingIntegrationBase",
    "WebSocketIntegrationBase",
    # Managers
    "ConnectionManager",
    "DeviceController",
    "IntegrationManager",
    "PerformanceOptimizer",
    "StateManager",
]
