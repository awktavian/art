"""Tests for kagami.forge.modules.generation.gaussian_splatting."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import numpy as np
import torch

from kagami.forge.modules.generation.gaussian_splatting import (
    GsgenGenerator,
    GaussianSplattingConfig,
    Gaussian3D,
    GaussianCloud,
    GenerationMode,
    GenerationResult,
    get_3d_generator,
)

pytestmark = pytest.mark.tier_integration


@pytest.fixture
def config():
    """Create test configuration."""
    return GaussianSplattingConfig(
        num_gaussians=100,
        num_iterations=10,  # Low for testing
        export_mesh=True,
    )


@pytest.fixture
def generator(config):
    """Create GsgenGenerator instance."""
    return GsgenGenerator(config)


class TestGaussian3D:
    """Test Gaussian3D dataclass."""

    def test_create_gaussian(self):
        """Test creating a Gaussian3D."""
        gaussian = Gaussian3D(
            position=np.array([0.0, 0.0, 0.0]),
            color=np.array([1.0, 0.0, 0.0]),
            opacity=0.5,
            scale=np.array([0.1, 0.1, 0.1]),
            rotation=np.array([1.0, 0.0, 0.0, 0.0]),
        )

        assert gaussian.position.shape == (3,)
        assert gaussian.color.shape == (3,)
        assert gaussian.opacity == 0.5

    def test_gaussian_to_dict(self):
        """Test converting Gaussian to dict."""
        gaussian = Gaussian3D(
            position=np.array([0.0, 0.0, 0.0]),
            color=np.array([1.0, 0.0, 0.0]),
            opacity=0.5,
            scale=np.array([0.1, 0.1, 0.1]),
            rotation=np.array([1.0, 0.0, 0.0, 0.0]),
        )

        d = gaussian.to_dict()
        assert "position" in d
        assert "color" in d
        assert d["opacity"] == 0.5


class TestGaussianCloud:
    """Test GaussianCloud collection."""

    def test_create_cloud(self):
        """Test creating a GaussianCloud."""
        gaussians = [
            Gaussian3D(
                position=np.array([i, 0, 0], dtype=np.float32),
                color=np.array([1, 0, 0], dtype=np.float32),
                opacity=0.5,
                scale=np.array([0.1, 0.1, 0.1], dtype=np.float32),
                rotation=np.array([1, 0, 0, 0], dtype=np.float32),
            )
            for i in range(5)
        ]

        cloud = GaussianCloud(gaussians=gaussians)
        assert cloud.num_gaussians == 5

    def test_get_positions(self):
        """Test getting all positions."""
        gaussians = [
            Gaussian3D(
                position=np.array([float(i), 0.0, 0.0]),
                color=np.array([1.0, 0.0, 0.0]),
                opacity=0.5,
                scale=np.array([0.1, 0.1, 0.1]),
                rotation=np.array([1.0, 0.0, 0.0, 0.0]),
            )
            for i in range(3)
        ]

        cloud = GaussianCloud(gaussians=gaussians)
        positions = cloud.get_positions()

        assert positions.shape == (3, 3)


class TestGsgenGeneratorInit:
    """Test GsgenGenerator initialization."""

    def test_init_default(self):
        """Test default initialization."""
        gen = GsgenGenerator()
        assert gen.config is not None
        assert gen._initialized is False

    def test_init_with_config(self, config):
        """Test initialization with config."""
        gen = GsgenGenerator(config)
        assert gen.config.num_gaussians == 100

    @pytest.mark.asyncio
    async def test_initialize(self, generator):
        """Test generator initialization."""
        with patch("kagami.core.boot_mode.is_test_mode", return_value=True):
            await generator.initialize()
            assert generator._initialized is True


class TestGaussianInitialization:
    """Test Gaussian cloud initialization."""

    def test_initialize_gaussians(self, generator):
        """Test initializing random Gaussians."""
        cloud = generator._initialize_gaussians()

        assert cloud.num_gaussians == generator.config.num_gaussians
        assert len(cloud.gaussians) > 0

        # Check first Gaussian has valid properties
        g = cloud.gaussians[0]
        assert g.position.shape == (3,)
        assert g.color.shape == (3,)
        assert 0 <= g.opacity <= 1


class TestGeneration:
    """Test 3D generation."""

    @pytest.mark.asyncio
    async def test_generate_simple(self, generator):
        """Test simple generation (without diffusion model)."""
        with patch("kagami.core.boot_mode.is_test_mode", return_value=True):
            await generator.initialize()

            result = await generator.generate(
                prompt="test object",
                num_iterations=5,
                output_name="test",
            )

            assert result.success is True
            assert result.num_gaussians > 0

    @pytest.mark.asyncio
    async def test_generate_with_negative_prompt(self, generator):
        """Test generation with negative prompt."""
        with patch("kagami.core.boot_mode.is_test_mode", return_value=True):
            await generator.initialize()

            result = await generator.generate(
                prompt="test",
                negative_prompt="low quality",
                num_iterations=5,
            )

            assert result.success is True


class TestExport:
    """Test export functionality."""

    @pytest.mark.asyncio
    async def test_export_ply(self, generator):
        """Test PLY export."""
        cloud = generator._initialize_gaussians()
        output_path = generator._output_dir / "test.ply"

        await generator._export_ply(cloud, output_path)

        assert output_path.exists()
        output_path.unlink()  # Cleanup

    @pytest.mark.asyncio
    async def test_export_mesh(self, generator):
        """Test mesh export."""
        cloud = generator._initialize_gaussians()
        output_path = generator._output_dir / "test.obj"

        with patch("scipy.ndimage.gaussian_filter") as mock_filter, \
             patch("skimage.measure.marching_cubes") as mock_mc:

            mock_filter.return_value = np.random.rand(64, 64, 64)
            mock_mc.return_value = (
                np.random.rand(10, 3),  # vertices
                np.random.randint(0, 10, (5, 3)),  # faces
                None,
                None,
            )

            await generator._export_mesh(cloud, output_path)

            assert output_path.exists()
            output_path.unlink()  # Cleanup


class TestSingletonAccess:
    """Test singleton access."""

    @pytest.mark.asyncio
    async def test_get_3d_generator(self):
        """Test getting global generator."""
        with patch("kagami.core.boot_mode.is_test_mode", return_value=True):
            gen = await get_3d_generator()
            assert gen is not None
