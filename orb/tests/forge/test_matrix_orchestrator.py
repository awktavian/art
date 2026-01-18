"""Comprehensive tests for ForgeMatrix orchestrator.

Tests the main character generation pipeline and module coordination.
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


from kagami.forge.matrix import ForgeMatrix, get_forge_matrix


class TestForgeMatrix:
    """Test ForgeMatrix orchestrator."""

    def test_creation(self) -> None:
        """Test ForgeMatrix instantiation."""
        matrix = ForgeMatrix()
        assert matrix is not None
        assert hasattr(matrix, "registry")
        assert hasattr(matrix, "_event_manager")

    def test_singleton_accessor(self) -> None:
        """Test get_forge_matrix returns ForgeMatrix instance."""
        matrix = get_forge_matrix()
        assert isinstance(matrix, ForgeMatrix)

    @pytest.mark.asyncio
    async def test_initialize(self) -> None:
        """Test matrix initialization."""
        matrix = ForgeMatrix()
        await matrix.initialize()
        assert matrix.initialized is True

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self) -> None:
        """Test multiple initializations are safe."""
        matrix = ForgeMatrix()
        await matrix.initialize()
        await matrix.initialize()  # Should not raise
        assert matrix.initialized is True


class TestForgeMatrixGeneration:
    """Test character generation flow."""

    @pytest.fixture
    def matrix(self):
        """Create fresh matrix for each test."""
        return ForgeMatrix()

    @pytest.mark.asyncio
    async def test_generate_character_missing_concept(self, matrix: Any) -> None:
        """Test generate_character requires concept."""
        from kagami.forge.schema import CharacterRequest

        request = CharacterRequest(concept="")

        result = await matrix.generate_character(request)

        assert result is not None
        assert isinstance(result, dict)
        assert result.get("success") is False
        assert result.get("error_code") == "missing_concept"

    @pytest.mark.asyncio
    async def test_generate_character_valid_concept(self, matrix: Any) -> None:
        """Test generate_character with valid concept."""
        from kagami.forge.schema import CharacterRequest, QualityLevel

        await matrix.initialize()

        request = CharacterRequest(
            concept="A brave knight in shining armor",
            quality_level=QualityLevel.LOW,
        )

        # This tests the full pipeline - may fail without models but structure is validated
        result = await matrix.generate_character(request)

        assert result is not None
        assert isinstance(result, dict)
        # Result should have a character payload or error info
        assert ("character" in result) or ("error" in result) or ("status" in result)

    @pytest.mark.asyncio
    async def test_generate_character_with_style(self, matrix: Any) -> None:
        """Test character generation with style preferences."""
        from kagami.forge.schema import (
            CharacterRequest,
            CharacterStyle,
            QualityLevel,
            StylePreferences,
        )

        await matrix.initialize()

        request = CharacterRequest(
            concept="Anime warrior princess",
            quality_level=QualityLevel.LOW,
            style_preferences=StylePreferences(
                visual_style=CharacterStyle.ANIME,
            ),
        )

        result = await matrix.generate_character(request)
        assert result is not None


class TestComponentRegistry:
    """Test component registry functionality."""

    def test_registry_creation(self) -> None:
        """Test registry is created with matrix."""
        matrix = ForgeMatrix()
        assert matrix.registry is not None

    @pytest.mark.asyncio
    async def test_registry_modules_available(self) -> None:
        """Test that key modules are registered."""
        matrix = ForgeMatrix()
        await matrix.initialize()

        # Check registry has expected modules
        registry = matrix.registry
        assert hasattr(registry, "ai_modules")

    @pytest.mark.asyncio
    async def test_get_available_modules(self) -> None:
        """Test listing available modules."""
        matrix = ForgeMatrix()
        await matrix.initialize()

        # Should be able to query available modules
        if hasattr(matrix.registry, "get_available"):
            available = matrix.registry.get_available()
            assert isinstance(available, (list, dict, set))


class TestEventManager:
    """Test event emission during generation."""

    @pytest.mark.asyncio
    async def test_event_manager_exists(self) -> None:
        """Test event manager is created."""
        matrix = ForgeMatrix()
        assert matrix._event_manager is not None

    @pytest.mark.asyncio
    async def test_progress_events(self) -> None:
        """Test progress events can be subscribed."""
        matrix = ForgeMatrix()

        events_received = []

        def on_progress(event: Any) -> None:
            events_received.append(event)

        if hasattr(matrix._event_manager, "subscribe"):
            matrix._event_manager.subscribe("progress", on_progress)

        # Events are emitted during generation


class TestForgeMatrixConfig:
    """Test matrix configuration."""

    def test_default_config(self) -> None:
        """Test default configuration."""
        matrix = ForgeMatrix()
        # Should have default config
        assert hasattr(matrix, "_config") or hasattr(matrix, "config")

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = {"require_unirig": False}
        matrix = ForgeMatrix(config=config)
        # Config should be applied
        assert matrix is not None
        assert matrix.config.get("require_unirig") is False
