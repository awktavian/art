"""
STL (Stereolithography) exporter for 3D printing.
"""

import asyncio
import struct
from typing import Any

import numpy as np

from .base import BaseExporter, ExportFormat, ExportResult


class STLExporter(BaseExporter):
    """STL format exporter for 3D printing applications.

    Supports both ASCII and binary STL formats.
    Binary is default as it's more compact and widely supported.
    """

    def get_supported_formats(self) -> list[ExportFormat]:
        return [ExportFormat.STL]

    async def export(self, data: dict[str, Any]) -> ExportResult:
        """Export data to STL format."""
        loop = asyncio.get_running_loop()
        start_time = loop.time()

        try:
            # Validate input data
            if not await self.validate_data(data):
                return ExportResult(success=False, errors=["Invalid input data for STL export"])

            # Triangulate mesh if needed
            mesh_data = await self._prepare_mesh(data.get("mesh", {}))

            # Determine output mode (binary is standard for 3D printing)
            binary_mode = data.get("binary", True)

            if binary_mode:
                await self._write_binary_stl(mesh_data)
            else:
                await self._write_ascii_stl(mesh_data)

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
                metadata={"format": "STL", "binary": binary_mode},
            )

        except Exception as e:
            self.logger.error(f"STL export failed: {e}")
            return ExportResult(success=False, errors=[str(e)])

    async def _prepare_mesh(self, mesh_data: dict[str, Any]) -> dict[str, Any]:
        """Prepare mesh for STL export (triangulate if needed)."""
        vertices = np.array(mesh_data.get("vertices", []), dtype=np.float32)
        faces = mesh_data.get("faces", [])
        _ = mesh_data.get("normals", [])  # normals extracted but recalculated below

        # Triangulate non-triangle faces
        triangles = []
        for face in faces:
            if len(face) == 3:
                triangles.append(face)
            elif len(face) > 3:
                # Fan triangulation for convex polygons
                for i in range(1, len(face) - 1):
                    triangles.append([face[0], face[i], face[i + 1]])

        # Calculate face normals if not provided
        face_normals = []
        for tri in triangles:
            if len(tri) == 3:
                v0 = vertices[tri[0]]
                v1 = vertices[tri[1]]
                v2 = vertices[tri[2]]
                # Calculate normal using cross product
                edge1 = v1 - v0
                edge2 = v2 - v0
                normal = np.cross(edge1, edge2)
                length = np.linalg.norm(normal)
                if length > 0:
                    normal = normal / length
                else:
                    normal = np.array([0.0, 0.0, 1.0])
                face_normals.append(normal)
            else:
                face_normals.append(np.array([0.0, 0.0, 1.0]))

        return {
            "vertices": vertices,
            "triangles": triangles,
            "face_normals": np.array(face_normals, dtype=np.float32),
        }

    async def _write_binary_stl(self, mesh_data: dict[str, Any]) -> None:
        """Write binary STL file."""
        if not self.config.output_path:
            raise ValueError("Output path not specified")

        vertices = mesh_data["vertices"]
        triangles = mesh_data["triangles"]
        face_normals = mesh_data["face_normals"]

        with open(self.config.output_path, "wb") as f:
            # Write 80-byte header
            header = b"Forge Export System - Binary STL".ljust(80, b"\0")
            f.write(header)

            # Write triangle count
            f.write(struct.pack("<I", len(triangles)))

            # Write triangles
            for i, tri in enumerate(triangles):
                # Face normal
                normal = face_normals[i] if i < len(face_normals) else [0.0, 0.0, 1.0]
                f.write(struct.pack("<fff", float(normal[0]), float(normal[1]), float(normal[2])))

                # Three vertices
                for vertex_idx in tri:
                    v = vertices[vertex_idx]
                    f.write(struct.pack("<fff", float(v[0]), float(v[1]), float(v[2])))

                # Attribute byte count (unused, set[Any] to 0)
                f.write(struct.pack("<H", 0))

    async def _write_ascii_stl(self, mesh_data: dict[str, Any]) -> None:
        """Write ASCII STL file."""
        if not self.config.output_path:
            raise ValueError("Output path not specified")

        vertices = mesh_data["vertices"]
        triangles = mesh_data["triangles"]
        face_normals = mesh_data["face_normals"]

        with open(self.config.output_path, "w") as f:
            f.write("solid ForgeExport\n")

            for i, tri in enumerate(triangles):
                normal = face_normals[i] if i < len(face_normals) else [0.0, 0.0, 1.0]
                f.write(f"  facet normal {normal[0]:.6e} {normal[1]:.6e} {normal[2]:.6e}\n")
                f.write("    outer loop\n")

                for vertex_idx in tri:
                    v = vertices[vertex_idx]
                    f.write(f"      vertex {v[0]:.6e} {v[1]:.6e} {v[2]:.6e}\n")

                f.write("    endloop\n")
                f.write("  endfacet\n")

            f.write("endsolid ForgeExport\n")
