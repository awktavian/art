"""Proof test: Gaussian Splatting generator produces artifacts.

This is intentionally small/CPU-bound so it can run in CI without requiring
large diffusion model downloads.

It proves that the Forge 3D generation code path executes, optimizes, and
writes a non-empty output file.
"""

from __future__ import annotations

import pytest
from typing import Any

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

from kagami.forge.modules.generation.gaussian_splatting import (
    Gaussian3D,
    GaussianCloud,
    GaussianSplattingConfig,
    GenerationMode,
    GsgenGenerator,
    DecompDreamerGenerator,
    Unified3DGenerator,
)


@pytest.mark.asyncio
async def test_gsgen_generator_generates_ply(tmp_path: Any, monkeypatch: Any) -> None:
    # Ensure the generator does not attempt to download/load Stable Diffusion.
    monkeypatch.setenv("KAGAMI_TEST_MODE", "1")

    # Deterministic (the generator uses numpy.random for initialization).
    np.random.seed(0)

    cfg = GaussianSplattingConfig(
        mode=GenerationMode.TEXT_TO_3D,
        num_gaussians=64,
        num_iterations=5,
        export_mesh=False,
        densify_interval=10**9,  # effectively disable densification
        device="cpu",
    )

    gen = GsgenGenerator(cfg)
    gen._output_dir = tmp_path / "gsgen"
    gen._output_dir.mkdir(parents=True, exist_ok=True)

    await gen.initialize()
    result = await gen.generate(
        prompt="a small red cube",
        num_iterations=5,
        output_name="test_cube",
    )

    assert result.success is True
    assert result.cloud is not None
    assert result.num_gaussians > 0
    assert result.iterations == 5
    assert result.mesh_path is None

    assert isinstance(result.output_path, str)
    out_path = Path(result.output_path)
    assert out_path.exists()
    assert out_path.stat().st_size > 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_gsgen_generator_initialization(tmp_path: Any, monkeypatch: Any) -> None:
    """Test GsgenGenerator initialization."""
    monkeypatch.setenv("KAGAMI_TEST_MODE", "1")

    cfg = GaussianSplattingConfig(device="cpu")
    gen = GsgenGenerator(cfg)

    assert not gen._initialized
    assert gen._diffusion_model is None
    assert gen._device == "cpu"

    await gen.initialize()
    assert gen._initialized


@pytest.mark.unit
def test_gaussian_cloud_properties():
    """Test GaussianCloud property accessors."""
    gaussians = [
        Gaussian3D(
            position=np.array([0.1, 0.2, 0.3]),
            color=np.array([1.0, 0.0, 0.0]),
            opacity=0.8,
            scale=np.array([0.05, 0.05, 0.05]),
            rotation=np.array([1, 0, 0, 0]),
        ),
        Gaussian3D(
            position=np.array([0.4, 0.5, 0.6]),
            color=np.array([0.0, 1.0, 0.0]),
            opacity=0.9,
            scale=np.array([0.04, 0.04, 0.04]),
            rotation=np.array([1, 0, 0, 0]),
        ),
    ]

    cloud = GaussianCloud(gaussians=gaussians)

    assert cloud.num_gaussians == 2
    assert cloud.get_positions().shape == (2, 3)
    assert cloud.get_colors().shape == (2, 3)
    assert cloud.get_opacities().shape == (2,)
    assert cloud.get_scales().shape == (2, 3)
    assert cloud.get_rotations().shape == (2, 4)


@pytest.mark.unit
def test_gaussian_3d_to_dict():
    """Test Gaussian3D serialization."""
    g = Gaussian3D(
        position=np.array([1.0, 2.0, 3.0]),
        color=np.array([0.5, 0.5, 0.5]),
        opacity=0.7,
        scale=np.array([0.1, 0.1, 0.1]),
        rotation=np.array([1, 0, 0, 0]),
    )

    d = g.to_dict()
    assert "position" in d
    assert "color" in d
    assert "opacity" in d
    assert d["opacity"] == 0.7
    assert len(d["position"]) == 3


@pytest.mark.unit
@pytest.mark.asyncio
async def test_gsgen_initialize_gaussians(monkeypatch: Any) -> None:
    """Test Gaussian initialization."""
    monkeypatch.setenv("KAGAMI_TEST_MODE", "1")
    np.random.seed(42)

    cfg = GaussianSplattingConfig(num_gaussians=100, device="cpu")
    gen = GsgenGenerator(cfg)

    cloud = gen._initialize_gaussians()

    assert cloud.num_gaussians == 100
    assert all(g.opacity == 0.5 for g in cloud.gaussians)
    assert all(np.array_equal(g.rotation, [1, 0, 0, 0]) for g in cloud.gaussians)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_gsgen_compute_regularization_loss(monkeypatch: Any) -> None:
    """Test regularization loss computation."""
    monkeypatch.setenv("KAGAMI_TEST_MODE", "1")
    import torch

    cfg = GaussianSplattingConfig(device="cpu")
    gen = GsgenGenerator(cfg)
    await gen.initialize()

    positions = torch.randn(10, 3)
    colors = torch.randn(10, 3)
    opacities = torch.randn(10, 1)
    scales = torch.randn(10, 3)

    loss = gen._compute_regularization_loss(positions, colors, opacities, scales)

    assert isinstance(loss, torch.Tensor)
    assert loss.ndim == 0  # scalar


@pytest.mark.unit
@pytest.mark.asyncio
async def test_gsgen_densify_and_prune(monkeypatch: Any) -> None:
    """Test densification and pruning."""
    monkeypatch.setenv("KAGAMI_TEST_MODE", "1")
    import torch

    cfg = GaussianSplattingConfig(device="cpu", prune_opacity_threshold=0.5)
    gen = GsgenGenerator(cfg)
    await gen.initialize()

    # Create test tensors with some low opacity values
    positions = torch.randn(10, 3, requires_grad=True)
    colors = torch.randn(10, 3, requires_grad=True)
    opacities = torch.cat([torch.ones(5, 1) * 0.8, torch.ones(5, 1) * 0.2], dim=0)  # 5 high, 5 low
    opacities.requires_grad = True
    scales = torch.randn(10, 3, requires_grad=True)
    rotations = torch.randn(10, 4, requires_grad=True)

    new_pos, _new_col, new_op, _new_sc, _new_rot = gen._densify_and_prune(
        positions, colors, opacities, scales, rotations
    )

    # Should have pruned low opacity Gaussians
    assert len(new_pos) == 5
    assert all(o > 0.5 for o in new_op.squeeze())


@pytest.mark.unit
@pytest.mark.asyncio
async def test_gsgen_export_mesh_with_empty_grid(tmp_path: Any, monkeypatch: Any) -> None:
    """Test mesh export with empty grid."""
    monkeypatch.setenv("KAGAMI_TEST_MODE", "1")
    np.random.seed(0)

    cfg = GaussianSplattingConfig(device="cpu", export_mesh=True)
    gen = GsgenGenerator(cfg)
    gen._output_dir = tmp_path

    # Create cloud with all zero opacities (empty)
    gaussians = [
        Gaussian3D(
            position=np.array([0, 0, 0]),
            color=np.array([1, 1, 1]),
            opacity=0.0,
            scale=np.array([0.01, 0.01, 0.01]),
            rotation=np.array([1, 0, 0, 0]),
        )
    ]
    cloud = GaussianCloud(gaussians=gaussians)

    output_path = tmp_path / "test.obj"
    await gen._export_mesh(cloud, output_path)

    # Should handle empty grid gracefully (may not create file or create empty file)
    # Just verify no crash


@pytest.mark.unit
@pytest.mark.asyncio
async def test_decomp_dreamer_initialization(monkeypatch: Any) -> None:
    """Test DecompDreamerGenerator initialization."""
    monkeypatch.setenv("KAGAMI_TEST_MODE", "1")

    cfg = GaussianSplattingConfig(device="cpu")
    gen = DecompDreamerGenerator(cfg)

    assert not gen._initialized
    assert gen._gsgen is not None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_decomp_dreamer_extract_objects():
    """Test object extraction from prompt."""
    cfg = GaussianSplattingConfig(device="cpu")
    gen = DecompDreamerGenerator(cfg)

    # Test with "and"
    prompt = "a red cube and a blue sphere"
    objects = gen._extract_objects_from_prompt(prompt)
    assert len(objects) > 1
    assert "cube" in objects[0].lower() or "sphere" in objects[1].lower()

    # Test with single object
    prompt = "a green pyramid"
    objects = gen._extract_objects_from_prompt(prompt)
    assert len(objects) >= 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_decomp_dreamer_compose_scene():
    """Test scene composition."""
    cfg = GaussianSplattingConfig(device="cpu")
    gen = DecompDreamerGenerator(cfg)

    # Create two simple clouds
    cloud1 = GaussianCloud(
        gaussians=[
            Gaussian3D(
                position=np.array([0, 0, 0]),
                color=np.array([1, 0, 0]),
                opacity=0.5,
                scale=np.array([0.1, 0.1, 0.1]),
                rotation=np.array([1, 0, 0, 0]),
            )
        ]
    )
    cloud2 = GaussianCloud(
        gaussians=[
            Gaussian3D(
                position=np.array([0, 0, 0]),
                color=np.array([0, 1, 0]),
                opacity=0.5,
                scale=np.array([0.1, 0.1, 0.1]),
                rotation=np.array([1, 0, 0, 0]),
            )
        ]
    )

    composed = gen._compose_scene([cloud1, cloud2])

    assert composed.num_gaussians == 2
    # Positions should be offset
    positions = composed.get_positions()
    assert not np.allclose(positions[0], positions[1])


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unified_3d_generator_detect_mode():
    """Test mode detection."""
    cfg = GaussianSplattingConfig(device="cpu")
    gen = Unified3DGenerator(cfg)

    # Single object
    assert gen._detect_mode("a red cube") == GenerationMode.TEXT_TO_3D

    # Multi-object
    assert gen._detect_mode("a cube and a sphere") == GenerationMode.MULTI_OBJECT
    assert gen._detect_mode("scene with multiple objects") == GenerationMode.MULTI_OBJECT
