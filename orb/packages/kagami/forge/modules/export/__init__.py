"""
Export module for industry-standard formats.
Direct imports - run `make forge-setup` to install dependencies.
"""

from typing import Any

from kagami.forge.modules.export.asset_exporter import (
    AssetExporter,
    ExportConfig,
    ExportResult,
)
from kagami.forge.modules.export.base import (
    BaseExporter,
    ExportFormat,
    ExportQuality,
)
from kagami.forge.modules.export.dae_exporter import DAEExporter
from kagami.forge.modules.export.fbx_exporter import FBXExporter
from kagami.forge.modules.export.gltf_exporter import GLTFExporter
from kagami.forge.modules.export.manager import ExportManager
from kagami.forge.modules.export.obj_exporter import OBJExporter
from kagami.forge.modules.export.ply_exporter import PLYExporter
from kagami.forge.modules.export.stl_exporter import STLExporter
from kagami.forge.modules.export.usd_exporter import USDExporter
from kagami.forge.modules.export.x3d_exporter import X3DExporter


class ExportModule:
    """Export module for backward compatibility."""

    def __init__(self, config=None) -> None:  # type: ignore[no-untyped-def]
        self.config = config or {}
        self.manager = ExportManager()
        self.asset_exporter = AssetExporter()

    async def process(self, input_data: Any) -> Any:
        """Process export request."""
        from kagami.forge.core_integration import (
            CharacterAspect,
            CharacterResult,
            ProcessingStatus,
        )

        try:
            export_config = ExportConfig(format=ExportFormat.GLTF, **self.config)
            result = await self.manager.export(input_data, export_config)

            if result.success:
                return CharacterResult(
                    status=ProcessingStatus.COMPLETED,
                    aspect=CharacterAspect.VISUAL_DESIGN,
                    data={"export_path": str(result.file_path) if result.file_path else ""},
                    processing_time=result.export_time or 0.0,
                )
            else:
                return CharacterResult(
                    status=ProcessingStatus.FAILED,
                    aspect=CharacterAspect.VISUAL_DESIGN,
                    data={},
                    error=("; ".join(result.errors) if result.errors else "Export failed"),
                    processing_time=result.export_time or 0.0,
                )
        except Exception as e:
            return CharacterResult(
                status=ProcessingStatus.FAILED,
                aspect=CharacterAspect.VISUAL_DESIGN,
                data={},
                error=str(e),
                processing_time=0.0,
            )

    async def initialize(self) -> None:
        """Initialize export module."""
        await self.asset_exporter.initialize()


__all__: list[str] = [
    "AssetExporter",
    "BaseExporter",
    "DAEExporter",
    "ExportConfig",
    "ExportFormat",
    "ExportManager",
    "ExportModule",
    "ExportQuality",
    "ExportResult",
    "FBXExporter",
    "GLTFExporter",
    "OBJExporter",
    "PLYExporter",
    "STLExporter",
    "USDExporter",
    "X3DExporter",
]
