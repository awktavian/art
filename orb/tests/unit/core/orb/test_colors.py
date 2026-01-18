"""Unit tests for colony colors.

Colony: Crystal (e₇) — Verification

Tests:
    - Color definitions
    - Color conversions (CSS, Swift, LED)
    - get_colony_color function
    - Safety color thresholds
"""

from kagami.core.orb.colors import (
    ColonyColor,
    COLONY_COLORS,
    DEFAULT_COLOR,
    ERROR_COLOR,
    SAFETY_COLOR,
    get_colony_color,
    get_safety_color,
)


class TestColonyColor:
    """Tests for ColonyColor dataclass."""

    def test_color_attributes(self) -> None:
        """Test ColonyColor has required attributes."""
        spark = COLONY_COLORS["spark"]

        assert spark.name == "spark"
        assert spark.hex == "#FF6B35"
        assert spark.rgb == (255, 107, 53)
        assert spark.description == "Phoenix Orange"

    def test_css_rgba(self) -> None:
        """Test CSS rgba string generation."""
        color = ColonyColor("test", "#FFFFFF", (255, 255, 255), "Test")

        assert color.css_rgba(1.0) == "rgba(255, 255, 255, 1.0)"
        assert color.css_rgba(0.5) == "rgba(255, 255, 255, 0.5)"

    def test_swift_color(self) -> None:
        """Test Swift Color initializer string."""
        color = ColonyColor("test", "#000000", (0, 0, 0), "Test")

        result = color.swift_color()
        assert "Color(red:" in result
        assert "0.00" in result

    def test_led_rgbw(self) -> None:
        """Test LED RGBW conversion with white extraction."""
        # Pure white should be all in W channel
        white = ColonyColor("white", "#FFFFFF", (255, 255, 255), "White")
        assert white.led_rgbw() == (0, 0, 0, 255)

        # Pure red should have no white
        red = ColonyColor("red", "#FF0000", (255, 0, 0), "Red")
        assert red.led_rgbw() == (255, 0, 0, 0)

        # Mixed color extracts minimum as white
        mixed = ColonyColor("mixed", "#FF8080", (255, 128, 128), "Mixed")
        r, g, b, w = mixed.led_rgbw()
        assert w == 128  # min(255, 128, 128)
        assert r == 127  # 255 - 128


class TestColonyColors:
    """Tests for colony color definitions."""

    def test_all_colonies_defined(self) -> None:
        """Test that all 7 colonies have colors."""
        expected_colonies = ["spark", "forge", "flow", "nexus", "beacon", "grove", "crystal"]

        for colony in expected_colonies:
            assert colony in COLONY_COLORS, f"Missing color for {colony}"

    def test_colors_are_distinct(self) -> None:
        """Test that each colony has a unique hex color."""
        hex_colors = [c.hex for c in COLONY_COLORS.values()]

        assert len(hex_colors) == len(set(hex_colors)), "Duplicate colony colors found"

    def test_special_colors_defined(self) -> None:
        """Test that special colors are defined."""
        assert DEFAULT_COLOR.name == "idle"
        assert ERROR_COLOR.name == "error"
        assert SAFETY_COLOR.name == "safety"


class TestGetColonyColor:
    """Tests for get_colony_color function."""

    def test_valid_colony(self) -> None:
        """Test getting color for valid colony."""
        color = get_colony_color("spark")
        assert color.hex == "#FF6B35"

    def test_case_insensitive(self) -> None:
        """Test that lookup is case insensitive."""
        assert get_colony_color("SPARK").hex == "#FF6B35"
        assert get_colony_color("Spark").hex == "#FF6B35"

    def test_none_returns_default(self) -> None:
        """Test that None returns default color."""
        color = get_colony_color(None)
        assert color == DEFAULT_COLOR

    def test_unknown_returns_default(self) -> None:
        """Test that unknown colony returns default."""
        color = get_colony_color("unknown_colony")
        assert color == DEFAULT_COLOR


class TestGetSafetyColor:
    """Tests for get_safety_color function."""

    def test_safe_range(self) -> None:
        """Test color for safe h(x) values."""
        # h(x) >= 0.7 should be Crystal (safe)
        color = get_safety_color(0.8)
        assert color.hex == "#E0E0E0"  # Crystal

    def test_caution_range(self) -> None:
        """Test color for caution h(x) values."""
        # 0.3 <= h(x) < 0.7 should be Safety amber
        color = get_safety_color(0.5)
        assert color == SAFETY_COLOR

    def test_danger_range(self) -> None:
        """Test color for dangerous h(x) values."""
        # h(x) < 0.3 should be Error red
        color = get_safety_color(0.1)
        assert color == ERROR_COLOR
