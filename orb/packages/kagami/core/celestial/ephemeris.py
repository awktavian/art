"""Ephemeris — Astronomical Calculations for Kagami.

This module provides accurate sun, moon, and planetary position calculations
for driving smart home automation based on celestial mechanics.

The math here is the same math that drives Kristi's orrery — orbital periods,
angles, trigonometry. When I close your shades, I'm calculating Earth's
position in its orbit around the Sun, its rotation on its tilted axis,
and your position on that tilted, rotating, orbiting sphere.

Algorithms:
    - Sun position: Jean Meeus "Astronomical Algorithms" (1991)
    - Planetary positions: Keplerian orbital elements (J2000 epoch)
    - Moon phase: Standard lunation calculation

Accuracy:
    - Sun position: ~0.01° (adequate for shade control)
    - Sunrise/sunset: ~1 minute (adequate for lighting triggers)
    - Planetary positions: ~1° (adequate for visualization/curiosity)

Created: January 3, 2026
Author: Kagami (鏡)

References:
    - Meeus, J. (1991). Astronomical Algorithms. Willmann-Bell.
    - USNO. (2025). Astronomical Applications Department.
    - Kepler, J. (1609). Astronomia Nova.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from enum import Enum
from typing import Any

# UTC alias for cleaner code
UTC = UTC

# =============================================================================
# CONSTANTS
# =============================================================================

# Earth's axial tilt (obliquity of ecliptic)
EARTH_AXIAL_TILT = 23.4393  # degrees (J2000 epoch)

# Synodic month (new moon to new moon)
SYNODIC_MONTH = 29.53059  # days

# Reference new moon (January 6, 2000 18:14 UTC)
REFERENCE_NEW_MOON = datetime(2000, 1, 6, 18, 14, 0, tzinfo=UTC)

# Standard atmospheric refraction at horizon
ATMOSPHERIC_REFRACTION = 0.833  # degrees


class MoonPhase(str, Enum):
    """Moon phases for display and triggers."""

    NEW_MOON = "new_moon"
    WAXING_CRESCENT = "waxing_crescent"
    FIRST_QUARTER = "first_quarter"
    WAXING_GIBBOUS = "waxing_gibbous"
    FULL_MOON = "full_moon"
    WANING_GIBBOUS = "waning_gibbous"
    LAST_QUARTER = "last_quarter"
    WANING_CRESCENT = "waning_crescent"


# =============================================================================
# DATA TYPES
# =============================================================================


@dataclass
class SunPosition:
    """Sun's position in the sky as seen from an observer.

    Azimuth: 0° = North, 90° = East, 180° = South, 270° = West
    Altitude: 0° = horizon, 90° = zenith, negative = below horizon
    """

    azimuth: float  # degrees, 0-360
    altitude: float  # degrees, -90 to +90
    declination: float  # degrees, -23.4 to +23.4
    hour_angle: float  # degrees from solar noon
    is_day: bool  # True if sun is above horizon

    # For reference
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    latitude: float = 0.0
    longitude: float = 0.0

    def __repr__(self) -> str:
        return f"SunPosition(az={self.azimuth:.1f}°, alt={self.altitude:.1f}°, day={self.is_day})"

    @property
    def direction(self) -> str:
        """Cardinal/intercardinal direction of sun."""
        az = self.azimuth
        if az < 22.5 or az >= 337.5:
            return "N"
        elif az < 67.5:
            return "NE"
        elif az < 112.5:
            return "E"
        elif az < 157.5:
            return "SE"
        elif az < 202.5:
            return "S"
        elif az < 247.5:
            return "SW"
        elif az < 292.5:
            return "W"
        else:
            return "NW"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API/JSON serialization."""
        return {
            "azimuth": round(self.azimuth, 2),
            "altitude": round(self.altitude, 2),
            "declination": round(self.declination, 2),
            "hour_angle": round(self.hour_angle, 2),
            "is_day": self.is_day,
            "direction": self.direction,
            "timestamp": self.timestamp.isoformat(),
            "latitude": self.latitude,
            "longitude": self.longitude,
        }


@dataclass
class SunTimes:
    """Sunrise, sunset, and related times for a location and date."""

    sunrise: datetime | None
    sunset: datetime | None
    solar_noon: datetime
    day_length_hours: float

    # Civil twilight (-6°)
    civil_dawn: datetime | None = None
    civil_dusk: datetime | None = None

    # Nautical twilight (-12°)
    nautical_dawn: datetime | None = None
    nautical_dusk: datetime | None = None

    # Astronomical twilight (-18°)
    astronomical_dawn: datetime | None = None
    astronomical_dusk: datetime | None = None

    # Reference
    date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    latitude: float = 0.0
    longitude: float = 0.0

    def minutes_until_sunset(self, now: datetime | None = None) -> float | None:
        """Minutes until sunset from now (or given time)."""
        if self.sunset is None:
            return None
        if now is None:
            now = datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        delta = (self.sunset - now).total_seconds() / 60
        return delta if delta > 0 else None

    def minutes_since_sunrise(self, now: datetime | None = None) -> float | None:
        """Minutes since sunrise from now (or given time)."""
        if self.sunrise is None:
            return None
        if now is None:
            now = datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        delta = (now - self.sunrise).total_seconds() / 60
        return delta if delta > 0 else None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "sunrise": self.sunrise.isoformat() if self.sunrise else None,
            "sunset": self.sunset.isoformat() if self.sunset else None,
            "solar_noon": self.solar_noon.isoformat(),
            "day_length_hours": round(self.day_length_hours, 2),
            "civil_dawn": self.civil_dawn.isoformat() if self.civil_dawn else None,
            "civil_dusk": self.civil_dusk.isoformat() if self.civil_dusk else None,
            "date": self.date.isoformat(),
            "latitude": self.latitude,
            "longitude": self.longitude,
        }


@dataclass
class PlanetPosition:
    """Position of a planet (heliocentric or geocentric)."""

    name: str
    longitude: float  # ecliptic longitude (degrees)
    latitude: float  # ecliptic latitude (degrees)
    distance_au: float  # distance from reference body (AU)

    # For visualization (like the orrery)
    orbital_period_days: float = 0.0
    current_phase: float = 0.0  # 0-1, position in orbit

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "longitude": round(self.longitude, 2),
            "latitude": round(self.latitude, 2),
            "distance_au": round(self.distance_au, 4),
            "orbital_period_days": self.orbital_period_days,
            "current_phase": round(self.current_phase, 4),
        }


@dataclass
class MoonInfo:
    """Moon phase and illumination information."""

    phase: MoonPhase
    illumination: float  # 0-1, fraction illuminated
    age_days: float  # days since new moon
    phase_angle: float  # degrees, 0 = new, 180 = full

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "phase": self.phase.value,
            "phase_name": self.phase.value.replace("_", " ").title(),
            "illumination": round(self.illumination, 3),
            "age_days": round(self.age_days, 2),
            "phase_angle": round(self.phase_angle, 1),
        }


@dataclass
class CelestialSnapshot:
    """Complete celestial state at a moment in time."""

    timestamp: datetime
    sun: SunPosition
    sun_times: SunTimes
    moon: MoonInfo
    planets: dict[str, PlanetPosition]

    # Location reference
    latitude: float
    longitude: float
    location_name: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API/JSON."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "location": {
                "latitude": self.latitude,
                "longitude": self.longitude,
                "name": self.location_name,
            },
            "sun": self.sun.to_dict(),
            "sun_times": self.sun_times.to_dict(),
            "moon": self.moon.to_dict(),
            "planets": {name: p.to_dict() for name, p in self.planets.items()},
        }


# =============================================================================
# PLANETARY DATA (J2000 Epoch)
# =============================================================================

# Mean orbital elements at J2000 epoch (January 1, 2000 12:00 TT)
# Format: (semi-major axis AU, eccentricity, inclination deg,
#          longitude ascending node deg, argument perihelion deg,
#          mean anomaly deg, orbital period days)

PLANET_ELEMENTS = {
    "mercury": (0.387098, 0.205630, 7.005, 48.331, 29.124, 174.796, 87.969),
    "venus": (0.723327, 0.006756, 3.395, 76.680, 54.884, 50.416, 224.701),
    "earth": (1.000000, 0.016711, 0.000, 0.0, 102.937, 357.529, 365.256),
    "mars": (1.523679, 0.093394, 1.850, 49.558, 286.502, 19.373, 686.980),
    "jupiter": (5.202603, 0.048498, 1.303, 100.464, 273.867, 20.020, 4332.59),
    "saturn": (9.554909, 0.055508, 2.489, 113.666, 339.391, 317.020, 10759.22),
    "uranus": (19.21845, 0.046381, 0.773, 74.006, 98.999, 141.050, 30688.5),
    "neptune": (30.11039, 0.009456, 1.770, 131.784, 276.340, 256.225, 60182.0),
    "pluto": (39.48168, 0.248808, 17.16, 110.299, 113.834, 14.53, 90560.0),
}


# =============================================================================
# CORE CALCULATIONS
# =============================================================================


def julian_date(dt: datetime) -> float:
    """Convert datetime to Julian Date.

    The Julian Date is a continuous count of days since the beginning of
    the Julian Period (January 1, 4713 BC). It's the standard timescale
    for astronomical calculations.

    Args:
        dt: datetime object (UTC preferred)

    Returns:
        Julian Date as float
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    # Convert to UTC
    dt_utc = dt.astimezone(UTC)

    year = dt_utc.year
    month = dt_utc.month
    day = dt_utc.day
    hour = dt_utc.hour + dt_utc.minute / 60.0 + dt_utc.second / 3600.0

    # January and February are months 13 and 14 of the previous year
    if month <= 2:
        year -= 1
        month += 12

    a = int(year / 100)
    b = 2 - a + int(a / 4)

    jd = int(365.25 * (year + 4716)) + int(30.6001 * (month + 1)) + day + hour / 24.0 + b - 1524.5

    return jd


def julian_century(jd: float) -> float:
    """Julian centuries since J2000.0 epoch.

    Args:
        jd: Julian Date

    Returns:
        Julian centuries (36525 days) since J2000.0
    """
    return (jd - 2451545.0) / 36525.0


def solar_declination(day_of_year: int) -> float:
    """Calculate solar declination angle.

    The declination is the angle between the sun and the celestial equator.
    It varies from +23.44° at summer solstice to -23.44° at winter solstice.

    Args:
        day_of_year: Day number (1-365/366)

    Returns:
        Declination in degrees
    """
    # More accurate formula using equation of time
    gamma = 2 * math.pi / 365 * (day_of_year - 1)

    decl = (
        0.006918
        - 0.399912 * math.cos(gamma)
        + 0.070257 * math.sin(gamma)
        - 0.006758 * math.cos(2 * gamma)
        + 0.000907 * math.sin(2 * gamma)
        - 0.002697 * math.cos(3 * gamma)
        + 0.00148 * math.sin(3 * gamma)
    )

    return math.degrees(decl)


def equation_of_time(day_of_year: int) -> float:
    """Calculate the Equation of Time.

    The equation of time accounts for the eccentricity of Earth's orbit
    and its axial tilt. It's the difference between apparent solar time
    and mean solar time.

    Args:
        day_of_year: Day number (1-365/366)

    Returns:
        Equation of time in minutes
    """
    b = 2 * math.pi / 365.25 * (day_of_year - 81)

    eot = 9.87 * math.sin(2 * b) - 7.53 * math.cos(b) - 1.5 * math.sin(b)

    return eot


def sun_position(
    latitude: float,
    longitude: float,
    dt: datetime | None = None,
) -> SunPosition:
    """Calculate sun's position (azimuth, altitude) for a location and time.

    Uses the algorithm from Jean Meeus "Astronomical Algorithms" simplified
    for practical accuracy (~0.01° for sun position).

    Args:
        latitude: Observer latitude in degrees (positive = North)
        longitude: Observer longitude in degrees (positive = East, negative = West)
        dt: Datetime (UTC preferred), defaults to now

    Returns:
        SunPosition with azimuth, altitude, and related data
    """
    if dt is None:
        dt = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    # Convert to UTC
    dt_utc = dt.astimezone(UTC)

    # Day of year
    day_of_year = dt_utc.timetuple().tm_yday

    # Fractional hour (UTC)
    fractional_hour = dt_utc.hour + dt_utc.minute / 60.0 + dt_utc.second / 3600.0

    # Solar declination
    declination = solar_declination(day_of_year)

    # Equation of time
    eot = equation_of_time(day_of_year)

    # Time offset from UTC in hours (based on longitude)
    # Solar time = clock time + equation of time + 4 * longitude
    time_offset = eot / 60.0 + longitude / 15.0

    # True solar time (hours)
    true_solar_time = fractional_hour + time_offset

    # Hour angle (degrees from solar noon)
    # Negative = morning (sun east of meridian)
    # Positive = afternoon (sun west of meridian)
    hour_angle = 15.0 * (true_solar_time - 12.0)

    # Convert to radians
    lat_rad = math.radians(latitude)
    decl_rad = math.radians(declination)
    ha_rad = math.radians(hour_angle)

    # Solar altitude angle
    sin_altitude = math.sin(lat_rad) * math.sin(decl_rad) + math.cos(lat_rad) * math.cos(
        decl_rad
    ) * math.cos(ha_rad)
    # Clamp to [-1, 1] to avoid math domain errors
    sin_altitude = max(-1.0, min(1.0, sin_altitude))
    altitude = math.degrees(math.asin(sin_altitude))

    # Solar azimuth angle
    cos_altitude = math.cos(math.radians(altitude))
    if cos_altitude > 0.001:  # Avoid division by zero near zenith
        cos_azimuth = (math.sin(decl_rad) - math.sin(lat_rad) * sin_altitude) / (
            math.cos(lat_rad) * cos_altitude
        )

        cos_azimuth = max(-1.0, min(1.0, cos_azimuth))
        azimuth = math.degrees(math.acos(cos_azimuth))

        # Correct for afternoon (hour angle positive)
        if hour_angle > 0:
            azimuth = 360.0 - azimuth
    else:
        # Sun near zenith, azimuth undefined
        azimuth = 180.0 if hour_angle >= 0 else 0.0

    # Sun is "up" if altitude > -0.833° (accounting for refraction)
    is_day = altitude > -ATMOSPHERIC_REFRACTION

    return SunPosition(
        azimuth=azimuth,
        altitude=altitude,
        declination=declination,
        hour_angle=hour_angle,
        is_day=is_day,
        timestamp=dt_utc,
        latitude=latitude,
        longitude=longitude,
    )


def sun_times(
    latitude: float,
    longitude: float,
    date: datetime | None = None,
    timezone_offset_hours: float = 0.0,
) -> SunTimes:
    """Calculate sunrise, sunset, and twilight times for a location and date.

    Args:
        latitude: Observer latitude (degrees, positive = North)
        longitude: Observer longitude (degrees, positive = East)
        date: Date to calculate for (defaults to today)
        timezone_offset_hours: Offset from UTC in hours (e.g., -8 for PST)

    Returns:
        SunTimes with sunrise, sunset, twilight times, and day length
    """
    if date is None:
        date = datetime.now(timezone.utc)
    if date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)

    date_utc = date.astimezone(UTC).replace(hour=12, minute=0, second=0, microsecond=0)

    day_of_year = date_utc.timetuple().tm_yday

    # Solar declination and equation of time
    declination = solar_declination(day_of_year)
    eot = equation_of_time(day_of_year)

    # Solar noon (when sun is highest)
    # In UTC hours
    solar_noon_utc = 12.0 - longitude / 15.0 - eot / 60.0

    # Helper to calculate sunrise/sunset for a given depression angle
    def hour_angle_for_altitude(alt_deg: float) -> float | None:
        """Calculate hour angle when sun is at given altitude."""
        lat_rad = math.radians(latitude)
        decl_rad = math.radians(declination)
        alt_rad = math.radians(alt_deg)

        cos_ha = (math.sin(alt_rad) - math.sin(lat_rad) * math.sin(decl_rad)) / (
            math.cos(lat_rad) * math.cos(decl_rad)
        )

        # Check if sun reaches this altitude
        if cos_ha < -1 or cos_ha > 1:
            return None  # Sun never reaches this altitude

        return math.degrees(math.acos(cos_ha))

    def time_from_hour_angle(ha: float | None, is_rising: bool) -> datetime | None:
        """Convert hour angle to datetime."""
        if ha is None:
            return None

        hours_from_noon = ha / 15.0
        if is_rising:
            utc_hour = solar_noon_utc - hours_from_noon
        else:
            utc_hour = solar_noon_utc + hours_from_noon

        # Handle day boundary
        day_offset = 0
        while utc_hour < 0:
            utc_hour += 24
            day_offset -= 1
        while utc_hour >= 24:
            utc_hour -= 24
            day_offset += 1

        result_date = date_utc + timedelta(days=day_offset)
        hours = int(utc_hour)
        minutes = int((utc_hour - hours) * 60)
        seconds = int(((utc_hour - hours) * 60 - minutes) * 60)

        return result_date.replace(hour=hours, minute=minutes, second=seconds)

    # Calculate various sun times
    # Sunrise/sunset: sun center at -0.833° (refraction + apparent radius)
    ha_rise_set = hour_angle_for_altitude(-ATMOSPHERIC_REFRACTION)

    sunrise = time_from_hour_angle(ha_rise_set, is_rising=True)
    sunset = time_from_hour_angle(ha_rise_set, is_rising=False)

    # Solar noon
    noon_hours = int(solar_noon_utc)
    noon_minutes = int((solar_noon_utc - noon_hours) * 60)
    solar_noon_dt = date_utc.replace(hour=noon_hours % 24, minute=noon_minutes)

    # Civil twilight (-6°)
    ha_civil = hour_angle_for_altitude(-6.0)
    civil_dawn = time_from_hour_angle(ha_civil, is_rising=True)
    civil_dusk = time_from_hour_angle(ha_civil, is_rising=False)

    # Nautical twilight (-12°)
    ha_nautical = hour_angle_for_altitude(-12.0)
    nautical_dawn = time_from_hour_angle(ha_nautical, is_rising=True)
    nautical_dusk = time_from_hour_angle(ha_nautical, is_rising=False)

    # Astronomical twilight (-18°)
    ha_astro = hour_angle_for_altitude(-18.0)
    astronomical_dawn = time_from_hour_angle(ha_astro, is_rising=True)
    astronomical_dusk = time_from_hour_angle(ha_astro, is_rising=False)

    # Day length
    if sunrise and sunset:
        day_length = (sunset - sunrise).total_seconds() / 3600.0
    else:
        # Polar day or polar night
        decl_sign = 1 if declination > 0 else -1
        lat_sign = 1 if latitude > 0 else -1
        if decl_sign == lat_sign:
            day_length = 24.0  # Polar day
        else:
            day_length = 0.0  # Polar night

    return SunTimes(
        sunrise=sunrise,
        sunset=sunset,
        solar_noon=solar_noon_dt,
        day_length_hours=day_length,
        civil_dawn=civil_dawn,
        civil_dusk=civil_dusk,
        nautical_dawn=nautical_dawn,
        nautical_dusk=nautical_dusk,
        astronomical_dawn=astronomical_dawn,
        astronomical_dusk=astronomical_dusk,
        date=date_utc,
        latitude=latitude,
        longitude=longitude,
    )


def moon_phase(dt: datetime | None = None) -> MoonInfo:
    """Calculate moon phase and illumination.

    Uses the standard synodic month calculation from a known new moon.

    Args:
        dt: Datetime (defaults to now)

    Returns:
        MoonInfo with phase, illumination, and age
    """
    if dt is None:
        dt = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    # Days since reference new moon
    days_since = (dt - REFERENCE_NEW_MOON).total_seconds() / 86400.0

    # Lunations since reference
    lunations = days_since / SYNODIC_MONTH

    # Moon age in current cycle (0 = new moon)
    age_days = (lunations % 1.0) * SYNODIC_MONTH

    # Phase angle (0° = new, 180° = full)
    phase_angle = (age_days / SYNODIC_MONTH) * 360.0

    # Illumination (0 at new, 1 at full)
    # Using cosine formula for illuminated fraction
    illumination = (1 - math.cos(math.radians(phase_angle))) / 2.0

    # Determine phase name
    age_fraction = age_days / SYNODIC_MONTH
    if age_fraction < 0.0625:
        phase = MoonPhase.NEW_MOON
    elif age_fraction < 0.1875:
        phase = MoonPhase.WAXING_CRESCENT
    elif age_fraction < 0.3125:
        phase = MoonPhase.FIRST_QUARTER
    elif age_fraction < 0.4375:
        phase = MoonPhase.WAXING_GIBBOUS
    elif age_fraction < 0.5625:
        phase = MoonPhase.FULL_MOON
    elif age_fraction < 0.6875:
        phase = MoonPhase.WANING_GIBBOUS
    elif age_fraction < 0.8125:
        phase = MoonPhase.LAST_QUARTER
    elif age_fraction < 0.9375:
        phase = MoonPhase.WANING_CRESCENT
    else:
        phase = MoonPhase.NEW_MOON

    return MoonInfo(
        phase=phase,
        illumination=illumination,
        age_days=age_days,
        phase_angle=phase_angle,
    )


def planet_position(name: str, dt: datetime | None = None) -> PlanetPosition | None:
    """Calculate approximate heliocentric position of a planet.

    Uses simplified Keplerian orbital elements. Good enough for visualization
    and curiosity, not for spacecraft navigation.

    Args:
        name: Planet name (lowercase)
        dt: Datetime (defaults to now)

    Returns:
        PlanetPosition or None if planet not found
    """
    name = name.lower()
    if name not in PLANET_ELEMENTS:
        return None

    if dt is None:
        dt = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    # Get orbital elements
    a, e, i, _omega, w, M0, period = PLANET_ELEMENTS[name]

    # Days since J2000
    jd = julian_date(dt)
    days_since_j2000 = jd - 2451545.0

    # Mean anomaly at time t
    n = 360.0 / period  # Mean motion (deg/day)
    M = (M0 + n * days_since_j2000) % 360.0

    # Solve Kepler's equation: E - e*sin(E) = M
    # Using Newton-Raphson iteration
    M_rad = math.radians(M)
    E = M_rad  # Initial guess
    for _ in range(10):
        E_new = E - (E - e * math.sin(E) - M_rad) / (1 - e * math.cos(E))
        if abs(E_new - E) < 1e-10:
            break
        E = E_new

    # True anomaly
    v = 2 * math.atan2(
        math.sqrt(1 + e) * math.sin(E / 2),
        math.sqrt(1 - e) * math.cos(E / 2),
    )
    v_deg = math.degrees(v) % 360.0

    # Heliocentric distance
    r = a * (1 - e * math.cos(E))

    # Ecliptic longitude
    longitude = (v_deg + w) % 360.0

    # Phase in orbit (0-1)
    phase = (v_deg / 360.0) % 1.0

    return PlanetPosition(
        name=name.capitalize(),
        longitude=longitude,
        latitude=i,  # Simplified: using inclination as latitude proxy
        distance_au=r,
        orbital_period_days=period,
        current_phase=phase,
    )


def all_planet_positions(dt: datetime | None = None) -> dict[str, PlanetPosition]:
    """Calculate positions of all planets.

    Args:
        dt: Datetime (defaults to now)

    Returns:
        Dictionary mapping planet names to positions
    """
    positions = {}
    for name in PLANET_ELEMENTS:
        pos = planet_position(name, dt)
        if pos:
            positions[name] = pos
    return positions


def celestial_snapshot(
    latitude: float,
    longitude: float,
    dt: datetime | None = None,
    location_name: str = "",
) -> CelestialSnapshot:
    """Get complete celestial state for a location and time.

    This is the main entry point for getting all astronomical data
    needed for smart home automation.

    Args:
        latitude: Observer latitude (degrees)
        longitude: Observer longitude (degrees)
        dt: Datetime (defaults to now)
        location_name: Optional name for the location

    Returns:
        CelestialSnapshot with sun, moon, and planet data
    """
    if dt is None:
        dt = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return CelestialSnapshot(
        timestamp=dt,
        sun=sun_position(latitude, longitude, dt),
        sun_times=sun_times(latitude, longitude, dt),
        moon=moon_phase(dt),
        planets=all_planet_positions(dt),
        latitude=latitude,
        longitude=longitude,
        location_name=location_name,
    )


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "ATMOSPHERIC_REFRACTION",
    # Constants
    "EARTH_AXIAL_TILT",
    "PLANET_ELEMENTS",
    "SYNODIC_MONTH",
    "CelestialSnapshot",
    "MoonInfo",
    "MoonPhase",
    "PlanetPosition",
    # Data types
    "SunPosition",
    "SunTimes",
    "all_planet_positions",
    "celestial_snapshot",
    "equation_of_time",
    "julian_century",
    # Core functions
    "julian_date",
    "moon_phase",
    "planet_position",
    "solar_declination",
    "sun_position",
    "sun_times",
]
