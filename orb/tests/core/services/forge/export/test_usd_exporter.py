"""
USD Exporter Tests

Tests the USD (Universal Scene Description) format exporter including:
- USDA (ASCII) format generation
- USD stage metadata (upAxis, metersPerUnit, timeCodesPerSecond)
- Mesh data conversion to USD primitives
- Material conversion to UsdPreviewSurface
- Animation export with timeSamples
- Point and face formatting
- Extent calculation
- Material binding
- Error handling and validation
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np

from kagami.forge.modules.export.base import ExportConfig, ExportFormat, ExportQuality
from kagami.forge.modules.export.usd_exporter import USDExporter


@pytest.fixture
def temp_output_dir():  # type: ignore[misc]
    """Create a temporary directory for test outputs"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def usd_config(temp_output_dir):
    """Create USD export configuration"""
    return ExportConfig(
        format=ExportFormat.USD,
        quality=ExportQuality.STANDARD,
        output_path=temp_output_dir / "test_export.usd",
        include_textures=True,
        include_animations=True,
        include_materials=True,
    )


@pytest.fixture
def usd_exporter(usd_config):
    """Create USD exporter instance"""
    return USDExporter(config=usd_config)


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
            "metallic": 0.5,
            "roughness": 0.3,
        },
        "metadata": {"upAxis": "Y", "metersPerUnit": 1.0, "timeCodesPerSecond": 24},
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
                {"time": 2.5, "translate": [2, 1, 0]},
            ]
        },
    }


@pytest.fixture
def sample_metadata_variations() -> list[dict[str, Any]]:
    """Create different metadata variations for testing"""
    return [
        {"upAxis": "Z", "metersPerUnit": 0.01, "timeCodesPerSecond": 30},
        {"upAxis": "Y", "metersPerUnit": 1.0, "timeCodesPerSecond": 60},
        {},  # Empty metadata should use defaults
    ]


class TestUSDExporterBasics:
    """Test basic USD exporter functionality"""

    def test_exporter_initialization(self, usd_config: ExportConfig) -> None:
        """Test USD exporter initializes correctly"""
        exporter = USDExporter(config=usd_config)
        assert exporter.config == usd_config
        assert exporter.logger is not None

    def test_get_supported_formats(self, usd_exporter: USDExporter) -> None:
        """Test USD exporter supports USD format"""
        formats = usd_exporter.get_supported_formats()
        assert ExportFormat.USD in formats
        assert len(formats) == 1


class TestUSDExport:
    """Test USD export functionality"""

    @pytest.mark.asyncio
    async def test_export_success(
        self, usd_exporter: USDExporter, sample_mesh_data: dict[str, Any]
    ) -> None:
        """Test successful USD export"""
        result = await usd_exporter.export(sample_mesh_data)
        assert result.success is True
        assert result.file_path is not None
        assert result.file_path.exists()
        assert result.file_size > 0
        assert result.export_time is not None

    @pytest.mark.asyncio
    async def test_export_creates_valid_usd_file(
        self, usd_exporter: USDExporter, sample_mesh_data: dict[str, Any]
    ) -> None:
        """Test export creates valid USD file"""
        result = await usd_exporter.export(sample_mesh_data)
        assert result.success is True

        with open(result.file_path) as f:
            content = f.read()

        # Check USD header
        assert "#usda 1.0" in content
        assert "defaultPrim" in content
        assert "upAxis" in content

    @pytest.mark.asyncio
    async def test_export_with_invalid_data(self, usd_exporter: USDExporter) -> None:
        """Test export fails with invalid data"""
        invalid_data = {"invalid": "data"}
        result = await usd_exporter.export(invalid_data)
        assert result.success is False
        assert len(result.errors) > 0

    @pytest.mark.asyncio
    async def test_export_metadata(
        self, usd_exporter: USDExporter, sample_mesh_data: dict[str, Any]
    ) -> None:
        """Test export result includes correct metadata"""
        result = await usd_exporter.export(sample_mesh_data)
        assert result.success is True
        assert result.metadata["format"] == "USD"
        assert result.metadata["version"] == "22.11"

    @pytest.mark.asyncio
    async def test_export_handles_exceptions(
        self, usd_exporter: USDExporter, sample_mesh_data: dict[str, Any]
    ) -> None:
        """Test export handles exceptions gracefully"""
        usd_exporter.config.output_path = Path("/invalid/path/output.usd")
        result = await usd_exporter.export(sample_mesh_data)
        assert result.success is False
        assert len(result.errors) > 0


class TestUSDStructure:
    """Test USD structure creation"""

    @pytest.mark.asyncio
    async def test_create_usd_structure(
        self, usd_exporter: USDExporter, sample_mesh_data: dict[str, Any]
    ) -> None:
        """Test creating basic USD structure"""
        usd_data = await usd_exporter._create_usd_structure(sample_mesh_data)

        assert "content" in usd_data
        assert len(usd_data["content"]) > 0

        content = "\n".join(usd_data["content"])
        assert "#usda 1.0" in content

    @pytest.mark.asyncio
    async def test_usd_stage_metadata(
        self, usd_exporter: USDExporter, sample_mesh_data: dict[str, Any]
    ) -> None:
        """Test USD stage metadata is correct"""
        usd_data = await usd_exporter._create_usd_structure(sample_mesh_data)

        content = "\n".join(usd_data["content"])
        assert 'upAxis = "Y"' in content
        assert "metersPerUnit = 1.0" in content
        assert "timeCodesPerSecond = 24" in content

    @pytest.mark.asyncio
    async def test_usd_default_prim(
        self, usd_exporter: USDExporter, sample_mesh_data: dict[str, Any]
    ) -> None:
        """Test USD defaultPrim is set"""
        usd_data = await usd_exporter._create_usd_structure(sample_mesh_data)

        content = "\n".join(usd_data["content"])
        assert 'defaultPrim = "Model"' in content

    @pytest.mark.asyncio
    async def test_usd_with_different_metadata(
        self, usd_exporter, sample_metadata_variations
    ) -> None:
        """Test USD structure with different metadata"""
        for metadata in sample_metadata_variations:
            data = {
                "mesh": {"vertices": [[0, 0, 0]], "faces": [], "normals": []},
                "materials": {},
                "metadata": metadata,
            }

            usd_data = await usd_exporter._create_usd_structure(data)
            content = "\n".join(usd_data["content"])

            # Check that metadata is present (with defaults if not specified)
            assert "upAxis" in content
            assert "metersPerUnit" in content
            assert "timeCodesPerSecond" in content


class TestUSDMeshConversion:
    """Test mesh data conversion to USD"""

    @pytest.mark.asyncio
    async def test_convert_mesh_to_usd(
        self, usd_exporter: USDExporter, sample_mesh_data: dict[str, Any]
    ) -> None:
        """Test converting mesh data to USD format"""
        mesh_lines = await usd_exporter._convert_mesh_to_usd(sample_mesh_data["mesh"])

        assert len(mesh_lines) > 0
        content = "\n".join(mesh_lines)

        assert "def Xform" in content
        assert "def Mesh" in content
        assert "points =" in content
        assert "faceVertexCounts =" in content
        assert "faceVertexIndices =" in content

    @pytest.mark.asyncio
    async def test_mesh_points_formatting(
        self, usd_exporter: USDExporter, sample_mesh_data: dict[str, Any]
    ) -> None:
        """Test mesh points are formatted correctly"""
        mesh_lines = await usd_exporter._convert_mesh_to_usd(sample_mesh_data["mesh"])
        content = "\n".join(mesh_lines)

        # Check that points are in correct format
        assert "point3f[]" in content
        assert "points =" in content

    @pytest.mark.asyncio
    async def test_mesh_face_counts(
        self, usd_exporter: USDExporter, sample_mesh_data: dict[str, Any]
    ) -> None:
        """Test face vertex counts are correct"""
        mesh_lines = await usd_exporter._convert_mesh_to_usd(sample_mesh_data["mesh"])
        content = "\n".join(mesh_lines)

        # Each face should have 3 vertices
        assert "faceVertexCounts =" in content
        assert "int[]" in content

    @pytest.mark.asyncio
    async def test_mesh_face_indices(
        self, usd_exporter: USDExporter, sample_mesh_data: dict[str, Any]
    ) -> None:
        """Test face vertex indices are correct"""
        mesh_lines = await usd_exporter._convert_mesh_to_usd(sample_mesh_data["mesh"])
        content = "\n".join(mesh_lines)

        assert "faceVertexIndices =" in content
        assert "int[]" in content

    @pytest.mark.asyncio
    async def test_mesh_normals(
        self, usd_exporter: USDExporter, sample_mesh_data: dict[str, Any]
    ) -> None:
        """Test mesh normals are included"""
        mesh_lines = await usd_exporter._convert_mesh_to_usd(sample_mesh_data["mesh"])
        content = "\n".join(mesh_lines)

        assert "normal3f[]" in content
        assert "normals =" in content

    @pytest.mark.asyncio
    async def test_mesh_extent(
        self, usd_exporter: USDExporter, sample_mesh_data: dict[str, Any]
    ) -> None:
        """Test mesh extent is calculated"""
        mesh_lines = await usd_exporter._convert_mesh_to_usd(sample_mesh_data["mesh"])
        content = "\n".join(mesh_lines)

        # Extent should be present for valid mesh
        assert "extent =" in content
        assert "point3f[2]" in content

    @pytest.mark.asyncio
    async def test_material_binding(
        self, usd_exporter: USDExporter, sample_mesh_data: dict[str, Any]
    ) -> None:
        """Test material binding is added to mesh"""
        mesh_lines = await usd_exporter._convert_mesh_to_usd(sample_mesh_data["mesh"])
        content = "\n".join(mesh_lines)

        assert "material:binding" in content
        assert "</Material>" in content


class TestUSDMaterialConversion:
    """Test material conversion to USD"""

    @pytest.mark.asyncio
    async def test_convert_materials_to_usd(
        self, usd_exporter: USDExporter, sample_mesh_data: dict[str, Any]
    ) -> None:
        """Test converting materials to USD format"""
        material_lines = await usd_exporter._convert_materials_to_usd(sample_mesh_data["materials"])

        assert len(material_lines) > 0
        content = "\n".join(material_lines)

        assert "def Material" in content
        assert "def Shader" in content
        assert "UsdPreviewSurface" in content

    @pytest.mark.asyncio
    async def test_material_preview_surface(
        self, usd_exporter: USDExporter, sample_mesh_data: dict[str, Any]
    ) -> None:
        """Test UsdPreviewSurface shader is created"""
        material_lines = await usd_exporter._convert_materials_to_usd(sample_mesh_data["materials"])
        content = "\n".join(material_lines)

        assert "UsdPreviewSurface" in content
        assert "diffuseColor" in content
        assert "outputs:surface" in content

    @pytest.mark.asyncio
    async def test_material_diffuse_color(
        self, usd_exporter: USDExporter, sample_mesh_data: dict[str, Any]
    ) -> None:
        """Test material diffuse color is set correctly"""
        material_lines = await usd_exporter._convert_materials_to_usd(sample_mesh_data["materials"])
        content = "\n".join(material_lines)

        # Should contain RGB tuple
        assert "color3f" in content
        assert "diffuseColor" in content

    @pytest.mark.asyncio
    async def test_material_with_different_colors(self, usd_exporter: USDExporter) -> None:
        """Test materials with different color formats"""
        test_materials = [
            {"diffuse_color": [1.0, 0.0, 0.0]},
            {"diffuse_color": [0.5, 0.5, 0.5]},
            {"diffuse_color": np.array([0.2, 0.8, 0.4])},
        ]

        for materials in test_materials:
            material_lines = await usd_exporter._convert_materials_to_usd(materials)
            content = "\n".join(material_lines)
            assert "diffuseColor" in content


class TestUSDAnimations:
    """Test animation conversion to USD"""

    @pytest.mark.asyncio
    async def test_convert_animations_to_usd(
        self, usd_exporter: USDExporter, sample_animation_data: dict[str, Any]
    ) -> None:
        """Test converting animations to USD format"""
        animation_lines = await usd_exporter._convert_animations_to_usd(
            sample_animation_data["animations"]
        )

        assert len(animation_lines) > 0
        content = "\n".join(animation_lines)

        assert "def Xform" in content
        assert "timeSamples" in content
        assert "xformOp:translate" in content

    @pytest.mark.asyncio
    async def test_animation_time_samples(
        self, usd_exporter: USDExporter, sample_animation_data: dict[str, Any]
    ) -> None:
        """Test animation time samples are created correctly"""
        animation_lines = await usd_exporter._convert_animations_to_usd(
            sample_animation_data["animations"]
        )
        content = "\n".join(animation_lines)

        # Check for time samples
        assert "timeSamples" in content
        assert "xformOp:translate" in content

    @pytest.mark.asyncio
    async def test_animation_keyframe_times(
        self, usd_exporter: USDExporter, sample_animation_data: dict[str, Any]
    ) -> None:
        """Test animation keyframe times are formatted correctly"""
        animation_lines = await usd_exporter._convert_animations_to_usd(
            sample_animation_data["animations"]
        )
        content = "\n".join(animation_lines)

        # Should contain integer and float time values
        assert "0:" in content or "1:" in content

    @pytest.mark.asyncio
    async def test_animation_translate_values(
        self, usd_exporter: USDExporter, sample_animation_data: dict[str, Any]
    ) -> None:
        """Test animation translate values are formatted correctly"""
        animation_lines = await usd_exporter._convert_animations_to_usd(
            sample_animation_data["animations"]
        )
        content = "\n".join(animation_lines)

        # Should contain double3 values
        assert "double3" in content

    @pytest.mark.asyncio
    async def test_animation_xform_op_order(
        self, usd_exporter: USDExporter, sample_animation_data: dict[str, Any]
    ) -> None:
        """Test animation xformOpOrder is set"""
        animation_lines = await usd_exporter._convert_animations_to_usd(
            sample_animation_data["animations"]
        )
        content = "\n".join(animation_lines)

        assert "xformOpOrder" in content
        assert "xformOp:translate" in content

    @pytest.mark.asyncio
    async def test_empty_animations_return_empty(self, usd_exporter: USDExporter) -> None:
        """Test empty animations return empty list"""
        empty_animations = {"keyframes": []}
        animation_lines = await usd_exporter._convert_animations_to_usd(empty_animations)
        assert len(animation_lines) == 0

    @pytest.mark.asyncio
    async def test_no_keyframes_return_empty(self, usd_exporter: USDExporter) -> None:
        """Test animations without keyframes return empty list"""
        no_keyframes = {}
        animation_lines = await usd_exporter._convert_animations_to_usd(no_keyframes)
        assert len(animation_lines) == 0


class TestUSDFormatting:
    """Test USD data formatting helpers"""

    def test_format_points_with_array(self, usd_exporter: USDExporter) -> None:
        """Test formatting points from numpy array"""
        points = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
        formatted = usd_exporter._format_points(points)

        assert formatted.startswith("[")
        assert formatted.endswith("]")
        assert "(" in formatted
        assert ")" in formatted

    def test_format_points_with_list(self, usd_exporter: USDExporter) -> None:
        """Test formatting points from list"""
        points = [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]
        formatted = usd_exporter._format_points(points)

        assert formatted.startswith("[")
        assert formatted.endswith("]")

    def test_format_points_empty(self, usd_exporter: USDExporter) -> None:
        """Test formatting empty points"""
        points = []
        formatted = usd_exporter._format_points(points)
        assert formatted == "[]"

    def test_format_face_counts(self, usd_exporter: USDExporter) -> None:
        """Test formatting face vertex counts"""
        faces = np.array([[0, 1, 2], [3, 4, 5]])
        formatted = usd_exporter._format_face_counts(faces)

        assert "[" in formatted
        assert "]" in formatted
        assert "3" in formatted

    def test_format_face_counts_empty(self, usd_exporter: USDExporter) -> None:
        """Test formatting empty face counts"""
        faces = []
        formatted = usd_exporter._format_face_counts(faces)
        assert formatted == "[]"

    def test_format_face_indices(self, usd_exporter: USDExporter) -> None:
        """Test formatting face vertex indices"""
        faces = np.array([[0, 1, 2], [3, 4, 5]])
        formatted = usd_exporter._format_face_indices(faces)

        assert "[" in formatted
        assert "]" in formatted
        # Should contain all indices
        for i in range(6):
            assert str(i) in formatted

    def test_format_face_indices_empty(self, usd_exporter: USDExporter) -> None:
        """Test formatting empty face indices"""
        faces = []
        formatted = usd_exporter._format_face_indices(faces)
        assert formatted == "[]"

    def test_to_ndarray_from_list(self, usd_exporter: USDExporter) -> None:
        """Test converting list to ndarray"""
        data = [[1, 2, 3], [4, 5, 6]]
        array = usd_exporter._to_ndarray(data)
        assert isinstance(array, np.ndarray)
        assert array.shape == (2, 3)

    def test_to_ndarray_from_array(self, usd_exporter: USDExporter) -> None:
        """Test converting existing ndarray"""
        data = np.array([[1, 2, 3]])
        array = usd_exporter._to_ndarray(data)
        assert isinstance(array, np.ndarray)

    def test_to_ndarray_invalid_data(self, usd_exporter: USDExporter) -> None:
        """Test converting invalid data returns empty array"""
        data = None
        array = usd_exporter._to_ndarray(data)
        assert isinstance(array, np.ndarray)
        assert array.size == 0


class TestUSDFileWriting:
    """Test USD file writing"""

    @pytest.mark.asyncio
    async def test_write_usd_file(self, usd_exporter: USDExporter, temp_output_dir: Path) -> None:
        """Test writing USD file to disk"""
        usd_data = {
            "content": [
                "#usda 1.0",
                "(",
                '    defaultPrim = "Model"',
                ")",
            ]
        }

        await usd_exporter._write_usd_file(usd_data)

        assert usd_exporter.config.output_path.exists()

        with open(usd_exporter.config.output_path) as f:
            content = f.read()

        assert "#usda 1.0" in content
        assert "defaultPrim" in content

    @pytest.mark.asyncio
    async def test_write_usd_file_creates_directories(
        self, usd_exporter: USDExporter, temp_output_dir: Path
    ) -> None:
        """Test writing USD file creates parent directories"""
        nested_path = temp_output_dir / "nested" / "path" / "output.usd"
        usd_exporter.config.output_path = nested_path

        usd_data = {"content": ["#usda 1.0"]}

        await usd_exporter._write_usd_file(usd_data)

        assert nested_path.exists()
        assert nested_path.parent.exists()

    @pytest.mark.asyncio
    async def test_write_usd_file_no_output_path(self, usd_exporter: USDExporter) -> None:
        """Test writing USD file raises error without output path"""
        usd_exporter.config.output_path = None
        usd_data = {"content": ["#usda 1.0"]}

        with pytest.raises(ValueError, match="Output path not specified"):
            await usd_exporter._write_usd_file(usd_data)

    @pytest.mark.asyncio
    async def test_write_usd_file_line_by_line(self, usd_exporter: USDExporter) -> None:
        """Test USD file is written line by line"""
        usd_data = {"content": ["line1", "line2", "line3"]}

        await usd_exporter._write_usd_file(usd_data)

        with open(usd_exporter.config.output_path) as f:
            lines = f.readlines()

        assert len(lines) == 3
        assert "line1" in lines[0]
        assert "line2" in lines[1]
        assert "line3" in lines[2]


class TestUSDQualityLevels:
    """Test different quality levels for USD export"""

    @pytest.mark.asyncio
    async def test_draft_quality_export(self, sample_mesh_data, temp_output_dir) -> None:
        """Test export with draft quality"""
        config = ExportConfig(
            format=ExportFormat.USD,
            quality=ExportQuality.DRAFT,
            output_path=temp_output_dir / "draft.usd",
        )
        exporter = USDExporter(config=config)

        result = await exporter.export(sample_mesh_data)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_high_quality_export(self, sample_mesh_data, temp_output_dir) -> None:
        """Test export with high quality"""
        config = ExportConfig(
            format=ExportFormat.USD,
            quality=ExportQuality.HIGH,
            output_path=temp_output_dir / "high.usd",
        )
        exporter = USDExporter(config=config)

        result = await exporter.export(sample_mesh_data)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_production_quality_export(self, sample_mesh_data, temp_output_dir) -> None:
        """Test export with production quality"""
        config = ExportConfig(
            format=ExportFormat.USD,
            quality=ExportQuality.PRODUCTION,
            output_path=temp_output_dir / "production.usd",
        )
        exporter = USDExporter(config=config)

        result = await exporter.export(sample_mesh_data)
        assert result.success is True
