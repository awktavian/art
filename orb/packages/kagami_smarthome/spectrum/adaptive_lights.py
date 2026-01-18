"""Adaptive Music-Reactive Lights — Real-Time Spectrum Synchronization.

LIGHT IS MUSIC IS SPECTRUM.

This module provides real-time music-reactive outdoor lighting that:
- Analyzes currently playing audio (Spotify, MIDI playback)
- Maps musical features to light parameters via SpectrumEngine
- Continuously updates Oelo with smooth transitions
- Respects circadian rhythms and household context

The adaptive loop runs continuously while music is playing,
creating an immersive audio-visual experience.

Created: January 3, 2026
h(x) >= 0 always.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from kagami_smarthome.spectrum.engine import (
    MusicalContext,
    MusicMood,
    PatternType,
    SpectrumOutput,
    get_spectrum_engine,
)

if TYPE_CHECKING:
    from kagami_smarthome.controller import SmartHomeController

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class AdaptiveLightConfig:
    """Configuration for adaptive music-reactive lights."""

    # Update rate
    update_interval_ms: int = 250  # 4 Hz update rate
    transition_smoothing: float = 0.3  # 0=instant, 1=very smooth

    # Brightness constraints (respects circadian)
    min_brightness: float = 0.1  # Never go fully dark
    max_brightness: float = 1.0  # Can be clamped by circadian

    # Pattern behavior
    allow_fast_patterns: bool = True  # Bolt, chase patterns
    max_pattern_speed: int = 15  # Limit for neighborhood courtesy

    # Audio source
    prefer_midi_analysis: bool = True  # Use MIDI if available
    spotify_polling_ms: int = 1000  # Spotify state poll rate

    # Safety
    emergency_off_velocity: int = 10  # Stop if velocity below this
    circadian_dim_factor: float = 0.5  # Late night dimming


# =============================================================================
# Spotify Audio Features
# =============================================================================


@dataclass
class SpotifyAudioFeatures:
    """Audio features from Spotify API."""

    # Rhythm
    tempo: float = 120.0  # BPM
    time_signature: int = 4

    # Tonality
    key: int = 0  # 0=C, 1=C#, ..., 11=B
    mode: int = 1  # 1=major, 0=minor

    # Energy/Mood
    energy: float = 0.5  # 0-1
    valence: float = 0.5  # 0-1 (happiness)
    danceability: float = 0.5  # 0-1

    # Dynamics
    loudness: float = -10.0  # dB

    # Instrumentation hints
    instrumentalness: float = 0.5  # 0-1
    acousticness: float = 0.5  # 0-1
    speechiness: float = 0.0  # 0-1

    def to_musical_context(self) -> MusicalContext:
        """Convert to MusicalContext for spectrum engine."""
        # Key mapping
        key_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        key_name = key_names[self.key % 12]
        mode_name = "major" if self.mode == 1 else "minor"

        # Dynamics from loudness (-60 to 0 dB typical)
        dynamics = max(0.0, min(1.0, (self.loudness + 30) / 30))

        # Infer articulation from energy and danceability
        if self.energy > 0.7 and self.danceability > 0.6:
            articulation = "staccato"
        elif self.energy < 0.3:
            articulation = "legato"
        elif self.acousticness > 0.7:
            articulation = "sustained"
        else:
            articulation = "normal"

        # Infer mood from valence and energy
        if self.valence > 0.7 and self.energy > 0.6:
            mood = MusicMood.ENERGETIC
        elif self.valence > 0.6 and self.energy < 0.4:
            mood = MusicMood.PEACEFUL
        elif self.valence < 0.3 and self.energy > 0.7:
            mood = MusicMood.INTENSE
        elif self.valence < 0.4 and self.energy < 0.4:
            mood = MusicMood.GENTLE
        elif self.energy > 0.8:
            mood = MusicMood.DRAMATIC
        else:
            mood = MusicMood.NEUTRAL

        return MusicalContext(
            tempo_bpm=self.tempo,
            key=key_name,
            mode=mode_name,
            dynamics=dynamics,
            dynamics_range=self.energy * 0.5,
            articulation=articulation,
            note_density=self.danceability,
            mood=mood,
        )


# =============================================================================
# Adaptive Light Controller
# =============================================================================


class AdaptiveLightController:
    """Real-time music-reactive outdoor lighting controller.

    Continuously analyzes playing music and updates Oelo lights
    to create synchronized audio-visual experiences.

    Usage:
        controller = AdaptiveLightController(smart_home)
        await controller.start()  # Begins reactive loop

        # Later...
        await controller.stop()
    """

    def __init__(
        self,
        smart_home: SmartHomeController,
        config: AdaptiveLightConfig | None = None,
    ) -> None:
        """Initialize adaptive light controller."""
        self._smart_home = smart_home
        self._config = config or AdaptiveLightConfig()
        self._spectrum = get_spectrum_engine()

        self._running = False
        self._task: asyncio.Task | None = None
        self._last_output: SpectrumOutput | None = None
        self._last_spotify_features: SpotifyAudioFeatures | None = None
        self._last_update: float = 0

        # Statistics
        self._updates = 0
        self._errors = 0

    @property
    def is_running(self) -> bool:
        """Check if adaptive loop is running."""
        return self._running

    async def start(self) -> bool:
        """Start the adaptive light loop.

        Returns:
            True if started successfully
        """
        if self._running:
            return True

        # Verify Oelo is available
        oelo_svc = getattr(self._smart_home, "_oelo_service", None)
        if not oelo_svc or not oelo_svc.is_available:
            logger.warning("Oelo not available - cannot start adaptive lights")
            return False

        self._running = True
        self._task = asyncio.create_task(self._adaptive_loop())
        logger.info("🌈 Adaptive music-reactive lights started")
        return True

    async def stop(self) -> None:
        """Stop the adaptive light loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        # Fade to default state
        await self._set_default_state()
        logger.info("🌈 Adaptive lights stopped")

    async def _adaptive_loop(self) -> None:
        """Main adaptive update loop."""
        while self._running:
            try:
                await self._update_cycle()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._errors += 1
                logger.debug(f"Adaptive loop error: {e}")

            # Wait for next update
            await asyncio.sleep(self._config.update_interval_ms / 1000)

    async def _update_cycle(self) -> None:
        """Single update cycle: analyze music → compute spectrum → update lights."""
        # 1. Get current music context
        context = await self._get_music_context()
        if not context:
            return  # No music playing

        # 2. Apply circadian constraints
        context = self._apply_circadian_constraints(context)

        # 3. Compute spectrum output
        output = self._spectrum.compute(context)

        # 4. Apply config constraints
        output = self._apply_config_constraints(output)

        # 5. Update Oelo if changed significantly
        if self._should_update(output):
            await self._update_oelo(output)
            self._last_output = output
            self._updates += 1

    async def _get_music_context(self) -> MusicalContext | None:
        """Get current music context from available sources."""
        # Try Spotify first (most common)
        context = await self._get_spotify_context()
        if context:
            return context

        # Try MIDI analysis if available
        if self._config.prefer_midi_analysis:
            context = await self._get_midi_context()
            if context:
                return context

        return None

    async def _get_spotify_context(self) -> MusicalContext | None:
        """Get music context from Spotify."""
        av_svc = getattr(self._smart_home, "_av_service", None)
        if not av_svc or not av_svc._spotify:
            return None

        try:
            # Get playback state
            state = av_svc.get_spotify_state()
            if not state or not state.get("is_playing"):
                return None

            # Get audio features for current track
            track = state.get("item", {})
            track_id = track.get("id")
            if not track_id:
                return None

            # Check if we have cached features for this track
            features = await self._get_spotify_audio_features(track_id)
            if features:
                self._last_spotify_features = features
                return features.to_musical_context()

            # Fallback to basic tempo estimation from track
            # (If audio features API unavailable)
            return MusicalContext(
                tempo_bpm=120,  # Default
                dynamics=0.6,
                articulation="normal",
            )

        except Exception as e:
            logger.debug(f"Spotify context error: {e}")
            return None

    async def _get_spotify_audio_features(self, track_id: str) -> SpotifyAudioFeatures | None:
        """Get Spotify audio features for a track."""
        # This would use Spotify's Audio Features API
        # For now, return None - full implementation would cache these
        try:
            av_svc = getattr(self._smart_home, "_av_service", None)
            if not av_svc or not av_svc._spotify:
                return None

            # Attempt to get audio features (if method exists)
            spotify = av_svc._spotify
            if hasattr(spotify, "get_audio_features"):
                features_data = await spotify.get_audio_features(track_id)
                if features_data:
                    return SpotifyAudioFeatures(
                        tempo=features_data.get("tempo", 120),
                        time_signature=features_data.get("time_signature", 4),
                        key=features_data.get("key", 0),
                        mode=features_data.get("mode", 1),
                        energy=features_data.get("energy", 0.5),
                        valence=features_data.get("valence", 0.5),
                        danceability=features_data.get("danceability", 0.5),
                        loudness=features_data.get("loudness", -10),
                        instrumentalness=features_data.get("instrumentalness", 0.5),
                        acousticness=features_data.get("acousticness", 0.5),
                        speechiness=features_data.get("speechiness", 0.0),
                    )
        except Exception as e:
            logger.debug(f"Audio features error: {e}")

        return None

    async def _get_midi_context(self) -> MusicalContext | None:
        """Get music context from MIDI playback."""
        # This would integrate with the RALPH/Virtuoso pipeline
        # For real-time MIDI analysis during BBC SO playback
        return None

    def _apply_circadian_constraints(self, context: MusicalContext) -> MusicalContext:
        """Apply circadian rhythm constraints to context."""
        try:
            from kagami_smarthome.context.context_engine import (
                CircadianPhase,
                get_circadian_phase,
            )

            phase = get_circadian_phase()

            # Late night: reduce dynamics
            if phase in (CircadianPhase.NIGHT, CircadianPhase.LATE_NIGHT):
                context.dynamics *= self._config.circadian_dim_factor
                # Shift mood toward peaceful
                if context.mood in (MusicMood.INTENSE, MusicMood.DRAMATIC):
                    context.mood = MusicMood.ENERGETIC
                elif context.mood == MusicMood.ENERGETIC:
                    context.mood = MusicMood.NEUTRAL

        except Exception:
            pass

        return context

    def _apply_config_constraints(self, output: SpectrumOutput) -> SpectrumOutput:
        """Apply configuration constraints to output."""
        # Brightness limits
        output.brightness = max(
            self._config.min_brightness, min(self._config.max_brightness, output.brightness)
        )

        # Pattern speed limit
        output.speed = min(self._config.max_pattern_speed, output.speed)

        # Disable fast patterns if configured
        if not self._config.allow_fast_patterns:
            if output.pattern in (PatternType.BOLT, PatternType.CHASE):
                output.pattern = PatternType.MARCH

        return output

    def _should_update(self, output: SpectrumOutput) -> bool:
        """Determine if we should send an update to Oelo."""
        if self._last_output is None:
            return True

        # Check if enough time has passed
        now = time.time()
        if now - self._last_update < 0.1:  # Max 10 Hz
            return False

        # Check for significant changes
        hue_diff = abs(output.hue - self._last_output.hue)
        if hue_diff > 180:
            hue_diff = 360 - hue_diff

        bright_diff = abs(output.brightness - self._last_output.brightness)
        pattern_changed = output.pattern != self._last_output.pattern

        # Update if significant change
        if hue_diff > 10 or bright_diff > 0.1 or pattern_changed:
            self._last_update = now
            return True

        return False

    async def _update_lights(self, output: SpectrumOutput) -> None:
        """Send spectrum output to all available light systems.

        LIGHT IS MUSIC IS SPECTRUM.

        Supports multiple light systems:
        - Oelo outdoor lights (ESP8266 controller)
        - Govee indoor/strip lights (Cloud + LAN API)
        """
        # Update Oelo
        await self._update_oelo(output)

        # Update Govee
        await self._update_govee(output)

    async def _update_oelo(self, output: SpectrumOutput) -> None:
        """Send spectrum output to Oelo."""
        oelo_svc = getattr(self._smart_home, "_oelo_service", None)
        if not oelo_svc:
            return

        try:
            # Convert colors to Oelo format
            from kagami_smarthome.integrations.oelo import Color

            colors = [Color(*rgb) for rgb in output.colors]

            # Get Oelo integration directly for custom pattern
            oelo = getattr(oelo_svc, "_oelo", None)
            if oelo:
                await oelo.set_custom(
                    pattern_type=output.pattern.value,
                    colors=colors,
                    speed=output.speed,
                )

        except Exception as e:
            logger.debug(f"Oelo update error: {e}")
            self._errors += 1

    async def _update_govee(self, output: SpectrumOutput) -> None:
        """Send spectrum output to Govee lights."""
        try:
            # Check if Govee integration is available
            govee = getattr(self._smart_home, "_govee", None)
            if not govee or not govee.is_connected:
                return

            # Apply spectrum to all Govee devices
            await govee.apply_spectrum_all(output)

        except Exception as e:
            logger.debug(f"Govee update error: {e}")

    async def _set_default_state(self) -> None:
        """Set lights to default state when stopping."""
        # Oelo
        oelo_svc = getattr(self._smart_home, "_oelo_service", None)
        if oelo_svc and oelo_svc.is_available:
            try:
                await oelo_svc.outdoor_welcome()
            except Exception:
                pass

        # Govee - set warm white
        try:
            govee = getattr(self._smart_home, "_govee", None)
            if govee and govee.is_connected and govee.devices:
                # Set all Govee devices in parallel
                tasks = []
                for device in govee.devices:
                    tasks.extend(
                        [
                            govee.set_color(device.device_id, (255, 200, 150)),
                            govee.set_brightness(device.device_id, 50),
                        ]
                    )
                await asyncio.gather(*tasks, return_exceptions=True)
        except Exception:
            pass

    def get_stats(self) -> dict[str, Any]:
        """Get controller statistics."""
        return {
            "running": self._running,
            "updates": self._updates,
            "errors": self._errors,
            "last_mood": self._last_output.mood.value if self._last_output else None,
            "last_pattern": self._last_output.pattern.value if self._last_output else None,
        }


# =============================================================================
# Convenience
# =============================================================================

# Global instance
_adaptive_controller: AdaptiveLightController | None = None


async def get_adaptive_lights(
    smart_home: SmartHomeController,
    config: AdaptiveLightConfig | None = None,
) -> AdaptiveLightController:
    """Get or create global adaptive light controller."""
    global _adaptive_controller
    if _adaptive_controller is None:
        _adaptive_controller = AdaptiveLightController(smart_home, config)
    return _adaptive_controller


__all__ = [
    "AdaptiveLightConfig",
    "AdaptiveLightController",
    "SpotifyAudioFeatures",
    "get_adaptive_lights",
]
