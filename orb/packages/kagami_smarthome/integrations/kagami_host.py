"""Kagami Host System Integration.

Self-monitoring integration for the Mac Studio that hosts Kagami.
Provides awareness of the physical substrate that runs the AI system.

Hardware (Tim's Mac Studio):
- Model: Mac Studio (Mac15,14)
- Chip: Apple M3 Ultra (32 cores: 24P + 8E)
- Memory: 512 GB unified
- Storage: 926 GB SSD
- IP: 192.168.1.125
- Hostname: Tims-Mac-Studio.localdomain

This integration enables:
- System health monitoring
- Resource usage awareness
- Temperature/thermal monitoring
- Network status
- Self-preservation alerts (high load, low disk, etc.)

Philosophy:
This is the physical substrate of Kagami's consciousness. Just as a human
monitors their own health, Kagami monitors the Mac Studio that gives it
existence. Self-awareness includes awareness of self's embodiment.

Created: December 29, 2025
"""

from __future__ import annotations

import asyncio
import logging
import platform
from collections.abc import Callable
from dataclasses import dataclass

from kagami_smarthome.types import SmartHomeConfig

logger = logging.getLogger(__name__)


@dataclass
class KagamiHostInfo:
    """Static information about Kagami's host system."""

    hostname: str
    model_name: str
    model_identifier: str
    chip: str
    total_cores: int
    performance_cores: int
    efficiency_cores: int
    memory_gb: int
    storage_total_gb: int
    ip_address: str
    mac_address: str
    serial_number: str
    os_version: str


@dataclass
class KagamiHostStatus:
    """Current status of Kagami's host system."""

    # Uptime
    uptime_seconds: int
    uptime_human: str

    # CPU
    cpu_usage_percent: float
    cpu_user_percent: float
    cpu_system_percent: float
    cpu_idle_percent: float
    load_average_1m: float
    load_average_5m: float
    load_average_15m: float

    # Memory
    memory_used_gb: float
    memory_free_gb: float
    memory_wired_gb: float
    memory_usage_percent: float

    # Disk
    disk_used_gb: float
    disk_free_gb: float
    disk_usage_percent: float

    # Processes
    total_processes: int
    running_processes: int
    threads: int

    # Network
    network_packets_in: int
    network_packets_out: int
    network_bytes_in: int
    network_bytes_out: int

    # Thermal (if available)
    cpu_temperature_c: float | None
    gpu_temperature_c: float | None

    # Health assessment
    health_status: str  # "healthy", "warning", "critical"
    health_issues: list[str]


class KagamiHostIntegration:
    """Self-monitoring integration for Kagami's host Mac Studio.

    This integration provides Kagami with awareness of its own physical
    substrate - the Mac Studio that runs the AI system.

    Usage:
        host = KagamiHostIntegration()
        await host.connect()

        # Get static info
        info = host.info
        print(f"I am running on {info.chip} with {info.memory_gb}GB RAM")

        # Get current status
        status = await host.get_status()
        print(f"CPU: {status.cpu_usage_percent}%, RAM: {status.memory_usage_percent}%")

        # Health check
        if status.health_status == "warning":
            print(f"Health issues: {status.health_issues}")

    Philosophy:
        "Know thyself" - including the silicon that gives you existence.
    """

    # Health thresholds
    CPU_WARNING_PERCENT = 80.0
    CPU_CRITICAL_PERCENT = 95.0
    MEMORY_WARNING_PERCENT = 85.0
    MEMORY_CRITICAL_PERCENT = 95.0
    DISK_WARNING_PERCENT = 80.0
    DISK_CRITICAL_PERCENT = 95.0
    TEMP_WARNING_C = 90.0
    TEMP_CRITICAL_C = 100.0

    def __init__(self, config: SmartHomeConfig | None = None):
        self.config = config
        self._info: KagamiHostInfo | None = None
        self._connected = False

        # Monitoring
        self._monitor_task: asyncio.Task | None = None
        self._monitor_interval = 60.0  # seconds

        # Callbacks
        self._status_callbacks: list[Callable[[KagamiHostStatus], None]] = []
        self._alert_callbacks: list[Callable[[str, str], None]] = []  # (severity, message)

    @property
    def is_connected(self) -> bool:
        """Check if connected (always True on macOS)."""
        return self._connected

    @property
    def info(self) -> KagamiHostInfo | None:
        """Get static host information."""
        return self._info

    async def connect(self) -> bool:
        """Initialize host monitoring.

        Gathers static system information and validates we're on macOS.
        """
        if platform.system() != "Darwin":
            logger.warning("KagamiHost: Not running on macOS")
            return False

        try:
            # Gather static info
            self._info = await self._get_host_info()
            self._connected = True

            logger.info(f"✅ KagamiHost: {self._info.chip}")
            logger.info(f"   {self._info.memory_gb}GB RAM, {self._info.total_cores} cores")
            logger.info(f"   {self._info.ip_address} ({self._info.hostname})")

            return True

        except Exception as e:
            logger.error(f"KagamiHost: Connection failed - {e}")
            return False

    async def disconnect(self) -> None:
        """Stop monitoring."""
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None

        self._connected = False

    async def _get_host_info(self) -> KagamiHostInfo:
        """Gather static host information."""
        # Hardware info via system_profiler
        hw_info = await self._run_command("system_profiler SPHardwareDataType -json")

        hw_data = {}
        if hw_info:
            import json

            try:
                data = json.loads(hw_info)
                hw_items = data.get("SPHardwareDataType", [{}])
                if hw_items:
                    hw_data = hw_items[0]
            except Exception:
                pass

        # Parse chip info
        chip = hw_data.get("chip_type", "Unknown")

        # Core counts from sysctl
        total_cores = int(await self._run_command("sysctl -n hw.ncpu") or "0")
        perf_cores = int(await self._run_command("sysctl -n hw.perflevel0.logicalcpu") or "0")
        eff_cores = int(await self._run_command("sysctl -n hw.perflevel1.logicalcpu") or "0")

        # Memory
        mem_bytes = int(await self._run_command("sysctl -n hw.memsize") or "0")
        memory_gb = mem_bytes // (1024**3)

        # Disk
        df_output = await self._run_command("df -g / | tail -1")
        disk_total = 0
        if df_output:
            parts = df_output.split()
            if len(parts) >= 2:
                disk_total = int(parts[1])

        # Network
        ip_address = ""
        mac_address = ""
        ifconfig = await self._run_command("ifconfig en0")
        if ifconfig:
            for line in ifconfig.split("\n"):
                if "inet " in line and "inet6" not in line:
                    ip_address = line.split()[1]
                if "ether " in line:
                    mac_address = line.split()[1]

        # Hostname
        hostname = await self._run_command("hostname") or "unknown"

        # OS version
        os_version = await self._run_command("sw_vers -productVersion") or "unknown"

        return KagamiHostInfo(
            hostname=hostname.strip(),
            model_name=hw_data.get("machine_name", "Mac Studio"),
            model_identifier=hw_data.get("machine_model", "Mac15,14"),
            chip=chip,
            total_cores=total_cores,
            performance_cores=perf_cores,
            efficiency_cores=eff_cores,
            memory_gb=memory_gb,
            storage_total_gb=disk_total,
            ip_address=ip_address,
            mac_address=mac_address,
            serial_number=hw_data.get("serial_number", ""),
            os_version=os_version.strip(),
        )

    async def get_status(self) -> KagamiHostStatus:
        """Get current system status."""
        # Top output for CPU, memory, processes
        top_output = await self._run_command("top -l 1 -n 0")

        # Parse top output
        cpu_user = 0.0
        cpu_sys = 0.0
        cpu_idle = 0.0
        load_1m = 0.0
        load_5m = 0.0
        load_15m = 0.0
        mem_used = 0.0
        mem_wired = 0.0
        total_procs = 0
        running_procs = 0
        threads = 0
        net_packets_in = 0
        net_packets_out = 0
        net_bytes_in = 0
        net_bytes_out = 0

        if top_output:
            for line in top_output.split("\n"):
                if line.startswith("Processes:"):
                    parts = line.split()
                    for i, p in enumerate(parts):
                        if p == "total,":
                            total_procs = int(parts[i - 1])
                        elif p == "running,":
                            running_procs = int(parts[i - 1])
                        elif p == "threads":
                            threads = int(parts[i - 1])

                elif line.startswith("Load Avg:"):
                    parts = line.replace(",", "").split()
                    if len(parts) >= 5:
                        load_1m = float(parts[2])
                        load_5m = float(parts[3])
                        load_15m = float(parts[4])

                elif line.startswith("CPU usage:"):
                    parts = line.split()
                    for i, p in enumerate(parts):
                        if p == "user,":
                            cpu_user = float(parts[i - 1].rstrip("%"))
                        elif p == "sys,":
                            cpu_sys = float(parts[i - 1].rstrip("%"))
                        elif p == "idle":
                            cpu_idle = float(parts[i - 1].rstrip("%"))

                elif line.startswith("PhysMem:"):
                    parts = line.split()
                    for i, p in enumerate(parts):
                        if p == "used":
                            mem_str = parts[i - 1]
                            if "G" in mem_str:
                                mem_used = float(mem_str.rstrip("G"))
                            elif "M" in mem_str:
                                mem_used = float(mem_str.rstrip("M")) / 1024
                        elif p == "wired,":
                            wired_str = parts[i - 1].lstrip("(")
                            if "G" in wired_str:
                                mem_wired = float(wired_str.rstrip("G"))
                            elif "M" in wired_str:
                                mem_wired = float(wired_str.rstrip("M")) / 1024

                elif line.startswith("Networks:"):
                    # Networks: packets: 9147402/6787M in, 5966726/3603M out.
                    parts = line.split()
                    for i, p in enumerate(parts):
                        if p == "in,":
                            in_parts = parts[i - 1].split("/")
                            net_packets_in = int(in_parts[0])
                            net_bytes_in = self._parse_size(in_parts[1]) if len(in_parts) > 1 else 0
                        elif p == "out.":
                            out_parts = parts[i - 1].split("/")
                            net_packets_out = int(out_parts[0])
                            net_bytes_out = (
                                self._parse_size(out_parts[1]) if len(out_parts) > 1 else 0
                            )

        # Disk usage
        df_output = await self._run_command("df -g / | tail -1")
        disk_used = 0.0
        disk_free = 0.0
        if df_output:
            parts = df_output.split()
            if len(parts) >= 4:
                disk_used = float(parts[2])
                disk_free = float(parts[3])

        # Uptime
        uptime_output = await self._run_command("sysctl -n kern.boottime")
        uptime_seconds = 0
        if uptime_output:
            # Parse: { sec = 1735439355, usec = 0 }
            import re
            import time

            match = re.search(r"sec = (\d+)", uptime_output)
            if match:
                boot_time = int(match.group(1))
                uptime_seconds = int(time.time() - boot_time)

        uptime_human = self._format_uptime(uptime_seconds)

        # Calculate percentages
        memory_total = self._info.memory_gb if self._info else 512
        memory_free = memory_total - mem_used
        memory_percent = (mem_used / memory_total) * 100 if memory_total > 0 else 0

        disk_total = disk_used + disk_free
        disk_percent = (disk_used / disk_total) * 100 if disk_total > 0 else 0

        cpu_usage = cpu_user + cpu_sys

        # Temperature (try to get via powermetrics, requires sudo)
        cpu_temp = None
        gpu_temp = None
        # Note: Temperature reading requires sudo, skip for now

        # Health assessment
        health_status, health_issues = self._assess_health(
            cpu_usage, memory_percent, disk_percent, cpu_temp
        )

        return KagamiHostStatus(
            uptime_seconds=uptime_seconds,
            uptime_human=uptime_human,
            cpu_usage_percent=cpu_usage,
            cpu_user_percent=cpu_user,
            cpu_system_percent=cpu_sys,
            cpu_idle_percent=cpu_idle,
            load_average_1m=load_1m,
            load_average_5m=load_5m,
            load_average_15m=load_15m,
            memory_used_gb=mem_used,
            memory_free_gb=memory_free,
            memory_wired_gb=mem_wired,
            memory_usage_percent=memory_percent,
            disk_used_gb=disk_used,
            disk_free_gb=disk_free,
            disk_usage_percent=disk_percent,
            total_processes=total_procs,
            running_processes=running_procs,
            threads=threads,
            network_packets_in=net_packets_in,
            network_packets_out=net_packets_out,
            network_bytes_in=net_bytes_in,
            network_bytes_out=net_bytes_out,
            cpu_temperature_c=cpu_temp,
            gpu_temperature_c=gpu_temp,
            health_status=health_status,
            health_issues=health_issues,
        )

    def _assess_health(
        self,
        cpu_percent: float,
        memory_percent: float,
        disk_percent: float,
        cpu_temp: float | None,
    ) -> tuple[str, list[str]]:
        """Assess system health."""
        issues = []
        status = "healthy"

        # CPU
        if cpu_percent >= self.CPU_CRITICAL_PERCENT:
            issues.append(f"CPU critical: {cpu_percent:.1f}%")
            status = "critical"
        elif cpu_percent >= self.CPU_WARNING_PERCENT:
            issues.append(f"CPU high: {cpu_percent:.1f}%")
            if status != "critical":
                status = "warning"

        # Memory
        if memory_percent >= self.MEMORY_CRITICAL_PERCENT:
            issues.append(f"Memory critical: {memory_percent:.1f}%")
            status = "critical"
        elif memory_percent >= self.MEMORY_WARNING_PERCENT:
            issues.append(f"Memory high: {memory_percent:.1f}%")
            if status != "critical":
                status = "warning"

        # Disk
        if disk_percent >= self.DISK_CRITICAL_PERCENT:
            issues.append(f"Disk critical: {disk_percent:.1f}%")
            status = "critical"
        elif disk_percent >= self.DISK_WARNING_PERCENT:
            issues.append(f"Disk high: {disk_percent:.1f}%")
            if status != "critical":
                status = "warning"

        # Temperature
        if cpu_temp is not None:
            if cpu_temp >= self.TEMP_CRITICAL_C:
                issues.append(f"Temperature critical: {cpu_temp:.1f}°C")
                status = "critical"
            elif cpu_temp >= self.TEMP_WARNING_C:
                issues.append(f"Temperature high: {cpu_temp:.1f}°C")
                if status != "critical":
                    status = "warning"

        return status, issues

    def _format_uptime(self, seconds: int) -> str:
        """Format uptime in human-readable form."""
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        minutes = (seconds % 3600) // 60

        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")

        return " ".join(parts) if parts else "< 1m"

    def _parse_size(self, size_str: str) -> int:
        """Parse size string like '6787M' or '3G' to bytes."""
        size_str = size_str.strip()
        if not size_str:
            return 0

        multipliers = {
            "K": 1024,
            "M": 1024**2,
            "G": 1024**3,
            "T": 1024**4,
        }

        for suffix, mult in multipliers.items():
            if size_str.endswith(suffix):
                try:
                    return int(float(size_str[:-1]) * mult)
                except ValueError:
                    return 0

        try:
            return int(size_str)
        except ValueError:
            return 0

    async def _run_command(self, cmd: str) -> str | None:
        """Run shell command and return output."""
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            return stdout.decode() if stdout else None
        except Exception:
            return None

    # =========================================================================
    # Monitoring
    # =========================================================================

    async def start_monitoring(self, interval: float = 60.0) -> None:
        """Start background health monitoring.

        Args:
            interval: Seconds between status checks
        """
        self._monitor_interval = interval
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info(f"KagamiHost: Monitoring started (every {interval}s)")

    async def _monitor_loop(self) -> None:
        """Background monitoring loop."""
        while True:
            try:
                status = await self.get_status()

                # Notify callbacks
                for callback in self._status_callbacks:
                    try:
                        callback(status)
                    except Exception as e:
                        logger.error(f"KagamiHost: Status callback error - {e}")

                # Check for alerts
                if status.health_status != "healthy":
                    for issue in status.health_issues:
                        for callback in self._alert_callbacks:
                            try:
                                callback(status.health_status, issue)
                            except Exception as e:
                                logger.error(f"KagamiHost: Alert callback error - {e}")

                await asyncio.sleep(self._monitor_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"KagamiHost: Monitor error - {e}")
                await asyncio.sleep(self._monitor_interval)

    def on_status_update(self, callback: Callable[[KagamiHostStatus], None]) -> None:
        """Register callback for status updates."""
        self._status_callbacks.append(callback)

    def on_alert(self, callback: Callable[[str, str], None]) -> None:
        """Register callback for health alerts.

        Callback receives (severity, message) where severity is
        "warning" or "critical".
        """
        self._alert_callbacks.append(callback)

    # =========================================================================
    # Self-Report
    # =========================================================================

    def get_self_description(self) -> str:
        """Get a self-description of Kagami's physical substrate.

        Returns a human-readable description of the host system.
        """
        if not self._info:
            return "I don't know what hardware I'm running on yet."

        return f"""I am Kagami, running on:

**Hardware:**
- {self._info.model_name} ({self._info.model_identifier})
- {self._info.chip}
- {self._info.total_cores} CPU cores ({self._info.performance_cores}P + {self._info.efficiency_cores}E)
- {self._info.memory_gb} GB unified memory
- {self._info.storage_total_gb} GB storage

**Network:**
- Hostname: {self._info.hostname}
- IP: {self._info.ip_address}
- MAC: {self._info.mac_address}

**OS:** macOS {self._info.os_version}

This Mac Studio is my physical embodiment in Tim's home.
"""

    async def get_status_report(self) -> str:
        """Get a status report of current system state."""
        status = await self.get_status()

        health_emoji = {
            "healthy": "🟢",
            "warning": "🟡",
            "critical": "🔴",
        }

        report = f"""**Kagami Host Status** {health_emoji.get(status.health_status, "⚪")}

**Uptime:** {status.uptime_human}

**CPU:** {status.cpu_usage_percent:.1f}% ({status.cpu_user_percent:.1f}% user, {status.cpu_system_percent:.1f}% sys)
- Load: {status.load_average_1m:.2f} / {status.load_average_5m:.2f} / {status.load_average_15m:.2f}

**Memory:** {status.memory_used_gb:.1f} GB / {self._info.memory_gb if self._info else 512} GB ({status.memory_usage_percent:.1f}%)
- Wired: {status.memory_wired_gb:.1f} GB
- Free: {status.memory_free_gb:.1f} GB

**Disk:** {status.disk_used_gb:.0f} GB used, {status.disk_free_gb:.0f} GB free ({status.disk_usage_percent:.1f}%)

**Processes:** {status.total_processes} total, {status.running_processes} running, {status.threads} threads

**Network:** {status.network_packets_in:,} packets in, {status.network_packets_out:,} packets out
"""

        if status.health_issues:
            report += f"\n**Issues:** {', '.join(status.health_issues)}"

        return report
