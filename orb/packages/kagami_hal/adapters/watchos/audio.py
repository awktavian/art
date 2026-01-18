"""WatchOS Audio Adapter.

Implements audio for Apple Watch using AVFoundation.

Features:
- Audio playback (limited speaker)
- Audio recording (microphone)
- Voice memo support
- Siri integration hooks

Note: Apple Watch has limited audio capabilities compared to iOS.
Speaker is primarily for alerts; headphone/AirPods are preferred for music.

Created: December 13, 2025
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

from kagami.core.boot_mode import is_test_mode

from kagami_hal.data_types import AudioConfig, AudioFormat

logger = logging.getLogger(__name__)

WATCHOS_AVAILABLE = sys.platform == "darwin" and os.environ.get("KAGAMI_PLATFORM") == "watchos"


class WatchOSAudio:
    """Apple Watch audio adapter.

    Provides:
    - Audio playback (speaker, limited)
    - Audio recording (microphone)
    - Volume control

    Note: For music/media, use watchOS Now Playing APIs.
    """

    def __init__(self):
        """Initialize WatchOS audio adapter."""
        self._audio_engine: Any = None
        self._audio_recorder: Any = None
        self._initialized = False
        self._volume: float = 0.5
        self._config: AudioConfig | None = None

    async def initialize(self, config: AudioConfig | None = None) -> bool:
        """Initialize audio adapter."""
        if not WATCHOS_AVAILABLE:
            if is_test_mode():
                logger.info("WatchOS audio not available, gracefully degrading")
                return False
            raise RuntimeError("WatchOS audio only available on Apple Watch")

        try:
            from AVFoundation import AVAudioSession

            # Configure audio session
            session = AVAudioSession.sharedInstance()
            session.setCategory_error_("AVAudioSessionCategoryPlayAndRecord", None)
            session.setActive_error_(True, None)

            self._config = config or AudioConfig(
                sample_rate=16000,  # Lower rate for watch
                channels=1,  # Mono
                format=AudioFormat.PCM_16,
                buffer_size=512,
            )

            self._initialized = True
            logger.info("✅ WatchOS audio adapter initialized")
            return True

        except ImportError as e:
            logger.error(f"AVFoundation not available: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize WatchOS audio: {e}", exc_info=True)
            return False

    async def shutdown(self) -> None:
        """Shutdown audio adapter."""
        try:
            if self._audio_recorder:
                self._audio_recorder.stop()
                self._audio_recorder = None

            from AVFoundation import AVAudioSession

            session = AVAudioSession.sharedInstance()
            session.setActive_error_(False, None)

        except Exception as e:
            logger.error(f"Error during audio shutdown: {e}")

        self._initialized = False
        logger.info("✅ WatchOS audio adapter shutdown")

    async def play(self, buffer: bytes) -> None:
        """Play audio buffer.

        Note: On watchOS, audio playback is typically through
        system sounds or AVAudioPlayer for short clips.
        """
        if not self._initialized:
            raise RuntimeError("Audio adapter not initialized")

        try:
            from AVFoundation import AVAudioPlayer
            from Foundation import NSData

            data = NSData.dataWithBytes_length_(buffer, len(buffer))
            player = AVAudioPlayer.alloc().initWithData_error_(data, None)

            if player:
                player.setVolume_(self._volume)
                player.play()
                logger.debug(f"Playing audio: {len(buffer)} bytes")

        except Exception as e:
            logger.error(f"Failed to play audio: {e}")

    async def record(self, duration_ms: int) -> bytes:
        """Record audio from microphone.

        Args:
            duration_ms: Recording duration in milliseconds

        Returns:
            Recorded audio data
        """
        if not self._initialized:
            raise RuntimeError("Audio adapter not initialized")

        try:
            import asyncio

            from AVFoundation import AVAudioRecorder
            from Foundation import NSURL, NSTemporaryDirectory

            # Create temp file for recording
            temp_path = NSTemporaryDirectory() + "kagami_recording.wav"
            url = NSURL.fileURLWithPath_(temp_path)

            # Recording settings
            settings = {
                "AVFormatIDKey": 1819304813,  # kAudioFormatLinearPCM
                "AVSampleRateKey": self._config.sample_rate if self._config else 16000,
                "AVNumberOfChannelsKey": 1,
                "AVLinearPCMBitDepthKey": 16,
            }

            recorder = AVAudioRecorder.alloc().initWithURL_settings_error_(url, settings, None)

            if recorder:
                recorder.record()
                await asyncio.sleep(duration_ms / 1000.0)
                recorder.stop()

                # Read recorded data
                with open(temp_path, "rb") as f:
                    data = f.read()

                # Cleanup
                import os

                os.remove(temp_path)

                logger.debug(f"Recorded {len(data)} bytes")
                return data

            return b""

        except Exception as e:
            logger.error(f"Failed to record audio: {e}")
            return b""

    async def set_volume(self, level: float) -> None:
        """Set playback volume."""
        self._volume = max(0.0, min(1.0, level))
        logger.debug(f"Volume set to {self._volume:.0%}")

    async def get_volume(self) -> float:
        """Get current volume."""
        return self._volume

    # =========================================================================
    # WatchOS-Specific Methods
    # =========================================================================

    async def play_system_sound(self, sound_id: int = 1000) -> None:
        """Play a system sound.

        Common sound IDs:
        - 1000: Default notification
        - 1001: Alarm
        - 1002: Timer
        """
        try:
            from AudioToolbox import AudioServicesPlaySystemSound

            AudioServicesPlaySystemSound(sound_id)
            logger.debug(f"System sound played: {sound_id}")

        except Exception as e:
            logger.error(f"Failed to play system sound: {e}")

    async def dictate(self, prompt: str = "") -> str | None:
        """Start dictation using Siri.

        Args:
            prompt: Optional prompt to show user

        Returns:
            Transcribed text or None if cancelled
        """
        # Dictation is handled by WKInterfaceController.presentTextInputController
        # This is a placeholder for the interface
        logger.debug(f"Dictation requested: {prompt}")
        return None

    @property
    def has_speaker(self) -> bool:
        """Check if device has speaker (Series 3+)."""
        return True  # All current Apple Watches have speakers

    @property
    def has_microphone(self) -> bool:
        """Check if device has microphone."""
        return True
