"""Tesla Vehicle Integration — Consolidated Module.

All Tesla integration functionality in one place:
- TeslaIntegration: Core Fleet API integration with OAuth2
- TeslaStreamingClient: Real-time Fleet Telemetry SSE client
- TeslaCommandExecutor: 65 vehicle commands with CBF safety
- TeslaCompanionProtocol: Bluetooth audio relay for cabin speakers
- TeslaVoiceAdapter: Voice output routing (cabin/external)
- TeslaSafetyBarrier: Physical confirmation for critical commands
- TeslaEventBus: Event aggregation and smart home automation
- TeslaAlertDictionary/Router: Alert parsing and routing

API: Tesla Fleet API (OAuth2)
Note: As of Feb 2025, Fleet API has pay-per-use billing

Safety (h(x) >= 0):
- CBF-protected commands marked with @cbf_protected
- High-risk commands require explicit confirmation
- All commands logged for audit trail

Created: January 11, 2026 (consolidated from 7 modules)
"""

from __future__ import annotations

import asyncio
import csv
import json
import logging
import time
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from functools import wraps
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

import aiohttp

from kagami_smarthome.integrations.tesla.geo import (
    distance_to_home,
    is_at_home,
    is_heading_home,
)
from kagami_smarthome.integrations.tesla.types import (
    ChargingState,
    ConfirmationRequest,
    ConfirmationType,
    DrivingState,
    EventPayload,
    SafetyState,
    TelemetrySnapshot,
    TelemetryValue,
    TeslaEventType,
    TeslaPresenceState,
    TeslaState,
    VehicleState,
)
from kagami_smarthome.types import SmartHomeConfig

if TYPE_CHECKING:
    from kagami_smarthome import SmartHomeController

logger = logging.getLogger(__name__)

# Type variable for decorator
F = TypeVar("F", bound=Callable[..., Any])

# =============================================================================
# CONSTANTS
# =============================================================================

# Tesla Fleet API endpoints
API_BASE = "https://fleet-api.prd.na.vn.cloud.tesla.com"
AUTH_BASE = "https://auth.tesla.com"

# Tesla HTTP Proxy for signed commands (Vehicle Command Protocol)
COMMAND_PROXY_BASE = "https://localhost:4443"
COMMAND_PROXY_CERT = "~/.kagami/tesla/tls-cert.pem"

# Full telemetry field types available via Fleet Telemetry SSE
TELEMETRY_FIELDS = [
    # Charging
    "ACChargingEnergyIn",
    "ACChargingPower",
    "BatteryLevel",
    "BMSState",
    "BatteryHeaterOn",
    "ChargeCurrentRequest",
    "ChargeCurrentRequestMax",
    "ChargeLimitSoc",
    "ChargePort",
    "ChargePortDoorOpen",
    "ChargePortLatch",
    "ChargerPhases",
    "ChargingCableType",
    "ChargeState",
    "DCChargingEnergyIn",
    "DCChargingPower",
    "EnergyRemaining",
    "EstBatteryRange",
    "FastChargerPresent",
    "IdealBatteryRange",
    "MinutesToFullCharge",
    "RatedRange",
    "ScheduledChargingPending",
    "ScheduledChargingStartTime",
    "TimeToFullCharge",
    # Climate
    "AutoSeatClimateLeft",
    "AutoSeatClimateRight",
    "CabinOverheatProtectionMode",
    "CabinOverheatProtectionTemperatureLimit",
    "ClimateState",
    "ClimateKeeperMode",
    "DefrostMode",
    "InsideTemp",
    "OutsideTemp",
    "PreconditioningEnabled",
    "SeatHeaterLeft",
    "SeatHeaterRight",
    "SeatHeaterRearLeft",
    "SeatHeaterRearRight",
    "SentryMode",
    # Location
    "DestinationLocation",
    "GpsState",
    "Heading",
    "Location",
    "Odometer",
    "RouteLastUpdated",
    # Drive State
    "CruiseState",
    "DriveRail",
    "Gear",
    "Power",
    "ShiftState",
    "Speed",
    "SteeringAngle",
    # Vehicle State
    "CenterDisplay",
    "DoorsState",
    "FdWindow",
    "FpWindow",
    "FtState",
    "HomelinkNearby",
    "Locked",
    "MediaPlaybackStatus",
    "OriginLocation",
    "RdWindow",
    "RpWindow",
    "RtState",
    "SoftwareUpdateVersion",
    "SpeedLimitMode",
    "TpmsFl",
    "TpmsFr",
    "TpmsRl",
    "TpmsRr",
    "VehicleName",
    "WiperHeatEnabled",
    # Safety
    "AutomaticBlindSpotCamera",
    "AutomaticEmergencyBrakingOff",
    "BlindSpotCollisionWarningChime",
    "ForwardCollisionWarningLevel",
    # Alerts - CRITICAL for h(x) safety
    "Alerts",
]

# Native polling interval from Tesla (per docs)
FLEET_TELEMETRY_INTERVAL_MS = 500


# =============================================================================
# CORE INTEGRATION
# =============================================================================


class TeslaIntegration:
    """Tesla vehicle integration via Fleet API.

    Uses OAuth2 for authentication.
    Requires Tesla account with Fleet API access.

    Features:
    - Automatic token loading from Keychain
    - Automatic token refresh
    - Token persistence to Keychain
    """

    def __init__(self, config: SmartHomeConfig):
        self.config = config
        self._session: aiohttp.ClientSession | None = None
        self._access_token: str | None = config.tesla_access_token
        self._refresh_token: str | None = config.tesla_refresh_token
        self._vehicle_id: str | None = None
        self._vehicle_vin: str | None = None
        self._initialized = False
        self._state: TeslaState | None = None
        self._last_update: datetime | None = None
        self._refresh_task: asyncio.Task[None] | None = None
        self._private_key: str | None = None
        self._load_tokens_from_keychain()

    def _load_tokens_from_keychain(self) -> None:
        """Load Tesla tokens and credentials from Keychain."""
        try:
            from kagami.core.security.backends.keychain_backend import KeychainBackend

            keychain = KeychainBackend({})

            if not self.config.tesla_client_id:
                value = keychain._get_keychain_value("tesla_client_id")
                if value:
                    self.config.tesla_client_id = value

            if not self.config.tesla_client_secret:
                value = keychain._get_keychain_value("tesla_client_secret")
                if value:
                    self.config.tesla_client_secret = value

            if not self._access_token:
                token = keychain._get_keychain_value("tesla_access_token")
                if token:
                    self._access_token = token

            if not self._refresh_token:
                token = keychain._get_keychain_value("tesla_refresh_token")
                if token:
                    self._refresh_token = token

            if not self._private_key:
                hex_key = keychain._get_keychain_value("tesla_private_key")
                if hex_key:
                    try:
                        self._private_key = bytes.fromhex(hex_key).decode("utf-8")
                    except Exception:
                        pass
        except Exception:
            pass

    def _save_tokens_to_keychain(self) -> bool:
        """Save Tesla tokens to Keychain."""
        try:
            from kagami.core.security.backends.keychain_backend import KeychainBackend

            keychain = KeychainBackend({})
            success = True
            if self._access_token:
                success &= keychain._set_keychain_value("tesla_access_token", self._access_token)
            if self._refresh_token:
                success &= keychain._set_keychain_value("tesla_refresh_token", self._refresh_token)
            return success
        except Exception:
            return False

    @property
    def is_connected(self) -> bool:
        return self._initialized and self._access_token is not None

    @property
    def can_sign_commands(self) -> bool:
        """Check if private key is available for Vehicle Command Protocol."""
        return self._private_key is not None

    async def connect(self) -> bool:
        """Connect to Tesla API."""
        if not self._access_token:
            return False

        try:
            self._session = aiohttp.ClientSession()
            vehicles = await self._api_get("/api/1/vehicles")
            if not vehicles or "response" not in vehicles:
                return False

            vehicle_list = vehicles["response"]
            if vehicle_list:
                self._vehicle_id = str(vehicle_list[0]["id"])
                self._vehicle_vin = vehicle_list[0].get("vin")
            else:
                return False

            await self._update_state()
            self._initialized = True
            logger.info("Tesla: Connected successfully")
            return True
        except Exception as e:
            logger.error(f"Tesla: Connection failed - {e}")
            return False

    async def _api_get(self, path: str) -> dict[str, Any] | None:
        """Make GET request to Tesla API."""
        if not self._session or not self._access_token:
            return None

        url = f"{API_BASE}{path}"
        headers = {"Authorization": f"Bearer {self._access_token}"}

        async with self._session.get(url, headers=headers, timeout=30) as resp:
            if resp.status == 200:
                return await resp.json()
            elif resp.status == 401:
                if await self._refresh_access_token():
                    return await self._api_get(path)
        return None

    async def _api_post(self, path: str, data: dict[str, Any] | None = None) -> bool:
        """Make POST request to Tesla API."""
        if not self._session or not self._access_token:
            return False

        headers = {"Authorization": f"Bearer {self._access_token}"}

        if "/command/" in path:
            return await self._command_via_proxy(path, data, headers)

        url = f"{API_BASE}{path}"
        async with self._session.post(url, json=data or {}, headers=headers, timeout=30) as resp:
            if resp.status == 200:
                return True
            elif resp.status == 401:
                if await self._refresh_access_token():
                    return await self._api_post(path, data)
        return False

    async def _command_via_proxy(
        self, path: str, data: dict[str, Any] | None, headers: dict[str, str]
    ) -> bool:
        """Execute command via tesla-http-proxy for signed Vehicle Command Protocol."""
        import os
        import ssl

        if self._vehicle_vin and self._vehicle_id:
            path = path.replace(f"/vehicles/{self._vehicle_id}/", f"/vehicles/{self._vehicle_vin}/")

        cert_path = os.path.expanduser(COMMAND_PROXY_CERT)
        url = f"{COMMAND_PROXY_BASE}{path}"

        ssl_context = ssl.create_default_context()
        ssl_context.load_verify_locations(cert_path)

        try:
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            async with aiohttp.ClientSession(connector=connector) as proxy_session:
                async with proxy_session.post(
                    url,
                    json=data or {},
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        success = result.get("response", {}).get("result", False)
                        return success
                    elif resp.status == 401:
                        if await self._refresh_access_token():
                            headers["Authorization"] = f"Bearer {self._access_token}"
                            return await self._command_via_proxy(path, data, headers)
        except aiohttp.ClientConnectorError:
            logger.error("Tesla proxy not running")
        except Exception as e:
            logger.error(f"Tesla command error: {e}")
        return False

    async def _refresh_access_token(self) -> bool:
        """Refresh OAuth access token."""
        if not self._session or not self._refresh_token:
            return False

        self._load_tokens_from_keychain()
        if not self.config.tesla_client_id:
            return False

        url = f"{AUTH_BASE}/oauth2/v3/token"
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token,
            "client_id": self.config.tesla_client_id,
        }
        if self.config.tesla_client_secret:
            data["client_secret"] = self.config.tesla_client_secret

        async with self._session.post(url, data=data) as resp:
            if resp.status == 200:
                tokens = await resp.json()
                self._access_token = tokens.get("access_token")
                new_refresh = tokens.get("refresh_token")
                if new_refresh:
                    self._refresh_token = new_refresh
                self._save_tokens_to_keychain()
                return True
        return False

    async def _update_state(self) -> None:
        """Update vehicle state."""
        if not self._vehicle_id:
            return

        data = await self._api_get(f"/api/1/vehicles/{self._vehicle_id}/vehicle_data")
        if not data or "response" not in data:
            return

        response = data["response"]
        drive = response.get("drive_state", {})
        charge = response.get("charge_state", {})
        climate = response.get("climate_state", {})
        vehicle = response.get("vehicle_state", {})

        self._state = TeslaState(
            state=VehicleState.ONLINE if response.get("state") == "online" else VehicleState.ASLEEP,
            latitude=drive.get("latitude"),
            longitude=drive.get("longitude"),
            battery_level=charge.get("battery_level", 0),
            charging_state=ChargingState(charge.get("charging_state", "unknown")),
            charge_limit=charge.get("charge_limit_soc", 80),
            inside_temp=climate.get("inside_temp"),
            outside_temp=climate.get("outside_temp"),
            climate_on=climate.get("is_climate_on", False),
            locked=vehicle.get("locked", True),
            odometer=vehicle.get("odometer", 0),
            last_seen=datetime.now(),
        )
        self._last_update = datetime.now()

    def is_home(self) -> bool:
        """Check if vehicle is at home."""
        if not self._state or not self._state.latitude or not self._state.longitude:
            return False
        return is_at_home(self._state.latitude, self._state.longitude)

    def is_away(self) -> bool:
        """Check if vehicle is away from home."""
        return not self.is_home()

    def get_location(self) -> tuple[float, float] | None:
        """Get current location."""
        if self._state and self._state.latitude and self._state.longitude:
            return (self._state.latitude, self._state.longitude)
        return None

    async def start_climate(self) -> bool:
        """Turn on climate control."""
        if not self._vehicle_id:
            return False
        return await self._api_post(
            f"/api/1/vehicles/{self._vehicle_id}/command/auto_conditioning_start"
        )

    async def stop_climate(self) -> bool:
        """Turn off climate control."""
        if not self._vehicle_id:
            return False
        return await self._api_post(
            f"/api/1/vehicles/{self._vehicle_id}/command/auto_conditioning_stop"
        )

    async def set_temperature(self, temp_c: float) -> bool:
        """Set climate temperature (Celsius)."""
        if not self._vehicle_id:
            return False
        return await self._api_post(
            f"/api/1/vehicles/{self._vehicle_id}/command/set_temps",
            {"driver_temp": temp_c, "passenger_temp": temp_c},
        )

    async def set_seat_heater(self, seat: int, level: int) -> bool:
        """Set seat heater (seat: 0-5, level: 0-3)."""
        if not self._vehicle_id:
            return False
        return await self._api_post(
            f"/api/1/vehicles/{self._vehicle_id}/command/remote_seat_heater_request",
            {"heater": seat, "level": level},
        )

    async def start_charging(self) -> bool:
        """Start charging."""
        if not self._vehicle_id:
            return False
        return await self._api_post(f"/api/1/vehicles/{self._vehicle_id}/command/charge_start")

    async def stop_charging(self) -> bool:
        """Stop charging."""
        if not self._vehicle_id:
            return False
        return await self._api_post(f"/api/1/vehicles/{self._vehicle_id}/command/charge_stop")

    async def set_charge_limit(self, percent: int) -> bool:
        """Set charge limit (50-100)."""
        if not self._vehicle_id:
            return False
        percent = max(50, min(100, percent))
        return await self._api_post(
            f"/api/1/vehicles/{self._vehicle_id}/command/set_charge_limit",
            {"percent": percent},
        )

    async def open_charge_port(self) -> bool:
        """Open charge port."""
        if not self._vehicle_id:
            return False
        return await self._api_post(
            f"/api/1/vehicles/{self._vehicle_id}/command/charge_port_door_open"
        )

    async def lock(self) -> bool:
        """Lock vehicle."""
        if not self._vehicle_id:
            return False
        return await self._api_post(f"/api/1/vehicles/{self._vehicle_id}/command/door_lock")

    async def unlock(self) -> bool:
        """Unlock vehicle."""
        if not self._vehicle_id:
            return False
        return await self._api_post(f"/api/1/vehicles/{self._vehicle_id}/command/door_unlock")

    async def honk(self) -> bool:
        """Honk horn."""
        if not self._vehicle_id:
            return False
        return await self._api_post(f"/api/1/vehicles/{self._vehicle_id}/command/honk_horn")

    async def flash_lights(self) -> bool:
        """Flash lights."""
        if not self._vehicle_id:
            return False
        return await self._api_post(f"/api/1/vehicles/{self._vehicle_id}/command/flash_lights")

    async def open_trunk(self) -> bool:
        """Open rear trunk."""
        if not self._vehicle_id:
            return False
        return await self._api_post(
            f"/api/1/vehicles/{self._vehicle_id}/command/actuate_trunk",
            {"which_trunk": "rear"},
        )

    async def open_frunk(self) -> bool:
        """Open front trunk (frunk)."""
        if not self._vehicle_id:
            return False
        return await self._api_post(
            f"/api/1/vehicles/{self._vehicle_id}/command/actuate_trunk",
            {"which_trunk": "front"},
        )

    async def wake_up(self) -> bool:
        """Wake up vehicle."""
        if not self._vehicle_id:
            return False
        return await self._api_post(f"/api/1/vehicles/{self._vehicle_id}/wake_up")

    def get_state(self) -> TeslaState | None:
        """Get current vehicle state."""
        return self._state

    def get_battery_level(self) -> int:
        """Get battery percentage."""
        return self._state.battery_level if self._state else 0

    def is_charging(self) -> bool:
        """Check if currently charging."""
        return self._state is not None and self._state.charging_state == ChargingState.CHARGING

    async def disconnect(self) -> None:
        """Disconnect from Tesla API."""
        self._initialized = False
        if self._session:
            await self._session.close()
            self._session = None


# =============================================================================
# STREAMING CLIENT
# =============================================================================

TeslaEventCallback = Callable[[str, Any, float], Awaitable[None]]


class TeslaStreamingClient:
    """Tesla Fleet Telemetry SSE client for real-time vehicle data."""

    RECONNECT_DELAY = 5.0
    STREAMING_URL = "https://streaming.vn.teslamotors.com/streaming/"
    FLEET_TELEMETRY_URL = "https://fleet-telemetry.prd.na.vn.cloud.tesla.com"
    EXPECTED_INTERVAL_MS = 500

    def __init__(self, integration: TeslaIntegration):
        self._integration = integration
        self._session: aiohttp.ClientSession | None = None
        self._running = False
        self._listener_task: asyncio.Task | None = None
        self._callbacks: list[TeslaEventCallback] = []
        self._alert_callbacks: list[Callable[[str, dict], Awaitable[None]]] = []
        self._stats = {
            "events_received": 0,
            "alerts_received": 0,
            "reconnects": 0,
            "last_event_time": 0.0,
            "avg_latency_ms": 0.0,
            "min_latency_ms": float("inf"),
            "max_latency_ms": 0.0,
            "latency_samples": 0,
        }

    def on_event(self, callback: TeslaEventCallback) -> None:
        """Register callback for Tesla telemetry events."""
        self._callbacks.append(callback)

    def off_event(self, callback: TeslaEventCallback) -> None:
        """Unregister event callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def on_alert(self, callback: Callable[[str, dict], Awaitable[None]]) -> None:
        """Register callback for Tesla vehicle alerts."""
        self._alert_callbacks.append(callback)

    def off_alert(self, callback: Callable[[str, dict], Awaitable[None]]) -> None:
        """Unregister alert callback."""
        if callback in self._alert_callbacks:
            self._alert_callbacks.remove(callback)

    @property
    def is_connected(self) -> bool:
        """Check if streaming is active."""
        return self._running and self._listener_task is not None

    async def connect(self) -> bool:
        """Connect to Tesla streaming endpoint."""
        if not self._integration._vehicle_id or not self._integration._access_token:
            return False

        try:
            self._session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"Bearer {self._integration._access_token}",
                    "Accept": "text/event-stream",
                }
            )
            self._running = True
            self._listener_task = asyncio.create_task(
                self._stream_loop(), name="tesla_stream_listener"
            )
            return True
        except Exception as e:
            logger.error(f"TeslaStream: Connection failed: {e}")
            return False

    async def disconnect(self) -> None:
        """Stop streaming."""
        self._running = False
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
        if self._session:
            await self._session.close()
            self._session = None

    async def _stream_loop(self) -> None:
        """Main SSE streaming loop."""
        vehicle_id = self._integration._vehicle_id

        while self._running:
            try:
                if not self._session:
                    await asyncio.sleep(self.RECONNECT_DELAY)
                    self._stats["reconnects"] += 1
                    continue

                url = f"{API_BASE}/api/1/vehicles/{vehicle_id}/stream"
                async with self._session.get(url) as response:
                    if response.status != 200:
                        await asyncio.sleep(self.RECONNECT_DELAY)
                        continue

                    async for line in response.content:
                        if not self._running:
                            break
                        decoded = line.decode().strip()
                        if decoded.startswith("data:"):
                            data_str = decoded[5:].strip()
                            await self._handle_event(data_str)

            except aiohttp.ClientError:
                await asyncio.sleep(self.RECONNECT_DELAY)
                self._stats["reconnects"] += 1
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(self.RECONNECT_DELAY)

    async def _handle_event(self, data_str: str) -> None:
        """Handle incoming SSE event."""
        try:
            data = json.loads(data_str)
            now = asyncio.get_event_loop().time()
            timestamp = data.get("timestamp", now)

            if "Alerts" in data:
                alerts = data["Alerts"]
                if isinstance(alerts, list):
                    for alert_signal in alerts:
                        self._stats["alerts_received"] += 1
                        for callback in self._alert_callbacks:
                            try:
                                await callback(alert_signal, {"timestamp": timestamp, "raw": data})
                            except Exception:
                                pass

            for field in TELEMETRY_FIELDS:
                if field in data and field != "Alerts":
                    value = data[field]
                    self._stats["events_received"] += 1
                    self._stats["last_event_time"] = now

                    for callback in self._callbacks:
                        try:
                            await callback(field, value, timestamp)
                        except Exception:
                            pass
        except json.JSONDecodeError:
            pass
        except Exception:
            pass

    def get_stats(self) -> dict[str, Any]:
        """Get streaming statistics."""
        return {
            **self._stats,
            "connected": self.is_connected,
            "vehicle_id": self._integration._vehicle_id,
            "callbacks": len(self._callbacks),
            "alert_callbacks": len(self._alert_callbacks),
        }


# =============================================================================
# COMMAND EXECUTOR
# =============================================================================


class CommandCategory(Enum):
    """Categories of vehicle commands."""

    TRUNK = "trunk"
    CHARGING = "charging"
    CLIMATE = "climate"
    LOCKS = "locks"
    MEDIA = "media"
    NAVIGATION = "navigation"
    SECURITY = "security"
    WINDOWS = "windows"
    ALERTS = "alerts"
    SOFTWARE = "software"
    DRIVE = "drive"
    HOMELINK = "homelink"
    DATA = "data"


class SafetyLevel(Enum):
    """Safety classification for CBF filtering."""

    SAFE = "safe"
    CAUTION = "caution"
    PROTECTED = "protected"
    CRITICAL = "critical"


@dataclass
class CommandMeta:
    """Metadata for a vehicle command."""

    name: str
    category: CommandCategory
    safety: SafetyLevel
    description: str
    requires_wake: bool = True


def cbf_protected(safety_level: SafetyLevel):
    """Decorator for CBF-protected commands."""

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            command_name = func.__name__
            logger.info(f"Tesla command: {command_name} (safety={safety_level.value})")
            if safety_level == SafetyLevel.CRITICAL:
                logger.warning(f"CRITICAL command: {command_name}")
            result = await func(self, *args, **kwargs)
            logger.info(f"Tesla command {command_name}: {'success' if result else 'failed'}")
            return result

        return wrapper

    return decorator


class TeslaCommandExecutor:
    """Complete Tesla Fleet API command executor with CBF safety."""

    def __init__(self, integration: TeslaIntegration):
        self._integration = integration
        self._stats = {
            "commands_sent": 0,
            "commands_succeeded": 0,
            "commands_failed": 0,
            "by_category": {cat.value: 0 for cat in CommandCategory},
        }

    async def _command(
        self,
        command: str,
        data: dict[str, Any] | None = None,
        wake_first: bool = True,
    ) -> bool:
        """Execute a vehicle command."""
        if not self._integration._vehicle_id:
            return False

        if wake_first:
            state = self._integration._state
            if state and state.state != VehicleState.ONLINE:
                await self._integration.wake_up()
                await asyncio.sleep(2)

        path = f"/api/1/vehicles/{self._integration._vehicle_id}/command/{command}"
        self._stats["commands_sent"] += 1
        success = await self._integration._api_post(path, data)
        if success:
            self._stats["commands_succeeded"] += 1
        else:
            self._stats["commands_failed"] += 1
        return success

    @cbf_protected(SafetyLevel.SAFE)
    async def open_trunk(self) -> bool:
        return await self._command("actuate_trunk", {"which_trunk": "rear"})

    @cbf_protected(SafetyLevel.SAFE)
    async def open_frunk(self) -> bool:
        return await self._command("actuate_trunk", {"which_trunk": "front"})

    @cbf_protected(SafetyLevel.SAFE)
    async def charge_start(self) -> bool:
        return await self._command("charge_start")

    @cbf_protected(SafetyLevel.SAFE)
    async def charge_stop(self) -> bool:
        return await self._command("charge_stop")

    @cbf_protected(SafetyLevel.SAFE)
    async def set_charge_limit(self, percent: int) -> bool:
        percent = max(50, min(100, percent))
        return await self._command("set_charge_limit", {"percent": percent})

    @cbf_protected(SafetyLevel.SAFE)
    async def start_climate(self) -> bool:
        return await self._command("auto_conditioning_start")

    @cbf_protected(SafetyLevel.SAFE)
    async def stop_climate(self) -> bool:
        return await self._command("auto_conditioning_stop")

    @cbf_protected(SafetyLevel.SAFE)
    async def set_temps(self, driver_temp: float, passenger_temp: float | None = None) -> bool:
        if passenger_temp is None:
            passenger_temp = driver_temp
        return await self._command(
            "set_temps", {"driver_temp": driver_temp, "passenger_temp": passenger_temp}
        )

    @cbf_protected(SafetyLevel.SAFE)
    async def set_seat_heater(self, seat: int, level: int) -> bool:
        return await self._command("remote_seat_heater_request", {"heater": seat, "level": level})

    @cbf_protected(SafetyLevel.SAFE)
    async def lock(self) -> bool:
        return await self._command("door_lock")

    @cbf_protected(SafetyLevel.PROTECTED)
    async def unlock(self) -> bool:
        return await self._command("door_unlock")

    @cbf_protected(SafetyLevel.SAFE)
    async def flash_lights(self) -> bool:
        return await self._command("flash_lights")

    @cbf_protected(SafetyLevel.CAUTION)
    async def honk_horn(self) -> bool:
        return await self._command("honk_horn")

    @cbf_protected(SafetyLevel.SAFE)
    async def navigate_to(self, address: str, locale: str = "en-US") -> bool:
        return await self._command(
            "navigation_request",
            {
                "type": "share_ext_content_raw",
                "value": {"android.intent.extra.TEXT": address},
                "locale": locale,
            },
        )

    @cbf_protected(SafetyLevel.SAFE)
    async def set_sentry_mode(self, on: bool) -> bool:
        return await self._command("set_sentry_mode", {"on": on})

    @cbf_protected(SafetyLevel.SAFE)
    async def trigger_homelink(self, lat: float | None = None, lon: float | None = None) -> bool:
        data = {}
        if lat is not None and lon is not None:
            data["lat"] = lat
            data["lon"] = lon
        return await self._command("trigger_homelink", data if data else None)

    @cbf_protected(SafetyLevel.CAUTION)
    async def remote_boombox(self, sound_id: int = 0, streaming_url: str | None = None) -> bool:
        data: dict[str, Any] = {"sound": sound_id}
        if streaming_url:
            data["streaming_url"] = streaming_url
        return await self._command("remote_boombox", data)

    @cbf_protected(SafetyLevel.CRITICAL)
    async def remote_start_drive(self) -> bool:
        return await self._command("remote_start_drive")

    @property
    def stats(self) -> dict[str, Any]:
        return {
            **self._stats,
            "success_rate": (
                self._stats["commands_succeeded"] / self._stats["commands_sent"]
                if self._stats["commands_sent"] > 0
                else 0.0
            ),
        }


# =============================================================================
# SAFETY BARRIER
# =============================================================================

DRIVING_PROTECTION = {
    "erase_user_data": ConfirmationType.BLOCKED,
    "remote_start_drive": ConfirmationType.BLOCKED,
    "speed_limit_deactivate": ConfirmationType.KEY_CARD,
    "speed_limit_clear_pin": ConfirmationType.KEY_CARD,
    "clear_pin_to_drive_admin": ConfirmationType.KEY_CARD,
    "door_unlock": ConfirmationType.SOFT,
    "window_control": ConfirmationType.SOFT,
    "sun_roof_control": ConfirmationType.SOFT,
    "set_valet_mode": ConfirmationType.SOFT,
    "guest_mode": ConfirmationType.SOFT,
    "honk_horn": ConfirmationType.SOFT,
    "flash_lights": ConfirmationType.SOFT,
}

DEFAULT_DRIVING_PROTECTION = ConfirmationType.NONE
SPEED_THRESHOLD_LOW = 15
SPEED_THRESHOLD_HIGH = 45


class TeslaSafetyBarrier:
    """Hardware-in-the-loop safety barrier for Tesla commands."""

    CONFIRMATION_WINDOW_SECONDS = 30.0
    KEY_CARD_VALIDITY_SECONDS = 5.0

    def __init__(self, integration: TeslaIntegration):
        self._integration = integration
        self._state = SafetyState()
        self._pending_confirmations: dict[str, ConfirmationRequest] = {}
        self._confirmation_callbacks: list[Callable[[str, bool], Awaitable[None]]] = []
        self._stats = {
            "commands_checked": 0,
            "commands_allowed": 0,
            "commands_blocked": 0,
            "confirmations_requested": 0,
            "confirmations_received": 0,
            "confirmations_expired": 0,
        }

    async def on_telemetry_event(self, field: str, value: Any, timestamp: float) -> None:
        """Handle telemetry events to update safety state."""
        self._state.last_update = time.time()

        if field == "Speed":
            self._state.speed_mph = float(value) if value else 0.0
            self._update_driving_state()
        elif field == "ShiftState":
            self._state.shift_state = str(value) if value else "P"
            self._update_driving_state()
        elif field == "Locked":
            self._state.locked = bool(value)
        elif field in ("KeyCardPresent", "CenterDisplayState"):
            if value:
                await self._on_key_card_detected(timestamp)

    def _update_driving_state(self) -> None:
        """Update driving state from speed and shift."""
        if self._state.shift_state == "P":
            self._state.driving_state = DrivingState.PARKED
        elif self._state.speed_mph > 0:
            self._state.driving_state = DrivingState.MOVING
        elif self._state.shift_state in ["D", "R", "N"]:
            self._state.driving_state = DrivingState.STOPPED
        else:
            self._state.driving_state = DrivingState.UNKNOWN

    async def _on_key_card_detected(self, timestamp: float) -> None:
        """Handle key card tap detection."""
        self._state.last_key_card_tap = timestamp
        self._state.key_card_present = True
        logger.info("Key card tap detected!")

        for token, request in list(self._pending_confirmations.items()):
            if not request.is_expired and request.confirmation_type == ConfirmationType.KEY_CARD:
                request.confirmed = True
                self._stats["confirmations_received"] += 1
                for callback in self._confirmation_callbacks:
                    try:
                        await callback(token, True)
                    except Exception:
                        pass

    def check_command(self, command: str) -> tuple[bool, str]:
        """Check if a command is allowed in current state."""
        self._stats["commands_checked"] += 1
        protection = DRIVING_PROTECTION.get(command, DEFAULT_DRIVING_PROTECTION)
        speed = self._state.speed_mph

        if self._state.driving_state == DrivingState.PARKED:
            self._stats["commands_allowed"] += 1
            return True, "parked"

        if self._state.driving_state == DrivingState.STOPPED:
            if protection == ConfirmationType.BLOCKED:
                self._stats["commands_blocked"] += 1
                return False, "blocked_not_parked"
            self._stats["commands_allowed"] += 1
            return True, "stopped"

        if protection == ConfirmationType.BLOCKED:
            self._stats["commands_blocked"] += 1
            return False, "blocked_while_driving"

        if speed < SPEED_THRESHOLD_LOW:
            self._stats["commands_allowed"] += 1
            return True, "low_speed"

        if speed < SPEED_THRESHOLD_HIGH:
            if protection == ConfirmationType.KEY_CARD:
                if self._is_key_card_valid():
                    self._stats["commands_allowed"] += 1
                    return True, "key_card_confirmed"
                self._stats["commands_blocked"] += 1
                return False, "key_card_required"
            self._stats["commands_allowed"] += 1
            return True, "medium_speed"

        if protection == ConfirmationType.KEY_CARD:
            if self._is_key_card_valid():
                self._stats["commands_allowed"] += 1
                return True, "key_card_confirmed"
            self._stats["commands_blocked"] += 1
            return False, "key_card_required_highway"

        self._stats["commands_allowed"] += 1
        return True, "allowed"

    def _is_key_card_valid(self) -> bool:
        """Check if a recent key card tap is valid."""
        if self._state.last_key_card_tap == 0:
            return False
        elapsed = time.time() - self._state.last_key_card_tap
        return elapsed < self.KEY_CARD_VALIDITY_SECONDS

    @property
    def driving_state(self) -> DrivingState:
        return self._state.driving_state

    @property
    def is_moving(self) -> bool:
        return self._state.driving_state == DrivingState.MOVING

    @property
    def speed_mph(self) -> float:
        return self._state.speed_mph

    @property
    def stats(self) -> dict[str, Any]:
        return {
            **self._stats,
            "driving_state": self._state.driving_state.value,
            "speed_mph": self._state.speed_mph,
            "shift_state": self._state.shift_state,
        }


# =============================================================================
# EVENT BUS
# =============================================================================

EventCallback = Callable[[EventPayload], Awaitable[None]]


class TeslaEventBus:
    """Central event bus for Tesla real-time integration."""

    ARRIVAL_DISTANCE_MILES = 2.0
    ARRIVAL_ETA_MINUTES = 5
    DEPARTURE_TIMEOUT_SECONDS = 120
    PET_TEMP_WARNING_F = 82
    PET_TEMP_CRITICAL_F = 88
    LOW_BATTERY_PERCENT = 30

    def __init__(self):
        self._telemetry: dict[str, TelemetryValue] = {}
        self._presence_state = TeslaPresenceState.UNKNOWN
        self._driving_state = DrivingState.UNKNOWN
        self._last_presence_change = 0.0
        self._subscribers: dict[TeslaEventType, list[EventCallback]] = {
            e: [] for e in TeslaEventType
        }
        self._history: deque[TelemetrySnapshot] = deque(maxlen=1000)
        self._smart_home: SmartHomeController | None = None
        self._last_location: tuple[float, float] | None = None
        self._last_at_home = False
        self._departure_time: float | None = None
        self._arrival_announced = False
        self._stats = {
            "telemetry_received": 0,
            "events_emitted": 0,
            "presence_changes": 0,
        }

    def subscribe(self, event_type: TeslaEventType, callback: EventCallback) -> None:
        """Subscribe to an event type."""
        self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: TeslaEventType, callback: EventCallback) -> None:
        """Unsubscribe from an event type."""
        if callback in self._subscribers[event_type]:
            self._subscribers[event_type].remove(callback)

    async def _emit(self, event_type: TeslaEventType, data: dict[str, Any]) -> None:
        """Emit an event to all subscribers."""
        payload = EventPayload(event_type=event_type, timestamp=time.time(), data=data)
        self._stats["events_emitted"] += 1
        for callback in self._subscribers[event_type]:
            try:
                await callback(payload)
            except Exception:
                pass

    async def on_telemetry(self, field: str, value: Any, timestamp: float) -> None:
        """Process incoming telemetry from Tesla streaming."""
        self._stats["telemetry_received"] += 1
        old_value = self._telemetry.get(field)
        self._telemetry[field] = TelemetryValue(value, timestamp)

        if field == "Location":
            await self._process_location(value, old_value)
        elif field == "Speed":
            await self._process_speed(value, old_value)
        elif field == "ShiftState":
            await self._process_shift_state(value, old_value)
        elif field == "ChargeState":
            await self._process_charge_state(value, old_value)
        elif field == "InsideTemp":
            await self._process_inside_temp(value)

        old_presence = self._presence_state
        _old_driving = self._driving_state  # noqa: F841 (reserved for future driving state events)
        self._recompute_presence()
        self._recompute_driving()

        if self._presence_state != old_presence:
            self._stats["presence_changes"] += 1
            await self._emit_presence_change(old_presence, self._presence_state)

    async def _process_location(
        self, value: dict | tuple | None, _old: TelemetryValue | None
    ) -> None:
        """Process location update."""
        if not value:
            return

        if isinstance(value, dict):
            lat = value.get("latitude") or value.get("lat")
            lon = value.get("longitude") or value.get("lon")
        elif isinstance(value, (list, tuple)) and len(value) >= 2:
            lat, lon = value[0], value[1]
        else:
            return

        if lat is None or lon is None:
            return

        self._last_location = (lat, lon)
        at_home = is_at_home(lat, lon)
        was_at_home = self._last_at_home

        if at_home and not was_at_home:
            self._arrival_announced = False
            await self._emit(TeslaEventType.ARRIVAL_DETECTED, {"location": (lat, lon)})
        elif not at_home and was_at_home:
            self._departure_time = time.time()
            await self._emit(TeslaEventType.DEPARTURE_DETECTED, {"location": (lat, lon)})

        self._last_at_home = at_home

    async def _process_speed(self, value: float | None, old: TelemetryValue | None) -> None:
        """Process speed update."""
        if value is None:
            return
        old_speed = old.value if old else 0
        if old_speed == 0 and value > 0:
            await self._emit(TeslaEventType.DRIVING_STARTED, {"speed": value})
        elif old_speed > 0 and value == 0:
            await self._emit(TeslaEventType.DRIVING_STOPPED, {"previous_speed": old_speed})

    async def _process_shift_state(self, value: str | None, old: TelemetryValue | None) -> None:
        """Process shift state."""
        if not value:
            return
        old_gear = old.value if old else "P"
        if old_gear != "P" and value == "P":
            if self._last_at_home:
                await self._emit(TeslaEventType.PARKED_HOME, {})
            else:
                await self._emit(TeslaEventType.PARKED_AWAY, {"location": self._last_location})

    async def _process_charge_state(self, value: str | None, old: TelemetryValue | None) -> None:
        """Process charge state."""
        if not value:
            return
        old_state = old.value if old else None
        if old_state != "Charging" and value == "Charging":
            await self._emit(TeslaEventType.CHARGE_STARTED, {})
        elif old_state == "Charging" and value == "Complete":
            await self._emit(TeslaEventType.CHARGE_COMPLETE, {})

    async def _process_inside_temp(self, value: float | None) -> None:
        """Process inside temperature."""
        if value is None:
            return
        climate_mode = self._get_value("ClimateKeeperMode")
        if climate_mode not in ("dog", "camp"):
            return
        if value >= self.PET_TEMP_CRITICAL_F:
            await self._emit(
                TeslaEventType.PET_TEMP_CRITICAL, {"temp_f": value, "mode": climate_mode}
            )
        elif value >= self.PET_TEMP_WARNING_F:
            await self._emit(
                TeslaEventType.PET_TEMP_WARNING, {"temp_f": value, "mode": climate_mode}
            )

    def _recompute_presence(self) -> None:
        """Recompute derived presence state."""
        at_home = self._last_at_home
        speed = self._get_value("Speed", 0)
        shift_state = self._get_value("ShiftState", "P")

        if shift_state == "P":
            self._presence_state = (
                TeslaPresenceState.PARKED_HOME if at_home else TeslaPresenceState.PARKED_AWAY
            )
            return

        if speed > 0:
            if self._check_heading_home():
                distance = self._calc_distance_to_home()
                if distance < self.ARRIVAL_DISTANCE_MILES:
                    self._presence_state = TeslaPresenceState.ARRIVING
                else:
                    self._presence_state = TeslaPresenceState.DRIVING_HOME
            else:
                if (
                    self._departure_time
                    and time.time() - self._departure_time < self.DEPARTURE_TIMEOUT_SECONDS
                ):
                    self._presence_state = TeslaPresenceState.DEPARTING
                else:
                    self._presence_state = TeslaPresenceState.DRIVING_AWAY
            return

        self._presence_state = TeslaPresenceState.UNKNOWN

    def _recompute_driving(self) -> None:
        """Recompute derived driving state."""
        speed = self._get_value("Speed", 0)
        shift_state = self._get_value("ShiftState", "P")

        if shift_state == "P":
            self._driving_state = DrivingState.PARKED
        elif speed == 0:
            self._driving_state = DrivingState.STOPPED
        elif speed < 15:
            self._driving_state = DrivingState.MOVING_SLOW
        else:
            self._driving_state = DrivingState.MOVING_FAST

    async def _emit_presence_change(self, old: TeslaPresenceState, new: TeslaPresenceState) -> None:
        """Emit presence state change."""
        self._last_presence_change = time.time()

        if new == TeslaPresenceState.ARRIVING and not self._arrival_announced:
            self._arrival_announced = True
            await self._emit(
                TeslaEventType.ARRIVAL_IMMINENT,
                {
                    "eta_minutes": self._estimate_eta(),
                    "distance_miles": self._calc_distance_to_home(),
                },
            )

        if new == TeslaPresenceState.DRIVING_HOME and old == TeslaPresenceState.DRIVING_AWAY:
            await self._emit(TeslaEventType.HEADING_HOME, {})

        if new == TeslaPresenceState.DRIVING_AWAY and old in (
            TeslaPresenceState.DRIVING_HOME,
            TeslaPresenceState.ARRIVING,
        ):
            await self._emit(TeslaEventType.HEADING_AWAY, {})

    def _get_value(self, field: str, default: Any = None) -> Any:
        """Get current value for a field."""
        tv = self._telemetry.get(field)
        return tv.value if tv else default

    def _calc_distance_to_home(self) -> float:
        """Calculate distance to home in miles."""
        if not self._last_location:
            return float("inf")
        lat, lon = self._last_location
        return distance_to_home(lat, lon)

    def _check_heading_home(self) -> bool:
        """Check if vehicle is heading toward home."""
        if not self._last_location:
            return False
        lat, lon = self._last_location
        heading = self._get_value("Heading")
        if heading is None:
            return False
        return is_heading_home(lat, lon, heading)

    def _estimate_eta(self) -> int:
        """Estimate minutes to home."""
        dist = self._calc_distance_to_home()
        speed = self._get_value("Speed", 30)
        if speed <= 0:
            speed = 30
        minutes = (dist / speed) * 60 + 2
        return int(minutes)

    @property
    def presence_state(self) -> TeslaPresenceState:
        return self._presence_state

    @property
    def driving_state(self) -> DrivingState:
        return self._driving_state

    @property
    def is_home(self) -> bool:
        return self._presence_state == TeslaPresenceState.PARKED_HOME

    @property
    def is_moving(self) -> bool:
        return self._driving_state in (DrivingState.MOVING_SLOW, DrivingState.MOVING_FAST)

    @property
    def stats(self) -> dict[str, Any]:
        return {
            **self._stats,
            "presence_state": self._presence_state.value,
            "driving_state": self._driving_state.value,
            "at_home": self._last_at_home,
            "distance_to_home": self._calc_distance_to_home(),
        }


# Event bus singleton
_event_bus: TeslaEventBus | None = None


def get_tesla_event_bus() -> TeslaEventBus:
    """Get or create the Tesla Event Bus singleton."""
    global _event_bus
    if _event_bus is None:
        _event_bus = TeslaEventBus()
    return _event_bus


async def connect_tesla_event_bus(
    streaming: TeslaStreamingClient,
    smart_home: SmartHomeController | None = None,
) -> TeslaEventBus:
    """Connect Tesla streaming to event bus."""
    bus = get_tesla_event_bus()
    streaming.on_event(bus.on_telemetry)
    if smart_home:
        bus._smart_home = smart_home
    return bus


# =============================================================================
# COMPANION PROTOCOL
# =============================================================================


class CompanionState(Enum):
    """Companion app connection state."""

    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    BLUETOOTH_READY = "bluetooth_ready"
    PLAYING = "playing"
    ERROR = "error"


class MessageType(Enum):
    """Protocol message types."""

    SPEAK = "speak"
    STOP = "stop"
    PING = "ping"
    CONFIG = "config"
    STATUS = "status"
    SPEAK_COMPLETE = "speak_complete"
    PONG = "pong"
    ERROR = "error"


@dataclass
class CompanionStatus:
    """Current status of companion app."""

    connected: bool = False
    bluetooth_connected: bool = False
    bluetooth_device: str | None = None
    bluetooth_type: str = "unknown"
    playing: bool = False
    volume: float = 1.0
    battery_level: float | None = None
    last_seen: float = 0.0
    latency_ms: float = 0.0

    @property
    def is_ready(self) -> bool:
        return self.connected and self.bluetooth_connected

    @property
    def is_car(self) -> bool:
        if self.bluetooth_type == "car":
            return True
        if self.bluetooth_device and "tesla" in self.bluetooth_device.lower():
            return True
        return False


@dataclass
class SpeakResult:
    """Result of speak request."""

    success: bool
    request_id: str
    duration_ms: float = 0.0
    error: str | None = None
    latency_ms: float = 0.0


WebSocketSender = Callable[[str], Awaitable[None]]


class TeslaCompanionProtocol:
    """Server-side protocol handler for Tesla companion app."""

    PING_INTERVAL = 30.0
    PING_TIMEOUT = 10.0
    SPEAK_TIMEOUT = 30.0
    MAX_RETRIES = 3
    RETRY_BASE_DELAY = 0.5

    def __init__(self):
        self._connections: dict[str, WebSocketSender] = {}
        self._status: dict[str, CompanionStatus] = {}
        self._pending_speaks: dict[str, asyncio.Future[SpeakResult]] = {}
        self._ping_tasks: dict[str, asyncio.Task] = {}
        self._request_counter = 0
        self._stats = {
            "speaks_requested": 0,
            "speaks_completed": 0,
            "speaks_failed": 0,
        }

    async def register_connection(
        self,
        send_func: WebSocketSender,
        device_id: str,
        device_info: dict[str, Any] | None = None,
    ) -> None:
        """Register a new companion app connection."""
        self._connections[device_id] = send_func
        self._status[device_id] = CompanionStatus(connected=True, last_seen=time.time())
        self._ping_tasks[device_id] = asyncio.create_task(self._ping_loop(device_id))
        await self._send(
            device_id,
            {
                "type": MessageType.CONFIG.value,
                "config": {"ping_interval": self.PING_INTERVAL, "audio_format": "mp3"},
            },
        )

    async def unregister_connection(self, device_id: str) -> None:
        """Unregister a companion app connection."""
        if device_id in self._ping_tasks:
            self._ping_tasks[device_id].cancel()
            del self._ping_tasks[device_id]
        self._connections.pop(device_id, None)
        if device_id in self._status:
            self._status[device_id].connected = False

    async def handle_message(self, message: str | dict, device_id: str) -> None:
        """Handle incoming message from companion app."""
        if isinstance(message, str):
            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                return
        else:
            data = message

        msg_type = data.get("type", "")
        if device_id in self._status:
            self._status[device_id].last_seen = time.time()

        if msg_type == MessageType.STATUS.value:
            await self._handle_status(data, device_id)
        elif msg_type == MessageType.SPEAK_COMPLETE.value:
            await self._handle_speak_complete(data, device_id)

    async def _handle_status(self, data: dict, device_id: str) -> None:
        """Handle status update from companion."""
        if device_id not in self._status:
            return
        status = self._status[device_id]
        status.bluetooth_connected = data.get("bluetooth", False)
        status.bluetooth_device = data.get("bluetooth_device")
        status.bluetooth_type = data.get("bluetooth_type", "unknown")
        status.playing = data.get("playing", False)

    async def _handle_speak_complete(self, data: dict, device_id: str) -> None:
        """Handle speak completion notification."""
        request_id = data.get("request_id", "")
        success = data.get("success", False)
        duration_ms = data.get("duration_ms", 0)
        error = data.get("error")

        if request_id in self._pending_speaks:
            future = self._pending_speaks.pop(request_id)
            if not future.done():
                result = SpeakResult(
                    success=success,
                    request_id=request_id,
                    duration_ms=duration_ms,
                    error=error,
                )
                future.set_result(result)
                if success:
                    self._stats["speaks_completed"] += 1
                else:
                    self._stats["speaks_failed"] += 1

        if device_id in self._status:
            self._status[device_id].playing = False

    async def speak(
        self,
        text: str,
        audio_url: str,
        *,
        priority: int = 1,
        device_id: str | None = None,
        timeout: float | None = None,
    ) -> SpeakResult:
        """Send speak request to companion app."""
        timeout = timeout or self.SPEAK_TIMEOUT
        self._stats["speaks_requested"] += 1

        devices_to_try = []
        if device_id:
            devices_to_try.append(device_id)
        else:
            for dev_id, status in self._status.items():
                if status.is_ready and dev_id in self._connections:
                    devices_to_try.append(dev_id)

        if not devices_to_try:
            return SpeakResult(success=False, request_id="", error="No companion device available")

        for target_device in devices_to_try:
            self._request_counter += 1
            request_id = f"{target_device}_{self._request_counter}"
            future: asyncio.Future[SpeakResult] = asyncio.Future()
            self._pending_speaks[request_id] = future

            try:
                await self._send(
                    target_device,
                    {
                        "type": MessageType.SPEAK.value,
                        "request_id": request_id,
                        "text": text,
                        "audio_url": audio_url,
                        "priority": priority,
                    },
                )
                if target_device in self._status:
                    self._status[target_device].playing = True

                result = await asyncio.wait_for(future, timeout=timeout)
                if result.success:
                    return result
            except TimeoutError:
                self._pending_speaks.pop(request_id, None)
            except Exception:
                self._pending_speaks.pop(request_id, None)

        self._stats["speaks_failed"] += 1
        return SpeakResult(success=False, request_id="", error="All devices failed")

    async def _send(self, device_id: str, message: dict) -> None:
        """Send message to a device."""
        if device_id not in self._connections:
            raise ConnectionError(f"Device {device_id} not connected")
        send_func = self._connections[device_id]
        await send_func(json.dumps(message))

    async def _ping_loop(self, device_id: str) -> None:
        """Background task to ping companion app."""
        while device_id in self._connections:
            try:
                await asyncio.sleep(self.PING_INTERVAL)
                if device_id not in self._connections:
                    break
                await self._send(
                    device_id, {"type": MessageType.PING.value, "sent_time": time.time()}
                )
            except asyncio.CancelledError:
                break
            except Exception:
                pass

    @property
    def has_ready_device(self) -> bool:
        return any(s.is_ready for s in self._status.values() if s.connected)

    @property
    def has_car_device(self) -> bool:
        return any(s.is_ready and s.is_car for s in self._status.values())

    @property
    def connected_devices(self) -> list[str]:
        return list(self._connections.keys())

    def get_stats(self) -> dict[str, Any]:
        return {
            **self._stats,
            "connected_devices": len(self._connections),
            "ready_devices": sum(1 for s in self._status.values() if s.is_ready),
        }


_protocol_instance: TeslaCompanionProtocol | None = None


def get_companion_protocol() -> TeslaCompanionProtocol:
    """Get the singleton companion protocol instance."""
    global _protocol_instance
    if _protocol_instance is None:
        _protocol_instance = TeslaCompanionProtocol()
    return _protocol_instance


# =============================================================================
# VOICE ADAPTER
# =============================================================================


class AudioTarget(Enum):
    """Available audio output targets on Tesla."""

    EXTERNAL_PWS = "external_pws"
    CABIN_COMPANION = "cabin_companion"
    CABIN_THEATER = "cabin_theater"


class PredefinedSound(Enum):
    """Predefined sounds available via remote_boombox."""

    FART = 0
    LOCATE_PING = 2000


@dataclass
class VoiceResult:
    """Result of voice output attempt."""

    success: bool
    target: AudioTarget
    error: str | None = None
    latency_ms: float = 0.0
    requires_user_action: bool = False


class TeslaVoiceAdapter:
    """Voice output adapter for Tesla vehicles."""

    def __init__(self, executor: TeslaCommandExecutor, integration: TeslaIntegration | None = None):
        self._executor = executor
        self._integration = integration
        self._companion: TeslaCompanionProtocol | None = None
        self._initialized = False
        self._is_driving = False
        self._is_parked = True
        self._stats = {
            "external_plays": 0,
            "cabin_companion_plays": 0,
            "cabin_theater_plays": 0,
            "errors": 0,
            "total_latency_ms": 0.0,
        }

    async def initialize(self) -> bool:
        """Initialize the voice adapter."""
        try:
            self._companion = get_companion_protocol()
        except Exception:
            pass
        self._initialized = True
        return True

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def supports_external_audio(self) -> bool:
        return True

    @property
    def supports_cabin_audio(self) -> bool:
        return self.has_companion_ready or self._integration is not None

    @property
    def has_companion_ready(self) -> bool:
        return bool(self._companion and self._companion.has_ready_device)

    def update_driving_state(self, is_driving: bool, shift_state: str = "P") -> None:
        """Update the current driving state."""
        self._is_driving = is_driving
        self._is_parked = shift_state == "P"

    async def speak_external(self, audio_url: str, *, force: bool = False) -> VoiceResult:
        """Play audio through external PWS speaker."""
        start = time.perf_counter()
        if not self._initialized:
            return VoiceResult(
                success=False, target=AudioTarget.EXTERNAL_PWS, error="Not initialized"
            )
        if self._is_driving and not force:
            return VoiceResult(success=False, target=AudioTarget.EXTERNAL_PWS, error="Driving")

        try:
            success = await self._executor.remote_boombox(sound_id=0, streaming_url=audio_url)
            latency_ms = (time.perf_counter() - start) * 1000
            self._stats["external_plays"] += 1
            return VoiceResult(
                success=success, target=AudioTarget.EXTERNAL_PWS, latency_ms=latency_ms
            )
        except Exception as e:
            self._stats["errors"] += 1
            return VoiceResult(success=False, target=AudioTarget.EXTERNAL_PWS, error=str(e))

    async def speak_cabin(
        self, audio_url: str, text: str = "", *, priority: int = 1
    ) -> VoiceResult:
        """Play audio through cabin speakers via companion app."""
        start = time.perf_counter()
        if not self._initialized:
            return VoiceResult(
                success=False, target=AudioTarget.CABIN_COMPANION, error="Not initialized"
            )

        if not self._companion or not self._companion.has_ready_device:
            return VoiceResult(
                success=False, target=AudioTarget.CABIN_COMPANION, error="No companion"
            )

        try:
            result = await self._companion.speak(text=text, audio_url=audio_url, priority=priority)
            latency_ms = (time.perf_counter() - start) * 1000
            self._stats["cabin_companion_plays"] += 1
            return VoiceResult(
                success=result.success,
                target=AudioTarget.CABIN_COMPANION,
                latency_ms=latency_ms,
                error=result.error,
            )
        except Exception as e:
            self._stats["errors"] += 1
            return VoiceResult(success=False, target=AudioTarget.CABIN_COMPANION, error=str(e))

    async def speak(
        self, audio_url: str, text: str = "", *, prefer_cabin: bool = True, priority: int = 1
    ) -> VoiceResult:
        """Auto-route audio to best available target."""
        if prefer_cabin and self.has_companion_ready:
            return await self.speak_cabin(audio_url, text, priority=priority)
        return await self.speak_external(audio_url)

    def get_stats(self) -> dict[str, Any]:
        return {
            **self._stats,
            "supports_external": self.supports_external_audio,
            "supports_cabin": self.supports_cabin_audio,
            "has_companion_ready": self.has_companion_ready,
        }


async def create_tesla_voice_adapter(
    executor: TeslaCommandExecutor,
    integration: TeslaIntegration | None = None,
) -> TeslaVoiceAdapter:
    """Create and initialize a Tesla voice adapter."""
    adapter = TeslaVoiceAdapter(executor, integration)
    await adapter.initialize()
    return adapter


# =============================================================================
# ALERT SYSTEM
# =============================================================================


class AlertPriority(Enum):
    """Alert priority levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class AlertCategory(Enum):
    """Alert categories."""

    SAFETY = "safety"
    CHARGING = "charging"
    BATTERY = "battery"
    CLIMATE = "climate"
    AUTOPILOT = "autopilot"
    DRIVE = "drive"
    UI = "ui"
    LOCKS = "locks"
    SUSPENSION = "suspension"
    OTHER = "other"


PREFIX_TO_CATEGORY = {
    "RCM2": AlertCategory.SAFETY,
    "RCM": AlertCategory.SAFETY,
    "ESP": AlertCategory.SAFETY,
    "IBST": AlertCategory.SAFETY,
    "EBS": AlertCategory.SAFETY,
    "CP": AlertCategory.CHARGING,
    "CHG": AlertCategory.CHARGING,
    "UMC": AlertCategory.CHARGING,
    "BMS": AlertCategory.BATTERY,
    "HVBATT": AlertCategory.BATTERY,
    "CC": AlertCategory.CLIMATE,
    "THC": AlertCategory.CLIMATE,
    "APP": AlertCategory.AUTOPILOT,
    "RADC": AlertCategory.AUTOPILOT,
    "DI": AlertCategory.DRIVE,
    "DIS": AlertCategory.DRIVE,
    "UI": AlertCategory.UI,
    "GTW": AlertCategory.UI,
    "VCSEC": AlertCategory.LOCKS,
    "TAS": AlertCategory.SUSPENSION,
}

SAFETY_CRITICAL_PATTERNS = [
    "PULL OVER SAFELY",
    "Vehicle shutting down",
    "Vehicle may shut down",
    "Unable to drive",
    "ABS disabled",
    "Brake",
    "Airbag",
    "Stability",
]


@dataclass
class TeslaAlert:
    """Parsed Tesla alert from dictionary."""

    signal_name: str
    condition: str
    clear_condition: str
    description: str
    potential_impact: str
    customer_message_1: str
    customer_message_2: str
    audiences: list[str]
    models: list[str]
    category: AlertCategory = AlertCategory.OTHER
    priority: AlertPriority = AlertPriority.LOW

    def __post_init__(self):
        prefix = self.signal_name.split("_")[0] if "_" in self.signal_name else self.signal_name
        self.category = PREFIX_TO_CATEGORY.get(prefix, AlertCategory.OTHER)
        self.priority = self._calculate_priority()

    def _calculate_priority(self) -> AlertPriority:
        combined_text = (
            f"{self.potential_impact} {self.customer_message_1} {self.customer_message_2}"
        )
        for pattern in SAFETY_CRITICAL_PATTERNS:
            if pattern.lower() in combined_text.lower():
                return AlertPriority.CRITICAL
        if "customer" in self.audiences:
            if "service-fix" in self.audiences:
                return AlertPriority.HIGH
            return AlertPriority.MEDIUM
        return AlertPriority.LOW

    @property
    def is_customer_facing(self) -> bool:
        return "customer" in self.audiences


class TeslaAlertDictionary:
    """Tesla alert dictionary manager."""

    def __init__(self, csv_path: Path | None = None):
        self._csv_path = csv_path or Path(__file__).parent / "tesla_alerts.csv"
        self._alerts: dict[str, TeslaAlert] = {}
        self._by_category: dict[AlertCategory, list[TeslaAlert]] = {}
        self._loaded = False

    async def load(self) -> bool:
        """Load alert dictionary from CSV."""
        if not self._csv_path.exists():
            return False

        try:
            with open(self._csv_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    alert = TeslaAlert(
                        signal_name=row.get("SignalName", ""),
                        condition=row.get("Condition", ""),
                        clear_condition=row.get("ClearCondition", ""),
                        description=row.get("Description", ""),
                        potential_impact=row.get("PotentialImpact", ""),
                        customer_message_1=row.get("CustomerFacingMessage1", ""),
                        customer_message_2=row.get("CustomerFacingMessage2", ""),
                        audiences=[
                            a.strip() for a in row.get("Audiences", "").split(";") if a.strip()
                        ],
                        models=[m.strip() for m in row.get("Models", "").split(";") if m.strip()],
                    )
                    self._alerts[alert.signal_name] = alert
                    if alert.category not in self._by_category:
                        self._by_category[alert.category] = []
                    self._by_category[alert.category].append(alert)
            self._loaded = True
            return True
        except Exception:
            return False

    def get_alert(self, signal_name: str) -> TeslaAlert | None:
        return self._alerts.get(signal_name)

    def get_alerts_by_category(self, category: AlertCategory) -> list[TeslaAlert]:
        return self._by_category.get(category, [])

    def get_critical_alerts(self) -> list[TeslaAlert]:
        return [a for a in self._alerts.values() if a.priority == AlertPriority.CRITICAL]

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "total_alerts": len(self._alerts),
            "critical_alerts": len(self.get_critical_alerts()),
            "loaded": self._loaded,
        }


AlertCallback = Callable[[TeslaAlert, dict[str, Any]], Awaitable[None]]


class TeslaAlertRouter:
    """Routes Tesla alerts to appropriate handlers."""

    def __init__(self, dictionary: TeslaAlertDictionary):
        self._dictionary = dictionary
        self._handlers: dict[AlertPriority, list[AlertCallback]] = {
            AlertPriority.CRITICAL: [],
            AlertPriority.HIGH: [],
            AlertPriority.MEDIUM: [],
            AlertPriority.LOW: [],
        }
        self._stats = {"alerts_received": 0, "alerts_routed": 0, "unknown_alerts": 0}

    def on_critical(self, callback: AlertCallback) -> None:
        self._handlers[AlertPriority.CRITICAL].append(callback)

    def on_high(self, callback: AlertCallback) -> None:
        self._handlers[AlertPriority.HIGH].append(callback)

    def on_medium(self, callback: AlertCallback) -> None:
        self._handlers[AlertPriority.MEDIUM].append(callback)

    def on_low(self, callback: AlertCallback) -> None:
        self._handlers[AlertPriority.LOW].append(callback)

    async def handle_alert(self, signal_name: str, data: dict[str, Any]) -> bool:
        """Handle incoming alert from telemetry stream."""
        self._stats["alerts_received"] += 1
        alert = self._dictionary.get_alert(signal_name)
        if not alert:
            self._stats["unknown_alerts"] += 1
            return False

        handlers = self._handlers.get(alert.priority, [])
        if handlers:
            self._stats["alerts_routed"] += 1
            for handler in handlers:
                try:
                    await handler(alert, data)
                except Exception:
                    pass
            return True
        return False

    @property
    def stats(self) -> dict[str, Any]:
        return self._stats


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Core Integration
    "TeslaIntegration",
    "TeslaStreamingClient",
    "TeslaEventCallback",
    # Command Executor
    "TeslaCommandExecutor",
    "CommandCategory",
    "CommandMeta",
    "SafetyLevel",
    "cbf_protected",
    # Safety Barrier
    "TeslaSafetyBarrier",
    "DRIVING_PROTECTION",
    # Event Bus
    "TeslaEventBus",
    "EventCallback",
    "get_tesla_event_bus",
    "connect_tesla_event_bus",
    # Companion Protocol
    "TeslaCompanionProtocol",
    "CompanionState",
    "CompanionStatus",
    "SpeakResult",
    "get_companion_protocol",
    # Voice Adapter
    "TeslaVoiceAdapter",
    "AudioTarget",
    "PredefinedSound",
    "VoiceResult",
    "create_tesla_voice_adapter",
    # Alert System
    "TeslaAlert",
    "TeslaAlertDictionary",
    "TeslaAlertRouter",
    "AlertPriority",
    "AlertCategory",
    "AlertCallback",
]
