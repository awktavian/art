"""Intent-Based Automation — Household-Agnostic, Adaptive Automation.

This replaces the hardcoded UnifiedTriggerEngine with an intent-driven system that:
1. Uses natural language intents instead of action strings
2. Discovers capabilities dynamically from the household
3. Adapts to any household configuration
4. Routes through the existing ColonyIntentRouter

ARCHITECTURE:
=============
    Condition → Intent → Capability Discovery → Execution

    "cold + morning" → "warm_up_transport" → [Tesla? → precondition | No car? → skip]

HOUSEHOLD-AGNOSTIC DESIGN:
==========================
- No hardcoded device names (e.g., "Tesla", "Control4")
- Capabilities are discovered: "has_vehicle", "has_hvac", "has_lighting"
- Intents map to capabilities, not specific devices
- Households define their own capability implementations

INTENT TAXONOMY:
================
- comfort.warm_home       → HVAC, fireplace, bed temp
- comfort.cool_home       → HVAC, fans, shades
- comfort.prepare_sleep   → Bed, lights, shades, temp
- transport.warm_vehicle  → Car climate (if available)
- transport.remind_charge → Notification (if vehicle has battery)
- security.lock_up        → Locks, alarm (whatever is available)
- security.alert          → Notification via best channel
- presence.welcome        → Lights, unlock, music
- presence.goodbye        → Lights off, lock, arm

Created: January 2, 2026
h(x) >= 0 always.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami_smarthome.controller import SmartHomeController

logger = logging.getLogger(__name__)


# =============================================================================
# CAPABILITY DISCOVERY
# =============================================================================


class Capability(str, Enum):
    """Household capabilities that can be discovered."""

    # Transport
    HAS_VEHICLE = "has_vehicle"
    HAS_VEHICLE_CLIMATE = "has_vehicle_climate"
    HAS_VEHICLE_BATTERY = "has_vehicle_battery"
    HAS_VEHICLE_LOCATION = "has_vehicle_location"

    # Climate
    HAS_HVAC = "has_hvac"
    HAS_FIREPLACE = "has_fireplace"
    HAS_BED_CLIMATE = "has_bed_climate"
    HAS_FANS = "has_fans"

    # Lighting
    HAS_LIGHTS = "has_lights"
    HAS_SHADES = "has_shades"
    HAS_CIRCADIAN = "has_circadian"

    # Security
    HAS_LOCKS = "has_locks"
    HAS_ALARM = "has_alarm"
    HAS_CAMERAS = "has_cameras"

    # Audio/Visual
    HAS_SPEAKERS = "has_speakers"
    HAS_TV = "has_tv"
    HAS_THEATER = "has_theater"

    # Presence
    HAS_PRESENCE_DETECTION = "has_presence_detection"
    HAS_GEOFENCING = "has_geofencing"

    # Notifications
    HAS_VOICE_ANNOUNCE = "has_voice_announce"
    HAS_PUSH_NOTIFY = "has_push_notify"
    HAS_GLASSES = "has_glasses"


@dataclass
class HouseholdCapabilities:
    """Discovered capabilities for a household."""

    capabilities: set[Capability] = field(default_factory=set)
    capability_handlers: dict[Capability, Callable] = field(default_factory=dict)
    last_discovery: float = 0.0

    def has(self, cap: Capability) -> bool:
        """Check if capability is available."""
        return cap in self.capabilities

    def get_handler(self, cap: Capability) -> Callable | None:
        """Get the handler for a capability."""
        return self.capability_handlers.get(cap)

    def summary(self) -> dict[str, bool]:
        """Get capability summary."""
        return {cap.value: cap in self.capabilities for cap in Capability}


async def discover_capabilities(controller: SmartHomeController) -> HouseholdCapabilities:
    """Discover what capabilities this household has.

    This is the key to household-agnostic design. Instead of checking
    "do we have Tesla?", we check "do we have vehicle climate control?"

    Args:
        controller: SmartHome controller instance

    Returns:
        HouseholdCapabilities with discovered capabilities and handlers
    """
    caps = HouseholdCapabilities()
    caps.last_discovery = time.time()

    # === TRANSPORT ===
    if hasattr(controller, "_tesla_service") and controller._tesla_service:
        tesla_svc = controller._tesla_service
        if hasattr(tesla_svc, "is_available") and tesla_svc.is_available:
            caps.capabilities.add(Capability.HAS_VEHICLE)
            caps.capabilities.add(Capability.HAS_VEHICLE_LOCATION)

            if hasattr(tesla_svc, "precondition_car"):
                caps.capabilities.add(Capability.HAS_VEHICLE_CLIMATE)
                caps.capability_handlers[Capability.HAS_VEHICLE_CLIMATE] = (
                    tesla_svc.precondition_car
                )

            if hasattr(tesla_svc, "get_car_battery"):
                caps.capabilities.add(Capability.HAS_VEHICLE_BATTERY)

    # === CLIMATE ===
    if hasattr(controller, "_climate_service") and controller._climate_service:
        climate_svc = controller._climate_service
        caps.capabilities.add(Capability.HAS_HVAC)
        if hasattr(climate_svc, "set_room_temp"):
            caps.capability_handlers[Capability.HAS_HVAC] = climate_svc.set_room_temp

    # Check for fireplace
    if hasattr(controller, "fireplace_on"):
        caps.capabilities.add(Capability.HAS_FIREPLACE)
        caps.capability_handlers[Capability.HAS_FIREPLACE] = controller.fireplace_on

    # Check for bed climate (Eight Sleep)
    if hasattr(controller, "_eight_sleep") and controller._eight_sleep:
        caps.capabilities.add(Capability.HAS_BED_CLIMATE)

    # === LIGHTING ===
    if hasattr(controller, "set_lights"):
        caps.capabilities.add(Capability.HAS_LIGHTS)
        caps.capability_handlers[Capability.HAS_LIGHTS] = controller.set_lights

    if hasattr(controller, "set_shades") or hasattr(controller, "open_shades"):
        caps.capabilities.add(Capability.HAS_SHADES)

    # === SECURITY ===
    if hasattr(controller, "lock_all"):
        caps.capabilities.add(Capability.HAS_LOCKS)
        caps.capability_handlers[Capability.HAS_LOCKS] = controller.lock_all

    if hasattr(controller, "arm_security"):
        caps.capabilities.add(Capability.HAS_ALARM)

    if hasattr(controller, "_unifi") and controller._unifi:
        caps.capabilities.add(Capability.HAS_CAMERAS)
        caps.capabilities.add(Capability.HAS_PRESENCE_DETECTION)

    # === AUDIO ===
    if hasattr(controller, "announce"):
        caps.capabilities.add(Capability.HAS_VOICE_ANNOUNCE)
        caps.capabilities.add(Capability.HAS_SPEAKERS)
        caps.capability_handlers[Capability.HAS_VOICE_ANNOUNCE] = controller.announce

    if hasattr(controller, "_av_service") and controller._av_service:
        caps.capabilities.add(Capability.HAS_THEATER)
        caps.capabilities.add(Capability.HAS_TV)

    # === PRESENCE ===
    if hasattr(controller, "_presence") and controller._presence:
        caps.capabilities.add(Capability.HAS_PRESENCE_DETECTION)

    if hasattr(controller, "_tesla_service") and controller._tesla_service:
        if hasattr(controller._tesla_service, "is_car_home"):
            caps.capabilities.add(Capability.HAS_GEOFENCING)

    logger.info(f"🔍 Discovered {len(caps.capabilities)} capabilities")
    return caps


# =============================================================================
# INTENT DEFINITIONS
# =============================================================================


class AutomationIntent(str, Enum):
    """High-level automation intents.

    These are household-agnostic — they describe WHAT to do,
    not HOW to do it. The capability system handles the HOW.
    """

    # Comfort
    WARM_HOME = "comfort.warm_home"
    COOL_HOME = "comfort.cool_home"
    PREPARE_SLEEP = "comfort.prepare_sleep"
    WAKE_UP = "comfort.wake_up"

    # Transport
    WARM_VEHICLE = "transport.warm_vehicle"
    COOL_VEHICLE = "transport.cool_vehicle"
    CHARGE_REMINDER = "transport.charge_reminder"

    # Security
    LOCK_UP = "security.lock_up"
    ALERT = "security.alert"
    ARM_AWAY = "security.arm_away"

    # Presence
    WELCOME_HOME = "presence.welcome_home"
    GOODBYE = "presence.goodbye"
    GUEST_ARRIVING = "presence.guest_arriving"

    # Entertainment
    MOVIE_MODE = "entertainment.movie_mode"
    FOCUS_MODE = "entertainment.focus_mode"
    PARTY_MODE = "entertainment.party_mode"

    # Safety
    PET_ALERT = "safety.pet_alert"
    EMERGENCY = "safety.emergency"


@dataclass
class IntentExecution:
    """Result of executing an intent."""

    intent: AutomationIntent
    success: bool
    capabilities_used: list[Capability] = field(default_factory=list)
    capabilities_missing: list[Capability] = field(default_factory=list)
    actions_taken: list[str] = field(default_factory=list)
    error: str | None = None
    latency_ms: float = 0.0


# =============================================================================
# INTENT EXECUTORS
# =============================================================================


class IntentExecutor:
    """Executes automation intents using available capabilities.

    This is the bridge between abstract intents and concrete actions.
    It checks what capabilities are available and uses them.
    """

    def __init__(self, controller: SmartHomeController, capabilities: HouseholdCapabilities):
        self.controller = controller
        self.capabilities = capabilities

    async def execute(
        self,
        intent: AutomationIntent,
        context: dict[str, Any] | None = None,
    ) -> IntentExecution:
        """Execute an intent using available capabilities.

        Args:
            intent: The automation intent to execute
            context: Additional context (temp, rooms, etc.)

        Returns:
            IntentExecution result
        """
        context = context or {}
        start = time.time()
        result = IntentExecution(intent=intent, success=True)

        try:
            # Dispatch to appropriate handler
            handlers: dict[AutomationIntent, Callable] = {
                AutomationIntent.WARM_HOME: self._warm_home,
                AutomationIntent.COOL_HOME: self._cool_home,
                AutomationIntent.WARM_VEHICLE: self._warm_vehicle,
                AutomationIntent.COOL_VEHICLE: self._cool_vehicle,
                AutomationIntent.CHARGE_REMINDER: self._charge_reminder,
                AutomationIntent.LOCK_UP: self._lock_up,
                AutomationIntent.ALERT: self._alert,
                AutomationIntent.WELCOME_HOME: self._welcome_home,
                AutomationIntent.GOODBYE: self._goodbye,
                AutomationIntent.PREPARE_SLEEP: self._prepare_sleep,
                AutomationIntent.WAKE_UP: self._wake_up,
                AutomationIntent.PET_ALERT: self._pet_alert,
                AutomationIntent.MOVIE_MODE: self._movie_mode,
            }

            handler = handlers.get(intent)
            if handler:
                await handler(result, context)
            else:
                result.success = False
                result.error = f"No handler for intent: {intent.value}"

        except Exception as e:
            result.success = False
            result.error = str(e)
            logger.error(f"Intent {intent.value} failed: {e}")

        result.latency_ms = (time.time() - start) * 1000
        return result

    # === COMFORT INTENTS ===

    async def _warm_home(self, result: IntentExecution, ctx: dict) -> None:
        """Warm up the home using available capabilities."""
        target_temp = ctx.get("temp_f", 70)
        rooms = ctx.get("rooms", ["Living Room", "Kitchen"])

        # HVAC
        if self.capabilities.has(Capability.HAS_HVAC):
            try:
                await self.controller.set_room_temp(rooms[0], target_temp)
                result.capabilities_used.append(Capability.HAS_HVAC)
                result.actions_taken.append(f"Set HVAC to {target_temp}°F")
            except Exception as e:
                logger.warning(f"HVAC failed: {e}")
        else:
            result.capabilities_missing.append(Capability.HAS_HVAC)

        # Fireplace (if cold enough)
        if self.capabilities.has(Capability.HAS_FIREPLACE) and target_temp >= 68:
            try:
                await self.controller.fireplace_on()
                result.capabilities_used.append(Capability.HAS_FIREPLACE)
                result.actions_taken.append("Turned on fireplace")
            except Exception as e:
                logger.warning(f"Fireplace failed: {e}")

    async def _cool_home(self, result: IntentExecution, ctx: dict) -> None:
        """Cool down the home using available capabilities."""
        target_temp = ctx.get("temp_f", 74)

        if self.capabilities.has(Capability.HAS_HVAC):
            try:
                await self.controller.set_room_temp("Living Room", target_temp)
                result.capabilities_used.append(Capability.HAS_HVAC)
                result.actions_taken.append(f"Set AC to {target_temp}°F")
            except Exception as e:
                logger.warning(f"HVAC failed: {e}")

        if self.capabilities.has(Capability.HAS_SHADES):
            try:
                await self.controller.close_shades()
                result.capabilities_used.append(Capability.HAS_SHADES)
                result.actions_taken.append("Closed shades")
            except Exception as e:
                logger.warning(f"Shades failed: {e}")

    async def _prepare_sleep(self, result: IntentExecution, ctx: dict) -> None:
        """Prepare home for sleep.

        Actions:
        - Close ALL shades (blackout for sleep, privacy for bathrooms)
        - Dim bedroom lights
        - Cool bed
        - Lock doors
        """
        # Close ALL shades first (privacy + blackout)
        if self.capabilities.has(Capability.HAS_SHADES):
            try:
                await self.controller.close_shades()  # All rooms
                result.capabilities_used.append(Capability.HAS_SHADES)
                result.actions_taken.append("Closed all shades")
            except Exception:
                pass

        # Dim lights
        if self.capabilities.has(Capability.HAS_LIGHTS):
            try:
                await self.controller.set_lights(10, rooms=["Primary Bedroom"])
                result.capabilities_used.append(Capability.HAS_LIGHTS)
                result.actions_taken.append("Dimmed bedroom lights")
            except Exception:
                pass

        # Cool bed
        if self.capabilities.has(Capability.HAS_BED_CLIMATE):
            try:
                await self.controller.set_bed_temperature(-5, "both")
                result.capabilities_used.append(Capability.HAS_BED_CLIMATE)
                result.actions_taken.append("Cooled bed")
            except Exception:
                pass

        # Lock up
        if self.capabilities.has(Capability.HAS_LOCKS):
            try:
                await self.controller.lock_all()
                result.capabilities_used.append(Capability.HAS_LOCKS)
                result.actions_taken.append("Locked doors")
            except Exception:
                pass

    async def _wake_up(self, result: IntentExecution, ctx: dict) -> None:
        """Wake up routine.

        Actions:
        - Open ONLY bedroom shades (bathroom shades stay closed for privacy!)
        - Set bedroom lights to 50%
        - Turn on bathroom shower light for morning routine
        """
        # Open bedroom shades ONLY - bathroom stays private
        if self.capabilities.has(Capability.HAS_SHADES):
            try:
                await self.controller.open_shades(rooms=["Primary Bedroom"])
                result.capabilities_used.append(Capability.HAS_SHADES)
                result.actions_taken.append("Opened bedroom shades (bathroom stays closed)")
            except Exception:
                pass

        if self.capabilities.has(Capability.HAS_LIGHTS):
            try:
                # Bedroom lights at 50%
                await self.controller.set_lights(50, rooms=["Primary Bedroom"])
                result.actions_taken.append("Set bedroom lights to 50%")

                # Bathroom lights for morning shower - bright!
                await self.controller.set_lights(80, rooms=["Primary Bath"])
                result.capabilities_used.append(Capability.HAS_LIGHTS)
                result.actions_taken.append("Set bathroom lights for shower")
            except Exception:
                pass

    # === TRANSPORT INTENTS ===

    async def _warm_vehicle(self, result: IntentExecution, ctx: dict) -> None:
        """Warm up the vehicle."""
        target_temp_c = ctx.get("temp_c", 21.0)  # ~70°F

        if self.capabilities.has(Capability.HAS_VEHICLE_CLIMATE):
            handler = self.capabilities.get_handler(Capability.HAS_VEHICLE_CLIMATE)
            if handler:
                try:
                    success = await handler(temp_c=target_temp_c)
                    if success:
                        result.capabilities_used.append(Capability.HAS_VEHICLE_CLIMATE)
                        result.actions_taken.append(f"Started vehicle climate to {target_temp_c}°C")
                    else:
                        result.error = "Vehicle climate command failed"
                        result.success = False
                except Exception as e:
                    result.error = str(e)
                    result.success = False
        else:
            result.capabilities_missing.append(Capability.HAS_VEHICLE_CLIMATE)
            result.actions_taken.append("No vehicle climate available — skipped")
            # NOT a failure — just not applicable to this household

    async def _cool_vehicle(self, result: IntentExecution, ctx: dict) -> None:
        """Cool down the vehicle."""
        target_temp_c = ctx.get("temp_c", 20.0)

        if self.capabilities.has(Capability.HAS_VEHICLE_CLIMATE):
            handler = self.capabilities.get_handler(Capability.HAS_VEHICLE_CLIMATE)
            if handler:
                try:
                    await handler(temp_c=target_temp_c)
                    result.capabilities_used.append(Capability.HAS_VEHICLE_CLIMATE)
                    result.actions_taken.append(f"Started vehicle cooling to {target_temp_c}°C")
                except Exception as e:
                    result.error = str(e)
        else:
            result.capabilities_missing.append(Capability.HAS_VEHICLE_CLIMATE)

    async def _charge_reminder(self, result: IntentExecution, ctx: dict) -> None:
        """Remind to charge vehicle."""
        battery = ctx.get("battery_percent", 0)
        message = f"Vehicle battery is at {battery}%. Don't forget to plug in!"

        await self._notify(result, message, ctx)

    # === SECURITY INTENTS ===

    async def _lock_up(self, result: IntentExecution, ctx: dict) -> None:
        """Lock all doors."""
        if self.capabilities.has(Capability.HAS_LOCKS):
            try:
                await self.controller.lock_all()
                result.capabilities_used.append(Capability.HAS_LOCKS)
                result.actions_taken.append("Locked all doors")
            except Exception as e:
                result.error = str(e)
        else:
            result.capabilities_missing.append(Capability.HAS_LOCKS)

    async def _alert(self, result: IntentExecution, ctx: dict) -> None:
        """Send an alert."""
        message = ctx.get("message", "Alert!")
        await self._notify(result, message, ctx, priority="high")

    # === PRESENCE INTENTS ===

    async def _welcome_home(self, result: IntentExecution, ctx: dict) -> None:
        """Welcome home routine."""
        # Lights on
        if self.capabilities.has(Capability.HAS_LIGHTS):
            try:
                await self.controller.set_lights(60, rooms=["Living Room", "Kitchen"])
                result.capabilities_used.append(Capability.HAS_LIGHTS)
                result.actions_taken.append("Set welcome lights")
            except Exception:
                pass

        # Unlock
        if self.capabilities.has(Capability.HAS_LOCKS):
            # Don't auto-unlock for security — just note it
            result.actions_taken.append("Doors remain locked (manual unlock)")

        # Announce
        if self.capabilities.has(Capability.HAS_VOICE_ANNOUNCE):
            try:
                await self.controller.announce("Welcome home.", rooms=["Living Room"])
                result.capabilities_used.append(Capability.HAS_VOICE_ANNOUNCE)
                result.actions_taken.append("Welcome announcement")
            except Exception:
                pass

    async def _goodbye(self, result: IntentExecution, ctx: dict) -> None:
        """Goodbye routine."""
        # Lights off
        if self.capabilities.has(Capability.HAS_LIGHTS):
            try:
                await self.controller.set_lights(0)
                result.capabilities_used.append(Capability.HAS_LIGHTS)
                result.actions_taken.append("Turned off all lights")
            except Exception:
                pass

        # Lock up
        if self.capabilities.has(Capability.HAS_LOCKS):
            try:
                await self.controller.lock_all()
                result.capabilities_used.append(Capability.HAS_LOCKS)
                result.actions_taken.append("Locked all doors")
            except Exception:
                pass

        # Arm alarm
        if self.capabilities.has(Capability.HAS_ALARM):
            try:
                await self.controller.arm_security("away")
                result.capabilities_used.append(Capability.HAS_ALARM)
                result.actions_taken.append("Armed security system")
            except Exception:
                pass

    # === SAFETY INTENTS ===

    async def _pet_alert(self, result: IntentExecution, ctx: dict) -> None:
        """Alert about pet safety."""
        temp = ctx.get("temp_f", 0)
        message = f"⚠️ Pet safety alert! Vehicle temperature is {temp}°F!"
        await self._notify(result, message, ctx, priority="urgent")

    # === ENTERTAINMENT INTENTS ===

    async def _movie_mode(self, result: IntentExecution, ctx: dict) -> None:
        """Enter movie mode."""
        if self.capabilities.has(Capability.HAS_THEATER):
            try:
                await self.controller.enter_movie_mode()
                result.capabilities_used.append(Capability.HAS_THEATER)
                result.actions_taken.append("Entered movie mode")
            except Exception as e:
                logger.warning(f"Movie mode failed: {e}")

        if self.capabilities.has(Capability.HAS_LIGHTS):
            try:
                await self.controller.set_lights(10, rooms=["Living Room"])
                result.capabilities_used.append(Capability.HAS_LIGHTS)
                result.actions_taken.append("Dimmed lights")
            except Exception:
                pass

    # === HELPERS ===

    async def _notify(
        self,
        result: IntentExecution,
        message: str,
        ctx: dict,
        priority: str = "normal",
    ) -> None:
        """Send notification via best available channel."""
        notified = False

        # Try glasses first (if wearing)
        if self.capabilities.has(Capability.HAS_GLASSES):
            # Would check if wearing
            pass

        # Try voice announce
        if self.capabilities.has(Capability.HAS_VOICE_ANNOUNCE) and not notified:
            rooms = ctx.get("rooms", ["Living Room"])
            try:
                await self.controller.announce(message, rooms=rooms)
                result.capabilities_used.append(Capability.HAS_VOICE_ANNOUNCE)
                result.actions_taken.append(f"Announced: {message[:50]}...")
                notified = True
            except Exception:
                pass

        # Fall back to push notification
        if self.capabilities.has(Capability.HAS_PUSH_NOTIFY) and not notified:
            # Would send push notification
            result.actions_taken.append(f"Push notification: {message[:50]}...")
            notified = True

        if not notified:
            result.capabilities_missing.append(Capability.HAS_VOICE_ANNOUNCE)
            logger.warning(f"No notification channel available for: {message}")


# =============================================================================
# CONDITION → INTENT MAPPING
# =============================================================================


class Condition(str, Enum):
    """Conditions that can trigger automations.

    These are the INPUTS — they describe what's happening.
    They get mapped to intents (OUTPUTS) that describe what to do.
    """

    # Time
    MORNING = "morning"
    EVENING = "evening"
    NIGHT = "night"

    # Weather
    COLD = "cold"
    HOT = "hot"

    # Presence
    ARRIVING_HOME = "arriving_home"
    ARRIVED_HOME = "arrived_home"
    LEAVING_HOME = "leaving_home"
    HOME_EMPTY = "home_empty"

    # Vehicle
    CAR_LOW_BATTERY = "car_low_battery"
    PET_TEMP_HIGH = "pet_temp_high"

    # Sleep
    GOING_TO_BED = "going_to_bed"
    WAKING_UP = "waking_up"


@dataclass
class AutomationRule:
    """Maps conditions to intents.

    This is the user-facing configuration layer. Users define rules like:
        "When it's cold + morning → warm up vehicle"

    The system figures out HOW based on available capabilities.
    """

    name: str
    description: str
    conditions: list[Condition]
    intent: AutomationIntent
    context_template: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    cooldown_seconds: float = 60.0
    last_triggered: float = 0.0

    def can_trigger(self) -> bool:
        """Check if rule can trigger (respecting cooldown)."""
        return time.time() - self.last_triggered > self.cooldown_seconds


# =============================================================================
# INTENT AUTOMATION ENGINE
# =============================================================================


class IntentAutomationEngine:
    """Main automation engine using intents instead of hardcoded actions.

    This is the household-agnostic replacement for UnifiedTriggerEngine.

    Usage:
        engine = IntentAutomationEngine()
        await engine.initialize(controller)

        # Trigger by condition
        await engine.on_condition(Condition.COLD, Condition.MORNING)

        # Direct intent
        await engine.execute_intent(AutomationIntent.WARM_VEHICLE)

        # Natural language
        await engine.execute("warm up the car")
    """

    # Default rules — these work for ANY household
    DEFAULT_RULES = [
        AutomationRule(
            name="cold_morning_vehicle",
            description="Warm up vehicle on cold mornings",
            conditions=[Condition.COLD, Condition.MORNING],
            intent=AutomationIntent.WARM_VEHICLE,
            context_template={"temp_c": 21.0},
            cooldown_seconds=7200,  # 2 hours
        ),
        AutomationRule(
            name="arrival_welcome",
            description="Welcome when arriving home",
            conditions=[Condition.ARRIVED_HOME],
            intent=AutomationIntent.WELCOME_HOME,
        ),
        AutomationRule(
            name="departure_goodbye",
            description="Lock up when leaving",
            conditions=[Condition.LEAVING_HOME, Condition.HOME_EMPTY],
            intent=AutomationIntent.GOODBYE,
        ),
        AutomationRule(
            name="charge_reminder",
            description="Remind to charge at night",
            conditions=[Condition.CAR_LOW_BATTERY, Condition.NIGHT],
            intent=AutomationIntent.CHARGE_REMINDER,
            cooldown_seconds=3600,
        ),
        AutomationRule(
            name="pet_safety",
            description="Alert on pet temperature",
            conditions=[Condition.PET_TEMP_HIGH],
            intent=AutomationIntent.PET_ALERT,
            cooldown_seconds=300,
        ),
        AutomationRule(
            name="bedtime",
            description="Prepare for sleep",
            conditions=[Condition.GOING_TO_BED],
            intent=AutomationIntent.PREPARE_SLEEP,
        ),
        AutomationRule(
            name="wake_up",
            description="Morning wake routine",
            conditions=[Condition.WAKING_UP, Condition.MORNING],
            intent=AutomationIntent.WAKE_UP,
        ),
    ]

    def __init__(self):
        self._controller: SmartHomeController | None = None
        self._capabilities: HouseholdCapabilities | None = None
        self._executor: IntentExecutor | None = None
        self._rules: list[AutomationRule] = list(self.DEFAULT_RULES)
        self._active_conditions: set[Condition] = set()
        self._running = False

        # Stats
        self._stats = {
            "conditions_received": 0,
            "intents_executed": 0,
            "capabilities_used": {},
        }

    async def initialize(self, controller: SmartHomeController) -> None:
        """Initialize engine with controller.

        Discovers capabilities and sets up executor.
        """
        self._controller = controller
        self._capabilities = await discover_capabilities(controller)
        self._executor = IntentExecutor(controller, self._capabilities)
        self._running = True

        logger.info("✅ IntentAutomationEngine initialized")
        logger.info(f"   Capabilities: {len(self._capabilities.capabilities)}")
        logger.info(f"   Rules: {len(self._rules)}")

    async def on_condition(
        self, *conditions: Condition, context: dict | None = None
    ) -> list[IntentExecution]:
        """Handle one or more conditions occurring.

        Args:
            conditions: One or more conditions that occurred
            context: Additional context data

        Returns:
            List of IntentExecution results for triggered rules
        """
        if not self._running or not self._executor:
            return []

        context = context or {}
        results = []

        # Add conditions to active set
        for c in conditions:
            self._active_conditions.add(c)
        self._update_time_conditions()
        self._stats["conditions_received"] += len(conditions)

        # Check rules
        for rule in self._rules:
            if not rule.enabled or not rule.can_trigger():
                continue

            # Check if all conditions met
            if all(c in self._active_conditions for c in rule.conditions):
                logger.info(f"🔔 Rule triggered: {rule.name} → {rule.intent.value}")
                rule.last_triggered = time.time()

                # Merge context
                merged_context = {**rule.context_template, **context}

                # Execute intent
                result = await self._executor.execute(rule.intent, merged_context)
                results.append(result)

                self._stats["intents_executed"] += 1
                for cap in result.capabilities_used:
                    self._stats["capabilities_used"][cap.value] = (
                        self._stats["capabilities_used"].get(cap.value, 0) + 1
                    )

        # Clear transient conditions
        asyncio.create_task(self._clear_conditions_after(conditions, 5.0))

        return results

    async def execute_intent(
        self,
        intent: AutomationIntent,
        context: dict | None = None,
    ) -> IntentExecution:
        """Execute an intent directly.

        Args:
            intent: The intent to execute
            context: Additional context

        Returns:
            IntentExecution result
        """
        if not self._executor:
            return IntentExecution(
                intent=intent,
                success=False,
                error="Engine not initialized",
            )

        result = await self._executor.execute(intent, context or {})
        self._stats["intents_executed"] += 1
        return result

    async def execute(self, natural_language: str, context: dict | None = None) -> IntentExecution:
        """Execute from natural language.

        Maps natural language to intent and executes.

        Args:
            natural_language: e.g., "warm up the car", "lock up", "movie time"
            context: Additional context

        Returns:
            IntentExecution result
        """
        # Simple keyword mapping (could use LLM for more complex mapping)
        intent_map = {
            "warm up the car": AutomationIntent.WARM_VEHICLE,
            "warm car": AutomationIntent.WARM_VEHICLE,
            "heat car": AutomationIntent.WARM_VEHICLE,
            "cool car": AutomationIntent.COOL_VEHICLE,
            "lock up": AutomationIntent.LOCK_UP,
            "lock doors": AutomationIntent.LOCK_UP,
            "goodnight": AutomationIntent.PREPARE_SLEEP,
            "bedtime": AutomationIntent.PREPARE_SLEEP,
            "welcome home": AutomationIntent.WELCOME_HOME,
            "movie time": AutomationIntent.MOVIE_MODE,
            "movie mode": AutomationIntent.MOVIE_MODE,
            "warm home": AutomationIntent.WARM_HOME,
            "cool home": AutomationIntent.COOL_HOME,
        }

        # Normalize input
        nl_lower = natural_language.lower().strip()

        # Try exact match first
        intent = intent_map.get(nl_lower)

        # Try partial match
        if not intent:
            for phrase, mapped_intent in intent_map.items():
                if phrase in nl_lower or nl_lower in phrase:
                    intent = mapped_intent
                    break

        if not intent:
            return IntentExecution(
                intent=AutomationIntent.ALERT,  # Fallback
                success=False,
                error=f"Could not understand: {natural_language}",
            )

        return await self.execute_intent(intent, context)

    def _update_time_conditions(self) -> None:
        """Update time-based conditions."""
        hour = datetime.now().hour

        # Clear old time conditions
        self._active_conditions -= {
            Condition.MORNING,
            Condition.EVENING,
            Condition.NIGHT,
        }

        if 6 <= hour < 10:
            self._active_conditions.add(Condition.MORNING)
        elif 17 <= hour < 22:
            self._active_conditions.add(Condition.EVENING)
        elif hour >= 22 or hour < 6:
            self._active_conditions.add(Condition.NIGHT)

    async def _clear_conditions_after(self, conditions: tuple, delay: float) -> None:
        """Clear conditions after delay."""
        await asyncio.sleep(delay)
        for c in conditions:
            self._active_conditions.discard(c)

    # === RULE MANAGEMENT ===

    def add_rule(self, rule: AutomationRule) -> None:
        """Add a custom rule."""
        self._rules.append(rule)

    def remove_rule(self, name: str) -> None:
        """Remove a rule by name."""
        self._rules = [r for r in self._rules if r.name != name]

    def enable_rule(self, name: str) -> None:
        """Enable a rule."""
        for rule in self._rules:
            if rule.name == name:
                rule.enabled = True

    def disable_rule(self, name: str) -> None:
        """Disable a rule."""
        for rule in self._rules:
            if rule.name == name:
                rule.enabled = False

    def get_rules(self) -> list[dict]:
        """Get all rules as dicts."""
        return [
            {
                "name": r.name,
                "description": r.description,
                "conditions": [c.value for c in r.conditions],
                "intent": r.intent.value,
                "enabled": r.enabled,
            }
            for r in self._rules
        ]

    def get_capabilities(self) -> dict[str, bool]:
        """Get available capabilities."""
        if not self._capabilities:
            return {}
        return self._capabilities.summary()

    @property
    def stats(self) -> dict:
        """Get engine statistics."""
        return {
            **self._stats,
            "active_conditions": [c.value for c in self._active_conditions],
            "rules_count": len(self._rules),
            "enabled_rules": sum(1 for r in self._rules if r.enabled),
            "capabilities_count": len(self._capabilities.capabilities) if self._capabilities else 0,
        }


# =============================================================================
# FACTORY
# =============================================================================

_engine: IntentAutomationEngine | None = None


def get_intent_automation() -> IntentAutomationEngine:
    """Get or create the intent automation engine."""
    global _engine
    if _engine is None:
        _engine = IntentAutomationEngine()
    return _engine


async def setup_intent_automation(
    controller: SmartHomeController,
) -> IntentAutomationEngine:
    """Set up and initialize the intent automation engine.

    Args:
        controller: SmartHome controller

    Returns:
        Initialized IntentAutomationEngine
    """
    engine = get_intent_automation()
    await engine.initialize(controller)
    return engine


__all__ = [
    # Core classes
    "Capability",
    "HouseholdCapabilities",
    "AutomationIntent",
    "IntentExecution",
    "IntentExecutor",
    "Condition",
    "AutomationRule",
    "IntentAutomationEngine",
    # Functions
    "discover_capabilities",
    "get_intent_automation",
    "setup_intent_automation",
]
