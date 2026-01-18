"""WatchOS Power Adapter.

Implements power management for Apple Watch using WatchKit.

Features:
- Battery monitoring
- Low Power Mode detection
- Background task scheduling
- Extended runtime sessions

Created: December 13, 2025
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

from kagami.core.boot_mode import is_test_mode

from kagami_hal.data_types import (
    BatteryStatus,
    PowerMode,
    PowerStats,
    SleepMode,
)

logger = logging.getLogger(__name__)

WATCHOS_AVAILABLE = sys.platform == "darwin" and os.environ.get("KAGAMI_PLATFORM") == "watchos"


class WatchOSPower:
    """Apple Watch power management adapter.

    Provides:
    - Battery status monitoring
    - Low Power Mode detection
    - Extended runtime session management
    """

    def __init__(self):
        """Initialize WatchOS power adapter."""
        self._device: Any = None
        self._extended_session: Any = None
        self._initialized = False

    async def initialize(self, config: Any | None = None) -> bool:
        """Initialize power monitoring."""
        if not WATCHOS_AVAILABLE:
            if is_test_mode():
                logger.info("WatchOS power not available, gracefully degrading")
                return False
            raise RuntimeError("WatchOS power only available on Apple Watch")

        try:
            from WatchKit import WKInterfaceDevice

            self._device = WKInterfaceDevice.currentDevice()
            self._device.setBatteryMonitoringEnabled_(True)

            self._initialized = True
            logger.info("✅ WatchOS power adapter initialized")
            return True

        except ImportError as e:
            logger.error(f"WatchKit not available: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize WatchOS power: {e}", exc_info=True)
            return False

    async def shutdown(self) -> None:
        """Shutdown power monitoring."""
        if self._extended_session:
            self._extended_session.invalidate()
            self._extended_session = None

        self._initialized = False
        logger.info("✅ WatchOS power adapter shutdown")

    async def get_battery_status(self) -> BatteryStatus:
        """Get current battery status."""
        if not self._device:
            raise RuntimeError("Power adapter not initialized")

        level = self._device.batteryLevel()
        state = self._device.batteryState()

        # Battery states: 0=unknown, 1=unplugged, 2=charging, 3=full
        charging = state == 2
        plugged = state in (2, 3)

        # Estimate time remaining (rough estimate based on typical usage)
        time_remaining = None
        if not charging and level > 0:
            # Apple Watch typically lasts ~18 hours
            time_remaining = int(level * 18 * 60)  # minutes

        return BatteryStatus(
            level=level * 100 if level >= 0 else 100.0,
            voltage=3.8,  # Typical Li-ion voltage
            charging=charging,
            plugged=plugged,
            time_remaining_minutes=time_remaining,
            temperature_c=None,  # Not exposed on watchOS
        )

    async def get_power_mode(self) -> PowerMode:
        """Get current power mode."""
        try:
            # Check if Low Power Mode is enabled
            from Foundation import NSProcessInfo

            info = NSProcessInfo.processInfo()
            if info.isLowPowerModeEnabled():
                return PowerMode.SAVER

            # Check battery level for critical mode
            if self._device:
                level = self._device.batteryLevel()
                if level >= 0 and level < 0.1:
                    return PowerMode.CRITICAL
                elif level < 0.2:
                    return PowerMode.SAVER

            return PowerMode.BALANCED

        except Exception:
            return PowerMode.BALANCED

    async def set_power_mode(self, mode: PowerMode) -> None:
        """Set power mode.

        Note: On watchOS, we can't directly set Low Power Mode,
        but we can adjust our own behavior.
        """
        logger.info(f"Power mode set to {mode.value} (advisory)")
        # Adjust internal behavior based on mode
        # The ambient system should respond to this

    async def set_cpu_frequency(self, freq_mhz: int) -> None:
        """Set CPU frequency (not available on watchOS)."""
        logger.debug("CPU frequency control not available on watchOS")

    async def enter_sleep(self, mode: SleepMode, duration_ms: int | None = None) -> None:
        """Enter sleep mode.

        On watchOS, we request the system to allow sleep rather than forcing it.
        """
        logger.debug(f"Sleep request: {mode.value}, duration={duration_ms}ms")
        # watchOS manages sleep automatically

    async def get_power_stats(self) -> PowerStats:
        """Get power consumption statistics."""
        # watchOS doesn't expose detailed power stats
        # Return estimates based on typical Apple Watch consumption
        return PowerStats(
            current_watts=0.3,  # ~300mW typical
            avg_watts=0.25,
            peak_watts=1.0,  # During workout with GPS
            total_wh=0.0,  # Not tracked
        )

    # =========================================================================
    # WatchOS-Specific Methods
    # =========================================================================

    async def start_extended_runtime_session(self, reason: str = "smart_alarm") -> bool:
        """Start an extended runtime session.

        Extended runtime sessions allow the app to continue running
        in the background for specific purposes:
        - smart_alarm: Wake user at optimal sleep phase
        - workout: Continuous health monitoring
        - mindfulness: Breathing/meditation sessions
        - physical_therapy: Exercise tracking

        Args:
            reason: Reason for extended runtime

        Returns:
            True if session started
        """
        try:
            from WatchKit import WKExtendedRuntimeSession

            if self._extended_session:
                self._extended_session.invalidate()

            self._extended_session = WKExtendedRuntimeSession.alloc().init()

            # Map reason to session type for logging
            # Note: WatchKit sessions don't take type param in start()
            _session_type = 0  # Default
            if reason == "smart_alarm":
                _session_type = 1  # WKExtendedRuntimeSessionInvalidationReasonDone
            elif reason == "workout":
                _session_type = 2
            _ = _session_type  # Silence unused warning; type used for documentation

            self._extended_session.start()
            logger.info(f"✅ Extended runtime session started: {reason}")
            return True

        except Exception as e:
            logger.error(f"Failed to start extended runtime: {e}")
            return False

    async def stop_extended_runtime_session(self) -> None:
        """Stop the extended runtime session."""
        if self._extended_session:
            self._extended_session.invalidate()
            self._extended_session = None
            logger.info("✅ Extended runtime session stopped")

    @property
    def is_low_power_mode(self) -> bool:
        """Check if Low Power Mode is enabled."""
        try:
            from Foundation import NSProcessInfo

            return NSProcessInfo.processInfo().isLowPowerModeEnabled()
        except Exception:
            return False

    @property
    def is_water_lock_enabled(self) -> bool:
        """Check if Water Lock is enabled."""
        try:
            if self._device:
                return self._device.waterResistanceRating() > 0
        except Exception:
            pass
        return False
