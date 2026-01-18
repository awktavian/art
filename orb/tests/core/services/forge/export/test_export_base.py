"""
Base Exporter Tests

Tests the base exporter functionality including:
- Configuration handling
- Data validation
- Export workflow
- Error handling
- Quality level processing
- Status reporting
- File I/O operations
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration


import json
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

from kagami.forge.modules.export.base import (
    BaseExporter,
    ExportConfig,
    ExportFormat,
    ExportQuality,
    ExportResult,
    ForgeComponent,
)


@pytest.fixture
def temp_output_dir():  # type: ignore[misc]
    """Create a temporary directory for test outputs"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def base_config(temp_output_dir):
    """Create basic export configuration"""
    return ExportConfig(
        format=ExportFormat.JSON,
        quality=ExportQuality.STANDARD,
        output_path=temp_output_dir / "test_export.json",
        include_textures=True,
        include_animations=True,
        include_materials=True,
        compression_level=5,
        texture_resolution=1024,
    )


@pytest.fixture
def base_exporter(base_config):
    """Create base exporter instance"""
    return BaseExporter(config=base_config)


@pytest.fixture
def sample_data() -> dict[str, Any]:
    """Create sample mesh data for testing"""
    return {
        "mesh": {
            "vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
            "faces": [[0, 1, 2]],
            "normals": [[0, 0, 1], [0, 0, 1], [0, 0, 1]],
        },
        "materials": {
            "diffuse_color": [1.0, 0.0, 0.0],
            "metallic": 0.5,
            "roughness": 0.3,
        },
        "animations": {
            "keyframes": [
                {"time": 0, "translate": [0, 0, 0]},
                {"time": 1, "translate": [1, 0, 0]},
            ]
        },
    }


class TestForgeComponent:
    """Test ForgeComponent fallback class"""

    def test_forge_component_initialization(self) -> None:
        """Test ForgeComponent can be initialized with a name"""
        component = ForgeComponent(name="TestComponent")
        assert component.name == "TestComponent"

    def test_forge_component_initialize(self) -> None:
        """Test ForgeComponent initialize method returns None"""
        component = ForgeComponent(name="TestComponent")
        result = component.initialize({"key": "value"})
        assert result is None

    def test_forge_component_initialize_no_config(self) -> None:
        """Test ForgeComponent initialize with no config"""
        component = ForgeComponent(name="TestComponent")
        result = component.initialize()
        assert result is None


class TestExportEnums:
    """Test export enumerations"""

    def test_export_format_values(self) -> None:
        """Test ExportFormat enum values are correct"""
        assert ExportFormat.FBX.value == "fbx"
        assert ExportFormat.USD.value == "usd"
        assert ExportFormat.GLTF.value == "gltf"
        assert ExportFormat.GLB.value == "glb"
        assert ExportFormat.OBJ.value == "obj"

    def test_export_quality_values(self) -> None:
        """Test ExportQuality enum values are correct"""
        assert ExportQuality.DRAFT.value == "draft"
        assert ExportQuality.STANDARD.value == "standard"
        assert ExportQuality.HIGH.value == "high"
        assert ExportQuality.PRODUCTION.value == "production"

    def test_export_format_membership(self) -> None:
        """Test ExportFormat enum membership"""
        assert ExportFormat.GLTF in ExportFormat
        assert "invalid" not in [f.value for f in ExportFormat]


class TestExportConfig:
    """Test ExportConfig dataclass"""

    def test_config_creation_with_defaults(self) -> None:
        """Test creating config with minimal parameters"""
        config = ExportConfig(format=ExportFormat.GLTF)
        assert config.format == ExportFormat.GLTF
        assert config.quality == ExportQuality.STANDARD
        assert config.include_textures is True
        assert config.include_animations is True
        assert config.include_materials is True

    def test_config_creation_with_all_params(self, temp_output_dir: Path) -> None:
        """Test creating config with all parameters"""
        output_path = temp_output_dir / "output.gltf"
        config = ExportConfig(
            format=ExportFormat.GLTF,
            quality=ExportQuality.HIGH,
            output_path=output_path,
            include_textures=False,
            include_animations=False,
            include_materials=False,
            compression_level=9,
            texture_resolution=2048,
            animation_fps=60,
        )
        assert config.format == ExportFormat.GLTF
        assert config.quality == ExportQuality.HIGH
        assert config.output_path == output_path
        assert config.include_textures is False
        assert config.compression_level == 9
        assert config.texture_resolution == 2048
        assert config.animation_fps == 60

    def test_config_output_path_default(self) -> None:
        """Test output_path is set to default if not provided"""
        config = ExportConfig(format=ExportFormat.USD)
        assert config.output_path == Path("output.usd")

    def test_config_quality_levels(self) -> None:
        """Test all quality levels can be set"""
        for quality in ExportQuality:
            config = ExportConfig(format=ExportFormat.FBX, quality=quality)
            assert config.quality == quality


class TestExportResult:
    """Test ExportResult dataclass"""

    def test_result_success(self, temp_output_dir: Path) -> None:
        """Test creating successful export result"""
        output_path = temp_output_dir / "output.json"
        result = ExportResult(
            success=True,
            file_path=output_path,
            file_size=1024,
            export_time=0.5,
            metadata={"format": "json"},
        )
        assert result.success is True
        assert result.file_path == output_path
        assert result.file_size == 1024
        assert result.export_time == 0.5
        assert result.metadata["format"] == "json"

    def test_result_failure(self) -> None:
        """Test creating failed export result"""
        result = ExportResult(
            success=False,
            errors=["Invalid data", "Missing required field"],
            warnings=["Low quality detected"],
        )
        assert result.success is False
        assert len(result.errors) == 2
        assert len(result.warnings) == 1
        assert result.file_path is None

    def test_result_with_exported_files(self) -> None:
        """Test result with exported_files list"""
        result = ExportResult(
            success=True,
            output_path="/path/to/output.gltf",
            exported_files=["/path/to/output.gltf", "/path/to/texture.png"],
        )
        assert result.success is True
        assert result.output_path == "/path/to/output.gltf"
        assert len(result.exported_files) == 2  # type: ignore[arg-type]


class TestBaseExporter:
    """Test BaseExporter class"""

    def test_exporter_initialization_with_config(self, base_config) -> None:
        """Test exporter initializes with provided config"""
        exporter = BaseExporter(config=base_config)
        assert exporter.config == base_config
        assert exporter.logger is not None

    def test_exporter_initialization_without_config(self) -> None:
        """Test exporter creates default config if none provided"""
        exporter = BaseExporter()
        assert exporter.config is not None
        assert exporter.config.format == ExportFormat.GLTF
        assert exporter.config.quality == ExportQuality.STANDARD

    def test_get_supported_formats(self, base_exporter: BaseExporter) -> None:
        """Test get_supported_formats returns JSON by default"""
        formats = base_exporter.get_supported_formats()
        assert ExportFormat.JSON in formats
        assert len(formats) == 1

    def test_get_status_specific(self, base_exporter: BaseExporter) -> None:
        """Test _get_status_specific returns correct info"""
        status = base_exporter._get_status_specific()
        assert "supported_formats" in status
        assert "output_path" in status
        assert "json" in status["supported_formats"]

    @pytest.mark.asyncio
    async def test_validate_data_success(self, base_exporter, sample_data) -> None:
        """Test data validation succeeds with valid data"""
        is_valid = await base_exporter.validate_data(sample_data)
        assert is_valid is True

    @pytest.mark.asyncio
    async def test_validate_data_missing_mesh(self, base_exporter: BaseExporter) -> None:
        """Test data validation fails when mesh is missing"""
        invalid_data = {"materials": {}}
        is_valid = await base_exporter.validate_data(invalid_data)
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_validate_data_missing_materials(self, base_exporter: BaseExporter) -> None:
        """Test data validation fails when materials are missing"""
        invalid_data = {"mesh": {}}
        is_valid = await base_exporter.validate_data(invalid_data)
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_export_success(self, base_exporter, sample_data, temp_output_dir) -> None:
        """Test successful export creates file"""
        result = await base_exporter.export(sample_data)
        assert result.success is True
        assert result.file_path is not None
        assert result.file_path.exists()
        assert result.file_size > 0
        assert result.export_time is not None

    @pytest.mark.asyncio
    async def test_export_creates_json_content(self, base_exporter, sample_data) -> None:
        """Test export creates valid JSON content"""
        result = await base_exporter.export(sample_data)
        assert result.success is True

        with open(result.file_path) as f:
            content = json.load(f)

        assert content["format"] == "generic"
        assert content["exporter"] == "BaseExporter"
        assert content["quality"] == "standard"
        assert content["data"] == sample_data

    @pytest.mark.asyncio
    async def test_export_with_invalid_data(self, base_exporter: BaseExporter) -> None:
        """Test export fails with invalid data"""
        invalid_data = {"invalid": "data"}
        result = await base_exporter.export(invalid_data)
        assert result.success is False
        assert len(result.errors) > 0
        assert "Invalid data" in result.errors[0]

    @pytest.mark.asyncio
    async def test_export_handles_write_errors(self, base_exporter, sample_data) -> None:
        """Test export handles file write errors gracefully"""
        # Set invalid output path
        base_exporter.config.output_path = Path("/invalid/path/output.json")

        result = await base_exporter.export(sample_data)
        assert result.success is False
        assert len(result.errors) > 0
        assert result.export_time is not None

    @pytest.mark.asyncio
    async def test_export_with_different_quality_levels(self, sample_data, temp_output_dir) -> None:
        """Test export with different quality levels"""
        for quality in ExportQuality:
            config = ExportConfig(
                format=ExportFormat.JSON,
                quality=quality,
                output_path=temp_output_dir / f"output_{quality.value}.json",
            )
            exporter = BaseExporter(config=config)
            result = await exporter.export(sample_data)

            assert result.success is True
            with open(result.file_path) as f:  # type: ignore[arg-type]
                content = json.load(f)
            assert content["quality"] == quality.value

    @pytest.mark.asyncio
    async def test_export_metadata_contains_fallback_flag(self, base_exporter, sample_data) -> None:
        """Test export result metadata indicates fallback implementation"""
        result = await base_exporter.export(sample_data)
        assert result.success is True
        assert result.metadata["fallback"] is True
        assert result.metadata["format"] == "json"

    @pytest.mark.asyncio
    async def test_export_with_custom_output_path(self, sample_data, temp_output_dir) -> None:
        """Test export respects custom output path"""
        custom_path = temp_output_dir / "custom" / "path" / "output.json"
        config = ExportConfig(format=ExportFormat.JSON, output_path=custom_path)
        exporter = BaseExporter(config=config)

        result = await exporter.export(sample_data)
        assert result.success is True
        assert result.file_path == custom_path

    @pytest.mark.asyncio
    async def test_export_logs_warning_for_base_implementation(
        self, base_exporter, sample_data, caplog
    ) -> None:
        """Test export logs warning when using base implementation"""
        await base_exporter.export(sample_data)
        assert any(
            "using base export implementation" in record.message.lower()
            for record in caplog.records
        )

    @pytest.mark.asyncio
    async def test_export_result_includes_output_path_string(
        self, base_exporter, sample_data
    ) -> None:
        """Test export result includes output_path as string for compatibility"""
        result = await base_exporter.export(sample_data)
        assert result.success is True
        assert result.output_path is not None
        assert isinstance(result.output_path, str)

    @pytest.mark.asyncio
    async def test_export_result_includes_exported_files_list(
        self, base_exporter, sample_data
    ) -> None:
        """Test export result includes exported_files list"""
        result = await base_exporter.export(sample_data)
        assert result.success is True
        assert result.exported_files is not None
        assert len(result.exported_files) == 1
        assert str(result.file_path) in result.exported_files
