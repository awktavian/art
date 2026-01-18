"""
FBX Exporter Tests

Tests the FBX format exporter including:
- FBX binary format generation
- FBX 7.4 structure
- Mesh data conversion (vertices, polygon indices, normals)
- Material conversion (diffuse, specular, ambient)
- Animation export with keyframes and FPS
- Binary header writing
- Object data serialization
- Numpy integration (with and without numpy)
- Error handling and validation
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import struct
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from kagami.forge.modules.export.base import ExportConfig, ExportFormat, ExportQuality
from kagami.forge.modules.export.fbx_exporter import FBXExporter


@pytest.fixture
def temp_output_dir():  # type: ignore[misc]
    """Create a temporary directory for test outputs"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def fbx_config(temp_output_dir):
    """Create FBX export configuration"""
    return ExportConfig(
        format=ExportFormat.FBX,
        quality=ExportQuality.STANDARD,
        output_path=temp_output_dir / "test_export.fbx",
        include_textures=True,
        include_animations=True,
        include_materials=True,
        animation_fps=30,
    )


@pytest.fixture
def fbx_exporter(fbx_config):
    """Create FBX exporter instance"""
    return FBXExporter(config=fbx_config)


@pytest.fixture
def sample_mesh_data() -> dict[str, Any]:
    """Create sample mesh data for testing"""
    return {
        "mesh": {
            "vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 1, 0]],
            "faces": [[0, 1, 2], [1, 3, 2]],
            "normals": [[0, 0, 1], [0, 0, 1], [0, 0, 1], [0, 0, 1]],
        },
        "materials": {
            "diffuse_color": [1.0, 0.0, 0.0],
            "specular_color": [1.0, 1.0, 1.0],
            "ambient_color": [0.1, 0.1, 0.1],
        },
    }


@pytest.fixture
def sample_animation_data() -> dict[str, Any]:
    """Create sample animation data"""
    return {
        "mesh": {"vertices": [[0, 0, 0]], "faces": [], "normals": []},
        "materials": {},
        "animations": {
            "keyframes": [
                {"time": 0, "translate": [0, 0, 0]},
                {"time": 1, "translate": [1, 0, 0]},
                {"time": 2, "translate": [2, 0, 0]},
            ],
            "duration": 2.0,
        },
    }


@pytest.fixture
def sample_full_data() -> dict[str, Any]:
    """Create complete data with mesh, materials, and animations"""
    return {
        "mesh": {
            "vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
            "faces": [[0, 1, 2]],
            "normals": [[0, 0, 1], [0, 0, 1], [0, 0, 1]],
        },
        "materials": {
            "diffuse_color": [0.8, 0.2, 0.2],
            "specular_color": [0.9, 0.9, 0.9],
            "ambient_color": [0.05, 0.05, 0.05],
        },
        "animations": {
            "keyframes": [{"time": 0, "translate": [0, 0, 0]}],
            "duration": 1.0,
        },
    }


class TestFBXExporterBasics:
    """Test basic FBX exporter functionality"""

    def test_exporter_initialization(self, fbx_config: ExportConfig) -> None:
        """Test FBX exporter initializes correctly"""
        exporter = FBXExporter(config=fbx_config)
        assert exporter.config == fbx_config
        assert exporter.logger is not None

    def test_get_supported_formats(self, fbx_exporter: FBXExporter) -> None:
        """Test FBX exporter supports FBX format"""
        formats = fbx_exporter.get_supported_formats()
        assert ExportFormat.FBX in formats
        assert len(formats) == 1

    def test_get_status_specific(self, fbx_exporter: FBXExporter) -> None:
        """Test FBX exporter status info"""
        status = fbx_exporter._get_status_specific()
        assert "supported_formats" in status
        assert "output_path" in status
        assert "fbx" in status["supported_formats"]


class TestFBXExport:
    """Test FBX export functionality"""

    @pytest.mark.asyncio
    async def test_export_success(
        self, fbx_exporter: FBXExporter, sample_mesh_data: dict[str, Any]
    ) -> None:
        """Test successful FBX export"""
        result = await fbx_exporter.export(sample_mesh_data)
        assert result.success is True
        assert result.file_path is not None
        assert result.file_path.exists()
        assert result.file_size > 0
        assert result.export_time is not None

    @pytest.mark.asyncio
    async def test_export_creates_binary_file(
        self, fbx_exporter: FBXExporter, sample_mesh_data: dict[str, Any]
    ) -> None:
        """Test export creates binary FBX file"""
        result = await fbx_exporter.export(sample_mesh_data)
        assert result.success is True

        with open(result.file_path, "rb") as f:
            magic = f.read(23)

        # Check FBX magic bytes
        assert magic == b"Kaydara FBX Binary  \x00\x1a\x00"

    @pytest.mark.asyncio
    async def test_export_with_invalid_data(self, fbx_exporter: FBXExporter) -> None:
        """Test export fails with invalid data"""
        invalid_data = {"invalid": "data"}
        result = await fbx_exporter.export(invalid_data)
        assert result.success is False
        assert len(result.errors) > 0

    @pytest.mark.asyncio
    async def test_export_metadata(
        self, fbx_exporter: FBXExporter, sample_mesh_data: dict[str, Any]
    ) -> None:
        """Test export result includes correct metadata"""
        result = await fbx_exporter.export(sample_mesh_data)
        assert result.success is True
        assert result.metadata["format"] == "FBX"
        assert result.metadata["version"] == "7.4"

    @pytest.mark.asyncio
    async def test_export_handles_exceptions(
        self, fbx_exporter: FBXExporter, sample_mesh_data: dict[str, Any]
    ) -> None:
        """Test export handles exceptions gracefully"""
        fbx_exporter.config.output_path = Path("/invalid/path/output.fbx")
        result = await fbx_exporter.export(sample_mesh_data)
        assert result.success is False
        assert len(result.errors) > 0


class TestFBXStructure:
    """Test FBX structure creation"""

    @pytest.mark.asyncio
    async def test_create_fbx_structure(
        self, fbx_exporter: FBXExporter, sample_mesh_data: dict[str, Any]
    ) -> None:
        """Test creating basic FBX structure"""
        fbx_data = await fbx_exporter._create_fbx_structure(sample_mesh_data)

        assert "header" in fbx_data
        assert "objects" in fbx_data
        assert "connections" in fbx_data

    @pytest.mark.asyncio
    async def test_fbx_header_structure(
        self, fbx_exporter: FBXExporter, sample_mesh_data: dict[str, Any]
    ) -> None:
        """Test FBX header is correct"""
        fbx_data = await fbx_exporter._create_fbx_structure(sample_mesh_data)

        header = fbx_data["header"]
        assert "magic" in header
        assert "version" in header
        assert "timestamp" in header
        assert header["magic"] == b"Kaydara FBX Binary  \x00\x1a\x00"
        assert header["version"] == 7400

    @pytest.mark.asyncio
    async def test_fbx_objects_structure(
        self, fbx_exporter: FBXExporter, sample_mesh_data: dict[str, Any]
    ) -> None:
        """Test FBX objects structure"""
        fbx_data = await fbx_exporter._create_fbx_structure(sample_mesh_data)

        objects = fbx_data["objects"]
        assert "geometry" in objects
        assert "materials" in objects
        assert "animations" in objects

    @pytest.mark.asyncio
    async def test_fbx_connections(
        self, fbx_exporter: FBXExporter, sample_mesh_data: dict[str, Any]
    ) -> None:
        """Test FBX connections are created"""
        fbx_data = await fbx_exporter._create_fbx_structure(sample_mesh_data)

        connections = fbx_data["connections"]
        assert len(connections) > 0
        assert all("type" in conn for conn in connections)
        assert all("child" in conn for conn in connections)
        assert all("parent" in conn for conn in connections)

    def test_create_fbx_header(self, fbx_exporter: FBXExporter) -> None:
        """Test FBX header creation"""
        header = fbx_exporter._create_fbx_header()

        assert header["magic"] == b"Kaydara FBX Binary  \x00\x1a\x00"
        assert header["version"] == 7400
        assert "timestamp" in header

    def test_create_fbx_connections(self, fbx_exporter: FBXExporter) -> None:
        """Test FBX connections creation"""
        connections = fbx_exporter._create_fbx_connections()

        assert len(connections) >= 2
        assert any(conn["child"] == "Geometry" for conn in connections)
        assert any(conn["child"] == "Material" for conn in connections)


class TestFBXMeshConversion:
    """Test mesh data conversion to FBX"""

    @pytest.mark.asyncio
    async def test_convert_mesh_to_fbx(
        self, fbx_exporter: FBXExporter, sample_mesh_data: dict[str, Any]
    ) -> None:
        """Test converting mesh data to FBX format"""
        mesh_data = await fbx_exporter._convert_mesh_to_fbx(sample_mesh_data["mesh"])

        assert "vertices" in mesh_data
        assert "polygon_vertex_index" in mesh_data
        assert "normals" in mesh_data

    @pytest.mark.asyncio
    async def test_mesh_vertices_conversion(
        self, fbx_exporter: FBXExporter, sample_mesh_data: dict[str, Any]
    ) -> None:
        """Test mesh vertices are converted correctly"""
        mesh_data = await fbx_exporter._convert_mesh_to_fbx(sample_mesh_data["mesh"])

        vertices = mesh_data["vertices"]
        # Should be array-like (list or numpy array)
        assert hasattr(vertices, "__len__")
        assert len(vertices) > 0

    @pytest.mark.asyncio
    async def test_mesh_faces_conversion(
        self, fbx_exporter: FBXExporter, sample_mesh_data: dict[str, Any]
    ) -> None:
        """Test mesh faces are converted to polygon indices"""
        mesh_data = await fbx_exporter._convert_mesh_to_fbx(sample_mesh_data["mesh"])

        indices = mesh_data["polygon_vertex_index"]
        assert hasattr(indices, "__len__")
        assert len(indices) > 0

    @pytest.mark.asyncio
    async def test_mesh_normals_conversion(
        self, fbx_exporter: FBXExporter, sample_mesh_data: dict[str, Any]
    ) -> None:
        """Test mesh normals are converted correctly"""
        mesh_data = await fbx_exporter._convert_mesh_to_fbx(sample_mesh_data["mesh"])

        normals = mesh_data["normals"]
        assert hasattr(normals, "__len__")
        assert len(normals) > 0

    @pytest.mark.asyncio
    async def test_mesh_empty_data(self, fbx_exporter: FBXExporter) -> None:
        """Test converting empty mesh data"""
        empty_mesh = {"vertices": [], "faces": [], "normals": []}
        mesh_data = await fbx_exporter._convert_mesh_to_fbx(empty_mesh)

        assert "vertices" in mesh_data
        assert "polygon_vertex_index" in mesh_data
        assert "normals" in mesh_data


class TestFBXMaterialConversion:
    """Test material conversion to FBX"""

    @pytest.mark.asyncio
    async def test_convert_materials_to_fbx(
        self, fbx_exporter: FBXExporter, sample_mesh_data: dict[str, Any]
    ) -> None:
        """Test converting materials to FBX format"""
        material_data = await fbx_exporter._convert_materials_to_fbx(sample_mesh_data["materials"])

        assert "diffuse_color" in material_data
        assert "specular_color" in material_data
        assert "ambient_color" in material_data

    @pytest.mark.asyncio
    async def test_material_diffuse_color(
        self, fbx_exporter: FBXExporter, sample_mesh_data: dict[str, Any]
    ) -> None:
        """Test material diffuse color is preserved"""
        material_data = await fbx_exporter._convert_materials_to_fbx(sample_mesh_data["materials"])

        assert material_data["diffuse_color"] == [1.0, 0.0, 0.0]

    @pytest.mark.asyncio
    async def test_material_specular_color(
        self, fbx_exporter: FBXExporter, sample_mesh_data: dict[str, Any]
    ) -> None:
        """Test material specular color is preserved"""
        material_data = await fbx_exporter._convert_materials_to_fbx(sample_mesh_data["materials"])

        assert material_data["specular_color"] == [1.0, 1.0, 1.0]

    @pytest.mark.asyncio
    async def test_material_ambient_color(
        self, fbx_exporter: FBXExporter, sample_mesh_data: dict[str, Any]
    ) -> None:
        """Test material ambient color is preserved"""
        material_data = await fbx_exporter._convert_materials_to_fbx(sample_mesh_data["materials"])

        assert material_data["ambient_color"] == [0.1, 0.1, 0.1]

    @pytest.mark.asyncio
    async def test_material_default_values(self, fbx_exporter: FBXExporter) -> None:
        """Test materials use default values when not specified"""
        empty_materials = {}
        material_data = await fbx_exporter._convert_materials_to_fbx(empty_materials)

        assert "diffuse_color" in material_data
        assert "specular_color" in material_data
        assert "ambient_color" in material_data

    @pytest.mark.asyncio
    async def test_material_partial_data(self, fbx_exporter: FBXExporter) -> None:
        """Test materials with partial data"""
        partial_materials = {"diffuse_color": [0.5, 0.5, 0.5]}
        material_data = await fbx_exporter._convert_materials_to_fbx(partial_materials)

        assert material_data["diffuse_color"] == [0.5, 0.5, 0.5]
        assert "specular_color" in material_data
        assert "ambient_color" in material_data


class TestFBXAnimationConversion:
    """Test animation conversion to FBX"""

    @pytest.mark.asyncio
    async def test_convert_animations_to_fbx(
        self, fbx_exporter: FBXExporter, sample_animation_data: dict[str, Any]
    ) -> None:
        """Test converting animations to FBX format"""
        animation_data = await fbx_exporter._convert_animations_to_fbx(
            sample_animation_data["animations"]
        )

        assert "keyframes" in animation_data
        assert "duration" in animation_data
        assert "fps" in animation_data

    @pytest.mark.asyncio
    async def test_animation_keyframes(
        self, fbx_exporter: FBXExporter, sample_animation_data: dict[str, Any]
    ) -> None:
        """Test animation keyframes are preserved"""
        animation_data = await fbx_exporter._convert_animations_to_fbx(
            sample_animation_data["animations"]
        )

        keyframes = animation_data["keyframes"]
        assert len(keyframes) == 3

    @pytest.mark.asyncio
    async def test_animation_duration(
        self, fbx_exporter: FBXExporter, sample_animation_data: dict[str, Any]
    ) -> None:
        """Test animation duration is preserved"""
        animation_data = await fbx_exporter._convert_animations_to_fbx(
            sample_animation_data["animations"]
        )

        assert animation_data["duration"] == 2.0

    @pytest.mark.asyncio
    async def test_animation_fps_from_config(
        self, fbx_exporter: FBXExporter, sample_animation_data: dict[str, Any]
    ) -> None:
        """Test animation FPS is taken from config"""
        animation_data = await fbx_exporter._convert_animations_to_fbx(
            sample_animation_data["animations"]
        )

        assert animation_data["fps"] == fbx_exporter.config.animation_fps
        assert animation_data["fps"] == 30

    @pytest.mark.asyncio
    async def test_animation_empty_keyframes(self, fbx_exporter: FBXExporter) -> None:
        """Test animations with empty keyframes"""
        empty_animations = {"keyframes": [], "duration": 0.0}
        animation_data = await fbx_exporter._convert_animations_to_fbx(empty_animations)

        assert animation_data["keyframes"] == []
        assert animation_data["duration"] == 0.0

    @pytest.mark.asyncio
    async def test_animation_default_duration(self, fbx_exporter: FBXExporter) -> None:
        """Test animations use default duration when not specified"""
        animations_no_duration = {"keyframes": []}
        animation_data = await fbx_exporter._convert_animations_to_fbx(animations_no_duration)

        assert "duration" in animation_data


class TestFBXFileWriting:
    """Test FBX file writing"""

    @pytest.mark.asyncio
    async def test_write_fbx_file(self, fbx_exporter: FBXExporter, temp_output_dir: Path) -> None:
        """Test writing FBX file to disk"""
        fbx_data = {
            "header": {
                "magic": b"Kaydara FBX Binary  \x00\x1a\x00",
                "version": 7400,
                "timestamp": 0,
            },
            "objects": {
                "geometry": {"vertices": [], "polygon_vertex_index": [], "normals": []},
                "materials": {},
                "animations": {},
            },
        }

        await fbx_exporter._write_fbx_file(fbx_data)

        assert fbx_exporter.config.output_path.exists()

    @pytest.mark.asyncio
    async def test_fbx_file_has_magic_bytes(
        self, fbx_exporter: FBXExporter, temp_output_dir: Path
    ) -> None:
        """Test FBX file starts with correct magic bytes"""
        fbx_data = {
            "header": {
                "magic": b"Kaydara FBX Binary  \x00\x1a\x00",
                "version": 7400,
            },
            "objects": {"geometry": {}, "materials": {}, "animations": {}},
        }

        await fbx_exporter._write_fbx_file(fbx_data)

        with open(fbx_exporter.config.output_path, "rb") as f:
            magic = f.read(23)

        assert magic == b"Kaydara FBX Binary  \x00\x1a\x00"

    @pytest.mark.asyncio
    async def test_fbx_file_has_version(
        self, fbx_exporter: FBXExporter, temp_output_dir: Path
    ) -> None:
        """Test FBX file includes version number"""
        fbx_data = {
            "header": {
                "magic": b"Kaydara FBX Binary  \x00\x1a\x00",
                "version": 7400,
            },
            "objects": {"geometry": {}, "materials": {}, "animations": {}},
        }

        await fbx_exporter._write_fbx_file(fbx_data)

        with open(fbx_exporter.config.output_path, "rb") as f:
            f.read(23)  # Skip magic
            version = struct.unpack("<I", f.read(4))[0]

        assert version == 7400

    @pytest.mark.asyncio
    async def test_write_fbx_file_no_output_path(self, fbx_exporter: FBXExporter) -> None:
        """Test writing FBX file raises error without output path"""
        fbx_exporter.config.output_path = None
        fbx_data = {"header": {}, "objects": {}}

        with pytest.raises(ValueError, match="Output path not specified"):
            await fbx_exporter._write_fbx_file(fbx_data)

    @pytest.mark.asyncio
    async def test_write_fbx_object(self, fbx_exporter: FBXExporter, temp_output_dir: Path) -> None:
        """Test writing individual FBX object"""
        test_file = temp_output_dir / "test.fbx"

        with open(test_file, "wb") as f:
            obj_data = {"vertices": [1, 2, 3]}
            fbx_exporter._write_fbx_object(f, "TestObject", obj_data)

        assert test_file.exists()
        assert test_file.stat().st_size > 0


class TestFBXCompleteExport:
    """Test complete FBX export workflow"""

    @pytest.mark.asyncio
    async def test_complete_export_with_all_data(self, fbx_exporter, sample_full_data) -> None:
        """Test complete export with mesh, materials, and animations"""
        result = await fbx_exporter.export(sample_full_data)

        assert result.success is True
        assert result.file_path.exists()

        # Verify file structure
        with open(result.file_path, "rb") as f:
            magic = f.read(23)
            assert magic == b"Kaydara FBX Binary  \x00\x1a\x00"

    @pytest.mark.asyncio
    async def test_export_file_size_reasonable(
        self, fbx_exporter: FBXExporter, sample_mesh_data: dict[str, Any]
    ) -> None:
        """Test exported file has reasonable size"""
        result = await fbx_exporter.export(sample_mesh_data)

        assert result.success is True
        assert result.file_size > 0
        assert result.file_size < 1_000_000  # Should be less than 1MB for test data


class TestFBXQualityLevels:
    """Test different quality levels for FBX export"""

    @pytest.mark.asyncio
    async def test_draft_quality_export(self, sample_mesh_data, temp_output_dir) -> None:
        """Test export with draft quality"""
        config = ExportConfig(
            format=ExportFormat.FBX,
            quality=ExportQuality.DRAFT,
            output_path=temp_output_dir / "draft.fbx",
        )
        exporter = FBXExporter(config=config)

        result = await exporter.export(sample_mesh_data)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_high_quality_export(self, sample_mesh_data, temp_output_dir) -> None:
        """Test export with high quality"""
        config = ExportConfig(
            format=ExportFormat.FBX,
            quality=ExportQuality.HIGH,
            output_path=temp_output_dir / "high.fbx",
        )
        exporter = FBXExporter(config=config)

        result = await exporter.export(sample_mesh_data)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_production_quality_export(self, sample_mesh_data, temp_output_dir) -> None:
        """Test export with production quality"""
        config = ExportConfig(
            format=ExportFormat.FBX,
            quality=ExportQuality.PRODUCTION,
            output_path=temp_output_dir / "production.fbx",
        )
        exporter = FBXExporter(config=config)

        result = await exporter.export(sample_mesh_data)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_custom_animation_fps(self, sample_animation_data, temp_output_dir) -> None:
        """Test export with custom animation FPS"""
        config = ExportConfig(
            format=ExportFormat.FBX,
            output_path=temp_output_dir / "custom_fps.fbx",
            animation_fps=60,
        )
        exporter = FBXExporter(config=config)

        result = await exporter.export(sample_animation_data)
        assert result.success is True

        # Verify FPS was used
        fbx_data = await exporter._create_fbx_structure(sample_animation_data)
        assert fbx_data["objects"]["animations"]["fps"] == 60
