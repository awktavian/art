"""Unified Sensory Aggregator - the main integration layer.

This module orchestrates all sensor modules, manages caching, polling,
event emission, and wires to consciousness and alert systems.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any

from .base import (
    ADAPTIVE_CONFIGS,
    DEFAULT_SENSE_CONFIGS,
    ActivityLevel,
    CachedSense,
    SenseEventCallback,
    SenseType,
)
from .biometric import BiometricSensors
from .digital import DigitalSensors
from .environmental import EnvironmentalSensors
from .home import HomeSensors
from .patterns import PatternManager
from .vehicle import VehicleSensors

if TYPE_CHECKING:
    from kagami_smarthome import SmartHomeController

    from kagami.core.services.composio import ComposioIntegrationService

logger = logging.getLogger(__name__)


class UnifiedSensoryIntegration:
    """Unified sensory bus - THE SINGLE source for all sensory data.

    This class orchestrates all sensor modules and provides:
    - Single polling loop for all senses
    - TTL-based caching
    - Event emission for state changes
    - Pattern learning for predictions
    - Alert and consciousness integration
    """

    def __init__(self):
        self._composio: ComposioIntegrationService | None = None
        self._smart_home: SmartHomeController | None = None

        # Sense configurations
        self._configs = DEFAULT_SENSE_CONFIGS.copy()
        self._adaptive_configs = ADAPTIVE_CONFIGS.copy()

        # Cache storage
        self._cache: dict[SenseType, CachedSense] = {}

        # Polling state
        self._running = False
        self._poll_task: asyncio.Task | None = None
        self._last_poll: dict[SenseType, float] = {}

        # Event subscribers
        self._listeners: list[SenseEventCallback] = []

        # Integrations
        self._alert_hierarchy: Any = None
        self._consciousness: Any = None
        self._situation_engine: Any = None

        # Statistics
        self._stats: dict[str, Any] = {
            "polls": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "events_emitted": 0,
            "alerts_submitted": 0,
        }

        # Pattern learning
        self._pattern_manager = PatternManager()
        self._last_pattern_save = time.monotonic()
        self._pattern_save_interval = 3600.0

        # Adaptive polling state
        self._activity_level = ActivityLevel.NORMAL
        self._last_activity_time = time.monotonic()
        self._is_home = True

        # Wakefulness multiplier
        self._poll_multiplier_func: Callable[[str | None], float] = lambda _: 1.0

        # Initialize sensor modules
        self._environmental = EnvironmentalSensors(self._cache, self._stats)
        self._biometric = BiometricSensors(self._cache, self._stats)
        self._digital = DigitalSensors(self._cache, self._stats)
        self._home = HomeSensors(self._cache, self._stats)
        self._vehicle = VehicleSensors(self._cache, self._stats)

        self._initialized = False

    async def initialize(
        self,
        composio: ComposioIntegrationService | None = None,
        smart_home: SmartHomeController | None = None,
    ) -> bool:
        """Initialize with service connections."""
        if composio:
            self._composio = composio
            if not composio.initialized:
                await composio.initialize()
            self._digital.set_composio(composio)

        if smart_home:
            self._smart_home = smart_home
            self._biometric.set_smart_home(smart_home)
            self._home.set_smart_home(smart_home)
            self._vehicle.set_smart_home(smart_home)

            if hasattr(smart_home, "on_state_change"):
                smart_home.on_state_change(self._on_smart_home_push)

            if hasattr(smart_home, "_unifi") and smart_home._unifi is not None:
                unifi = smart_home._unifi
                if hasattr(unifi, "on_event"):
                    unifi.on_event(self._on_unifi_realtime_event)
                    logger.info("UnifiedSensory: Subscribed to UniFi WebSocket events")

        # Initialize pattern learning
        self._pattern_manager.initialize()

        self._initialized = bool(self._composio or self._smart_home)

        if self._initialized:
            logger.info(
                f"UnifiedSensoryIntegration initialized: "
                f"digital={bool(self._composio)}, physical={bool(self._smart_home)}"
            )

        return self._initialized

    def set_poll_multiplier(self, func: Callable[[str | None], float]) -> None:
        """Set poll interval multiplier function."""
        self._poll_multiplier_func = func
        logger.info("UnifiedSensory poll multiplier wired to WakefulnessManager")

    def set_alert_hierarchy(self, alert_hierarchy: Any) -> None:
        """Wire the alert hierarchy for automatic alert submission."""
        self._alert_hierarchy = alert_hierarchy
        logger.info("AlertHierarchy wired to UnifiedSensory")

    def set_consciousness(self, consciousness: Any) -> None:
        """Wire organism consciousness for direct perception updates."""
        self._consciousness = consciousness
        logger.info("OrganismConsciousness wired to UnifiedSensory")

    # =========================================================================
    # ADAPTIVE POLLING
    # =========================================================================

    def get_effective_poll_interval(self, sense_type: SenseType) -> float:
        """Get effective poll interval with adaptive strategies."""
        base_interval = self._configs[sense_type].poll_interval
        wake_mult = self._poll_multiplier_func(sense_type.value)

        adaptive = self._adaptive_configs.get(sense_type)
        if not adaptive:
            return base_interval * wake_mult

        activity_mult = adaptive.activity_multipliers.get(self._activity_level, 1.0)
        presence_mult = adaptive.present_multiplier if self._is_home else adaptive.away_multiplier

        time_mult = 1.0
        if adaptive.time_multipliers:
            current_hour = datetime.now().hour
            time_mult = adaptive.time_multipliers.get(current_hour, 1.0)

        effective = base_interval * wake_mult * activity_mult * presence_mult * time_mult

        config = self._configs[sense_type]
        min_interval = config.poll_interval * 0.25
        max_interval = config.poll_interval * 10.0

        return max(min_interval, min(max_interval, effective))

    def update_activity_level(self, level: ActivityLevel | None = None) -> None:
        """Update activity level for adaptive polling."""
        now = time.monotonic()

        if level is not None:
            self._activity_level = level
            self._last_activity_time = now
            return

        idle_seconds = now - self._last_activity_time

        if idle_seconds < 30:
            self._activity_level = ActivityLevel.HIGH
        elif idle_seconds < 120:
            self._activity_level = ActivityLevel.NORMAL
        elif idle_seconds < 300:
            self._activity_level = ActivityLevel.LOW
        else:
            self._activity_level = ActivityLevel.INACTIVE

    def record_activity(self) -> None:
        """Record user activity."""
        self._last_activity_time = time.monotonic()
        self.update_activity_level()

    def set_presence(self, is_home: bool) -> None:
        """Update presence state for adaptive polling."""
        self._is_home = is_home

    # =========================================================================
    # EVENT SYSTEM
    # =========================================================================

    def on_sense_change(self, callback: SenseEventCallback) -> None:
        """Register callback for sensory changes."""
        self._listeners.append(callback)

    def remove_listener(self, callback: SenseEventCallback) -> None:
        """Remove a listener."""
        if callback in self._listeners:
            self._listeners.remove(callback)

    async def _emit_change(
        self, sense_type: SenseType, data: dict[str, Any], delta: dict[str, Any]
    ) -> None:
        """Emit change event to all listeners."""
        self._stats["events_emitted"] += 1

        for listener in self._listeners:
            try:
                await listener(sense_type, data, delta)
            except Exception as e:
                listener_name = getattr(listener, "__name__", repr(listener))
                logger.debug(
                    f"Listener {listener_name} failed for {sense_type.value}: {type(e).__name__}: {e}"
                )

        if self._alert_hierarchy and self._configs[sense_type].alert_on_change and delta:
            await self._submit_auto_alert(sense_type, data, delta)

        if self._consciousness:
            await self._update_consciousness(sense_type, data)

    async def _submit_auto_alert(
        self, sense_type: SenseType, data: dict[str, Any], delta: dict[str, Any]
    ) -> None:
        """Automatically submit alerts for significant changes."""
        try:
            from kagami.core.integrations.alert_hierarchy import AlertCategory

            category_map = {
                SenseType.GMAIL: AlertCategory.COMMUNICATION,
                SenseType.CALENDAR: AlertCategory.CALENDAR,
                SenseType.GITHUB: AlertCategory.WORK,
                SenseType.LINEAR: AlertCategory.WORK,
                SenseType.PRESENCE: AlertCategory.HOME,
                SenseType.LOCKS: AlertCategory.SECURITY,
                SenseType.SECURITY: AlertCategory.SECURITY,
                SenseType.SLEEP: AlertCategory.HEALTH,
            }

            category = category_map.get(sense_type, AlertCategory.SYSTEM)

            if sense_type == SenseType.GMAIL and data.get("urgent_count", 0) > 0:
                await self._alert_hierarchy.submit_from_sense(
                    title=f"{data['urgent_count']} urgent emails",
                    message=f"From: {', '.join(data.get('urgent_senders', [])[:3])}",
                    source="gmail",
                    category=category,
                )
                self._stats["alerts_submitted"] += 1

            elif sense_type == SenseType.LOCKS and not data.get("all_locked", True):
                await self._alert_hierarchy.submit_from_sense(
                    title="Door unlocked",
                    message="A door lock state changed",
                    source="locks",
                    category=category,
                )
                self._stats["alerts_submitted"] += 1

            elif sense_type == SenseType.SECURITY:
                if data.get("alarm_active"):
                    await self._alert_hierarchy.submit_from_sense(
                        title="Security alert",
                        message="Security system triggered",
                        source="security",
                        category=category,
                    )
                    self._stats["alerts_submitted"] += 1

        except Exception as e:
            logger.debug(f"Auto-alert error: {e}")

    async def _update_consciousness(self, sense_type: SenseType, data: dict[str, Any]) -> None:
        """Update organism consciousness with sensory data."""
        if not self._consciousness:
            return

        try:
            perception_vector = self._encode_to_perception(sense_type, data)

            if perception_vector is not None:
                import torch

                self._consciousness.update_subsystem_direct(
                    "perception",
                    torch.tensor(perception_vector).unsqueeze(0),
                    alpha=0.2,
                )

        except Exception as e:
            logger.debug(f"Consciousness update error: {e}")

    def _encode_to_perception(
        self, sense_type: SenseType, data: dict[str, Any]
    ) -> list[float] | None:
        """Encode sensory data to perception vector (512 dims)."""
        base_vector = [0.0] * 512

        sense_offset = {
            SenseType.GMAIL: 0,
            SenseType.GITHUB: 32,
            SenseType.LINEAR: 64,
            SenseType.CALENDAR: 96,
            SenseType.PRESENCE: 256,
            SenseType.LOCKS: 288,
            SenseType.CLIMATE: 320,
            SenseType.SLEEP: 352,
            SenseType.SECURITY: 384,
            SenseType.VEHICLE: 416,
            SenseType.WEATHER: 448,
            SenseType.SOCIAL: 480,
        }

        offset = sense_offset.get(sense_type)
        if offset is None:
            return None

        if sense_type == SenseType.GMAIL:
            base_vector[offset] = float(data.get("urgent_count", 0)) / 10.0
            base_vector[offset + 1] = float(data.get("unread_count", 0)) / 50.0

        elif sense_type == SenseType.PRESENCE:
            presence_map = {
                "away": 0.0,
                "arriving": 0.3,
                "home": 0.6,
                "active": 0.8,
                "sleeping": 0.2,
            }
            base_vector[offset] = presence_map.get(data.get("presence", "unknown"), 0.5)

        elif sense_type == SenseType.LOCKS:
            base_vector[offset] = 1.0 if data.get("all_locked", True) else 0.0

        elif sense_type == SenseType.CLIMATE:
            base_vector[offset] = (data.get("avg_temp", 72) - 60) / 30.0

        elif sense_type == SenseType.SLEEP:
            state_map = {"unknown": 0.5, "awake": 1.0, "sleeping": 0.0, "in_bed": 0.3}
            base_vector[offset] = state_map.get(data.get("state", "unknown"), 0.5)

        elif sense_type == SenseType.VEHICLE:
            base_vector[offset] = 1.0 if data.get("is_home") else 0.0
            base_vector[offset + 1] = 1.0 if data.get("is_driving") else 0.0
            base_vector[offset + 2] = 1.0 if data.get("is_arriving") else 0.0
            base_vector[offset + 3] = min(float(data.get("eta_minutes", 0)) / 60.0, 1.0)
            base_vector[offset + 4] = float(data.get("battery_level", 0)) / 100.0

        elif sense_type == SenseType.WEATHER:
            condition_map = {
                "clear": 0.9,
                "clouds": 0.7,
                "fog": 0.5,
                "rain": 0.3,
                "snow": 0.1,
            }
            base_vector[offset] = condition_map.get(data.get("condition", "clear"), 0.5)
            base_vector[offset + 1] = (data.get("temperature", 60) - 20) / 80.0

        return base_vector

    # =========================================================================
    # CACHING
    # =========================================================================

    def _get_cached(self, sense_type: SenseType) -> CachedSense | None:
        """Get cached data if valid."""
        cached = self._cache.get(sense_type)
        if cached and cached.is_valid:
            self._stats["cache_hits"] += 1
            return cached
        self._stats["cache_misses"] += 1
        return None

    def _set_cached(self, sense_type: SenseType, data: dict[str, Any]) -> dict[str, Any]:
        """Cache sensory data and return delta from previous."""
        config = self._configs.get(sense_type)
        ttl = config.cache_ttl if config else 60.0

        old_data = self._cache.get(sense_type)
        delta = {}
        if old_data:
            for key, value in data.items():
                if old_data.data.get(key) != value:
                    delta[key] = value
        else:
            delta = data.copy()

        self._cache[sense_type] = CachedSense(sense_type=sense_type, data=data, ttl=ttl)

        # Record patterns
        self._pattern_manager.record_sense_patterns(sense_type, data)

        return delta

    def invalidate_cache(self, sense_type: SenseType | None = None) -> None:
        """Invalidate cache for one or all senses."""
        if sense_type:
            self._cache.pop(sense_type, None)
        else:
            self._cache.clear()

    # =========================================================================
    # PUSH EVENT HANDLERS
    # =========================================================================

    def _on_smart_home_push(self, home_state: Any) -> None:
        """Handle push events from SmartHome."""
        try:
            data = {
                "presence": home_state.presence.value if home_state.presence else "unknown",
                "activity": home_state.activity.value if home_state.activity else "unknown",
                "location": home_state.last_location,
            }

            self.invalidate_cache(SenseType.PRESENCE)
            asyncio.create_task(self._emit_change(SenseType.PRESENCE, data, data))

        except Exception as e:
            logger.debug(f"SmartHome push handler error: {e}")

    def _on_unifi_realtime_event(self, event: Any) -> None:
        """Handle real-time UniFi WebSocket events."""
        try:
            event_type = event.event_type if hasattr(event, "event_type") else str(event)
            location = event.location if hasattr(event, "location") else None
            confidence = event.confidence if hasattr(event, "confidence") else 0.8
            metadata = event.metadata if hasattr(event, "metadata") else {}

            sense_type_map = {
                "person": SenseType.MOTION,
                "vehicle": SenseType.MOTION,
                "motion": SenseType.MOTION,
                "motion_start": SenseType.MOTION,
                "doorbell": SenseType.SECURITY,
            }

            sense_type = sense_type_map.get(event_type, SenseType.MOTION)

            data = {
                "event_type": event_type,
                "location": location,
                "confidence": confidence,
                "camera_id": metadata.get("camera_id"),
                "realtime": True,
                "timestamp": datetime.now().isoformat(),
            }

            asyncio.create_task(self._emit_change(sense_type, data, data))

            logger.debug(f"UniFi realtime: {event_type} at {location}")

        except Exception as e:
            logger.debug(f"UniFi realtime event handler error: {e}")

    # =========================================================================
    # POLLING
    # =========================================================================

    async def _poll_sense(self, sense_type: SenseType) -> dict[str, Any]:
        """Poll a single sense type."""
        data: dict[str, Any] = {}

        if sense_type == SenseType.GMAIL:
            data = await self._digital.poll_gmail()
        elif sense_type == SenseType.GITHUB:
            data = await self._digital.poll_github()
        elif sense_type == SenseType.LINEAR:
            data = await self._digital.poll_linear()
        elif sense_type == SenseType.SLACK:
            data = await self._digital.poll_slack()
        elif sense_type == SenseType.FIGMA:
            data = await self._digital.poll_figma()
        elif sense_type == SenseType.CALENDAR:
            data = await self._digital.poll_calendar()
        elif sense_type == SenseType.SOCIAL:
            data = await self._digital.poll_social(self._get_cached)
        elif sense_type == SenseType.PRESENCE:
            data = await self._home.poll_presence()
            # Update adaptive polling state
            presence = data.get("presence", "unknown")
            self._is_home = presence in ("home", "active", "sleeping")
        elif sense_type == SenseType.LOCKS:
            data = await self._home.poll_locks()
        elif sense_type == SenseType.CLIMATE:
            data = await self._home.poll_climate()
        elif sense_type == SenseType.SECURITY:
            data = await self._home.poll_security()
        elif sense_type == SenseType.CAMERAS:
            data = await self._home.poll_cameras()
        elif sense_type == SenseType.SLEEP:
            data = await self._biometric.poll_sleep()
        elif sense_type == SenseType.HEALTH:
            data = await self._biometric.poll_health()
        elif sense_type == SenseType.VEHICLE:
            data = await self._vehicle.poll_vehicle()
        elif sense_type == SenseType.WEATHER:
            data = await self._environmental.poll_weather()
        elif sense_type == SenseType.WORLD_STATE:
            data = await self._environmental.poll_world_state()
        elif sense_type == SenseType.SITUATION:
            data = await self._environmental.poll_situation(self._get_cached)

        if data:
            delta = self._set_cached(sense_type, data)
            self._stats["polls"] += 1
            self._last_poll[sense_type] = time.monotonic()

            if delta:
                await self._emit_change(sense_type, data, delta)

        return data

    async def poll_all(self, use_cache: bool = True) -> dict[SenseType, dict[str, Any]]:
        """Poll all enabled senses and return data."""
        if not use_cache:
            self.invalidate_cache()

        results: dict[SenseType, dict[str, Any]] = {}

        digital_tasks = []
        if self._composio and self._composio.initialized:
            digital_tasks = [
                (SenseType.GMAIL, self._poll_sense(SenseType.GMAIL)),
                (SenseType.GITHUB, self._poll_sense(SenseType.GITHUB)),
                (SenseType.LINEAR, self._poll_sense(SenseType.LINEAR)),
                (SenseType.CALENDAR, self._poll_sense(SenseType.CALENDAR)),
            ]

        physical_tasks = []
        if self._smart_home:
            physical_tasks = [
                (SenseType.PRESENCE, self._poll_sense(SenseType.PRESENCE)),
                (SenseType.LOCKS, self._poll_sense(SenseType.LOCKS)),
                (SenseType.SLEEP, self._poll_sense(SenseType.SLEEP)),
                (SenseType.HEALTH, self._poll_sense(SenseType.HEALTH)),
                (SenseType.CLIMATE, self._poll_sense(SenseType.CLIMATE)),
                (SenseType.SECURITY, self._poll_sense(SenseType.SECURITY)),
                (SenseType.CAMERAS, self._poll_sense(SenseType.CAMERAS)),
                (SenseType.VEHICLE, self._poll_sense(SenseType.VEHICLE)),
            ]

        environmental_tasks = [
            (SenseType.WEATHER, self._poll_sense(SenseType.WEATHER)),
            (SenseType.WORLD_STATE, self._poll_sense(SenseType.WORLD_STATE)),
            (SenseType.SITUATION, self._poll_sense(SenseType.SITUATION)),
        ]

        all_tasks = digital_tasks + physical_tasks + environmental_tasks
        if all_tasks:
            task_results = await asyncio.gather(
                *[task[1] for task in all_tasks], return_exceptions=True
            )

            for (sense_type, _), result in zip(all_tasks, task_results, strict=False):
                if isinstance(result, Exception):
                    logger.debug(f"Poll {sense_type.value} failed: {result}")
                else:
                    results[sense_type] = result

        try:
            social_result = await self._poll_sense(SenseType.SOCIAL)
            results[SenseType.SOCIAL] = social_result
        except Exception as e:
            logger.debug(f"Social sense failed: {e}")

        return results

    async def start_polling(self) -> None:
        """Start the unified polling loop."""
        if self._running:
            return

        self._running = True

        from kagami.core.async_utils import safe_create_task

        self._poll_task = safe_create_task(
            self._poll_loop(),
            name="unified_sensory_poll",
            error_callback=lambda e: logger.error(f"Sensory poll error: {e}"),
        )

        logger.info("UnifiedSensory polling started (single loop)")

    async def stop_polling(self) -> None:
        """Stop the polling loop and persist learned patterns."""
        self._running = False

        if self._poll_task:
            self._poll_task.cancel()
            self._poll_task = None

        self._pattern_manager.save_all()
        logger.info("Saved learned patterns to disk")
        logger.info("UnifiedSensory polling stopped")

    async def _poll_loop(self) -> None:
        """The unified polling loop."""
        poll_functions = {
            SenseType.GMAIL: self._poll_sense,
            SenseType.GITHUB: self._poll_sense,
            SenseType.LINEAR: self._poll_sense,
            SenseType.SLACK: self._poll_sense,
            SenseType.CALENDAR: self._poll_sense,
            SenseType.FIGMA: self._poll_sense,
            SenseType.PRESENCE: self._poll_sense,
            SenseType.LOCKS: self._poll_sense,
            SenseType.SLEEP: self._poll_sense,
            SenseType.CLIMATE: self._poll_sense,
            SenseType.SECURITY: self._poll_sense,
            SenseType.VEHICLE: self._poll_sense,
            SenseType.CAMERAS: self._poll_sense,
            SenseType.WEATHER: self._poll_sense,
            SenseType.WORLD_STATE: self._poll_sense,
            SenseType.SITUATION: self._poll_sense,
            SenseType.SOCIAL: self._poll_sense,
            SenseType.HEALTH: self._poll_sense,
        }

        digital_senses = {SenseType.GMAIL, SenseType.GITHUB, SenseType.LINEAR}
        physical_senses = {
            SenseType.PRESENCE,
            SenseType.LOCKS,
            SenseType.SLEEP,
            SenseType.CLIMATE,
            SenseType.SECURITY,
            SenseType.VEHICLE,
            SenseType.CAMERAS,
        }
        # Environmental senses - not separately tracked as they poll via external services

        while self._running:
            try:
                now = time.monotonic()

                due_senses = []
                for sense_type, config in self._configs.items():
                    if not config.enabled:
                        continue
                    if sense_type not in poll_functions:
                        continue

                    if sense_type in digital_senses:
                        if not self._composio or not self._composio.initialized:
                            continue
                    if sense_type in physical_senses:
                        if not self._smart_home:
                            continue

                    last = self._last_poll.get(sense_type, 0)
                    effective_interval = self.get_effective_poll_interval(sense_type)
                    if (now - last) >= effective_interval:
                        due_senses.append(sense_type)

                if due_senses:
                    tasks = [poll_functions[st](st) for st in due_senses]
                    await asyncio.gather(*tasks, return_exceptions=True)

                next_poll_in = float("inf")
                for sense_type, config in self._configs.items():
                    if not config.enabled or sense_type not in poll_functions:
                        continue
                    last = self._last_poll.get(sense_type, 0)
                    effective_interval = self.get_effective_poll_interval(sense_type)
                    remaining = effective_interval - (now - last)
                    if remaining > 0:
                        next_poll_in = min(next_poll_in, remaining)

                if now - self._last_pattern_save >= self._pattern_save_interval:
                    self._pattern_manager.save_all()
                    self._last_pattern_save = now
                    logger.debug("Periodic pattern save completed")

                sleep_time = max(1.0, min(next_poll_in, 60.0))
                await asyncio.sleep(sleep_time)

            except asyncio.CancelledError:
                self._pattern_manager.save_all()
                break
            except Exception as e:
                logger.error(f"Poll loop error: {e}")
                await asyncio.sleep(60)

    # =========================================================================
    # PATTERN LEARNING API
    # =========================================================================

    def get_pattern_prediction(
        self, pattern_name: str, at: datetime | None = None
    ) -> dict[str, Any] | None:
        """Get pattern prediction for a specific behavior."""
        return self._pattern_manager.get_prediction(pattern_name, at)

    def get_all_pattern_predictions(self, at: datetime | None = None) -> dict[str, dict[str, Any]]:
        """Get predictions for all learned patterns."""
        return self._pattern_manager.get_all_predictions(at)

    def get_pattern_summaries(self) -> dict[str, dict[str, Any]]:
        """Get summaries of all learned patterns."""
        return self._pattern_manager.get_summaries()

    def predict_upcoming(self, horizon_minutes: int = 60) -> list[dict[str, Any]]:
        """Predict upcoming patterns within time horizon."""
        return self._pattern_manager.predict_upcoming(horizon_minutes)

    def get_proactive_suggestions(self) -> list[dict[str, Any]]:
        """Get proactive suggestions based on pattern predictions."""
        return self._pattern_manager.get_proactive_suggestions()

    def save_patterns(self) -> None:
        """Save all learned patterns to disk."""
        self._pattern_manager.save_all()

    # =========================================================================
    # CLIENT HEALTH UPDATE
    # =========================================================================

    async def update_client_health(self, source: str, data: dict[str, Any]) -> None:
        """Update health data from a client device."""
        health_data: dict[str, Any] = {
            "heart_rate": data.get("heart_rate"),
            "resting_heart_rate": data.get("resting_heart_rate"),
            "hrv": data.get("hrv"),
            "hrv_status": self._biometric.classify_hrv(data.get("hrv")),
            "steps": data.get("steps", 0),
            "active_calories": data.get("active_calories", 0),
            "exercise_minutes": data.get("exercise_minutes", 0),
            "blood_oxygen": data.get("blood_oxygen"),
            "sleep_quality": self._biometric.classify_sleep(data.get("sleep_hours")),
            "sleep_hours": data.get("sleep_hours"),
            "all_rings_closed": self._biometric.check_rings_closed(data),
            "timestamp": datetime.now().isoformat(),
            "source": source,
            "source_type": "client",
        }

        hr = data.get("heart_rate")
        health_data["is_heart_elevated"] = bool(hr and hr > 100)

        spo2 = data.get("blood_oxygen")
        if spo2:
            if spo2 < 92:
                health_data["oxygen_status"] = "low"
            elif spo2 < 95:
                health_data["oxygen_status"] = "borderline"
            else:
                health_data["oxygen_status"] = "normal"

        delta = self._set_cached(SenseType.HEALTH, health_data)
        self._stats["polls"] += 1
        self._last_poll[SenseType.HEALTH] = time.monotonic()

        if delta:
            await self._emit_change(SenseType.HEALTH, health_data, delta)

            if health_data.get("is_heart_elevated"):
                await self._biometric.emit_health_alert(
                    "Elevated heart rate detected",
                    f"Heart rate: {hr} bpm (from {source})",
                    priority=2,
                )
            if health_data.get("oxygen_status") == "low":
                await self._biometric.emit_health_alert(
                    "Low blood oxygen detected",
                    f"SpO2: {spo2}% (from {source})",
                    priority=1,
                )

        logger.debug(f"Health data updated from client: {source}")

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def get_stats(self) -> dict[str, Any]:
        """Get polling statistics."""
        return {
            **self._stats,
            "cache_size": len(self._cache),
            "listeners": len(self._listeners),
            "running": self._running,
            "initialized": self._initialized,
        }

    def get_cache_status(self) -> dict[str, Any]:
        """Get cache status for all senses."""
        return {
            sense_type.value: {
                "valid": cached.is_valid,
                "age": cached.age,
                "ttl": cached.ttl,
            }
            for sense_type, cached in self._cache.items()
        }

    def get_latest(self, sense_type: SenseType) -> dict[str, Any] | None:
        """Get latest cached data for a sense type."""
        cached = self._cache.get(sense_type)
        return cached.data if cached else None


__all__ = ["UnifiedSensoryIntegration"]
