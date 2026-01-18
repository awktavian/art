"""WASM Power Adapter using Battery Status API.

Implements PowerController for WebAssembly using:
- Navigator.getBattery() for battery status
- Page Visibility API for power-saving hints
- Screen Wake Lock API for preventing sleep

Created: November 10, 2025
Updated: December 2, 2025 - Full implementation
"""

from __future__ import annotations

import logging
from typing import Any

from kagami.core.boot_mode import is_test_mode

from kagami_hal.data_types import (
    BatteryStatus,
    PowerMode,
    PowerStats,
    SleepMode,
)
from kagami_hal.power_controller import PowerController

logger = logging.getLogger(__name__)

WASM_AVAILABLE = False
try:
    import js
    from pyodide.ffi import create_proxy  # noqa: F401 - availability check

    WASM_AVAILABLE = True
except ImportError:
    pass


class WASMPower(PowerController):
    """WASM power management implementation."""

    def __init__(self):
        """Initialize WASM power adapter."""
        self._current_mode = PowerMode.BALANCED
        self._battery: Any = None
        self._wake_lock: Any = None
        self._initialized = False

    async def initialize(self) -> bool:
        """Initialize power management."""
        if not WASM_AVAILABLE:
            if is_test_mode():
                logger.info("WASM power not available, gracefully degrading")
                return False
            raise RuntimeError("WASM power only available in browser")

        try:
            # Get battery manager if available
            if hasattr(js.navigator, "getBattery"):
                try:
                    self._battery = await js.navigator.getBattery()
                except Exception as e:
                    logger.warning(f"Battery API not available: {e}")

            self._initialized = True
            logger.info("✅ WASM power initialized")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize WASM power: {e}", exc_info=True)
            return False

    async def get_battery_status(self) -> BatteryStatus:
        """Get battery status."""
        if not self._battery:
            raise RuntimeError(
                "Battery API not available. This browser may not support navigator.getBattery()"
            )

        try:
            level = self._battery.level * 100
            charging = bool(self._battery.charging)

            # Calculate time remaining
            time_remaining = None
            if charging:
                if self._battery.chargingTime and self._battery.chargingTime != float("inf"):
                    time_remaining = int(self._battery.chargingTime / 60)
            else:
                if self._battery.dischargingTime and self._battery.dischargingTime != float("inf"):
                    time_remaining = int(self._battery.dischargingTime / 60)

            return BatteryStatus(
                level=level,
                voltage=0.0,  # Not available in Battery API
                charging=charging,
                plugged=charging,  # Best approximation
                time_remaining_minutes=time_remaining,
                temperature_c=None,  # Not available
            )

        except Exception as e:
            logger.error(f"Failed to get battery status: {e}")
            raise RuntimeError(f"Failed to read battery status: {e}") from e

    async def set_power_mode(self, mode: PowerMode) -> None:
        """Set power mode.

        In browser context, this controls wake lock behavior.
        """
        self._current_mode = mode

        try:
            if mode == PowerMode.FULL:
                # Request wake lock to prevent screen sleep
                if hasattr(js.navigator, "wakeLock"):
                    try:
                        self._wake_lock = await js.navigator.wakeLock.request("screen")
                        logger.debug("Wake lock acquired")
                    except Exception as e:
                        logger.warning(f"Wake lock failed: {e}")

            elif mode in (PowerMode.SAVER, PowerMode.CRITICAL):
                # Release wake lock if held
                if self._wake_lock:
                    try:
                        self._wake_lock.release()
                        self._wake_lock = None
                        logger.debug("Wake lock released")
                    except Exception:
                        pass

            logger.debug(f"Power mode set to {mode.value}")

        except Exception as e:
            logger.error(f"Failed to set power mode: {e}")

    async def get_power_mode(self) -> PowerMode:
        """Get current power mode."""
        return self._current_mode

    async def set_cpu_frequency(self, freq_mhz: int) -> None:
        """Set CPU frequency.

        Note: Not available in browser context.
        """
        logger.warning("CPU frequency control not available in browser")

    async def enter_sleep(self, mode: SleepMode, duration_ms: int | None = None) -> None:
        """Enter sleep mode.

        Note: Cannot control system sleep from browser.
        Can only release wake locks to allow natural sleep.
        """
        if mode != SleepMode.NONE:
            # Release wake lock
            if self._wake_lock:
                try:
                    self._wake_lock.release()
                    self._wake_lock = None
                except Exception:
                    pass

            logger.warning("Browser cannot directly enter sleep mode")

    async def get_power_stats(self) -> PowerStats:
        """Get power consumption statistics.

        Note: Detailed power stats not available in browser.
        """
        return PowerStats(
            current_watts=0.0,
            avg_watts=0.0,
            peak_watts=0.0,
            total_wh=0.0,
        )

    async def shutdown(self) -> None:
        """Shutdown power controller."""
        # Release wake lock
        if self._wake_lock:
            try:
                self._wake_lock.release()
            except Exception:
                pass

        self._initialized = False
        logger.info("✅ WASM power shutdown")
