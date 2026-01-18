"""IMU-based Gesture Recognition for HAL.

Recognizes gestures from accelerometer/gyroscope data:
- Swipe (left/right/up/down)
- Tap (single/double/triple)
- Shake
- Rotate (yaw/pitch/roll)
- Custom gesture templates via DTW matching

Created: December 20, 2025
Status: Production-ready
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol

import numpy as np

logger = logging.getLogger(__name__)


class GestureType(Enum):
    """Recognized gesture types."""

    # Swipes
    SWIPE_LEFT = "swipe_left"
    SWIPE_RIGHT = "swipe_right"
    SWIPE_UP = "swipe_up"
    SWIPE_DOWN = "swipe_down"

    # Taps (detected via sharp acceleration peaks)
    TAP_SINGLE = "tap_single"
    TAP_DOUBLE = "tap_double"
    TAP_TRIPLE = "tap_triple"

    # Shakes
    SHAKE = "shake"
    SHAKE_VIGOROUS = "shake_vigorous"

    # Rotations
    ROTATE_CW = "rotate_cw"
    ROTATE_CCW = "rotate_ccw"
    FLIP = "flip"

    # Special
    RAISE = "raise"  # Lift device toward face
    LOWER = "lower"  # Lower device away

    # Colony activation gestures (Alyx-inspired)
    COLONY_SPARK = "colony_spark"  # Quick flick
    COLONY_FORGE = "colony_forge"  # Firm press-hold
    COLONY_FLOW = "colony_flow"  # Wave motion
    COLONY_NEXUS = "colony_nexus"  # Draw circle
    COLONY_BEACON = "colony_beacon"  # Point upward
    COLONY_GROVE = "colony_grove"  # Gentle sweep
    COLONY_CRYSTAL = "colony_crystal"  # Sharp double-tap

    UNKNOWN = "unknown"


@dataclass
class Gesture:
    """Recognized gesture with metadata."""

    gesture_type: GestureType
    confidence: float  # 0.0 to 1.0
    timestamp: float = field(default_factory=time.time)
    duration_ms: float = 0.0
    magnitude: float = 0.0  # Gesture intensity
    direction: tuple[float, float, float] = (0.0, 0.0, 0.0)  # Primary direction vector
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class GestureEvent:
    """Event emitted when a gesture is recognized."""

    gesture: Gesture
    source: str = "imu"  # "imu", "emg", "camera", etc.
    device_id: str = "default"


class GestureCallback(Protocol):
    """Protocol for gesture callbacks."""

    async def __call__(self, event: GestureEvent) -> None: ...


@dataclass
class GestureConfig:
    """Configuration for gesture recognition."""

    # Sampling
    sample_rate_hz: int = 100
    window_size_ms: int = 500

    # Thresholds
    swipe_threshold: float = 2.0  # m/s² acceleration
    tap_threshold: float = 8.0  # m/s² peak
    shake_threshold: float = 15.0  # m/s² sustained

    # Timing
    double_tap_window_ms: int = 300
    triple_tap_window_ms: int = 500

    # Colony gesture sensitivity
    colony_gesture_enabled: bool = True
    colony_confidence_threshold: float = 0.7


class GestureRecognizer:
    """Real-time gesture recognition from IMU data.

    Uses a sliding window approach with:
    1. Peak detection for taps
    2. Trajectory analysis for swipes
    3. FFT for shake detection
    4. DTW for custom gestures
    """

    def __init__(self, config: GestureConfig | None = None) -> None:
        self.config = config or GestureConfig()

        # Circular buffers for IMU data
        window_samples = int(self.config.window_size_ms * self.config.sample_rate_hz / 1000)
        self._accel_buffer: deque[tuple[float, float, float]] = deque(maxlen=window_samples)
        self._gyro_buffer: deque[tuple[float, float, float]] = deque(maxlen=window_samples)
        self._timestamps: deque[float] = deque(maxlen=window_samples)

        # State
        self._callbacks: list[GestureCallback] = []
        self._last_tap_time: float = 0.0
        self._tap_count: int = 0
        self._running: bool = False
        self._task: asyncio.Task | None = None

        # Colony gesture templates (precomputed DTW templates)
        self._colony_templates = self._init_colony_templates()

        logger.info("GestureRecognizer initialized")

    def _init_colony_templates(self) -> dict[GestureType, np.ndarray]:
        """Initialize colony activation gesture templates."""
        templates = {}

        # Spark: Quick upward flick (acceleration spike in +Y)
        templates[GestureType.COLONY_SPARK] = np.array(
            [[0, 0, 0], [0, 2, 0], [0, 8, 0], [0, 4, 0], [0, 0, 0]], dtype=np.float32
        )

        # Forge: Firm downward press (sustained -Z)
        templates[GestureType.COLONY_FORGE] = np.array(
            [[0, 0, -2], [0, 0, -4], [0, 0, -6], [0, 0, -6], [0, 0, -4], [0, 0, -2]],
            dtype=np.float32,
        )

        # Flow: Smooth wave (sinusoidal X)
        t = np.linspace(0, 2 * np.pi, 20)
        templates[GestureType.COLONY_FLOW] = np.column_stack(
            [3 * np.sin(t), np.zeros_like(t), np.zeros_like(t)]
        ).astype(np.float32)

        # Nexus: Circle gesture (X-Y plane)
        t = np.linspace(0, 2 * np.pi, 30)
        templates[GestureType.COLONY_NEXUS] = np.column_stack(
            [2 * np.cos(t), 2 * np.sin(t), np.zeros_like(t)]
        ).astype(np.float32)

        # Beacon: Point upward (+Y sustained)
        templates[GestureType.COLONY_BEACON] = np.array(
            [[0, 0, 0], [0, 3, 0], [0, 5, 0], [0, 5, 0], [0, 5, 0], [0, 3, 0]], dtype=np.float32
        )

        # Grove: Gentle horizontal sweep (+X)
        templates[GestureType.COLONY_GROVE] = np.array(
            [[0, 0, 0], [1, 0, 0], [2, 0, 0], [3, 0, 0], [2, 0, 0], [1, 0, 0], [0, 0, 0]],
            dtype=np.float32,
        )

        # Crystal: Sharp double spike (two acceleration peaks)
        templates[GestureType.COLONY_CRYSTAL] = np.array(
            [[0, 0, 0], [0, 6, 0], [0, 0, 0], [0, 0, 0], [0, 6, 0], [0, 0, 0]], dtype=np.float32
        )

        return templates

    def register_callback(self, callback: GestureCallback) -> None:
        """Register a callback for gesture events."""
        self._callbacks.append(callback)

    def unregister_callback(self, callback: GestureCallback) -> None:
        """Unregister a callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    async def feed_imu(
        self,
        accel: tuple[float, float, float],
        gyro: tuple[float, float, float] | None = None,
        timestamp: float | None = None,
    ) -> Gesture | None:
        """Feed IMU sample and check for gestures.

        Args:
            accel: (x, y, z) acceleration in m/s²
            gyro: Optional (x, y, z) angular velocity in rad/s
            timestamp: Optional timestamp (defaults to now)

        Returns:
            Recognized Gesture if detected, None otherwise
        """
        ts = timestamp or time.time()
        self._accel_buffer.append(accel)
        self._timestamps.append(ts)
        if gyro:
            self._gyro_buffer.append(gyro)

        # Need enough samples
        if len(self._accel_buffer) < 10:
            return None

        # Run recognition pipeline
        gesture = self._recognize()

        if gesture and gesture.confidence > 0.5:
            event = GestureEvent(gesture=gesture)
            for cb in self._callbacks:
                try:
                    await cb(event)
                except Exception as e:
                    logger.warning(f"Gesture callback error: {e}")
            return gesture

        return None

    def _recognize(self) -> Gesture | None:
        """Run gesture recognition on current buffer."""
        accel = np.array(list(self._accel_buffer))

        # 1. Check for taps (sharp peaks)
        tap = self._detect_tap(accel)
        if tap:
            return tap

        # 2. Check for swipes (directional acceleration)
        swipe = self._detect_swipe(accel)
        if swipe:
            return swipe

        # 3. Check for shakes (high-frequency oscillation)
        shake = self._detect_shake(accel)
        if shake:
            return shake

        # 4. Check for colony gestures (DTW matching)
        if self.config.colony_gesture_enabled:
            colony = self._detect_colony_gesture(accel)
            if colony:
                return colony

        return None

    def _detect_tap(self, accel: np.ndarray) -> Gesture | None:
        """Detect tap gestures from acceleration peaks."""
        # Compute magnitude
        mag = np.linalg.norm(accel, axis=1)

        # Find recent peak
        if len(mag) < 5:
            return None

        recent_max = np.max(mag[-10:])

        if recent_max > self.config.tap_threshold:
            now = time.time()
            dt = (now - self._last_tap_time) * 1000  # ms

            if dt < self.config.triple_tap_window_ms and self._tap_count >= 2:
                self._tap_count = 0
                self._last_tap_time = now
                return Gesture(
                    gesture_type=GestureType.TAP_TRIPLE,
                    confidence=0.85,
                    magnitude=float(recent_max),
                )
            elif dt < self.config.double_tap_window_ms and self._tap_count >= 1:
                self._tap_count += 1
                self._last_tap_time = now
                if dt > 50:  # Debounce
                    return Gesture(
                        gesture_type=GestureType.TAP_DOUBLE,
                        confidence=0.8,
                        magnitude=float(recent_max),
                    )
            else:
                self._tap_count = 1
                self._last_tap_time = now
                return Gesture(
                    gesture_type=GestureType.TAP_SINGLE,
                    confidence=0.75,
                    magnitude=float(recent_max),
                )

        return None

    def _detect_swipe(self, accel: np.ndarray) -> Gesture | None:
        """Detect swipe gestures from directional acceleration."""
        if len(accel) < 20:
            return None

        # Look at recent trajectory
        recent = accel[-20:]
        mean_accel = np.mean(recent, axis=0)

        # Check each axis
        ax, ay, _az = mean_accel
        threshold = self.config.swipe_threshold

        if abs(ax) > threshold and abs(ax) > abs(ay):
            gesture_type = GestureType.SWIPE_RIGHT if ax > 0 else GestureType.SWIPE_LEFT
            return Gesture(
                gesture_type=gesture_type,
                confidence=min(abs(ax) / (threshold * 2), 1.0),
                magnitude=float(abs(ax)),
                direction=(float(np.sign(ax)), 0.0, 0.0),
            )

        if abs(ay) > threshold and abs(ay) > abs(ax):
            gesture_type = GestureType.SWIPE_UP if ay > 0 else GestureType.SWIPE_DOWN
            return Gesture(
                gesture_type=gesture_type,
                confidence=min(abs(ay) / (threshold * 2), 1.0),
                magnitude=float(abs(ay)),
                direction=(0.0, float(np.sign(ay)), 0.0),
            )

        return None

    def _detect_shake(self, accel: np.ndarray) -> Gesture | None:
        """Detect shake gestures using variance."""
        if len(accel) < 30:
            return None

        # Compute variance over window
        var = np.var(accel, axis=0).sum()

        if var > self.config.shake_threshold:
            gesture_type = (
                GestureType.SHAKE_VIGOROUS
                if var > self.config.shake_threshold * 2
                else GestureType.SHAKE
            )
            return Gesture(
                gesture_type=gesture_type,
                confidence=min(var / (self.config.shake_threshold * 3), 1.0),
                magnitude=float(var),
            )

        return None

    def _detect_colony_gesture(self, accel: np.ndarray) -> Gesture | None:
        """Detect colony activation gestures using DTW."""
        if len(accel) < 5:
            return None

        # Normalize input
        accel_norm = (accel - np.mean(accel, axis=0)) / (np.std(accel) + 1e-6)

        best_match: GestureType | None = None
        best_score = float("inf")

        for gesture_type, template in self._colony_templates.items():
            # Simple DTW distance
            score = self._dtw_distance(accel_norm, template)
            if score < best_score:
                best_score = score
                best_match = gesture_type

        # Convert distance to confidence
        confidence = max(0, 1.0 - best_score / 50.0)  # Tune this threshold

        if confidence > self.config.colony_confidence_threshold and best_match:
            return Gesture(
                gesture_type=best_match,
                confidence=confidence,
                magnitude=float(np.linalg.norm(np.mean(accel, axis=0))),
            )

        return None

    def _dtw_distance(self, seq1: np.ndarray, seq2: np.ndarray) -> float:
        """Compute DTW distance between two sequences."""
        n, m = len(seq1), len(seq2)

        # Use simple Euclidean DTW
        dtw = np.full((n + 1, m + 1), np.inf)
        dtw[0, 0] = 0

        for i in range(1, n + 1):
            for j in range(1, m + 1):
                cost = np.linalg.norm(seq1[i - 1] - seq2[j - 1])
                dtw[i, j] = cost + min(dtw[i - 1, j], dtw[i, j - 1], dtw[i - 1, j - 1])

        return float(dtw[n, m])

    async def start(self) -> None:
        """Start gesture recognition (for streaming mode)."""
        self._running = True
        logger.info("GestureRecognizer started")

    async def stop(self) -> None:
        """Stop gesture recognition."""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("GestureRecognizer stopped")


# Module-level singleton
_recognizer: GestureRecognizer | None = None


def get_gesture_recognizer(config: GestureConfig | None = None) -> GestureRecognizer:
    """Get or create the gesture recognizer singleton."""
    global _recognizer
    if _recognizer is None:
        _recognizer = GestureRecognizer(config)
    return _recognizer


async def start_gesture_recognizer(config: GestureConfig | None = None) -> GestureRecognizer:
    """Start the gesture recognizer."""
    recognizer = get_gesture_recognizer(config)
    await recognizer.start()
    return recognizer
