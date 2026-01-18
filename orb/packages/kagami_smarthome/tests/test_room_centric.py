"""Tests for Room-Centric Architecture.

Tests for:
- Room model and registry
- Scenes
- Orchestrator (mock-based)
"""

from kagami_smarthome.orchestrator import (
    OrchestratorConfig,
)
from kagami_smarthome.room import (
    ActivityContext,
    AudioZone,
    Light,
    Room,
    RoomRegistry,
    RoomType,
    Shade,
)
from kagami_smarthome.scenes import (
    HVACPreset,
    LightingPreset,
    Season,
    TimeOfDay,
    get_all_scenes,
    get_scene,
)


class TestRoomModel:
    """Test Room data model."""

    def test_room_creation(self) -> None:
        """Room should be creatable with minimal args."""
        room = Room(id=1, name="Living Room")
        assert room.id == 1
        assert room.name == "Living Room"
        assert room.room_type == RoomType.OTHER
        assert room.floor == "Main"

    def test_room_with_devices(self) -> None:
        """Room can hold lights, shades, and audio zone."""
        light = Light(id=100, name="Ceiling Light")
        shade = Shade(id=200, name="Window Shade")
        audio = AudioZone(id=1, name="Living Room")

        room = Room(
            id=1,
            name="Living Room",
            lights=[light],
            shades=[shade],
            audio_zone=audio,
        )

        assert len(room.lights) == 1
        assert len(room.shades) == 1
        assert room.audio_zone is not None
        assert room.audio_zone.name == "Living Room"

    def test_room_preferences(self) -> None:
        """Room should have default preferences."""
        room = Room(id=1, name="Test Room")

        # Default light level for waking
        assert room.get_preferred_light_level(ActivityContext.WAKING) == 60
        # Default temp for sleeping
        assert room.get_preferred_temp(ActivityContext.SLEEPING) == 68.0

    def test_room_preference_update(self) -> None:
        """Room preferences should be learnable."""
        room = Room(id=1, name="Test Room")

        # Initial value
        initial = room.get_preferred_light_level(ActivityContext.WORKING)

        # Update preference
        room.update_preference("light", ActivityContext.WORKING, 90)

        # Should have moved toward 90
        new_value = room.get_preferred_light_level(ActivityContext.WORKING)
        assert new_value > initial

    def test_room_occupancy(self) -> None:
        """Room occupancy tracking."""
        room = Room(id=1, name="Test Room")

        assert not room.state.occupied

        room.mark_occupied(ActivityContext.WORKING)
        assert room.state.occupied
        assert room.state.activity == ActivityContext.WORKING

        room.mark_vacant()
        assert not room.state.occupied
        assert room.state.activity == ActivityContext.AWAY


class TestRoomRegistry:
    """Test RoomRegistry."""

    def test_registry_add_and_get(self) -> None:
        """Registry should add and retrieve rooms."""
        registry = RoomRegistry()
        room = Room(id=1, name="Living Room")

        registry.add_room(room)

        # Get by ID
        assert registry.get_by_id(1) == room

        # Get by name (case-insensitive)
        assert registry.get_by_name("living room") == room
        assert registry.get_by_name("LIVING ROOM") == room

    def test_registry_get_all(self) -> None:
        """Registry should return all rooms."""
        registry = RoomRegistry()
        registry.add_room(Room(id=1, name="Room 1"))
        registry.add_room(Room(id=2, name="Room 2"))
        registry.add_room(Room(id=3, name="Room 3"))

        all_rooms = registry.get_all()
        assert len(all_rooms) == 3

    def test_registry_get_occupied(self) -> None:
        """Registry should return only occupied rooms."""
        registry = RoomRegistry()
        room1 = Room(id=1, name="Room 1")
        room2 = Room(id=2, name="Room 2")
        room3 = Room(id=3, name="Room 3")

        registry.add_room(room1)
        registry.add_room(room2)
        registry.add_room(room3)

        # Mark some occupied
        room1.mark_occupied()
        room3.mark_occupied()

        occupied = registry.get_occupied()
        assert len(occupied) == 2
        assert room1 in occupied
        assert room3 in occupied
        assert room2 not in occupied

    def test_registry_get_by_floor(self) -> None:
        """Registry should filter by floor."""
        registry = RoomRegistry()
        registry.add_room(Room(id=1, name="Living Room", floor="Main"))
        registry.add_room(Room(id=2, name="Kitchen", floor="Main"))
        registry.add_room(Room(id=3, name="Bedroom", floor="Upper"))

        main_floor = registry.get_by_floor("Main")
        assert len(main_floor) == 2

        upper_floor = registry.get_by_floor("Upper")
        assert len(upper_floor) == 1

    def test_registry_get_by_type(self) -> None:
        """Registry should filter by room type."""
        registry = RoomRegistry()
        registry.add_room(Room(id=1, name="Living Room", room_type=RoomType.LIVING))
        registry.add_room(Room(id=2, name="Kitchen", room_type=RoomType.KITCHEN))
        registry.add_room(Room(id=3, name="Family Room", room_type=RoomType.FAMILY))

        living_rooms = registry.get_by_type(RoomType.LIVING)
        assert len(living_rooms) == 1

    def test_registry_infer_room_type(self) -> None:
        """Registry should infer room type from name."""
        assert RoomRegistry._infer_room_type("Living Room") == RoomType.LIVING
        assert RoomRegistry._infer_room_type("Kitchen Area") == RoomType.KITCHEN
        assert RoomRegistry._infer_room_type("Master Bedroom") == RoomType.BEDROOM
        assert RoomRegistry._infer_room_type("Home Office") == RoomType.OFFICE
        assert RoomRegistry._infer_room_type("Unknown Space") == RoomType.OTHER


class TestScenes:
    """Test Scene definitions."""

    def test_get_scene(self) -> None:
        """Should retrieve scenes by name."""
        morning = get_scene("morning")
        assert morning is not None
        assert morning.name == "morning"
        assert morning.display_name == "Morning"

    def test_get_all_scenes(self) -> None:
        """Should get all registered scenes."""
        scenes = get_all_scenes()
        assert len(scenes) >= 10  # At least 10 built-in scenes

        # Check some expected scenes exist
        names = [s.name for s in scenes]
        assert "morning" in names
        assert "working" in names
        assert "relaxing" in names
        assert "movie" in names
        assert "sleeping" in names
        assert "away" in names

    def test_scene_has_presets(self) -> None:
        """Scene should have all preset types."""
        scene = get_scene("relaxing")
        assert scene is not None

        assert hasattr(scene, "lighting")
        assert hasattr(scene, "shades")
        assert hasattr(scene, "audio")
        assert hasattr(scene, "hvac")

    def test_lighting_preset_time_adjustment(self) -> None:
        """Lighting preset should adjust for time of day."""
        preset = LightingPreset(level=60)

        # Morning should apply dawn modifier
        morning_level = preset.get_level(TimeOfDay.DAWN)
        assert morning_level < 60  # Should be dimmer

        # Night should apply night modifier
        night_level = preset.get_level(TimeOfDay.NIGHT)
        assert night_level < 60  # Should be dimmer

    def test_hvac_preset_season_adjustment(self) -> None:
        """HVAC preset should adjust for season."""
        preset = HVACPreset(target_temp_f=72.0, summer_offset=-1.0, winter_offset=1.0)

        summer_temp = preset.get_temp(Season.SUMMER)
        assert summer_temp == 71.0  # Cooler in summer

        winter_temp = preset.get_temp(Season.WINTER)
        assert winter_temp == 73.0  # Warmer in winter


class TestTimeOfDay:
    """Test TimeOfDay enum."""

    def test_from_hour(self) -> None:
        """Should correctly determine time of day from hour."""
        assert TimeOfDay.from_hour(6) == TimeOfDay.DAWN
        assert TimeOfDay.from_hour(10) == TimeOfDay.MORNING
        assert TimeOfDay.from_hour(14) == TimeOfDay.AFTERNOON
        assert TimeOfDay.from_hour(19) == TimeOfDay.EVENING
        assert TimeOfDay.from_hour(22) == TimeOfDay.NIGHT
        assert TimeOfDay.from_hour(2) == TimeOfDay.LATE_NIGHT


class TestSeason:
    """Test Season enum."""

    def test_seasons(self) -> None:
        """Season enum should have all seasons."""
        assert Season.SPRING
        assert Season.SUMMER
        assert Season.AUTUMN
        assert Season.WINTER


class TestOrchestratorConfig:
    """Test orchestrator configuration."""

    def test_default_config(self) -> None:
        """Default config should have sensible values."""
        config = OrchestratorConfig()

        assert config.default_fade_seconds == 3.0
        assert config.movie_fade_seconds == 5.0
        assert config.min_temp_f == 62.0
        assert config.max_temp_f == 78.0
        assert config.home_theater_room == "Living Room"

    def test_custom_config(self) -> None:
        """Config should be customizable."""
        config = OrchestratorConfig(
            default_fade_seconds=5.0,
            home_theater_room="Media Room",
        )

        assert config.default_fade_seconds == 5.0
        assert config.home_theater_room == "Media Room"


class TestActivityContext:
    """Test ActivityContext enum."""

    def test_activity_values(self) -> None:
        """All activities should have string values."""
        assert ActivityContext.UNKNOWN.value == "unknown"
        assert ActivityContext.WAKING.value == "waking"
        assert ActivityContext.WORKING.value == "working"
        assert ActivityContext.COOKING.value == "cooking"
        assert ActivityContext.RELAXING.value == "relaxing"
        assert ActivityContext.SLEEPING.value == "sleeping"
        assert ActivityContext.AWAY.value == "away"

    def test_activity_count(self) -> None:
        """Should have expected number of activities."""
        activities = list(ActivityContext)
        assert len(activities) >= 9  # At least 9 activities


class TestImports:
    """Test that all new components are importable."""

    def test_room_imports(self) -> None:
        """Room module should be importable."""
        from kagami_smarthome import (
            Room,
        )

        assert Room is not None

    def test_scene_imports(self) -> None:
        """Scene module should be importable."""
        from kagami_smarthome import (
            SCENES,
            Scene,
        )

        assert Scene is not None
        assert SCENES is not None

    def test_orchestrator_imports(self) -> None:
        """Orchestrator module should be importable."""
        from kagami_smarthome import (
            RoomOrchestrator,
        )

        assert RoomOrchestrator is not None

    def test_integration_imports(self) -> None:
        """New integrations should be importable."""
        from kagami_smarthome import (
            HVACMode,
            KagamiHostIntegration,
            MitsubishiIntegration,
            SamsungTVIntegration,
        )

        assert SamsungTVIntegration is not None
        assert MitsubishiIntegration is not None
        assert HVACMode is not None
        assert KagamiHostIntegration is not None
