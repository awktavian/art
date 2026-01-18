"""Comprehensive tests for forge streaming module.

Tests StreamingGenerator, ProgressUpdate, and GenerationStage.
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


from kagami.forge.streaming import (
    GenerationStage,
    ProgressUpdate,
    StreamingGenerator,
    get_streaming_generator,
)


class TestGenerationStage:
    """Test GenerationStage enum."""

    def test_stage_values(self) -> None:
        """Test all stage values are defined."""
        assert GenerationStage.INIT.value == "init"
        assert GenerationStage.MESH.value == "mesh"
        assert GenerationStage.RIGGING.value == "rigging"
        assert GenerationStage.TEXTURING.value == "texturing"
        assert GenerationStage.PERSONALITY.value == "personality"
        assert GenerationStage.VOICE.value == "voice"
        assert GenerationStage.COMPLETE.value == "complete"


class TestProgressUpdate:
    """Test ProgressUpdate dataclass."""

    def test_creation(self) -> None:
        """Test creating a progress update."""
        update = ProgressUpdate(
            stage=GenerationStage.MESH,
            percent=50.0,
            message="Generating mesh...",
            eta_seconds=5.0,
        )

        assert update.stage == GenerationStage.MESH
        assert update.percent == 50.0
        assert update.message == "Generating mesh..."
        assert update.eta_seconds == 5.0
        assert update.preview_url is None

    def test_to_dict(self) -> None:
        """Test converting progress update to dict."""
        update = ProgressUpdate(
            stage=GenerationStage.RIGGING,
            percent=75.5,
            message="Rigging skeleton...",
            preview_url="http://example.com/preview.png",
            eta_seconds=2.5,
        )

        data = update.to_dict()

        assert data["stage"] == "rigging"
        assert data["percent"] == 75.5
        assert data["message"] == "Rigging skeleton..."
        assert data["preview_url"] == "http://example.com/preview.png"
        assert data["eta_seconds"] == 2.5
        assert "timestamp" in data

    def test_to_dict_rounds_values(self) -> None:
        """Test that to_dict rounds values appropriately."""
        update = ProgressUpdate(
            stage=GenerationStage.TEXTURING,
            percent=33.3333,
            message="Texturing...",
            eta_seconds=1.2345,
        )

        data = update.to_dict()

        assert data["percent"] == 33.3
        assert data["eta_seconds"] == 1.2


class TestStreamingGenerator:
    """Test StreamingGenerator class."""

    @pytest.fixture
    def mock_forge_matrix(self) -> None:
        """Create mock forge matrix."""

        class MockForge:
            initialized = True

            async def initialize(self) -> None:
                pass

            async def generate_character(self, request) -> None:
                return {"character": "generated"}

        return MockForge()

    @pytest.fixture
    def uninitialized_forge(self) -> None:
        """Create uninitialized mock forge."""

        class MockForge:
            initialized = False

            async def initialize(self) -> None:
                self.initialized = True

            async def generate_character(self, request) -> None:
                return {"character": "generated"}

        return MockForge()

    @pytest.mark.asyncio
    async def test_generate_with_progress_yields_updates(self, mock_forge_matrix: Any) -> None:
        """Test that generator yields progress updates."""
        generator = StreamingGenerator(mock_forge_matrix)

        class MockRequest:
            concept = "Test character"

        updates = []
        async for update in generator.generate_with_progress(MockRequest()):
            updates.append(update)

        assert len(updates) > 0
        assert updates[0].stage == GenerationStage.INIT
        assert updates[-1].stage == GenerationStage.COMPLETE
        assert updates[-1].percent == 100.0

    @pytest.mark.asyncio
    async def test_generate_with_progress_stages(self, mock_forge_matrix: Any) -> None:
        """Test that all expected stages are emitted."""
        generator = StreamingGenerator(mock_forge_matrix)

        class MockRequest:
            concept = "Test character"

        stages = []
        async for update in generator.generate_with_progress(MockRequest()):
            stages.append(update.stage)

        assert GenerationStage.INIT in stages
        assert GenerationStage.MESH in stages
        assert GenerationStage.RIGGING in stages
        assert GenerationStage.TEXTURING in stages
        assert GenerationStage.PERSONALITY in stages
        assert GenerationStage.COMPLETE in stages

    @pytest.mark.asyncio
    async def test_generate_initializes_if_needed(self, uninitialized_forge: Any) -> None:
        """Test that forge is initialized if not already."""
        assert uninitialized_forge.initialized is False

        generator = StreamingGenerator(uninitialized_forge)

        class MockRequest:
            concept = "Test character"

        async for _ in generator.generate_with_progress(MockRequest()):
            pass

        assert uninitialized_forge.initialized is True


class TestGetStreamingGenerator:
    """Test get_streaming_generator factory function."""

    def test_returns_streaming_generator(self) -> None:
        """Test factory returns StreamingGenerator instance."""

        class MockForge:
            initialized = True

        gen = get_streaming_generator(MockForge())
        assert isinstance(gen, StreamingGenerator)
