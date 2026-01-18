"""
PLY (Polygon File Format) exporter for 3D scanning and point cloud data.
"""

import asyncio
import struct
from typing import Any

import numpy as np

from .base import BaseExporter, ExportFormat, ExportResult


class PLYExporter(BaseExporter):
    """PLY format exporter for mesh and point cloud data.

    Supports both ASCII and binary PLY formats.
    Inherits all default methods from BaseExporter.
    """

    def get_supported_formats(self) -> list[ExportFormat]:
        return [ExportFormat.PLY]

    async def export(self, data: dict[str, Any]) -> ExportResult:
        """Export data to PLY format."""
        loop = asyncio.get_running_loop()
        start_time = loop.time()

        try:
            # Validate input data
            if not await self.validate_data(data):
                return ExportResult(success=False, errors=["Invalid input data for PLY export"])

            # Determine output mode (binary is more efficient)
            binary_mode = data.get("binary", True)

            # Create PLY content
            if binary_mode:
                await self._write_binary_ply(data)
            else:
                await self._write_ascii_ply(data)

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
                metadata={"format": "PLY", "binary": binary_mode},
            )

        except Exception as e:
            self.logger.error(f"PLY export failed: {e}")
            return ExportResult(success=False, errors=[str(e)])

    async def _write_ascii_ply(self, data: dict[str, Any]) -> None:
        """Write ASCII PLY file."""
        if not self.config.output_path:
            raise ValueError("Output path not specified")

        mesh_data = data.get("mesh", {})
        vertices = np.array(mesh_data.get("vertices", []), dtype=np.float32)
        faces = mesh_data.get("faces", [])
        normals = np.array(mesh_data.get("normals", []), dtype=np.float32)
        colors = np.array(mesh_data.get("vertex_colors", []), dtype=np.uint8)

        has_normals = len(normals) == len(vertices) and len(normals) > 0
        has_colors = len(colors) == len(vertices) and len(colors) > 0

        with open(self.config.output_path, "w") as f:
            # Write header
            f.write("ply\n")
            f.write("format ascii 1.0\n")
            f.write("comment Exported from Forge Export System\n")
            f.write(f"element vertex {len(vertices)}\n")
            f.write("property float x\n")
            f.write("property float y\n")
            f.write("property float z\n")

            if has_normals:
                f.write("property float nx\n")
                f.write("property float ny\n")
                f.write("property float nz\n")

            if has_colors:
                f.write("property uchar red\n")
                f.write("property uchar green\n")
                f.write("property uchar blue\n")

            if faces:
                f.write(f"element face {len(faces)}\n")
                f.write("property list[Any] uchar int vertex_indices\n")

            f.write("end_header\n")

            # Write vertices
            for i, vertex in enumerate(vertices):
                line = f"{vertex[0]} {vertex[1]} {vertex[2]}"
                if has_normals:
                    line += f" {normals[i][0]} {normals[i][1]} {normals[i][2]}"
                if has_colors:
                    line += f" {colors[i][0]} {colors[i][1]} {colors[i][2]}"
                f.write(line + "\n")

            # Write faces
            for face in faces:
                f.write(f"{len(face)} " + " ".join(str(idx) for idx in face) + "\n")

    async def _write_binary_ply(self, data: dict[str, Any]) -> None:
        """Write binary PLY file (little-endian)."""
        if not self.config.output_path:
            raise ValueError("Output path not specified")

        mesh_data = data.get("mesh", {})
        vertices = np.array(mesh_data.get("vertices", []), dtype=np.float32)
        faces = mesh_data.get("faces", [])
        normals = np.array(mesh_data.get("normals", []), dtype=np.float32)
        colors = np.array(mesh_data.get("vertex_colors", []), dtype=np.uint8)

        has_normals = len(normals) == len(vertices) and len(normals) > 0
        has_colors = len(colors) == len(vertices) and len(colors) > 0

        with open(self.config.output_path, "wb") as f:
            # Write header (ASCII)
            header_lines = [
                "ply",
                "format binary_little_endian 1.0",
                "comment Exported from Forge Export System",
                f"element vertex {len(vertices)}",
                "property float x",
                "property float y",
                "property float z",
            ]

            if has_normals:
                header_lines.extend(["property float nx", "property float ny", "property float nz"])

            if has_colors:
                header_lines.extend(
                    ["property uchar red", "property uchar green", "property uchar blue"]
                )

            if faces:
                header_lines.append(f"element face {len(faces)}")
                header_lines.append("property list[Any] uchar int vertex_indices")

            header_lines.append("end_header")

            header = "\n".join(header_lines) + "\n"
            f.write(header.encode("ascii"))

            # Write binary vertex data
            for i, vertex in enumerate(vertices):
                f.write(struct.pack("<fff", vertex[0], vertex[1], vertex[2]))
                if has_normals:
                    f.write(struct.pack("<fff", normals[i][0], normals[i][1], normals[i][2]))
                if has_colors:
                    f.write(struct.pack("<BBB", colors[i][0], colors[i][1], colors[i][2]))

            # Write binary face data
            for face in faces:
                f.write(struct.pack("<B", len(face)))  # vertex count
                for idx in face:
                    f.write(struct.pack("<i", idx))
