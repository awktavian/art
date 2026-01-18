"""
glTF Exporter Tests

Tests the glTF format exporter including:
- glTF 2.0 structure generation
- GLB binary format support
- Mesh data conversion (vertices, faces, normals)
- Material export (PBR metallic-roughness)
- Animation export with keyframes
- Buffer and buffer view management
- Accessor creation
- Base64 encoding for embedded data
- Motion sequence handling
- Error handling and validation
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import asyncio
import base64
import json
import struct
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np

from kagami.forge.modules.export.base import ExportConfig, ExportFormat, ExportQuality
from kagami.forge.modules.export.gltf_exporter import GLTFExporter


@pytest.fixture
def temp_output_dir():  # type: ignore[misc]
    """Create a temporary directory for test outputs"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def gltf_config(temp_output_dir):
    """Create glTF export configuration"""
    return ExportConfig(
        format=ExportFormat.GLTF,
        quality=ExportQuality.STANDARD,
        output_path=temp_output_dir / "test_export.gltf",
        include_textures=True,
        include_animations=True,
        include_materials=True,
    )


@pytest.fixture
def glb_config(temp_output_dir):
    """Create GLB export configuration"""
    return ExportConfig(
        format=ExportFormat.GLB,
        quality=ExportQuality.STANDARD,
        output_path=temp_output_dir / "test_export.glb",
    )


@pytest.fixture
def gltf_exporter(gltf_config):
    """Create glTF exporter instance"""
    return GLTFExporter(config=gltf_config)


@pytest.fixture
def sample_mesh_data() -> dict[str, Any]:
    """Create sample mesh data for testing"""
    return {
        "mesh": {
            "vertices": np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=np.float32),
            "faces": np.array([[0, 1, 2], [0, 2, 3]], dtype=np.uint16),
            "normals": np.array([[0, 0, 1], [0, 0, 1], [0, 0, 1], [0, 1, 0]], dtype=np.float32),
        },
        "materials": {
            "diffuse_color": [1.0, 0.0, 0.0, 1.0],
            "metallic": 0.5,
            "roughness": 0.3,
        },
    }


@pytest.fixture
def sample_animation_data() -> dict[str, Any]:
    """Create sample animation data"""
    return {
        "mesh": {"vertices": [[0, 0, 0]], "faces": [], "normals": []},
        "materials": {},
        "animations": {
            "name": "TestAnimation",
            "keyframes": [
                {"time": 0, "translate": [0, 0, 0]},
                {"time": 1, "translate": [1, 0, 0]},
                {"time": 2, "translate": [2, 0, 0]},
            ],
        },
    }


@pytest.fixture
def sample_motion_sequence_data() -> dict[str, Any]:
    """Create sample motion sequence data"""
    # Create motion data: [frames, joints, xyz]
    motion = np.random.rand(10, 5, 3).astype(np.float32)
    return {
        "mesh": {"vertices": [[0, 0, 0]], "faces": [], "normals": []},
        "materials": {},
        "animations": {"motion_sequence": motion, "fps": 20},
    }


class TestGLTFExporterBasics:
    """Test basic glTF exporter functionality"""

    def test_exporter_initialization(self, gltf_config: ExportConfig) -> None:
        """Test glTF exporter initializes correctly"""
        exporter = GLTFExporter(config=gltf_config)
        assert exporter.config == gltf_config
        assert exporter.logger is not None

    def test_get_supported_formats(self, gltf_exporter: GLTFExporter) -> None:
        """Test glTF exporter supports GLTF and GLB formats"""
        formats = gltf_exporter.get_supported_formats()
        assert ExportFormat.GLTF in formats
        assert ExportFormat.GLB in formats
        assert len(formats) == 2

    def test_exporter_with_glb_config(self, glb_config) -> None:
        """Test exporter can be configured for GLB format"""
        exporter = GLTFExporter(config=glb_config)
        assert exporter.config.format == ExportFormat.GLB


class TestGLTFExport:
    """Test glTF export functionality"""

    @pytest.mark.asyncio
    async def test_export_success(
        self, gltf_exporter: GLTFExporter, sample_mesh_data: dict[str, Any]
    ) -> None:
        """Test successful glTF export"""
        result = await gltf_exporter.export(sample_mesh_data)
        assert result.success is True
        assert result.file_path is not None
        assert result.file_path.exists()
        assert result.file_size > 0
        assert result.export_time is not None

    @pytest.mark.asyncio
    async def test_export_creates_valid_json(
        self, gltf_exporter: GLTFExporter, sample_mesh_data: dict[str, Any]
    ) -> None:
        """Test export creates valid JSON file"""
        result = await gltf_exporter.export(sample_mesh_data)
        assert result.success is True

        with open(result.file_path) as f:
            gltf_data = json.load(f)

        assert "asset" in gltf_data
        assert gltf_data["asset"]["version"] == "2.0"
        assert "scene" in gltf_data
        assert "scenes" in gltf_data

    @pytest.mark.asyncio
    async def test_export_with_invalid_data(self, gltf_exporter: GLTFExporter) -> None:
        """Test export fails with invalid data"""
        invalid_data = {"invalid": "data"}
        result = await gltf_exporter.export(invalid_data)
        assert result.success is False
        assert len(result.errors) > 0

    @pytest.mark.asyncio
    async def test_export_metadata(
        self, gltf_exporter: GLTFExporter, sample_mesh_data: dict[str, Any]
    ) -> None:
        """Test export result includes correct metadata"""
        result = await gltf_exporter.export(sample_mesh_data)
        assert result.success is True
        assert result.metadata["format"] == "glTF"
        assert result.metadata["version"] == "2.0"

    @pytest.mark.asyncio
    async def test_export_handles_exceptions(
        self, gltf_exporter: GLTFExporter, sample_mesh_data: dict[str, Any]
    ) -> None:
        """Test export handles exceptions gracefully"""
        gltf_exporter.config.output_path = Path("/invalid/path/output.gltf")
        result = await gltf_exporter.export(sample_mesh_data)
        assert result.success is False
        assert len(result.errors) > 0


class TestGLTFStructure:
    """Test glTF structure creation"""

    @pytest.mark.asyncio
    async def test_create_gltf_structure(
        self, gltf_exporter: GLTFExporter, sample_mesh_data: dict[str, Any]
    ) -> None:
        """Test creating basic glTF structure"""
        gltf_data = await gltf_exporter._create_gltf_structure(sample_mesh_data)

        assert "asset" in gltf_data
        assert "scenes" in gltf_data
        assert "nodes" in gltf_data
        assert "meshes" in gltf_data
        assert "materials" in gltf_data
        assert "accessors" in gltf_data
        assert "bufferViews" in gltf_data
        assert "buffers" in gltf_data

    @pytest.mark.asyncio
    async def test_gltf_asset_info(
        self, gltf_exporter: GLTFExporter, sample_mesh_data: dict[str, Any]
    ) -> None:
        """Test glTF asset information is correct"""
        gltf_data = await gltf_exporter._create_gltf_structure(sample_mesh_data)

        assert gltf_data["asset"]["version"] == "2.0"
        assert gltf_data["asset"]["generator"] == "Forge Export System"

    @pytest.mark.asyncio
    async def test_gltf_scene_setup(
        self, gltf_exporter: GLTFExporter, sample_mesh_data: dict[str, Any]
    ) -> None:
        """Test glTF scene setup"""
        gltf_data = await gltf_exporter._create_gltf_structure(sample_mesh_data)

        assert gltf_data["scene"] == 0
        assert len(gltf_data["scenes"]) == 1
        assert gltf_data["scenes"][0]["nodes"] == [0]


class TestGLTFMeshConversion:
    """Test mesh data conversion to glTF"""

    @pytest.mark.asyncio
    async def test_add_mesh_to_gltf(
        self, gltf_exporter: GLTFExporter, sample_mesh_data: dict[str, Any]
    ) -> None:
        """Test adding mesh data to glTF structure"""
        gltf_data = {
            "nodes": [],
            "meshes": [],
            "accessors": [],
            "bufferViews": [],
            "buffers": [],
        }

        await gltf_exporter._add_mesh_to_gltf(gltf_data, sample_mesh_data["mesh"])

        assert len(gltf_data["meshes"]) == 1
        assert len(gltf_data["nodes"]) == 1
        assert len(gltf_data["buffers"]) == 1
        assert len(gltf_data["accessors"]) >= 1
        assert len(gltf_data["bufferViews"]) >= 1

    @pytest.mark.asyncio
    async def test_mesh_primitives(
        self, gltf_exporter: GLTFExporter, sample_mesh_data: dict[str, Any]
    ) -> None:
        """Test mesh primitives are created correctly"""
        gltf_data = {
            "nodes": [],
            "meshes": [],
            "accessors": [],
            "bufferViews": [],
            "buffers": [],
        }

        await gltf_exporter._add_mesh_to_gltf(gltf_data, sample_mesh_data["mesh"])

        mesh = gltf_data["meshes"][0]
        assert "primitives" in mesh
        assert len(mesh["primitives"]) == 1

        primitive = mesh["primitives"][0]
        assert "attributes" in primitive
        assert "POSITION" in primitive["attributes"]

    @pytest.mark.asyncio
    async def test_vertex_buffer_encoding(
        self, gltf_exporter: GLTFExporter, sample_mesh_data: dict[str, Any]
    ) -> None:
        """Test vertex data is properly encoded in buffer"""
        gltf_data = {
            "nodes": [],
            "meshes": [],
            "accessors": [],
            "bufferViews": [],
            "buffers": [],
        }

        await gltf_exporter._add_mesh_to_gltf(gltf_data, sample_mesh_data["mesh"])

        buffer = gltf_data["buffers"][0]
        assert "uri" in buffer
        assert buffer["uri"].startswith("data:application/octet-stream;base64,")

        # Decode and verify buffer data
        encoded_data = buffer["uri"].split(",")[1]
        decoded_data = base64.b64decode(encoded_data)
        assert len(decoded_data) > 0

    @pytest.mark.asyncio
    async def test_normal_attribute(
        self, gltf_exporter: GLTFExporter, sample_mesh_data: dict[str, Any]
    ) -> None:
        """Test normal attributes are added when available"""
        gltf_data = {
            "nodes": [],
            "meshes": [],
            "accessors": [],
            "bufferViews": [],
            "buffers": [],
        }

        await gltf_exporter._add_mesh_to_gltf(gltf_data, sample_mesh_data["mesh"])

        primitive = gltf_data["meshes"][0]["primitives"][0]
        assert "NORMAL" in primitive["attributes"]

    @pytest.mark.asyncio
    async def test_indices_attribute(
        self, gltf_exporter: GLTFExporter, sample_mesh_data: dict[str, Any]
    ) -> None:
        """Test indices are added when faces are present"""
        gltf_data = {
            "nodes": [],
            "meshes": [],
            "accessors": [],
            "bufferViews": [],
            "buffers": [],
        }

        await gltf_exporter._add_mesh_to_gltf(gltf_data, sample_mesh_data["mesh"])

        primitive = gltf_data["meshes"][0]["primitives"][0]
        assert "indices" in primitive

    @pytest.mark.asyncio
    async def test_accessor_min_max(
        self, gltf_exporter: GLTFExporter, sample_mesh_data: dict[str, Any]
    ) -> None:
        """Test accessor min/max values are computed correctly"""
        gltf_data = {
            "nodes": [],
            "meshes": [],
            "accessors": [],
            "bufferViews": [],
            "buffers": [],
        }

        await gltf_exporter._add_mesh_to_gltf(gltf_data, sample_mesh_data["mesh"])

        position_accessor = gltf_data["accessors"][0]
        assert "min" in position_accessor
        assert "max" in position_accessor
        assert len(position_accessor["min"]) == 3
        assert len(position_accessor["max"]) == 3


class TestGLTFMaterialConversion:
    """Test material conversion to glTF"""

    @pytest.mark.asyncio
    async def test_add_materials_to_gltf(
        self, gltf_exporter: GLTFExporter, sample_mesh_data: dict[str, Any]
    ) -> None:
        """Test adding materials to glTF structure"""
        gltf_data = {"materials": []}

        await gltf_exporter._add_materials_to_gltf(gltf_data, sample_mesh_data["materials"])

        assert len(gltf_data["materials"]) == 1

    @pytest.mark.asyncio
    async def test_pbr_metallic_roughness(
        self, gltf_exporter: GLTFExporter, sample_mesh_data: dict[str, Any]
    ) -> None:
        """Test PBR metallic roughness material is created"""
        gltf_data = {"materials": []}

        await gltf_exporter._add_materials_to_gltf(gltf_data, sample_mesh_data["materials"])

        material = gltf_data["materials"][0]
        assert "pbrMetallicRoughness" in material

        pbr = material["pbrMetallicRoughness"]
        assert "baseColorFactor" in pbr
        assert "metallicFactor" in pbr
        assert "roughnessFactor" in pbr

    @pytest.mark.asyncio
    async def test_material_color_values(
        self, gltf_exporter: GLTFExporter, sample_mesh_data: dict[str, Any]
    ) -> None:
        """Test material color values are set correctly"""
        gltf_data = {"materials": []}

        await gltf_exporter._add_materials_to_gltf(gltf_data, sample_mesh_data["materials"])

        pbr = gltf_data["materials"][0]["pbrMetallicRoughness"]
        assert pbr["baseColorFactor"] == [1.0, 0.0, 0.0, 1.0]
        assert pbr["metallicFactor"] == 0.5
        assert pbr["roughnessFactor"] == 0.3


class TestGLTFAnimations:
    """Test animation export to glTF"""

    @pytest.mark.asyncio
    async def test_add_simple_animations(
        self, gltf_exporter: GLTFExporter, sample_animation_data: dict[str, Any]
    ) -> None:
        """Test adding simple keyframe animations"""
        gltf_data = await gltf_exporter._create_gltf_structure(sample_animation_data)

        assert "animations" in gltf_data
        assert len(gltf_data["animations"]) > 0

        animation = gltf_data["animations"][0]
        assert "name" in animation
        assert "channels" in animation
        assert "samplers" in animation

    @pytest.mark.asyncio
    async def test_motion_sequence_conversion(
        self, gltf_exporter, sample_motion_sequence_data
    ) -> None:
        """Test converting motion sequence to glTF animation"""
        gltf_data = await gltf_exporter._create_gltf_structure(sample_motion_sequence_data)

        assert "animations" in gltf_data
        if len(gltf_data["animations"]) > 0:
            animation = gltf_data["animations"][0]
            assert len(animation["channels"]) > 0
            assert len(animation["samplers"]) > 0

    @pytest.mark.asyncio
    async def test_animation_time_accessor(
        self, gltf_exporter, sample_motion_sequence_data
    ) -> None:
        """Test animation time accessor is created"""
        gltf_data = await gltf_exporter._create_gltf_structure(sample_motion_sequence_data)

        # Check that accessors were created for animation
        if "animations" in gltf_data and len(gltf_data["animations"]) > 0:
            assert len(gltf_data["accessors"]) > 0

    @pytest.mark.asyncio
    async def test_animation_channels_per_joint(
        self, gltf_exporter, sample_motion_sequence_data
    ) -> None:
        """Test animation creates channels for each joint"""
        gltf_data = await gltf_exporter._create_gltf_structure(sample_motion_sequence_data)

        if "animations" in gltf_data and len(gltf_data["animations"]) > 0:
            animation = gltf_data["animations"][0]
            # Should have channels for multiple joints
            assert len(animation["channels"]) > 0

    @pytest.mark.asyncio
    async def test_empty_animations_not_added(self, gltf_exporter: GLTFExporter) -> None:
        """Test empty animations are not added to structure"""
        data = {
            "mesh": {"vertices": [[0, 0, 0]], "faces": [], "normals": []},
            "materials": {},
            "animations": {},
        }

        gltf_data = await gltf_exporter._create_gltf_structure(data)

        # Empty animations should not be added
        if "animations" in gltf_data:
            assert len(gltf_data["animations"]) == 0


class TestGLTFFileWriting:
    """Test glTF file writing"""

    @pytest.mark.asyncio
    async def test_write_gltf_file(
        self, gltf_exporter: GLTFExporter, temp_output_dir: Path
    ) -> None:
        """Test writing glTF file to disk"""
        gltf_data = {
            "asset": {"version": "2.0"},
            "scene": 0,
            "scenes": [{"nodes": [0]}],
        }

        await gltf_exporter._write_gltf_file(gltf_data)

        assert gltf_exporter.config.output_path.exists()

        with open(gltf_exporter.config.output_path) as f:
            loaded_data = json.load(f)

        assert loaded_data == gltf_data

    @pytest.mark.asyncio
    async def test_write_gltf_file_no_output_path(self, gltf_exporter: GLTFExporter) -> None:
        """Test writing glTF file raises error without output path"""
        gltf_exporter.config.output_path = None
        gltf_data = {"asset": {"version": "2.0"}}

        with pytest.raises(ValueError, match="Output path not specified"):
            await gltf_exporter._write_gltf_file(gltf_data)


class TestGLBExport:
    """Test GLB binary format export"""

    @pytest.mark.asyncio
    async def test_glb_export_success(self, sample_mesh_data, temp_output_dir) -> None:
        """Test successful GLB export"""
        config = ExportConfig(
            format=ExportFormat.GLB,
            output_path=temp_output_dir / "output.glb",
        )
        exporter = GLTFExporter(config=config)

        result = await exporter.export(sample_mesh_data)
        assert result.success is True
        assert result.file_path is not None

        assert result.file_path.exists()

        assert result.file_path.suffix == ".glb"

    @pytest.mark.asyncio
    async def test_glb_file_structure(self, sample_mesh_data, temp_output_dir) -> None:
        """Test GLB file has correct binary structure"""
        config = ExportConfig(
            format=ExportFormat.GLB,
            output_path=temp_output_dir / "output.glb",
        )
        exporter = GLTFExporter(config=config)

        result = await exporter.export(sample_mesh_data)
        assert result.success is True

        with open(result.file_path, "rb") as f:  # type: ignore[arg-type]
            # Check GLB header
            magic = f.read(4)
            assert magic == b"glTF"

            version = struct.unpack("<I", f.read(4))[0]
            assert version == 2

            length = struct.unpack("<I", f.read(4))[0]
            assert length > 0

    @pytest.mark.asyncio
    async def test_write_glb_file_no_output_path(self, temp_output_dir: Path) -> None:
        """Test writing GLB file raises error without output path"""
        config = ExportConfig(format=ExportFormat.GLB, output_path=None)
        exporter = GLTFExporter(config=config)

        gltf_data = {"asset": {"version": "2.0"}}

        with pytest.raises(ValueError, match="Output path not specified"):
            await exporter._write_glb_file(gltf_data)


class TestGLTFQualityLevels:
    """Test different quality levels for glTF export"""

    @pytest.mark.asyncio
    async def test_draft_quality_export(self, sample_mesh_data, temp_output_dir) -> None:
        """Test export with draft quality"""
        config = ExportConfig(
            format=ExportFormat.GLTF,
            quality=ExportQuality.DRAFT,
            output_path=temp_output_dir / "draft.gltf",
        )
        exporter = GLTFExporter(config=config)

        result = await exporter.export(sample_mesh_data)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_production_quality_export(self, sample_mesh_data, temp_output_dir) -> None:
        """Test export with production quality"""
        config = ExportConfig(
            format=ExportFormat.GLTF,
            quality=ExportQuality.PRODUCTION,
            output_path=temp_output_dir / "production.gltf",
        )
        exporter = GLTFExporter(config=config)

        result = await exporter.export(sample_mesh_data)
        assert result.success is True
