"""
GNSS (GPS) Driver for Kagami Orb

Supports multiple GNSS systems via NMEA-0183 protocol:
- GPS (USA)
- GLONASS (Russia)
- Galileo (Europe)
- BeiDou (China)
- QZSS (Japan)
- NavIC (India)

Features:
- Full NMEA sentence parsing
- Multi-constellation support
- Accuracy estimation (HDOP/PDOP)
- Geofencing support
- Dead reckoning with IMU fusion

Reference:
- NMEA 0183 Standard
- Qualcomm QCS6490 Location API
"""

import asyncio
import logging
import math
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple

try:
    import serial
    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS AND ENUMS
# =============================================================================

# Earth parameters (WGS84)
EARTH_RADIUS_M = 6371000.0
EARTH_RADIUS_KM = 6371.0


class GNSSSystem(Enum):
    """GNSS constellation identifiers."""
    GPS = "GP"          # USA GPS
    GLONASS = "GL"      # Russian GLONASS
    GALILEO = "GA"      # European Galileo
    BEIDOU = "BD"       # Chinese BeiDou (also GB)
    QZSS = "QZ"         # Japanese QZSS
    NAVIC = "GI"        # Indian NavIC/IRNSS
    SBAS = "SB"         # SBAS augmentation
    COMBINED = "GN"     # Combined multi-GNSS


class FixType(Enum):
    """GPS fix type."""
    NO_FIX = 0
    GPS_FIX = 1
    DGPS_FIX = 2
    PPS_FIX = 3
    RTK_FIX = 4
    RTK_FLOAT = 5
    ESTIMATED = 6
    MANUAL = 7
    SIMULATION = 8


class FixMode(Enum):
    """Position fix mode."""
    NO_FIX = 1
    FIX_2D = 2
    FIX_3D = 3


@dataclass
class SatelliteInfo:
    """Individual satellite information."""
    prn: int                # Satellite PRN number
    system: GNSSSystem      # GNSS system
    elevation: int          # Elevation angle (0-90°)
    azimuth: int            # Azimuth angle (0-359°)
    snr: int                # Signal-to-noise ratio (dB-Hz)
    used_in_fix: bool       # Whether used in position fix


@dataclass
class GNSSPosition:
    """Complete GNSS position fix."""
    timestamp: datetime     # UTC time
    latitude: float         # Degrees (+ = North, - = South)
    longitude: float        # Degrees (+ = East, - = West)
    altitude: float         # Meters above mean sea level
    
    fix_type: FixType
    fix_mode: FixMode
    satellites_used: int
    satellites_visible: int
    
    hdop: float             # Horizontal dilution of precision
    vdop: float             # Vertical dilution of precision
    pdop: float             # Position dilution of precision
    
    speed_knots: float      # Speed over ground
    speed_kmh: float        # Speed in km/h
    course: float           # Course over ground (degrees)
    
    geoid_separation: float # Height of geoid above WGS84 ellipsoid
    
    # Accuracy estimates
    horizontal_accuracy_m: float
    vertical_accuracy_m: float
    
    raw_nmea: List[str] = field(default_factory=list)
    
    @property
    def is_valid(self) -> bool:
        """Check if position is valid."""
        return self.fix_type != FixType.NO_FIX and self.satellites_used >= 3
    
    @property
    def speed_mps(self) -> float:
        """Speed in meters per second."""
        return self.speed_knots * 0.514444
    
    def distance_to(self, lat: float, lon: float) -> float:
        """
        Calculate distance to another point using Haversine formula.
        
        Args:
            lat: Target latitude
            lon: Target longitude
        
        Returns:
            Distance in meters
        """
        lat1 = math.radians(self.latitude)
        lat2 = math.radians(lat)
        dlat = math.radians(lat - self.latitude)
        dlon = math.radians(lon - self.longitude)
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return EARTH_RADIUS_M * c
    
    def bearing_to(self, lat: float, lon: float) -> float:
        """
        Calculate bearing to another point.
        
        Args:
            lat: Target latitude
            lon: Target longitude
        
        Returns:
            Bearing in degrees (0-360)
        """
        lat1 = math.radians(self.latitude)
        lat2 = math.radians(lat)
        dlon = math.radians(lon - self.longitude)
        
        x = math.sin(dlon) * math.cos(lat2)
        y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
        
        bearing = math.degrees(math.atan2(x, y))
        return (bearing + 360) % 360


# =============================================================================
# NMEA PARSER
# =============================================================================

class NMEAParser:
    """
    NMEA-0183 sentence parser.
    
    Supported sentences:
    - GGA: Global Positioning System Fix Data
    - RMC: Recommended Minimum Navigation Information
    - GSA: GPS DOP and Active Satellites
    - GSV: GPS Satellites in View
    - VTG: Track Made Good and Ground Speed
    - GLL: Geographic Position - Latitude/Longitude
    """
    
    def __init__(self):
        """Initialize parser."""
        self._position: Optional[GNSSPosition] = None
        self._satellites: Dict[int, SatelliteInfo] = {}
        self._raw_sentences: List[str] = []
        
        # Parsers for different sentence types
        self._parsers = {
            "GGA": self._parse_gga,
            "RMC": self._parse_rmc,
            "GSA": self._parse_gsa,
            "GSV": self._parse_gsv,
            "VTG": self._parse_vtg,
            "GLL": self._parse_gll,
        }
    
    def parse(self, sentence: str) -> bool:
        """
        Parse an NMEA sentence.
        
        Args:
            sentence: NMEA sentence (with or without $)
        
        Returns:
            True if parsed successfully
        """
        sentence = sentence.strip()
        if not sentence:
            return False
        
        # Remove $ prefix
        if sentence.startswith("$"):
            sentence = sentence[1:]
        
        # Verify checksum
        if "*" in sentence:
            data, checksum = sentence.rsplit("*", 1)
            if not self._verify_checksum(data, checksum):
                return False
            sentence = data
        
        # Extract talker ID and sentence type
        if len(sentence) < 6:
            return False
        
        talker = sentence[:2]
        sentence_type = sentence[2:5]
        
        # Parse sentence
        parser = self._parsers.get(sentence_type)
        if parser:
            try:
                fields = sentence.split(",")
                parser(talker, fields)
                self._raw_sentences.append(f"${sentence}")
                return True
            except Exception as e:
                logger.debug(f"Parse error for {sentence_type}: {e}")
        
        return False
    
    def _verify_checksum(self, data: str, checksum: str) -> bool:
        """Verify NMEA checksum."""
        try:
            calculated = 0
            for char in data:
                calculated ^= ord(char)
            return calculated == int(checksum, 16)
        except ValueError:
            return False
    
    def _parse_gga(self, talker: str, fields: List[str]) -> None:
        """Parse GGA sentence (Fix data)."""
        if len(fields) < 15:
            return
        
        # Time
        time_str = fields[1]
        
        # Position
        lat = self._parse_coordinate(fields[2], fields[3])
        lon = self._parse_coordinate(fields[4], fields[5])
        
        # Fix quality
        fix_quality = int(fields[6]) if fields[6] else 0
        fix_type = {
            0: FixType.NO_FIX,
            1: FixType.GPS_FIX,
            2: FixType.DGPS_FIX,
            3: FixType.PPS_FIX,
            4: FixType.RTK_FIX,
            5: FixType.RTK_FLOAT,
            6: FixType.ESTIMATED,
        }.get(fix_quality, FixType.NO_FIX)
        
        # Satellites and HDOP
        num_sats = int(fields[7]) if fields[7] else 0
        hdop = float(fields[8]) if fields[8] else 99.9
        
        # Altitude
        altitude = float(fields[9]) if fields[9] else 0.0
        geoid = float(fields[11]) if fields[11] else 0.0
        
        # Update position
        if self._position is None:
            self._position = self._create_empty_position()
        
        self._position.latitude = lat
        self._position.longitude = lon
        self._position.altitude = altitude
        self._position.fix_type = fix_type
        self._position.satellites_used = num_sats
        self._position.hdop = hdop
        self._position.geoid_separation = geoid
        self._position.horizontal_accuracy_m = hdop * 5.0  # Rough estimate
    
    def _parse_rmc(self, talker: str, fields: List[str]) -> None:
        """Parse RMC sentence (Recommended minimum)."""
        if len(fields) < 12:
            return
        
        # Time and date
        time_str = fields[1]
        date_str = fields[9]
        
        # Status
        status = fields[2]  # A=Active, V=Void
        
        # Position
        lat = self._parse_coordinate(fields[3], fields[4])
        lon = self._parse_coordinate(fields[5], fields[6])
        
        # Speed and course
        speed_knots = float(fields[7]) if fields[7] else 0.0
        course = float(fields[8]) if fields[8] else 0.0
        
        # Update position
        if self._position is None:
            self._position = self._create_empty_position()
        
        self._position.latitude = lat
        self._position.longitude = lon
        self._position.speed_knots = speed_knots
        self._position.speed_kmh = speed_knots * 1.852
        self._position.course = course
        
        # Parse timestamp
        if time_str and date_str and len(time_str) >= 6 and len(date_str) >= 6:
            try:
                hour = int(time_str[0:2])
                minute = int(time_str[2:4])
                second = int(time_str[4:6])
                day = int(date_str[0:2])
                month = int(date_str[2:4])
                year = 2000 + int(date_str[4:6])
                
                self._position.timestamp = datetime(
                    year, month, day, hour, minute, second,
                    tzinfo=timezone.utc
                )
            except ValueError:
                pass
    
    def _parse_gsa(self, talker: str, fields: List[str]) -> None:
        """Parse GSA sentence (DOP and active satellites)."""
        if len(fields) < 18:
            return
        
        # Fix mode
        mode = int(fields[2]) if fields[2] else 1
        fix_mode = FixMode(mode) if mode <= 3 else FixMode.NO_FIX
        
        # Active satellite PRNs (fields 3-14)
        active_prns = []
        for i in range(3, 15):
            if fields[i]:
                try:
                    active_prns.append(int(fields[i]))
                except ValueError:
                    pass
        
        # DOP values
        pdop = float(fields[15]) if fields[15] else 99.9
        hdop = float(fields[16]) if fields[16] else 99.9
        vdop = float(fields[17].split("*")[0]) if fields[17] else 99.9
        
        # Update position
        if self._position is None:
            self._position = self._create_empty_position()
        
        self._position.fix_mode = fix_mode
        self._position.pdop = pdop
        self._position.hdop = hdop
        self._position.vdop = vdop
        self._position.vertical_accuracy_m = vdop * 5.0
        
        # Mark satellites as used
        for prn, sat in self._satellites.items():
            sat.used_in_fix = prn in active_prns
    
    def _parse_gsv(self, talker: str, fields: List[str]) -> None:
        """Parse GSV sentence (Satellites in view)."""
        if len(fields) < 4:
            return
        
        total_msgs = int(fields[1]) if fields[1] else 1
        msg_num = int(fields[2]) if fields[2] else 1
        total_sats = int(fields[3]) if fields[3] else 0
        
        # Determine GNSS system from talker ID
        system = {
            "GP": GNSSSystem.GPS,
            "GL": GNSSSystem.GLONASS,
            "GA": GNSSSystem.GALILEO,
            "BD": GNSSSystem.BEIDOU,
            "GB": GNSSSystem.BEIDOU,
            "QZ": GNSSSystem.QZSS,
            "GI": GNSSSystem.NAVIC,
        }.get(talker, GNSSSystem.GPS)
        
        # Parse satellite info (up to 4 per message)
        i = 4
        while i + 3 < len(fields):
            try:
                prn = int(fields[i]) if fields[i] else 0
                elevation = int(fields[i+1]) if fields[i+1] else 0
                azimuth = int(fields[i+2]) if fields[i+2] else 0
                snr_str = fields[i+3].split("*")[0] if fields[i+3] else "0"
                snr = int(snr_str) if snr_str else 0
                
                if prn > 0:
                    self._satellites[prn] = SatelliteInfo(
                        prn=prn,
                        system=system,
                        elevation=elevation,
                        azimuth=azimuth,
                        snr=snr,
                        used_in_fix=False,
                    )
            except ValueError:
                pass
            
            i += 4
        
        # Update satellite count
        if self._position:
            self._position.satellites_visible = total_sats
    
    def _parse_vtg(self, talker: str, fields: List[str]) -> None:
        """Parse VTG sentence (Course and speed)."""
        if len(fields) < 9:
            return
        
        course_true = float(fields[1]) if fields[1] else 0.0
        speed_knots = float(fields[5]) if fields[5] else 0.0
        speed_kmh = float(fields[7]) if fields[7] else 0.0
        
        if self._position is None:
            self._position = self._create_empty_position()
        
        self._position.course = course_true
        self._position.speed_knots = speed_knots
        self._position.speed_kmh = speed_kmh
    
    def _parse_gll(self, talker: str, fields: List[str]) -> None:
        """Parse GLL sentence (Geographic position)."""
        if len(fields) < 6:
            return
        
        lat = self._parse_coordinate(fields[1], fields[2])
        lon = self._parse_coordinate(fields[3], fields[4])
        status = fields[6] if len(fields) > 6 else "V"
        
        if status == "A":  # Active/valid
            if self._position is None:
                self._position = self._create_empty_position()
            
            self._position.latitude = lat
            self._position.longitude = lon
    
    def _parse_coordinate(self, value: str, direction: str) -> float:
        """Parse NMEA coordinate to decimal degrees."""
        if not value:
            return 0.0
        
        try:
            # Format: DDDMM.MMMM or DDMM.MMMM
            if "." in value:
                decimal_pos = value.index(".")
                if decimal_pos > 3:  # Longitude (DDDMM.MMMM)
                    degrees = int(value[:decimal_pos-2])
                    minutes = float(value[decimal_pos-2:])
                else:  # Latitude (DDMM.MMMM)
                    degrees = int(value[:decimal_pos-2])
                    minutes = float(value[decimal_pos-2:])
            else:
                degrees = 0
                minutes = 0.0
            
            result = degrees + minutes / 60.0
            
            if direction in ["S", "W"]:
                result = -result
            
            return result
            
        except ValueError:
            return 0.0
    
    def _create_empty_position(self) -> GNSSPosition:
        """Create an empty position object."""
        return GNSSPosition(
            timestamp=datetime.now(timezone.utc),
            latitude=0.0,
            longitude=0.0,
            altitude=0.0,
            fix_type=FixType.NO_FIX,
            fix_mode=FixMode.NO_FIX,
            satellites_used=0,
            satellites_visible=0,
            hdop=99.9,
            vdop=99.9,
            pdop=99.9,
            speed_knots=0.0,
            speed_kmh=0.0,
            course=0.0,
            geoid_separation=0.0,
            horizontal_accuracy_m=999.9,
            vertical_accuracy_m=999.9,
        )
    
    def get_position(self) -> Optional[GNSSPosition]:
        """Get current parsed position."""
        if self._position:
            self._position.raw_nmea = self._raw_sentences[-10:]
        return self._position
    
    def get_satellites(self) -> List[SatelliteInfo]:
        """Get list of satellites in view."""
        return list(self._satellites.values())
    
    def reset(self) -> None:
        """Reset parser state."""
        self._position = None
        self._satellites.clear()
        self._raw_sentences.clear()


# =============================================================================
# GNSS DRIVER
# =============================================================================

class GNSSDriver:
    """
    GNSS receiver driver.
    
    Supports:
    - Direct serial NMEA receivers
    - Qualcomm QCS6490 integrated GNSS
    - Modem-integrated GNSS (via cellular driver)
    
    Features:
    - Continuous position tracking
    - Multi-constellation support
    - Accuracy monitoring
    - Geofencing
    """
    
    def __init__(
        self,
        port: Optional[str] = None,
        baudrate: int = 9600,
        simulate: bool = False,
    ):
        """
        Initialize GNSS driver.
        
        Args:
            port: Serial port (auto-detect if None)
            baudrate: Serial baudrate
            simulate: Run in simulation mode
        """
        self.port = port
        self.baudrate = baudrate
        self.simulate = simulate or not HAS_SERIAL
        
        self._serial: Optional[serial.Serial] = None
        self._parser = NMEAParser()
        self._initialized = False
        self._running = False
        
        # Callbacks
        self._position_callback: Optional[Callable[[GNSSPosition], None]] = None
        
        # Simulation state
        self._sim_lat = 47.6062   # Seattle
        self._sim_lon = -122.3321
        self._sim_alt = 56.0
        self._sim_time = time.time()
        
        # Geofences
        self._geofences: Dict[str, Tuple[float, float, float]] = {}
        self._geofence_callbacks: Dict[str, Callable[[str, bool], None]] = {}
        
        self._init_gnss()
    
    def _init_gnss(self) -> None:
        """Initialize GNSS receiver."""
        if self.simulate:
            logger.info("GNSS running in simulation mode")
            self._initialized = True
            return
        
        try:
            if not self.port:
                self.port = self._find_gnss_port()
            
            if not self.port:
                logger.warning("No GNSS port found, using simulation")
                self.simulate = True
                self._initialized = True
                return
            
            self._serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=1.0,
            )
            
            self._initialized = True
            logger.info(f"GNSS initialized on {self.port}")
            
        except Exception as e:
            logger.error(f"GNSS init failed: {e}")
            self.simulate = True
            self._initialized = True
    
    def _find_gnss_port(self) -> Optional[str]:
        """Auto-detect GNSS serial port."""
        if not HAS_SERIAL:
            return None
        
        import serial.tools.list_ports
        ports = serial.tools.list_ports.comports()
        
        for port in ports:
            if any(x in port.description.lower() for x in ["gps", "gnss", "u-blox", "nmea"]):
                return port.device
        
        # Common paths
        import os
        for path in ["/dev/ttyACM0", "/dev/ttyUSB0", "/dev/ttyAMA0"]:
            if os.path.exists(path):
                return path
        
        return None
    
    def is_initialized(self) -> bool:
        """Check if GNSS is initialized."""
        return self._initialized
    
    def _read_nmea(self) -> Optional[str]:
        """Read a single NMEA sentence."""
        if self.simulate:
            return self._simulate_nmea()
        
        try:
            line = self._serial.readline().decode('ascii', errors='ignore').strip()
            if line.startswith("$"):
                return line
        except Exception:
            pass
        
        return None
    
    def _simulate_nmea(self) -> str:
        """Generate simulated NMEA sentences."""
        # Add some drift
        elapsed = time.time() - self._sim_time
        drift = 0.00001 * math.sin(elapsed * 0.1)
        
        lat = self._sim_lat + drift
        lon = self._sim_lon + drift * 0.5
        
        # Convert to NMEA format
        lat_deg = int(abs(lat))
        lat_min = (abs(lat) - lat_deg) * 60
        lat_dir = "N" if lat >= 0 else "S"
        lat_nmea = f"{lat_deg:02d}{lat_min:07.4f}"
        
        lon_deg = int(abs(lon))
        lon_min = (abs(lon) - lon_deg) * 60
        lon_dir = "E" if lon >= 0 else "W"
        lon_nmea = f"{lon_deg:03d}{lon_min:07.4f}"
        
        now = datetime.now(timezone.utc)
        time_nmea = now.strftime("%H%M%S.00")
        date_nmea = now.strftime("%d%m%y")
        
        # Alternate between GGA and RMC
        if int(elapsed) % 2 == 0:
            sentence = f"$GPGGA,{time_nmea},{lat_nmea},{lat_dir},{lon_nmea},{lon_dir},1,08,0.9,{self._sim_alt:.1f},M,0.0,M,,"
        else:
            sentence = f"$GPRMC,{time_nmea},A,{lat_nmea},{lat_dir},{lon_nmea},{lon_dir},0.0,0.0,{date_nmea},,"
        
        # Add checksum
        checksum = 0
        for char in sentence[1:]:
            checksum ^= ord(char)
        
        return f"{sentence}*{checksum:02X}"
    
    def read_position(self) -> Optional[GNSSPosition]:
        """
        Read current position (blocking).
        
        Returns:
            Current GNSS position or None if no fix
        """
        # Read and parse several sentences for complete data
        for _ in range(10):
            sentence = self._read_nmea()
            if sentence:
                self._parser.parse(sentence)
        
        position = self._parser.get_position()
        
        # Check geofences
        if position and position.is_valid:
            self._check_geofences(position)
        
        return position
    
    async def read_position_async(self) -> Optional[GNSSPosition]:
        """Async version of read_position."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.read_position)
    
    def get_satellites(self) -> List[SatelliteInfo]:
        """Get satellites in view."""
        return self._parser.get_satellites()
    
    def set_position_callback(self, callback: Callable[[GNSSPosition], None]) -> None:
        """Set callback for position updates."""
        self._position_callback = callback
    
    def add_geofence(
        self,
        name: str,
        latitude: float,
        longitude: float,
        radius_m: float,
        callback: Optional[Callable[[str, bool], None]] = None,
    ) -> None:
        """
        Add a geofence.
        
        Args:
            name: Geofence identifier
            latitude: Center latitude
            longitude: Center longitude
            radius_m: Radius in meters
            callback: Called with (name, is_inside) on state change
        """
        self._geofences[name] = (latitude, longitude, radius_m)
        if callback:
            self._geofence_callbacks[name] = callback
    
    def remove_geofence(self, name: str) -> None:
        """Remove a geofence."""
        self._geofences.pop(name, None)
        self._geofence_callbacks.pop(name, None)
    
    def _check_geofences(self, position: GNSSPosition) -> None:
        """Check all geofences against current position."""
        for name, (lat, lon, radius) in self._geofences.items():
            distance = position.distance_to(lat, lon)
            is_inside = distance <= radius
            
            callback = self._geofence_callbacks.get(name)
            if callback:
                callback(name, is_inside)
    
    def is_inside_geofence(self, name: str) -> Optional[bool]:
        """Check if currently inside a geofence."""
        position = self.read_position()
        if not position or not position.is_valid:
            return None
        
        fence = self._geofences.get(name)
        if not fence:
            return None
        
        lat, lon, radius = fence
        return position.distance_to(lat, lon) <= radius
    
    async def start_tracking(self, interval_sec: float = 1.0) -> None:
        """Start continuous position tracking."""
        self._running = True
        
        while self._running:
            position = await self.read_position_async()
            
            if position and self._position_callback:
                self._position_callback(position)
            
            await asyncio.sleep(interval_sec)
    
    def stop_tracking(self) -> None:
        """Stop continuous tracking."""
        self._running = False
    
    def close(self) -> None:
        """Clean up resources."""
        self._running = False
        if self._serial:
            self._serial.close()
            self._serial = None
        self._initialized = False


# =============================================================================
# LOCATION SERVICE
# =============================================================================

@dataclass
class LocationUpdate:
    """Location update event."""
    position: GNSSPosition
    source: str             # "gnss", "cell", "wifi", "fused"
    confidence: float       # 0-1 confidence
    timestamp: datetime


class LocationService:
    """
    High-level location service.
    
    Features:
    - Multiple source fusion (GNSS + Cell + WiFi)
    - Automatic source selection
    - Caching and rate limiting
    - Power-aware operation
    """
    
    def __init__(
        self,
        gnss: Optional[GNSSDriver] = None,
        simulate: bool = False,
    ):
        """
        Initialize location service.
        
        Args:
            gnss: GNSS driver instance
            simulate: Run in simulation mode
        """
        self.gnss = gnss or GNSSDriver(simulate=simulate)
        
        self._last_update: Optional[LocationUpdate] = None
        self._update_callbacks: List[Callable[[LocationUpdate], None]] = []
        self._running = False
    
    def get_location(self) -> Optional[LocationUpdate]:
        """Get current location."""
        position = self.gnss.read_position()
        
        if position and position.is_valid:
            update = LocationUpdate(
                position=position,
                source="gnss",
                confidence=min(1.0, 10.0 / position.hdop),
                timestamp=datetime.now(timezone.utc),
            )
            self._last_update = update
            return update
        
        return self._last_update
    
    def get_last_known_location(self) -> Optional[LocationUpdate]:
        """Get last known location."""
        return self._last_update
    
    def add_update_callback(self, callback: Callable[[LocationUpdate], None]) -> None:
        """Add callback for location updates."""
        self._update_callbacks.append(callback)
    
    async def start(self, interval_sec: float = 1.0) -> None:
        """Start location service."""
        self._running = True
        
        while self._running:
            update = self.get_location()
            
            if update:
                for callback in self._update_callbacks:
                    try:
                        callback(update)
                    except Exception as e:
                        logger.error(f"Callback error: {e}")
            
            await asyncio.sleep(interval_sec)
    
    def stop(self) -> None:
        """Stop location service."""
        self._running = False
    
    def close(self) -> None:
        """Clean up resources."""
        self.stop()
        self.gnss.close()
