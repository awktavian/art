"""Tests for kagami.forge.modules.motion.gesture_engine (GestureEngine)."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from kagami.forge.modules.motion.gesture_engine import GestureEngine

pytestmark = pytest.mark.tier_integration


@pytest.fixture
def gesture_engine():
    """Create GestureEngine instance."""
    return GestureEngine()


class TestGestureEngineInit:
    """Test GestureEngine initialization."""

    def test_init_default(self):
        """Test default initialization."""
        engine = GestureEngine()
        assert engine is not None

    @pytest.mark.asyncio
    async def test_generate_idle_gestures(self, gesture_engine):
        """Test generating idle gestures."""
        animation = await gesture_engine.generate_idle_gestures(
            duration=10.0,
            character_traits={"energy_level": 0.3},
        )

        assert animation is not None

    @pytest.mark.asyncio
    async def test_generate_from_speech(self, gesture_engine):
        """Test generating gestures from speech."""
        speech_data = {
            "text": "Hello world",
            "emphasis_words": ["Hello"],
            "duration": 5.0,
            "prosody": {"pitch_contour": [], "energy": []},
        }

        animation = await gesture_engine.generate_from_speech(speech_data)
        assert animation is not None
