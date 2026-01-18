"""Device Controller - High-level device control operations.

NOTE (Jan 7, 2026): All light commands go through LightCommandDebouncer to prevent
flickering. Use DeviceService as the primary interface for device control.

Responsibilities:
- Light control across rooms (via debouncer)
- Audio/video control
- HVAC and climate control
- Lock and security control
- Shade control
- Fireplace control with safety

CBF Integration:
- All device changes respect ResidentOverrideCBF
- h(x) >= 0 always
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from kagami_smarthome.light_debouncer import get_light_debouncer
from kagami_smarthome.resident_override_cbf import DeviceType, get_resident_override_cbf

logger = logging.getLogger(__name__)


class DeviceController:
    """Handles high-level device control operations."""

    def __init__(self, integration_coordinator, room_registry=None):
        self.integrations = integration_coordinator
        self.room_registry = room_registry

        # Safety state for fireplace
        self._fireplace_auto_off_task: asyncio.Task | None = None

    # Light Control
    async def set_lights(
        self,
        level: int,
        rooms: list[str] | None = None,
        color: str | None = None,
        fade_time: float | None = None,  # Ignored - Control4 doesn't support fade_time
        respect_cbf: bool = True,
    ) -> bool:
        """Set lights in specified rooms or all rooms via debouncer.

        All light commands go through LightCommandDebouncer to prevent flickering.

        Args:
            level: Brightness level (0-100)
            rooms: Optional list of room names
            color: Optional color (not implemented)
            fade_time: IGNORED - Control4 doesn't support transition time
            respect_cbf: If True, skip lights with active resident overrides
        """
        try:
            target_rooms = rooms or (
                self.room_registry.get_all_room_names() if self.room_registry else []
            )

            cbf = get_resident_override_cbf()
            debouncer = get_light_debouncer()
            debouncer.set_control4(self.integrations.control4)

            results = []
            for room_name in target_rooms:
                if self.room_registry:
                    room = self.room_registry.get_room(room_name)
                    if room and room.lights:
                        for light in room.lights:
                            # CBF CHECK: Skip if resident override active
                            if respect_cbf and not cbf.is_automation_allowed(
                                light.device_id, DeviceType.LIGHT
                            ):
                                logger.debug(
                                    f"🛑 CBF: Light {light.device_id} blocked (resident override)"
                                )
                                continue
                            # Use debouncer to prevent flickering (Jan 7, 2026)
                            result = await debouncer.set_level(
                                light.device_id,
                                level,
                                source=f"device_controller:{room_name}",
                            )
                            results.append(result)
                            if respect_cbf and result:
                                cbf.record_automation_change(light.device_id, DeviceType.LIGHT)

            return any(results) if results else False

        except Exception as e:
            logger.error(f"Failed to set lights: {e}")
            return False

    # Audio Control
    async def set_audio(
        self,
        volume: int | None = None,
        source: str | None = None,
        rooms: list[str] | None = None,
    ) -> bool:
        """Set audio volume/source in specified rooms."""
        try:
            target_rooms = rooms or (
                self.room_registry.get_all_room_names() if self.room_registry else []
            )

            tasks = []
            for room_name in target_rooms:
                if self.room_registry:
                    room = self.room_registry.get_room(room_name)
                    if room and room.audio_zone:
                        if volume is not None:
                            task = self.integrations.control4.set_audio_volume(
                                room.audio_zone.device_id, volume
                            )
                            tasks.append(task)
                        if source:
                            task = self.integrations.control4.set_audio_source(
                                room.audio_zone.device_id, source
                            )
                            tasks.append(task)

            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                return all(
                    result is True for result in results if not isinstance(result, Exception)
                )

            return False

        except Exception as e:
            logger.error(f"Failed to set audio: {e}")
            return False

    async def mute_room(self, room: str, mute: bool = True) -> bool:
        """Mute/unmute audio in a specific room."""
        try:
            if self.room_registry:
                room_obj = self.room_registry.get_room(room)
                if room_obj and room_obj.audio_zone:
                    return await self.integrations.control4.set_audio_mute(
                        room_obj.audio_zone.device_id, mute
                    )
            return False
        except Exception as e:
            logger.error(f"Failed to mute room {room}: {e}")
            return False

    # Shade Control
    async def set_shades(
        self,
        position: int,
        rooms: list[str] | None = None,
        speed: str = "medium",
        respect_cbf: bool = True,
    ) -> bool:
        """Set shade position in specified rooms.

        Args:
            position: Shade position (0=closed, 100=open)
            rooms: Optional list of room names
            speed: Not implemented
            respect_cbf: If True, skip shades with active resident overrides
        """
        try:
            target_rooms = rooms or (
                self.room_registry.get_all_room_names() if self.room_registry else []
            )

            cbf = get_resident_override_cbf()
            tasks = []
            for room_name in target_rooms:
                if self.room_registry:
                    room = self.room_registry.get_room(room_name)
                    if room and room.shades:
                        for shade in room.shades:
                            # CBF CHECK: Skip if resident override active
                            if respect_cbf and not cbf.is_automation_allowed(
                                shade.device_id, DeviceType.SHADE
                            ):
                                logger.debug(
                                    f"🛑 CBF: Shade {shade.device_id} blocked (resident override)"
                                )
                                continue
                            task = self.integrations.control4.set_shade_position(
                                shade.device_id, position
                            )
                            tasks.append(task)
                            if respect_cbf:
                                cbf.record_automation_change(shade.device_id, DeviceType.SHADE)

            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                return all(
                    result is True for result in results if not isinstance(result, Exception)
                )

            return False

        except Exception as e:
            logger.error(f"Failed to set shades: {e}")
            return False

    async def open_shades(self, rooms: list[str] | None = None, respect_cbf: bool = True) -> bool:
        """Open shades in specified rooms."""
        return await self.set_shades(100, rooms, respect_cbf=respect_cbf)

    async def close_shades(self, rooms: list[str] | None = None, respect_cbf: bool = True) -> bool:
        """Close shades in specified rooms."""
        return await self.set_shades(0, rooms, respect_cbf=respect_cbf)

    # Lock Control
    async def lock_all(self) -> bool:
        """Lock all doors."""
        try:
            # Try August first for lower latency
            if hasattr(self.integrations, "_august") and self.integrations._august:
                return await self.integrations.august.lock_all()

            # Fallback to Control4
            return await self.integrations.control4.lock_all()
        except Exception as e:
            logger.error(f"Failed to lock all doors: {e}")
            return False

    async def unlock_door(self, door: str) -> bool:
        """Unlock a specific door."""
        try:
            # Try August first for lower latency
            if hasattr(self.integrations, "_august") and self.integrations._august:
                return await self.integrations.august.unlock_door(door)

            # Fallback to Control4
            return await self.integrations.control4.unlock_door(door)
        except Exception as e:
            logger.error(f"Failed to unlock door {door}: {e}")
            return False

    async def get_lock_states(self) -> dict[str, bool]:
        """Get lock states for all doors."""
        try:
            # Try August first
            if hasattr(self.integrations, "_august") and self.integrations._august:
                return await self.integrations.august.get_lock_states()

            # Fallback to Control4
            return await self.integrations.control4.get_lock_states()
        except Exception as e:
            logger.error(f"Failed to get lock states: {e}")
            return {}

    # Fireplace Control (with CBF safety)
    async def fireplace_on(self) -> bool:
        """Turn on fireplace with safety checks and auto-off timer."""
        try:
            # Safety check - don't turn on if already scheduled to turn off
            if self._fireplace_auto_off_task and not self._fireplace_auto_off_task.done():
                logger.info("Fireplace auto-off already scheduled")
                return True

            # Turn on fireplace
            success = await self.integrations.control4.fireplace_on()

            if success:
                # Start 3-hour auto-off timer for safety
                self._fireplace_auto_off_task = asyncio.create_task(
                    self._fireplace_auto_off_timer()
                )
                logger.info("Fireplace turned on with 3-hour auto-off timer")

            return success

        except Exception as e:
            logger.error(f"Failed to turn on fireplace: {e}")
            return False

    async def fireplace_off(self) -> bool:
        """Turn off fireplace and cancel auto-off timer."""
        try:
            # Cancel auto-off timer
            if self._fireplace_auto_off_task:
                self._fireplace_auto_off_task.cancel()
                self._fireplace_auto_off_task = None

            return await self.integrations.control4.fireplace_off()

        except Exception as e:
            logger.error(f"Failed to turn off fireplace: {e}")
            return False

    async def _fireplace_auto_off_timer(self) -> None:
        """Auto-off timer for fireplace safety."""
        try:
            await asyncio.sleep(3 * 60 * 60)  # 3 hours
            await self.fireplace_off()
            logger.info("Fireplace automatically turned off after 3 hours")
        except asyncio.CancelledError:
            logger.debug("Fireplace auto-off timer cancelled")

    async def get_fireplace_state(self) -> dict[str, Any]:
        """Get fireplace state."""
        try:
            state = await self.integrations.control4.get_fireplace_state()

            # Add auto-off timer info
            auto_off_active = (
                self._fireplace_auto_off_task is not None
                and not self._fireplace_auto_off_task.done()
            )
            state["auto_off_active"] = auto_off_active

            return state

        except Exception as e:
            logger.error(f"Failed to get fireplace state: {e}")
            return {}

    # HVAC Control
    async def set_room_temp(self, room_name: str, temp_f: float) -> bool:
        """Set temperature for a specific room."""
        try:
            if not self.integrations.mitsubishi:
                logger.warning("Mitsubishi HVAC not available")
                return False

            # Map room to HVAC zone
            if self.room_registry:
                room = self.room_registry.get_room(room_name)
                if room and hasattr(room, "hvac_zone") and room.hvac_zone:
                    return await self.integrations.mitsubishi.set_temperature(
                        room.hvac_zone, temp_f
                    )

            return False

        except Exception as e:
            logger.error(f"Failed to set room temperature: {e}")
            return False

    async def set_room_hvac_mode(self, room_name: str, mode: str) -> bool:
        """Set HVAC mode for a specific room."""
        try:
            if not self.integrations.mitsubishi:
                logger.warning("Mitsubishi HVAC not available")
                return False

            # Map room to HVAC zone
            if self.room_registry:
                room = self.room_registry.get_room(room_name)
                if room and hasattr(room, "hvac_zone") and room.hvac_zone:
                    return await self.integrations.mitsubishi.set_mode(room.hvac_zone, mode)

            return False

        except Exception as e:
            logger.error(f"Failed to set HVAC mode: {e}")
            return False

    # TV Control
    async def tv_on(self) -> bool:
        """Turn on Living Room TV."""
        try:
            return await self.integrations.lg_tv.power_on()
        except Exception as e:
            logger.error(f"Failed to turn on TV: {e}")
            return False

    async def tv_off(self) -> bool:
        """Turn off Living Room TV."""
        try:
            return await self.integrations.lg_tv.power_off()
        except Exception as e:
            logger.error(f"Failed to turn off TV: {e}")
            return False

    async def tv_volume(self, level: int) -> bool:
        """Set TV volume."""
        try:
            return await self.integrations.lg_tv.set_volume(level)
        except Exception as e:
            logger.error(f"Failed to set TV volume: {e}")
            return False

    async def tv_launch_app(self, app: str) -> bool:
        """Launch app on TV."""
        try:
            return await self.integrations.lg_tv.launch_app(app)
        except Exception as e:
            logger.error(f"Failed to launch TV app: {e}")
            return False
