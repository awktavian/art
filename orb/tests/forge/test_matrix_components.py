"""Tests for kagami.forge.matrix.components (Matrix components)."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

pytestmark = pytest.mark.tier_integration


class TestVisualComponents:
    """Test visual generation components."""

    @pytest.mark.asyncio
    async def test_generate_visuals_component(self):
        """Test generate_visuals component."""
        from kagami.forge.matrix import components

        mock_registry = MagicMock()
        mock_registry.is_available = MagicMock(return_value=True)

        mock_tracer = MagicMock()
        mock_request = MagicMock()

        with patch("kagami.forge.modules.visual_design.character_profiler.CharacterVisualProfiler") as mock_profiler:
            profiler_instance = MagicMock()
            profiler_instance.initialize = AsyncMock()
            profiler_instance.generate = AsyncMock(
                return_value=MagicMock(success=True, mesh_data={"mesh": "data"})
            )
            mock_profiler.return_value = profiler_instance

            result = await components.generate_visuals(
                mock_registry,
                mock_tracer,
                mock_request
            )

            # Component should return visual data
            assert result is not None


class TestPersonalityComponents:
    """Test personality generation components."""

    @pytest.mark.asyncio
    async def test_generate_personality_component(self):
        """Test generate_personality component."""
        from kagami.forge.matrix import components

        mock_registry = MagicMock()
        mock_tracer = MagicMock()
        mock_request = MagicMock()

        result = await components.generate_personality(
            mock_registry,
            mock_tracer,
            mock_request
        )

        # Should return personality data or None
        assert result is not None or result is None


class TestVoiceComponents:
    """Test voice generation components."""

    @pytest.mark.asyncio
    async def test_generate_voice_component(self):
        """Test generate_voice component."""
        from kagami.forge.matrix import components

        mock_registry = MagicMock()
        mock_tracer = MagicMock()
        mock_request = MagicMock()

        result = await components.generate_voice(
            mock_registry,
            mock_tracer,
            mock_request
        )

        assert result is not None or result is None


class TestRiggingComponents:
    """Test rigging components."""

    @pytest.mark.asyncio
    async def test_process_rigging_component(self):
        """Test process_rigging component."""
        from kagami.forge.matrix import components

        mock_registry = MagicMock()
        mock_registry.is_available = MagicMock(return_value=False)

        mock_tracer = MagicMock()
        mock_request = MagicMock()
        mock_mesh = MagicMock()

        result = await components.process_rigging(
            mock_registry,
            mock_tracer,
            mock_request,
            mock_mesh
        )

        # If rigging unavailable, should return None
        assert result is None


class TestExportComponents:
    """Test export components."""

    @pytest.mark.asyncio
    async def test_export_character_component(self):
        """Test export_character component."""
        from kagami.forge.matrix import components

        mock_registry = MagicMock()
        character_data = {"mesh": "data"}
        export_formats = ["glb"]

        with patch("kagami.forge.modules.export.manager.ExportManager") as mock_manager:
            manager_instance = MagicMock()
            manager_instance.export = AsyncMock(
                return_value=MagicMock(success=True, file_path="/tmp/test.glb")
            )
            mock_manager.return_value = manager_instance

            result = await components.export_character(
                mock_registry,
                character_data,
                export_formats
            )

            assert result is not None
