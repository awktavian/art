"""
Tests for GNSS Driver

Tests cover:
- NMEA sentence parsing
- Position calculation
- Satellite tracking
- Geofencing
- Distance/bearing calculations
"""

import pytest
import math
from datetime import datetime, timezone

import sys
sys.path.insert(0, str(pytest.importorskip("pathlib").Path(__file__).parent.parent))

from kagami_orb.drivers.gnss import (
    GNSSDriver,
    GNSSPosition,
    NMEAParser,
    SatelliteInfo,
    GNSSSystem,
    FixType,
    FixMode,
    LocationService,
    LocationUpdate,
    EARTH_RADIUS_M,
)


def calc_nmea_checksum(sentence: str) -> str:
    """Calculate NMEA checksum for a sentence (without $ or *)."""
    if sentence.startswith("$"):
        sentence = sentence[1:]
    if "*" in sentence:
        sentence = sentence.split("*")[0]
    
    checksum = 0
    for char in sentence:
        checksum ^= ord(char)
    return f"{checksum:02X}"


class TestNMEAParser:
    """Test NMEA sentence parsing."""
    
    @pytest.fixture
    def parser(self):
        return NMEAParser()
    
    def test_parse_gga(self, parser):
        """Test parsing GGA sentence."""
        # Build sentence with correct checksum
        data = "GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,47.0,M,,"
        checksum = calc_nmea_checksum(data)
        sentence = f"${data}*{checksum}"
        
        result = parser.parse(sentence)
        position = parser.get_position()
        
        assert result
        assert position is not None
        assert abs(position.latitude - 48.1173) < 0.001
        assert abs(position.longitude - 11.5167) < 0.001
        assert position.altitude == 545.4
        assert position.satellites_used == 8
        assert position.hdop == 0.9
    
    def test_parse_rmc(self, parser):
        """Test parsing RMC sentence."""
        data = "GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W"
        checksum = calc_nmea_checksum(data)
        sentence = f"${data}*{checksum}"
        
        result = parser.parse(sentence)
        position = parser.get_position()
        
        assert result
        assert position is not None
        assert abs(position.latitude - 48.1173) < 0.001
        assert abs(position.longitude - 11.5167) < 0.001
        assert position.speed_knots == 22.4
        assert position.course == 84.4
    
    def test_parse_gsa(self, parser):
        """Test parsing GSA sentence."""
        # First parse a GGA to create position
        gga_data = "GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,47.0,M,,"
        parser.parse(f"${gga_data}*{calc_nmea_checksum(gga_data)}")
        
        gsa_data = "GPGSA,A,3,04,05,,09,12,,,24,,,,,2.5,1.3,2.1"
        sentence = f"${gsa_data}*{calc_nmea_checksum(gsa_data)}"
        
        result = parser.parse(sentence)
        position = parser.get_position()
        
        assert result
        assert position.fix_mode == FixMode.FIX_3D
        assert position.pdop == 2.5
        assert position.hdop == 1.3
        assert position.vdop == 2.1
    
    def test_parse_gsv(self, parser):
        """Test parsing GSV sentence."""
        gsv_data = "GPGSV,3,1,11,03,03,111,00,04,15,270,00,06,01,010,00,13,06,292,00"
        sentence = f"${gsv_data}*{calc_nmea_checksum(gsv_data)}"
        
        result = parser.parse(sentence)
        satellites = parser.get_satellites()
        
        assert result
        assert len(satellites) >= 4
        
        sat = satellites[0] if satellites else None
        assert sat is not None
        assert sat.system == GNSSSystem.GPS
    
    def test_parse_vtg(self, parser):
        """Test parsing VTG sentence."""
        gga_data = "GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,47.0,M,,"
        parser.parse(f"${gga_data}*{calc_nmea_checksum(gga_data)}")
        
        vtg_data = "GPVTG,054.7,T,034.4,M,005.5,N,010.2,K"
        sentence = f"${vtg_data}*{calc_nmea_checksum(vtg_data)}"
        
        result = parser.parse(sentence)
        position = parser.get_position()
        
        assert result
        assert position.course == 54.7
        assert position.speed_knots == 5.5
        assert position.speed_kmh == 10.2
    
    def test_checksum_validation(self, parser):
        """Test checksum validation."""
        # Valid checksum
        valid_data = "GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,47.0,M,,"
        valid = f"${valid_data}*{calc_nmea_checksum(valid_data)}"
        assert parser.parse(valid)
        
        # Invalid checksum (use wrong checksum)
        invalid = f"${valid_data}*00"
        parser.reset()
        assert not parser.parse(invalid)
    
    def test_coordinate_parsing(self, parser):
        """Test coordinate conversion."""
        # North, East
        ne_data = "GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,47.0,M,,"
        parser.parse(f"${ne_data}*{calc_nmea_checksum(ne_data)}")
        pos = parser.get_position()
        assert pos.latitude > 0
        assert pos.longitude > 0
        
        # South, West
        parser.reset()
        sw_data = "GPGGA,123519,4807.038,S,01131.000,W,1,08,0.9,545.4,M,47.0,M,,"
        parser.parse(f"${sw_data}*{calc_nmea_checksum(sw_data)}")
        pos = parser.get_position()
        assert pos.latitude < 0
        assert pos.longitude < 0


class TestGNSSPosition:
    """Test GNSSPosition dataclass."""
    
    @pytest.fixture
    def position(self):
        return GNSSPosition(
            timestamp=datetime.now(timezone.utc),
            latitude=47.6062,
            longitude=-122.3321,
            altitude=56.0,
            fix_type=FixType.GPS_FIX,
            fix_mode=FixMode.FIX_3D,
            satellites_used=8,
            satellites_visible=12,
            hdop=1.0,
            vdop=1.5,
            pdop=1.8,
            speed_knots=5.0,
            speed_kmh=9.26,
            course=45.0,
            geoid_separation=0.0,
            horizontal_accuracy_m=5.0,
            vertical_accuracy_m=7.5,
        )
    
    def test_is_valid(self, position):
        """Test validity check."""
        assert position.is_valid
        
        position.fix_type = FixType.NO_FIX
        assert not position.is_valid
    
    def test_speed_mps(self, position):
        """Test speed conversion to m/s."""
        # 5 knots ≈ 2.57 m/s
        assert abs(position.speed_mps - 2.57222) < 0.01
    
    def test_distance_to_same_point(self, position):
        """Test distance to same point is zero."""
        dist = position.distance_to(position.latitude, position.longitude)
        assert dist < 1  # Less than 1 meter
    
    def test_distance_to_known_point(self, position):
        """Test distance calculation."""
        # Seattle to Portland ≈ 233 km
        portland_lat = 45.5051
        portland_lon = -122.6750
        
        dist = position.distance_to(portland_lat, portland_lon)
        assert 230000 < dist < 240000  # 230-240 km
    
    def test_bearing_north(self, position):
        """Test bearing calculation north."""
        # Point directly north
        north_lat = position.latitude + 1.0
        north_lon = position.longitude
        
        bearing = position.bearing_to(north_lat, north_lon)
        assert abs(bearing - 0) < 5  # Within 5 degrees of north
    
    def test_bearing_east(self, position):
        """Test bearing calculation east."""
        # Point directly east
        east_lat = position.latitude
        east_lon = position.longitude + 1.0
        
        bearing = position.bearing_to(east_lat, east_lon)
        assert abs(bearing - 90) < 5  # Within 5 degrees of east


class TestGNSSDriver:
    """Test GNSS driver."""
    
    @pytest.fixture
    def gnss(self):
        return GNSSDriver(simulate=True)
    
    def test_initialization(self, gnss):
        """Test driver initializes correctly."""
        assert gnss.is_initialized()
    
    def test_read_position(self, gnss):
        """Test reading position."""
        position = gnss.read_position()
        
        assert position is not None
        # Simulation defaults to Seattle
        assert abs(position.latitude - 47.6062) < 0.01
        assert abs(position.longitude - (-122.3321)) < 0.01
    
    @pytest.mark.asyncio
    async def test_read_position_async(self, gnss):
        """Test async position reading."""
        position = await gnss.read_position_async()
        
        assert position is not None
    
    def test_get_satellites(self, gnss):
        """Test satellite listing."""
        # Read position to populate satellites
        gnss.read_position()
        satellites = gnss.get_satellites()
        
        # May be empty in simulation without GSV
        assert isinstance(satellites, list)
    
    def test_geofence_add_remove(self, gnss):
        """Test geofence management."""
        gnss.add_geofence("home", 47.6062, -122.3321, 100.0)
        
        assert "home" in gnss._geofences
        
        gnss.remove_geofence("home")
        
        assert "home" not in gnss._geofences
    
    def test_geofence_inside(self, gnss):
        """Test geofence containment check."""
        # Add geofence around simulation location
        gnss.add_geofence("home", 47.6062, -122.3321, 1000.0)
        
        is_inside = gnss.is_inside_geofence("home")
        
        assert is_inside is True
    
    def test_geofence_outside(self, gnss):
        """Test geofence outside check."""
        # Add geofence far away
        gnss.add_geofence("far_away", 0.0, 0.0, 100.0)
        
        is_inside = gnss.is_inside_geofence("far_away")
        
        assert is_inside is False
    
    def test_geofence_callback(self, gnss):
        """Test geofence callback."""
        callback_results = []
        
        def on_geofence(name: str, is_inside: bool):
            callback_results.append((name, is_inside))
        
        gnss.add_geofence("test", 47.6062, -122.3321, 1000.0, on_geofence)
        gnss.read_position()
        
        assert len(callback_results) > 0
        assert callback_results[0][0] == "test"
        assert callback_results[0][1] is True


class TestLocationService:
    """Test location service."""
    
    @pytest.fixture
    def service(self):
        return LocationService(simulate=True)
    
    def test_get_location(self, service):
        """Test getting current location."""
        update = service.get_location()
        
        assert update is not None
        assert isinstance(update, LocationUpdate)
        assert update.source == "gnss"
    
    def test_get_last_known_location(self, service):
        """Test last known location caching."""
        # First get creates cache
        service.get_location()
        
        # Last known should return cached value
        update = service.get_last_known_location()
        
        assert update is not None
    
    def test_location_callback(self, service):
        """Test location update callback."""
        updates = []
        
        def on_update(update: LocationUpdate):
            updates.append(update)
        
        service.add_update_callback(on_update)
        service.get_location()
        
        # Callback isn't called for manual get, only for start()
        # Just verify callback was registered
        assert len(service._update_callbacks) == 1


class TestGNSSSystemEnum:
    """Test GNSS system enumeration."""
    
    def test_gnss_systems(self):
        """Test GNSS system values."""
        assert GNSSSystem.GPS.value == "GP"
        assert GNSSSystem.GLONASS.value == "GL"
        assert GNSSSystem.GALILEO.value == "GA"
        assert GNSSSystem.BEIDOU.value == "BD"
        assert GNSSSystem.QZSS.value == "QZ"
        assert GNSSSystem.COMBINED.value == "GN"


class TestFixTypes:
    """Test fix type enumerations."""
    
    def test_fix_types(self):
        """Test fix type values."""
        assert FixType.NO_FIX.value == 0
        assert FixType.GPS_FIX.value == 1
        assert FixType.DGPS_FIX.value == 2
        assert FixType.RTK_FIX.value == 4
    
    def test_fix_modes(self):
        """Test fix mode values."""
        assert FixMode.NO_FIX.value == 1
        assert FixMode.FIX_2D.value == 2
        assert FixMode.FIX_3D.value == 3


class TestDistanceCalculations:
    """Test distance and bearing calculations."""
    
    def test_haversine_formula(self):
        """Test Haversine distance calculation."""
        # New York to Los Angeles ≈ 3940 km
        pos = GNSSPosition(
            timestamp=datetime.now(timezone.utc),
            latitude=40.7128,
            longitude=-74.0060,
            altitude=0,
            fix_type=FixType.GPS_FIX,
            fix_mode=FixMode.FIX_3D,
            satellites_used=8,
            satellites_visible=10,
            hdop=1.0,
            vdop=1.0,
            pdop=1.5,
            speed_knots=0,
            speed_kmh=0,
            course=0,
            geoid_separation=0,
            horizontal_accuracy_m=5,
            vertical_accuracy_m=5,
        )
        
        la_lat = 34.0522
        la_lon = -118.2437
        
        dist = pos.distance_to(la_lat, la_lon)
        
        # Should be approximately 3940 km = 3940000 m
        assert 3900000 < dist < 4000000
    
    def test_bearing_wraparound(self):
        """Test bearing handles wraparound correctly."""
        pos = GNSSPosition(
            timestamp=datetime.now(timezone.utc),
            latitude=0,
            longitude=0,
            altitude=0,
            fix_type=FixType.GPS_FIX,
            fix_mode=FixMode.FIX_3D,
            satellites_used=8,
            satellites_visible=10,
            hdop=1.0,
            vdop=1.0,
            pdop=1.5,
            speed_knots=0,
            speed_kmh=0,
            course=0,
            geoid_separation=0,
            horizontal_accuracy_m=5,
            vertical_accuracy_m=5,
        )
        
        # Point to the west
        bearing = pos.bearing_to(0, -10)
        
        # Should be ~270 degrees (west)
        assert 265 < bearing < 275


class TestSatelliteInfo:
    """Test satellite information."""
    
    def test_satellite_dataclass(self):
        """Test SatelliteInfo dataclass."""
        sat = SatelliteInfo(
            prn=12,
            system=GNSSSystem.GPS,
            elevation=45,
            azimuth=180,
            snr=35,
            used_in_fix=True,
        )
        
        assert sat.prn == 12
        assert sat.system == GNSSSystem.GPS
        assert sat.elevation == 45
        assert sat.azimuth == 180
        assert sat.snr == 35
        assert sat.used_in_fix


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
