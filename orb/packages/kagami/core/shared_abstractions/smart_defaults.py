"""Smart Defaults Registry — Intelligent Parameter Selection for All Tools.

CONSOLIDATES: Default parameter patterns across 500+ tools
REDUCES: Configuration overhead, parameter guesswork, error rates
PROVIDES: Context-aware smart defaults with safety validation

This module provides intelligent default parameter selection for:
- Physical effectors (SmartHome devices: 100+ devices)
- Digital effectors (Composio tools: 500+ actions)
- Cognitive tools (LLM, world model, memory operations)
- System tools (database, caching, configuration)

Created: December 30, 2025
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .action_result import (
    ActionError,
    ActionErrorType,
    ActionResult,
)

logger = logging.getLogger(__name__)


class ToolCategory(Enum):
    """Categories of tools for smart defaults."""

    PHYSICAL = "physical"  # Smart home devices
    DIGITAL = "digital"  # Composio API actions
    COGNITIVE = "cognitive"  # LLM, world model, inference
    SYSTEM = "system"  # Database, caching, config
    SAFETY = "safety"  # CBF, boundary enforcement


class ContextType(Enum):
    """Context types that influence default parameter selection."""

    TIME_OF_DAY = "time_of_day"  # Morning, afternoon, evening, night
    OCCUPANCY = "occupancy"  # Home, away, sleeping
    ACTIVITY = "activity"  # Work, entertainment, relaxation, meal
    URGENCY = "urgency"  # Low, medium, high, critical
    SAFETY_LEVEL = "safety_level"  # Permissive, normal, strict, maximum
    ROOM_CONTEXT = "room_context"  # Living room, office, bedroom, kitchen


@dataclass
class SmartDefault:
    """Smart default parameter configuration."""

    parameter_name: str
    default_value: Any
    context_overrides: dict[str, Any] = field(default_factory=dict)
    safety_constraints: dict[str, Any] = field(default_factory=dict)
    validation_function: Callable[[Any], bool] | None = None
    description: str = ""


@dataclass
class ToolDefaults:
    """Complete default configuration for a tool."""

    tool_id: str
    category: ToolCategory
    defaults: dict[str, SmartDefault]
    context_rules: dict[str, dict[str, Any]] = field(default_factory=dict)
    safety_requirements: dict[str, float] = field(default_factory=dict)


class SmartDefaultsRegistry:
    """Registry for intelligent tool parameter defaults."""

    def __init__(self):
        self._tool_defaults: dict[str, ToolDefaults] = {}
        self._context_state: dict[ContextType, str] = {}

        # Initialize with built-in defaults
        self._initialize_physical_defaults()
        self._initialize_digital_defaults()
        self._initialize_cognitive_defaults()
        self._initialize_system_defaults()

    def register_tool_defaults(self, tool_defaults: ToolDefaults) -> None:
        """Register smart defaults for a tool."""
        self._tool_defaults[tool_defaults.tool_id] = tool_defaults
        logger.debug(f"Registered smart defaults for tool: {tool_defaults.tool_id}")

    def get_smart_defaults(
        self, tool_id: str, context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Get smart defaults for a tool with context awareness."""
        if tool_id not in self._tool_defaults:
            logger.warning(f"No smart defaults registered for tool: {tool_id}")
            return {}

        tool_defaults = self._tool_defaults[tool_id]
        context = context or {}

        # Update context state
        self._update_context_state(context)

        # Generate smart defaults
        smart_params = {}
        for param_name, smart_default in tool_defaults.defaults.items():
            value = self._resolve_parameter_value(smart_default, context)
            if self._validate_parameter(smart_default, value):
                smart_params[param_name] = value
            else:
                logger.warning(f"Invalid default value for {tool_id}.{param_name}: {value}")

        return smart_params

    def _update_context_state(self, context: dict[str, Any]) -> None:
        """Update current context state for smart defaults."""
        # Extract context information
        if "time_of_day" in context:
            self._context_state[ContextType.TIME_OF_DAY] = context["time_of_day"]
        if "occupancy" in context:
            self._context_state[ContextType.OCCUPANCY] = context["occupancy"]
        if "activity" in context:
            self._context_state[ContextType.ACTIVITY] = context["activity"]
        if "urgency" in context:
            self._context_state[ContextType.URGENCY] = context["urgency"]
        if "room" in context:
            self._context_state[ContextType.ROOM_CONTEXT] = context["room"]

    def _resolve_parameter_value(self, smart_default: SmartDefault, context: dict[str, Any]) -> Any:
        """Resolve parameter value based on context and defaults."""
        # Check context overrides first
        for context_key, override_value in smart_default.context_overrides.items():
            if self._match_context(context_key, context):
                return override_value

        return smart_default.default_value

    def _match_context(self, context_key: str, context: dict[str, Any]) -> bool:
        """Check if context matches the specified key."""
        # Parse context key (e.g., "time_of_day:evening")
        if ":" in context_key:
            context_type, context_value = context_key.split(":", 1)
            return context.get(context_type) == context_value
        return context_key in context

    def _validate_parameter(self, smart_default: SmartDefault, value: Any) -> bool:
        """Validate parameter value against constraints."""
        # Use custom validation function if provided
        if smart_default.validation_function:
            return smart_default.validation_function(value)

        # Apply safety constraints
        for constraint, limit in smart_default.safety_constraints.items():
            if (
                (constraint == "min_value" and value < limit)
                or (constraint == "max_value" and value > limit)
                or (constraint == "allowed_values" and value not in limit)
            ):
                return False

        return True

    def _initialize_physical_defaults(self) -> None:
        """Initialize smart defaults for physical devices."""

        # Smart Home Light Controls
        light_defaults = ToolDefaults(
            tool_id="smarthome.set_lights",
            category=ToolCategory.PHYSICAL,
            defaults={
                "level": SmartDefault(
                    parameter_name="level",
                    default_value=70,  # Comfortable default
                    context_overrides={
                        "time_of_day:morning": 80,
                        "time_of_day:evening": 50,
                        "time_of_day:night": 20,
                        "activity:work": 85,
                        "activity:entertainment": 40,
                        "activity:sleep": 5,
                    },
                    safety_constraints={"min_value": 0, "max_value": 100},
                    description="Light brightness level (0-100%)",
                ),
                "rooms": SmartDefault(
                    parameter_name="rooms",
                    default_value=None,  # All rooms
                    context_overrides={
                        "activity:work": ["Office"],
                        "activity:entertainment": ["Living Room"],
                        "activity:sleep": ["Primary Bed"],
                    },
                    description="Target rooms for lighting control",
                ),
            },
        )
        self.register_tool_defaults(light_defaults)

        # Smart Home Audio Controls
        audio_defaults = ToolDefaults(
            tool_id="smarthome.set_audio",
            category=ToolCategory.PHYSICAL,
            defaults={
                "volume": SmartDefault(
                    parameter_name="volume",
                    default_value=40,
                    context_overrides={
                        "time_of_day:morning": 35,
                        "time_of_day:evening": 45,
                        "time_of_day:night": 25,
                        "activity:work": 30,
                        "activity:entertainment": 60,
                        "urgency:high": 70,
                    },
                    safety_constraints={"min_value": 0, "max_value": 100},
                    description="Audio volume level (0-100%)",
                ),
                "room": SmartDefault(
                    parameter_name="room",
                    default_value=None,  # Current room
                    description="Target room for audio control",
                ),
                "use_home_theater": SmartDefault(
                    parameter_name="use_home_theater",
                    default_value=False,
                    context_overrides={
                        "activity:entertainment": True,
                        "room_context:Living Room": True,
                    },
                    description="Use Denon home theater system",
                ),
            },
        )
        self.register_tool_defaults(audio_defaults)

        # Climate Controls
        climate_defaults = ToolDefaults(
            tool_id="smarthome.set_temperature",
            category=ToolCategory.PHYSICAL,
            defaults={
                "temperature": SmartDefault(
                    parameter_name="temperature",
                    default_value=72,  # Fahrenheit
                    context_overrides={
                        "time_of_day:morning": 70,
                        "time_of_day:night": 68,
                        "activity:sleep": 65,
                        "activity:work": 71,
                    },
                    safety_constraints={"min_value": 60, "max_value": 85},
                    description="Target temperature in Fahrenheit",
                )
            },
        )
        self.register_tool_defaults(climate_defaults)

    def _initialize_digital_defaults(self) -> None:
        """Initialize smart defaults for digital tools (Composio)."""

        # Gmail Actions
        gmail_defaults = ToolDefaults(
            tool_id="composio.gmail.send_email",
            category=ToolCategory.DIGITAL,
            defaults={
                "priority": SmartDefault(
                    parameter_name="priority",
                    default_value="normal",
                    context_overrides={"urgency:high": "high", "urgency:critical": "urgent"},
                    safety_constraints={"allowed_values": ["low", "normal", "high", "urgent"]},
                    description="Email priority level",
                ),
                "send_immediately": SmartDefault(
                    parameter_name="send_immediately",
                    default_value=True,
                    context_overrides={"urgency:low": False},
                    description="Send email immediately or queue",
                ),
            },
        )
        self.register_tool_defaults(gmail_defaults)

        # Linear Task Management
        linear_defaults = ToolDefaults(
            tool_id="composio.linear.create_issue",
            category=ToolCategory.DIGITAL,
            defaults={
                "priority": SmartDefault(
                    parameter_name="priority",
                    default_value=2,  # Normal priority
                    context_overrides={"urgency:low": 1, "urgency:high": 3, "urgency:critical": 4},
                    safety_constraints={"min_value": 1, "max_value": 4},
                    description="Issue priority (1=Low, 2=Medium, 3=High, 4=Urgent)",
                ),
                "assignee": SmartDefault(
                    parameter_name="assignee",
                    default_value=None,  # Unassigned
                    description="Issue assignee",
                ),
            },
        )
        self.register_tool_defaults(linear_defaults)

    def _initialize_cognitive_defaults(self) -> None:
        """Initialize smart defaults for cognitive tools."""

        # LLM Generation
        llm_defaults = ToolDefaults(
            tool_id="cognitive.llm_generate",
            category=ToolCategory.COGNITIVE,
            defaults={
                "temperature": SmartDefault(
                    parameter_name="temperature",
                    default_value=0.7,
                    context_overrides={
                        "activity:work": 0.3,  # More focused for work
                        "activity:entertainment": 0.9,  # More creative
                        "urgency:high": 0.2,  # Very focused for urgent tasks
                    },
                    safety_constraints={"min_value": 0.0, "max_value": 2.0},
                    description="LLM sampling temperature",
                ),
                "max_tokens": SmartDefault(
                    parameter_name="max_tokens",
                    default_value=1000,
                    context_overrides={
                        "urgency:high": 500,  # Shorter for urgent
                        "activity:entertainment": 2000,  # Longer for creative work
                    },
                    safety_constraints={"min_value": 1, "max_value": 4000},
                    description="Maximum tokens to generate",
                ),
            },
        )
        self.register_tool_defaults(llm_defaults)

        # EFE Calculations
        efe_defaults = ToolDefaults(
            tool_id="cognitive.efe_calculate",
            category=ToolCategory.COGNITIVE,
            defaults={
                "batch_size": SmartDefault(
                    parameter_name="batch_size",
                    default_value=32,
                    context_overrides={
                        "urgency:high": 16,  # Smaller batches for speed
                        "urgency:low": 64,  # Larger batches for efficiency
                    },
                    safety_constraints={"min_value": 1, "max_value": 128},
                    description="Batch size for EFE calculations",
                ),
                "use_cache": SmartDefault(
                    parameter_name="use_cache",
                    default_value=True,
                    context_overrides={
                        "urgency:critical": False  # Skip cache for critical operations
                    },
                    description="Use cached EFE values when available",
                ),
            },
        )
        self.register_tool_defaults(efe_defaults)

    def _initialize_system_defaults(self) -> None:
        """Initialize smart defaults for system tools."""

        # Database Operations
        db_defaults = ToolDefaults(
            tool_id="system.database_query",
            category=ToolCategory.SYSTEM,
            defaults={
                "timeout": SmartDefault(
                    parameter_name="timeout",
                    default_value=30.0,  # seconds
                    context_overrides={"urgency:high": 10.0, "urgency:low": 60.0},
                    safety_constraints={"min_value": 1.0, "max_value": 300.0},
                    description="Query timeout in seconds",
                ),
                "retry_count": SmartDefault(
                    parameter_name="retry_count",
                    default_value=3,
                    context_overrides={"urgency:critical": 5, "urgency:low": 1},
                    safety_constraints={"min_value": 0, "max_value": 10},
                    description="Number of retry attempts",
                ),
            },
        )
        self.register_tool_defaults(db_defaults)

        # Caching Operations
        cache_defaults = ToolDefaults(
            tool_id="system.cache_operation",
            category=ToolCategory.SYSTEM,
            defaults={
                "ttl": SmartDefault(
                    parameter_name="ttl",
                    default_value=300,  # 5 minutes
                    context_overrides={
                        "urgency:high": 60,  # 1 minute for urgent
                        "urgency:low": 3600,  # 1 hour for low priority
                    },
                    safety_constraints={"min_value": 1, "max_value": 86400},
                    description="Cache TTL in seconds",
                )
            },
        )
        self.register_tool_defaults(cache_defaults)

    def get_context_aware_defaults(
        self, tool_category: ToolCategory, context: dict[str, Any] | None = None
    ) -> dict[str, dict[str, Any]]:
        """Get smart defaults for all tools in a category."""
        context = context or {}
        category_defaults = {}

        for tool_id, tool_defaults in self._tool_defaults.items():
            if tool_defaults.category == tool_category:
                category_defaults[tool_id] = self.get_smart_defaults(tool_id, context)

        return category_defaults

    def validate_parameters(
        self, tool_id: str, parameters: dict[str, Any]
    ) -> ActionResult[dict[str, Any]]:
        """Validate parameters against smart defaults and constraints."""
        if tool_id not in self._tool_defaults:
            return ActionResult.success(
                data=parameters, message=f"No validation rules for {tool_id}"
            )

        tool_defaults = self._tool_defaults[tool_id]
        validated_params = parameters.copy()
        warnings = []

        for param_name, value in parameters.items():
            if param_name in tool_defaults.defaults:
                smart_default = tool_defaults.defaults[param_name]
                if not self._validate_parameter(smart_default, value):
                    error = ActionError(
                        ActionErrorType.VALIDATION_ERROR,
                        f"Parameter {param_name}={value} violates safety constraints",
                    )
                    return ActionResult.failure(error)

            # Apply smart defaults for missing parameters
            for param_name, smart_default in tool_defaults.defaults.items():
                if param_name not in validated_params:
                    default_value = smart_default.default_value
                    validated_params[param_name] = default_value
                    warnings.append(f"Applied smart default {param_name}={default_value}")

        if warnings:
            return ActionResult.partial_success(
                data=validated_params,
                warnings=warnings,
                message="Applied smart defaults for missing parameters",
            )
        else:
            return ActionResult.success(
                data=validated_params, message="Parameter validation successful"
            )

    def get_tool_categories(self) -> list[str]:
        """Get all tool categories with registered defaults."""
        categories = set()
        for tool_defaults in self._tool_defaults.values():
            categories.add(tool_defaults.category.value)
        return sorted(categories)

    def get_registry_stats(self) -> dict[str, Any]:
        """Get smart defaults registry statistics."""
        stats = {"total_tools": len(self._tool_defaults), "categories": {}, "total_parameters": 0}

        for tool_defaults in self._tool_defaults.values():
            category = tool_defaults.category.value
            if category not in stats["categories"]:
                stats["categories"][category] = 0
            stats["categories"][category] += 1
            stats["total_parameters"] += len(tool_defaults.defaults)

        return stats


# Global smart defaults registry
_global_smart_defaults_registry: SmartDefaultsRegistry | None = None


def get_smart_defaults_registry() -> SmartDefaultsRegistry:
    """Get the global smart defaults registry."""
    global _global_smart_defaults_registry
    if _global_smart_defaults_registry is None:
        _global_smart_defaults_registry = SmartDefaultsRegistry()
    return _global_smart_defaults_registry


def get_smart_defaults(tool_id: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Get smart defaults for a tool (convenience function)."""
    registry = get_smart_defaults_registry()
    return registry.get_smart_defaults(tool_id, context)


def validate_tool_parameters(
    tool_id: str, parameters: dict[str, Any]
) -> ActionResult[dict[str, Any]]:
    """Validate and enhance parameters with smart defaults."""
    registry = get_smart_defaults_registry()
    return registry.validate_parameters(tool_id, parameters)


# Export all smart defaults functionality
__all__ = [
    "ContextType",
    "SmartDefault",
    "SmartDefaultsRegistry",
    "ToolCategory",
    "ToolDefaults",
    "get_smart_defaults",
    "get_smart_defaults_registry",
    "validate_tool_parameters",
]
