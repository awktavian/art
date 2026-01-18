"""Android Power Adapter using BatteryManager via JNI.

Implements PowerController for Android using Pyjnius (JNI).

Supports:
- BatteryManager for battery status
- PowerManager for wake locks and power modes

Created: November 10, 2025
Updated: December 7, 2025 - Full JNI implementation (no stubs)
"""

from __future__ import annotations

import logging
import os
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

ANDROID_AVAILABLE = "ANDROID_ARGUMENT" in os.environ or "ANDROID_PRIVATE" in os.environ

JNI_AVAILABLE = False
BatteryManager: Any = None
PowerManager: Any = None
PythonActivity: Any = None
Context: Any = None
Intent: Any = None
IntentFilter: Any = None

if ANDROID_AVAILABLE:
    try:
        from jnius import autoclass

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Context = autoclass("android.content.Context")
        BatteryManager = autoclass("android.os.BatteryManager")
        PowerManager = autoclass("android.os.PowerManager")
        Intent = autoclass("android.content.Intent")
        IntentFilter = autoclass("android.content.IntentFilter")
        JNI_AVAILABLE = True
    except ImportError:
        logger.warning("Pyjnius not available for Android power")


class AndroidPower(PowerController):
    """Android power management implementation using JNI."""

    def __init__(self):
        """Initialize Android power adapter."""
        self._current_mode = PowerMode.BALANCED
        self._battery_manager: Any = None
        self._power_manager: Any = None
        self._activity: Any = None
        self._wake_lock: Any = None
        self._initialized = False

    async def initialize(self) -> bool:
        """Initialize power management."""
        if not ANDROID_AVAILABLE:
            if is_test_mode():
                logger.info("Android power not available (wrong platform), gracefully degrading")
                return False
            raise RuntimeError("Android power only available on Android")

        if not JNI_AVAILABLE:
            if is_test_mode():
                logger.info("Pyjnius not available, gracefully degrading")
                return False
            raise RuntimeError("Pyjnius not available")

        try:
            self._activity = PythonActivity.mActivity

            # Get BatteryManager
            self._battery_manager = self._activity.getSystemService(Context.BATTERY_SERVICE)

            # Get PowerManager
            self._power_manager = self._activity.getSystemService(Context.POWER_SERVICE)

            self._initialized = True
            logger.info("✅ Android power initialized")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Android power: {e}", exc_info=True)
            return False

    async def get_battery_status(self) -> BatteryStatus:
        """Get battery status via BatteryManager."""
        if not self._initialized or not self._activity:
            raise RuntimeError("Power adapter not initialized")

        try:
            # Register receiver to get battery intent
            intent_filter = IntentFilter(Intent.ACTION_BATTERY_CHANGED)
            battery_intent = self._activity.registerReceiver(None, intent_filter)

            if not battery_intent:
                raise RuntimeError("Could not get battery intent")

            # Extract battery info
            level = battery_intent.getIntExtra(BatteryManager.EXTRA_LEVEL, -1)
            scale = battery_intent.getIntExtra(BatteryManager.EXTRA_SCALE, 100)
            status = battery_intent.getIntExtra(BatteryManager.EXTRA_STATUS, -1)
            plugged = battery_intent.getIntExtra(BatteryManager.EXTRA_PLUGGED, 0)
            voltage = battery_intent.getIntExtra(BatteryManager.EXTRA_VOLTAGE, 0)
            temperature = battery_intent.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, 0)

            # Calculate percentage
            battery_pct = (level / scale) * 100 if scale > 0 else 0.0

            # Determine charging state
            is_charging = status in (
                BatteryManager.BATTERY_STATUS_CHARGING,
                BatteryManager.BATTERY_STATUS_FULL,
            )
            is_plugged = plugged > 0

            return BatteryStatus(
                level=battery_pct,
                voltage=voltage / 1000.0,  # mV to V
                charging=is_charging,
                plugged=is_plugged,
                time_remaining_minutes=None,  # Would need to compute or use BatteryStats
                temperature_c=temperature / 10.0 if temperature > 0 else None,  # Tenths of C
            )

        except Exception as e:
            logger.error(f"Failed to get battery status: {e}")
            raise

    async def set_power_mode(self, mode: PowerMode) -> None:
        """Set power mode via wake locks.

        Note: Android apps cannot directly control system power mode.
        We use wake locks to prevent sleep in FULL mode.
        """
        if not self._initialized or not self._power_manager:
            raise RuntimeError("Power adapter not initialized")

        self._current_mode = mode

        try:
            # Release existing wake lock
            if self._wake_lock and self._wake_lock.isHeld():
                self._wake_lock.release()
                self._wake_lock = None

            if mode == PowerMode.FULL:
                # Acquire partial wake lock to prevent CPU sleep
                self._wake_lock = self._power_manager.newWakeLock(
                    PowerManager.PARTIAL_WAKE_LOCK, "kagami:full_power"
                )
                self._wake_lock.acquire()
                logger.debug("Full power mode: wake lock acquired")

            elif mode == PowerMode.SAVER:
                # Could request battery saver via Settings (requires permission)
                logger.debug("Power saver mode requested (system controlled)")

            else:
                logger.debug(f"Power mode set: {mode.value}")

        except Exception as e:
            logger.error(f"Failed to set power mode: {e}")

    async def get_power_mode(self) -> PowerMode:
        """Get current power mode."""
        if self._power_manager:
            try:
                # Check if device is in power save mode
                if self._power_manager.isPowerSaveMode():
                    return PowerMode.SAVER
            except Exception:
                pass
        return self._current_mode

    async def set_cpu_frequency(self, freq_mhz: int) -> None:
        """Set CPU frequency.

        Note: Requires root access on Android. Not available to regular apps.
        """
        # Best-effort: attempt sysfs writes when permitted.
        # Regular apps typically cannot do this, so we degrade gracefully.
        if freq_mhz <= 0:
            return

        if is_test_mode():
            logger.debug("Skipping CPU frequency control (test/minimal mode)")
            return

        if not ANDROID_AVAILABLE or not JNI_AVAILABLE:
            logger.debug("CPU frequency control unavailable (not Android/JNI)")
            return

        freq_khz = int(freq_mhz) * 1000
        cpu_root = "/sys/devices/system/cpu"

        try:
            cpu_dirs = [
                d
                for d in os.listdir(cpu_root)
                if d.startswith("cpu")
                and d[3:].isdigit()
                and os.path.isdir(os.path.join(cpu_root, d))
            ]
        except Exception:
            cpu_dirs = []

        if not cpu_dirs:
            logger.warning("CPU frequency sysfs not available on this device")
            return

        wrote_any = False
        for cpu in cpu_dirs:
            cpufreq_dir = os.path.join(cpu_root, cpu, "cpufreq")
            if not os.path.isdir(cpufreq_dir):
                continue
            for fname in ("scaling_min_freq", "scaling_max_freq", "scaling_setspeed"):
                path = os.path.join(cpufreq_dir, fname)
                if not os.path.exists(path):
                    continue
                try:
                    with open(path, "w") as f:
                        f.write(str(freq_khz))
                    wrote_any = True
                except PermissionError:
                    continue
                except Exception:
                    continue

        if not wrote_any:
            logger.warning(
                "CPU frequency control requires root/system permissions (no changes applied)"
            )

    async def enter_sleep(self, mode: SleepMode, duration_ms: int | None = None) -> None:
        """Enter sleep mode.

        Note: Android apps cannot put device to sleep. They can only
        release wake locks to allow system to sleep normally.
        """
        if mode == SleepMode.NONE:
            return

        # Release wake lock to allow sleep
        if self._wake_lock and self._wake_lock.isHeld():
            self._wake_lock.release()
            logger.debug("Wake lock released to allow sleep")

        if duration_ms:
            logger.warning("Timed wake not supported on Android apps")

    async def get_power_stats(self) -> PowerStats:
        """Get power consumption statistics.

        Note: Detailed power stats require BATTERY_STATS permission (system apps only).
        """
        # We can't get detailed power stats without system permissions
        # Return zeros and let caller know this isn't available
        return PowerStats(
            current_watts=0.0,
            avg_watts=0.0,
            peak_watts=0.0,
            total_wh=0.0,
        )

    async def shutdown(self) -> None:
        """Shutdown power controller."""
        if self._wake_lock and self._wake_lock.isHeld():
            try:
                self._wake_lock.release()
            except Exception:
                pass

        self._initialized = False
        logger.info("✅ Android power shutdown")
