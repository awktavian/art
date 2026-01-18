"""Property-based tests using Hypothesis.

Tests invariants and properties that should hold for all valid inputs.

Created: January 2, 2026
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from kagami_smarthome.validation import (
    VALID_ROOMS,
    LightCommand,
    ShadeCommand,
    TemperatureCommand,
    TVMountCommand,
    VolumeCommand,
)

# Strategies for valid inputs
valid_room = st.sampled_from(sorted(VALID_ROOMS))
valid_rooms_list = st.lists(valid_room, min_size=1, max_size=5, unique=True)
valid_light_level = st.integers(min_value=0, max_value=100)
valid_shade_position = st.integers(min_value=0, max_value=100)
valid_temperature = st.floats(min_value=60, max_value=85, allow_nan=False)
valid_volume = st.integers(min_value=0, max_value=100)
valid_tv_preset = st.integers(min_value=1, max_value=4)

# Strategies for invalid inputs
invalid_light_level = st.one_of(
    st.integers(max_value=-1),
    st.integers(min_value=101),
)
invalid_temperature = st.one_of(
    st.floats(max_value=59.9, allow_nan=False),
    st.floats(min_value=85.1, allow_nan=False, allow_infinity=False),
)


class TestLightCommandProperties:
    """Property-based tests for LightCommand."""

    @given(level=valid_light_level, rooms=valid_rooms_list)
    @settings(max_examples=100)
    def test_valid_inputs_never_raise(self, level: int, rooms: list[str]):
        """Property: Valid inputs never raise ValidationError."""
        cmd = LightCommand(level=level, rooms=rooms)
        assert cmd.level == level
        assert set(cmd.rooms) == set(rooms)

    @given(level=invalid_light_level, rooms=valid_rooms_list)
    @settings(max_examples=50)
    def test_invalid_level_always_raises(self, level: int, rooms: list[str]):
        """Property: Invalid levels always raise ValidationError."""
        with pytest.raises(ValidationError):
            LightCommand(level=level, rooms=rooms)

    @given(level=valid_light_level)
    @settings(max_examples=50)
    def test_empty_rooms_always_raises(self, level: int):
        """Property: Empty rooms always raises ValidationError."""
        with pytest.raises(ValidationError):
            LightCommand(level=level, rooms=[])

    @given(level=valid_light_level, room=st.text(min_size=1).filter(lambda x: x not in VALID_ROOMS))
    @settings(max_examples=50)
    def test_invalid_room_always_raises(self, level: int, room: str):
        """Property: Invalid room names always raise ValidationError."""
        with pytest.raises(ValidationError):
            LightCommand(level=level, rooms=[room])


class TestShadeCommandProperties:
    """Property-based tests for ShadeCommand."""

    @given(position=valid_shade_position, rooms=valid_rooms_list)
    @settings(max_examples=100)
    def test_valid_inputs_never_raise(self, position: int, rooms: list[str]):
        """Property: Valid inputs never raise ValidationError."""
        cmd = ShadeCommand(position=position, rooms=rooms)
        assert cmd.position == position

    @given(position=st.integers(max_value=-1), rooms=valid_rooms_list)
    @settings(max_examples=50)
    def test_negative_position_raises(self, position: int, rooms: list[str]):
        """Property: Negative position always raises."""
        with pytest.raises(ValidationError):
            ShadeCommand(position=position, rooms=rooms)


class TestTVMountCommandProperties:
    """Property-based tests for TVMountCommand."""

    @given(preset=valid_tv_preset)
    @settings(max_examples=20)
    def test_valid_presets_never_raise(self, preset: int):
        """Property: Valid presets 1-4 never raise."""
        cmd = TVMountCommand(preset=preset)
        assert cmd.preset == preset

    @given(preset=st.integers().filter(lambda x: x < 1 or x > 4))
    @settings(max_examples=50)
    def test_invalid_presets_always_raise(self, preset: int):
        """Property: Invalid presets always raise."""
        with pytest.raises(ValidationError):
            TVMountCommand(preset=preset)


class TestTemperatureCommandProperties:
    """Property-based tests for TemperatureCommand."""

    @given(temp=valid_temperature, room=valid_room)
    @settings(max_examples=100)
    def test_valid_inputs_never_raise(self, temp: float, room: str):
        """Property: Valid inputs never raise ValidationError."""
        cmd = TemperatureCommand(temp_f=temp, room=room)
        assert cmd.temp_f == temp
        assert cmd.room == room

    @given(temp=invalid_temperature, room=valid_room)
    @settings(max_examples=50)
    def test_invalid_temperature_always_raises(self, temp: float, room: str):
        """Property: Invalid temperature always raises."""
        with pytest.raises(ValidationError):
            TemperatureCommand(temp_f=temp, room=room)


class TestVolumeCommandProperties:
    """Property-based tests for VolumeCommand."""

    @given(level=valid_volume)
    @settings(max_examples=100)
    def test_valid_volume_never_raises(self, level: int):
        """Property: Valid volume levels never raise."""
        cmd = VolumeCommand(level=level)
        assert cmd.level == level

    @given(level=st.one_of(st.integers(max_value=-1), st.integers(min_value=101)))
    @settings(max_examples=50)
    def test_invalid_volume_always_raises(self, level: int):
        """Property: Invalid volume always raises."""
        with pytest.raises(ValidationError):
            VolumeCommand(level=level)


class TestRoomInvariant:
    """Test room name invariants."""

    @given(rooms=st.lists(valid_room, min_size=1, max_size=10))
    @settings(max_examples=100)
    def test_all_valid_rooms_accepted(self, rooms: list[str]):
        """Property: Any subset of VALID_ROOMS is accepted."""
        # Remove duplicates while preserving order
        unique_rooms = list(dict.fromkeys(rooms))
        if unique_rooms:
            cmd = LightCommand(level=50, rooms=unique_rooms)
            assert all(r in VALID_ROOMS for r in cmd.rooms)

    def test_valid_rooms_is_frozen(self):
        """Property: VALID_ROOMS is immutable."""
        assert isinstance(VALID_ROOMS, frozenset)

        # Can't modify
        with pytest.raises(AttributeError):
            VALID_ROOMS.add("New Room")


class TestLevelBoundaries:
    """Test boundary conditions for level values."""

    @pytest.mark.parametrize("level", [0, 1, 50, 99, 100])
    def test_light_level_boundaries(self, level: int):
        """Boundary values for light level are valid."""
        cmd = LightCommand(level=level, rooms=["Living Room"])
        assert cmd.level == level

    @pytest.mark.parametrize("level", [-1, 101, -100, 200])
    def test_light_level_outside_boundaries(self, level: int):
        """Values outside boundaries are rejected."""
        with pytest.raises(ValidationError):
            LightCommand(level=level, rooms=["Living Room"])
