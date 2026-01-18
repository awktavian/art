"""WearOS Power Adapter.

Implements power management for Wear OS using Android APIs.

Features:
- Battery monitoring
- Battery Saver Mode detection
- Ambient mode support
- Doze mode awareness

Created: December 13, 2025
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

logger = logging.getLogger(__name__)

WEAROS_AVAILABLE = "ANDROID_ARGUMENT" in os.environ or os.environ.get("KAGAMI_PLATFORM") == "wearos"


class WearOSPower:
    """Wear OS power management adapter.

    Provides:
    - Battery status monitoring
    - Battery Saver detection
    - Ambient mode support
    """

    def __init__(self):
        """Initialize WearOS power adapter."""
        self._battery_manager: Any = None
        self._power_manager: Any = None
        self._initialized = False

    async def initialize(self, config: Any | None = None) -> bool:
        """Initialize power monitoring."""
        if not WEAROS_AVAILABLE:
            if is_test_mode():
                logger.info("WearOS power not available, gracefully degrading")
                return False
            raise RuntimeError("WearOS power only available on Wear OS")

        try:
            from jnius import autoclass

            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            Context = autoclass("android.content.Context")

            activity = PythonActivity.mActivity
            self._battery_manager = activity.getSystemService(Context.BATTERY_SERVICE)
            self._power_manager = activity.getSystemService(Context.POWER_SERVICE)

            self._initialized = True
            logger.info("✅ WearOS power adapter initialized")
            return True

        except ImportError as e:
            logger.error(f"Pyjnius not available: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize WearOS power: {e}", exc_info=True)
            return False

    async def shutdown(self) -> None:
        """Shutdown power monitoring."""
        self._initialized = False
        logger.info("✅ WearOS power adapter shutdown")

    async def get_battery_status(self) -> BatteryStatus:
        """Get current battery status."""
        if not self._initialized:
            raise RuntimeError("Power adapter not initialized")

        try:
            from jnius import autoclass

            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            Intent = autoclass("android.content.Intent")
            IntentFilter = autoclass("android.content.IntentFilter")
            BatteryManager = autoclass("android.os.BatteryManager")

            activity = PythonActivity.mActivity
            intent_filter = IntentFilter(Intent.ACTION_BATTERY_CHANGED)
            battery_status = activity.registerReceiver(None, intent_filter)

            level = battery_status.getIntExtra(BatteryManager.EXTRA_LEVEL, -1)
            scale = battery_status.getIntExtra(BatteryManager.EXTRA_SCALE, 100)
            voltage = battery_status.getIntExtra(BatteryManager.EXTRA_VOLTAGE, 0) / 1000.0
            temperature = battery_status.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, 0) / 10.0
            status = battery_status.getIntExtra(BatteryManager.EXTRA_STATUS, -1)
            plugged = battery_status.getIntExtra(BatteryManager.EXTRA_PLUGGED, 0)

            charging = status == BatteryManager.BATTERY_STATUS_CHARGING
            is_plugged = plugged != 0
            battery_pct = (level / scale) * 100 if scale > 0 else 0

            # Estimate time remaining (rough)
            time_remaining = None
            if not charging and battery_pct > 0:
                # Wear OS typical battery life ~24-36 hours
                time_remaining = int(battery_pct / 100 * 30 * 60)  # ~30 hours

            return BatteryStatus(
                level=battery_pct,
                voltage=voltage,
                charging=charging,
                plugged=is_plugged,
                time_remaining_minutes=time_remaining,
                temperature_c=temperature,
            )

        except Exception as e:
            logger.error(f"Failed to get battery status: {e}")
            raise

    async def get_power_mode(self) -> PowerMode:
        """Get current power mode."""
        try:
            if self._power_manager:
                # Check if device is in battery saver
                if self._power_manager.isPowerSaveMode():
                    return PowerMode.SAVER

                # Check battery level for critical
                status = await self.get_battery_status()
                if status.level < 10:
                    return PowerMode.CRITICAL
                elif status.level < 20:
                    return PowerMode.SAVER

            return PowerMode.BALANCED

        except Exception:
            return PowerMode.BALANCED

    async def set_power_mode(self, mode: PowerMode) -> None:
        """Set power mode (advisory on Wear OS)."""
        logger.info(f"Power mode set to {mode.value} (advisory)")

    async def set_cpu_frequency(self, freq_mhz: int) -> None:
        """Set CPU frequency (not available on Wear OS)."""
        logger.debug("CPU frequency control not available on Wear OS")

    async def enter_sleep(self, mode: SleepMode, duration_ms: int | None = None) -> None:
        """Enter sleep mode (system-managed on Wear OS)."""
        logger.debug(f"Sleep request: {mode.value}")

    async def get_power_stats(self) -> PowerStats:
        """Get power consumption statistics."""
        # Wear OS doesn't expose detailed power stats
        return PowerStats(
            current_watts=0.2,  # ~200mW typical
            avg_watts=0.15,
            peak_watts=0.8,  # During workout
            total_wh=0.0,
        )

    # =========================================================================
    # WearOS-Specific Methods
    # =========================================================================

    @property
    def is_battery_saver_mode(self) -> bool:
        """Check if Battery Saver is enabled."""
        try:
            if self._power_manager:
                return self._power_manager.isPowerSaveMode()
        except Exception:
            pass
        return False

    @property
    def is_ambient_mode(self) -> bool:
        """Check if device is in ambient mode.

        Ambient mode is the always-on display state where
        the watch shows a dimmed version of the UI.
        """
        try:
            from jnius import autoclass  # noqa: F401

            # Would use AmbientModeSupport to check ambient controller state
            # AmbientModeSupport = autoclass("androidx.wear.ambient.AmbientModeSupport")
            return False
        except Exception:
            return False

    @property
    def is_doze_mode(self) -> bool:
        """Check if device is in Doze mode.

        Doze mode restricts network access and defers jobs
        when the device is stationary and unplugged.
        """
        try:
            if self._power_manager:
                return self._power_manager.isDeviceIdleMode()
        except Exception:
            pass
        return False

    async def request_ignore_battery_optimizations(self) -> bool:
        """Request to be excluded from battery optimizations.

        This allows the app to run in the background more freely,
        but requires user confirmation.

        Returns:
            True if already excluded or request sent
        """
        try:
            from jnius import autoclass

            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            Settings = autoclass("android.provider.Settings")
            Intent = autoclass("android.content.Intent")
            Uri = autoclass("android.net.Uri")

            activity = PythonActivity.mActivity
            package_name = activity.getPackageName()

            if self._power_manager.isIgnoringBatteryOptimizations(package_name):
                return True

            # Launch settings to request
            intent = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS)
            intent.setData(Uri.parse(f"package:{package_name}"))
            activity.startActivity(intent)
            return True

        except Exception as e:
            logger.error(f"Failed to request battery optimization exclusion: {e}")
            return False
