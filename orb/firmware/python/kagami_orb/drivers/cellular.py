"""
Cellular Modem Driver for Kagami Orb

Supports Quectel EG25-G and compatible LTE Cat 4 modems.
Uses AT command interface over serial.

Features:
- LTE Cat 4 (150 Mbps DL / 50 Mbps UL)
- Integrated GNSS
- SMS support
- Data connection management

Reference:
- Quectel EG25-G AT Commands: https://www.quectel.com/product/lte-eg25-g
- 3GPP TS 27.007: AT command set for GSM/UMTS/LTE
"""

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any, Callable, Dict, List, Optional, Tuple
from datetime import datetime

try:
    import serial
    import serial.tools.list_ports
    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS AND DATA TYPES
# =============================================================================

class NetworkType(Enum):
    """Network access technology."""
    NONE = "none"
    GSM = "gsm"           # 2G
    GPRS = "gprs"         # 2.5G
    EDGE = "edge"         # 2.75G
    UMTS = "umts"         # 3G
    HSDPA = "hsdpa"       # 3.5G
    HSUPA = "hsupa"       # 3.5G
    HSPA = "hspa"         # 3.5G
    HSPA_PLUS = "hspa+"   # 3.75G
    LTE = "lte"           # 4G
    LTE_CA = "lte_ca"     # 4G+ (Carrier Aggregation)
    NR5G_NSA = "nr5g_nsa" # 5G NSA
    NR5G_SA = "nr5g_sa"   # 5G SA


class RegistrationStatus(IntEnum):
    """Network registration status (3GPP TS 27.007)."""
    NOT_REGISTERED = 0
    REGISTERED_HOME = 1
    SEARCHING = 2
    DENIED = 3
    UNKNOWN = 4
    REGISTERED_ROAMING = 5


class SIMStatus(Enum):
    """SIM card status."""
    READY = "ready"
    NOT_INSERTED = "not_inserted"
    PIN_REQUIRED = "pin_required"
    PUK_REQUIRED = "puk_required"
    BLOCKED = "blocked"
    ERROR = "error"


class ConnectionState(Enum):
    """Data connection state."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    SUSPENDED = "suspended"
    ERROR = "error"


@dataclass
class SignalQuality:
    """Cellular signal quality metrics."""
    rssi_dbm: int         # Received Signal Strength (-113 to -51 dBm)
    rsrp_dbm: int         # Reference Signal Received Power (LTE)
    rsrq_db: float        # Reference Signal Received Quality (LTE)
    sinr_db: float        # Signal to Interference plus Noise Ratio
    ber: int              # Bit Error Rate (0-7, 99=unknown)
    bars: int             # Signal bars (0-5)
    
    @property
    def quality_percent(self) -> int:
        """Convert RSSI to percentage (0-100)."""
        if self.rssi_dbm <= -113:
            return 0
        if self.rssi_dbm >= -51:
            return 100
        return int((self.rssi_dbm + 113) / 62 * 100)


@dataclass
class CellInfo:
    """Current cell information."""
    mcc: str              # Mobile Country Code
    mnc: str              # Mobile Network Code
    lac: int              # Location Area Code
    cell_id: int          # Cell ID
    operator: str         # Operator name
    network_type: NetworkType
    band: str             # Frequency band
    channel: int          # EARFCN (LTE) or ARFCN


@dataclass
class DataUsage:
    """Data usage statistics."""
    tx_bytes: int
    rx_bytes: int
    session_duration_sec: int
    
    @property
    def total_mb(self) -> float:
        """Total usage in MB."""
        return (self.tx_bytes + self.rx_bytes) / (1024 * 1024)


@dataclass
class ModemInfo:
    """Modem identification information."""
    manufacturer: str
    model: str
    revision: str
    imei: str
    imsi: str
    iccid: str


# =============================================================================
# CELLULAR MODEM DRIVER
# =============================================================================

class CellularModem:
    """
    Driver for LTE cellular modem with AT command interface.
    
    Compatible with:
    - Quectel EG25-G (primary target)
    - Quectel EC25/EC21 series
    - SIMCom SIM7600/SIM7000 series
    - Sierra Wireless modules
    
    Features:
    - Network registration and attachment
    - Data connection (PDP context)
    - Signal quality monitoring
    - SMS send/receive
    - Integrated GNSS control
    """
    
    # AT command timeouts
    TIMEOUT_DEFAULT = 1.0
    TIMEOUT_REGISTRATION = 30.0
    TIMEOUT_CONNECTION = 60.0
    TIMEOUT_SMS = 10.0
    
    def __init__(
        self,
        port: Optional[str] = None,
        baudrate: int = 115200,
        apn: str = "internet",
        simulate: bool = False,
    ):
        """
        Initialize cellular modem driver.
        
        Args:
            port: Serial port (auto-detect if None)
            baudrate: Serial baudrate (115200 typical)
            apn: APN for data connection
            simulate: Run in simulation mode
        """
        self.port = port
        self.baudrate = baudrate
        self.apn = apn
        self.simulate = simulate or not HAS_SERIAL
        
        self._serial: Optional[serial.Serial] = None
        self._initialized = False
        self._connection_state = ConnectionState.DISCONNECTED
        
        # Callbacks
        self._sms_callback: Optional[Callable] = None
        self._network_callback: Optional[Callable] = None
        
        # Simulation state
        self._sim_signal = -75  # dBm
        self._sim_registered = True
        self._sim_connected = False
        
        self._init_modem()
    
    def _init_modem(self) -> None:
        """Initialize modem connection."""
        if self.simulate:
            logger.info("Cellular modem running in simulation mode")
            self._initialized = True
            return
        
        try:
            # Auto-detect port if not specified
            if not self.port:
                self.port = self._find_modem_port()
            
            if not self.port:
                raise RuntimeError("No modem port found")
            
            self._serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=1.0,
                write_timeout=1.0,
            )
            
            # Test communication
            if not self._send_at_ok("AT"):
                raise RuntimeError("Modem not responding")
            
            # Disable echo
            self._send_at_ok("ATE0")
            
            # Set verbose error messages
            self._send_at_ok("AT+CMEE=2")
            
            # Enable network registration URCs
            self._send_at_ok("AT+CREG=2")
            self._send_at_ok("AT+CEREG=2")
            
            self._initialized = True
            logger.info(f"Cellular modem initialized on {self.port}")
            
        except Exception as e:
            logger.error(f"Modem init failed: {e}")
            self.simulate = True
            self._initialized = True
    
    def _find_modem_port(self) -> Optional[str]:
        """Auto-detect modem serial port."""
        if not HAS_SERIAL:
            return None
        
        ports = serial.tools.list_ports.comports()
        for port in ports:
            # Look for common modem identifiers
            if any(x in port.description.lower() for x in ["quectel", "modem", "lte", "usb serial"]):
                return port.device
            if any(x in str(port.vid) for x in ["2c7c", "1e0e"]):  # Quectel, SIMCom VIDs
                return port.device
        
        # Fallback to common paths
        import os
        for path in ["/dev/ttyUSB2", "/dev/ttyUSB0", "/dev/ttyACM0"]:
            if os.path.exists(path):
                return path
        
        return None
    
    def _send_command(
        self,
        command: str,
        timeout: float = TIMEOUT_DEFAULT,
        wait_for: str = "OK",
    ) -> Tuple[bool, List[str]]:
        """
        Send AT command and wait for response.
        
        Args:
            command: AT command to send
            timeout: Response timeout
            wait_for: Expected success response
        
        Returns:
            Tuple of (success, response_lines)
        """
        if self.simulate:
            return self._simulate_command(command)
        
        try:
            # Clear buffer
            self._serial.reset_input_buffer()
            
            # Send command
            self._serial.write(f"{command}\r\n".encode())
            
            # Read response
            lines = []
            start = time.monotonic()
            
            while time.monotonic() - start < timeout:
                if self._serial.in_waiting:
                    line = self._serial.readline().decode().strip()
                    if line:
                        lines.append(line)
                        if line == wait_for:
                            return True, lines
                        if line.startswith("ERROR") or line.startswith("+CME ERROR"):
                            return False, lines
                else:
                    time.sleep(0.01)
            
            return False, lines
            
        except Exception as e:
            logger.error(f"Command failed: {command} - {e}")
            return False, []
    
    def _send_at_ok(self, command: str, timeout: float = TIMEOUT_DEFAULT) -> bool:
        """Send command and check for OK response."""
        success, _ = self._send_command(command, timeout)
        return success
    
    def _simulate_command(self, command: str) -> Tuple[bool, List[str]]:
        """Simulate AT command response."""
        cmd = command.upper()
        
        if cmd == "AT":
            return True, ["OK"]
        
        elif cmd.startswith("AT+CPIN"):
            return True, ["+CPIN: READY", "OK"]
        
        elif cmd.startswith("AT+CSQ"):
            # Convert dBm to CSQ (0-31)
            csq = max(0, min(31, (self._sim_signal + 113) // 2))
            return True, [f"+CSQ: {csq},99", "OK"]
        
        elif cmd.startswith("AT+CREG?"):
            stat = 1 if self._sim_registered else 0
            return True, [f"+CREG: 2,{stat},\"1A2B\",\"0012CDEF\"", "OK"]
        
        elif cmd.startswith("AT+COPS?"):
            return True, ["+COPS: 0,0,\"T-Mobile\",7", "OK"]
        
        elif cmd.startswith("AT+CGATT?"):
            return True, [f"+CGATT: {1 if self._sim_connected else 0}", "OK"]
        
        elif cmd.startswith("AT+CGACT=1"):
            self._sim_connected = True
            return True, ["OK"]
        
        elif cmd.startswith("AT+CGACT=0"):
            self._sim_connected = False
            return True, ["OK"]
        
        elif cmd.startswith("ATI"):
            return True, [
                "Quectel",
                "EG25-G",
                "Revision: EG25GGBR07A08M2G_30.002.30.002",
                "OK"
            ]
        
        elif cmd.startswith("AT+GSN"):
            return True, ["867686041234567", "OK"]
        
        elif cmd.startswith("AT+CIMI"):
            return True, ["310260123456789", "OK"]
        
        elif cmd.startswith("AT+CCID"):
            return True, ["+CCID: 8901260123456789012F", "OK"]
        
        elif cmd.startswith("AT+QGPS"):
            return True, ["OK"]
        
        return True, ["OK"]
    
    def is_initialized(self) -> bool:
        """Check if modem is initialized."""
        return self._initialized
    
    def get_modem_info(self) -> ModemInfo:
        """Get modem identification information."""
        # Manufacturer and model
        success, lines = self._send_command("ATI")
        manufacturer = lines[0] if len(lines) > 0 else "Unknown"
        model = lines[1] if len(lines) > 1 else "Unknown"
        revision = ""
        for line in lines:
            if line.startswith("Revision:"):
                revision = line.split(":", 1)[1].strip()
        
        # IMEI
        success, lines = self._send_command("AT+GSN")
        imei = lines[0] if success and lines else ""
        
        # IMSI
        success, lines = self._send_command("AT+CIMI")
        imsi = lines[0] if success and lines else ""
        
        # ICCID
        success, lines = self._send_command("AT+CCID")
        iccid = ""
        for line in lines:
            if line.startswith("+CCID:"):
                iccid = line.split(":", 1)[1].strip()
        
        return ModemInfo(
            manufacturer=manufacturer,
            model=model,
            revision=revision,
            imei=imei,
            imsi=imsi,
            iccid=iccid,
        )
    
    def get_sim_status(self) -> SIMStatus:
        """Get SIM card status."""
        success, lines = self._send_command("AT+CPIN?")
        
        for line in lines:
            if "+CPIN:" in line:
                status = line.split(":", 1)[1].strip()
                if status == "READY":
                    return SIMStatus.READY
                elif status == "SIM PIN":
                    return SIMStatus.PIN_REQUIRED
                elif status == "SIM PUK":
                    return SIMStatus.PUK_REQUIRED
        
        if not success:
            # Check for specific errors
            for line in lines:
                if "SIM not inserted" in line:
                    return SIMStatus.NOT_INSERTED
        
        return SIMStatus.ERROR
    
    def get_signal_quality(self) -> SignalQuality:
        """Get current signal quality."""
        # Basic signal (CSQ)
        success, lines = self._send_command("AT+CSQ")
        rssi_dbm = -113
        ber = 99
        
        for line in lines:
            if "+CSQ:" in line:
                match = re.search(r'\+CSQ:\s*(\d+),(\d+)', line)
                if match:
                    csq = int(match.group(1))
                    ber = int(match.group(2))
                    if csq == 99:
                        rssi_dbm = -999  # Not known
                    else:
                        rssi_dbm = -113 + (csq * 2)
        
        # LTE-specific metrics (Quectel)
        rsrp_dbm = -140
        rsrq_db = -20.0
        sinr_db = -20.0
        
        success, lines = self._send_command("AT+QENG=\"servingcell\"")
        for line in lines:
            if "+QENG:" in line and "LTE" in line:
                # Parse LTE serving cell info
                parts = line.split(",")
                if len(parts) > 13:
                    try:
                        rsrp_dbm = int(parts[12]) if parts[12] else -140
                        rsrq_db = float(parts[13]) if parts[13] else -20.0
                        sinr_db = float(parts[14]) if len(parts) > 14 and parts[14] else -20.0
                    except (ValueError, IndexError):
                        pass
        
        # Calculate bars
        if rssi_dbm <= -113:
            bars = 0
        elif rssi_dbm >= -51:
            bars = 5
        else:
            bars = int((rssi_dbm + 113) / 12) + 1
        
        return SignalQuality(
            rssi_dbm=rssi_dbm,
            rsrp_dbm=rsrp_dbm,
            rsrq_db=rsrq_db,
            sinr_db=sinr_db,
            ber=ber,
            bars=bars,
        )
    
    def get_registration_status(self) -> Tuple[RegistrationStatus, Optional[CellInfo]]:
        """Get network registration status and cell info."""
        success, lines = self._send_command("AT+CREG?")
        
        status = RegistrationStatus.UNKNOWN
        cell_info = None
        
        for line in lines:
            if "+CREG:" in line:
                # Format: +CREG: <n>,<stat>[,<lac>,<ci>[,<AcT>]]
                match = re.search(r'\+CREG:\s*\d+,(\d+)(?:,"([^"]+)","([^"]+)")?', line)
                if match:
                    stat = int(match.group(1))
                    status = RegistrationStatus(stat) if stat < 6 else RegistrationStatus.UNKNOWN
                    
                    if match.group(2) and match.group(3):
                        lac = int(match.group(2), 16)
                        cell_id = int(match.group(3), 16)
                        
                        # Get operator info
                        op_success, op_lines = self._send_command("AT+COPS?")
                        operator = ""
                        network_type = NetworkType.NONE
                        
                        for op_line in op_lines:
                            if "+COPS:" in op_line:
                                op_match = re.search(r'\+COPS:\s*\d+,\d+,"([^"]+)",(\d+)', op_line)
                                if op_match:
                                    operator = op_match.group(1)
                                    act = int(op_match.group(2))
                                    network_type = {
                                        0: NetworkType.GSM,
                                        2: NetworkType.UMTS,
                                        3: NetworkType.EDGE,
                                        4: NetworkType.HSDPA,
                                        5: NetworkType.HSUPA,
                                        6: NetworkType.HSPA,
                                        7: NetworkType.LTE,
                                        8: NetworkType.LTE_CA,
                                        11: NetworkType.NR5G_NSA,
                                        12: NetworkType.NR5G_SA,
                                    }.get(act, NetworkType.NONE)
                        
                        cell_info = CellInfo(
                            mcc="",
                            mnc="",
                            lac=lac,
                            cell_id=cell_id,
                            operator=operator,
                            network_type=network_type,
                            band="",
                            channel=0,
                        )
        
        return status, cell_info
    
    def connect(self, timeout: float = TIMEOUT_CONNECTION) -> bool:
        """
        Establish data connection.
        
        Args:
            timeout: Connection timeout in seconds
        
        Returns:
            True if connected successfully
        """
        self._connection_state = ConnectionState.CONNECTING
        
        try:
            # Check registration
            status, _ = self.get_registration_status()
            if status not in [RegistrationStatus.REGISTERED_HOME, RegistrationStatus.REGISTERED_ROAMING]:
                logger.error("Not registered to network")
                self._connection_state = ConnectionState.ERROR
                return False
            
            # Set APN
            self._send_at_ok(f'AT+CGDCONT=1,"IP","{self.apn}"')
            
            # Activate PDP context
            success = self._send_at_ok("AT+CGACT=1,1", timeout=timeout)
            
            if success:
                self._connection_state = ConnectionState.CONNECTED
                logger.info("Data connection established")
                return True
            else:
                self._connection_state = ConnectionState.ERROR
                return False
                
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            self._connection_state = ConnectionState.ERROR
            return False
    
    def disconnect(self) -> bool:
        """Disconnect data connection."""
        success = self._send_at_ok("AT+CGACT=0,1")
        if success:
            self._connection_state = ConnectionState.DISCONNECTED
        return success
    
    def is_connected(self) -> bool:
        """Check if data connection is active."""
        success, lines = self._send_command("AT+CGATT?")
        
        for line in lines:
            if "+CGATT:" in line:
                attached = "1" in line
                self._connection_state = ConnectionState.CONNECTED if attached else ConnectionState.DISCONNECTED
                return attached
        
        return False
    
    def get_connection_state(self) -> ConnectionState:
        """Get current connection state."""
        return self._connection_state
    
    def send_sms(self, number: str, message: str) -> bool:
        """
        Send SMS message.
        
        Args:
            number: Destination phone number
            message: Message text
        
        Returns:
            True if sent successfully
        """
        # Set text mode
        self._send_at_ok("AT+CMGF=1")
        
        # Set character set
        self._send_at_ok('AT+CSCS="GSM"')
        
        # Send SMS
        success, _ = self._send_command(f'AT+CMGS="{number}"', timeout=2.0, wait_for=">")
        if not success:
            return False
        
        if self.simulate:
            return True
        
        # Send message body
        self._serial.write(f"{message}\x1A".encode())
        
        # Wait for response
        success, _ = self._send_command("", timeout=self.TIMEOUT_SMS)
        return success
    
    def enable_gnss(self) -> bool:
        """Enable integrated GNSS receiver."""
        return self._send_at_ok("AT+QGPS=1")
    
    def disable_gnss(self) -> bool:
        """Disable integrated GNSS receiver."""
        return self._send_at_ok("AT+QGPSEND")
    
    def get_gnss_location(self) -> Optional[Tuple[float, float, float]]:
        """
        Get current GNSS location.
        
        Returns:
            Tuple of (latitude, longitude, altitude) or None if no fix
        """
        success, lines = self._send_command("AT+QGPSLOC?")
        
        for line in lines:
            if "+QGPSLOC:" in line:
                # Format: +QGPSLOC: <UTC>,<latitude>,<longitude>,<hdop>,<altitude>,...
                parts = line.split(":", 1)[1].strip().split(",")
                if len(parts) >= 5:
                    try:
                        lat = float(parts[1])
                        lon = float(parts[2])
                        alt = float(parts[4])
                        return (lat, lon, alt)
                    except ValueError:
                        pass
        
        return None
    
    def close(self) -> None:
        """Clean up resources."""
        if self._serial:
            self._serial.close()
            self._serial = None
        self._initialized = False


# =============================================================================
# MODEM MANAGER
# =============================================================================

class ModemManager:
    """
    High-level modem manager with automatic reconnection.
    
    Features:
    - Connection monitoring
    - Automatic reconnection
    - Signal quality tracking
    - Event callbacks
    """
    
    def __init__(
        self,
        modem: Optional[CellularModem] = None,
        auto_connect: bool = True,
        reconnect_interval: float = 30.0,
        simulate: bool = False,
    ):
        """
        Initialize modem manager.
        
        Args:
            modem: Cellular modem instance
            auto_connect: Automatically establish data connection
            reconnect_interval: Seconds between reconnection attempts
            simulate: Run in simulation mode
        """
        self.modem = modem or CellularModem(simulate=simulate)
        self.auto_connect = auto_connect
        self.reconnect_interval = reconnect_interval
        
        self._running = False
        self._task: Optional[asyncio.Task] = None
        
        # State
        self._last_signal: Optional[SignalQuality] = None
        self._last_registration: Optional[RegistrationStatus] = None
    
    async def start(self) -> None:
        """Start the modem manager."""
        self._running = True
        
        if self.auto_connect:
            self.modem.connect()
        
        # Start monitoring task
        self._task = asyncio.create_task(self._monitor_loop())
    
    async def stop(self) -> None:
        """Stop the modem manager."""
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        self.modem.disconnect()
    
    async def _monitor_loop(self) -> None:
        """Background monitoring loop."""
        while self._running:
            try:
                # Update signal quality
                self._last_signal = self.modem.get_signal_quality()
                
                # Check registration
                status, _ = self.modem.get_registration_status()
                self._last_registration = status
                
                # Auto-reconnect if needed
                if self.auto_connect and not self.modem.is_connected():
                    if status in [RegistrationStatus.REGISTERED_HOME, RegistrationStatus.REGISTERED_ROAMING]:
                        logger.info("Reconnecting...")
                        self.modem.connect()
                
                await asyncio.sleep(self.reconnect_interval)
                
            except Exception as e:
                logger.error(f"Monitor error: {e}")
                await asyncio.sleep(5.0)
    
    def get_signal_quality(self) -> Optional[SignalQuality]:
        """Get last signal quality reading."""
        return self._last_signal
    
    def is_connected(self) -> bool:
        """Check if data connection is active."""
        return self.modem.is_connected()
    
    def close(self) -> None:
        """Clean up resources."""
        self.modem.close()
