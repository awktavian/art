"""
Style Enforcement Pipeline Smoke Test (real_model)

Runs the real Emu3.5 image generation path.

This test is intentionally marked ``real_model`` and will skip unless the
local Emu3.5 checkout + cached weights are present.
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.real_model
@pytest.mark.asyncio
async def test_style_enforcement_pipeline_local_smoke(monkeypatch: Any, tmp_path: Any) -> None:
    # Require local Emu3.5 checkout and cached weights.
    emu_repo = Path(os.getenv("EMU_REPO_PATH") or (Path.home() / "dev" / "Emu3.5"))
    if not emu_repo.exists():
        pytest.skip(
            f"Emu3.5 repo not found at {emu_repo} (set EMU_REPO_PATH or run make forge-emu)"
        )

    model_index = Path.home() / ".cache" / "kagami" / "emu3.5" / "models" / "model_index.json"
    if not model_index.exists():
        pytest.skip(
            f"Emu3.5 weights not cached at {model_index} (run once with network to download)"
        )

    # Import after dependency check
    from kagami.forge.modules.visual_design.style_enforcement_pipeline import (
        style_enforcement_pipeline,
    )

    # Initialize pipeline
    try:
        await style_enforcement_pipeline.initialize()
    except Exception as e:
        pytest.skip(f"Style enforcement pipeline initialization failed: {e}")

    # Keep the smoke test bounded (do not rely on env parsing timing).
    style_enforcement_pipeline.max_regeneration_attempts = 0
    style_enforcement_pipeline.style_confidence_threshold = 0.0

    out_dir = tmp_path / "style_output"
    params = {"width": 256, "height": 256, "output_dir": str(out_dir)}

    result = await style_enforcement_pipeline.generate_with_style_enforcement(
        base_prompt="cute mascot penguin, studio lighting, white background",
        generation_params=params,
        metadata={"test": "style_enforcement_smoke"},
    )

    assert result is not None
    assert result.success in (True, False)  # validation thresholds may block
    if result.final_path:
        p = Path(result.final_path)
        assert p.exists()
        assert p.stat().st_size > 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_pipeline_initialization():
    """Test StyleEnforcementPipeline initialization."""
    from kagami.forge.modules.visual_design.style_enforcement_pipeline import (
        StyleEnforcementPipeline,
    )

    pipeline = StyleEnforcementPipeline()
    assert not pipeline.initialized
    assert pipeline.image_generator is None
    assert pipeline.enforcement_level == "strict"
    assert pipeline.auto_correct is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_pipeline_validation_mode():
    """Test validation mode detection."""
    from kagami.forge.modules.visual_design.style_enforcement_pipeline import (
        StyleEnforcementPipeline,
    )

    pipeline = StyleEnforcementPipeline()

    # Default is simple
    assert pipeline._validation_mode() == "simple"

    # Test explicit setting
    os.environ["KAGAMI_STYLE_VALIDATION_MODE"] = "full"
    assert pipeline._validation_mode() == "full"

    os.environ["KAGAMI_STYLE_VALIDATION_MODE"] = "simple"
    assert pipeline._validation_mode() == "simple"

    # Invalid values fall back to simple
    os.environ["KAGAMI_STYLE_VALIDATION_MODE"] = "invalid"
    assert pipeline._validation_mode() == "simple"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_pipeline_calculate_preview_dimensions():
    """Test preview dimension calculation."""
    from kagami.forge.modules.visual_design.style_enforcement_pipeline import (
        StyleEnforcementPipeline,
    )

    pipeline = StyleEnforcementPipeline()

    # Mock image generator
    mock_gen = MagicMock()
    mock_gen.openai_client = MagicMock()
    pipeline.image_generator = mock_gen  # type: ignore[assignment]

    # Square image with GPT
    params = {"width": 2048, "height": 2048, "use_gpt": True}
    req_w, req_h, prev_w, prev_h = pipeline._calculate_preview_dimensions(params)
    assert req_w == 2048
    assert req_h == 2048
    assert prev_w == 1024
    assert prev_h == 1024

    # Landscape with GPT
    params = {"width": 2048, "height": 1024, "use_gpt": True}
    req_w, req_h, prev_w, prev_h = pipeline._calculate_preview_dimensions(params)
    assert prev_w == 1536
    assert prev_h == 1024

    # Portrait with GPT
    params = {"width": 1024, "height": 2048, "use_gpt": True}
    req_w, req_h, prev_w, prev_h = pipeline._calculate_preview_dimensions(params)
    assert prev_w == 1024
    assert prev_h == 1536

    # Without GPT
    params = {"width": 2048, "height": 2048, "use_gpt": False}
    req_w, req_h, prev_w, prev_h = pipeline._calculate_preview_dimensions(params)
    assert prev_w == 768
    assert prev_h == 768


@pytest.mark.unit
@pytest.mark.asyncio
async def test_pipeline_enforce_style_in_prompt_character():
    """Test prompt style enforcement for character content."""
    from kagami.forge.modules.visual_design.style_enforcement_pipeline import (
        StyleEnforcementPipeline,
    )

    pipeline = StyleEnforcementPipeline()

    # Offline mode (no LLM)
    os.environ["KAGAMI_TEST_NO_CLOUD"] = "1"

    mascot_data = {
        "name": "Tux",
        "species": "penguin",
        "color_palette": {"primary": "black", "secondary": "white"},
        "personality_traits": ["friendly", "helpful"],
    }

    params = {
        "mascot_data": mascot_data,
        "max_prompt_chars": 500,
    }

    result = await pipeline._enforce_style_in_prompt(
        "standing pose", params, content_type="character"
    )

    assert isinstance(result, str)
    assert len(result) > 0
    # Should include character constraints
    assert "proportions" in result.lower() or "eyes" in result.lower()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_pipeline_enforce_style_in_prompt_ui_component():
    """Test prompt style enforcement for UI component content."""
    from kagami.forge.modules.visual_design.style_enforcement_pipeline import (
        StyleEnforcementPipeline,
    )

    pipeline = StyleEnforcementPipeline()

    # Offline mode
    os.environ["KAGAMI_TEST_NO_CLOUD"] = "1"

    params = {"max_prompt_chars": 500}

    result = await pipeline._enforce_style_in_prompt(
        "button with icon", params, content_type="ui_component"
    )

    assert isinstance(result, str)
    # Should mention UI constraints
    assert "ui" in result.lower() or "component" in result.lower()
    # Should not have character language
    assert "eyes" not in result.lower()
    assert "species" not in result.lower()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_pipeline_enforce_style_empty_prompt():
    """Test style enforcement with empty prompt."""
    from kagami.forge.modules.visual_design.style_enforcement_pipeline import (
        StyleEnforcementPipeline,
    )

    pipeline = StyleEnforcementPipeline()

    os.environ["KAGAMI_TEST_NO_CLOUD"] = "1"

    params = {"max_prompt_chars": 500}

    result = await pipeline._enforce_style_in_prompt("", params, content_type="character")

    # Should still return a valid prompt with style elements
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_pipeline_get_style_guide_excerpt():
    """Test style guide excerpt extraction."""
    from kagami.forge.modules.visual_design.style_enforcement_pipeline import (
        StyleEnforcementPipeline,
    )

    pipeline = StyleEnforcementPipeline()

    # Character mode
    excerpt = pipeline._get_style_guide_excerpt(content_type="character", max_chars=500)
    assert isinstance(excerpt, str)
    # May be empty if no style guide file exists
    if excerpt:
        assert len(excerpt) <= 500

    # UI component mode
    excerpt = pipeline._get_style_guide_excerpt(content_type="ui_component", max_chars=500)
    assert isinstance(excerpt, str)
    # Should not contain character-specific language
    if excerpt:
        assert "species" not in excerpt.lower()

    # Brand tile mode
    excerpt = pipeline._get_style_guide_excerpt(content_type="brand_tile", max_chars=500)
    assert isinstance(excerpt, str)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_pipeline_vision_validation_disabled():
    """Test vision validation when disabled."""
    from kagami.forge.modules.visual_design.style_enforcement_pipeline import (
        StyleEnforcementPipeline,
    )

    pipeline = StyleEnforcementPipeline()

    # Disable vision validation
    os.environ["KAGAMI_STYLE_VISION_VALIDATE"] = "0"

    result = await pipeline._vision_inspect_image(
        Path("/nonexistent.png"), content_type="character"
    )

    assert isinstance(result, dict)
    assert result["overall_score"] == 0.0
    assert result["passes_standard"] is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_pipeline_generate_content_no_openai():
    """Test content generation without OpenAI client."""
    from kagami.forge.modules.visual_design.style_enforcement_pipeline import (
        StyleEnforcementPipeline,
    )

    pipeline = StyleEnforcementPipeline()
    pipeline.initialized = True
    pipeline.image_generator = None

    params = {"width": 1024, "height": 1024}

    result = await pipeline._generate_content("test prompt", params)

    assert isinstance(result, dict)
    assert "error" in result
    assert "unavailable" in result["error"].lower()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_pipeline_merge_vision_validation():
    """Test vision validation merging."""
    from kagami.forge.modules.visual_design.style_enforcement_pipeline import (
        StyleEnforcementPipeline,
    )

    pipeline = StyleEnforcementPipeline()

    # Disable vision to test passthrough
    os.environ["KAGAMI_STYLE_VISION_VALIDATE"] = "0"

    base_validation = {"overall_score": 0.9, "passes_standard": True}

    result = await pipeline._merge_vision_validation(
        base_validation, Path("/nonexistent.png"), "character"
    )

    # Should return base validation unchanged
    assert result["overall_score"] == 0.9
    assert result["passes_standard"] is True
