"""Tests for input validation — Pydantic models.

Tests all validation rules for SmartHome API inputs.

Created: January 2, 2026
"""

import pytest
from pydantic import ValidationError

from kagami_smarthome.validation import (
    VALID_ROOMS,
    AnnounceCommand,
    LightCommand,
    LockCommand,
    SceneCommand,
    ShadeCommand,
    SpotifyCommand,
    TemperatureCommand,
    TVMountCommand,
    validate_command,
)


class TestLightCommand:
    """Tests for LightCommand validation."""

    def test_valid_light_command(self):
        """Valid light command passes."""
        cmd = LightCommand(level=50, rooms=["Living Room"])
        assert cmd.level == 50
        assert cmd.rooms == ["Living Room"]

    def test_level_range(self):
        """Level must be 0-100."""
        # Valid range
        LightCommand(level=0, rooms=["Living Room"])
        LightCommand(level=100, rooms=["Living Room"])

        # Invalid range
        with pytest.raises(ValidationError):
            LightCommand(level=-1, rooms=["Living Room"])
        with pytest.raises(ValidationError):
            LightCommand(level=101, rooms=["Living Room"])

    def test_invalid_room(self):
        """Invalid room name raises error."""
        with pytest.raises(ValidationError) as exc_info:
            LightCommand(level=50, rooms=["Invalid Room"])
        assert "Unknown rooms" in str(exc_info.value)

    def test_empty_rooms(self):
        """Empty rooms list raises error."""
        with pytest.raises(ValidationError):
            LightCommand(level=50, rooms=[])

    def test_multiple_rooms(self):
        """Multiple valid rooms work."""
        cmd = LightCommand(level=50, rooms=["Living Room", "Kitchen", "Dining"])
        assert len(cmd.rooms) == 3

    def test_fade_duration(self):
        """Fade duration validation."""
        cmd = LightCommand(level=50, rooms=["Living Room"], fade_seconds=5.0)
        assert cmd.fade_seconds == 5.0

        with pytest.raises(ValidationError):
            LightCommand(level=50, rooms=["Living Room"], fade_seconds=-1)
        with pytest.raises(ValidationError):
            LightCommand(level=50, rooms=["Living Room"], fade_seconds=100)


class TestShadeCommand:
    """Tests for ShadeCommand validation."""

    def test_valid_shade_command(self):
        """Valid shade command passes."""
        cmd = ShadeCommand(position=50, rooms=["Living Room"])
        assert cmd.position == 50

    def test_position_range(self):
        """Position must be 0-100."""
        ShadeCommand(position=0, rooms=["Living Room"])  # Closed
        ShadeCommand(position=100, rooms=["Living Room"])  # Open

        with pytest.raises(ValidationError):
            ShadeCommand(position=-1, rooms=["Living Room"])


class TestTVMountCommand:
    """Tests for TVMountCommand validation."""

    def test_valid_presets(self):
        """Valid presets 1-4 work."""
        for preset in (1, 2, 3, 4):
            cmd = TVMountCommand(preset=preset)
            assert cmd.preset == preset

    def test_invalid_preset(self):
        """Invalid preset raises error."""
        with pytest.raises(ValidationError):
            TVMountCommand(preset=0)
        with pytest.raises(ValidationError):
            TVMountCommand(preset=5)


class TestTemperatureCommand:
    """Tests for TemperatureCommand validation."""

    def test_valid_temperature(self):
        """Valid temperature range."""
        cmd = TemperatureCommand(temp_f=72, room="Office")
        assert cmd.temp_f == 72

    def test_temperature_range(self):
        """Temperature must be 60-85."""
        TemperatureCommand(temp_f=60, room="Office")
        TemperatureCommand(temp_f=85, room="Office")

        with pytest.raises(ValidationError):
            TemperatureCommand(temp_f=59, room="Office")
        with pytest.raises(ValidationError):
            TemperatureCommand(temp_f=86, room="Office")


class TestAnnounceCommand:
    """Tests for AnnounceCommand validation."""

    def test_valid_announce(self):
        """Valid announce command."""
        cmd = AnnounceCommand(text="Hello Tim")
        assert cmd.text == "Hello Tim"
        assert cmd.rooms == []  # Default to all

    def test_text_length(self):
        """Text must be 1-500 chars."""
        with pytest.raises(ValidationError):
            AnnounceCommand(text="")

        # 500 chars OK
        AnnounceCommand(text="x" * 500)

        # 501 chars too long
        with pytest.raises(ValidationError):
            AnnounceCommand(text="x" * 501)


class TestLockCommand:
    """Tests for LockCommand validation."""

    def test_valid_actions(self):
        """Valid lock/unlock actions."""
        LockCommand(action="lock")
        LockCommand(action="unlock")

    def test_invalid_action(self):
        """Invalid action raises error."""
        with pytest.raises(ValidationError):
            LockCommand(action="toggle")


class TestSceneCommand:
    """Tests for SceneCommand validation."""

    def test_valid_scenes(self):
        """Valid scene names."""
        for scene in ["morning", "working", "relaxing", "movie", "goodnight"]:
            cmd = SceneCommand(scene_name=scene)
            assert cmd.scene_name == scene

    def test_invalid_scene(self):
        """Invalid scene raises error."""
        with pytest.raises(ValidationError) as exc_info:
            SceneCommand(scene_name="invalid_scene")
        assert "Unknown scene" in str(exc_info.value)

    def test_case_insensitive(self):
        """Scene names are case insensitive."""
        cmd = SceneCommand(scene_name="MORNING")
        assert cmd.scene_name == "morning"


class TestSpotifyCommand:
    """Tests for SpotifyCommand validation."""

    def test_play_requires_playlist(self):
        """Play action requires playlist."""
        cmd = SpotifyCommand(action="play", playlist="Focus")
        assert cmd.playlist == "Focus"

        with pytest.raises(ValidationError):
            SpotifyCommand(action="play")

    def test_volume_requires_level(self):
        """Volume action requires level."""
        cmd = SpotifyCommand(action="volume", volume=50)
        assert cmd.volume == 50

        with pytest.raises(ValidationError):
            SpotifyCommand(action="volume")

    def test_pause_no_params(self):
        """Pause doesn't require extra params."""
        SpotifyCommand(action="pause")
        SpotifyCommand(action="next")
        SpotifyCommand(action="previous")


class TestValidateCommand:
    """Tests for validate_command helper."""

    def test_valid_command(self):
        """Valid command returns model."""
        cmd = validate_command(LightCommand, level=50, rooms=["Living Room"])
        assert isinstance(cmd, LightCommand)

    def test_invalid_command(self):
        """Invalid command raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_command(LightCommand, level=150, rooms=["Living Room"])
        assert "Invalid LightCommand" in str(exc_info.value)


class TestValidRooms:
    """Tests for VALID_ROOMS constant."""

    def test_all_rooms_present(self):
        """All expected rooms are in VALID_ROOMS."""
        expected = [
            "Living Room",
            "Kitchen",
            "Dining",
            "Entry",
            "Primary Bed",
            "Office",
            "Game Room",
            "Gym",
        ]
        for room in expected:
            assert room in VALID_ROOMS

    def test_room_count(self):
        """Correct number of rooms."""
        assert len(VALID_ROOMS) == 26
