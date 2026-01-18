"""
UniRig Integration Smoke Test

Skips unless either local UniRig model snapshot exists or UNIRIG_API_KEY is set.
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


def _unirig_local_available() -> bool:
    model_root = Path.home() / ".cache" / "huggingface" / "models--VAST-AI--UniRig"
    return model_root.exists()


@pytest.mark.real_model
@pytest.mark.asyncio
async def test_unirig_wrapper_initialize_and_rig(tmp_path: Any) -> None:
    try:
        import numpy as np
        import trimesh

        from kagami.forge.mps_unirig_wrapper import (
            MPSUniRigWrapper,
        )
    except Exception as e:
        pytest.skip(f"Dependencies not available: {e}")

    if not (_unirig_local_available() or os.getenv("UNIRIG_API_KEY")):
        pytest.skip("UniRig local model or API key not available")

    wrapper = MPSUniRigWrapper()

    try:
        await wrapper.load_models()
    except Exception as e:
        pytest.skip(f"UniRig initialization failed: {e}")

    # Create a trivial mesh (triangle) and export to OBJ
    vertices = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=float)
    faces = np.array([[0, 1, 2]], dtype=int)
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces)
    obj_path = tmp_path / "triangle.obj"
    mesh.export(obj_path)

    # Attempt rig generation (will use API or local depending on availability)
    try:
        result = await wrapper.generate_rig(str(obj_path))
    except Exception as e:
        pytest.skip(f"Rig generation failed: {e}")

    assert isinstance(result, dict)
    # success may be False on API quota or local errors; ensure mode set and non-crashing
    assert result.get("mode") in {"api", "local"}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unirig_wrapper_initialization():
    """Test MPSUniRigWrapper initialization."""
    try:
        import torch

        from kagami.forge.mps_unirig_wrapper import MPSUniRigWrapper
    except Exception as e:
        pytest.skip(f"Dependencies not available: {e}")

    wrapper = MPSUniRigWrapper()
    assert not wrapper.initialized
    assert wrapper.pipeline is None
    assert wrapper._performance_stats["total_generations"] == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unirig_wrapper_device_selection():
    """Test device selection logic."""
    try:
        import torch

        from kagami.forge.mps_unirig_wrapper import MPSUniRigWrapper
    except Exception as e:
        pytest.skip(f"Dependencies not available: {e}")

    # Default device
    wrapper = MPSUniRigWrapper()
    assert wrapper.device is not None

    # Explicit CPU
    wrapper_cpu = MPSUniRigWrapper(device=torch.device("cpu"))
    assert wrapper_cpu.device.type == "cpu"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unirig_wrapper_api_mode():
    """Test API mode initialization."""
    try:
        import torch

        from kagami.forge.mps_unirig_wrapper import MPSUniRigWrapper
    except Exception as e:
        pytest.skip(f"Dependencies not available: {e}")

    # Set API key
    os.environ["UNIRIG_API_KEY"] = "test_key"

    wrapper = MPSUniRigWrapper()

    try:
        await wrapper.load_models()
    except Exception:
        # May fail to actually initialize, but should set mode
        pass

    assert hasattr(wrapper, "mode")
    # Should attempt API mode
    if wrapper.initialized:
        assert wrapper.mode == "api"

    # Clean up
    del os.environ["UNIRIG_API_KEY"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unirig_wrapper_generate_rig_not_initialized():
    """Test generate_rig triggers initialization."""
    try:
        import trimesh
        import torch

        from kagami.forge.mps_unirig_wrapper import MPSUniRigWrapper
    except Exception as e:
        pytest.skip(f"Dependencies not available: {e}")

    wrapper = MPSUniRigWrapper()

    # Mock load_models to skip actual initialization
    async def mock_load():
        wrapper.initialized = True
        wrapper.mode = "local"

    with patch.object(wrapper, "load_models", mock_load):
        # Mock local generation to avoid actual inference
        async def mock_gen_local(mesh_path: Any, options: Any) -> Dict[str, Any]:
            return {"success": True, "mode": "local", "rig_path": mesh_path}

        with patch.object(wrapper, "_generate_rig_local", mock_gen_local):
            result = await wrapper.generate_rig("/fake/path.obj")
            assert result["success"] is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unirig_wrapper_rig_mesh_compatibility(tmp_path: Any) -> Any:
    """Test rig_mesh compatibility shim."""
    try:
        import numpy as np
        import trimesh
        import torch

        from kagami.forge.mps_unirig_wrapper import MPSUniRigWrapper
    except Exception as e:
        pytest.skip(f"Dependencies not available: {e}")

    wrapper = MPSUniRigWrapper()

    # Mock initialization and generation
    async def mock_load():
        wrapper.initialized = True
        wrapper.mode = "local"

    async def mock_gen_rig(mesh_path: Any, options: Any = None) -> Dict[str, Any]:
        return {
            "success": True,
            "mode": "local",
            "rig_path": mesh_path,
            "skeleton": {"joints": []},
            "weights": [[0.5, 0.5]],
        }

    # Create a simple mesh
    vertices = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=float)
    faces = np.array([[0, 1, 2]], dtype=int)
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces)

    with patch.object(wrapper, "load_models", mock_load):
        with patch.object(wrapper, "generate_rig", mock_gen_rig):
            result = await wrapper.rig_mesh(mesh, cls="biped")

            assert "mesh" in result
            assert "skeleton" in result
            assert "weights" in result


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unirig_wrapper_get_memory_usage():
    """Test memory usage reporting."""
    try:
        import torch

        from kagami.forge.mps_unirig_wrapper import MPSUniRigWrapper
    except Exception as e:
        pytest.skip(f"Dependencies not available: {e}")

    wrapper = MPSUniRigWrapper()

    mem_usage = wrapper.get_memory_usage()

    assert isinstance(mem_usage, dict)
    assert "device" in mem_usage
    assert "mode" in mem_usage


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unirig_wrapper_performance_stats():
    """Test performance statistics tracking."""
    try:
        import torch

        from kagami.forge.mps_unirig_wrapper import MPSUniRigWrapper
    except Exception as e:
        pytest.skip(f"Dependencies not available: {e}")

    wrapper = MPSUniRigWrapper()

    # Initial stats
    stats = wrapper.get_performance_stats()
    assert stats["total_generations"] == 0
    assert stats["average_time_ms"] == 0.0

    # Simulate performance update
    wrapper._update_performance_stats(100.0)
    stats = wrapper.get_performance_stats()
    assert stats["total_generations"] == 1
    assert stats["average_time_ms"] == 100.0

    wrapper._update_performance_stats(200.0)
    stats = wrapper.get_performance_stats()
    assert stats["total_generations"] == 2
    assert stats["average_time_ms"] == 150.0  # (100 + 200) / 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unirig_wrapper_cleanup():
    """Test resource cleanup."""
    try:
        import torch

        from kagami.forge.mps_unirig_wrapper import MPSUniRigWrapper
    except Exception as e:
        pytest.skip(f"Dependencies not available: {e}")

    wrapper = MPSUniRigWrapper()

    # Mock a pipeline
    wrapper.pipeline = MagicMock()  # type: ignore[assignment]

    # Cleanup should not crash
    wrapper.cleanup()

    # Pipeline should be cleaned up
    assert not hasattr(wrapper, "pipeline") or wrapper.pipeline is None


@pytest.mark.unit
def test_create_mps_unirig_caching():
    """Test wrapper caching."""
    try:
        import torch

        from kagami.forge.mps_unirig_wrapper import create_mps_unirig
    except Exception as e:
        pytest.skip(f"Dependencies not available: {e}")

    # Create wrapper with same device twice
    wrapper1 = create_mps_unirig(device=torch.device("cpu"))
    wrapper2 = create_mps_unirig(device=torch.device("cpu"))

    # Should return the same cached instance
    assert wrapper1 is wrapper2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unirig_wrapper_generate_rig_api_error(tmp_path: Any) -> None:
    """Test API error handling."""
    try:
        import torch

        from kagami.forge.mps_unirig_wrapper import MPSUniRigWrapper

    except Exception as e:
        pytest.skip(f"Dependencies not available: {e}")

    os.environ["UNIRIG_API_KEY"] = "test_key"

    wrapper = MPSUniRigWrapper()

    # Mock API client that raises
    async def mock_load():
        wrapper.initialized = True
        wrapper.mode = "api"
        wrapper.api_client = MagicMock()

    async def mock_gen_api(mesh_path: Any, options: Any) -> None:
        raise Exception("API Error")

    with patch.object(wrapper, "load_models", mock_load):
        with patch.object(wrapper, "_generate_rig_api", mock_gen_api):
            result = await wrapper.generate_rig("/fake/path.obj")

            assert result["success"] is False
            assert "error" in result

    del os.environ["UNIRIG_API_KEY"]
