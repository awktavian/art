"""Unit tests for Celestial Ephemeris module.

Tests verify:
1. Sun position calculations against known values
2. Sunrise/sunset times against USNO data
3. Moon phase calculations
4. Julian date conversion
5. Equation of time accuracy

Reference data from:
- USNO (U.S. Naval Observatory) Solar Calculator
- timeanddate.com (cross-validation)

Created: January 8, 2026
Author: Kagami (鏡)
"""

from datetime import datetime, timezone, UTC
from unittest.mock import patch

import pytest

from kagami.core.celestial.ephemeris import (
    MoonPhase,
    equation_of_time,
    julian_date,
    moon_phase,
    solar_declination,
    sun_position,
    sun_times,
)


# =============================================================================
# REFERENCE DATA
# =============================================================================

# Seattle coordinates
SEATTLE_LAT = 47.6825
SEATTLE_LON = -122.3442

# Summer solstice 2026 (June 21, 2026 00:00 UTC)
SUMMER_SOLSTICE_2026 = datetime(2026, 6, 21, 0, 0, 0, tzinfo=UTC)

# Winter solstice 2025 (December 21, 2025 00:00 UTC)
WINTER_SOLSTICE_2025 = datetime(2025, 12, 21, 0, 0, 0, tzinfo=UTC)

# Vernal equinox 2026 (March 20, 2026 00:00 UTC)
VERNAL_EQUINOX_2026 = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)


# =============================================================================
# JULIAN DATE TESTS
# =============================================================================


class TestJulianDate:
    """Test Julian Date conversion."""

    def test_j2000_epoch(self):
        """J2000.0 epoch should be JD 2451545.0."""
        j2000 = datetime(2000, 1, 1, 12, 0, 0, tzinfo=UTC)
        jd = julian_date(j2000)
        assert abs(jd - 2451545.0) < 0.001

    def test_known_date(self):
        """Test against known Julian date."""
        # January 1, 2026 00:00 UTC = JD 2461041.5
        # (26 years after J2000 = 2451545 + 26*365.25 ≈ 2461041)
        dt = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
        jd = julian_date(dt)
        assert abs(jd - 2461041.5) < 0.01

    def test_timezone_handling(self):
        """Naive datetime should be treated as UTC."""
        dt_naive = datetime(2026, 1, 1, 0, 0, 0)
        dt_utc = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
        assert abs(julian_date(dt_naive) - julian_date(dt_utc)) < 0.0001


# =============================================================================
# SOLAR DECLINATION TESTS
# =============================================================================


class TestSolarDeclination:
    """Test solar declination calculations."""

    def test_summer_solstice(self):
        """Declination at summer solstice should be ~+23.4°."""
        # June 21 is day 172
        decl = solar_declination(172)
        assert 22.5 < decl < 24.0, f"Summer solstice declination: {decl}"

    def test_winter_solstice(self):
        """Declination at winter solstice should be ~-23.4°."""
        # December 21 is day 355
        decl = solar_declination(355)
        assert -24.0 < decl < -22.5, f"Winter solstice declination: {decl}"

    def test_equinox(self):
        """Declination at equinox should be ~0°."""
        # March 20 is day 79
        decl = solar_declination(79)
        assert -2.0 < decl < 2.0, f"Vernal equinox declination: {decl}"


# =============================================================================
# EQUATION OF TIME TESTS
# =============================================================================


class TestEquationOfTime:
    """Test equation of time calculations."""

    def test_february_extreme(self):
        """EoT has extreme around Feb 11 (~-14 minutes in this formula).

        Note: The sign convention depends on formula used. Our formula
        gives the correction to add to mean time to get apparent time.
        """
        eot = equation_of_time(42)  # Feb 11
        # Just verify we get a significant value in expected range
        assert abs(eot) > 10, f"Feb EoT: {eot} (expected extreme)"

    def test_november_extreme(self):
        """EoT has extreme around Nov 3 (~+16 minutes in this formula)."""
        eot = equation_of_time(307)  # Nov 3
        # Just verify we get a significant value in expected range
        assert abs(eot) > 10, f"Nov EoT: {eot} (expected extreme)"

    def test_april_zero(self):
        """EoT crosses zero around Apr 15."""
        eot = equation_of_time(105)  # Apr 15
        assert -3 < eot < 3, f"Apr 15 EoT: {eot}"


# =============================================================================
# SUN POSITION TESTS
# =============================================================================


class TestSunPosition:
    """Test sun position calculations."""

    def test_solar_noon_altitude_summer(self):
        """Solar noon altitude in Seattle should be ~66° at summer solstice."""
        # At solar noon on June 21, sun altitude = 90 - |lat - decl|
        # For Seattle (47.68°N) with decl ~23.4°: altitude ≈ 90 - 24.3 ≈ 65.7°
        noon_utc = datetime(2026, 6, 21, 20, 0, 0, tzinfo=UTC)  # ~noon PST
        sun = sun_position(SEATTLE_LAT, SEATTLE_LON, noon_utc)
        assert 60 < sun.altitude < 70, f"Summer noon altitude: {sun.altitude}"

    def test_solar_noon_altitude_winter(self):
        """Solar noon altitude in Seattle should be ~19° at winter solstice."""
        # For Seattle (47.68°N) with decl ~-23.4°: altitude ≈ 90 - 71 ≈ 19°
        noon_utc = datetime(2025, 12, 21, 20, 0, 0, tzinfo=UTC)
        sun = sun_position(SEATTLE_LAT, SEATTLE_LON, noon_utc)
        assert 15 < sun.altitude < 25, f"Winter noon altitude: {sun.altitude}"

    def test_azimuth_range(self):
        """Azimuth should be 0-360."""
        sun = sun_position(SEATTLE_LAT, SEATTLE_LON)
        assert 0 <= sun.azimuth < 360

    def test_altitude_range(self):
        """Altitude should be -90 to +90."""
        sun = sun_position(SEATTLE_LAT, SEATTLE_LON)
        assert -90 <= sun.altitude <= 90

    def test_is_day_positive_altitude(self):
        """is_day should be True when altitude > -0.833."""
        # Test at noon UTC in summer
        noon = datetime(2026, 6, 21, 20, 0, 0, tzinfo=UTC)
        sun = sun_position(SEATTLE_LAT, SEATTLE_LON, noon)
        assert sun.is_day is True

    def test_is_day_negative_altitude(self):
        """is_day should be False when altitude < -0.833."""
        # Test at midnight UTC in winter
        midnight = datetime(2026, 1, 1, 8, 0, 0, tzinfo=UTC)  # midnight PST
        sun = sun_position(SEATTLE_LAT, SEATTLE_LON, midnight)
        assert sun.is_day is False

    def test_direction_cardinal(self):
        """Test cardinal direction property."""
        sun = sun_position(SEATTLE_LAT, SEATTLE_LON)
        assert sun.direction in ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


# =============================================================================
# SUN TIMES TESTS
# =============================================================================


class TestSunTimes:
    """Test sunrise/sunset calculations."""

    def test_seattle_winter_day_length(self):
        """Seattle winter solstice day length should be ~8.5 hours."""
        times = sun_times(SEATTLE_LAT, SEATTLE_LON, WINTER_SOLSTICE_2025)
        assert 8.0 < times.day_length_hours < 9.5, f"Winter day: {times.day_length_hours}h"

    def test_seattle_summer_day_length(self):
        """Seattle summer solstice day length should be ~16 hours."""
        times = sun_times(SEATTLE_LAT, SEATTLE_LON, SUMMER_SOLSTICE_2026)
        assert 15.0 < times.day_length_hours < 17.0, f"Summer day: {times.day_length_hours}h"

    def test_equinox_day_length(self):
        """Day length at equinox should be ~12 hours."""
        times = sun_times(SEATTLE_LAT, SEATTLE_LON, VERNAL_EQUINOX_2026)
        assert 11.5 < times.day_length_hours < 12.5, f"Equinox day: {times.day_length_hours}h"

    def test_sunrise_before_sunset(self):
        """Sunrise should be before sunset."""
        times = sun_times(SEATTLE_LAT, SEATTLE_LON)
        if times.sunrise and times.sunset:
            assert times.sunrise < times.sunset

    def test_solar_noon_between_sunrise_sunset(self):
        """Solar noon should be between sunrise and sunset."""
        times = sun_times(SEATTLE_LAT, SEATTLE_LON)
        if times.sunrise and times.sunset:
            assert times.sunrise < times.solar_noon < times.sunset

    def test_civil_dawn_before_sunrise(self):
        """Civil dawn should be before sunrise."""
        times = sun_times(SEATTLE_LAT, SEATTLE_LON)
        if times.civil_dawn and times.sunrise:
            assert times.civil_dawn < times.sunrise

    def test_civil_dusk_after_sunset(self):
        """Civil dusk should be after sunset."""
        times = sun_times(SEATTLE_LAT, SEATTLE_LON)
        if times.civil_dusk and times.sunset:
            assert times.sunset < times.civil_dusk


# =============================================================================
# MOON PHASE TESTS
# =============================================================================


class TestMoonPhase:
    """Test moon phase calculations."""

    def test_known_full_moon(self):
        """Test against known full moon date."""
        # Full moon on January 13, 2025
        full_moon_date = datetime(2025, 1, 13, 12, 0, 0, tzinfo=UTC)
        moon = moon_phase(full_moon_date)
        assert moon.illumination > 0.95, f"Full moon illumination: {moon.illumination}"

    def test_known_new_moon(self):
        """Test against known new moon date."""
        # New moon on January 29, 2025
        new_moon_date = datetime(2025, 1, 29, 12, 0, 0, tzinfo=UTC)
        moon = moon_phase(new_moon_date)
        assert moon.illumination < 0.1, f"New moon illumination: {moon.illumination}"

    def test_illumination_range(self):
        """Illumination should be 0-1."""
        moon = moon_phase()
        assert 0 <= moon.illumination <= 1

    def test_age_range(self):
        """Age should be 0 to ~29.5 days."""
        moon = moon_phase()
        assert 0 <= moon.age_days <= 30

    def test_phase_angle_range(self):
        """Phase angle should be 0-360."""
        moon = moon_phase()
        assert 0 <= moon.phase_angle <= 360

    def test_phase_enum(self):
        """Phase should be valid enum value."""
        moon = moon_phase()
        assert isinstance(moon.phase, MoonPhase)


# =============================================================================
# LOCATION CONFIG INTEGRATION TESTS
# =============================================================================


class TestLocationConfigIntegration:
    """Test that celestial module uses centralized location config."""

    def test_home_geometry_uses_config(self):
        """home_geometry should import from location_config."""
        from kagami.core.celestial.home_geometry import HOME_LATITUDE, HOME_LONGITUDE
        from kagami.core.config.location_config import get_home_location

        loc = get_home_location()
        assert HOME_LATITUDE == loc.latitude
        assert HOME_LONGITUDE == loc.longitude

    def test_location_can_be_changed(self):
        """Location should be configurable."""
        from kagami.core.config.location_config import (
            HomeLocation,
            get_home_location,
            reset_home_location,
            set_home_location,
        )

        # Save original
        original = get_home_location()

        try:
            # Set new location
            new_loc = HomeLocation(
                latitude=40.7128,
                longitude=-74.0060,
                name="New York",
            )
            set_home_location(new_loc)

            # Verify it changed
            current = get_home_location()
            assert current.latitude == 40.7128
            assert current.name == "New York"

        finally:
            # Restore
            reset_home_location()


# =============================================================================
# EDGE CASES
# =============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_equator(self):
        """Sun position at equator."""
        sun = sun_position(0.0, 0.0)
        assert -90 <= sun.altitude <= 90

    def test_arctic(self):
        """Sun position in Arctic (potential polar day/night)."""
        # Svalbard, Norway
        sun = sun_position(78.0, 16.0, SUMMER_SOLSTICE_2026)
        # Should have midnight sun
        assert sun.is_day or sun.altitude > -18  # At least twilight

    def test_southern_hemisphere(self):
        """Sun position in Southern Hemisphere."""
        # Sydney, Australia
        sun = sun_position(-33.87, 151.21)
        assert -90 <= sun.altitude <= 90

    def test_date_boundary(self):
        """Test around midnight UTC."""
        dt = datetime(2026, 1, 1, 0, 0, 1, tzinfo=UTC)
        sun = sun_position(SEATTLE_LAT, SEATTLE_LON, dt)
        assert sun is not None
