"""
FBX format exporter
"""

import asyncio
import struct
from typing import Any

_np: Any = None
_NUMPY_IMPORT_ERROR: Exception | None = None

try:  # pragma: no cover - optional heavy dependency
    import numpy

    _np = numpy
except Exception as _numpy_err:  # pragma: no cover
    _NUMPY_IMPORT_ERROR = _numpy_err

if _np is None:

    def _to_array(values: Any, dtype: Any | None = None) -> Any:
        return list(values)

else:  # pragma: no cover - standard path

    def _to_array(values: Any, dtype: Any | None = None) -> Any:
        return _np.array(values, dtype=dtype)


from .base import BaseExporter, ExportFormat, ExportResult


class FBXExporter(BaseExporter):
    """FBX format exporter

    Inherits all default methods from BaseExporter.
    Only overrides get_supported_formats() and export() for FBX-specific logic.
    """

    def get_supported_formats(self) -> list[ExportFormat]:
        return [ExportFormat.FBX]

    def _get_status_specific(self) -> dict[str, Any]:
        """Get FBX exporter specific status"""
        return {
            "supported_formats": [f.value for f in self.get_supported_formats()],
            "output_path": (str(self.config.output_path) if hasattr(self, "config") else None),
        }

    async def export(self, data: dict[str, Any]) -> ExportResult:
        """Export data to FBX format"""
        loop = asyncio.get_running_loop()
        start_time = loop.time()

        try:
            # Validate input data
            if not await self.validate_data(data):
                return ExportResult(success=False, errors=["Invalid input data for FBX export"])

            # Create FBX file structure
            fbx_data = await self._create_fbx_structure(data)

            # Write FBX file
            await self._write_fbx_file(fbx_data)

            export_time = loop.time() - start_time
            file_size = (
                self.config.output_path.stat().st_size
                if self.config.output_path and self.config.output_path.exists()
                else 0
            )

            return ExportResult(
                success=True,
                file_path=self.config.output_path,
                file_size=file_size,
                export_time=export_time,
                metadata={"format": "FBX", "version": "7.4"},
            )

        except Exception as e:
            self.logger.error(f"FBX export failed: {e}")
            return ExportResult(success=False, errors=[str(e)])

    async def _create_fbx_structure(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create FBX file structure"""
        # Convert mesh data to FBX format
        mesh_data = await self._convert_mesh_to_fbx(data.get("mesh", {}))

        # Convert materials to FBX format
        materials_data = await self._convert_materials_to_fbx(data.get("materials", {}))

        # Convert animations to FBX format
        animations_data = await self._convert_animations_to_fbx(data.get("animations", {}))

        return {
            "header": self._create_fbx_header(),
            "objects": {
                "geometry": mesh_data,
                "materials": materials_data,
                "animations": animations_data,
            },
            "connections": self._create_fbx_connections(),
        }

    def _create_fbx_header(self) -> dict[str, Any]:
        """Create FBX header"""
        return {
            "magic": b"Kaydara FBX Binary  \x00\x1a\x00",
            "version": 7400,
            "timestamp": 0,
        }

    def _create_fbx_connections(self) -> list[dict[str, Any]]:
        """Create FBX connections"""
        return [
            {"type": "OO", "child": "Geometry", "parent": "Model"},
            {"type": "OO", "child": "Material", "parent": "Model"},
        ]

    async def _convert_mesh_to_fbx(self, mesh: dict[str, Any]) -> dict[str, Any]:
        """Convert mesh data to FBX format"""
        vertices = mesh.get("vertices", [])
        faces = mesh.get("faces", [])
        normals = mesh.get("normals", [])

        return {
            "vertices": _to_array(vertices, dtype=getattr(_np, "float32", None)),
            "polygon_vertex_index": _to_array(faces, dtype=getattr(_np, "int32", None)),
            "normals": _to_array(normals, dtype=getattr(_np, "float32", None)),
        }

    async def _convert_materials_to_fbx(self, materials: dict[str, Any]) -> dict[str, Any]:
        """Convert materials to FBX format"""
        return {
            "diffuse_color": materials.get("diffuse_color", [1.0, 1.0, 1.0]),
            "specular_color": materials.get("specular_color", [1.0, 1.0, 1.0]),
            "ambient_color": materials.get("ambient_color", [0.1, 0.1, 0.1]),
        }

    async def _convert_animations_to_fbx(self, animations: dict[str, Any]) -> dict[str, Any]:
        """Convert animations to FBX format"""
        return {
            "keyframes": animations.get("keyframes", []),
            "duration": animations.get("duration", 1.0),
            "fps": self.config.animation_fps,
        }

    async def _write_fbx_file(self, fbx_data: dict[str, Any]) -> None:
        """Write FBX file to disk"""
        if not self.config.output_path:
            raise ValueError("Output path not specified")
        with open(self.config.output_path, "wb") as f:
            # Write header
            f.write(fbx_data["header"]["magic"])
            f.write(struct.pack("<I", fbx_data["header"]["version"]))

            # Write object data (simplified)
            objects = fbx_data["objects"]
            for obj_type, obj_data in objects.items():
                self._write_fbx_object(f, obj_type, obj_data)

    def _write_fbx_object(self, file_handle: Any, obj_type: str, obj_data: dict[str, Any]) -> None:
        """Write FBX object to file"""
        import json

        # Simplified FBX object writing
        obj_name = obj_type.encode("utf-8")
        file_handle.write(struct.pack("<I", len(obj_name)))
        file_handle.write(obj_name)

        # Write object data as JSON for simplicity
        data_bytes = json.dumps(obj_data, default=str).encode("utf-8")
        file_handle.write(struct.pack("<I", len(data_bytes)))
        file_handle.write(data_bytes)
