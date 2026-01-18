"""Tests for kagami.forge.matrix.orchestrator (ForgeMatrix)."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import torch

from kagami.forge.matrix.orchestrator import ForgeMatrix, _hash_embedding
from kagami.forge.schema import CharacterRequest, ExportFormat, QualityLevel
from kagami.forge.exceptions import ExportError

pytestmark = pytest.mark.tier_integration


@pytest.fixture
def mock_registry():
    """Create mock ComponentRegistry."""
    registry = MagicMock()
    registry.is_available = MagicMock(return_value=True)
    registry.ai_modules = {}
    return registry


@pytest.fixture
def mock_lifecycle():
    """Create mock LifecycleManager."""
    lifecycle = MagicMock()
    lifecycle.initialize = MagicMock()
    lifecycle.initialized = True
    lifecycle.asset_cache = MagicMock()
    return lifecycle


@pytest.fixture
def forge_matrix(mock_registry, mock_lifecycle):
    """Create ForgeMatrix with mocked subsystems."""
    matrix = ForgeMatrix(config={"test": True})
    matrix.registry = mock_registry
    matrix.lifecycle = mock_lifecycle
    return matrix


class TestForgeMatrixInitialization:
    """Test ForgeMatrix initialization."""

    def test_init(self):
        """Test ForgeMatrix initialization."""
        matrix = ForgeMatrix()
        assert matrix.config is not None
        assert matrix.registry is not None
        assert matrix.lifecycle is not None

    @pytest.mark.asyncio
    async def test_initialize(self, forge_matrix, mock_lifecycle):
        """Test ForgeMatrix.initialize()."""
        mock_lifecycle.initialized = False
        await forge_matrix.initialize()
        mock_lifecycle.initialize.assert_called_once()

    def test_properties(self, forge_matrix):
        """Test ForgeMatrix properties."""
        assert forge_matrix.ai_modules == {}
        assert isinstance(forge_matrix.execution_trace, list)
        assert forge_matrix.initialized is True
        assert forge_matrix.asset_cache is not None


class TestHashEmbedding:
    """Test _hash_embedding helper function."""

    def test_hash_embedding_deterministic(self):
        """Test that hash embedding is deterministic."""
        text = "test concept"
        emb1 = _hash_embedding(text)
        emb2 = _hash_embedding(text)

        assert torch.allclose(emb1, emb2)

    def test_hash_embedding_shape(self):
        """Test hash embedding output shape."""
        text = "test"
        emb = _hash_embedding(text, dim=256)

        assert emb.shape == (1, 256)

    def test_hash_embedding_normalized(self):
        """Test hash embedding is normalized."""
        text = "test"
        emb = _hash_embedding(text)

        norm = torch.norm(emb)
        assert torch.isclose(norm, torch.tensor(1.0), atol=1e-5)

    def test_hash_embedding_different_texts(self):
        """Test different texts produce different embeddings."""
        emb1 = _hash_embedding("concept1")
        emb2 = _hash_embedding("concept2")

        # Embeddings should be different
        assert not torch.allclose(emb1, emb2, atol=0.1)

    def test_hash_embedding_empty_string(self):
        """Test hash embedding with empty string."""
        emb = _hash_embedding("")

        assert emb.shape[0] == 1
        assert emb.shape[1] > 0


class TestCharacterGeneration:
    """Test character generation pipeline."""

    @pytest.mark.asyncio
    async def test_generate_character_success(self, forge_matrix):
        """Test successful character generation."""
        request = CharacterRequest(
            request_id="test-123",
            concept="warrior character",
            export_formats=[ExportFormat.GLB],
            quality_level=QualityLevel.LOW,
        )

        with patch.object(forge_matrix, "_generate_character_impl") as mock_impl:
            mock_impl.return_value = {
                "request_id": "test-123",
                "concept": "warrior character",
                "status": "success",
                "success": True,
                "character": {"mesh": "data"},
                "metrics": {"quality": 0.9},
            }

            result = await forge_matrix.generate_character(request)

            assert result["success"] is True
            assert result["concept"] == "warrior character"
            mock_impl.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_character_empty_concept(self, forge_matrix):
        """Test character generation with empty concept."""
        request = CharacterRequest(
            request_id="test-123",
            concept="",  # Empty
        )

        result = await forge_matrix.generate_character(request)

        assert result["success"] is False
        assert "concept is required" in result["error"]
        assert result["error_code"] == "missing_concept"

    @pytest.mark.asyncio
    async def test_generate_character_short_concept(self, forge_matrix):
        """Test character generation with too-short concept."""
        request = CharacterRequest(
            request_id="test-123",
            concept="ab",  # Less than 3 chars
        )

        result = await forge_matrix.generate_character(request)

        assert result["success"] is False
        assert result["error_code"] == "missing_concept"

    @pytest.mark.asyncio
    async def test_generate_character_dict_input(self, forge_matrix):
        """Test character generation with dict input."""
        request_dict = {
            "request_id": "test-123",
            "concept": "warrior character",
        }

        with patch.object(forge_matrix, "_generate_character_impl") as mock_impl:
            mock_impl.return_value = {
                "success": True,
                "character": {},
                "metrics": {},
            }

            result = await forge_matrix.generate_character(request_dict)

            assert result["success"] is True


class TestCharacterGenerationImplementation:
    """Test _generate_character_impl internal implementation."""

    @pytest.mark.asyncio
    async def test_full_pipeline(self, forge_matrix):
        """Test full character generation pipeline."""
        request = CharacterRequest(
            request_id="test-123",
            concept="warrior character",
            export_formats=[ExportFormat.GLB],
            quality_level=QualityLevel.MEDIUM,
        )

        with patch("kagami.forge.matrix.components.generate_visuals") as mock_visuals, \
             patch("kagami.forge.matrix.components.generate_personality") as mock_personality, \
             patch("kagami.forge.matrix.components.generate_voice") as mock_voice, \
             patch("kagami.forge.matrix.components.generate_narrative") as mock_narrative, \
             patch("kagami.forge.matrix.components.process_rigging") as mock_rigging, \
             patch("kagami.forge.matrix.components.export_character") as mock_export, \
             patch("kagami.forge.matrix.converters.compile_character") as mock_compile, \
             patch("kagami.forge.matrix.converters.calculate_quality_metrics") as mock_metrics:

            mock_visuals.return_value = {"mesh": "data"}
            mock_personality.return_value = {"personality": "brave"}
            mock_voice.return_value = {"voice": "deep"}
            mock_narrative.return_value = {"backstory": "from the north"}
            mock_rigging.return_value = {"rigged": True}
            mock_export.return_value = {"files": ["model.glb"]}
            mock_compile.return_value = {"complete": True}
            mock_metrics.return_value = {"overall_score": 0.9}

            result = await forge_matrix._generate_character_impl(request)

            assert result["success"] is True
            assert "character" in result
            assert "metrics" in result

            # Verify pipeline stages were called
            mock_visuals.assert_called_once()
            mock_personality.assert_called_once()
            mock_voice.assert_called_once()
            mock_narrative.assert_called_once()

    @pytest.mark.asyncio
    async def test_pipeline_no_exports_raises(self, forge_matrix):
        """Test pipeline raises ExportError when no export formats."""
        request = CharacterRequest(
            request_id="test-123",
            concept="warrior",
            export_formats=[],  # No formats
        )

        with patch("kagami.forge.matrix.components.generate_visuals") as mock_visuals, \
             patch("kagami.forge.matrix.components.generate_personality"), \
             patch("kagami.forge.matrix.components.generate_voice"), \
             patch("kagami.forge.matrix.components.generate_narrative"):

            mock_visuals.return_value = {"mesh": "data"}

            with pytest.raises(ExportError) as exc_info:
                await forge_matrix._generate_character_impl(request)

            assert "No export formats" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_pipeline_handles_behavior_exception(self, forge_matrix):
        """Test pipeline handles exceptions in behavior generation."""
        request = CharacterRequest(
            request_id="test-123",
            concept="warrior",
            export_formats=[ExportFormat.GLB],
        )

        with patch("kagami.forge.matrix.components.generate_visuals") as mock_visuals, \
             patch("kagami.forge.matrix.components.generate_personality") as mock_personality, \
             patch("kagami.forge.matrix.components.generate_voice") as mock_voice, \
             patch("kagami.forge.matrix.components.generate_narrative") as mock_narrative, \
             patch("kagami.forge.matrix.components.export_character") as mock_export, \
             patch("kagami.forge.matrix.converters.compile_character") as mock_compile, \
             patch("kagami.forge.matrix.converters.calculate_quality_metrics") as mock_metrics:

            mock_visuals.return_value = {"mesh": "data"}
            mock_personality.side_effect = RuntimeError("Personality failed")
            mock_voice.return_value = {"voice": "data"}
            mock_narrative.return_value = {"narrative": "data"}
            mock_export.return_value = {"files": []}
            mock_compile.return_value = {}
            mock_metrics.return_value = {}

            result = await forge_matrix._generate_character_impl(request)

            # Should still succeed, just with None for behavior
            assert result["success"] is True


class TestColonyIntegration:
    """Test colony integration features."""

    @pytest.mark.asyncio
    async def test_colony_bridge_integration(self, forge_matrix):
        """Test colony bridge is called during generation."""
        request = CharacterRequest(
            request_id="test-123",
            concept="warrior",
            export_formats=[ExportFormat.GLB],
        )

        with patch("kagami.forge.matrix.orchestrator._get_colony_bridge") as mock_bridge, \
             patch("kagami.forge.matrix.components.generate_visuals") as mock_visuals, \
             patch("kagami.forge.matrix.components.generate_personality"), \
             patch("kagami.forge.matrix.components.generate_voice"), \
             patch("kagami.forge.matrix.components.generate_narrative"), \
             patch("kagami.forge.matrix.components.export_character") as mock_export, \
             patch("kagami.forge.matrix.converters.compile_character") as mock_compile, \
             patch("kagami.forge.matrix.converters.calculate_quality_metrics") as mock_metrics:

            bridge = MagicMock()
            bridge.return_value = {"state": {"value": 0.5}, "metrics": {}}
            bridge.update_from_result = MagicMock()
            mock_bridge.return_value = bridge

            mock_visuals.return_value = {"mesh": "data"}
            mock_export.return_value = {"files": []}
            mock_compile.return_value = {}
            mock_metrics.return_value = MagicMock(overall_score=0.9)

            result = await forge_matrix._generate_character_impl(request)

            # Colony bridge should have been called
            bridge.assert_called_once()
            bridge.update_from_result.assert_called_once()

    @pytest.mark.asyncio
    async def test_colony_bridge_exception_handled(self, forge_matrix):
        """Test exceptions in colony bridge are handled gracefully."""
        request = CharacterRequest(
            request_id="test-123",
            concept="warrior",
            export_formats=[ExportFormat.GLB],
        )

        with patch("kagami.forge.matrix.orchestrator._get_colony_bridge") as mock_bridge, \
             patch("kagami.forge.matrix.components.generate_visuals") as mock_visuals, \
             patch("kagami.forge.matrix.components.generate_personality"), \
             patch("kagami.forge.matrix.components.generate_voice"), \
             patch("kagami.forge.matrix.components.generate_narrative"), \
             patch("kagami.forge.matrix.components.export_character") as mock_export, \
             patch("kagami.forge.matrix.converters.compile_character") as mock_compile, \
             patch("kagami.forge.matrix.converters.calculate_quality_metrics") as mock_metrics:

            mock_bridge.side_effect = RuntimeError("Colony bridge failed")
            mock_visuals.return_value = {"mesh": "data"}
            mock_export.return_value = {"files": []}
            mock_compile.return_value = {}
            mock_metrics.return_value = {}

            # Should not raise, just log and continue
            result = await forge_matrix._generate_character_impl(request)
            assert result["success"] is True


class TestProgressEmission:
    """Test progress event emission."""

    @pytest.mark.asyncio
    async def test_emit_progress(self, forge_matrix):
        """Test progress emission."""
        with patch("kagami.core.events.get_unified_bus") as mock_bus:
            bus = MagicMock()
            bus.publish = AsyncMock()
            mock_bus.return_value = bus

            await forge_matrix._emit_progress(
                stage="forge.start",
                progress=10,
                eta=5000,
                rationale="Starting",
                correlation_id="test-123",
            )

            bus.publish.assert_called_once()
            args = bus.publish.call_args[0]
            assert args[0] == "forge.progress"
            assert args[1]["stage"] == "forge.start"

    @pytest.mark.asyncio
    async def test_emit_progress_exception_handled(self, forge_matrix):
        """Test progress emission handles exceptions gracefully."""
        with patch("kagami.core.events.get_unified_bus") as mock_bus:
            mock_bus.side_effect = RuntimeError("Bus not available")

            # Should not raise
            await forge_matrix._emit_progress(
                stage="forge.start",
                progress=10,
                eta=5000,
                rationale="Starting",
                correlation_id="test-123",
            )


class TestTracing:
    """Test execution tracing."""

    def test_trace_stage_context(self, forge_matrix):
        """Test trace stage context manager."""
        request = MagicMock()
        context = forge_matrix._trace_stage("test.component", request)

        assert context is not None
        assert hasattr(context, "__enter__")
        assert hasattr(context, "__exit__")

    def test_build_trace_attrs(self, forge_matrix):
        """Test building trace attributes."""
        request = MagicMock()
        attrs = forge_matrix._build_trace_attrs(
            "test.component",
            request,
            {"extra": "data"}
        )

        assert isinstance(attrs, dict)

    def test_record_trace_event(self, forge_matrix):
        """Test recording trace event."""
        # Should not raise
        forge_matrix._record_trace_event(
            "test.component",
            "success",
            None,
            extra_data="test"
        )

        # Check trace was recorded
        assert len(forge_matrix.execution_trace) > 0
