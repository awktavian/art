"""Unit tests for UnifiedVoiceEffector.

Tests the voice routing, context awareness, and target selection logic
without requiring actual TTS or smart home connections.

Created: January 11, 2026
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.tier_unit


# =============================================================================
# Imports (with fallbacks for testing)
# =============================================================================


def get_voice_effector_class():
    """Import UnifiedVoiceEffector with proper handling."""
    from kagami.core.effectors.voice import UnifiedVoiceEffector, VoiceTarget

    return UnifiedVoiceEffector, VoiceTarget


def get_voice_result_class():
    """Import VoiceEffectorResult."""
    from kagami.core.effectors.voice import VoiceEffectorResult

    return VoiceEffectorResult


# =============================================================================
# VoiceTarget Enum Tests
# =============================================================================


class TestVoiceTarget:
    """Test VoiceTarget enum."""

    def test_target_values(self):
        """Test all target enum values exist."""
        _, VoiceTarget = get_voice_effector_class()

        assert VoiceTarget.AUTO.value == "auto"
        assert VoiceTarget.HOME_ROOM.value == "home_room"
        assert VoiceTarget.HOME_ALL.value == "home_all"
        assert VoiceTarget.CAR.value == "car"
        assert VoiceTarget.GLASSES.value == "glasses"
        assert VoiceTarget.DESKTOP.value == "desktop"

    def test_target_is_string_enum(self):
        """Test that VoiceTarget is a string enum."""
        _, VoiceTarget = get_voice_effector_class()

        # String enum allows direct string comparison
        assert VoiceTarget.AUTO == "auto"
        assert VoiceTarget.HOME_ROOM == "home_room"

    def test_all_targets_count(self):
        """Test we have all expected targets."""
        _, VoiceTarget = get_voice_effector_class()

        assert len(VoiceTarget) == 6


# =============================================================================
# VoiceEffectorResult Tests
# =============================================================================


class TestVoiceEffectorResult:
    """Test VoiceEffectorResult dataclass."""

    def test_result_creation(self):
        """Test creating a result."""
        VoiceEffectorResult = get_voice_result_class()
        _, VoiceTarget = get_voice_effector_class()

        result = VoiceEffectorResult(
            success=True,
            target=VoiceTarget.DESKTOP,
            target_detail="stereo",
            synthesis_ms=50.0,
            routing_ms=10.0,
            latency_ms=60.0,
        )

        assert result.success is True
        assert result.target == VoiceTarget.DESKTOP
        assert result.synthesis_ms == 50.0

    def test_result_with_error(self):
        """Test result with error."""
        VoiceEffectorResult = get_voice_result_class()
        _, VoiceTarget = get_voice_effector_class()

        result = VoiceEffectorResult(
            success=False,
            target=VoiceTarget.HOME_ALL,
            error="Smart home not connected",
        )

        assert result.success is False
        assert result.error == "Smart home not connected"

    def test_result_with_audio_path(self):
        """Test result with audio path."""
        VoiceEffectorResult = get_voice_result_class()
        _, VoiceTarget = get_voice_effector_class()

        audio_path = Path("/tmp/test.mp3")
        result = VoiceEffectorResult(
            success=True,
            target=VoiceTarget.DESKTOP,
            audio_path=audio_path,
        )

        assert result.audio_path == audio_path


# =============================================================================
# UnifiedVoiceEffector Tests
# =============================================================================


class TestUnifiedVoiceEffector:
    """Test UnifiedVoiceEffector class."""

    def test_effector_creation(self):
        """Test creating an effector instance."""
        UnifiedVoiceEffector, _ = get_voice_effector_class()

        effector = UnifiedVoiceEffector()

        assert effector._initialized is False
        assert effector._at_home is True
        assert effector._in_car is False
        assert effector._movie_mode is False

    def test_volume_defaults(self):
        """Test volume defaults."""
        UnifiedVoiceEffector, _ = get_voice_effector_class()

        effector = UnifiedVoiceEffector()

        assert effector._volume_normal == 1.0
        assert effector._volume_night == 0.5
        assert effector._volume_movie == 0.3

    def test_stats_initial(self):
        """Test initial stats structure."""
        UnifiedVoiceEffector, VoiceTarget = get_voice_effector_class()

        effector = UnifiedVoiceEffector()
        stats = effector.get_stats()

        assert stats["total_speaks"] == 0
        assert stats["errors"] == 0
        assert stats["initialized"] is False
        assert "by_target" in stats
        assert len(stats["by_target"]) == 6

    def test_set_movie_mode(self):
        """Test setting movie mode."""
        UnifiedVoiceEffector, _ = get_voice_effector_class()

        effector = UnifiedVoiceEffector()
        effector.set_movie_mode(True)

        assert effector._movie_mode is True

        effector.set_movie_mode(False)
        assert effector._movie_mode is False

    def test_set_night_mode(self):
        """Test setting night mode."""
        UnifiedVoiceEffector, _ = get_voice_effector_class()

        effector = UnifiedVoiceEffector()
        effector.set_night_mode(True)

        assert effector._night_mode is True

    def test_set_current_room(self):
        """Test setting current room."""
        UnifiedVoiceEffector, _ = get_voice_effector_class()

        effector = UnifiedVoiceEffector()
        effector.set_current_room("Office")

        assert effector._current_room == "Office"

        effector.set_current_room(None)
        assert effector._current_room is None


# =============================================================================
# Target Determination Tests
# =============================================================================


class TestTargetDetermination:
    """Test the _determine_target method logic."""

    def test_explicit_desktop_target(self):
        """Test explicit desktop target."""
        UnifiedVoiceEffector, VoiceTarget = get_voice_effector_class()

        effector = UnifiedVoiceEffector()
        target, detail = effector._determine_target(VoiceTarget.DESKTOP, None)

        assert target == VoiceTarget.DESKTOP
        assert detail == "stereo"

    def test_explicit_home_room_with_rooms(self):
        """Test explicit home room with rooms specified."""
        UnifiedVoiceEffector, VoiceTarget = get_voice_effector_class()

        effector = UnifiedVoiceEffector()
        target, detail = effector._determine_target(VoiceTarget.HOME_ROOM, ["Kitchen", "Office"])

        assert target == VoiceTarget.HOME_ROOM
        assert detail == "Kitchen, Office"

    def test_explicit_home_all(self):
        """Test explicit home all target."""
        UnifiedVoiceEffector, VoiceTarget = get_voice_effector_class()

        effector = UnifiedVoiceEffector()
        target, detail = effector._determine_target(VoiceTarget.HOME_ALL, None)

        assert target == VoiceTarget.HOME_ALL
        assert detail == "all zones"

    def test_explicit_car_target(self):
        """Test explicit car target."""
        UnifiedVoiceEffector, VoiceTarget = get_voice_effector_class()

        effector = UnifiedVoiceEffector()
        target, detail = effector._determine_target(VoiceTarget.CAR, None)

        assert target == VoiceTarget.CAR
        assert detail == "cabin"

    def test_explicit_glasses_target(self):
        """Test explicit glasses target."""
        UnifiedVoiceEffector, VoiceTarget = get_voice_effector_class()

        effector = UnifiedVoiceEffector()
        target, detail = effector._determine_target(VoiceTarget.GLASSES, None)

        assert target == VoiceTarget.GLASSES
        assert detail == "spatial"

    def test_auto_routes_to_car_when_driving(self):
        """Test AUTO routes to car when in_car is True."""
        UnifiedVoiceEffector, VoiceTarget = get_voice_effector_class()

        effector = UnifiedVoiceEffector()
        effector._in_car = True

        target, detail = effector._determine_target(VoiceTarget.AUTO, None)

        assert target == VoiceTarget.CAR
        assert detail == "cabin"

    def test_auto_routes_to_desktop_when_not_home(self):
        """Test AUTO routes to desktop when not at home."""
        UnifiedVoiceEffector, VoiceTarget = get_voice_effector_class()

        effector = UnifiedVoiceEffector()
        effector._at_home = False
        effector._in_car = False

        target, detail = effector._determine_target(VoiceTarget.AUTO, None)

        assert target == VoiceTarget.DESKTOP
        assert detail == "stereo"

    def test_auto_routes_to_current_room_at_home(self):
        """Test AUTO routes to current room when at home with room set."""
        UnifiedVoiceEffector, VoiceTarget = get_voice_effector_class()

        effector = UnifiedVoiceEffector()
        effector._at_home = True
        effector._current_room = "Office"

        target, detail = effector._determine_target(VoiceTarget.AUTO, None)

        assert target == VoiceTarget.HOME_ROOM
        assert detail == "Office"

    def test_auto_routes_to_all_zones_by_default(self):
        """Test AUTO routes to all zones when at home without current room."""
        UnifiedVoiceEffector, VoiceTarget = get_voice_effector_class()

        effector = UnifiedVoiceEffector()
        effector._at_home = True
        effector._current_room = None

        target, detail = effector._determine_target(VoiceTarget.AUTO, None)

        assert target == VoiceTarget.HOME_ALL
        assert detail == "all zones"


# =============================================================================
# Desktop Playback Tests
# =============================================================================


class TestDesktopPlayback:
    """Test desktop (afplay) playback."""

    @pytest.mark.asyncio
    async def test_play_desktop_with_valid_file(self):
        """Test desktop playback with a valid file."""
        UnifiedVoiceEffector, _ = get_voice_effector_class()

        effector = UnifiedVoiceEffector()

        # Create a temp file
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"fake audio data")
            audio_path = Path(f.name)

        try:
            with patch("asyncio.create_subprocess_exec") as mock_exec:
                mock_proc = MagicMock()
                mock_proc.wait = AsyncMock(return_value=None)
                mock_proc.returncode = 0
                mock_exec.return_value = mock_proc

                result = await effector._play_desktop(audio_path, volume=0.8)

                assert result is True
                mock_exec.assert_called_once()
                # Check afplay was called with correct args
                call_args = mock_exec.call_args[0]
                assert call_args[0] == "afplay"
                assert "-v" in call_args
        finally:
            audio_path.unlink()

    @pytest.mark.asyncio
    async def test_play_desktop_no_file(self):
        """Test desktop playback fails with no file."""
        UnifiedVoiceEffector, _ = get_voice_effector_class()

        effector = UnifiedVoiceEffector()
        result = await effector._play_desktop(None, volume=1.0)

        assert result is False


# =============================================================================
# Stats Tracking Tests
# =============================================================================


class TestStatsTracking:
    """Test statistics tracking."""

    def test_stats_context_updates(self):
        """Test that context is reflected in stats."""
        UnifiedVoiceEffector, _ = get_voice_effector_class()

        effector = UnifiedVoiceEffector()
        effector._at_home = True
        effector._in_car = False
        effector._movie_mode = True
        effector._current_room = "Living Room"

        stats = effector.get_stats()
        context = stats["context"]

        assert context["at_home"] is True
        assert context["in_car"] is False
        assert context["movie_mode"] is True
        assert context["current_room"] == "Living Room"

    def test_avg_latency_calculation(self):
        """Test average latency is calculated correctly."""
        UnifiedVoiceEffector, _ = get_voice_effector_class()

        effector = UnifiedVoiceEffector()
        effector._stats["total_speaks"] = 10
        effector._stats["total_latency_ms"] = 500.0

        stats = effector.get_stats()

        assert stats["avg_latency_ms"] == 50.0

    def test_error_rate_calculation(self):
        """Test error rate is calculated correctly."""
        UnifiedVoiceEffector, _ = get_voice_effector_class()

        effector = UnifiedVoiceEffector()
        effector._stats["total_speaks"] = 10
        effector._stats["errors"] = 2

        stats = effector.get_stats()

        assert stats["error_rate"] == 0.2
