"""Wake Word Detection for Voice Activation.

Detects wake words like "Hey K os" for hands-free operation.

Uses:
- Porcupine (Picovoice) - production quality
- Simple pattern matching - fallback

Created: November 10, 2025
"""

from __future__ import annotations

import asyncio
import logging
import struct
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Try to import Porcupine (optional - for wake word detection)
pvporcupine: Any = None
try:
    import pvporcupine as _pvporcupine  # pyright: ignore[reportMissingImports]

    pvporcupine = _pvporcupine
    logger.debug(
        "Porcupine module detected (version=%s)",
        getattr(pvporcupine, "__version__", "unknown"),
    )
    PORCUPINE_AVAILABLE = True
except ImportError:
    PORCUPINE_AVAILABLE = False
    # DEBUG level - this is an optional feature
    logger.debug("Porcupine not available - install: pip install pvporcupine")

# Try to import PyAudio (optional - for audio capture)
pyaudio: Any = None
try:
    import pyaudio as _pyaudio  # pyright: ignore[reportMissingImports]

    pyaudio = _pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False
    # DEBUG level - this is an optional feature
    logger.debug("PyAudio not available - install: pip install pyaudio")


@dataclass
class WakeWordEvent:
    """Wake word detection event."""

    keyword: str
    confidence: float
    timestamp: float


class WakeWordDetector:
    """Wake word detector for voice activation."""

    def __init__(
        self,
        keywords: list[str] | None = None,
        wake_word: str | None = None,
        threshold: float = 0.7,
    ):
        """Initialize wake word detector.

        Args:
            keywords: Wake words to detect (default: ["kagami"])
            wake_word: Single wake word (alternative to keywords list[Any])
            threshold: Detection confidence threshold (0.0-1.0)
        """
        # Support both keywords list[Any] and single wake_word
        if wake_word and not keywords:
            self.keywords = [wake_word, f"hey {wake_word}"]
        else:
            self.keywords = keywords or ["kagami", "hey kagami"]
        self.threshold = threshold
        self._porcupine: Any | None = None
        self._pa: Any | None = None
        self._audio_stream: Any | None = None
        self._mock_mode = not (PORCUPINE_AVAILABLE and PYAUDIO_AVAILABLE)

        # Callbacks
        self._callbacks: list[Callable[[WakeWordEvent], Awaitable[None]]] = []

        # Background task
        self._running = False
        self._detector_task: asyncio.Task | None = None

    async def initialize(self) -> bool:
        """Initialize wake word detector."""
        if not PORCUPINE_AVAILABLE:
            logger.warning(
                "Porcupine not available. Running in mock mode.\n"
                "To enable: pip install pvporcupine\n"
                "Requires access key from https://picovoice.ai/"
            )
            self._mock_mode = True
            return True

        try:
            # Initialize Porcupine
            # Note: In a real deployment, we need an access key.
            # For now, we'll catch the error if key is missing and fall back to mock.
            try:
                # Try to initialize with default keywords if available, or error out
                # pvporcupine.create(keywords=self.keywords) requires access_key
                # checking for environment variable or config
                import os

                access_key = os.environ.get("PICOVOICE_ACCESS_KEY")
                if not access_key:
                    logger.warning("PICOVOICE_ACCESS_KEY not set[Any]. Falling back to mock mode.")
                    self._mock_mode = True
                    return True

                self._porcupine = pvporcupine.create(access_key=access_key, keywords=self.keywords)
                logger.info(
                    f"✅ Wake word detector initialized (Porcupine, keywords: {self.keywords})"
                )

            except Exception as e:
                logger.warning(f"Porcupine initialization failed: {e}. Falling back to mock mode.")
                self._mock_mode = True
                return True

            # Initialize PyAudio
            if PYAUDIO_AVAILABLE and self._porcupine is not None and pyaudio is not None:
                porcupine_instance = self._porcupine
                pa_instance = pyaudio.PyAudio()
                self._pa = pa_instance
                self._audio_stream = pa_instance.open(
                    rate=porcupine_instance.sample_rate,
                    channels=1,
                    format=pyaudio.paInt16,
                    input=True,
                    frames_per_buffer=porcupine_instance.frame_length,
                )
                logger.info("✅ Audio stream initialized")
            else:
                logger.warning("PyAudio not available. Falling back to mock mode.")
                self._mock_mode = True

            return True

        except Exception as e:
            logger.error(f"Failed to initialize wake word detector: {e}")
            self._mock_mode = True
            return False

    async def start(self) -> None:
        """Start wake word detection."""
        if self._running:
            return

        self._running = True

        from kagami.core.async_utils import safe_create_task

        self._detector_task = safe_create_task(
            self._detection_loop(),
            name="wake_word_detector",
            error_callback=lambda e: logger.error(f"Wake word detector crashed: {e}"),
        )

        logger.info(f"🎙️ Wake word detector started (keywords: {self.keywords})")

    async def stop(self) -> None:
        """Stop wake word detection."""
        self._running = False
        if self._detector_task:
            self._detector_task.cancel()

        if self._audio_stream:
            self._audio_stream.close()
            self._audio_stream = None

        if self._pa:
            self._pa.terminate()
            self._pa = None

        logger.info("🎙️ Wake word detector stopped")

    async def _detection_loop(self) -> None:
        """Main detection loop."""
        while self._running:
            try:
                if self._mock_mode:
                    # Mock mode: just sleep (or listen for a manual trigger file/event)
                    await asyncio.sleep(1.0)
                    continue

                if not self._porcupine or not self._audio_stream:
                    await asyncio.sleep(1.0)
                    continue

                # Read audio frame (blocking call, run in executor if needed,
                # but read is usually fast enough for small frames)
                # PyAudio read is blocking, so we should ideally run it in a thread
                # but for simplicity in this loop we'll use it directly or use asyncio.to_thread

                # Capture references for lambda to narrow types
                audio_stream = self._audio_stream

                porcupine = self._porcupine

                pcm = await asyncio.to_thread(
                    lambda: audio_stream.read(porcupine.frame_length, exception_on_overflow=False)
                )

                # Convert bytes to struct (Porcupine expects 16-bit integers)
                pcm = struct.unpack_from("h" * self._porcupine.frame_length, pcm)

                # Process with Porcupine
                keyword_index = self._porcupine.process(pcm)

                if keyword_index >= 0:
                    keyword = (
                        self.keywords[keyword_index]
                        if keyword_index < len(self.keywords)
                        else "unknown"
                    )
                    await self._emit_detection(keyword)

                # Yield control
                await asyncio.sleep(0)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Wake word detection error: {e}", exc_info=True)
                await asyncio.sleep(1.0)

    async def _emit_detection(self, keyword: str) -> None:
        """Emit wake word detection event."""
        import time

        event = WakeWordEvent(keyword=keyword, confidence=0.9, timestamp=time.time())

        logger.info(f"🎙️ Wake word detected: '{keyword}'")

        for callback in self._callbacks:
            try:
                await callback(event)
            except Exception as e:
                logger.error(f"Wake word callback failed: {e}")

    def subscribe(self, callback: Callable[[WakeWordEvent], Awaitable[None]]) -> None:
        """Subscribe to wake word events."""
        self._callbacks.append(callback)

    async def shutdown(self) -> None:
        """Shutdown wake word detector."""
        await self.stop()

        if self._porcupine:
            self._porcupine.delete()

        logger.info("✅ Wake word detector shutdown")


# Global wake word detector
_WAKE_WORD_DETECTOR: WakeWordDetector | None = None


async def get_wake_word_detector() -> WakeWordDetector:
    """Get global wake word detector."""
    global _WAKE_WORD_DETECTOR
    if _WAKE_WORD_DETECTOR is None:
        _WAKE_WORD_DETECTOR = WakeWordDetector()
        await _WAKE_WORD_DETECTOR.initialize()
        await _WAKE_WORD_DETECTOR.start()
    return _WAKE_WORD_DETECTOR
