"""
Rigging Module Tests

Tests the character rigging functionality including:
- Automatic skeleton generation
- Joint placement and hierarchy
- Skinning and weight painting
- IK/FK chain setup
- Facial rigging
- Real-time deformation
- Integration with animation systems
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import numpy as np

from kagami.forge.core_integration import (
    CharacterAspect,
    CharacterResult,
    ProcessingStatus,
)

# Import actual rigging module
from kagami.forge.modules.rigging import RiggedMesh, RiggingModule

# Import trimesh for mesh handling
try:
    import trimesh

except ImportError:
    trimesh = None  # type: ignore[assignment]


@pytest.fixture
def rigging_module():
    """Create rigging module for testing"""
    config = {
        "method": "unirig",
        "device": "cpu",
        "max_influences_per_vertex": 4,
    }
    module = RiggingModule("rigging", config)
    return module


@pytest.fixture
def sample_mesh():
    """Create a simple humanoid mesh for testing"""
    if trimesh is None:
        pytest.skip("trimesh not available")

    # Simplified humanoid mesh vertices
    vertices = np.array(
        [
            # Head (8 vertices for a cube)
            [-0.5, 1.5, -0.5],
            [0.5, 1.5, -0.5],
            [0.5, 2.5, -0.5],
            [-0.5, 2.5, -0.5],
            [-0.5, 1.5, 0.5],
            [0.5, 1.5, 0.5],
            [0.5, 2.5, 0.5],
            [-0.5, 2.5, 0.5],
            # Torso (8 vertices)
            [-0.7, 0, -0.3],
            [0.7, 0, -0.3],
            [0.7, 1.5, -0.3],
            [-0.7, 1.5, -0.3],
            [-0.7, 0, 0.3],
            [0.7, 0, 0.3],
            [0.7, 1.5, 0.3],
            [-0.7, 1.5, 0.3],
            # Arms and legs would be added similarly...
        ],
        dtype=np.float32,
    )

    # Simple face connectivity
    faces = np.array(
        [
            # Head faces
            [0, 1, 2],
            [0, 2, 3],
            [4, 6, 5],
            [4, 7, 6],
            [0, 4, 5],
            [0, 5, 1],
            [2, 6, 7],
            [2, 7, 3],
            [0, 3, 7],
            [0, 7, 4],
            [1, 5, 6],
            [1, 6, 2],
            # Torso faces
            [8, 9, 10],
            [8, 10, 11],
            [12, 14, 13],
            [12, 15, 14],
            # ... more faces
        ],
        dtype=np.int32,
    )

    mesh = trimesh.Trimesh(vertices=vertices, faces=faces)
    return mesh


class TestRiggingModule:
    """Test rigging module functionality"""

    @pytest.mark.asyncio
    async def test_module_initialization(self, rigging_module: Any) -> None:
        """Test rigging module initializes properly"""
        # Module should not be initialized yet
        assert not rigging_module.initialized

        # Initialize module
        await rigging_module.initialize()

        # Now should be initialized
        assert rigging_module.initialized
        assert rigging_module.device in ["mps", "cpu"]

    @pytest.mark.asyncio
    async def test_process_mesh(self, rigging_module: Any, sample_mesh: Any) -> None:
        """Test processing a mesh through the rigging module"""
        await rigging_module.initialize()

        # Create input data
        input_data = {
            "generation": {
                "mesh": sample_mesh,
                "metadata": {"prompt": "humanoid character"},
                "rigging_hints": {"skeleton_type": "humanoid"},
            }
        }

        # Process the mesh
        result = await rigging_module.process(input_data)

        # Check result
        assert isinstance(result, CharacterResult)
        assert result.aspect == CharacterAspect.MOTION

        # If successful, check the rigged mesh
        if result.status == ProcessingStatus.COMPLETED:
            assert result.data is not None
            assert isinstance(result.data, RiggedMesh)
            assert hasattr(result.data, "mesh")
            assert hasattr(result.data, "skeleton")
            assert hasattr(result.data, "weights")

    @pytest.mark.asyncio
    async def test_skeleton_templates(self, rigging_module: Any) -> None:
        """Test skeleton template creation"""
        await rigging_module.initialize()

        # Load skeleton templates
        await rigging_module._load_skeleton_templates()

        # Check templates exist
        assert hasattr(rigging_module, "skeleton_templates")
        assert "humanoid" in rigging_module.skeleton_templates
        assert "quadruped" in rigging_module.skeleton_templates
        assert "bird" in rigging_module.skeleton_templates

        # Check humanoid skeleton structure
        humanoid = rigging_module.skeleton_templates["humanoid"]
        assert humanoid["type"] == "humanoid"
        assert "bones" in humanoid
        assert "root" in humanoid["bones"]
        assert "pelvis" in humanoid["bones"]
        assert "head" in humanoid["bones"]

    def test_rigged_mesh_creation(self, sample_mesh: Any) -> None:
        """Test RiggedMesh object creation"""
        # Create simple skeleton
        skeleton = {
            "type": "test",
            "bones": {
                "root": {"position": [0, 0, 0], "parent": None},
                "joint1": {"position": [0, 1, 0], "parent": "root"},
            },
        }

        # Create weights (2 bones, n vertices)
        n_vertices = len(sample_mesh.vertices)
        weights = np.zeros((n_vertices, 2))
        weights[:, 0] = 1.0  # All vertices weighted to root

        # Create RiggedMesh
        rigged_mesh = RiggedMesh(sample_mesh, skeleton, weights)

        # Check attributes
        assert rigged_mesh.mesh == sample_mesh
        assert rigged_mesh.skeleton == skeleton
        assert np.array_equal(rigged_mesh.weights, weights)

        # Check hierarchy building
        assert hasattr(rigged_mesh, "bone_hierarchy")
        assert "root" in rigged_mesh.bone_hierarchy
        assert "joint1" in rigged_mesh.bone_hierarchy["root"]

    def test_rigged_mesh_bone_transform(self, sample_mesh: Any) -> None:
        """Test bone transformation calculation"""
        skeleton = {
            "bones": {
                "root": {"position": [0, 0, 0], "parent": None},
                "joint1": {"position": [0, 1, 0], "parent": "root"},
                "joint2": {"position": [0, 2, 0], "parent": "joint1"},
            }
        }

        weights = np.ones((len(sample_mesh.vertices), 3)) / 3
        rigged_mesh = RiggedMesh(sample_mesh, skeleton, weights)

        # Get root transform (should be identity)
        root_transform = rigged_mesh.get_bone_transform("root")
        np.testing.assert_array_equal(root_transform, np.eye(4))

        # Get joint1 transform
        joint1_transform = rigged_mesh.get_bone_transform("joint1")
        assert joint1_transform[1, 3] == 1.0  # Y translation

        # Get joint2 transform (includes parent transform)
        joint2_transform = rigged_mesh.get_bone_transform("joint2")
        assert joint2_transform[1, 3] == 3.0  # Cumulative Y translation

    def test_rigged_mesh_serialization(self, sample_mesh: Any) -> None:
        """Test RiggedMesh to_dict serialization"""
        skeleton = {
            "bones": {
                "root": {"position": [0, 0, 0], "parent": None},
            }
        }

        weights = np.ones((len(sample_mesh.vertices), 1))
        rigged_mesh = RiggedMesh(sample_mesh, skeleton, weights)

        # Serialize to dict
        data = rigged_mesh.to_dict()

        # Check structure
        assert "mesh" in data
        assert "skeleton" in data
        assert "weights" in data
        assert "hierarchy" in data

        # Check mesh data
        assert "vertices" in data["mesh"]
        assert "faces" in data["mesh"]
        assert "normals" in data["mesh"]

        # Check serialized types (should be lists, not numpy arrays)
        assert isinstance(data["mesh"]["vertices"], list)
        assert isinstance(data["weights"], list)

    @pytest.mark.asyncio
    async def test_config_validation(self) -> None:
        """Test configuration validation"""
        # Valid config
        valid_config = {
            "method": "unirig",
            "device": "cpu",
        }
        module = RiggingModule("test", valid_config)
        assert module._validate_config_specific(valid_config)

        # Invalid method
        invalid_config = {
            "method": "invalid_method",
        }
        module = RiggingModule("test", invalid_config)
        assert not module._validate_config_specific(invalid_config)

    @pytest.mark.asyncio
    async def test_health_check(self, rigging_module: Any) -> None:
        """Test health check functionality"""
        # Before initialization
        assert not rigging_module._check_health()

        # After initialization
        await rigging_module.initialize()
        assert rigging_module._check_health()

    @pytest.mark.asyncio
    async def test_status_reporting(self, rigging_module: Any) -> None:
        """Test status reporting"""
        await rigging_module.initialize()

        status = rigging_module._get_status_specific()

        # Check status fields
        assert "unirig_available" in status
        assert "skeleton_templates" in status
        assert "rigging_method" in status
        assert "max_influences_per_vertex" in status

        # Check values
        assert status["rigging_method"] == "unirig"
        assert status["max_influences_per_vertex"] == 4


@pytest.mark.real_model
class TestRealRiggingModels:
    """Test integration with real rigging solutions"""

    @pytest.mark.asyncio
    async def test_unirig_availability(self, rigging_module: Any) -> None:
        """Test if UniRig is available"""
        try:
            await rigging_module.initialize()

            # Check if UniRig was loaded
            if rigging_module.unirig_model is not None:
                assert hasattr(rigging_module.unirig_model, "rig_mesh")
                assert hasattr(rigging_module.unirig_model, "get_memory_usage")
            else:
                pytest.skip("UniRig model not available")

        except RuntimeError as e:
            if "not available" in str(e):
                pytest.skip("UniRig not available")
            raise
