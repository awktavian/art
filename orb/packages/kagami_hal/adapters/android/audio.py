"""Android Audio Adapter using AudioTrack/AudioRecord via JNI.

Implements AudioController for Android using Pyjnius (JNI).

Supports:
- AudioTrack for playback
- AudioRecord for recording
- AudioManager for volume control

Created: November 10, 2025
Updated: December 7, 2025 - Full JNI implementation (no stubs)
"""

from __future__ import annotations

import logging
import os
from typing import Any

from kagami.core.boot_mode import is_test_mode

from kagami_hal.audio_controller import AudioController
from kagami_hal.data_types import AudioConfig, AudioFormat

logger = logging.getLogger(__name__)

ANDROID_AVAILABLE = "ANDROID_ARGUMENT" in os.environ or "ANDROID_PRIVATE" in os.environ

JNI_AVAILABLE = False
AudioTrack: Any = None
AudioRecord: Any = None
AudioManager: Any = None
AudioFormat_Android: Any = None
PythonActivity: Any = None
Context: Any = None

if ANDROID_AVAILABLE:
    try:
        from jnius import autoclass

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Context = autoclass("android.content.Context")
        AudioTrack = autoclass("android.media.AudioTrack")
        AudioRecord = autoclass("android.media.AudioRecord")
        AudioManager = autoclass("android.media.AudioManager")
        AudioFormat_Android = autoclass("android.media.AudioFormat")
        JNI_AVAILABLE = True
    except ImportError:
        logger.warning("Pyjnius not available for Android audio")


class AndroidAudio(AudioController):
    """Android audio implementation using JNI AudioTrack/AudioRecord."""

    def __init__(self):
        """Initialize Android audio."""
        self._config: AudioConfig | None = None
        self._volume: float = 0.7
        self._audio_track: Any = None
        self._audio_record: Any = None
        self._audio_manager: Any = None
        self._stream_type: int = 3  # STREAM_MUSIC

    async def initialize(self, config: AudioConfig) -> bool:
        """Initialize audio with config."""
        if not ANDROID_AVAILABLE:
            if is_test_mode():
                logger.info("Android audio not available (wrong platform), gracefully degrading")
                return False
            raise RuntimeError("Android audio only available on Android")

        if not JNI_AVAILABLE:
            if is_test_mode():
                logger.info("Pyjnius not available, gracefully degrading")
                return False
            raise RuntimeError(
                "Pyjnius not available. Ensure you're running on Android with Pyjnius installed."
            )

        try:
            activity = PythonActivity.mActivity

            # Get AudioManager for volume control
            self._audio_manager = activity.getSystemService(Context.AUDIO_SERVICE)

            # Determine channel config
            channel_config = (
                AudioFormat_Android.CHANNEL_OUT_STEREO
                if config.channels == 2
                else AudioFormat_Android.CHANNEL_OUT_MONO
            )

            # Determine encoding
            if config.format == AudioFormat.PCM_16:
                encoding = AudioFormat_Android.ENCODING_PCM_16BIT
            elif config.format == AudioFormat.PCM_32:
                encoding = AudioFormat_Android.ENCODING_PCM_32BIT
            elif config.format == AudioFormat.FLOAT_32:
                encoding = AudioFormat_Android.ENCODING_PCM_FLOAT
            else:
                encoding = AudioFormat_Android.ENCODING_PCM_16BIT

            # Calculate buffer size
            min_buffer = AudioTrack.getMinBufferSize(config.sample_rate, channel_config, encoding)
            buffer_size = max(min_buffer, config.buffer_size * config.channels * 2)

            # Create AudioTrack
            self._audio_track = AudioTrack(
                self._stream_type,  # STREAM_MUSIC
                config.sample_rate,
                channel_config,
                encoding,
                buffer_size,
                AudioTrack.MODE_STREAM,
            )

            # Create AudioRecord for recording
            record_channel = (
                AudioFormat_Android.CHANNEL_IN_STEREO
                if config.channels == 2
                else AudioFormat_Android.CHANNEL_IN_MONO
            )
            record_min_buffer = AudioRecord.getMinBufferSize(
                config.sample_rate, record_channel, encoding
            )

            self._audio_record = AudioRecord(
                1,  # AUDIO_SOURCE_MIC
                config.sample_rate,
                record_channel,
                encoding,
                max(record_min_buffer, config.buffer_size * config.channels * 2),
            )

            self._config = config

            logger.info(
                f"✅ Android audio initialized: {config.sample_rate}Hz, "
                f"{config.channels}ch, {config.format.value}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Android audio: {e}", exc_info=True)
            return False

    async def play(self, buffer: bytes) -> None:
        """Play audio buffer via AudioTrack."""
        if not self._audio_track:
            raise RuntimeError("Audio not initialized")

        try:
            # Start playback if not already playing
            if self._audio_track.getPlayState() != AudioTrack.PLAYSTATE_PLAYING:
                self._audio_track.play()

            # Write buffer to AudioTrack
            # Convert bytes to Java byte array
            from jnius import cast

            byte_array = cast("byte[]", buffer)
            written = self._audio_track.write(byte_array, 0, len(buffer))

            if written < 0:
                logger.error(f"AudioTrack write error: {written}")

        except Exception as e:
            logger.error(f"Playback error: {e}")
            raise

    async def record(self, duration_ms: int) -> bytes:
        """Record audio via AudioRecord."""
        if not self._audio_record or not self._config:
            raise RuntimeError("Audio not initialized")

        try:
            # Calculate buffer size for duration
            bytes_per_sample = 2 if self._config.format == AudioFormat.PCM_16 else 4
            total_bytes = int(
                (duration_ms / 1000)
                * self._config.sample_rate
                * self._config.channels
                * bytes_per_sample
            )

            # Start recording
            self._audio_record.startRecording()

            # Read data
            import array

            from jnius import cast

            buffer = array.array("b", [0] * total_bytes)
            byte_array = cast("byte[]", buffer.tobytes())

            read_bytes = self._audio_record.read(byte_array, 0, total_bytes)

            # Stop recording
            self._audio_record.stop()

            if read_bytes < 0:
                logger.error(f"AudioRecord read error: {read_bytes}")
                return b""

            # Convert back to Python bytes
            return bytes(byte_array[:read_bytes])

        except Exception as e:
            logger.error(f"Recording error: {e}")
            return b""

    async def set_volume(self, level: float) -> None:
        """Set volume via AudioManager."""
        if not (0.0 <= level <= 1.0):
            raise ValueError("Volume must be between 0.0 and 1.0")

        self._volume = level

        if self._audio_manager:
            try:
                max_volume = self._audio_manager.getStreamMaxVolume(self._stream_type)
                target_volume = int(level * max_volume)
                self._audio_manager.setStreamVolume(
                    self._stream_type,
                    target_volume,
                    0,  # No flags
                )
                logger.debug(f"Volume set to {level:.1%}")
            except Exception as e:
                logger.warning(f"Failed to set volume: {e}")

    async def get_volume(self) -> float:
        """Get current volume from AudioManager."""
        if self._audio_manager:
            try:
                current = self._audio_manager.getStreamVolume(self._stream_type)
                max_vol = self._audio_manager.getStreamMaxVolume(self._stream_type)
                if max_vol > 0:
                    return current / max_vol
            except Exception:
                pass
        return self._volume

    async def shutdown(self) -> None:
        """Shutdown audio."""
        if self._audio_track:
            try:
                self._audio_track.stop()
                self._audio_track.release()
            except Exception:
                pass
            self._audio_track = None

        if self._audio_record:
            try:
                self._audio_record.stop()
                self._audio_record.release()
            except Exception:
                pass
            self._audio_record = None

        logger.info("✅ Android audio shutdown")
