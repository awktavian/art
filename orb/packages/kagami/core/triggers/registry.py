"""Unified Trigger Registry — Single source of truth for all triggers.

CREATED: January 5, 2026
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import TYPE_CHECKING, Any

from .base import (
    TriggerExecutionResult,
    TriggerSourceType,
    UnifiedTrigger,
)

if TYPE_CHECKING:
    from kagami_smarthome import SmartHomeController

logger = logging.getLogger(__name__)


class TriggerRegistry:
    """Unified trigger registry — manages all triggers.

    Single source of truth for:
    - Sensory triggers (weather, email, presence)
    - Service triggers (GitHub, Linear, Slack)
    - Celestial triggers (sunset, sunrise)
    - Autonomous actions (morning routine, focus mode)

    Example:
        >>> registry = get_trigger_registry()
        >>> registry.register(my_trigger)
        >>> await registry.evaluate("weather", weather_data)
    """

    def __init__(self):
        self._triggers: dict[str, UnifiedTrigger] = {}
        self._by_source: dict[str, list[UnifiedTrigger]] = defaultdict(list)
        self._by_source_type: dict[TriggerSourceType, list[UnifiedTrigger]] = defaultdict(list)

        # Connected services
        self._smart_home: SmartHomeController | None = None
        self._sensory: Any | None = None

        # Metrics
        self._stats = {
            "triggers_registered": 0,
            "triggers_evaluated": 0,
            "triggers_fired": 0,
            "triggers_failed": 0,
        }

    def connect(self, smart_home: SmartHomeController, sensory: Any | None = None) -> None:
        """Connect to smart home and sensory systems.

        Args:
            smart_home: SmartHomeController for physical actions
            sensory: UnifiedSensoryIntegration for presence detection
        """
        self._smart_home = smart_home
        self._sensory = sensory
        logger.info("🔗 TriggerRegistry connected to SmartHome")

    def register(self, trigger: UnifiedTrigger) -> None:
        """Register a trigger.

        Args:
            trigger: UnifiedTrigger to register

        Raises:
            ValueError: If trigger name already exists
        """
        if trigger.name in self._triggers:
            raise ValueError(f"Trigger already registered: {trigger.name}")

        self._triggers[trigger.name] = trigger
        self._by_source[trigger.source].append(trigger)
        self._by_source_type[trigger.source_type].append(trigger)
        self._stats["triggers_registered"] += 1

        logger.debug(
            f"Registered trigger: {trigger.name} "
            f"({trigger.source_type.value}/{trigger.source}, "
            f"cooldown={trigger.cooldown}s)"
        )

    def unregister(self, name: str) -> bool:
        """Unregister a trigger.

        Args:
            name: Trigger name

        Returns:
            True if trigger was removed
        """
        if name not in self._triggers:
            return False

        trigger = self._triggers[name]
        del self._triggers[name]
        self._by_source[trigger.source].remove(trigger)
        self._by_source_type[trigger.source_type].remove(trigger)

        logger.debug(f"Unregistered trigger: {name}")
        return True

    def get(self, name: str) -> UnifiedTrigger | None:
        """Get trigger by name."""
        return self._triggers.get(name)

    def list_by_source(self, source: str) -> list[UnifiedTrigger]:
        """List all triggers for a given source."""
        return self._by_source.get(source, [])

    def list_by_source_type(self, source_type: TriggerSourceType) -> list[UnifiedTrigger]:
        """List all triggers of a given type."""
        return self._by_source_type.get(source_type, [])

    def list_all(self) -> list[UnifiedTrigger]:
        """List all registered triggers."""
        return list(self._triggers.values())

    async def evaluate(
        self, source: str, data: dict, *, force: bool = False
    ) -> list[TriggerExecutionResult]:
        """Evaluate all triggers for a given source.

        Args:
            source: Source identifier (e.g., "weather", "github")
            data: Trigger data
            force: Force evaluation even if on cooldown

        Returns:
            List of execution results
        """
        self._stats["triggers_evaluated"] += 1

        triggers = self._by_source.get(source, [])
        if not triggers:
            return []

        # Check presence if needed
        presence_home = await self._check_presence()

        results = []

        for trigger in triggers:
            # Skip if can't trigger (cooldown, presence, condition)
            if not force and not trigger.can_trigger(data, presence_home):
                continue

            # Execute trigger
            result = await self._execute_trigger(trigger, data)
            results.append(result)

        return results

    async def fire(self, name: str, data: dict) -> TriggerExecutionResult | None:
        """Manually fire a trigger by name.

        Args:
            name: Trigger name
            data: Trigger data

        Returns:
            Execution result or None if trigger not found
        """
        trigger = self._triggers.get(name)
        if not trigger:
            logger.warning(f"Trigger not found: {name}")
            return None

        return await self._execute_trigger(trigger, data)

    async def _execute_trigger(self, trigger: UnifiedTrigger, data: dict) -> TriggerExecutionResult:
        """Execute a single trigger.

        Args:
            trigger: Trigger to execute
            data: Trigger data

        Returns:
            Execution result
        """
        start = time.time()

        try:
            # Update state
            trigger.last_triggered = time.time()
            trigger.trigger_count += 1

            # Execute action
            await trigger.action(data)

            # Success
            trigger.success_count += 1
            self._stats["triggers_fired"] += 1

            elapsed = time.time() - start
            logger.info(f"🎯 Trigger fired: {trigger.name} ({elapsed:.3f}s)")

            return TriggerExecutionResult(
                trigger_name=trigger.name,
                success=True,
                execution_time=elapsed,
            )

        except Exception as e:
            # Failure
            trigger.failure_count += 1
            self._stats["triggers_failed"] += 1

            elapsed = time.time() - start
            logger.error(f"❌ Trigger failed: {trigger.name} — {e}")

            return TriggerExecutionResult(
                trigger_name=trigger.name,
                success=False,
                execution_time=elapsed,
                error=str(e),
            )

    async def _check_presence(self) -> bool:
        """Check if Tim is home.

        Returns:
            True if home or unknown
        """
        if not self._sensory:
            return True  # Assume home if no sensory

        try:
            from kagami.core.integrations.unified_sensory import SenseType

            presence_data = await self._sensory.poll_specific(SenseType.PRESENCE)
            return presence_data.get("is_home", True)
        except Exception:
            return True  # Fail open

    def get_stats(self) -> dict[str, Any]:
        """Get trigger statistics."""
        return {
            **self._stats,
            "triggers_by_type": {
                source_type.value: len(triggers)
                for source_type, triggers in self._by_source_type.items()
            },
            "triggers_by_success_rate": {
                trigger.name: (
                    trigger.success_count / trigger.trigger_count
                    if trigger.trigger_count > 0
                    else 0.0
                )
                for trigger in self._triggers.values()
            },
        }

    def get_health(self) -> dict[str, Any]:
        """Get health status."""
        return {
            "connected": self._smart_home is not None,
            "triggers_registered": len(self._triggers),
            "triggers_enabled": sum(1 for t in self._triggers.values() if t.enabled),
            "stats": self._stats,
        }


# Singleton
_registry: TriggerRegistry | None = None


def get_trigger_registry() -> TriggerRegistry:
    """Get the global trigger registry singleton."""
    global _registry
    if _registry is None:
        _registry = TriggerRegistry()
    return _registry


def reset_trigger_registry() -> None:
    """Reset the singleton (for testing)."""
    global _registry
    _registry = None
