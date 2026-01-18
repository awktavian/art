"""Tests for kagami.forge.modules.visual_design.character_profiler (CharacterVisualProfiler)."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import numpy as np

from kagami.forge.modules.visual_design.character_profiler import (
    CharacterVisualProfiler,
    StyleConfig,
)
from kagami.forge.schema import CharacterRequest, QualityLevel, GenerationResult

pytestmark = pytest.mark.tier_integration


@pytest.fixture
def profiler():
    """Create CharacterVisualProfiler instance."""
    return CharacterVisualProfiler(config={"llm": {}})


@pytest.fixture
def mock_llm():
    """Create mock LLM adapter."""
    llm = MagicMock()
    llm.initialize = AsyncMock()
    llm.generate_text = AsyncMock(return_value="Generated visual design")
    return llm


class TestCharacterVisualProfilerInit:
    """Test CharacterVisualProfiler initialization."""

    def test_init_default(self):
        """Test default initialization."""
        profiler = CharacterVisualProfiler()
        assert profiler._initialized is False
        assert len(profiler.design_history) == 0

    def test_init_with_config(self):
        """Test initialization with config."""
        config = {"llm": {"model": "test"}}
        profiler = CharacterVisualProfiler(config=config)
        assert profiler.style_config is not None

    @pytest.mark.asyncio
    async def test_initialize(self, profiler, mock_llm):
        """Test profiler initialization."""
        profiler.llm = mock_llm
        await profiler.initialize()
        assert profiler._initialized is True
        mock_llm.initialize.assert_called_once()


class TestStyleConfig:
    """Test StyleConfig dataclass."""

    def test_default_style_config(self):
        """Test default StyleConfig."""
        config = StyleConfig()
        assert config.color_palette == "vibrant"
        assert config.cuteness_level == "cute"
        assert config.emoji_compatible is True

    def test_custom_style_config(self):
        """Test custom StyleConfig."""
        config = StyleConfig(
            color_palette="muted",
            cuteness_level="realistic",
            emoji_compatible=False,
        )
        assert config.color_palette == "muted"
        assert config.cuteness_level == "realistic"


class TestKagamiStylePrompts:
    """Test Kagami house-style prompt generation."""

    @pytest.mark.asyncio
    async def test_create_kagami_style_prompt(self, profiler, mock_llm):
        """Test creating Kagami-style prompt."""
        profiler.llm = mock_llm
        await profiler.initialize()

        prompt = await profiler.create_kagami_style_prompt(
            character_concept="warrior",
            character_traits=["brave", "strong"],
            outfit_style="armor",
        )

        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_get_kagami_negative_prompt(self, profiler):
        """Test Kagami negative prompt generation."""
        negative = profiler.get_kagami_negative_prompt()
        assert "low quality" in negative
        assert "blurry" in negative


class TestGeneration:
    """Test character visual generation."""

    @pytest.mark.asyncio
    async def test_generate_success(self, profiler, mock_llm):
        """Test successful generation."""
        profiler.llm = mock_llm
        await profiler.initialize()

        request = CharacterRequest(
            request_id="test-123",
            concept="warrior character",
            quality_level=QualityLevel.LOW,
        )

        with patch("kagami.forge.modules.generation.get_3d_generator") as mock_gen:
            gen_instance = MagicMock()
            gen_result = MagicMock()
            gen_result.success = True
            gen_result.mesh_path = "/tmp/test.obj"
            gen_result.num_gaussians = 1000
            gen_result.final_loss = 0.1
            gen_instance.generate = AsyncMock(return_value=gen_result)
            mock_gen.return_value = gen_instance

            with patch("trimesh.load") as mock_load:
                mesh = MagicMock()
                mesh.vertices = np.array([[0, 0, 0], [1, 1, 1]])
                mesh.faces = np.array([[0, 1, 2]])
                mock_load.return_value = mesh

                result = await profiler.generate(request)

                assert result.success is True
                assert result.mesh_data is not None

    @pytest.mark.asyncio
    async def test_generate_mesh_failure(self, profiler, mock_llm):
        """Test generation with mesh failure."""
        profiler.llm = mock_llm
        await profiler.initialize()

        request = CharacterRequest(
            request_id="test-123",
            concept="warrior",
            quality_level=QualityLevel.LOW,
        )

        with patch("kagami.forge.modules.generation.get_3d_generator") as mock_gen:
            mock_gen.side_effect = RuntimeError("Generation failed")

            result = await profiler.generate(request)

            assert result.success is False
            assert result.error is not None


class TestVisualAnalysis:
    """Test visual analysis and parsing."""

    @pytest.mark.asyncio
    async def test_generate_visual_design(self, profiler, mock_llm):
        """Test visual design generation."""
        profiler.llm = mock_llm
        await profiler.initialize()

        from kagami.forge.forge_llm_base import CharacterContext, CharacterAspect
        context = CharacterContext(
            character_id="test",
            name="warrior",
            aspect=CharacterAspect.VISUAL_DESIGN,
        )

        result = await profiler._generate_visual_design(context, None)

        assert "raw_content" in result

    @pytest.mark.asyncio
    async def test_parse_visual_design(self, profiler, mock_llm):
        """Test parsing visual design response."""
        profiler.llm = mock_llm
        await profiler.initialize()

        response = "Physical: tall, muscular. Style: medieval armor."

        result = await profiler._parse_visual_design(response)

        assert "raw_content" in result
        assert result["raw_content"] == response


class TestQualityAssessment:
    """Test quality scoring."""

    def test_calculate_quality_score_high(self, profiler):
        """Test high quality score calculation."""
        visual_profile = {
            "design_elements": {"physical": "data"},
            "raw_content": "a" * 1000,
            "structured_sections": {"section": "data"},
            "reasoning": "detailed reasoning",
        }

        score = profiler._calculate_quality_score(visual_profile)
        assert score > 0.8

    def test_calculate_quality_score_low(self, profiler):
        """Test low quality score calculation."""
        visual_profile = {
            "raw_content": "short",
        }

        score = profiler._calculate_quality_score(visual_profile)
        assert score < 0.5
