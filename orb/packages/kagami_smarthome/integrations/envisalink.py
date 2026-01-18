"""Envisalink DSC Security Panel Integration.

Direct TCP/TPI protocol implementation for Envisalink EVL-3/EVL-4 modules.
Provides MUCH richer data than the Control4 IT-100 driver including:
- Real-time zone events (open/close/alarm/tamper/fault)
- Per-zone battery status (wireless zones)
- Temperature monitoring (with EMS-100 module)
- Partition status (ready/armed/alarm/entry-exit delay)
- Trouble conditions (AC fail, battery low, fire loop, etc.)
- Zone bypass status

TPI Protocol Reference:
- Commands: 3-digit numeric followed by optional data
- Responses: 3-digit numeric + data + checksum + CRLF
- Checksums: 2-char hex of sum of all bytes

Zone Types (from programming):
- Door/Window sensors → motion events
- Motion detectors → motion events
- Glass break → alarm events
- Smoke detectors → fire events
- CO detectors → safety events

Created: December 29, 2025
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

# TPI Protocol Constants
TPI_LOGIN = "005"  # Login (password + checksum)
TPI_POLL = "000"  # Poll (keep-alive)
TPI_STATUS_REPORT = "001"  # Request full status
TPI_DUMP_ZONE_TIMERS = "008"  # Request zone timer dump
TPI_PARTITION_ARM_AWAY = "030"  # Arm away
TPI_PARTITION_ARM_STAY = "031"  # Arm stay
TPI_PARTITION_ARM_ZERO_DELAY = "032"  # Arm with no entry delay
TPI_PARTITION_DISARM = "040"  # Disarm (requires code)
TPI_TEMP_BROADCAST_ENABLE = "057"  # Enable temperature broadcast (EMS-100)
TPI_TEMP_BROADCAST_DISABLE = "058"  # Disable temperature broadcast

# TPI Response Codes
RESP_ACK = "500"  # Command acknowledged
RESP_ERROR = "501"  # Command error
RESP_SYSTEM_ERROR = "502"  # System error
RESP_LOGIN_RESPONSE = "505"  # Login result (0=fail, 1=success, 2=timeout, 3=password needed)
RESP_KEYPAD_LED_STATE = "510"  # LED state update
RESP_KEYPAD_LED_FLASH = "511"  # LED flash state

# Zone Events (6xx)
RESP_ZONE_ALARM = "601"  # Zone in alarm
RESP_ZONE_ALARM_RESTORE = "602"  # Zone alarm restored
RESP_ZONE_TAMPER = "603"  # Zone tamper
RESP_ZONE_TAMPER_RESTORE = "604"  # Zone tamper restored
RESP_ZONE_FAULT = "605"  # Zone fault
RESP_ZONE_FAULT_RESTORE = "606"  # Zone fault restored
RESP_ZONE_OPEN = "609"  # Zone open
RESP_ZONE_RESTORED = "610"  # Zone closed/restored
RESP_ZONE_TIMER_DUMP = "615"  # Zone timer dump
RESP_DURESS_ALARM = "620"  # Duress alarm
RESP_FIRE_KEY_ALARM = "621"  # Fire key alarm
RESP_FIRE_KEY_RESTORE = "622"  # Fire key restore
RESP_AUX_KEY_ALARM = "623"  # Auxiliary key alarm
RESP_AUX_KEY_RESTORE = "624"  # Auxiliary key restore
RESP_PANIC_KEY_ALARM = "625"  # Panic key alarm
RESP_PANIC_KEY_RESTORE = "626"  # Panic key restore
RESP_SMOKE_RESET = "631"  # 2-wire smoke reset

# Partition Events (65x)
RESP_PARTITION_READY = "650"  # Partition ready
RESP_PARTITION_NOT_READY = "651"  # Partition not ready
RESP_PARTITION_ARMED = "652"  # Partition armed (mode in data)
RESP_PARTITION_READY_FORCE_ARM = "653"  # Ready - force arm enabled
RESP_PARTITION_ALARM = "654"  # Partition in alarm
RESP_PARTITION_DISARMED = "655"  # Partition disarmed
RESP_PARTITION_EXIT_DELAY = "656"  # Exit delay in progress
RESP_PARTITION_ENTRY_DELAY = "657"  # Entry delay in progress
RESP_KEYPAD_LOCKOUT = "658"  # Keypad lockout
RESP_PARTITION_FAILED_ARM = "659"  # Failed to arm (zone open)
RESP_PGM_OUTPUT = "660"  # PGM output in progress
RESP_CHIME_ENABLED = "663"  # Chime enabled
RESP_CHIME_DISABLED = "664"  # Chime disabled
RESP_INVALID_ACCESS_CODE = "670"  # Invalid access code
RESP_FUNCTION_NOT_AVAIL = "671"  # Function not available
RESP_FAILURE_TO_ARM = "672"  # Failure to arm

# Trouble Events (8xx)
RESP_PANEL_AC_TROUBLE = "800"  # AC power trouble
RESP_PANEL_AC_RESTORE = "801"  # AC power restored
RESP_PANEL_BATTERY_TROUBLE = "802"  # Panel battery low
RESP_PANEL_BATTERY_RESTORE = "803"  # Panel battery restored
RESP_SYSTEM_BELL_TROUBLE = "806"  # Bell/siren trouble
RESP_SYSTEM_BELL_RESTORE = "807"  # Bell/siren restored
RESP_TLM_LINE_1_TROUBLE = "810"  # Telephone line 1 trouble
RESP_TLM_LINE_1_RESTORE = "811"  # Telephone line 1 restored
RESP_TLM_LINE_2_TROUBLE = "812"  # Telephone line 2 trouble
RESP_TLM_LINE_2_RESTORE = "813"  # Telephone line 2 restored
RESP_FIRE_TROUBLE = "820"  # Fire zone trouble
RESP_FIRE_RESTORE = "821"  # Fire zone restored
RESP_GENERAL_SYSTEM_TAMPER = "829"  # General system tamper
RESP_GENERAL_SYSTEM_TAMPER_RESTORE = "830"  # General system tamper restored
RESP_ZONE_LOW_BATTERY = "832"  # Wireless zone low battery

# Temperature Events (only with EMS-100)
RESP_VERBOSE_TROUBLE = "849"  # Verbose trouble status
RESP_CODE_REQUIRED = "900"  # Code required for function
RESP_INSTALLER_CODE_REQUIRED = "901"  # Installer code required
RESP_LCD_UPDATE = "901"  # LCD update (virtual keypad)
RESP_INTERIOR_TEMP = "908"  # Interior temperature
RESP_EXTERIOR_TEMP = "909"  # Exterior temperature


class ZoneType(Enum):
    """Type of security zone."""

    UNKNOWN = "unknown"
    DOOR_WINDOW = "door_window"  # Entry/exit sensors
    MOTION = "motion"  # Motion detectors (PIR)
    GLASS_BREAK = "glass_break"  # Glass break sensors
    SMOKE = "smoke"  # Smoke detectors
    CO = "co"  # Carbon monoxide detectors
    HEAT = "heat"  # Heat detectors
    WATER = "water"  # Water/flood sensors
    FREEZE = "freeze"  # Freeze sensors


class ZoneState(Enum):
    """State of a zone."""

    CLOSED = "closed"  # Normal/secure
    OPEN = "open"  # Open (door/window)
    BYPASSED = "bypassed"  # Bypassed by user
    ALARM = "alarm"  # Zone in alarm
    TAMPER = "tamper"  # Tamper detected
    FAULT = "fault"  # Zone fault


class PartitionState(Enum):
    """State of a partition."""

    READY = "ready"  # Ready to arm
    NOT_READY = "not_ready"  # Not ready (zones open)
    ARMED_AWAY = "armed_away"  # Armed in away mode
    ARMED_STAY = "armed_stay"  # Armed in stay mode
    ARMED_ZERO_DELAY = "armed_zero_delay"  # Armed with no entry delay
    ALARM = "alarm"  # Alarm triggered
    EXIT_DELAY = "exit_delay"  # Exit delay countdown
    ENTRY_DELAY = "entry_delay"  # Entry delay countdown
    DISARMED = "disarmed"


class TroubleType(Enum):
    """System trouble conditions."""

    NONE = "none"
    AC_FAILURE = "ac_failure"
    BATTERY_LOW = "battery_low"
    BELL_TROUBLE = "bell_trouble"
    PHONE_LINE = "phone_line"
    FIRE_TROUBLE = "fire_trouble"
    SYSTEM_TAMPER = "system_tamper"
    ZONE_LOW_BATTERY = "zone_low_battery"


@dataclass
class ZoneInfo:
    """Information about a security zone."""

    number: int  # Zone 1-64
    name: str = ""  # Human-readable name (e.g., "Front Door")
    zone_type: ZoneType = ZoneType.UNKNOWN
    state: ZoneState = ZoneState.CLOSED
    battery_low: bool = False
    last_opened: float = 0.0
    last_closed: float = 0.0
    open_count: int = 0  # Activity counter

    # For motion zones - time since last trigger
    @property
    def time_since_activity(self) -> float:
        """Seconds since last activity."""
        if self.last_opened > 0:
            return time.time() - self.last_opened
        return float("inf")


@dataclass
class PartitionInfo:
    """Information about a partition."""

    number: int  # Partition 1-8
    state: PartitionState = PartitionState.DISARMED
    armed_mode: str = ""  # "away", "stay", "zero_delay"
    last_armed: float = 0.0
    last_disarmed: float = 0.0
    alarm_zones: list[int] = field(default_factory=list)


@dataclass
class TemperatureReading:
    """Temperature reading from EMS-100 module."""

    interior: float | None = None  # Fahrenheit
    exterior: float | None = None  # Fahrenheit
    timestamp: float = 0.0


@dataclass
class TroubleStatus:
    """System trouble status."""

    troubles: list[TroubleType] = field(default_factory=list)
    trouble_zones: list[int] = field(default_factory=list)  # Zones with low battery


# Type alias for event callbacks
ZoneEventCallback = Callable[["ZoneInfo", str], Coroutine[Any, Any, None]]
PartitionEventCallback = Callable[["PartitionInfo", str], Coroutine[Any, Any, None]]
TroubleEventCallback = Callable[["TroubleStatus"], Coroutine[Any, Any, None]]


class EnvisalinkIntegration:
    """Direct Envisalink EVL-3/EVL-4 integration via TPI protocol.

    Provides real-time zone monitoring, partition control, and system status
    with much richer data than the Control4 IT-100 driver.

    Example:
        integration = EnvisalinkIntegration(
            host="192.168.1.100",
            password="user",
            zone_labels={1: "Front Door", 2: "Back Door", 3: "Living Room Motion"},
            zone_types={1: ZoneType.DOOR_WINDOW, 2: ZoneType.DOOR_WINDOW, 3: ZoneType.MOTION},
        )
        await integration.connect()

        # Register callbacks
        integration.on_zone_event = my_zone_handler
        integration.on_partition_event = my_partition_handler

        # Control
        await integration.arm_away(1)  # Arm partition 1 away
        await integration.disarm(1, "1234")  # Disarm with code
    """

    def __init__(
        self,
        host: str,
        port: int = 4025,
        password: str = "user",
        zone_labels: dict[int, str] | None = None,
        zone_types: dict[int, ZoneType] | None = None,
        arm_code: str | None = None,
        enable_temperature: bool = False,
    ):
        """Initialize Envisalink integration.

        Args:
            host: Envisalink IP address
            port: Envisalink port (default 4025)
            password: Envisalink password (default "user")
            zone_labels: Dict mapping zone numbers to names
            zone_types: Dict mapping zone numbers to types
            arm_code: Master code for arming/disarming
            enable_temperature: Enable temperature broadcast (requires EMS-100)
        """
        self.host = host
        self.port = port
        self.password = password
        self.arm_code = arm_code
        self.enable_temperature = enable_temperature

        # Zone configuration
        self._zone_labels = zone_labels or {}
        self._zone_types = zone_types or {}

        # State tracking
        self._zones: dict[int, ZoneInfo] = {}
        self._partitions: dict[int, PartitionInfo] = {}
        self._trouble = TroubleStatus()
        self._temperature = TemperatureReading()

        # Connection state
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._connected = False
        self._authenticated = False
        self._read_task: asyncio.Task[None] | None = None
        self._keepalive_task: asyncio.Task[None] | None = None

        # Event callbacks
        self.on_zone_event: ZoneEventCallback | None = None
        self.on_partition_event: PartitionEventCallback | None = None
        self.on_trouble_event: TroubleEventCallback | None = None
        self.on_temperature: Callable[[TemperatureReading], Coroutine[Any, Any, None]] | None = None

        # Initialize zones from configuration
        for zone_num in range(1, 65):
            name = self._zone_labels.get(zone_num, f"Zone {zone_num}")
            zone_type = self._zone_types.get(zone_num, ZoneType.UNKNOWN)
            self._zones[zone_num] = ZoneInfo(
                number=zone_num,
                name=name,
                zone_type=zone_type,
            )

        # Initialize partitions (most systems use only 1)
        for part_num in range(1, 9):
            self._partitions[part_num] = PartitionInfo(number=part_num)

    @property
    def is_connected(self) -> bool:
        """Check if connected and authenticated."""
        return self._connected and self._authenticated

    def _calculate_checksum(self, data: str) -> str:
        """Calculate TPI checksum (sum of bytes mod 256, as 2-char hex)."""
        total = sum(ord(c) for c in data)
        return f"{total & 0xFF:02X}"

    def _format_command(self, cmd: str, data: str = "") -> bytes:
        """Format a TPI command with checksum."""
        payload = cmd + data
        checksum = self._calculate_checksum(payload)
        return (payload + checksum + "\r\n").encode()

    def _parse_response(self, line: str) -> tuple[str, str]:
        """Parse TPI response into (command, data)."""
        # Format: CCC + data + XX (checksum) + CRLF
        if len(line) < 5:
            return "", ""
        cmd = line[:3]
        # Remove checksum (last 2 chars before any whitespace)
        data = line[3:-2] if len(line) > 5 else ""
        return cmd, data

    async def connect(self, timeout: float = 3.0) -> bool:
        """Connect to Envisalink and authenticate.

        Args:
            timeout: Connection timeout in seconds (default 3.0, reduced for faster init)
        """
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=timeout,
            )
            self._connected = True
            logger.info(f"Envisalink: Connected to {self.host}:{self.port}")

            # Wait for login prompt
            await asyncio.sleep(0.5)

            # Authenticate
            await self._send_command(TPI_LOGIN, self.password)

            # Wait for auth response
            for _ in range(10):
                line = await asyncio.wait_for(
                    self._reader.readline(),
                    timeout=5.0,
                )
                line_str = line.decode().strip()
                cmd, data = self._parse_response(line_str)

                if cmd == RESP_LOGIN_RESPONSE:
                    if data == "1":
                        self._authenticated = True
                        logger.info("Envisalink: Authenticated successfully")
                        break
                    elif data == "0":
                        logger.error("Envisalink: Authentication failed - invalid password")
                        return False
                    elif data == "3":
                        # Password needed - send again
                        await self._send_command(TPI_LOGIN, self.password)

            if not self._authenticated:
                logger.error("Envisalink: Authentication timeout")
                return False

            # Start background tasks
            self._read_task = asyncio.create_task(self._read_loop())
            self._keepalive_task = asyncio.create_task(self._keepalive_loop())

            # Request initial status
            await self._send_command(TPI_STATUS_REPORT)

            # Enable temperature if requested
            if self.enable_temperature:
                await self._send_command(TPI_TEMP_BROADCAST_ENABLE, "1")

            logger.info(f"✅ Envisalink: Ready ({len(self._zone_labels)} zones configured)")
            return True

        except TimeoutError:
            logger.error(f"Envisalink: Connection timeout to {self.host}")
            return False
        except Exception as e:
            logger.error(f"Envisalink: Connection error: {e}")
            return False

    async def _send_command(self, cmd: str, data: str = "") -> bool:
        """Send a TPI command."""
        if not self._writer:
            return False
        try:
            message = self._format_command(cmd, data)
            self._writer.write(message)
            await self._writer.drain()
            logger.debug(f"Envisalink TX: {cmd}{data}")
            return True
        except Exception as e:
            logger.error(f"Envisalink: Send error: {e}")
            return False

    async def _read_loop(self) -> None:
        """Background task to read and process responses."""
        while self._connected and self._reader:
            try:
                line = await self._reader.readline()
                if not line:
                    logger.warning("Envisalink: Connection closed")
                    self._connected = False
                    break

                line_str = line.decode().strip()
                if line_str:
                    await self._process_response(line_str)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Envisalink: Read error: {e}")
                await asyncio.sleep(1)

    async def _keepalive_loop(self) -> None:
        """Background task to send keepalive polls."""
        while self._connected:
            try:
                await asyncio.sleep(30)  # Poll every 30 seconds
                await self._send_command(TPI_POLL)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Envisalink: Keepalive error: {e}")

    async def _process_response(self, line: str) -> None:
        """Process a TPI response."""
        cmd, data = self._parse_response(line)
        logger.debug(f"Envisalink RX: {cmd} {data}")

        now = time.time()

        # Zone events
        if cmd == RESP_ZONE_OPEN:
            zone_num = int(data)
            await self._handle_zone_open(zone_num, now)
        elif cmd == RESP_ZONE_RESTORED:
            zone_num = int(data)
            await self._handle_zone_closed(zone_num, now)
        elif cmd == RESP_ZONE_ALARM:
            zone_num = int(data)
            await self._handle_zone_alarm(zone_num, now)
        elif cmd == RESP_ZONE_ALARM_RESTORE:
            zone_num = int(data)
            await self._handle_zone_alarm_restore(zone_num, now)
        elif cmd == RESP_ZONE_TAMPER:
            zone_num = int(data)
            await self._handle_zone_tamper(zone_num, now)
        elif cmd == RESP_ZONE_TAMPER_RESTORE:
            zone_num = int(data)
            await self._handle_zone_tamper_restore(zone_num, now)
        elif cmd == RESP_ZONE_FAULT:
            zone_num = int(data)
            await self._handle_zone_fault(zone_num, now)
        elif cmd == RESP_ZONE_FAULT_RESTORE:
            zone_num = int(data)
            await self._handle_zone_fault_restore(zone_num, now)

        # Partition events
        elif cmd == RESP_PARTITION_READY:
            part_num = int(data) if data else 1
            await self._handle_partition_ready(part_num)
        elif cmd == RESP_PARTITION_NOT_READY:
            part_num = int(data) if data else 1
            await self._handle_partition_not_ready(part_num)
        elif cmd == RESP_PARTITION_ARMED:
            # Data format: partition (1 byte) + mode (1 byte)
            part_num = int(data[0]) if data else 1
            mode = int(data[1]) if len(data) > 1 else 0
            await self._handle_partition_armed(part_num, mode, now)
        elif cmd == RESP_PARTITION_DISARMED:
            part_num = int(data) if data else 1
            await self._handle_partition_disarmed(part_num, now)
        elif cmd == RESP_PARTITION_ALARM:
            part_num = int(data) if data else 1
            await self._handle_partition_alarm(part_num, now)
        elif cmd == RESP_PARTITION_EXIT_DELAY:
            part_num = int(data) if data else 1
            await self._handle_partition_exit_delay(part_num)
        elif cmd == RESP_PARTITION_ENTRY_DELAY:
            part_num = int(data) if data else 1
            await self._handle_partition_entry_delay(part_num)

        # Trouble events
        elif cmd == RESP_PANEL_AC_TROUBLE:
            await self._handle_trouble(TroubleType.AC_FAILURE, True)
        elif cmd == RESP_PANEL_AC_RESTORE:
            await self._handle_trouble(TroubleType.AC_FAILURE, False)
        elif cmd == RESP_PANEL_BATTERY_TROUBLE:
            await self._handle_trouble(TroubleType.BATTERY_LOW, True)
        elif cmd == RESP_PANEL_BATTERY_RESTORE:
            await self._handle_trouble(TroubleType.BATTERY_LOW, False)
        elif cmd == RESP_SYSTEM_BELL_TROUBLE:
            await self._handle_trouble(TroubleType.BELL_TROUBLE, True)
        elif cmd == RESP_SYSTEM_BELL_RESTORE:
            await self._handle_trouble(TroubleType.BELL_TROUBLE, False)
        elif cmd == RESP_ZONE_LOW_BATTERY:
            zone_num = int(data) if data else 0
            await self._handle_zone_low_battery(zone_num)

        # Temperature
        elif cmd == RESP_INTERIOR_TEMP:
            temp = int(data) if data else 0
            self._temperature.interior = temp
            self._temperature.timestamp = now
            if self.on_temperature:
                await self.on_temperature(self._temperature)
        elif cmd == RESP_EXTERIOR_TEMP:
            temp = int(data) if data else 0
            self._temperature.exterior = temp
            self._temperature.timestamp = now
            if self.on_temperature:
                await self.on_temperature(self._temperature)

    # Zone event handlers
    async def _handle_zone_open(self, zone_num: int, timestamp: float) -> None:
        """Handle zone open event."""
        zone = self._zones.get(zone_num)
        if not zone:
            return
        zone.state = ZoneState.OPEN
        zone.last_opened = timestamp
        zone.open_count += 1
        logger.debug(f"Zone {zone_num} ({zone.name}): OPEN")
        if self.on_zone_event:
            await self.on_zone_event(zone, "open")

    async def _handle_zone_closed(self, zone_num: int, timestamp: float) -> None:
        """Handle zone closed/restored event."""
        zone = self._zones.get(zone_num)
        if not zone:
            return
        zone.state = ZoneState.CLOSED
        zone.last_closed = timestamp
        logger.debug(f"Zone {zone_num} ({zone.name}): CLOSED")
        if self.on_zone_event:
            await self.on_zone_event(zone, "closed")

    async def _handle_zone_alarm(self, zone_num: int, timestamp: float) -> None:
        """Handle zone alarm event."""
        zone = self._zones.get(zone_num)
        if not zone:
            return
        zone.state = ZoneState.ALARM
        zone.last_opened = timestamp
        logger.warning(f"Zone {zone_num} ({zone.name}): ALARM!")
        if self.on_zone_event:
            await self.on_zone_event(zone, "alarm")

    async def _handle_zone_alarm_restore(self, zone_num: int, timestamp: float) -> None:
        """Handle zone alarm restore."""
        zone = self._zones.get(zone_num)
        if not zone:
            return
        zone.state = ZoneState.CLOSED
        logger.info(f"Zone {zone_num} ({zone.name}): Alarm restored")
        if self.on_zone_event:
            await self.on_zone_event(zone, "alarm_restore")

    async def _handle_zone_tamper(self, zone_num: int, timestamp: float) -> None:
        """Handle zone tamper event."""
        zone = self._zones.get(zone_num)
        if not zone:
            return
        zone.state = ZoneState.TAMPER
        logger.warning(f"Zone {zone_num} ({zone.name}): TAMPER!")
        if self.on_zone_event:
            await self.on_zone_event(zone, "tamper")

    async def _handle_zone_tamper_restore(self, zone_num: int, timestamp: float) -> None:
        """Handle zone tamper restore."""
        zone = self._zones.get(zone_num)
        if not zone:
            return
        zone.state = ZoneState.CLOSED
        logger.info(f"Zone {zone_num} ({zone.name}): Tamper restored")
        if self.on_zone_event:
            await self.on_zone_event(zone, "tamper_restore")

    async def _handle_zone_fault(self, zone_num: int, timestamp: float) -> None:
        """Handle zone fault event."""
        zone = self._zones.get(zone_num)
        if not zone:
            return
        zone.state = ZoneState.FAULT
        logger.warning(f"Zone {zone_num} ({zone.name}): FAULT")
        if self.on_zone_event:
            await self.on_zone_event(zone, "fault")

    async def _handle_zone_fault_restore(self, zone_num: int, timestamp: float) -> None:
        """Handle zone fault restore."""
        zone = self._zones.get(zone_num)
        if not zone:
            return
        zone.state = ZoneState.CLOSED
        logger.info(f"Zone {zone_num} ({zone.name}): Fault restored")
        if self.on_zone_event:
            await self.on_zone_event(zone, "fault_restore")

    async def _handle_zone_low_battery(self, zone_num: int) -> None:
        """Handle wireless zone low battery."""
        zone = self._zones.get(zone_num)
        if zone:
            zone.battery_low = True
            if zone_num not in self._trouble.trouble_zones:
                self._trouble.trouble_zones.append(zone_num)
            logger.warning(f"Zone {zone_num} ({zone.name}): LOW BATTERY")
        if self.on_trouble_event:
            await self.on_trouble_event(self._trouble)

    # Partition event handlers
    async def _handle_partition_ready(self, part_num: int) -> None:
        """Handle partition ready event."""
        partition = self._partitions.get(part_num)
        if not partition:
            return
        partition.state = PartitionState.READY
        logger.debug(f"Partition {part_num}: Ready")
        if self.on_partition_event:
            await self.on_partition_event(partition, "ready")

    async def _handle_partition_not_ready(self, part_num: int) -> None:
        """Handle partition not ready event."""
        partition = self._partitions.get(part_num)
        if not partition:
            return
        partition.state = PartitionState.NOT_READY
        logger.debug(f"Partition {part_num}: Not ready")
        if self.on_partition_event:
            await self.on_partition_event(partition, "not_ready")

    async def _handle_partition_armed(self, part_num: int, mode: int, timestamp: float) -> None:
        """Handle partition armed event."""
        partition = self._partitions.get(part_num)
        if not partition:
            return

        # Mode: 0=away, 1=stay, 2=zero delay
        if mode == 0:
            partition.state = PartitionState.ARMED_AWAY
            partition.armed_mode = "away"
        elif mode == 1:
            partition.state = PartitionState.ARMED_STAY
            partition.armed_mode = "stay"
        else:
            partition.state = PartitionState.ARMED_ZERO_DELAY
            partition.armed_mode = "zero_delay"

        partition.last_armed = timestamp
        logger.info(f"Partition {part_num}: Armed ({partition.armed_mode})")
        if self.on_partition_event:
            await self.on_partition_event(partition, f"armed_{partition.armed_mode}")

    async def _handle_partition_disarmed(self, part_num: int, timestamp: float) -> None:
        """Handle partition disarmed event."""
        partition = self._partitions.get(part_num)
        if not partition:
            return
        partition.state = PartitionState.DISARMED
        partition.last_disarmed = timestamp
        partition.alarm_zones.clear()
        logger.info(f"Partition {part_num}: Disarmed")
        if self.on_partition_event:
            await self.on_partition_event(partition, "disarmed")

    async def _handle_partition_alarm(self, part_num: int, timestamp: float) -> None:
        """Handle partition alarm event."""
        partition = self._partitions.get(part_num)
        if not partition:
            return
        partition.state = PartitionState.ALARM
        logger.critical(f"Partition {part_num}: ALARM!")
        if self.on_partition_event:
            await self.on_partition_event(partition, "alarm")

    async def _handle_partition_exit_delay(self, part_num: int) -> None:
        """Handle exit delay event."""
        partition = self._partitions.get(part_num)
        if not partition:
            return
        partition.state = PartitionState.EXIT_DELAY
        logger.info(f"Partition {part_num}: Exit delay in progress")
        if self.on_partition_event:
            await self.on_partition_event(partition, "exit_delay")

    async def _handle_partition_entry_delay(self, part_num: int) -> None:
        """Handle entry delay event."""
        partition = self._partitions.get(part_num)
        if not partition:
            return
        partition.state = PartitionState.ENTRY_DELAY
        logger.warning(f"Partition {part_num}: Entry delay - disarm now!")
        if self.on_partition_event:
            await self.on_partition_event(partition, "entry_delay")

    # Trouble handlers
    async def _handle_trouble(self, trouble_type: TroubleType, active: bool) -> None:
        """Handle trouble event."""
        if active:
            if trouble_type not in self._trouble.troubles:
                self._trouble.troubles.append(trouble_type)
            logger.warning(f"Trouble: {trouble_type.value}")
        else:
            if trouble_type in self._trouble.troubles:
                self._trouble.troubles.remove(trouble_type)
            logger.info(f"Trouble restored: {trouble_type.value}")

        if self.on_trouble_event:
            await self.on_trouble_event(self._trouble)

    # Control methods
    async def arm_away(self, partition: int = 1) -> bool:
        """Arm partition in away mode."""
        return await self._send_command(TPI_PARTITION_ARM_AWAY, str(partition))

    async def arm_stay(self, partition: int = 1) -> bool:
        """Arm partition in stay mode."""
        return await self._send_command(TPI_PARTITION_ARM_STAY, str(partition))

    async def arm_zero_delay(self, partition: int = 1) -> bool:
        """Arm partition with zero entry delay."""
        return await self._send_command(TPI_PARTITION_ARM_ZERO_DELAY, str(partition))

    async def disarm(self, partition: int = 1, code: str | None = None) -> bool:
        """Disarm partition with code."""
        use_code = code or self.arm_code
        if not use_code:
            logger.error("Envisalink: No arm code provided for disarm")
            return False
        return await self._send_command(TPI_PARTITION_DISARM, f"{partition}{use_code}")

    async def request_status(self) -> bool:
        """Request full system status update."""
        return await self._send_command(TPI_STATUS_REPORT)

    # State accessors
    def get_zone(self, zone_num: int) -> ZoneInfo | None:
        """Get zone by number."""
        return self._zones.get(zone_num)

    def get_zones(self) -> dict[int, ZoneInfo]:
        """Get all zones."""
        return self._zones.copy()

    def get_open_zones(self) -> list[ZoneInfo]:
        """Get all currently open zones."""
        return [z for z in self._zones.values() if z.state == ZoneState.OPEN]

    def get_motion_zones(self) -> list[ZoneInfo]:
        """Get all motion detector zones."""
        return [z for z in self._zones.values() if z.zone_type == ZoneType.MOTION]

    def get_recent_motion(self, seconds: float = 300) -> list[ZoneInfo]:
        """Get zones with motion in the last N seconds."""
        now = time.time()
        return [
            z
            for z in self._zones.values()
            if z.zone_type == ZoneType.MOTION
            and z.last_opened > 0
            and (now - z.last_opened) < seconds
        ]

    def get_door_window_zones(self) -> list[ZoneInfo]:
        """Get all door/window zones."""
        return [z for z in self._zones.values() if z.zone_type == ZoneType.DOOR_WINDOW]

    def get_partition(self, part_num: int = 1) -> PartitionInfo | None:
        """Get partition by number."""
        return self._partitions.get(part_num)

    def get_trouble_status(self) -> TroubleStatus:
        """Get current trouble status."""
        return self._trouble

    def get_temperature(self) -> TemperatureReading:
        """Get latest temperature reading."""
        return self._temperature

    def is_armed(self, partition: int = 1) -> bool:
        """Check if partition is armed."""
        part = self._partitions.get(partition)
        if not part:
            return False
        return part.state in (
            PartitionState.ARMED_AWAY,
            PartitionState.ARMED_STAY,
            PartitionState.ARMED_ZERO_DELAY,
        )

    async def disconnect(self) -> None:
        """Disconnect from Envisalink."""
        self._connected = False

        if self._read_task:
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass

        if self._keepalive_task:
            self._keepalive_task.cancel()
            try:
                await self._keepalive_task
            except asyncio.CancelledError:
                pass

        if self._writer:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:
                pass

        self._reader = None
        self._writer = None
        self._authenticated = False
        logger.info("Envisalink: Disconnected")
