"""Base types, enums, and configurations for the sensory system.

This module provides the foundation for all sensory integrations:
- SenseType enum defining all 24+ sense types
- SenseConfig for per-sense configuration
- CachedSense for TTL-based caching
- AdaptiveConfig for activity-aware polling
- ActivityLevel for adaptive polling states
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SenseType(Enum):
    """Types of sensory inputs."""

    # Digital (Composio)
    GMAIL = "gmail"
    GITHUB = "github"
    LINEAR = "linear"
    NOTION = "notion"
    DISCORD = "discord"
    CALENDAR = "calendar"
    DRIVE = "drive"
    SHEETS = "sheets"
    FIGMA = "figma"
    SLACK = "slack"

    # Physical (SmartHome)
    PRESENCE = "presence"
    MOTION = "motion"
    LIGHTS = "lights"
    SHADES = "shades"
    LOCKS = "locks"
    CLIMATE = "climate"
    AUDIO = "audio"
    SLEEP = "sleep"
    VEHICLE = "vehicle"
    CAMERAS = "cameras"
    SECURITY = "security"

    # Environmental
    WEATHER = "weather"

    # World State
    WORLD_STATE = "world_state"

    # Situation Awareness
    SITUATION = "situation"

    # Biometric (Apple Health)
    HEALTH = "health"

    # Aggregated / Derived
    SOCIAL = "social"


@dataclass
class SenseConfig:
    """Configuration for a sensory source."""

    sense_type: SenseType
    poll_interval: float  # seconds between polls
    cache_ttl: float  # seconds to cache results
    enabled: bool = True
    priority: int = 5  # 1=highest, 10=lowest
    alert_on_change: bool = False
    alert_threshold: float | None = None


class ActivityLevel(Enum):
    """Activity levels for adaptive polling."""

    INACTIVE = "inactive"
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    BURST = "burst"


@dataclass
class AdaptiveConfig:
    """Adaptive polling configuration for a sense type."""

    activity_multipliers: dict[ActivityLevel, float] = field(
        default_factory=lambda: {
            ActivityLevel.INACTIVE: 2.0,
            ActivityLevel.LOW: 1.3,
            ActivityLevel.NORMAL: 1.0,
            ActivityLevel.HIGH: 0.7,
            ActivityLevel.BURST: 0.5,
        }
    )
    present_multiplier: float = 1.0
    away_multiplier: float = 2.0
    time_multipliers: dict[int, float] | None = None


@dataclass
class CachedSense:
    """Cached sensory data with TTL."""

    sense_type: SenseType
    data: dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    ttl: float = 60.0

    @property
    def is_valid(self) -> bool:
        """Check if cache is still valid."""
        return (time.time() - self.timestamp) < self.ttl

    @property
    def age(self) -> float:
        """Get age of cached data in seconds."""
        return time.time() - self.timestamp


# Type for event callbacks
SenseEventCallback = Callable[[SenseType, dict[str, Any], dict[str, Any]], Awaitable[None]]


# Default configurations - OPTIMIZED intervals
DEFAULT_SENSE_CONFIGS: dict[SenseType, SenseConfig] = {
    # Digital senses
    SenseType.GMAIL: SenseConfig(
        SenseType.GMAIL, poll_interval=120, cache_ttl=120, priority=2, alert_on_change=True
    ),
    SenseType.GITHUB: SenseConfig(SenseType.GITHUB, poll_interval=600, cache_ttl=600, priority=5),
    SenseType.LINEAR: SenseConfig(SenseType.LINEAR, poll_interval=600, cache_ttl=600, priority=4),
    SenseType.NOTION: SenseConfig(SenseType.NOTION, poll_interval=900, cache_ttl=900, priority=6),
    SenseType.DISCORD: SenseConfig(SenseType.DISCORD, poll_interval=300, cache_ttl=300, priority=5),
    SenseType.CALENDAR: SenseConfig(
        SenseType.CALENDAR, poll_interval=120, cache_ttl=120, priority=1, alert_on_change=True
    ),
    SenseType.DRIVE: SenseConfig(SenseType.DRIVE, poll_interval=900, cache_ttl=900, priority=7),
    SenseType.SHEETS: SenseConfig(SenseType.SHEETS, poll_interval=900, cache_ttl=900, priority=7),
    SenseType.FIGMA: SenseConfig(SenseType.FIGMA, poll_interval=120, cache_ttl=120, priority=5),
    SenseType.SLACK: SenseConfig(
        SenseType.SLACK, poll_interval=60, cache_ttl=60, priority=2, alert_on_change=True
    ),
    # Physical senses
    SenseType.PRESENCE: SenseConfig(
        SenseType.PRESENCE, poll_interval=30, cache_ttl=30, priority=1, alert_on_change=True
    ),
    SenseType.MOTION: SenseConfig(SenseType.MOTION, poll_interval=15, cache_ttl=15, priority=2),
    SenseType.LIGHTS: SenseConfig(SenseType.LIGHTS, poll_interval=60, cache_ttl=60, priority=6),
    SenseType.SHADES: SenseConfig(SenseType.SHADES, poll_interval=60, cache_ttl=60, priority=6),
    SenseType.LOCKS: SenseConfig(
        SenseType.LOCKS, poll_interval=30, cache_ttl=30, priority=2, alert_on_change=True
    ),
    SenseType.CLIMATE: SenseConfig(SenseType.CLIMATE, poll_interval=300, cache_ttl=300, priority=5),
    SenseType.AUDIO: SenseConfig(SenseType.AUDIO, poll_interval=60, cache_ttl=60, priority=5),
    SenseType.SLEEP: SenseConfig(SenseType.SLEEP, poll_interval=600, cache_ttl=600, priority=4),
    SenseType.VEHICLE: SenseConfig(SenseType.VEHICLE, poll_interval=300, cache_ttl=300, priority=4),
    SenseType.CAMERAS: SenseConfig(SenseType.CAMERAS, poll_interval=60, cache_ttl=60, priority=3),
    SenseType.SECURITY: SenseConfig(
        SenseType.SECURITY, poll_interval=30, cache_ttl=30, priority=1, alert_on_change=True
    ),
    # Environmental
    SenseType.WEATHER: SenseConfig(
        SenseType.WEATHER, poll_interval=300, cache_ttl=300, priority=5, alert_on_change=False
    ),
    SenseType.WORLD_STATE: SenseConfig(
        SenseType.WORLD_STATE, poll_interval=300, cache_ttl=300, priority=4, alert_on_change=False
    ),
    SenseType.SITUATION: SenseConfig(
        SenseType.SITUATION, poll_interval=60, cache_ttl=60, priority=1, alert_on_change=True
    ),
    # Biometric
    SenseType.HEALTH: SenseConfig(
        SenseType.HEALTH, poll_interval=60, cache_ttl=60, priority=2, alert_on_change=True
    ),
    # Aggregated
    SenseType.SOCIAL: SenseConfig(
        SenseType.SOCIAL, poll_interval=60, cache_ttl=60, priority=3, alert_on_change=True
    ),
}


# Default adaptive configs per sense type
ADAPTIVE_CONFIGS: dict[SenseType, AdaptiveConfig] = {
    SenseType.SECURITY: AdaptiveConfig(
        activity_multipliers={
            ActivityLevel.INACTIVE: 1.0,
            ActivityLevel.LOW: 1.0,
            ActivityLevel.NORMAL: 1.0,
            ActivityLevel.HIGH: 0.8,
            ActivityLevel.BURST: 0.5,
        },
        away_multiplier=0.8,
    ),
    SenseType.LOCKS: AdaptiveConfig(
        activity_multipliers={
            ActivityLevel.INACTIVE: 1.5,
            ActivityLevel.LOW: 1.2,
            ActivityLevel.NORMAL: 1.0,
            ActivityLevel.HIGH: 0.8,
            ActivityLevel.BURST: 0.5,
        },
        away_multiplier=0.8,
    ),
    SenseType.PRESENCE: AdaptiveConfig(
        present_multiplier=1.0,
        away_multiplier=0.8,
    ),
    SenseType.AUDIO: AdaptiveConfig(
        activity_multipliers={
            ActivityLevel.INACTIVE: 5.0,
            ActivityLevel.LOW: 2.0,
            ActivityLevel.NORMAL: 1.0,
            ActivityLevel.HIGH: 0.5,
            ActivityLevel.BURST: 0.3,
        },
    ),
    SenseType.CLIMATE: AdaptiveConfig(
        time_multipliers={
            **dict.fromkeys(range(6, 10), 0.8),
            **dict.fromkeys(range(10, 17), 1.2),
            **dict.fromkeys(range(17, 23), 0.8),
            **dict.fromkeys(range(23, 24), 1.5),
            **dict.fromkeys(range(0, 6), 1.5),
        },
    ),
    SenseType.SLEEP: AdaptiveConfig(
        time_multipliers={
            **dict.fromkeys(range(0, 5), 1.5),
            **dict.fromkeys(range(5, 8), 0.5),
            **dict.fromkeys(range(8, 20), 2.0),
            **dict.fromkeys(range(20, 24), 0.5),
        },
    ),
    SenseType.GMAIL: AdaptiveConfig(
        activity_multipliers={
            ActivityLevel.INACTIVE: 2.0,
            ActivityLevel.LOW: 1.5,
            ActivityLevel.NORMAL: 1.0,
            ActivityLevel.HIGH: 0.8,
            ActivityLevel.BURST: 0.5,
        },
    ),
    SenseType.GITHUB: AdaptiveConfig(
        activity_multipliers={
            ActivityLevel.INACTIVE: 2.0,
            ActivityLevel.LOW: 1.5,
            ActivityLevel.NORMAL: 1.0,
            ActivityLevel.HIGH: 0.5,
            ActivityLevel.BURST: 0.3,
        },
    ),
    SenseType.LINEAR: AdaptiveConfig(
        activity_multipliers={
            ActivityLevel.INACTIVE: 2.0,
            ActivityLevel.LOW: 1.5,
            ActivityLevel.NORMAL: 1.0,
            ActivityLevel.HIGH: 0.5,
            ActivityLevel.BURST: 0.3,
        },
    ),
}


__all__ = [
    "ADAPTIVE_CONFIGS",
    "DEFAULT_SENSE_CONFIGS",
    "ActivityLevel",
    "AdaptiveConfig",
    "CachedSense",
    "SenseConfig",
    "SenseEventCallback",
    "SenseType",
]
