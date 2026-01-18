"""Room Orchestrator — Coordinating All Room Systems.

NOTE (Jan 7, 2026): This orchestrator is currently NOT INSTANTIATED in production.
All light commands should go through DeviceService which uses LightCommandDebouncer.
If you need to use this orchestrator, ensure it's wired to use the debouncer.

The orchestrator translates high-level intents (scenes, activities)
into coordinated actions across all room systems:
- Lights (Control4/Lutron) — via LightCommandDebouncer to prevent flickering
- Shades (Control4/Lutron)
- Audio (Triad AMS via Control4)
- HVAC (Mitsubishi)
- Special devices (Denon AVR, LG TV, fireplace, MantelMount)

The orchestrator ensures:
1. Actions happen in the right order (blackout shades before movie)
2. Transitions are smooth (fades, not jumps)
3. Room state is tracked and queryable
4. Manual overrides are respected via CBF

Philosophy:
The home should feel like it's reading your mind.
Scenes encode intent, the orchestrator makes it real.
h(x) >= 0 always.

Created: December 29, 2025
CBF Integration: January 3, 2026
Updated: January 7, 2026 — Added LightCommandDebouncer for flicker prevention
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from kagami_smarthome.light_debouncer import get_light_debouncer
from kagami_smarthome.resident_override_cbf import DeviceType, get_resident_override_cbf
from kagami_smarthome.room import (
    ActivityContext,
    Room,
    RoomRegistry,
    RoomType,
)
from kagami_smarthome.scenes import (
    SCENES,
    Scene,
    TimeOfDay,
)

if TYPE_CHECKING:
    from kagami_smarthome.controller import SmartHomeController

logger = logging.getLogger(__name__)


@dataclass
class OrchestratorConfig:
    """Configuration for the room orchestrator."""

    # Transition timings
    default_fade_seconds: float = 3.0
    movie_fade_seconds: float = 5.0
    sleep_fade_seconds: float = 30.0

    # Delays between actions (seconds)
    shade_to_light_delay: float = 0.5
    light_to_audio_delay: float = 0.2

    # Override behavior
    manual_override_timeout: float = 3600.0  # 1 hour

    # Home theater settings
    home_theater_room: str = "Living Room"
    avr_default_volume: int = 40
    tv_app_for_streaming: str = "Netflix"

    # HVAC comfort ranges
    min_temp_f: float = 62.0
    max_temp_f: float = 78.0


@dataclass
class SceneExecution:
    """Represents a scene execution plan."""

    room_id: int
    scene_name: str
    scene: Scene
    priority: int = 5  # 1=highest, 10=lowest
    estimated_duration_ms: float = 1000.0
    dependencies: list[int] = field(default_factory=list)
    pre_computed: bool = False


@dataclass
class SceneCache:
    """Cached scene execution data."""

    execution_plan: list[SceneExecution]
    precomputed_states: dict[str, Any]
    last_updated: float
    usage_count: int = 0


class RoomOrchestrator:
    """Coordinates all systems within a room.

    The orchestrator:
    - Applies scenes to rooms
    - Handles activity transitions
    - Manages special modes (movie night, sleep)
    - Tracks manual overrides
    - Provides smooth transitions

    Usage:
        orchestrator = RoomOrchestrator(controller, rooms)

        # Apply a scene to a room
        await orchestrator.set_room_scene(living_room, "relaxing")

        # Handle arrival
        await orchestrator.enter_room(kitchen, ActivityContext.COOKING)

        # House-wide scenes
        await orchestrator.goodnight()
    """

    def __init__(
        self,
        controller: SmartHomeController,
        rooms: RoomRegistry,
        config: OrchestratorConfig | None = None,
        performance_monitor: Any = None,
    ):
        self.controller = controller
        self.rooms = rooms
        self.config = config or OrchestratorConfig()

        # Performance monitoring
        self._performance_monitor = performance_monitor

        # Track overrides (room_id -> expiry timestamp)
        self._overrides: dict[int, float] = {}

        # Track current scenes (room_id -> scene_name)
        self._current_scenes: dict[int, str] = {}

        # Home theater state
        self._movie_mode_active = False

        # Lock for coordinated operations
        self._lock = asyncio.Lock()

        # Performance optimization features
        self._scene_cache: dict[str, SceneCache] = {}
        self._execution_history: dict[str, list[float]] = defaultdict(list)
        self._active_executions: dict[int, asyncio.Task] = {}

        # Parallel execution control
        self._max_concurrent_rooms = 8
        self._room_semaphore = asyncio.Semaphore(self._max_concurrent_rooms)

        # Scene prediction
        self._scene_predictions: dict[str, list[tuple[str, float]]] = {}
        self._prediction_enabled = True

        # Performance optimization
        self._adaptive_timing_enabled = True
        self._timing_adjustments: dict[str, float] = {}

        # Conflict resolution
        self._priority_overrides: dict[int, int] = {}  # room_id -> priority level

    # =========================================================================
    # Scene Application
    # =========================================================================

    async def set_room_scene(
        self,
        room: Room,
        scene_name: str,
        force: bool = False,
        priority: int = 5,
    ) -> bool:
        """Apply a scene to a room with performance optimization.

        Args:
            room: Room to apply scene to
            scene_name: Name of scene to apply
            force: Override manual overrides
            priority: Execution priority (1=highest, 10=lowest)

        Returns:
            True if scene was applied
        """
        start_time = time.monotonic()
        scene = SCENES.get(scene_name)
        if not scene:
            logger.warning(f"Unknown scene: {scene_name}")
            return False

        # Check for manual override
        if not force and self._is_overridden(room):
            logger.debug(f"Room {room.name} has override, skipping scene")
            return False

        try:
            # Check cache for optimized execution plan
            cache_key = f"{room.id}:{scene_name}"
            cached_plan = self._get_cached_execution_plan(cache_key)

            if cached_plan and not force:
                success = await self._execute_cached_scene(room, cached_plan)
            else:
                success = await self._execute_optimized_scene(room, scene_name, priority)

            execution_time = (time.monotonic() - start_time) * 1000

            # Record performance
            self._record_scene_execution(scene_name, execution_time, success)

            # Update execution history for adaptive timing
            self._update_execution_history(cache_key, execution_time)

            return success

        except Exception as e:
            logger.error(f"Optimized scene execution failed for {room.name}: {e}")
            return False

    async def _apply_lights(self, room: Room, scene: Scene) -> None:
        """Apply lighting preset to room with weather adaptation."""
        if not room.lights:
            return

        # Get time-adjusted level
        level = scene.lighting.get_level()

        # Apply weather adaptation
        weather_adaptation = await self._get_weather_adaptation()
        brightness_modifier = weather_adaptation.get("brightness_modifier", 0)
        level = max(0, min(100, level + brightness_modifier))

        if brightness_modifier != 0:
            logger.debug(
                f"Weather adaptation: {brightness_modifier:+d}% brightness for {room.name}"
            )

        # Apply to all lights in room (with CBF protection + debouncer)
        cbf = get_resident_override_cbf()
        debouncer = get_light_debouncer()
        debouncer.set_control4(self.controller.control4)

        for light in room.lights:
            # CBF CHECK: Skip if resident override active
            if not cbf.is_automation_allowed(light.id, DeviceType.LIGHT):
                logger.debug(f"🛑 CBF: Light {light.id} blocked (resident override)")
                continue

            light_level = level

            # Check for named overrides
            for pattern, override_level in scene.lighting.overrides.items():
                if pattern.lower() in light.name.lower():
                    light_level = override_level
                    break

            # Use debouncer to prevent flickering (Jan 7, 2026)
            await debouncer.set_level(
                light.id,
                light_level,
                source=f"orchestrator:{room.name}",
            )
            cbf.record_automation_change(light.id, DeviceType.LIGHT)

    async def _get_weather_adaptation(self) -> dict[str, Any]:
        """Get weather-based scene adaptations.

        Returns modifiers to apply to scenes based on current weather:
        - brightness_modifier: Added to base brightness (-20 to +20)
        - color_temp_modifier: Added to base color temp in Kelvin
        - shade_modifier: Added to base shade position
        """
        try:
            from kagami_smarthome import get_current_weather

            weather = await get_current_weather()
            if weather:
                return weather.get_scene_adaptation()
        except Exception as e:
            logger.debug(f"Weather adaptation not available: {e}")

        return {
            "brightness_modifier": 0,
            "color_temp_modifier": 0,
            "shade_modifier": 0,
            "reason": [],
        }

    async def _apply_shades(self, room: Room, scene: Scene) -> None:
        """Apply shade preset to room (with CBF protection)."""
        if not room.shades:
            return

        cbf = get_resident_override_cbf()
        for shade in room.shades:
            # CBF CHECK: Skip if resident override active
            if not cbf.is_automation_allowed(shade.id, DeviceType.SHADE):
                logger.debug(f"🛑 CBF: Shade {shade.id} blocked (resident override)")
                continue

            position = scene.shades.position

            # Check orientation overrides
            orientation = shade.orientation.lower()
            if orientation == "south" and scene.shades.south_override is not None:
                position = scene.shades.south_override
            elif orientation == "east" and scene.shades.east_override is not None:
                position = scene.shades.east_override
            elif orientation == "west" and scene.shades.west_override is not None:
                position = scene.shades.west_override

            await self.controller.control4.set_shade_level(shade.id, position)
            cbf.record_automation_change(shade.id, DeviceType.SHADE)

    async def _apply_audio(self, room: Room, scene: Scene) -> None:
        """Apply audio preset to room."""
        if not room.audio_zone:
            return

        if scene.audio.muted:
            await self.controller.control4.mute_room(room.id)
        else:
            await self.controller.control4.unmute_room(room.id)
            await self.controller.control4.set_room_volume(
                room.id,
                scene.audio.volume,
            )

    async def _apply_hvac(self, room: Room, scene: Scene) -> None:
        """Apply HVAC preset to room."""
        if not room.hvac_zone_id:
            return

        if not self.controller.mitsubishi:
            return

        # Get season-adjusted temp
        temp = scene.hvac.get_temp()

        # Clamp to safe range
        temp = max(self.config.min_temp_f, min(self.config.max_temp_f, temp))

        await self.controller.mitsubishi.set_zone_temp(room.hvac_zone_id, temp)

    async def _apply_special(self, room: Room, scene: Scene) -> None:
        """Apply special device actions."""
        # Fireplace
        if scene.fireplace_on is not None and room.has_fireplace:
            if scene.fireplace_on:
                await self.controller.control4.fireplace_on()
            else:
                await self.controller.control4.fireplace_off()

        # TV
        if scene.tv_on is not None and room.has_tv:
            if room.is_home_theater:
                # Use LG TV
                if scene.tv_on:
                    await self.controller.lg_tv.power_on()
                else:
                    await self.controller.lg_tv.power_off()
            elif room.name.lower() == "family room":
                # Use Samsung TV
                if self.controller.samsung_tv:
                    if scene.tv_on:
                        await self.controller.samsung_tv.power_on()
                    else:
                        await self.controller.samsung_tv.power_off()

    # =========================================================================
    # Activity Handling
    # =========================================================================

    async def enter_room(
        self,
        room: Room,
        activity: ActivityContext = ActivityContext.UNKNOWN,
    ) -> None:
        """Handle entering a room with an activity.

        Maps activity to appropriate scene and applies it.
        """
        # Map activity to scene
        scene_name = self._activity_to_scene(activity, room.room_type)

        # Mark room occupied
        room.mark_occupied(activity)

        # Apply scene
        await self.set_room_scene(room, scene_name)

    async def leave_room(self, room: Room) -> None:
        """Handle leaving a room.

        Sets room to 'away' state after brief delay.
        """
        room.mark_vacant()

        # Apply away scene (or turn off if no other rooms on floor occupied)
        floor_rooms = self.rooms.get_by_floor(room.floor)
        floor_occupied = any(r.state.occupied for r in floor_rooms if r.id != room.id)

        if floor_occupied:
            # Just turn off lights, keep HVAC (with CBF protection)
            cbf = get_resident_override_cbf()
            debouncer = get_light_debouncer()
            debouncer.set_control4(self.controller.control4)
            for light in room.lights:
                if not cbf.is_automation_allowed(light.id, DeviceType.LIGHT):
                    logger.debug(f"🛑 CBF: Light {light.id} blocked (resident override)")
                    continue
                # Use debouncer to prevent flickering
                await debouncer.set_level(light.id, 0, source=f"leave_room:{room.name}")
                cbf.record_automation_change(light.id, DeviceType.LIGHT)
        else:
            # Full away scene
            await self.set_room_scene(room, "away", force=True)

    async def transition_activity(
        self,
        room: Room,
        new_activity: ActivityContext,
    ) -> None:
        """Handle activity change within a room."""
        old_activity = room.state.activity

        if old_activity == new_activity:
            return

        # Update room state
        room.mark_occupied(new_activity)

        # Map to scene
        scene_name = self._activity_to_scene(new_activity, room.room_type)

        logger.info(f"Activity transition: {room.name} {old_activity.value} → {new_activity.value}")

        await self.set_room_scene(room, scene_name)

    def _activity_to_scene(self, activity: ActivityContext, room_type: RoomType) -> str:
        """Map activity context to scene name."""
        mapping = {
            ActivityContext.WAKING: "morning",
            ActivityContext.WORKING: "working",
            ActivityContext.COOKING: "cooking",
            ActivityContext.DINING: "dining",
            ActivityContext.RELAXING: "relaxing",
            ActivityContext.WATCHING: "watching",
            ActivityContext.SLEEPING: "sleeping",
            ActivityContext.AWAY: "away",
            ActivityContext.ENTERTAINING: "entertaining",
        }

        scene_name = mapping.get(activity, "relaxing")

        # Room type overrides
        if room_type == RoomType.KITCHEN and activity == ActivityContext.RELAXING:
            scene_name = "dining"  # Kitchen relaxing = dining
        elif room_type == RoomType.BEDROOM and activity == ActivityContext.RELAXING:
            scene_name = "sleeping"  # Bedroom relaxing = pre-sleep

        return scene_name

    # =========================================================================
    # House-Wide Scenes
    # =========================================================================

    async def goodnight(self) -> None:
        """Execute house-wide goodnight routine.

        - All lights off
        - All shades closed
        - Audio off
        - HVAC to sleep temps
        - TVs off
        - Fireplace off
        """
        logger.info("🌙 Good Night — shutting down house")

        # Apply goodnight scene to all rooms in parallel
        all_rooms = self.rooms.get_all()
        await asyncio.gather(
            *[self.set_room_scene(room, "goodnight", force=True) for room in all_rooms],
            return_exceptions=True,
        )
        for room in all_rooms:
            room.mark_vacant()

        # Ensure home theater is off
        if self._movie_mode_active:
            await self.exit_movie_mode()

    async def welcome_home(self) -> None:
        """Execute house-wide welcome home routine.

        Applied when Tim arrives home.
        Guest rooms (Bed 3, Bath 3, Bed 4, Bath 4) stay dark unless occupied.
        """
        logger.info("🏠 Welcome Home")

        # Light up entry and common areas in parallel
        # EXCLUDE guest rooms — they stay dark unless someone is using them
        target_rooms = [
            room
            for room in self.rooms.get_all()
            if room.room_type in (RoomType.ENTRY, RoomType.LIVING, RoomType.KITCHEN)
            and not room.is_guest_room
        ]
        if target_rooms:
            await asyncio.gather(
                *[self.set_room_scene(room, "welcome_home") for room in target_rooms],
                return_exceptions=True,
            )

    async def set_away_mode(self) -> None:
        """Set house to away mode.

        Applied when nobody is home.
        """
        logger.info("🚪 Away Mode — nobody home")

        # Apply away scene to all rooms in parallel
        all_rooms = self.rooms.get_all()
        await asyncio.gather(
            *[self.set_room_scene(room, "away", force=True) for room in all_rooms],
            return_exceptions=True,
        )
        for room in all_rooms:
            room.mark_vacant()

        # Ensure everything is off
        if self._movie_mode_active:
            await self.exit_movie_mode()

    # =========================================================================
    # Home Theater Mode
    # =========================================================================

    async def enter_movie_mode(self) -> None:
        """Enter home theater movie mode.

        Coordinates:
        - Living room lights to bias only
        - Shades to blackout
        - MantelMount lowered
        - Denon AVR on with movie mode
        - LG TV on
        - HVAC comfort
        - Mute other rooms
        """
        if self._movie_mode_active:
            logger.debug("Already in movie mode")
            return

        logger.info("🎬 Entering Movie Mode")

        home_theater = self.rooms.get_home_theater()
        if not home_theater:
            home_theater = self.rooms.get_by_name(self.config.home_theater_room)

        if not home_theater:
            logger.warning("No home theater room found")
            return

        self._movie_mode_active = True
        cbf = get_resident_override_cbf()

        # 1. Close shades first (takes time, with CBF protection)
        for shade in home_theater.shades:
            if not cbf.is_automation_allowed(shade.id, DeviceType.SHADE):
                logger.debug(f"🛑 CBF: Shade {shade.id} blocked (resident override)")
                continue
            await self.controller.control4.set_shade_level(shade.id, 100)
            cbf.record_automation_change(shade.id, DeviceType.SHADE)

        # 2. Lower MantelMount
        await self.controller.control4.mantelmount_down()

        # 3. Wait for shades
        await asyncio.sleep(5)

        # 4. Dim lights to bias only (with CBF protection)
        debouncer = get_light_debouncer()
        debouncer.set_control4(self.controller.control4)
        for light in home_theater.lights:
            if not cbf.is_automation_allowed(light.id, DeviceType.LIGHT):
                logger.debug(f"🛑 CBF: Light {light.id} blocked (resident override)")
                continue
            level = 5 if "bias" in light.name.lower() else 0
            # Use debouncer to prevent flickering
            await debouncer.set_level(light.id, level, source="movie_mode")
            cbf.record_automation_change(light.id, DeviceType.LIGHT)

        # 5. Power on Denon AVR and LG TV in parallel
        await asyncio.gather(
            self.controller.denon.power_on(),
            self.controller.lg_tv.power_on(),
        )
        await asyncio.sleep(2)  # Wait for power up

        # 6. Configure Denon and set HVAC in parallel
        denon_config = asyncio.gather(
            self.controller.denon.select_input("BD"),  # Blu-ray/streaming
            self.controller.denon.set_surround_mode("MOVIE"),
            self.controller.denon.set_volume(self.config.avr_default_volume),
        )

        hvac_task = None
        if self.controller.mitsubishi and home_theater.hvac_zone_id:
            hvac_task = self.controller.mitsubishi.set_zone_temp(
                home_theater.hvac_zone_id,
                70.0,  # Movie comfort temp
            )

        # 7. Mute other audio zones in parallel
        other_rooms = [
            room for room in self.rooms.get_all() if room.id != home_theater.id and room.audio_zone
        ]
        mute_tasks = [self.controller.control4.mute_room(room.id) for room in other_rooms]

        # Wait for all parallel tasks
        await denon_config
        if hvac_task:
            await hvac_task
        if mute_tasks:
            await asyncio.gather(*mute_tasks, return_exceptions=True)

        # 9. Mark state
        home_theater.mark_occupied(ActivityContext.WATCHING)
        self._current_scenes[home_theater.id] = "movie"

        logger.info("✅ Movie Mode active")

    async def exit_movie_mode(self) -> None:
        """Exit home theater movie mode."""
        if not self._movie_mode_active:
            return

        logger.info("🎬 Exiting Movie Mode")

        home_theater = self.rooms.get_home_theater()
        if not home_theater:
            home_theater = self.rooms.get_by_name(self.config.home_theater_room)

        if not home_theater:
            return

        self._movie_mode_active = False

        # 1. Turn off AVR
        await self.controller.denon.power_off()

        # 2. Turn off TV
        await self.controller.lg_tv.power_off()

        # 3. Raise MantelMount
        await self.controller.control4.mantelmount_up()

        # 4. Open shades (if daytime, with CBF protection)
        if TimeOfDay.current() in (TimeOfDay.MORNING, TimeOfDay.AFTERNOON):
            cbf = get_resident_override_cbf()
            for shade in home_theater.shades:
                if not cbf.is_automation_allowed(shade.id, DeviceType.SHADE):
                    logger.debug(f"🛑 CBF: Shade {shade.id} blocked (resident override)")
                    continue
                await self.controller.control4.set_shade_level(shade.id, 0)
                cbf.record_automation_change(shade.id, DeviceType.SHADE)

        # 5. Apply relaxing scene
        await self.set_room_scene(home_theater, "relaxing", force=True)

        logger.info("✅ Movie Mode deactivated")

    @property
    def is_movie_mode(self) -> bool:
        """Check if movie mode is active."""
        return self._movie_mode_active

    # =========================================================================
    # Override Handling
    # =========================================================================

    def set_override(self, room: Room, duration: float | None = None) -> None:
        """Set manual override for a room.

        Prevents automatic scene changes for the duration.
        """
        timeout = duration or self.config.manual_override_timeout
        self._overrides[room.id] = datetime.now().timestamp() + timeout
        logger.debug(f"Override set for {room.name} ({timeout}s)")

    def clear_override(self, room: Room) -> None:
        """Clear manual override for a room."""
        self._overrides.pop(room.id, None)

    def _is_overridden(self, room: Room) -> bool:
        """Check if room has active override."""
        expiry = self._overrides.get(room.id)
        if expiry is None:
            return False

        if datetime.now().timestamp() > expiry:
            # Override expired
            del self._overrides[room.id]
            return False

        return True

    # =========================================================================
    # State Queries
    # =========================================================================

    def get_current_scene(self, room: Room) -> str | None:
        """Get current scene for a room."""
        return self._current_scenes.get(room.id)

    def get_all_states(self) -> dict[str, dict[str, Any]]:
        """Get state summary for all rooms."""
        states = {}
        for room in self.rooms.get_all():
            states[room.name] = {
                "occupied": room.state.occupied,
                "activity": room.state.activity.value,
                "scene": self._current_scenes.get(room.id),
                "overridden": self._is_overridden(room),
            }
        return states

    # =========================================================================
    # Performance Optimization Methods
    # =========================================================================

    async def _execute_optimized_scene(self, room: Room, scene_name: str, priority: int) -> bool:
        """Execute scene with optimization."""
        scene = SCENES.get(scene_name)
        if not scene:
            return False

        # Create execution plan
        execution = SceneExecution(
            room_id=room.id,
            scene_name=scene_name,
            scene=scene,
            priority=priority,
            estimated_duration_ms=self._estimate_execution_time(room, scene),
        )

        # Check for conflicts with active executions
        if await self._resolve_execution_conflicts(execution):
            return await self._execute_scene_plan(execution)

        return False

    async def _execute_cached_scene(self, room: Room, cached_plan: SceneCache) -> bool:
        """Execute pre-computed scene from cache."""
        cached_plan.usage_count += 1

        # Execute in parallel if multiple rooms
        if len(cached_plan.execution_plan) > 1:
            return await self._execute_parallel_scenes(cached_plan.execution_plan)
        else:
            return await self._execute_scene_plan(cached_plan.execution_plan[0])

    async def _execute_scene_plan(self, execution: SceneExecution) -> bool:
        """Execute a single scene execution plan."""
        async with self._room_semaphore:
            room = self.rooms.get_by_id(execution.room_id)
            if not room:
                return False

            try:
                # Use adaptive timing if available
                timing_key = f"{room.id}:{execution.scene_name}"
                adjusted_delays = self._get_adaptive_timing(timing_key)

                # Execute scene components in optimized order
                success = await self._execute_scene_components(
                    room, execution.scene, adjusted_delays
                )

                if success:
                    self._current_scenes[room.id] = execution.scene_name
                    logger.info(f"🎬 {room.name} → {execution.scene.display_name}")

                return success

            except Exception as e:
                logger.error(f"Scene execution error for {room.name}: {e}")
                return False

    async def _execute_scene_components(
        self, room: Room, scene: Scene, timing_adjustments: dict[str, float]
    ) -> bool:
        """Execute scene components with optimized timing."""

        # Create parallel tasks for independent components
        tasks = []

        # HVAC (can run in parallel with others)
        if room.hvac_zone_id:
            tasks.append(
                asyncio.create_task(self._apply_hvac_optimized(room, scene), name=f"hvac_{room.id}")
            )

        # Special devices (can run in parallel)
        tasks.append(
            asyncio.create_task(
                self._apply_special_optimized(room, scene), name=f"special_{room.id}"
            )
        )

        # Sequential components (shades -> lights -> audio)
        sequential_success = await self._execute_sequential_components(
            room, scene, timing_adjustments
        )

        # Wait for parallel tasks
        if tasks:
            parallel_results = await asyncio.gather(*tasks, return_exceptions=True)
            parallel_success = all(
                result is True or not isinstance(result, Exception) for result in parallel_results
            )
        else:
            parallel_success = True

        return sequential_success and parallel_success

    async def _execute_sequential_components(
        self, room: Room, scene: Scene, timing_adjustments: dict[str, float]
    ) -> bool:
        """Execute components that must run sequentially."""
        try:
            # Shades first (affects lighting)
            if room.shades:
                await self._apply_shades(room, scene)

                # Adaptive delay
                shade_delay = timing_adjustments.get(
                    "shade_to_light", self.config.shade_to_light_delay
                )
                if shade_delay > 0:
                    await asyncio.sleep(shade_delay)

            # Lights next
            if room.lights:
                await self._apply_lights(room, scene)

                # Adaptive delay
                light_delay = timing_adjustments.get(
                    "light_to_audio", self.config.light_to_audio_delay
                )
                if light_delay > 0:
                    await asyncio.sleep(light_delay)

            # Audio last
            if room.audio_zone:
                await self._apply_audio(room, scene)

            return True

        except Exception as e:
            logger.error(f"Sequential component execution error: {e}")
            return False

    async def _apply_hvac_optimized(self, room: Room, scene: Scene) -> bool:
        """Optimized HVAC application."""
        if not room.hvac_zone_id or not self.controller.mitsubishi:
            return True

        try:
            temp = scene.hvac.get_temp()
            temp = max(self.config.min_temp_f, min(self.config.max_temp_f, temp))

            await self.controller.mitsubishi.set_zone_temp(room.hvac_zone_id, temp)
            return True

        except Exception as e:
            logger.debug(f"HVAC optimization error: {e}")
            return False

    async def _apply_special_optimized(self, room: Room, scene: Scene) -> bool:
        """Optimized special device control."""
        tasks = []

        # Fireplace
        if scene.fireplace_on is not None and room.has_fireplace:
            if scene.fireplace_on:
                task = self.controller.control4.fireplace_on()
            else:
                task = self.controller.control4.fireplace_off()
            tasks.append(asyncio.create_task(task))

        # TV control
        if scene.tv_on is not None and room.has_tv:
            if room.is_home_theater:
                if scene.tv_on:
                    task = self.controller.lg_tv.power_on()
                else:
                    task = self.controller.lg_tv.power_off()
                tasks.append(asyncio.create_task(task))
            elif room.name.lower() == "family room" and self.controller.samsung_tv:
                if scene.tv_on:
                    task = self.controller.samsung_tv.power_on()
                else:
                    task = self.controller.samsung_tv.power_off()
                tasks.append(asyncio.create_task(task))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            return all(not isinstance(result, Exception) for result in results)

        return True

    async def set_multiple_room_scenes(
        self,
        room_scenes: dict[str, str],  # room_name -> scene_name
        force: bool = False,
    ) -> dict[str, bool]:
        """Set scenes for multiple rooms in parallel."""
        start_time = time.monotonic()

        # Convert to execution plans
        executions = []
        for room_name, scene_name in room_scenes.items():
            room = self.rooms.get_by_name(room_name)
            if room:
                scene = SCENES.get(scene_name)
                if scene:
                    execution = SceneExecution(
                        room_id=room.id,
                        scene_name=scene_name,
                        scene=scene,
                        estimated_duration_ms=self._estimate_execution_time(room, scene),
                    )
                    executions.append(execution)

        if not executions:
            return {}

        # Resolve conflicts and dependencies
        optimized_executions = await self._optimize_execution_order(executions)

        # Execute in parallel
        results = await self._execute_parallel_scenes(optimized_executions)

        total_time = (time.monotonic() - start_time) * 1000

        # Record multi-room performance
        if self._performance_monitor:
            from kagami_smarthome.performance_monitor import MetricType

            self._performance_monitor.record_metric(
                MetricType.SCENE_ACTIVATION_TIME,
                total_time,
                "multi_room",
                {
                    "room_count": len(room_scenes),
                    "success_count": sum(1 for success in results.values() if success),
                },
            )

        logger.info(
            f"🎬 Multi-room scene execution completed in {total_time:.1f}ms ({len(results)} rooms)"
        )

        return results

    async def _execute_parallel_scenes(self, executions: list[SceneExecution]) -> dict[str, bool]:
        """Execute multiple scenes in parallel."""
        # Group by priority and dependencies
        execution_groups = self._group_executions_by_priority(executions)

        results = {}

        # Execute in priority order, with parallelism within each priority
        for priority, group in sorted(execution_groups.items()):
            group_tasks = []

            for execution in group:
                room = self.rooms.get_by_id(execution.room_id)
                if room:
                    task = asyncio.create_task(
                        self._execute_scene_plan(execution),
                        name=f"scene_{room.name}_{execution.scene_name}",
                    )
                    group_tasks.append((room.name, task))

            # Wait for this priority group to complete
            if group_tasks:
                group_results = await asyncio.gather(
                    *[task for _, task in group_tasks], return_exceptions=True
                )

                # Process results
                for (room_name, _), result in zip(group_tasks, group_results, strict=False):
                    if isinstance(result, Exception):
                        logger.error(f"Scene execution error for {room_name}: {result}")
                        results[room_name] = False
                    else:
                        results[room_name] = bool(result)

        return results

    def _group_executions_by_priority(
        self, executions: list[SceneExecution]
    ) -> dict[int, list[SceneExecution]]:
        """Group executions by priority level."""
        groups = defaultdict(list)

        for execution in executions:
            # Apply priority overrides
            priority = self._priority_overrides.get(execution.room_id, execution.priority)
            groups[priority].append(execution)

        return dict(groups)

    # =========================================================================
    # Performance Optimization Helpers
    # =========================================================================

    def _get_cached_execution_plan(self, cache_key: str) -> SceneCache | None:
        """Get cached execution plan if valid."""
        if cache_key not in self._scene_cache:
            return None

        cache = self._scene_cache[cache_key]

        # Check if cache is still valid (5 minutes)
        if time.time() - cache.last_updated > 300:
            del self._scene_cache[cache_key]
            return None

        return cache

    def _estimate_execution_time(self, room: Room, scene: Scene) -> float:
        """Estimate scene execution time in milliseconds."""
        base_time = 500.0  # Base execution time

        # Adjust based on room complexity
        component_count = (
            len(room.lights)
            + len(room.shades)
            + (1 if room.audio_zone else 0)
            + (1 if room.hvac_zone_id else 0)
        )

        complexity_time = component_count * 50.0

        # Adjust based on scene transition time
        transition_time = scene.transition_seconds * 100.0

        # Use historical data if available
        cache_key = f"{room.id}:{scene.name}"
        if cache_key in self._execution_history:
            history = self._execution_history[cache_key]
            if history:
                # Use average of recent executions
                recent_average = sum(history[-10:]) / len(history[-10:])
                return recent_average

        return base_time + complexity_time + transition_time

    def _get_adaptive_timing(self, timing_key: str) -> dict[str, float]:
        """Get adaptive timing adjustments based on performance."""
        if not self._adaptive_timing_enabled:
            return {}

        adjustments = {}

        # Get historical performance for this timing scenario
        if timing_key in self._execution_history:
            history = self._execution_history[timing_key]
            if len(history) >= 5:
                avg_time = sum(history[-10:]) / len(history[-10:])

                # If consistently fast, reduce delays
                if avg_time < 200:  # <200ms
                    adjustments["shade_to_light"] = max(0.1, self.config.shade_to_light_delay * 0.5)
                    adjustments["light_to_audio"] = max(
                        0.05, self.config.light_to_audio_delay * 0.5
                    )
                # If slow, increase delays slightly for reliability
                elif avg_time > 1000:  # >1s
                    adjustments["shade_to_light"] = self.config.shade_to_light_delay * 1.5
                    adjustments["light_to_audio"] = self.config.light_to_audio_delay * 1.5

        return adjustments

    def _record_scene_execution(
        self, scene_name: str, execution_time_ms: float, success: bool
    ) -> None:
        """Record scene execution performance."""
        if self._performance_monitor:
            from kagami_smarthome.performance_monitor import MetricType

            self._performance_monitor.record_metric(
                MetricType.SCENE_ACTIVATION_TIME,
                execution_time_ms,
                scene_name,
                {"success": success},
            )

    def _update_execution_history(self, cache_key: str, execution_time_ms: float) -> None:
        """Update execution time history for adaptive optimization."""
        if cache_key not in self._execution_history:
            self._execution_history[cache_key] = []

        self._execution_history[cache_key].append(execution_time_ms)

        # Keep only recent history
        if len(self._execution_history[cache_key]) > 20:
            self._execution_history[cache_key] = self._execution_history[cache_key][-20:]

    async def _resolve_execution_conflicts(self, execution: SceneExecution) -> bool:
        """Resolve conflicts with active executions."""
        room_id = execution.room_id

        # Check if room has active execution
        if room_id in self._active_executions:
            active_task = self._active_executions[room_id]

            if not active_task.done():
                # If higher priority, cancel existing
                if execution.priority < 5:  # Higher priority
                    logger.debug(f"Cancelling lower priority execution for room {room_id}")
                    active_task.cancel()
                    del self._active_executions[room_id]
                else:
                    # Wait for current execution to finish
                    logger.debug(f"Waiting for active execution in room {room_id}")
                    try:
                        await asyncio.wait_for(active_task, timeout=5.0)
                    except TimeoutError:
                        active_task.cancel()
                    del self._active_executions[room_id]

        return True

    async def _optimize_execution_order(
        self, executions: list[SceneExecution]
    ) -> list[SceneExecution]:
        """Optimize execution order based on dependencies and performance."""
        # Sort by priority and estimated duration
        optimized = sorted(executions, key=lambda e: (e.priority, e.estimated_duration_ms))

        return optimized

    # =========================================================================
    # Configuration and Performance Methods
    # =========================================================================

    def set_room_priority(self, room_id: int, priority: int) -> None:
        """Set priority override for a room."""
        self._priority_overrides[room_id] = priority

    def enable_prediction(self, enabled: bool = True) -> None:
        """Enable or disable scene prediction."""
        self._prediction_enabled = enabled

    def enable_adaptive_timing(self, enabled: bool = True) -> None:
        """Enable or disable adaptive timing optimization."""
        self._adaptive_timing_enabled = enabled

    def get_performance_stats(self) -> dict[str, Any]:
        """Get orchestrator performance statistics."""
        return {
            "scene_cache_size": len(self._scene_cache),
            "execution_history_size": sum(
                len(history) for history in self._execution_history.values()
            ),
            "active_executions": len(self._active_executions),
            "adaptive_timing_enabled": self._adaptive_timing_enabled,
            "prediction_enabled": self._prediction_enabled,
            "max_concurrent_rooms": self._max_concurrent_rooms,
        }

    def clear_cache(self) -> None:
        """Clear scene cache and execution history."""
        self._scene_cache.clear()
        self._execution_history.clear()
        logger.info("🗑️ Scene cache and execution history cleared")
