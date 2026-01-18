"""Advanced Automation — Predictive and Intelligent Home Control.

Implements improvements identified in architecture audit (Dec 30, 2025):
1. State Reconciliation — Periodic sync between cached and actual device state
2. Predictive HVAC — Pre-condition home based on arrival prediction
3. Circadian Lighting — Time-of-day color temperature adjustment
4. Guest Mode — Differentiate between owner and guest presence
5. Vacation Mode — Security simulation with random lighting
6. Sleep Optimization — Coordinate Eight Sleep + HVAC + Shades

Created: December 30, 2025
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami_smarthome.controller import SmartHomeController

logger = logging.getLogger(__name__)


# =============================================================================
# CIRCADIAN LIGHTING
# =============================================================================


class CircadianPhase(str, Enum):
    """Circadian rhythm phase."""

    DAWN = "dawn"  # 5am-7am: Warm, gradually brightening
    MORNING = "morning"  # 7am-10am: Energizing, cooler
    MIDDAY = "midday"  # 10am-3pm: Peak alertness, neutral
    AFTERNOON = "afternoon"  # 3pm-6pm: Slightly warm
    EVENING = "evening"  # 6pm-9pm: Warm, dimming
    NIGHT = "night"  # 9pm-11pm: Very warm, dim
    LATE_NIGHT = "late_night"  # 11pm-5am: Minimal, very warm


@dataclass
class CircadianSettings:
    """Circadian lighting settings for a phase."""

    phase: CircadianPhase
    color_temp_kelvin: int  # 2200K (warm) to 6500K (cool)
    max_brightness: int  # 0-100 (limits bright scenes)
    bias_brightness: int  # For TV bias lighting

    @classmethod
    def for_phase(cls, phase: CircadianPhase) -> CircadianSettings:
        """Get settings for a circadian phase."""
        settings_map = {
            CircadianPhase.DAWN: cls(phase, 2400, 40, 5),
            CircadianPhase.MORNING: cls(phase, 3500, 100, 15),
            CircadianPhase.MIDDAY: cls(phase, 4500, 100, 20),
            CircadianPhase.AFTERNOON: cls(phase, 4000, 100, 15),
            CircadianPhase.EVENING: cls(phase, 3000, 80, 10),
            CircadianPhase.NIGHT: cls(phase, 2700, 50, 5),
            CircadianPhase.LATE_NIGHT: cls(phase, 2200, 20, 3),
        }
        return settings_map.get(phase, settings_map[CircadianPhase.MIDDAY])


def get_current_circadian_phase() -> CircadianPhase:
    """Get current circadian phase based on time."""
    hour = datetime.now().hour

    if 5 <= hour < 7:
        return CircadianPhase.DAWN
    elif 7 <= hour < 10:
        return CircadianPhase.MORNING
    elif 10 <= hour < 15:
        return CircadianPhase.MIDDAY
    elif 15 <= hour < 18:
        return CircadianPhase.AFTERNOON
    elif 18 <= hour < 21:
        return CircadianPhase.EVENING
    elif 21 <= hour < 23:
        return CircadianPhase.NIGHT
    else:  # 23-5
        return CircadianPhase.LATE_NIGHT


def get_circadian_color_temp() -> int:
    """Get appropriate color temperature for current time.

    Returns:
        Color temperature in Kelvin (2200-6500K)
    """
    phase = get_current_circadian_phase()
    return CircadianSettings.for_phase(phase).color_temp_kelvin


def get_circadian_max_brightness() -> int:
    """Get maximum brightness allowed for current circadian phase.

    Returns:
        Maximum brightness level (0-100)
    """
    phase = get_current_circadian_phase()
    return CircadianSettings.for_phase(phase).max_brightness


# =============================================================================
# GUEST MODE
# =============================================================================


class GuestMode(str, Enum):
    """Guest mode states."""

    NONE = "none"  # Normal operation (owner only)
    GUEST_PRESENT = "guest_present"  # Guest visiting (reduce automation)
    PARTY = "party"  # Party mode (all rooms active)
    AIRBNB = "airbnb"  # Rental mode (disable some features)


@dataclass
class GuestModeConfig:
    """Configuration for guest mode."""

    mode: GuestMode = GuestMode.NONE
    guest_count: int = 0
    start_time: float = 0.0
    end_time: float | None = None

    # Behavior adjustments
    disable_auto_lights: bool = False
    disable_auto_hvac: bool = False
    disable_presence_tracking: bool = False
    unlock_guest_rooms: list[str] = field(default_factory=list)

    # Privacy
    disable_cameras_in_rooms: list[str] = field(default_factory=list)

    @classmethod
    def for_mode(cls, mode: GuestMode) -> GuestModeConfig:
        """Get default config for a mode."""
        if mode == GuestMode.NONE:
            return cls(mode=mode)
        elif mode == GuestMode.GUEST_PRESENT:
            return cls(
                mode=mode,
                disable_auto_lights=True,  # Don't turn off lights automatically
                unlock_guest_rooms=["Game Room"],
            )
        elif mode == GuestMode.PARTY:
            return cls(
                mode=mode,
                disable_auto_lights=True,
                disable_presence_tracking=True,
            )
        elif mode == GuestMode.AIRBNB:
            return cls(
                mode=mode,
                disable_auto_lights=True,
                disable_auto_hvac=True,
                disable_presence_tracking=True,
                unlock_guest_rooms=["Game Room", "Bath 4", "Bed 4"],
                disable_cameras_in_rooms=["Game Room", "Bath 4", "Bed 4"],
            )
        return cls(mode=mode)


# =============================================================================
# VACATION MODE
# =============================================================================


@dataclass
class VacationModeConfig:
    """Configuration for vacation mode."""

    enabled: bool = False
    start_date: datetime | None = None
    end_date: datetime | None = None

    # Security simulation
    simulate_occupancy: bool = True
    random_lights_enabled: bool = True
    random_lights_rooms: list[str] = field(
        default_factory=lambda: ["Living Room", "Kitchen", "Primary Bedroom", "Office"]
    )
    lights_on_hour: int = 17  # 5 PM
    lights_off_hour: int = 23  # 11 PM

    # Energy saving
    hvac_setback_temp_f: float = 62.0  # Winter
    hvac_setpoint_summer_f: float = 78.0  # Summer

    # Notifications
    notify_on_motion: bool = True
    notify_on_door_open: bool = True


class OccupancySimulator:
    """Simulates occupancy for vacation mode."""

    def __init__(self, controller: SmartHomeController, config: VacationModeConfig):
        self.controller = controller
        self.config = config
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start occupancy simulation."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._simulation_loop())
        logger.info("🏖️ Vacation mode: Occupancy simulation started")

    async def stop(self) -> None:
        """Stop occupancy simulation."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("🏖️ Vacation mode: Occupancy simulation stopped")

    async def _simulation_loop(self) -> None:
        """Main simulation loop."""
        while self._running:
            try:
                hour = datetime.now().hour

                # Only simulate during "active hours"
                if self.config.lights_on_hour <= hour < self.config.lights_off_hour:
                    await self._simulate_activity()
                else:
                    # Night - all lights off (parallel)
                    if self.config.random_lights_rooms:
                        await asyncio.gather(
                            *[
                                self.controller.set_lights(0, rooms=[room])
                                for room in self.config.random_lights_rooms
                            ],
                            return_exceptions=True,
                        )

                # Random interval (15-45 minutes)
                await asyncio.sleep(random.randint(15, 45) * 60)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Occupancy simulation error: {e}")
                await asyncio.sleep(300)  # 5 min on error

    async def _simulate_activity(self) -> None:
        """Simulate realistic activity pattern."""
        # Pick 1-2 random rooms
        num_rooms = random.randint(1, 2)
        active_rooms = random.sample(self.config.random_lights_rooms, num_rooms)

        # Turn on lights in active rooms, off in others
        for room in self.config.random_lights_rooms:
            if room in active_rooms:
                level = random.randint(40, 80)
                await self.controller.set_lights(level, rooms=[room])
            else:
                await self.controller.set_lights(0, rooms=[room])

        logger.debug(f"🏖️ Simulated activity in: {active_rooms}")


# =============================================================================
# STATE RECONCILIATION
# =============================================================================


class StateReconciler:
    """Periodically reconciles cached state with actual device state.

    Detects and logs discrepancies when devices are controlled externally
    (physical switches, other apps, etc.)
    """

    def __init__(self, controller: SmartHomeController):
        self.controller = controller
        self._running = False
        self._task: asyncio.Task | None = None
        self._reconciliation_interval = 300.0  # 5 minutes
        self._last_known_state: dict[str, Any] = {}
        self._discrepancies: list[dict[str, Any]] = []

    async def start(self) -> None:
        """Start state reconciliation loop."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._reconciliation_loop())
        logger.info("🔄 State reconciliation started (5 min interval)")

    async def stop(self) -> None:
        """Stop state reconciliation."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _reconciliation_loop(self) -> None:
        """Main reconciliation loop."""
        while self._running:
            try:
                await asyncio.sleep(self._reconciliation_interval)
                await self.reconcile()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"State reconciliation error: {e}")
                await asyncio.sleep(60)  # 1 min on error

    async def reconcile(self) -> dict[str, Any]:
        """Perform state reconciliation.

        Returns:
            Dict with reconciliation results
        """
        control4 = self.controller._integration_manager.get_integration("control4")
        if not control4:
            return {"error": "Control4 not connected"}

        discrepancies = []

        # Get current state from Control4
        try:
            lights = control4.get_lights()
            shades = control4.get_shades()

            # Check lights
            for light_id, light_info in lights.items():
                actual_level = light_info.get("level", 0)
                cached_level = self._last_known_state.get(f"light_{light_id}", {}).get("level")

                if cached_level is not None and cached_level != actual_level:
                    discrepancy = {
                        "type": "light",
                        "id": light_id,
                        "name": light_info.get("name", "Unknown"),
                        "cached": cached_level,
                        "actual": actual_level,
                        "timestamp": time.time(),
                    }
                    discrepancies.append(discrepancy)
                    logger.info(
                        f"🔄 Light discrepancy: {light_info.get('name')} "
                        f"expected {cached_level}%, actual {actual_level}%"
                    )

                # Update cached state
                self._last_known_state[f"light_{light_id}"] = {"level": actual_level}

            # Check shades
            for shade_id, shade_info in shades.items():
                actual_level = shade_info.get("level", 0)
                cached_level = self._last_known_state.get(f"shade_{shade_id}", {}).get("level")

                if cached_level is not None and cached_level != actual_level:
                    discrepancy = {
                        "type": "shade",
                        "id": shade_id,
                        "name": shade_info.get("name", "Unknown"),
                        "cached": cached_level,
                        "actual": actual_level,
                        "timestamp": time.time(),
                    }
                    discrepancies.append(discrepancy)
                    logger.info(
                        f"🔄 Shade discrepancy: {shade_info.get('name')} "
                        f"expected {cached_level}%, actual {actual_level}%"
                    )

                self._last_known_state[f"shade_{shade_id}"] = {"level": actual_level}

        except Exception as e:
            logger.error(f"Failed to reconcile state: {e}")
            return {"error": str(e)}

        # Store discrepancies
        self._discrepancies.extend(discrepancies)
        # Keep only last 100 discrepancies
        self._discrepancies = self._discrepancies[-100:]

        return {
            "discrepancies_found": len(discrepancies),
            "discrepancies": discrepancies,
            "total_lights_checked": len(lights) if lights else 0,
            "total_shades_checked": len(shades) if shades else 0,
        }

    def get_recent_discrepancies(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get recent state discrepancies."""
        return self._discrepancies[-limit:]

    def record_command(
        self, device_type: str, device_id: int, expected_state: dict[str, Any]
    ) -> None:
        """Record expected state after a command.

        Call this after sending a command to track expected state.
        """
        key = f"{device_type}_{device_id}"
        self._last_known_state[key] = expected_state


# =============================================================================
# PREDICTIVE HVAC
# =============================================================================


class PredictiveHVAC:
    """Predictive HVAC pre-conditioning based on arrival prediction.

    Uses pattern learning to predict arrival times and pre-heats/cools
    the home before owner arrives.
    """

    def __init__(self, controller: SmartHomeController):
        self.controller = controller
        self._running = False
        self._task: asyncio.Task | None = None
        self._pre_conditioning_lead_time_minutes = 30
        self._last_preconditioning: float = 0.0

    async def start(self) -> None:
        """Start predictive HVAC monitoring."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._monitoring_loop())
        logger.info("🌡️ Predictive HVAC started (30 min lead time)")

    async def stop(self) -> None:
        """Stop predictive HVAC."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _monitoring_loop(self) -> None:
        """Monitor for arrival prediction and pre-condition."""
        while self._running:
            try:
                # Check every 5 minutes
                await asyncio.sleep(300)

                # Only pre-condition if owner is away
                if self.controller.is_owner_home():
                    continue

                # Get arrival prediction
                eta_minutes = await self._predict_arrival_eta()

                if eta_minutes is not None:
                    if eta_minutes <= self._pre_conditioning_lead_time_minutes:
                        # Check cooldown (don't re-trigger for 2 hours)
                        if time.time() - self._last_preconditioning > 7200:
                            await self._precondition_home()
                            self._last_preconditioning = time.time()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Predictive HVAC error: {e}")
                await asyncio.sleep(60)

    async def _predict_arrival_eta(self) -> int | None:
        """Predict ETA in minutes.

        Returns:
            Estimated minutes until arrival, or None if unknown
        """
        # Check Tesla location
        tesla = self.controller._integration_manager.get_integration("tesla")
        if tesla and tesla.is_connected:
            distance = tesla.get_distance_to_home()
            if distance is not None and distance < 50:  # Within 50 miles
                # Rough estimate: 2 min/mile average
                return int(distance * 2)

        # Check pattern-based prediction
        presence = self.controller._presence
        if hasattr(presence, "predict_arrival_probability"):
            prob = presence.predict_arrival_probability()
            if prob > 0.7:  # 70% confident
                return 20  # Assume 20 minutes

        return None

    async def _precondition_home(self) -> None:
        """Pre-condition the home for arrival."""
        logger.info("🌡️ Pre-conditioning home for predicted arrival")

        # Determine season for temp target
        month = datetime.now().month
        is_winter = month in (11, 12, 1, 2, 3)

        if is_winter:
            target_temp = 70  # Heat up
        else:
            target_temp = 74  # Cool down

        # Set HVAC in main rooms
        rooms_to_condition = ["Living Room", "Kitchen", "Primary Bedroom"]

        for room in rooms_to_condition:
            try:
                await self.controller.set_room_temp(room, target_temp)
            except Exception as e:
                logger.warning(f"Failed to pre-condition {room}: {e}")

        logger.info(f"🌡️ Pre-conditioning set to {target_temp}°F in {len(rooms_to_condition)} rooms")


# =============================================================================
# SLEEP OPTIMIZATION
# =============================================================================


class SleepOptimizer:
    """Coordinates Eight Sleep + HVAC + Shades for optimal sleep.

    Features:
    - Lower bed temp during deep sleep phases
    - Raise room temp 30 min before wake time
    - Gradually open shades at wake time
    - Adjust color temp in evening for better melatonin
    """

    def __init__(self, controller: SmartHomeController):
        self.controller = controller
        self._running = False
        self._task: asyncio.Task | None = None

        # Configuration
        self.wake_time_hour = 7
        self.wake_time_minute = 0
        self.pre_wake_minutes = 30
        self.shade_gradual_open_minutes = 20

    async def start(self) -> None:
        """Start sleep optimization."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._optimization_loop())
        logger.info("😴 Sleep optimization started")

    async def stop(self) -> None:
        """Stop sleep optimization."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _optimization_loop(self) -> None:
        """Main optimization loop."""
        while self._running:
            try:
                now = datetime.now()

                # Check if it's pre-wake time
                wake_time = now.replace(
                    hour=self.wake_time_hour,
                    minute=self.wake_time_minute,
                    second=0,
                    microsecond=0,
                )

                time_to_wake = (wake_time - now).total_seconds() / 60

                # Pre-wake routine (30 min before)
                if 0 < time_to_wake <= self.pre_wake_minutes:
                    # Check if anyone is actually in bed
                    if self.controller.is_anyone_in_bed():
                        await self._pre_wake_routine(time_to_wake)

                # Sleep check every 5 minutes
                await asyncio.sleep(300)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Sleep optimization error: {e}")
                await asyncio.sleep(60)

    async def _pre_wake_routine(self, minutes_to_wake: float) -> None:
        """Execute pre-wake routine."""
        logger.info(f"😴 Pre-wake routine: {minutes_to_wake:.0f} min to wake time")

        # Gradually raise room temperature
        current_temp = 68  # Sleep temp
        target_temp = 70  # Wake temp
        progress = 1 - (minutes_to_wake / self.pre_wake_minutes)
        temp = current_temp + (target_temp - current_temp) * progress

        await self.controller.set_room_temp("Primary Bedroom", int(temp))

        # Gradually warm bed temperature (if Eight Sleep connected)
        eight_sleep = self.controller._integration_manager.get_integration("eight_sleep")
        if eight_sleep:
            bed_temp = int(-10 + 20 * progress)  # -10 (cold) to +10 (warm)
            await self.controller.set_bed_temperature(bed_temp, "both")

        # Gradually open shades (last 20 minutes)
        if minutes_to_wake <= self.shade_gradual_open_minutes:
            shade_progress = 1 - (minutes_to_wake / self.shade_gradual_open_minutes)
            shade_level = int(shade_progress * 100)  # 0 (closed) to 100 (open)
            await self.controller.set_shades(shade_level, rooms=["Primary Bedroom"])


# =============================================================================
# CELESTIAL SHADE OPTIMIZER
# =============================================================================


class CelestialShadeOptimizer:
    """Automatically optimizes shades based on sun position.

    Runs every 30 minutes during daylight to prevent glare and
    maximize natural light when the sun isn't hitting windows directly.

    h(x) >= 0: Respects resident manual overrides via CBF.
    """

    def __init__(self, controller: SmartHomeController):
        self.controller = controller
        self._running = False
        self._task: asyncio.Task | None = None
        self._interval_minutes = 30  # Run every 30 minutes

    async def start(self) -> None:
        """Start celestial shade optimization."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._optimization_loop())
        logger.info("☀️ Celestial shade optimizer started (30 min interval)")

    async def stop(self) -> None:
        """Stop celestial shade optimization."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _optimization_loop(self) -> None:
        """Main optimization loop - runs every 30 minutes during daylight."""
        # Run immediately on start
        await self._run_optimization()

        while self._running:
            try:
                # Wait for next interval
                await asyncio.sleep(self._interval_minutes * 60)

                # Check if it's daytime before running
                try:
                    from kagami.core.celestial import (
                        HOME_LATITUDE,
                        HOME_LONGITUDE,
                        sun_position,
                    )

                    sun = sun_position(HOME_LATITUDE, HOME_LONGITUDE)
                    if not sun.is_day:
                        logger.debug("☀️ Celestial: Skipping (nighttime)")
                        continue
                except ImportError:
                    pass  # Run anyway if celestial module not available

                await self._run_optimization()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"☀️ Celestial optimization error: {e}")
                await asyncio.sleep(60)  # Wait 1 min on error

    async def _run_optimization(self) -> None:
        """Execute shade optimization."""
        try:
            results = await self.controller.optimize_shades_celestial()

            if results:
                optimized = sum(1 for r in results if r.sun_hits)
                logger.info(f"☀️ Celestial: Optimized {optimized}/{len(results)} shades")
        except Exception as e:
            logger.error(f"☀️ Celestial optimization failed: {e}")

    async def run_now(self) -> list:
        """Run optimization immediately (manual trigger)."""
        return await self.controller.optimize_shades_celestial()


# =============================================================================
# ADVANCED AUTOMATION MANAGER
# =============================================================================


class AdvancedAutomationManager:
    """Central manager for all advanced automation features.

    Coordinates:
    - State reconciliation
    - Predictive HVAC
    - Circadian lighting
    - Celestial shades (NEW)
    - Guest mode
    - Vacation mode
    - Sleep optimization
    """

    def __init__(self, controller: SmartHomeController):
        self.controller = controller

        # Feature modules
        self.state_reconciler = StateReconciler(controller)
        self.predictive_hvac = PredictiveHVAC(controller)
        self.sleep_optimizer = SleepOptimizer(controller)
        self.celestial_shades = CelestialShadeOptimizer(controller)  # NEW

        # Modes
        self._guest_mode = GuestModeConfig()
        self._vacation_mode = VacationModeConfig()
        self._occupancy_simulator: OccupancySimulator | None = None

        # Circadian
        self._circadian_enabled = True

        self._running = False

    async def start(self) -> None:
        """Start all advanced automation features."""
        self._running = True

        # Start modules in parallel
        await asyncio.gather(
            self.state_reconciler.start(),
            self.predictive_hvac.start(),
            self.sleep_optimizer.start(),
            self.celestial_shades.start(),  # NEW
            return_exceptions=True,
        )

        logger.info("✨ Advanced automation manager started")

    async def stop(self) -> None:
        """Stop all advanced automation features."""
        self._running = False

        # Stop modules in parallel
        await asyncio.gather(
            self.state_reconciler.stop(),
            self.predictive_hvac.stop(),
            self.sleep_optimizer.stop(),
            self.celestial_shades.stop(),  # NEW
            return_exceptions=True,
        )

        # Stop occupancy simulation if active
        if self._occupancy_simulator:
            await self._occupancy_simulator.stop()

        logger.info("✨ Advanced automation manager stopped")

    # =========================================================================
    # Guest Mode
    # =========================================================================

    def set_guest_mode(self, mode: GuestMode, guest_count: int = 1) -> GuestModeConfig:
        """Set guest mode.

        Args:
            mode: Guest mode to activate
            guest_count: Number of guests

        Returns:
            Active guest mode configuration
        """
        self._guest_mode = GuestModeConfig.for_mode(mode)
        self._guest_mode.guest_count = guest_count
        self._guest_mode.start_time = time.time()

        logger.info(f"👥 Guest mode set to: {mode.value} ({guest_count} guests)")
        return self._guest_mode

    def clear_guest_mode(self) -> None:
        """Clear guest mode and return to normal operation."""
        self._guest_mode = GuestModeConfig()
        logger.info("👥 Guest mode cleared")

    def get_guest_mode(self) -> GuestModeConfig:
        """Get current guest mode configuration."""
        return self._guest_mode

    def is_guest_mode_active(self) -> bool:
        """Check if any guest mode is active."""
        return self._guest_mode.mode != GuestMode.NONE

    # =========================================================================
    # Vacation Mode
    # =========================================================================

    async def enable_vacation_mode(
        self,
        end_date: datetime | None = None,
        simulate_occupancy: bool = True,
    ) -> VacationModeConfig:
        """Enable vacation mode.

        Args:
            end_date: When vacation ends (for auto-disable)
            simulate_occupancy: Whether to simulate occupancy for security

        Returns:
            Vacation mode configuration
        """
        self._vacation_mode = VacationModeConfig(
            enabled=True,
            start_date=datetime.now(),
            end_date=end_date,
            simulate_occupancy=simulate_occupancy,
        )

        # Set HVAC to setback
        month = datetime.now().month
        is_winter = month in (11, 12, 1, 2, 3)
        setback_temp = (
            self._vacation_mode.hvac_setback_temp_f
            if is_winter
            else self._vacation_mode.hvac_setpoint_summer_f
        )

        for room in ["Living Room", "Kitchen", "Primary Bedroom", "Office"]:
            try:
                await self.controller.set_room_temp(room, int(setback_temp))
            except Exception:
                pass

        # Start occupancy simulation
        if simulate_occupancy:
            self._occupancy_simulator = OccupancySimulator(self.controller, self._vacation_mode)
            await self._occupancy_simulator.start()

        # Arm security
        await self.controller.arm_security("away")

        logger.info("🏖️ Vacation mode enabled")
        return self._vacation_mode

    async def disable_vacation_mode(self) -> None:
        """Disable vacation mode."""
        self._vacation_mode.enabled = False

        # Stop occupancy simulation
        if self._occupancy_simulator:
            await self._occupancy_simulator.stop()
            self._occupancy_simulator = None

        # Restore normal HVAC
        for room in ["Living Room", "Kitchen", "Primary Bedroom", "Office"]:
            try:
                await self.controller.set_room_temp(room, 72)
            except Exception:
                pass

        logger.info("🏖️ Vacation mode disabled")

    def is_vacation_mode(self) -> bool:
        """Check if vacation mode is active."""
        return self._vacation_mode.enabled

    # =========================================================================
    # Circadian Lighting
    # =========================================================================

    def enable_circadian(self) -> None:
        """Enable circadian lighting adjustments."""
        self._circadian_enabled = True
        logger.info("☀️ Circadian lighting enabled")

    def disable_circadian(self) -> None:
        """Disable circadian lighting adjustments."""
        self._circadian_enabled = False
        logger.info("☀️ Circadian lighting disabled")

    def is_circadian_enabled(self) -> bool:
        """Check if circadian lighting is enabled."""
        return self._circadian_enabled

    def get_circadian_settings(self) -> CircadianSettings:
        """Get current circadian settings."""
        phase = get_current_circadian_phase()
        return CircadianSettings.for_phase(phase)

    def adjust_brightness_for_circadian(self, requested_level: int) -> int:
        """Adjust brightness level for circadian phase.

        Args:
            requested_level: Requested brightness (0-100)

        Returns:
            Adjusted brightness respecting circadian limits
        """
        if not self._circadian_enabled:
            return requested_level

        max_brightness = get_circadian_max_brightness()
        return min(requested_level, max_brightness)

    # =========================================================================
    # Status
    # =========================================================================

    def get_status(self) -> dict[str, Any]:
        """Get status of all advanced automation features."""
        return {
            "running": self._running,
            "guest_mode": {
                "active": self.is_guest_mode_active(),
                "mode": self._guest_mode.mode.value,
                "guest_count": self._guest_mode.guest_count,
            },
            "vacation_mode": {
                "active": self.is_vacation_mode(),
                "simulating_occupancy": self._occupancy_simulator is not None,
            },
            "circadian": {
                "enabled": self._circadian_enabled,
                "current_phase": get_current_circadian_phase().value,
                "color_temp_k": get_circadian_color_temp(),
                "max_brightness": get_circadian_max_brightness(),
            },
            "predictive_hvac": {
                "enabled": self.predictive_hvac._running,
            },
            "sleep_optimization": {
                "enabled": self.sleep_optimizer._running,
                "wake_time": f"{self.sleep_optimizer.wake_time_hour:02d}:{self.sleep_optimizer.wake_time_minute:02d}",
            },
            "state_reconciliation": {
                "enabled": self.state_reconciler._running,
                "recent_discrepancies": len(self.state_reconciler._discrepancies),
            },
        }


# =============================================================================
# FACTORY
# =============================================================================

_automation_manager: AdvancedAutomationManager | None = None


def get_advanced_automation(controller: SmartHomeController) -> AdvancedAutomationManager:
    """Get or create advanced automation manager."""
    global _automation_manager

    if _automation_manager is None:
        _automation_manager = AdvancedAutomationManager(controller)

    return _automation_manager


async def start_advanced_automation(controller: SmartHomeController) -> AdvancedAutomationManager:
    """Start advanced automation features.

    Args:
        controller: SmartHomeController instance

    Returns:
        Running AdvancedAutomationManager
    """
    manager = get_advanced_automation(controller)
    await manager.start()
    return manager


__all__ = [
    # Circadian
    "CircadianPhase",
    "CircadianSettings",
    "get_current_circadian_phase",
    "get_circadian_color_temp",
    "get_circadian_max_brightness",
    # Guest Mode
    "GuestMode",
    "GuestModeConfig",
    # Vacation Mode
    "VacationModeConfig",
    "OccupancySimulator",
    # State Reconciliation
    "StateReconciler",
    # Predictive HVAC
    "PredictiveHVAC",
    # Sleep Optimization
    "SleepOptimizer",
    # Manager
    "AdvancedAutomationManager",
    "get_advanced_automation",
    "start_advanced_automation",
]
