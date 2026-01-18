"""Wake Word Detection for HAL.

Integrates Porcupine wake word detection into the Hardware Abstraction Layer.
Provides wake word events through the HAL sensor interface.

Configuration:
    Requires PICOVOICE_ACCESS_KEY environment variable.
    Get free key at: https://console.picovoice.ai/

Created: December 30, 2025
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from kagami_hal.data_types import SensorReading, SensorType

logger = logging.getLogger(__name__)

# Check for core wake word module
WAKE_WORD_AVAILABLE = False
WakeWordDetector = None
WakeWordEvent = None

try:
    from kagami.core.ambient.wake_word import (
        PORCUPINE_AVAILABLE,
        PYAUDIO_AVAILABLE,
    )
    from kagami.core.ambient.wake_word import (
        WakeWordDetector as _WakeWordDetector,
    )
    from kagami.core.ambient.wake_word import (
        WakeWordEvent as _WakeWordEvent,
    )

    WakeWordDetector = _WakeWordDetector
    WakeWordEvent = _WakeWordEvent
    WAKE_WORD_AVAILABLE = PORCUPINE_AVAILABLE and PYAUDIO_AVAILABLE
except ImportError:
    logger.debug("Wake word module not available from kagami.core.ambient")
    PORCUPINE_AVAILABLE = False
    PYAUDIO_AVAILABLE = False


@dataclass
class WakeWordConfig:
    """Configuration for wake word detection."""

    # Keywords to listen for (built-in: porcupine, computer, jarvis, alexa, etc.)
    keywords: list[str] | None = None

    # Detection threshold (0.0-1.0, higher = more strict)
    threshold: float = 0.5

    # Custom keyword paths (.ppn files from Picovoice Console)
    custom_keyword_paths: list[str] | None = None


class HALWakeWord:
    """HAL Wake Word Detector.

    Wraps the core Kagami wake word detector and exposes it through
    the HAL interface for consistent hardware abstraction.

    Usage:
        from kagami_hal.wake_word import HALWakeWord, WakeWordConfig

        wake = HALWakeWord()
        config = WakeWordConfig(keywords=['computer', 'jarvis'])

        await wake.initialize(config)

        # Register callback
        wake.on_wake_word(lambda event: print(f"Detected: {event.keyword}"))

        # Start detection
        await wake.start()

        # ... later ...
        await wake.stop()
        await wake.shutdown()
    """

    def __init__(self) -> None:
        """Initialize wake word sensor."""
        self._initialized = False
        self._detector: Any | None = None
        self._callbacks: list[Callable] = []
        self._running = False
        self._config: WakeWordConfig | None = None

    @property
    def is_available(self) -> bool:
        """Check if wake word detection is available."""
        return WAKE_WORD_AVAILABLE and bool(os.environ.get("PICOVOICE_ACCESS_KEY"))

    @property
    def is_initialized(self) -> bool:
        """Check if wake word detector is initialized."""
        return self._initialized

    @property
    def is_running(self) -> bool:
        """Check if wake word detection is active."""
        return self._running

    async def initialize(self, config: WakeWordConfig | None = None) -> bool:
        """Initialize wake word detector.

        Args:
            config: Wake word configuration

        Returns:
            True if initialization succeeded
        """
        if self._initialized:
            logger.warning("Wake word detector already initialized")
            return True

        if not WAKE_WORD_AVAILABLE:
            logger.warning(
                "Wake word detection unavailable. Install: pip install pyaudio pvporcupine"
            )
            return False

        access_key = os.environ.get("PICOVOICE_ACCESS_KEY")
        if not access_key:
            logger.warning(
                "PICOVOICE_ACCESS_KEY not set. Get your free key at: https://console.picovoice.ai/"
            )
            return False

        self._config = config or WakeWordConfig()

        # Default to 'computer' if no keywords specified
        keywords = self._config.keywords or ["computer"]

        try:
            if WakeWordDetector is None:
                return False

            self._detector = WakeWordDetector(
                keywords=keywords,
                threshold=self._config.threshold,
            )

            result = await self._detector.initialize()

            if result and not self._detector._mock_mode:
                self._initialized = True
                logger.info(f"✅ HAL Wake Word initialized (keywords: {keywords})")
                return True
            else:
                logger.warning("Wake word detector running in mock mode")
                self._initialized = True  # Still usable in mock mode
                return True

        except Exception as e:
            logger.error(f"Failed to initialize wake word detector: {e}")
            return False

    def on_wake_word(self, callback: Callable) -> None:
        """Register callback for wake word detection.

        Args:
            callback: Function called with WakeWordEvent when keyword detected
        """
        self._callbacks.append(callback)

        # Also register with underlying detector
        if self._detector:
            self._detector.on_wake_word(callback)

    async def start(self) -> None:
        """Start wake word detection."""
        if not self._initialized:
            raise RuntimeError("Wake word detector not initialized")

        if self._running:
            logger.warning("Wake word detection already running")
            return

        if self._detector:
            await self._detector.start()
            self._running = True
            logger.info("🎤 HAL Wake Word detection started")

    async def stop(self) -> None:
        """Stop wake word detection."""
        if not self._running:
            return

        if self._detector:
            await self._detector.stop()

        self._running = False
        logger.info("🎤 HAL Wake Word detection stopped")

    async def read_sensor(self) -> SensorReading:
        """Read wake word as sensor (for HAL sensor interface compatibility).

        Returns:
            SensorReading with detection status
        """
        import time

        return SensorReading(
            sensor=SensorType.MICROPHONE,
            value={
                "wake_word_active": self._running,
                "keywords": self._config.keywords if self._config else [],
                "mock_mode": self._detector._mock_mode if self._detector else True,
            },
            timestamp_ms=int(time.time() * 1000),
            accuracy=1.0 if self._initialized else 0.0,
        )

    async def shutdown(self) -> None:
        """Shutdown wake word detector."""
        await self.stop()

        if self._detector:
            await self._detector.shutdown()
            self._detector = None

        self._initialized = False
        self._callbacks.clear()
        logger.info("✅ HAL Wake Word shutdown")


# Global singleton
_HAL_WAKE_WORD: HALWakeWord | None = None


def get_hal_wake_word() -> HALWakeWord:
    """Get global HAL wake word detector singleton.

    Returns:
        HALWakeWord instance (call initialize() before use)
    """
    global _HAL_WAKE_WORD

    if _HAL_WAKE_WORD is None:
        _HAL_WAKE_WORD = HALWakeWord()

    return _HAL_WAKE_WORD


async def initialize_hal_wake_word(
    config: WakeWordConfig | None = None,
) -> HALWakeWord:
    """Initialize and return global HAL wake word detector.

    Args:
        config: Wake word configuration

    Returns:
        Initialized HALWakeWord instance
    """
    wake = get_hal_wake_word()
    await wake.initialize(config)
    return wake


async def shutdown_hal_wake_word() -> None:
    """Shutdown global HAL wake word detector."""
    global _HAL_WAKE_WORD

    if _HAL_WAKE_WORD is not None:
        await _HAL_WAKE_WORD.shutdown()
        _HAL_WAKE_WORD = None


__all__ = [
    "WAKE_WORD_AVAILABLE",
    "HALWakeWord",
    "WakeWordConfig",
    "get_hal_wake_word",
    "initialize_hal_wake_word",
    "shutdown_hal_wake_word",
]
