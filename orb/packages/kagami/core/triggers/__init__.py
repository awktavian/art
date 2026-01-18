"""Unified Trigger System — Single registry for all triggers.

CREATED: January 5, 2026 (Phase 2 Consolidation)

## Architecture

ONE registry, FOUR source types:
1. SENSORY — Sense changes (weather, presence, sleep, email, etc.)
2. SERVICE — Service events (GitHub, Linear, Slack, etc.)
3. CELESTIAL — Astronomical events (sunrise, sunset, moon phases)
4. AUTONOMOUS — Internal goals (time-based, learned preferences)

ALL triggers use the same interface:
- Unified registration
- Unified evaluation
- Unified cooldown management
- Unified metrics

## Usage

```python
from kagami.core.triggers import get_trigger_registry, UnifiedTrigger, TriggerSourceType

registry = get_trigger_registry()

# Register a trigger
registry.register(UnifiedTrigger(
    name="morning_weather",
    source_type=TriggerSourceType.SENSORY,
    source="weather",
    condition=lambda data: 6 <= datetime.now().hour < 10,
    action=announce_weather,
    cooldown=21600.0,
))

# Evaluate (called by event handlers)
await registry.evaluate("weather", weather_data)
```

## Migration from Legacy

- CrossDomainBridge triggers → SENSORY triggers
- PhysicalAction → AUTONOMOUS triggers
- AutoTriggers → SERVICE triggers
- CelestialTriggers → CELESTIAL triggers (keep specialized)
"""

from .base import (
    TriggerExecutionResult,
    TriggerPriority,
    TriggerSourceType,
    UnifiedTrigger,
)
from .conditions import (
    keyword_match,
    significant_change,
    temperature_threshold,
    time_window,
)
from .registry import TriggerRegistry, get_trigger_registry, reset_trigger_registry

__all__ = [
    "TriggerExecutionResult",
    "TriggerPriority",
    "TriggerRegistry",
    "TriggerSourceType",
    "UnifiedTrigger",
    "get_trigger_registry",
    "keyword_match",
    "reset_trigger_registry",
    "significant_change",
    "temperature_threshold",
    "time_window",
]
