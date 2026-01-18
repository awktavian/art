from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from kagami.forge.matrix.core import ForgeMatrix
from kagami.forge.schema import CharacterRequest, ExportFormat


@pytest.fixture
def mock_config():
    return {
        "require_unirig": False,
        "modules": {
            "rigging": {"method": "unirig"},
        },
    }


@pytest.fixture
def forge_matrix(mock_config: Any) -> None:
    # Mock safety gate to avoid middleware blocking - patch WHERE IT IS USED
    with patch("kagami.forge.forge_middleware.get_safety_gate") as mock_get_gate:
        mock_gate = MagicMock()
        mock_gate.assess_threat = AsyncMock(
            return_value={"score": 0.0, "requires_confirmation": False, "reason": "safe"}
        )
        mock_gate.evaluate_ethical = AsyncMock(return_value={"permissible": True, "reason": "safe"})
        mock_get_gate.return_value = mock_gate

        # Mock all module imports to avoid needing real dependencies
        with (
            patch("kagami.forge.matrix.registry.PersonalityEngine"),
            patch("kagami.forge.matrix.registry.NarrativeModule"),
            patch("kagami.forge.matrix.registry.IntelligentVisualDesigner"),
            patch("kagami.forge.matrix.registry.CharacterVisualProfiler"),
            patch("kagami.forge.matrix.registry.RiggingModule"),
            patch("kagami.forge.matrix.registry.AnimationModule"),
            patch("kagami.forge.matrix.registry.VoiceModule"),
            patch("kagami.forge.matrix.registry.ExportManager"),
            patch("kagami.forge.matrix.registry.GenesisPhysicsWrapper"),
            patch("kagami.forge.matrix.registry.WorldGenerationModule"),
        ):
            matrix = ForgeMatrix(config=mock_config)

            # Helper to create well-behaved mocks
            def create_module_mock():
                m = AsyncMock()
                # Ensure to_dict doesn't return a coroutine by default
                m.generate.return_value = {}
                return m

            # Mock module instances
            matrix.registry.ai_modules = {
                "visual_designer": create_module_mock(),
                "character_profiler": create_module_mock(),
                "personality_engine": create_module_mock(),
                "voice": create_module_mock(),
                "narrative": create_module_mock(),
                "rigging": create_module_mock(),
                "animation": create_module_mock(),
                "export_manager": create_module_mock(),
                "physics_engine": create_module_mock(),
                "world_generation": create_module_mock(),
            }
            # Prevent re-initialization overwriting mocks
            matrix.lifecycle.initialized = True

            # Special case: rigging.process needs to return something with .data
            matrix.registry.ai_modules["rigging"].process.return_value = MagicMock(
                data=MagicMock(skeleton="skel")
            )

            # Mock internal methods
            matrix._emit_progress = AsyncMock()  # type: ignore[method-assign]
            matrix._record_trace_event = MagicMock()  # type: ignore[method-assign]
            matrix.validate_models = AsyncMock(return_value=True)

            yield matrix


@pytest.mark.asyncio
async def test_initialization(mock_config: Any) -> None:
    """Test that ForgeMatrix initializes correctly."""
    with (
        patch("kagami.forge.matrix.registry.PersonalityEngine"),
        patch("kagami.forge.matrix.registry.NarrativeModule"),
    ):
        matrix = ForgeMatrix(config=mock_config)
        assert matrix.config["require_unirig"] is False
        assert not matrix.initialized


@pytest.mark.asyncio
async def test_generate_character_success(forge_matrix: Any) -> None:
    """Test successful character generation flow."""
    # Setup request
    request = CharacterRequest(concept="A brave knight", export_formats=[ExportFormat.GLB])

    # Setup module responses
    forge_matrix.registry.ai_modules["character_profiler"].generate.return_value = MagicMock(
        mesh_data=MagicMock(vertices=[[0, 0, 0]], faces=[[0, 1, 2]]),
        to_dict=lambda: {"visual": "data"},
    )
    forge_matrix.registry.ai_modules["personality_engine"].generate.return_value = {
        "traits": ["brave"]
    }
    forge_matrix.registry.ai_modules["voice"].generate.return_value = {"voice_id": "v1"}
    forge_matrix.registry.ai_modules["narrative"].generate.return_value = {
        "story": "once upon a time"
    }
    forge_matrix.registry.ai_modules["rigging"].process.return_value = MagicMock(
        data=MagicMock(skeleton="skel", weights="w")
    )
    forge_matrix.registry.ai_modules["export_manager"].export.return_value = "/path/to/file.glb"

    # Run generation
    result = await forge_matrix.generate_character(request)

    # Assertions
    assert result["success"] is True
    assert result["concept"] == "A brave knight"
    assert "character" in result

    # Verify module calls
    forge_matrix.registry.ai_modules["character_profiler"].generate.assert_called_once()
    forge_matrix.registry.ai_modules["personality_engine"].generate.assert_called_once()
    forge_matrix.registry.ai_modules["voice"].generate.assert_called_once()
    forge_matrix.registry.ai_modules["narrative"].generate.assert_called_once()
    forge_matrix.registry.ai_modules["rigging"].process.assert_called_once()
    forge_matrix.registry.ai_modules["export_manager"].export.assert_called_once()


@pytest.mark.asyncio
async def test_generate_character_missing_module(forge_matrix: Any) -> None:
    """Test generation handles missing modules gracefully or raises."""
    # Remove a critical module
    del forge_matrix.registry.ai_modules["character_profiler"]

    request = CharacterRequest(concept="Broken character")

    # In the current implementation, missing profiler logs warning but continues
    # until it tries to use mesh data, or skips if fast mode.
    # Actually looking at code:
    # if "character_profiler" in self.ai_modules: ... else: skipped
    # Then checks mesh_obj for rigging.

    # We expect failure here because rigging is enabled but no mesh generated
    with pytest.raises(Exception):  # noqa: B017
        await forge_matrix.generate_character(request)


@pytest.mark.asyncio
async def test_export_character_no_formats(forge_matrix: Any) -> None:
    """Test export fails if no formats requested."""
    request = CharacterRequest(concept="No export", export_formats=[])

    # Mock profiler to return mesh so we get to export stage
    forge_matrix.registry.ai_modules["character_profiler"].generate.return_value = MagicMock(
        mesh_data=MagicMock(vertices=[[0, 0, 0]], faces=[[0, 1, 2]]),
        to_dict=lambda: {"visual": "data"},
    )

    # Mock rigging to succeed
    forge_matrix.registry.ai_modules["rigging"].process.return_value = MagicMock(
        data=MagicMock(skeleton="skel", weights="w")
    )

    # Should raise ExportError("none", ...)
    from kagami.forge.exceptions import ExportError

    with pytest.raises(ExportError):
        await forge_matrix.generate_character(request)
