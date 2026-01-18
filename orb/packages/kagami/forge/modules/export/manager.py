"""
Export manager for coordinating different export formats.
Direct imports - run `make forge-setup` to install dependencies.
"""

import asyncio
import logging
from typing import Any

from .base import BaseExporter, ExportConfig, ExportFormat, ExportResult
from .fbx_exporter import FBXExporter
from .gltf_exporter import GLTFExporter
from .obj_exporter import OBJExporter
from .usd_exporter import USDExporter


class ExportManager:
    """Manager for coordinating different export formats."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.logger = logging.getLogger(__name__)
        self.config = config or {}
        self._exporters: dict[ExportFormat, type[BaseExporter]] = {
            ExportFormat.FBX: FBXExporter,
            ExportFormat.GLTF: GLTFExporter,
            ExportFormat.GLB: GLTFExporter,
            ExportFormat.USD: USDExporter,
            ExportFormat.OBJ: OBJExporter,
        }

    def get_supported_formats(self) -> list[ExportFormat]:
        """Get all supported export formats."""
        return list(self._exporters.keys())

    async def export(
        self,
        data: dict[str, Any],
        config: ExportConfig | None = None,
        format: str | None = None,
    ) -> Any:
        """Export data using the specified format.

        Args:
            data: Character data to export
            config: Export configuration (preferred)
            format: Export format string (for convenience)
        """
        if config is None:
            format_str = format or "glb"
            format_upper = format_str.upper()
            format_map = {
                "GLTF": ExportFormat.GLTF,
                "GLB": ExportFormat.GLB,
                "FBX": ExportFormat.FBX,
                "USD": ExportFormat.USD,
                "OBJ": ExportFormat.OBJ,
            }
            export_format = format_map.get(format_upper, ExportFormat.GLB)
            config = ExportConfig(
                format=export_format,
                include_animations=True,
                include_materials=True,
            )

        try:
            exporter_class = self._exporters.get(config.format)
            if not exporter_class:
                return ExportResult(
                    success=False,
                    errors=[f"Unsupported export format: {config.format}"],
                )

            exporter = exporter_class(config)

            if config.format not in exporter.get_supported_formats():
                return ExportResult(
                    success=False,
                    errors=[f"Exporter does not support format: {config.format}"],
                )

            self.logger.info(f"Starting export to {config.format.value} format")
            result = await exporter.export(data)

            if result.success:
                self.logger.info(f"Export completed successfully: {result.file_path}")
            else:
                self.logger.error(f"Export failed: {result.errors}")

            return result

        except Exception as e:
            self.logger.error(f"Export failed with exception: {e}")
            return ExportResult(success=False, errors=[str(e)])

    async def export_multiple(
        self, data: dict[str, Any], configs: list[ExportConfig]
    ) -> list[ExportResult]:
        """Export data to multiple formats concurrently."""
        try:
            tasks = [asyncio.create_task(self.export(data, config)) for config in configs]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            export_results = []
            for result in results:
                if isinstance(result, Exception):
                    export_results.append(ExportResult(success=False, errors=[str(result)]))
                elif isinstance(result, ExportResult):
                    export_results.append(result)
                else:
                    export_results.append(
                        ExportResult(success=False, errors=["Invalid result type"])
                    )

            return export_results

        except Exception as e:
            self.logger.error(f"Multiple export failed: {e}")
            return [ExportResult(success=False, errors=[str(e)]) for _ in configs]

    async def validate_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Validate data for export."""
        validation_result: dict[str, Any] = {"valid": True, "errors": [], "warnings": []}

        required_fields = ["mesh", "materials"]
        for field in required_fields:
            if field not in data:
                validation_result["errors"].append(f"Missing required field: {field}")
                validation_result["valid"] = False

        if "mesh" in data:
            mesh_validation = await self._validate_mesh_data(data["mesh"])
            if not mesh_validation["valid"]:
                validation_result["errors"].extend(mesh_validation["errors"])
                validation_result["valid"] = False
            validation_result["warnings"].extend(mesh_validation["warnings"])

        if "materials" in data:
            material_validation = await self._validate_material_data(data["materials"])
            if not material_validation["valid"]:
                validation_result["errors"].extend(material_validation["errors"])
                validation_result["valid"] = False
            validation_result["warnings"].extend(material_validation["warnings"])

        return validation_result

    async def _validate_mesh_data(self, mesh_data: dict[str, Any]) -> dict[str, Any]:
        """Validate mesh data."""
        result: dict[str, Any] = {"valid": True, "errors": [], "warnings": []}

        vertices = mesh_data.get("vertices", [])
        if not vertices:
            result["errors"].append("Mesh has no vertices")
            result["valid"] = False
        elif len(vertices[0]) < 3:
            result["errors"].append("Vertices must have at least 3 components (x, y, z)")
            result["valid"] = False

        faces = mesh_data.get("faces", [])
        if not faces:
            result["warnings"].append("Mesh has no faces")
        elif any(len(face) < 3 for face in faces):
            result["errors"].append("All faces must have at least 3 vertices")
            result["valid"] = False

        normals = mesh_data.get("normals", [])
        if normals and len(normals) != len(vertices):
            result["warnings"].append("Number of normals doesn't match number of vertices")

        return result

    async def _validate_material_data(self, material_data: dict[str, Any]) -> dict[str, Any]:
        """Validate material data."""
        result: dict[str, Any] = {"valid": True, "errors": [], "warnings": []}

        for color_key in ["diffuse_color", "specular_color", "ambient_color"]:
            if color_key in material_data:
                color = material_data[color_key]
                if not isinstance(color, list) or len(color) < 3:
                    result["errors"].append(
                        f"{color_key} must be a list[Any] with at least 3 components"
                    )
                    result["valid"] = False
                elif any(not isinstance(c, (int, float)) for c in color):
                    result["errors"].append(f"{color_key} components must be numeric")
                    result["valid"] = False

        return result

    def add_exporter(self, format_type: ExportFormat, exporter_class: type[BaseExporter]) -> None:
        """Add a custom exporter."""
        self._exporters[format_type] = exporter_class

    def remove_exporter(self, format_type: ExportFormat) -> None:
        """Remove an exporter."""
        if format_type in self._exporters:
            del self._exporters[format_type]
