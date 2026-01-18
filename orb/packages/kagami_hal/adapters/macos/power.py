"""macOS Power Adapter via IOKit.

Provides battery and power management on macOS.
- Battery status via IOKit (IOPowerSources)
- Power mode via pmset / IOKit assertions
- CPU frequency via pmset (limited)

Created: November 15, 2025
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from kagami_hal.data_types import BatteryStatus, PowerMode, PowerStats, SleepMode

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


from kagami_hal.adapters.common import PowerModeMixin


class MacOSPower(PowerModeMixin):
    """macOS power adapter using IOKit."""

    def __init__(self) -> None:
        PowerModeMixin.__init__(self, default_mode=PowerMode.BALANCED)
        self._power_mode = PowerMode.BALANCED  # Explicit init for safety
        self._initialized = False
        self._total_wh = 0.0

        # Power tracking for averaging
        self._power_samples: list[float] = []
        self._peak_watts = 0.0

        # IOKit Helper
        self._iokit_lib: IOKitLib | None = None
        self._has_iokit = False
        try:
            from kagami_hal.adapters.macos.iokit import IOKitLib

            self._iokit_lib = IOKitLib()
            self._has_iokit = self._iokit_lib.available
        except ImportError:
            logger.debug(
                "IOKit library wrapper not available. Using pmset fallback for power management."
            )

        # IOKit Assertions
        self._prevent_sleep_assertion = None

    async def initialize(self) -> bool:
        """Initialize power adapter."""
        try:
            # Check for IOKit availability
            if self._has_iokit:
                logger.info("IOKit framework initialized via ctypes")
            else:
                logger.debug("IOKit framework not available, falling back to pmset")

            # Check if we can read battery info via pmset as fallback

            import subprocess

            result = subprocess.run(
                ["pmset", "-g", "batt"],
                capture_output=True,
                timeout=1,
                text=True,
            )

            if result.returncode == 0:
                self._initialized = True
                logger.info("macOS power adapter initialized")
                return True

            logger.warning("pmset not available (may require macOS)")
            return False

        except Exception as e:
            logger.error(f"Failed to initialize macOS power: {e}")
            return False

    async def get_battery_status(self) -> BatteryStatus:
        """Get battery information via IOKit or pmset."""
        if not self._initialized:
            raise RuntimeError("Power adapter not initialized") from None

        # Try IOKit first
        if self._has_iokit:
            try:
                return self._get_battery_iokit()
            except Exception as e:
                logger.debug(f"IOKit battery read failed: {e}")

        # Fallback to pmset
        try:
            import subprocess

            result = subprocess.run(
                ["pmset", "-g", "batt"],
                capture_output=True,
                timeout=1,
                text=True,
            )

            if result.returncode != 0:
                raise RuntimeError("pmset failed")

            # Parse output: "InternalBattery-0 (id=12345)	95%; discharging; 2:30 remaining"
            output = result.stdout

            # Extract percentage (keep as 0-100 to match HAL standard)
            percentage_match = re.search(r"(\d+)%", output)
            percentage = int(percentage_match.group(1)) if percentage_match else 0
            level = float(percentage)  # 0-100 percentage

            # Extract charging state
            is_charging = "charging" in output.lower()
            plugged = "AC Power" in output or is_charging

            # Extract time remaining
            time_match = re.search(r"(\d+):(\d+) remaining", output)
            if time_match:
                hours = int(time_match.group(1))
                minutes = int(time_match.group(2))
                time_remaining_mins = hours * 60 + minutes
            else:
                time_remaining_mins = None

            return BatteryStatus(
                level=level,
                voltage=0.0,  # pmset doesn't provide voltage
                charging=is_charging,
                plugged=plugged,
                time_remaining_minutes=time_remaining_mins,
                temperature_c=None,  # pmset doesn't provide temp
            )

        except Exception as e:
            logger.error(f"Failed to get battery status: {e}")
            return BatteryStatus(
                level=0.0,  # 0% on error
                voltage=0.0,
                charging=False,
                plugged=False,
                time_remaining_minutes=None,
                temperature_c=None,
            )

    def _get_battery_iokit(self) -> BatteryStatus:
        """Get battery status via IOKit."""
        if not self._iokit_lib:
            raise RuntimeError("IOKit library not loaded")

        info = self._iokit_lib.get_power_sources_info()
        sources = info.get("sources", [])

        if not sources:
            # No battery found (desktop?), return 100% plugged
            return BatteryStatus(
                level=100.0,  # 100% when plugged with no battery
                voltage=0.0,
                charging=True,  # Assume AC if no battery
                plugged=True,
                time_remaining_minutes=None,
                temperature_c=None,
            )

        # Use first source (usually internal battery)
        source = sources[0]

        max_cap = source.get("max_capacity", 100)
        current_cap = source.get("current_capacity", 0)
        # Return level as 0-100 percentage to match HAL standard
        level = (float(current_cap) / float(max_cap)) * 100.0 if max_cap > 0 else 0.0

        return BatteryStatus(
            level=level,
            voltage=source.get("voltage", 0.0) / 1000.0,  # mV to V
            charging=source.get("is_charging", False),
            plugged=True,  # IOKit implies we are connected if we can read it? Not necessarily.
            time_remaining_minutes=(
                source.get("time_remaining") if source.get("time_remaining", -1) != -1 else None
            ),
            temperature_c=None,
        )

    async def set_power_mode(self, mode: PowerMode) -> None:
        """Set power mode via pmset and assertions."""
        if not self._initialized:
            raise RuntimeError("Power adapter not initialized")

        self._power_mode = mode

        try:
            import subprocess

            # Map power mode to pmset settings
            if mode == PowerMode.SAVER:
                # Low power mode
                subprocess.run(
                    ["sudo", "pmset", "-a", "lowpowermode", "1"],
                    check=False,
                    timeout=2,
                )
                self._release_sleep_assertion()

            elif mode == PowerMode.FULL:
                # Disable low power mode
                subprocess.run(
                    ["sudo", "pmset", "-a", "lowpowermode", "0"],
                    check=False,
                    timeout=2,
                )
                # Prevent sleep in FULL mode
                self._create_sleep_assertion("K os Full Performance")

            elif mode == PowerMode.BALANCED:
                subprocess.run(
                    ["sudo", "pmset", "-a", "lowpowermode", "0"],
                    check=False,
                    timeout=2,
                )
                self._release_sleep_assertion()

            logger.debug(f"Power mode set: {mode.value}")

        except Exception as e:
            logger.warning(f"Failed to set power mode (may need sudo): {e}")

    def _create_sleep_assertion(self, reason: str) -> None:
        """Create IOKit power assertion to prevent sleep."""
        if self._prevent_sleep_assertion:
            return

        # Best-effort implementation: use `caffeinate` to keep the system awake.
        # This avoids fragile ctypes bindings and works on stock macOS.
        try:
            import subprocess
            import sys

            if sys.platform != "darwin":
                return

            self._prevent_sleep_assertion = subprocess.Popen(  # type: ignore[assignment]
                ["caffeinate", "-dimsu"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.debug("Created sleep assertion via caffeinate (%s)", reason)
        except FileNotFoundError:
            logger.debug("caffeinate not available; cannot create sleep assertion")
            self._prevent_sleep_assertion = None
        except Exception:
            self._prevent_sleep_assertion = None

    def _release_sleep_assertion(self) -> None:
        """Release sleep assertion."""
        if self._prevent_sleep_assertion:
            try:
                proc = self._prevent_sleep_assertion
                if hasattr(proc, "terminate"):
                    proc.terminate()
                    try:
                        proc.wait(timeout=1)
                    except Exception:
                        try:
                            proc.kill()
                        except Exception:
                            pass
                self._prevent_sleep_assertion = None
            except Exception:
                pass

    async def get_power_mode(self) -> PowerMode:
        """Get current power mode."""
        return self._power_mode

    async def enter_sleep(self, mode: SleepMode, duration_ms: int | None = None) -> None:
        """Enter sleep mode via pmset."""
        if mode == SleepMode.NONE:
            return

        try:
            import subprocess

            # Map sleep mode to pmset command
            if mode == SleepMode.LIGHT:
                # Display sleep
                subprocess.run(["pmset", "displaysleepnow"], timeout=2)
            elif mode == SleepMode.DEEP:
                # System sleep
                subprocess.run(["pmset", "sleepnow"], timeout=2)
            elif mode == SleepMode.HIBERNATE:
                # Hibernate (standby mode)
                subprocess.run(["sudo", "pmset", "-a", "hibernatemode", "25"], timeout=2)
                subprocess.run(["pmset", "sleepnow"], timeout=2)

            logger.debug(f"Entered sleep mode: {mode.value}")

        except Exception as e:
            logger.error(f"Failed to enter sleep mode: {e}")

    async def get_power_stats(self) -> PowerStats:
        """Get power consumption statistics."""
        try:
            import subprocess

            # Use powermetrics to get power consumption (requires sudo)
            result = subprocess.run(
                ["sudo", "powermetrics", "-n", "1", "-i", "1000", "--samplers", "cpu_power"],
                capture_output=True,
                timeout=2,
                text=True,
            )

            current_watts = 0.0

            if result.returncode == 0:
                # Parse output for power consumption
                power_match = re.search(r"CPU Power: (\d+\.?\d*) mW", result.stdout)
                if power_match:
                    current_watts = float(power_match.group(1)) / 1000.0  # mW to W

            # Track samples for averaging
            self._power_samples.append(current_watts)

            # Keep last 60 samples
            if len(self._power_samples) > 60:
                self._power_samples = self._power_samples[-60:]

            avg_watts = (
                sum(self._power_samples) / len(self._power_samples) if self._power_samples else 0.0
            )
            self._peak_watts = max(self._peak_watts, current_watts)

            return PowerStats(
                current_watts=current_watts,
                avg_watts=avg_watts,
                peak_watts=self._peak_watts,
                total_wh=self._total_wh,
            )

        except Exception as e:
            logger.debug(f"Power stats unavailable (may need sudo): {e}")
            return PowerStats(
                current_watts=0.0,
                avg_watts=0.0,
                peak_watts=0.0,
                total_wh=self._total_wh,
            )

    async def set_cpu_frequency(self, freq_mhz: int) -> None:
        """Set CPU frequency (DVFS).

        Note: macOS doesn't expose direct CPU frequency control.
        """
        logger.debug(f"CPU frequency control not available on macOS (requested: {freq_mhz}MHz)")

    async def shutdown(self) -> None:
        """Shutdown power adapter."""
        self._release_sleep_assertion()
        logger.info("macOS power adapter shut down")


__all__ = ["MacOSPower"]
