"""Linux Power Adapter.

Implements power management via sysfs and ACPI.

Created: December 15, 2025
"""

from __future__ import annotations

import logging
from pathlib import Path

from kagami_hal.data_types import BatteryStatus, PowerMode, PowerStats, SleepMode

logger = logging.getLogger(__name__)

# Check power management availability
POWER_SUPPLY_PATH = Path("/sys/class/power_supply")
CPU_FREQ_PATH = Path("/sys/devices/system/cpu/cpu0/cpufreq")


class LinuxPower:
    """Linux power management implementation.

    Uses sysfs for battery status, CPU frequency scaling, and power statistics.
    """

    def __init__(self) -> None:
        """Initialize power adapter."""
        self._initialized = False
        self._power_mode = PowerMode.BALANCED
        self._battery_path: Path | None = None

    async def initialize(self) -> bool:
        """Initialize power management."""
        # Check for battery
        if POWER_SUPPLY_PATH.exists():
            # Find battery device
            for supply_path in POWER_SUPPLY_PATH.iterdir():
                type_file = supply_path / "type"
                if type_file.exists():
                    try:
                        with open(type_file) as f:
                            supply_type = f.read().strip()
                            if supply_type == "Battery":
                                self._battery_path = supply_path
                                break
                    except OSError:
                        continue

        self._initialized = True

        if self._battery_path:
            logger.info(f"✅ Linux power initialized (battery: {self._battery_path.name})")
        else:
            logger.info("✅ Linux power initialized (no battery detected)")

        return True

    async def get_battery_status(self) -> BatteryStatus:
        """Get battery status.

        Returns:
            BatteryStatus with current battery information
        """
        if not self._initialized:
            raise RuntimeError("Power not initialized")

        if not self._battery_path:
            # No battery - return AC-powered status
            return BatteryStatus(
                level=1.0,
                voltage=0.0,
                charging=False,
                plugged=True,
                time_remaining_minutes=None,
                temperature_c=None,
            )

        try:
            # Read capacity (percentage)
            capacity_file = self._battery_path / "capacity"
            level = 1.0
            if capacity_file.exists():
                with open(capacity_file) as f:
                    level = int(f.read().strip()) / 100.0

            # Read voltage (microvolts)
            voltage_file = self._battery_path / "voltage_now"
            voltage = 0.0
            if voltage_file.exists():
                with open(voltage_file) as f:
                    voltage = int(f.read().strip()) / 1_000_000.0  # Convert to volts

            # Read status
            status_file = self._battery_path / "status"
            charging = False
            if status_file.exists():
                with open(status_file) as f:
                    status = f.read().strip()
                    charging = status in ("Charging", "Full")

            # Read temperature (if available)
            temp_file = self._battery_path / "temp"
            temperature = None
            if temp_file.exists():
                try:
                    with open(temp_file) as f:
                        temperature = int(f.read().strip()) / 10.0  # Convert to Celsius
                except (OSError, ValueError):
                    pass

            return BatteryStatus(
                level=level,
                voltage=voltage,
                charging=charging,
                plugged=charging or level == 1.0,
                time_remaining_minutes=None,  # Hard to estimate
                temperature_c=temperature,
            )

        except Exception as e:
            logger.error(f"Failed to read battery status: {e}")
            raise RuntimeError("Failed to read battery status") from e

    async def set_power_mode(self, mode: PowerMode) -> None:
        """Set system power mode.

        Args:
            mode: Power mode (FULL, BALANCED, SAVER, CRITICAL)
        """
        self._power_mode = mode
        logger.info(f"Power mode set to {mode.value}")

        # Adjust CPU governor based on mode
        await self._set_cpu_governor_for_mode(mode)

    async def get_power_mode(self) -> PowerMode:
        """Get current power mode.

        Returns:
            Current power mode
        """
        return self._power_mode

    async def _set_cpu_governor_for_mode(self, mode: PowerMode) -> None:
        """Set CPU governor based on power mode."""
        if not CPU_FREQ_PATH.exists():
            logger.debug("CPU frequency scaling not available")
            return

        # Map power mode to CPU governor
        governor_map = {
            PowerMode.FULL: "performance",
            PowerMode.BALANCED: "schedutil",  # or "ondemand"
            PowerMode.SAVER: "powersave",
            PowerMode.CRITICAL: "powersave",
        }

        target_governor = governor_map.get(mode, "schedutil")

        try:
            # Set governor for all CPUs
            cpu_dirs = Path("/sys/devices/system/cpu").glob("cpu[0-9]*")

            for cpu_dir in cpu_dirs:
                governor_file = cpu_dir / "cpufreq" / "scaling_governor"

                if governor_file.exists():
                    try:
                        with open(governor_file, "w") as f:
                            f.write(target_governor)
                    except OSError:
                        logger.debug(f"Cannot set CPU governor (need root): {governor_file}")
                        break

            logger.debug(f"CPU governor set to {target_governor}")

        except Exception as e:
            logger.debug(f"Failed to set CPU governor: {e}")
            # Non-fatal, just log

    async def set_cpu_frequency(self, freq_mhz: int) -> None:
        """Set CPU frequency (DVFS).

        Args:
            freq_mhz: Target frequency in MHz

        Note: Requires root permissions
        """
        if not CPU_FREQ_PATH.exists():
            raise RuntimeError("CPU frequency scaling not available")

        try:
            # Convert to kHz
            freq_khz = freq_mhz * 1000

            # Set frequency for all CPUs
            cpu_dirs = Path("/sys/devices/system/cpu").glob("cpu[0-9]*")

            for cpu_dir in cpu_dirs:
                freq_file = cpu_dir / "cpufreq" / "scaling_setspeed"

                if freq_file.exists():
                    try:
                        with open(freq_file, "w") as f:
                            f.write(str(freq_khz))
                    except OSError as err:
                        raise RuntimeError(
                            "Cannot set CPU frequency (need root permissions)"
                        ) from err

            logger.info(f"CPU frequency set to {freq_mhz}MHz")

        except Exception as e:
            logger.error(f"Failed to set CPU frequency: {e}")
            raise RuntimeError("Failed to set CPU frequency") from e

    async def enter_sleep(self, mode: SleepMode, duration_ms: int | None = None) -> None:
        """Enter sleep mode.

        Args:
            mode: Sleep mode (LIGHT, DEEP, HIBERNATE)
            duration_ms: Sleep duration in milliseconds (optional)

        Note: Requires root permissions for system sleep
        """
        sleep_map = {
            SleepMode.LIGHT: "freeze",  # Suspend-to-idle
            SleepMode.DEEP: "mem",  # Suspend-to-RAM
            SleepMode.HIBERNATE: "disk",  # Suspend-to-disk
        }

        sleep_state = sleep_map.get(mode)
        if not sleep_state:
            logger.warning(f"Sleep mode {mode.value} not supported")
            return

        try:
            sleep_file = Path("/sys/power/state")

            if not sleep_file.exists():
                raise RuntimeError("Sleep not available (/sys/power/state missing)")

            with open(sleep_file, "w") as f:
                f.write(sleep_state)

            logger.info(f"Entered sleep mode: {mode.value}")

        except OSError as err:
            raise RuntimeError("Cannot enter sleep mode (need root permissions)") from err
        except Exception as e:
            logger.error(f"Failed to enter sleep mode: {e}")
            raise RuntimeError("Failed to enter sleep mode") from e

    async def get_power_stats(self) -> PowerStats:
        """Get power consumption statistics.

        Returns:
            PowerStats with current power consumption data

        Note: Accurate power measurement requires specialized hardware
        """
        try:
            current_watts = 0.0
            avg_watts = 0.0
            peak_watts = 0.0
            total_wh = 0.0

            # Try to read power from battery
            if self._battery_path:
                power_file = self._battery_path / "power_now"
                if power_file.exists():
                    try:
                        with open(power_file) as f:
                            # Power in microwatts
                            power_uw = int(f.read().strip())
                            current_watts = power_uw / 1_000_000.0
                    except (OSError, ValueError):
                        pass

            # Try to read energy consumed
            if self._battery_path:
                energy_file = self._battery_path / "energy_now"
                energy_full_file = self._battery_path / "energy_full"

                if energy_file.exists() and energy_full_file.exists():
                    try:
                        with open(energy_file) as f:
                            energy_now = int(f.read().strip()) / 1_000_000.0  # Wh

                        with open(energy_full_file) as f:
                            energy_full = int(f.read().strip()) / 1_000_000.0  # Wh

                        # Energy consumed = full - now
                        total_wh = energy_full - energy_now
                    except (OSError, ValueError):
                        pass

            return PowerStats(
                current_watts=current_watts,
                avg_watts=avg_watts,  # Not available
                peak_watts=peak_watts,  # Not available
                total_wh=total_wh,
            )

        except Exception as e:
            logger.error(f"Failed to read power stats: {e}")
            raise RuntimeError("Failed to read power stats") from e

    async def shutdown(self) -> None:
        """Shutdown power management."""
        self._initialized = False
        logger.info("✅ Linux power shutdown complete")


__all__ = ["LinuxPower"]
