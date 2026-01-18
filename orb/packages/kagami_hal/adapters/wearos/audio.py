"""WearOS Audio Adapter.

Implements audio for Wear OS using Android APIs.

Features:
- Audio playback (speaker)
- Audio recording (microphone)
- Voice recognition hooks

Created: December 13, 2025
"""

from __future__ import annotations

import logging
import os
from typing import Any

from kagami.core.boot_mode import is_test_mode

from kagami_hal.data_types import AudioConfig, AudioFormat

logger = logging.getLogger(__name__)

WEAROS_AVAILABLE = "ANDROID_ARGUMENT" in os.environ or os.environ.get("KAGAMI_PLATFORM") == "wearos"


class WearOSAudio:
    """Wear OS audio adapter.

    Provides:
    - Audio playback
    - Audio recording
    - Volume control
    """

    def __init__(self):
        """Initialize WearOS audio adapter."""
        self._audio_manager: Any = None
        self._media_player: Any = None
        self._audio_record: Any = None
        self._initialized = False
        self._volume: float = 0.5
        self._config: AudioConfig | None = None

    async def initialize(self, config: AudioConfig | None = None) -> bool:
        """Initialize audio adapter."""
        if not WEAROS_AVAILABLE:
            if is_test_mode():
                logger.info("WearOS audio not available, gracefully degrading")
                return False
            raise RuntimeError("WearOS audio only available on Wear OS")

        try:
            from jnius import autoclass

            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            Context = autoclass("android.content.Context")

            activity = PythonActivity.mActivity
            self._audio_manager = activity.getSystemService(Context.AUDIO_SERVICE)

            self._config = config or AudioConfig(
                sample_rate=16000,
                channels=1,
                format=AudioFormat.PCM_16,
                buffer_size=1024,
            )

            self._initialized = True
            logger.info("✅ WearOS audio adapter initialized")
            return True

        except ImportError as e:
            logger.error(f"Pyjnius not available: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize WearOS audio: {e}", exc_info=True)
            return False

    async def shutdown(self) -> None:
        """Shutdown audio adapter."""
        if self._media_player:
            try:
                self._media_player.release()
            except Exception:
                pass
            self._media_player = None

        if self._audio_record:
            try:
                self._audio_record.stop()
                self._audio_record.release()
            except Exception:
                pass
            self._audio_record = None

        self._initialized = False
        logger.info("✅ WearOS audio adapter shutdown")

    async def play(self, buffer: bytes) -> None:
        """Play audio buffer."""
        if not self._initialized:
            raise RuntimeError("Audio adapter not initialized")

        try:
            from jnius import autoclass

            AudioTrack = autoclass("android.media.AudioTrack")
            AudioManager = autoclass("android.media.AudioManager")
            AudioFormat = autoclass("android.media.AudioFormat")

            # Create AudioTrack for playback
            sample_rate = self._config.sample_rate if self._config else 16000
            channel_config = (
                AudioFormat.CHANNEL_OUT_MONO
                if (self._config and self._config.channels == 1)
                else AudioFormat.CHANNEL_OUT_STEREO
            )
            audio_format = AudioFormat.ENCODING_PCM_16BIT

            buffer_size = AudioTrack.getMinBufferSize(sample_rate, channel_config, audio_format)

            track = AudioTrack(
                AudioManager.STREAM_MUSIC,
                sample_rate,
                channel_config,
                audio_format,
                buffer_size,
                AudioTrack.MODE_STREAM,
            )

            track.play()
            track.write(buffer, 0, len(buffer))
            track.stop()
            track.release()

            logger.debug(f"Played audio: {len(buffer)} bytes")

        except Exception as e:
            logger.error(f"Failed to play audio: {e}")

    async def record(self, duration_ms: int) -> bytes:
        """Record audio from microphone."""
        if not self._initialized:
            raise RuntimeError("Audio adapter not initialized")

        try:
            import asyncio

            from jnius import autoclass

            AudioRecordClass = autoclass("android.media.AudioRecord")
            MediaRecorder = autoclass("android.media.MediaRecorder")
            AudioFormatClass = autoclass("android.media.AudioFormat")

            sample_rate = self._config.sample_rate if self._config else 16000
            channel_config = AudioFormatClass.CHANNEL_IN_MONO
            audio_format = AudioFormatClass.ENCODING_PCM_16BIT

            buffer_size = AudioRecordClass.getMinBufferSize(
                sample_rate, channel_config, audio_format
            )

            recorder = AudioRecordClass(
                MediaRecorder.AudioSource.MIC,
                sample_rate,
                channel_config,
                audio_format,
                buffer_size,
            )

            # Calculate total bytes to record
            bytes_per_sample = 2  # 16-bit
            samples_per_second = sample_rate
            total_samples = int((duration_ms / 1000.0) * samples_per_second)
            total_bytes = total_samples * bytes_per_sample

            # Record
            recorded_data = bytearray()
            buffer = bytearray(buffer_size)

            recorder.startRecording()

            while len(recorded_data) < total_bytes:
                read = recorder.read(buffer, 0, buffer_size)
                if read > 0:
                    recorded_data.extend(buffer[:read])
                await asyncio.sleep(0.01)

            recorder.stop()
            recorder.release()

            logger.debug(f"Recorded {len(recorded_data)} bytes")
            return bytes(recorded_data[:total_bytes])

        except Exception as e:
            logger.error(f"Failed to record audio: {e}")
            return b""

    async def set_volume(self, level: float) -> None:
        """Set playback volume."""
        self._volume = max(0.0, min(1.0, level))

        try:
            if self._audio_manager:
                from jnius import autoclass

                AudioManager = autoclass("android.media.AudioManager")
                max_vol = self._audio_manager.getStreamMaxVolume(AudioManager.STREAM_MUSIC)
                target_vol = int(self._volume * max_vol)
                self._audio_manager.setStreamVolume(AudioManager.STREAM_MUSIC, target_vol, 0)

            logger.debug(f"Volume set to {self._volume:.0%}")

        except Exception as e:
            logger.error(f"Failed to set volume: {e}")

    async def get_volume(self) -> float:
        """Get current volume."""
        try:
            if self._audio_manager:
                from jnius import autoclass

                AudioManager = autoclass("android.media.AudioManager")
                current = self._audio_manager.getStreamVolume(AudioManager.STREAM_MUSIC)
                max_vol = self._audio_manager.getStreamMaxVolume(AudioManager.STREAM_MUSIC)
                self._volume = current / max_vol if max_vol > 0 else 0.5

        except Exception:
            pass

        return self._volume

    # =========================================================================
    # WearOS-Specific Methods
    # =========================================================================

    async def start_voice_recognition(self) -> str | None:
        """Start voice recognition.

        Returns:
            Recognized text or None if cancelled/failed
        """
        try:
            from jnius import autoclass

            Intent = autoclass("android.content.Intent")
            RecognizerIntent = autoclass("android.speech.RecognizerIntent")

            intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
            intent.putExtra(
                RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                RecognizerIntent.LANGUAGE_MODEL_FREE_FORM,
            )

            # Would start activity for result
            # Placeholder - actual implementation needs activity result handling
            logger.debug("Voice recognition requested")
            return None

        except Exception as e:
            logger.error(f"Failed to start voice recognition: {e}")
            return None

    @property
    def has_speaker(self) -> bool:
        """Check if device has speaker."""
        try:
            if self._audio_manager:
                from jnius import autoclass

                PackageManager = autoclass("android.content.pm.PackageManager")
                PythonActivity = autoclass("org.kivy.android.PythonActivity")

                activity = PythonActivity.mActivity
                pm = activity.getPackageManager()
                return pm.hasSystemFeature(PackageManager.FEATURE_AUDIO_OUTPUT)
        except Exception:
            pass
        return True  # Most Wear OS devices have speakers

    @property
    def has_microphone(self) -> bool:
        """Check if device has microphone."""
        return True  # All Wear OS devices have microphones
