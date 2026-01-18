"""
OBJ format exporter
"""

import asyncio
from typing import Any

from .base import BaseExporter, ExportFormat, ExportResult


class OBJExporter(BaseExporter):
    """OBJ format exporter

    Inherits all default methods from BaseExporter.
    Only overrides get_supported_formats() and export() for OBJ-specific logic.
    """

    def get_supported_formats(self) -> list[ExportFormat]:
        return [ExportFormat.OBJ]

    async def export(self, data: dict[str, Any]) -> ExportResult:
        """Export data to OBJ format"""
        loop = asyncio.get_running_loop()
        start_time = loop.time()

        try:
            # Validate input data
            if not await self.validate_data(data):
                return ExportResult(success=False, errors=["Invalid input data for OBJ export"])

            # Create OBJ content
            obj_content = await self._create_obj_content(data)

            # Write OBJ file
            await self._write_obj_file(obj_content)

            # Write MTL file if materials are present
            if self.config.include_materials and data.get("materials"):
                await self._write_mtl_file(data["materials"])

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
                metadata={"format": "OBJ", "version": "1.0"},
            )

        except Exception as e:
            self.logger.error(f"OBJ export failed: {e}")
            return ExportResult(success=False, errors=[str(e)])

    async def _create_obj_content(self, data: dict[str, Any]) -> list[str]:
        """Create OBJ file content"""
        obj_lines = ["# Exported from Forge Export System", "# OBJ file format", ""]

        # Add MTL file reference if materials are present
        if self.config.include_materials and data.get("materials") and self.config.output_path:
            mtl_file = self.config.output_path.with_suffix(".mtl")
            obj_lines.append(f"mtllib {mtl_file.name}")
            obj_lines.append("")

        # Add mesh data
        mesh_data = data.get("mesh", {})
        if mesh_data:
            mesh_lines = await self._convert_mesh_to_obj(mesh_data)
            obj_lines.extend(mesh_lines)

        return obj_lines

    async def _convert_mesh_to_obj(self, mesh_data: dict[str, Any]) -> list[str]:
        """Convert mesh data to OBJ format"""
        obj_lines = []

        # Add vertices
        vertices = mesh_data.get("vertices", [])
        for vertex in vertices:
            if len(vertex) >= 3:
                obj_lines.append(f"v {vertex[0]} {vertex[1]} {vertex[2]}")
            else:
                obj_lines.append(
                    f"v {vertex[0] if len(vertex) > 0 else 0} {vertex[1] if len(vertex) > 1 else 0} 0"
                )

        # Add texture coordinates
        uvs = mesh_data.get("uvs", [])
        for uv in uvs:
            if len(uv) >= 2:
                obj_lines.append(f"vt {uv[0]} {uv[1]}")

        # Add normals
        normals = mesh_data.get("normals", [])
        for normal in normals:
            if len(normal) >= 3:
                obj_lines.append(f"vn {normal[0]} {normal[1]} {normal[2]}")

        # Add faces
        faces = mesh_data.get("faces", [])
        for face in faces:
            face_str = "f"
            for vertex_index in face:
                # OBJ uses 1-based indexing
                vertex_idx = vertex_index + 1

                # Format: vertex/texture/normal
                if uvs and normals:
                    face_str += f" {vertex_idx}/{vertex_idx}/{vertex_idx}"
                elif uvs:
                    face_str += f" {vertex_idx}/{vertex_idx}"
                elif normals:
                    face_str += f" {vertex_idx}//{vertex_idx}"
                else:
                    face_str += f" {vertex_idx}"

            obj_lines.append(face_str)

        return obj_lines

    async def _write_obj_file(self, obj_content: list[str]) -> None:
        """Write OBJ file to disk"""
        if not self.config.output_path:
            raise ValueError("Output path not specified")
        with open(self.config.output_path, "w") as f:
            for line in obj_content:
                f.write(line + "\n")

    async def _write_mtl_file(self, materials: dict[str, Any]) -> None:
        """Write MTL file to disk"""
        if not self.config.output_path:
            raise ValueError("Output path not specified")
        mtl_path = self.config.output_path.with_suffix(".mtl")

        mtl_lines = [
            "# Material file for Forge Export System",
            "# MTL file format",
            "",
            "newmtl Material",
        ]

        # Add material properties
        diffuse_color = materials.get("diffuse_color", [1.0, 1.0, 1.0])
        specular_color = materials.get("specular_color", [1.0, 1.0, 1.0])
        ambient_color = materials.get("ambient_color", [0.1, 0.1, 0.1])

        mtl_lines.extend(
            [
                f"Ka {ambient_color[0]} {ambient_color[1]} {ambient_color[2]}",
                f"Kd {diffuse_color[0]} {diffuse_color[1]} {diffuse_color[2]}",
                f"Ks {specular_color[0]} {specular_color[1]} {specular_color[2]}",
                f"Ns {materials.get('shininess', 32.0)}",
                f"d {materials.get('opacity', 1.0)}",
            ]
        )

        # Add texture maps if present
        if "diffuse_map" in materials:
            mtl_lines.append(f"map_Kd {materials['diffuse_map']}")

        if "normal_map" in materials:
            mtl_lines.append(f"map_Bump {materials['normal_map']}")

        with open(mtl_path, "w") as f:
            for line in mtl_lines:
                f.write(line + "\n")
