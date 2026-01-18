"""
Base classes for export system
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class ForgeComponent:
    """Fallback Forge component base for export modules (GAIA purged)."""

    def __init__(self, name: str) -> None:
        self.name = name

    def initialize(self, _config: dict[str, Any] | None = None) -> None:
        return None


LOGGER = logging.getLogger(__name__)


class ExportFormat(Enum):
    """Supported export formats"""

    FBX = "fbx"
    USD = "usd"
    GLTF = "gltf"
    GLB = "glb"
    OBJ = "obj"
    DAE = "dae"
    PLY = "ply"
    STL = "stl"
    JSON = "json"
    BLEND = "blend"
    X3D = "x3d"
    VRML = "vrml"


class ExportQuality(Enum):
    """Export quality levels"""

    DRAFT = "draft"
    STANDARD = "standard"
    HIGH = "high"
    PRODUCTION = "production"


@dataclass
class ExportConfig:
    """Configuration for export operations"""

    format: ExportFormat
    quality: ExportQuality = ExportQuality.STANDARD
    output_path: Path | None = None
    include_textures: bool = True
    include_animations: bool = True
    include_materials: bool = True
    include_metadata: bool = True
    compression_level: int = 5
    texture_resolution: int = 1024
    animation_fps: int = 30

    def __post_init__(self) -> None:
        if self.output_path is None:
            self.output_path = Path(f"output.{self.format.value}")


@dataclass
class ExportResult:
    """Result of export operation"""

    success: bool
    file_path: Path | None = None
    file_size: int | None = None
    export_time: float | None = None
    warnings: list[str] = field(default_factory=list[Any])
    errors: list[str] = field(default_factory=list[Any])
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])
    # Additional fields for compatibility
    output_path: str | None = None
    exported_files: list[str] | None = None


class BaseExporter(ForgeComponent):
    """Base class for all exporters with sensible defaults.

    Subclasses only need to override:
    - get_supported_formats() - list[Any] of formats this exporter handles
    - export() - the actual export logic

    All other methods have sensible defaults that work for most cases.
    """

    def __init__(self, config: ExportConfig | None = None) -> None:
        # Create default config if none provided
        if config is None:
            config = ExportConfig(format=ExportFormat.GLTF)
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)

    def _get_status_specific(self) -> dict[str, Any]:
        """Get status info - works for all exporters."""
        return {
            "supported_formats": [f.value for f in self.get_supported_formats()],
            "output_path": (
                str(self.config.output_path)
                if hasattr(self, "config") and self.config.output_path
                else None
            ),
        }

    async def export(self, data: dict[str, Any]) -> ExportResult:
        """Export data to target format

        This base implementation provides a framework that subclasses can override.
        """
        import time

        start_time = time.time()

        # Default implementation that subclasses should override
        self.logger.warning(
            f"{self.__class__.__name__} using base export implementation. "
            "Consider implementing a format-specific export method."
        )

        # Validate data
        if not await self.validate_data(data):
            return ExportResult(
                success=False, errors=[f"Invalid data for {self.__class__.__name__}"]
            )

        # Basic export logic - write JSON representation
        try:
            import json

            output_path = self.config.output_path or Path(f"export_{int(time.time())}.json")

            # Convert data to exportable format
            export_data = {
                "format": "generic",
                "exporter": self.__class__.__name__,
                "timestamp": time.time(),
                "quality": self.config.quality.value,
                "data": data,
            }

            # Write to file
            with open(output_path, "w") as f:
                json.dump(export_data, f, indent=2)

            file_size = output_path.stat().st_size
            export_time = time.time() - start_time

            return ExportResult(
                success=True,
                file_path=output_path,
                file_size=file_size,
                export_time=export_time,
                output_path=str(output_path),
                exported_files=[str(output_path)],
                metadata={"format": "json", "fallback": True},
            )

        except Exception as e:
            self.logger.error(f"Export failed: {e}")
            return ExportResult(
                success=False, errors=[str(e)], export_time=time.time() - start_time
            )

    async def validate_data(self, data: dict[str, Any]) -> bool:
        """Validate input data"""
        required_fields = ["mesh", "materials"]
        return all(field in data for field in required_fields)

    def get_supported_formats(self) -> list[ExportFormat]:
        """Get supported export formats

        Base implementation returns JSON format as fallback.
        Subclasses should override to specify their supported formats.
        """
        return [ExportFormat.JSON]
