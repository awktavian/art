"""Device Service — Lights and Shades Control.

Handles all lighting and shade control through Control4/Lutron.

ALL light commands go through the LightCommandDebouncer to prevent flickering.

Includes celestial-aware shade optimization based on sun position
and window geometry.

CBF INTEGRATION:
    h(x) >= 0 always.
    Resident manual changes are protected from automation override
    via ResidentOverrideCBF with configurable cooldown periods.

Created: December 30, 2025
Updated: January 3, 2026 — Added celestial shade optimization
Updated: January 3, 2026 — Added ResidentOverrideCBF integration
Updated: January 7, 2026 — Added LightCommandDebouncer to prevent flickering
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami_smarthome.integrations.control4 import Control4Integration

from kagami_smarthome.light_debouncer import get_light_debouncer
from kagami_smarthome.resident_override_cbf import DeviceType, get_resident_override_cbf

logger = logging.getLogger(__name__)


@dataclass
class ShadeOptimization:
    """Result of shade optimization calculation."""

    shade_id: int
    name: str
    facing: str
    sun_hits: bool
    current_level: int | None
    optimal_level: int
    reason: str


class DeviceService:
    """Service for controlling lights and shades.

    ALL light commands go through LightCommandDebouncer to prevent flickering.

    Encapsulates all Control4/Lutron device interactions for
    cleaner separation of concerns.

    Usage:
        device_svc = DeviceService(control4_integration)
        await device_svc.set_lights(50, rooms=["Living Room"])
        await device_svc.close_shades(rooms=["Living Room"])
    """

    def __init__(
        self,
        control4: Control4Integration | None = None,
        automation_tracker: set[int] | None = None,
    ) -> None:
        """Initialize device service.

        Args:
            control4: Control4 integration instance
            automation_tracker: Set to track automation-initiated changes (for CBF)
        """
        self._control4 = control4
        self._automation_tracker = automation_tracker or set()
        self._debouncer = get_light_debouncer()

    def set_control4(self, control4: Control4Integration) -> None:
        """Set or update Control4 integration."""
        self._control4 = control4
        self._debouncer.set_control4(control4)

    @property
    def is_available(self) -> bool:
        """Check if device service is available."""
        return self._control4 is not None

    # =========================================================================
    # Light Control
    # =========================================================================

    async def set_lights(
        self,
        level: int,
        rooms: list[str] | None = None,
        respect_cbf: bool = True,
        source: str = "device_service",
    ) -> bool:
        """Set lighting level via debouncer (prevents flickering).

        ALL light commands go through the LightCommandDebouncer which:
        - Rate-limits to max 1 command per 200ms per light
        - Skips redundant commands (level unchanged)
        - Coalesces rapid changes (last write wins)

        Args:
            level: Brightness level (0-100)
            rooms: Optional list of room names to control
            respect_cbf: If True, skip lights with active resident overrides
            source: Caller identifier for debugging

        Returns:
            True if any lights were set successfully
        """
        if not self._control4:
            return False

        cbf = get_resident_override_cbf()

        if rooms:
            # Room-based control - CBF checked per room's lights
            results = []
            for room in rooms:
                room_lights = self._get_lights_for_room(room)
                for light_id in room_lights:
                    if respect_cbf and not cbf.is_automation_allowed(light_id, DeviceType.LIGHT):
                        logger.debug(f"🛑 CBF: Light {light_id} blocked (resident override)")
                        continue
                    # Mark as automation-initiated BEFORE making change
                    self._automation_tracker.add(light_id)
                    try:
                        # Use debouncer instead of direct Control4 call
                        result = await self._debouncer.set_level(
                            light_id, level, source=f"{source}:{room}"
                        )
                        results.append(result)
                        if respect_cbf and result:
                            cbf.record_automation_change(light_id, DeviceType.LIGHT)
                    finally:
                        asyncio.create_task(self._cleanup_tracker(light_id))
            return any(results) if results else False
        else:
            results = []
            for light_id in self._control4.get_lights():
                if respect_cbf and not cbf.is_automation_allowed(light_id, DeviceType.LIGHT):
                    logger.debug(f"🛑 CBF: Light {light_id} blocked (resident override)")
                    continue
                # Mark as automation-initiated BEFORE making change
                self._automation_tracker.add(light_id)
                try:
                    # Use debouncer instead of direct Control4 call
                    result = await self._debouncer.set_level(
                        light_id, level, source=f"{source}:all"
                    )
                    results.append(result)
                    if respect_cbf and result:
                        cbf.record_automation_change(light_id, DeviceType.LIGHT)
                finally:
                    asyncio.create_task(self._cleanup_tracker(light_id))
            return any(results) if results else False

    def _get_lights_for_room(self, room: str) -> list[int]:
        """Get light IDs for a specific room."""
        if not self._control4:
            return []
        lights = self._control4.get_lights()
        room_lower = room.lower()
        return [
            lid for lid, data in lights.items() if room_lower in data.get("room_name", "").lower()
        ]

    async def toggle_light(self, room: str, fixture: str | None = None) -> bool:
        """Toggle a light in a room.

        Args:
            room: Room name
            fixture: Optional specific fixture name

        Returns:
            True if toggle succeeded
        """
        if not self._control4:
            return False
        return await self._control4.toggle_room_light(room, fixture)

    async def set_light_level(
        self, light_id: int, level: int, source: str = "device_service"
    ) -> bool:
        """Set specific light level by ID via debouncer.

        Args:
            light_id: Control4 light device ID
            level: Brightness level (0-100)
            source: Caller identifier for debugging

        Returns:
            True if successful
        """
        if not self._control4:
            return False
        # Use debouncer instead of direct Control4 call
        return await self._debouncer.set_level(light_id, level, source=source)

    def get_lights(self) -> dict[int, dict[str, Any]]:
        """Get all lights.

        Returns:
            Dict of light_id -> light info
        """
        if not self._control4:
            return {}
        return self._control4.get_lights()

    def get_light_level(self, light_id: int) -> int:
        """Get current light level.

        Args:
            light_id: Control4 light device ID

        Returns:
            Current brightness level (0-100)
        """
        if not self._control4:
            return 0
        lights = self._control4.get_lights()
        return lights.get(light_id, {}).get("level", 0)

    # =========================================================================
    # Shade Control
    # =========================================================================

    async def set_shades(
        self,
        level: int,
        rooms: list[str] | None = None,
    ) -> bool:
        """Set shade position.

        Lutron/Control4 convention:
        - 0 = fully CLOSED (lowered/down)
        - 100 = fully OPEN (raised/up)

        Args:
            level: Position (0=closed, 100=open)
            rooms: Optional list of room names

        Returns:
            True if any shades were set successfully
        """
        if not self._control4:
            return False

        if rooms:
            results = [await self._control4.set_room_shades(room, level) for room in rooms]
            return any(results)
        else:
            results = []
            for shade_id in self._control4.get_shades():
                results.append(await self._control4.set_shade_level(shade_id, level))
            return any(results)

    async def open_shades(
        self,
        rooms: list[str] | None = None,
        respect_cbf: bool = True,
    ) -> bool:
        """Open (raise) shades.

        Args:
            rooms: Optional list of room names
            respect_cbf: If True, skip shades with active resident overrides

        Returns:
            True if any shades were opened
        """
        if not self._control4:
            return False

        shades = self._control4.get_shades()
        if rooms:
            room_lower = [r.lower() for r in rooms]
            shades = {
                sid: s
                for sid, s in shades.items()
                if any(r in s.get("room_name", "").lower() for r in room_lower)
            }

        # CBF CHECK: Respect resident manual overrides
        cbf = get_resident_override_cbf()
        results = []
        for sid in shades:
            if respect_cbf and not cbf.is_automation_allowed(sid, DeviceType.SHADE):
                logger.debug(f"🛑 CBF: Shade {sid} blocked (resident override)")
                continue
            results.append(await self._control4.open_shade(sid))
            if respect_cbf:
                cbf.record_automation_change(sid, DeviceType.SHADE)

        return any(results) if results else False

    async def close_shades(
        self,
        rooms: list[str] | None = None,
        respect_cbf: bool = True,
    ) -> bool:
        """Close (lower) shades.

        Args:
            rooms: Optional list of room names
            respect_cbf: If True, skip shades with active resident overrides

        Returns:
            True if any shades were closed
        """
        if not self._control4:
            return False

        shades = self._control4.get_shades()
        if rooms:
            room_lower = [r.lower() for r in rooms]
            shades = {
                sid: s
                for sid, s in shades.items()
                if any(r in s.get("room_name", "").lower() for r in room_lower)
            }

        # CBF CHECK: Respect resident manual overrides
        cbf = get_resident_override_cbf()
        results = []
        for sid in shades:
            if respect_cbf and not cbf.is_automation_allowed(sid, DeviceType.SHADE):
                logger.debug(f"🛑 CBF: Shade {sid} blocked (resident override)")
                continue
            results.append(await self._control4.close_shade(sid))
            if respect_cbf:
                cbf.record_automation_change(sid, DeviceType.SHADE)

        return any(results) if results else False

    def get_shades(self) -> dict[int, dict[str, Any]]:
        """Get all shades.

        Returns:
            Dict of shade_id -> shade info
        """
        if not self._control4:
            return {}
        return self._control4.get_shades()

    # =========================================================================
    # Celestial-Aware Shade Optimization (First Principles)
    # =========================================================================

    async def optimize_shades_celestial(self) -> list[ShadeOptimization]:
        """Optimize ALL shades based on sun position AND weather.

        FIRST PRINCIPLES:
        1. Night → All shades OPEN
        2. Cloudy/Rainy → All shades OPEN (no glare)
        3. Sun NOT hitting shade's direction → OPEN
        4. Sun hitting shade's direction → Close proportionally
           - Lower sun = more glare = more closed
           - Level = altitude * 2 (clamped 20-80%)
        5. BINARY shades (doors) → Default OPEN for walkthrough

        WEATHER INTEGRATION:
        - If cloud_coverage > 70%: Skip shade closing (no direct sun)
        - If raining: Skip shade closing entirely
        - Forecast considered for trend (partly cloudy = still close)

        Runs every 30 minutes during daylight.
        """
        if not self._control4:
            return []

        # Import celestial module
        try:
            from kagami.core.celestial import sun_position
            from kagami.core.celestial.home_geometry import (
                HOME_LATITUDE,
                HOME_LONGITUDE,
                SHADES,
                ShadeMode,
                calculate_shade_level,
                sun_hits_direction,
            )
        except ImportError as e:
            logger.error(f"Celestial module not available: {e}")
            return []

        # Get current sun position
        sun = sun_position(HOME_LATITUDE, HOME_LONGITUDE)

        # Check weather conditions
        weather_override = False
        weather_reason = ""
        try:
            from kagami_smarthome.integrations.weather import (
                WeatherCondition,
                get_shade_recommendation,
                get_weather_service,
            )

            service = get_weather_service()
            weather = service._cache  # Use cached data to avoid API call

            if weather:
                # Heavy clouds = no direct sunlight = no glare
                if weather.cloud_coverage > 70:
                    weather_override = True
                    weather_reason = f"cloudy ({weather.cloud_coverage}%)"
                    logger.info(f"☁️ Weather override: {weather_reason} — shades stay open")

                # Rain/storm = definitely no direct sun
                elif weather.condition in (
                    WeatherCondition.RAIN,
                    WeatherCondition.DRIZZLE,
                    WeatherCondition.THUNDERSTORM,
                ):
                    weather_override = True
                    weather_reason = f"{weather.condition.value}"
                    logger.info(f"🌧️ Weather override: {weather_reason} — shades stay open")

        except ImportError:
            pass  # Weather module not available, continue with celestial-only
        except Exception as e:
            logger.debug(f"Weather check failed: {e}")

        results: list[ShadeOptimization] = []

        for shade_id, shade in SHADES.items():
            # Calculate optimal level using first principles
            optimal, reason = calculate_shade_level(shade, sun.azimuth, sun.altitude, sun.is_day)

            # WEATHER OVERRIDE: If cloudy/rainy, keep shades open regardless
            if weather_override and optimal < 100:
                optimal = 100
                reason = f"OPEN (weather: {weather_reason})"

            # Check if sun is hitting this direction
            sun_hits = sun_hits_direction(sun.azimuth, shade.facing) if sun.is_day else False

            # Get current state
            current = None
            try:
                state = await self._control4.get_shade_state(shade_id)
                current = state.get("level")
            except Exception:
                pass

            # Apply if different from current
            # BINARY: exact match required
            # ANALOG: 5% tolerance
            is_binary = shade.mode == ShadeMode.BINARY
            tolerance = 0 if is_binary else 5

            if current is None or abs(current - optimal) > tolerance:
                # CBF CHECK: Respect resident manual overrides
                cbf = get_resident_override_cbf()
                if not cbf.is_automation_allowed(shade_id, DeviceType.SHADE):
                    remaining = cbf.get_cooldown_remaining(shade_id, DeviceType.SHADE)
                    logger.info(
                        f"🛑 CBF: {shade.name} blocked — manual override ({remaining:.0f}s)"
                    )
                    reason = f"CBF BLOCKED ({remaining:.0f}s cooldown)"
                else:
                    # h(x) >= 0 → automation allowed
                    # Mark as automation-initiated BEFORE making change
                    self._automation_tracker.add(shade_id)
                    try:
                        success = await self._control4.set_shade_level(shade_id, optimal)
                        if success:
                            icon = "🚪" if is_binary else "☀️"
                            logger.info(f"{icon} {shade.name}: {current}% → {optimal}% ({reason})")
                            cbf.record_automation_change(shade_id, DeviceType.SHADE)
                    finally:
                        # Clean up tracker after a short delay (allow WebSocket event to process)
                        asyncio.create_task(self._cleanup_tracker(shade_id))

            results.append(
                ShadeOptimization(
                    shade_id=shade_id,
                    name=shade.name,
                    facing=shade.facing.value,
                    sun_hits=sun_hits,
                    current_level=current,
                    optimal_level=optimal,
                    reason=reason,
                )
            )

        return results

    async def get_shade_optimization_status(self) -> dict[str, Any]:
        """Get current shade status with celestial context.

        Returns dict with:
        - sun: current sun position
        - shades: list of shade states with optimal levels
        """
        if not self._control4:
            return {"error": "Control4 not available"}

        try:
            from kagami.core.celestial import (
                HOME_LATITUDE,
                HOME_LONGITUDE,
                WINDOWS,
                sun_position,
            )
        except ImportError:
            return {"error": "Celestial module not available"}

        sun = sun_position(HOME_LATITUDE, HOME_LONGITUDE)
        glare_level = int(max(20, min(90, sun.altitude * 2)))

        shades = []
        for window_key, window in WINDOWS.items():
            if not window.shade_id:
                continue

            sun_hits = window.sun_can_enter(sun.azimuth, sun.altitude)
            optimal = glare_level if sun_hits else 100

            state = await self._control4.get_shade_state(window.shade_id)
            current = state.get("level", 0)

            shades.append(
                {
                    "id": window.shade_id,
                    "name": window.name,
                    "facing": window.facing.value,
                    "current": current,
                    "optimal": optimal,
                    "sun_hits": sun_hits,
                    "is_optimal": abs(current - optimal) <= 5,
                }
            )

        return {
            "sun": {
                "azimuth": sun.azimuth,
                "altitude": sun.altitude,
                "direction": sun.direction,
                "is_day": sun.is_day,
            },
            "glare_level": glare_level,
            "shades": shades,
        }

    # =========================================================================
    # Fireplace Control
    # =========================================================================

    async def fireplace_on(self) -> bool:
        """Turn fireplace on."""
        if not self._control4:
            return False
        return await self._control4.fireplace_on()

    async def fireplace_off(self) -> bool:
        """Turn fireplace off."""
        if not self._control4:
            return False
        return await self._control4.fireplace_off()

    async def get_fireplace_state(self) -> dict[str, Any]:
        """Get fireplace state."""
        if not self._control4:
            return {"available": False}
        return await self._control4.get_fireplace_state()

    # =========================================================================
    # MantelMount TV Control
    # =========================================================================

    async def raise_tv(self) -> bool:
        """Raise TV mount to home position."""
        if not self._control4:
            return False
        return await self._control4.mantelmount_home()

    async def lower_tv(self, preset: int = 1) -> bool:
        """Lower TV mount to preset position.

        Args:
            preset: Preset number (1-4)

        Returns:
            True if successful
        """
        if not self._control4:
            return False
        return await self._control4.mantelmount_preset(preset)

    async def stop_tv(self) -> bool:
        """Emergency stop TV mount."""
        if not self._control4:
            return False
        return await self._control4.mantelmount_stop()

    async def get_tv_mount_state(self) -> dict[str, Any]:
        """Get TV mount state."""
        if not self._control4:
            return {"available": False}
        return await self._control4.get_mantelmount_state()

    async def _cleanup_tracker(self, device_id: int) -> None:
        """Remove device from automation tracker after WebSocket event processes.

        Increased delay to 2s to handle rapid consecutive changes and ensure
        WebSocket callback sees the device in the tracker.

        Args:
            device_id: Device ID to remove from tracker
        """
        await asyncio.sleep(2.0)  # 2s - handles rapid changes and debouncer delays
        self._automation_tracker.discard(device_id)


__all__ = ["DeviceService"]
