"""Tests for kagami.forge.modules.motion.facial_animator (FacialAnimator)."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import torch

from kagami.forge.modules.motion.facial_animator import FacialAnimator

pytestmark = pytest.mark.tier_integration


@pytest.fixture
def facial_animator():
    """Create FacialAnimator instance."""
    return FacialAnimator(device=torch.device("cpu"))


class TestFacialAnimatorInit:
    """Test FacialAnimator initialization."""

    def test_init_default(self):
        """Test default initialization."""
        animator = FacialAnimator()
        assert animator.initialized is False
        assert animator.default_framerate == 30.0

    def test_init_with_config(self):
        """Test initialization with config."""
        config = {"fps": 60.0, "blend_shape_count": 100}
        animator = FacialAnimator(config=config)
        assert animator.default_framerate == 60.0
        assert animator.max_blend_shapes == 100

    @pytest.mark.asyncio
    async def test_initialize(self, facial_animator):
        """Test animator initialization."""
        with patch("kagami.forge.modules.motion.deca_integration.DECAIntegration") as mock_deca, \
             patch("kagami.forge.modules.motion.audio2face_integration.Audio2FaceIntegration") as mock_a2f:

            mock_deca.return_value = MagicMock()
            mock_a2f.return_value = MagicMock()

            await facial_animator.initialize()
            assert facial_animator.is_initialized is True


class TestBlinkGeneration:
    """Test blink animation generation."""

    @pytest.mark.asyncio
    async def test_generate_blinks(self, facial_animator):
        """Test generating blink animations."""
        # Mock initialization
        facial_animator.initialized = True
        facial_animator.expression_library = {
            "neutral": MagicMock(blendshapes={})
        }

        animation = await facial_animator.generate_blinks(
            duration=5.0,
            blink_rate=20,
        )

        assert animation is not None
        assert "frames" in animation or isinstance(animation, dict)

    @pytest.mark.asyncio
    async def test_blink_rate_variation(self, facial_animator):
        """Test different blink rates."""
        facial_animator.initialized = True
        facial_animator.expression_library = {"neutral": MagicMock(blendshapes={})}

        # Test low blink rate
        anim_low = await facial_animator.generate_blinks(duration=5.0, blink_rate=10)

        # Test high blink rate
        anim_high = await facial_animator.generate_blinks(duration=5.0, blink_rate=30)

        assert anim_low is not None
        assert anim_high is not None


class TestExpressionGeneration:
    """Test facial expression generation."""

    @pytest.mark.asyncio
    async def test_generate_expression(self, facial_animator):
        """Test generating facial expressions."""
        facial_animator.initialized = True
        facial_animator.expression_library = {
            "happy": MagicMock(blendshapes={"mouthSmile": 0.8})
        }

        expression = await facial_animator.generate_expression(
            emotion="happy",
            intensity=0.8,
        )

        assert expression is not None

    @pytest.mark.asyncio
    async def test_expression_intensity_scaling(self, facial_animator):
        """Test expression intensity scaling."""
        facial_animator.initialized = True
        facial_animator.expression_library = {
            "happy": MagicMock(blendshapes={"mouthSmile": 1.0})
        }

        # Low intensity
        expr_low = await facial_animator.generate_expression("happy", 0.3)

        # High intensity
        expr_high = await facial_animator.generate_expression("happy", 1.0)

        assert expr_low is not None
        assert expr_high is not None
