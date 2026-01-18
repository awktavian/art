"""Formlabs Form 4 3D Printer Integration.

Integration for Formlabs Form 4 resin 3D printer via Local API.

Provides:
- Print job status monitoring
- Printer state (idle, printing, paused)
- Resin level and tank status
- Build platform detection
- Estimated time remaining
- Job history

API: Formlabs Local API (PreFormServer)
Docs: https://github.com/Formlabs/formlabs-api-python

Equipment:
- Formlabs Form 4 (MSLA with Low Force Display™)
- Build: 20 × 12.5 × 21 cm
- Resolution: 50μm XY, 25-300μm Z
- Speed: Up to 100 mm/h
- 23+ compatible resins

Created: December 30, 2025
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import aiohttp

from kagami_smarthome.types import SmartHomeConfig

logger = logging.getLogger(__name__)

# Default PreFormServer port
DEFAULT_PORT = 44388
DEFAULT_HOST = "localhost"


class PrinterState(Enum):
    """Form 4 printer state."""

    IDLE = "idle"
    PRINTING = "printing"
    PAUSED = "paused"
    HEATING = "heating"
    FILLING = "filling"
    FINISHING = "finishing"
    ERROR = "error"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class PrintJobStatus(Enum):
    """Print job status."""

    QUEUED = "queued"
    PRINTING = "printing"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ResinType(Enum):
    """Common Formlabs resin types."""

    CLEAR = "Clear"
    GREY = "Grey"
    WHITE = "White"
    BLACK = "Black"
    TOUGH = "Tough"
    DURABLE = "Durable"
    FLEXIBLE = "Flexible"
    CASTABLE = "Castable"
    DENTAL = "Dental"
    HIGH_TEMP = "High Temp"
    RIGID = "Rigid"
    UNKNOWN = "Unknown"


@dataclass
class PrintJob:
    """Current or recent print job."""

    id: str
    name: str
    status: PrintJobStatus
    progress: float  # 0-100
    layer_current: int
    layer_total: int
    estimated_time_total: int  # seconds
    time_remaining: int  # seconds
    time_elapsed: int  # seconds
    resin_type: str
    resin_used_ml: float
    started_at: datetime | None = None
    finished_at: datetime | None = None


@dataclass
class TankStatus:
    """Resin tank status."""

    installed: bool
    resin_type: str
    resin_level_ml: float
    resin_level_percent: float
    tank_lifetime_layers: int
    tank_used_layers: int


@dataclass
class FormlabsState:
    """Complete Form 4 printer state."""

    state: PrinterState
    connected: bool
    serial_number: str | None
    firmware_version: str | None

    # Current job
    current_job: PrintJob | None

    # Hardware status
    tank: TankStatus | None
    build_platform_inserted: bool
    cover_closed: bool

    # Temperature
    resin_temp_c: float | None
    chamber_temp_c: float | None

    # Consumables
    resin_cartridge_ml: float

    # Network
    ip_address: str | None

    # Timestamps
    last_update: datetime = field(default_factory=datetime.now)


class FormlabsIntegration:
    """Formlabs Form 4 integration via Local API.

    Uses PreFormServer for local network communication.
    No internet required for basic monitoring.

    Features:
    - Real-time print monitoring
    - Job status tracking
    - Resin and consumables monitoring
    - Event callbacks for state changes

    Note: PreFormServer must be running on the same network.
    Download from Formlabs Dashboard or GitHub SDK.
    """

    def __init__(self, config: SmartHomeConfig):
        self.config = config
        self._session: aiohttp.ClientSession | None = None
        self._initialized = False

        # Load from config first, then try Keychain
        self._host = getattr(config, "formlabs_host", None) or DEFAULT_HOST
        self._port = getattr(config, "formlabs_port", None) or DEFAULT_PORT

        # Current state
        self._state: FormlabsState | None = None
        self._last_update: datetime | None = None

        # Polling task
        self._poll_task: asyncio.Task[None] | None = None
        self._poll_interval = 10.0  # seconds

        # Previous state for change detection
        self._prev_job_status: PrintJobStatus | None = None

        # Resilience: reconnection tracking
        self._consecutive_failures = 0
        self._max_failures_before_backoff = 3
        self._backoff_interval = 30.0  # seconds

        # Event callbacks
        self._on_state_change: Callable[[FormlabsState], None] | None = None
        self._on_print_complete: Callable[[PrintJob], None] | None = None
        self._on_error: Callable[[str], None] | None = None

        # Load from Keychain (after all instance vars initialized)
        self._load_from_keychain()

    def _load_from_keychain(self) -> None:
        """Load Formlabs config from Keychain."""
        try:
            from kagami_smarthome.secrets import secrets

            # Load host if not already set
            if self._host == DEFAULT_HOST:
                host = secrets.get("formlabs_host")
                if host:
                    self._host = host
                    logger.debug("Formlabs: Loaded host from Keychain")

            # Load port if not already set
            if self._port == DEFAULT_PORT:
                port_str = secrets.get("formlabs_port")
                if port_str:
                    try:
                        self._port = int(port_str)
                        logger.debug("Formlabs: Loaded port from Keychain")
                    except ValueError:
                        pass

        except Exception as e:
            logger.debug(f"Formlabs: Could not load from Keychain: {e}")

    @property
    def base_url(self) -> str:
        """Get API base URL."""
        return f"http://{self._host}:{self._port}"

    @property
    def is_connected(self) -> bool:
        return self._initialized and self._state is not None

    @property
    def state(self) -> FormlabsState | None:
        return self._state

    async def connect(self) -> bool:
        """Connect to PreFormServer and discover printers."""
        try:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))

            # Check if PreFormServer is running
            status = await self._api_get("/")
            if status is None:
                logger.warning("Formlabs: PreFormServer not responding")
                return False

            # Discover printers
            printers = await self._api_get("/discover/")
            if printers and printers.get("printers"):
                printer = printers["printers"][0]
                logger.info(f"Formlabs: Found {printer.get('product_name', 'printer')}")

            # Get initial state
            await self._update_state()

            self._initialized = True
            logger.info("Formlabs: Connected to Form 4")

            # Start polling
            self._start_polling()

            return True

        except Exception as e:
            logger.error(f"Formlabs: Connection failed - {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from PreFormServer."""
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
            self._poll_task = None

        if self._session:
            await self._session.close()
            self._session = None

        self._initialized = False
        logger.info("Formlabs: Disconnected")

    async def _api_get(self, path: str) -> dict[str, Any] | None:
        """Make GET request to PreFormServer."""
        if not self._session:
            return None

        url = f"{self.base_url}{path}"
        try:
            async with self._session.get(url) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    logger.debug(f"Formlabs API error: {resp.status}")
                    return None
        except aiohttp.ClientError as e:
            logger.debug(f"Formlabs API request failed: {e}")
            return None
        except Exception as e:
            logger.debug(f"Formlabs API error: {e}")
            return None

    async def _api_post(
        self, path: str, data: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        """Make POST request to PreFormServer."""
        if not self._session:
            return None

        url = f"{self.base_url}{path}"
        try:
            async with self._session.post(url, json=data) as resp:
                if resp.status in (200, 201, 204):
                    if resp.content_type == "application/json":
                        return await resp.json()
                    return {}
                else:
                    logger.debug(f"Formlabs API POST error: {resp.status}")
                    return None
        except Exception as e:
            logger.debug(f"Formlabs API POST error: {e}")
            return None

    async def _update_state(self) -> None:
        """Update printer state from API."""
        try:
            # Get printer status
            status = await self._api_get("/printer/")
            if not status:
                self._state = FormlabsState(
                    state=PrinterState.OFFLINE,
                    connected=False,
                    serial_number=None,
                    firmware_version=None,
                    current_job=None,
                    tank=None,
                    build_platform_inserted=False,
                    cover_closed=False,
                    resin_temp_c=None,
                    chamber_temp_c=None,
                    resin_cartridge_ml=0,
                    ip_address=None,
                )
                return

            # Parse printer state
            printer_state = self._parse_printer_state(status.get("state", ""))

            # Get current print job if any
            current_job = None
            if printer_state == PrinterState.PRINTING:
                job_data = await self._api_get("/job/")
                if job_data:
                    current_job = self._parse_job(job_data)

            # Get tank status
            tank = None
            tank_data = status.get("tank", {})
            if tank_data:
                tank = TankStatus(
                    installed=tank_data.get("installed", False),
                    resin_type=tank_data.get("resin_type", "Unknown"),
                    resin_level_ml=tank_data.get("resin_level_ml", 0),
                    resin_level_percent=tank_data.get("resin_level_percent", 0),
                    tank_lifetime_layers=tank_data.get("lifetime_layers", 0),
                    tank_used_layers=tank_data.get("used_layers", 0),
                )

            # Build state
            self._state = FormlabsState(
                state=printer_state,
                connected=True,
                serial_number=status.get("serial"),
                firmware_version=status.get("firmware_version"),
                current_job=current_job,
                tank=tank,
                build_platform_inserted=status.get("build_platform_inserted", False),
                cover_closed=status.get("cover_closed", True),
                resin_temp_c=status.get("resin_temperature_c"),
                chamber_temp_c=status.get("chamber_temperature_c"),
                resin_cartridge_ml=status.get("cartridge_ml", 0),
                ip_address=status.get("ip_address"),
                last_update=datetime.now(),
            )

            self._last_update = datetime.now()

            # Check for job completion
            if current_job:
                if (
                    self._prev_job_status == PrintJobStatus.PRINTING
                    and current_job.status == PrintJobStatus.COMPLETED
                ):
                    if self._on_print_complete:
                        self._on_print_complete(current_job)
                self._prev_job_status = current_job.status

            # Emit state change
            if self._on_state_change and self._state:
                self._on_state_change(self._state)

        except Exception as e:
            logger.error(f"Formlabs: State update failed - {e}")

    def _parse_printer_state(self, state: str) -> PrinterState:
        """Parse printer state string to enum."""
        state_map = {
            "idle": PrinterState.IDLE,
            "printing": PrinterState.PRINTING,
            "paused": PrinterState.PAUSED,
            "heating": PrinterState.HEATING,
            "filling": PrinterState.FILLING,
            "finishing": PrinterState.FINISHING,
            "error": PrinterState.ERROR,
        }
        return state_map.get(state.lower(), PrinterState.UNKNOWN)

    def _parse_job(self, data: dict[str, Any]) -> PrintJob:
        """Parse print job from API response."""
        status_map = {
            "queued": PrintJobStatus.QUEUED,
            "printing": PrintJobStatus.PRINTING,
            "paused": PrintJobStatus.PAUSED,
            "completed": PrintJobStatus.COMPLETED,
            "failed": PrintJobStatus.FAILED,
            "cancelled": PrintJobStatus.CANCELLED,
        }

        return PrintJob(
            id=data.get("id", ""),
            name=data.get("name", "Unknown"),
            status=status_map.get(data.get("status", ""), PrintJobStatus.PRINTING),
            progress=data.get("progress", 0) * 100,  # API returns 0-1
            layer_current=data.get("current_layer", 0),
            layer_total=data.get("total_layers", 0),
            estimated_time_total=data.get("estimated_time_s", 0),
            time_remaining=data.get("time_remaining_s", 0),
            time_elapsed=data.get("time_elapsed_s", 0),
            resin_type=data.get("resin_type", "Unknown"),
            resin_used_ml=data.get("resin_used_ml", 0),
            started_at=datetime.fromisoformat(data["started_at"])
            if data.get("started_at")
            else None,
            finished_at=datetime.fromisoformat(data["finished_at"])
            if data.get("finished_at")
            else None,
        )

    def _start_polling(self) -> None:
        """Start background polling task."""
        if self._poll_task is None:
            self._poll_task = asyncio.create_task(self._poll_loop())

    async def _poll_loop(self) -> None:
        """Background polling loop with resilience."""
        while True:
            try:
                # Adaptive interval based on failure count
                if self._consecutive_failures >= self._max_failures_before_backoff:
                    interval = self._backoff_interval * min(self._consecutive_failures, 10)
                else:
                    interval = self._poll_interval

                await asyncio.sleep(interval)
                await self._update_state()

                # Reset failures on success
                if self._state and self._state.connected:
                    self._consecutive_failures = 0

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._consecutive_failures += 1
                logger.debug(f"Formlabs poll error (attempt {self._consecutive_failures}): {e}")

                # Emit error callback
                if (
                    self._on_error
                    and self._consecutive_failures >= self._max_failures_before_backoff
                ):
                    self._on_error(f"Connection issues: {e}")

    # === Event Callbacks ===

    def on_state_change(self, callback: Callable[[FormlabsState], None]) -> None:
        """Register state change callback."""
        self._on_state_change = callback

    def on_print_complete(self, callback: Callable[[PrintJob], None]) -> None:
        """Register print completion callback."""
        self._on_print_complete = callback

    def on_error(self, callback: Callable[[str], None]) -> None:
        """Register error callback."""
        self._on_error = callback

    # === Status Methods ===

    def is_printing(self) -> bool:
        """Check if currently printing."""
        return self._state is not None and self._state.state == PrinterState.PRINTING

    def get_print_progress(self) -> float:
        """Get current print progress (0-100)."""
        if self._state and self._state.current_job:
            return self._state.current_job.progress
        return 0.0

    def get_time_remaining(self) -> int:
        """Get estimated time remaining in seconds."""
        if self._state and self._state.current_job:
            return self._state.current_job.time_remaining
        return 0

    def get_resin_level(self) -> float:
        """Get resin tank level percentage."""
        if self._state and self._state.tank:
            return self._state.tank.resin_level_percent
        return 0.0

    async def get_job_history(self, limit: int = 10) -> list[PrintJob]:
        """Get recent print job history."""
        jobs_data = await self._api_get(f"/jobs/?limit={limit}")
        if not jobs_data or "jobs" not in jobs_data:
            return []

        return [self._parse_job(job) for job in jobs_data["jobs"]]

    # === Control Methods ===

    async def pause_print(self) -> bool:
        """Pause current print."""
        if not self.is_printing():
            return False
        result = await self._api_post("/job/pause/")
        return result is not None

    async def resume_print(self) -> bool:
        """Resume paused print."""
        if self._state and self._state.state != PrinterState.PAUSED:
            return False
        result = await self._api_post("/job/resume/")
        return result is not None

    async def cancel_print(self) -> bool:
        """Cancel current print."""
        result = await self._api_post("/job/cancel/")
        return result is not None

    def to_dict(self) -> dict[str, Any]:
        """Export state as dictionary for unified sensory."""
        if not self._state:
            return {"connected": False, "state": "offline"}

        state = self._state
        result: dict[str, Any] = {
            "connected": state.connected,
            "state": state.state.value,
            "serial_number": state.serial_number,
            "firmware_version": state.firmware_version,
            "build_platform_inserted": state.build_platform_inserted,
            "cover_closed": state.cover_closed,
            "resin_temp_c": state.resin_temp_c,
            "chamber_temp_c": state.chamber_temp_c,
            "resin_cartridge_ml": state.resin_cartridge_ml,
            "ip_address": state.ip_address,
            "last_update": state.last_update.isoformat(),
        }

        if state.current_job:
            job = state.current_job
            result["job"] = {
                "name": job.name,
                "status": job.status.value,
                "progress": job.progress,
                "layer": f"{job.layer_current}/{job.layer_total}",
                "time_remaining_s": job.time_remaining,
                "resin_type": job.resin_type,
            }

        if state.tank:
            result["tank"] = {
                "installed": state.tank.installed,
                "resin_type": state.tank.resin_type,
                "level_percent": state.tank.resin_level_percent,
            }

        return result


# Factory function
_instance: FormlabsIntegration | None = None


def get_formlabs() -> FormlabsIntegration | None:
    """Get the global Formlabs integration instance."""
    return _instance


async def start_formlabs(config: SmartHomeConfig) -> FormlabsIntegration | None:
    """Start Formlabs integration."""
    global _instance

    _instance = FormlabsIntegration(config)
    if await _instance.connect():
        return _instance

    _instance = None
    return None
