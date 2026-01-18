"""Unified trigger base types.

CREATED: January 5, 2026
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TriggerSourceType(str, Enum):
    """Source types for triggers."""

    SENSORY = "sensory"  # UnifiedSensory sense changes
    SERVICE = "service"  # Composio service events
    CELESTIAL = "celestial"  # Astronomical events
    AUTONOMOUS = "autonomous"  # Internal goals, time-based


class TriggerPriority(int, Enum):
    """Trigger priority levels."""

    CRITICAL = 1  # Safety-critical, immediate
    HIGH = 2  # Important, <1 min
    NORMAL = 3  # Regular, <5 min
    LOW = 4  # Background, batched


@dataclass
class UnifiedTrigger:
    """THE unified trigger abstraction.

    All triggers in Kagami use this interface:
    - Sensory triggers (weather, email, presence)
    - Service triggers (GitHub, Linear, Slack)
    - Celestial triggers (sunset, sunrise)
    - Autonomous actions (morning routine, focus mode)

    Attributes:
        name: Unique trigger identifier
        source_type: Type of trigger source
        source: Specific source (e.g., "weather", "github", "sunrise")
        condition: Function that evaluates whether trigger should fire
        action: Async function to execute when trigger fires
        cooldown: Minimum seconds between trigger fires
        priority: Trigger priority level
        enabled: Whether trigger is active
        requires_presence: Only fire when Tim is home
        safety_priority: CBF priority (1=highest)
        metadata: Additional metadata for logging/metrics
    """

    name: str
    source_type: TriggerSourceType
    source: str
    condition: Callable[[dict], bool]
    action: Callable[[dict], Awaitable[Any]]
    cooldown: float = 60.0
    priority: TriggerPriority = TriggerPriority.NORMAL
    enabled: bool = True
    requires_presence: bool = False
    safety_priority: int = 5  # 1=highest, 10=lowest

    # State (managed by registry)
    last_triggered: float = field(default=0.0, init=False)
    trigger_count: int = field(default=0, init=False)
    success_count: int = field(default=0, init=False)
    failure_count: int = field(default=0, init=False)

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    def can_trigger(self, data: dict, presence_home: bool = True) -> bool:
        """Check if trigger can fire.

        Args:
            data: Trigger data
            presence_home: Whether Tim is home

        Returns:
            True if trigger should fire
        """
        if not self.enabled:
            return False

        # Check presence requirement
        if self.requires_presence and not presence_home:
            return False

        # Check cooldown
        if (time.time() - self.last_triggered) < self.cooldown:
            return False

        # Evaluate condition
        try:
            return self.condition(data)
        except Exception:
            return False


@dataclass
class TriggerExecutionResult:
    """Result of trigger execution."""

    trigger_name: str
    success: bool
    execution_time: float
    error: str | None = None
    data: dict = field(default_factory=dict)
