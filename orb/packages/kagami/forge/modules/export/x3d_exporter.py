"""
X3D format exporter for web-based 3D content.
"""

import asyncio
from typing import Any
from xml.etree import ElementTree as ET

import numpy as np

from .base import BaseExporter, ExportFormat, ExportResult


class X3DExporter(BaseExporter):
    """X3D format exporter for web 3D content.

    Exports to X3D 3.3 specification (successor to VRML).
    Supports indexed face sets, materials, and basic transforms.
    """

    def get_supported_formats(self) -> list[ExportFormat]:
        return [ExportFormat.X3D]

    async def export(self, data: dict[str, Any]) -> ExportResult:
        """Export data to X3D format."""
        loop = asyncio.get_running_loop()
        start_time = loop.time()

        try:
            # Validate input data
            if not await self.validate_data(data):
                return ExportResult(success=False, errors=["Invalid input data for X3D export"])

            # Create X3D XML structure
            root = await self._create_x3d_document(data)

            # Write to file
            await self._write_x3d_file(root)

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
                metadata={"format": "X3D", "version": "3.3"},
            )

        except Exception as e:
            self.logger.error(f"X3D export failed: {e}")
            return ExportResult(success=False, errors=[str(e)])

    async def _create_x3d_document(self, data: dict[str, Any]) -> ET.Element:
        """Create complete X3D XML document."""
        # Root X3D element
        root = ET.Element("X3D")
        root.set("profile", "Interchange")
        root.set("version", "3.3")
        root.set("xmlns:xsd", "http://www.w3.org/2001/XMLSchema-instance")
        root.set(
            "xsd:noNamespaceSchemaLocation",
            "http://www.web3d.org/specifications/x3d-3.3.xsd",
        )

        # Head with metadata
        head = ET.SubElement(root, "head")
        meta = ET.SubElement(head, "meta")
        meta.set("name", "generator")
        meta.set("content", "Forge Export System")

        meta2 = ET.SubElement(head, "meta")
        meta2.set("name", "description")
        meta2.set("content", "3D model exported from KagamiOS Forge")

        # Scene
        scene = ET.SubElement(root, "Scene")

        # Add navigation info
        nav_info = ET.SubElement(scene, "NavigationInfo")
        nav_info.set("headlight", "true")

        # Add directional light
        light = ET.SubElement(scene, "DirectionalLight")
        light.set("direction", "0 -1 -1")
        light.set("intensity", "0.8")

        # Add background
        background = ET.SubElement(scene, "Background")
        background.set("skyColor", "0.8 0.8 0.9")

        # Add viewpoint
        viewpoint = ET.SubElement(scene, "Viewpoint")
        viewpoint.set("description", "Default View")
        viewpoint.set("position", "0 1 5")

        # Add shape with geometry
        await self._add_shape(scene, data)

        return root

    async def _add_shape(self, scene: ET.Element, data: dict[str, Any]) -> None:
        """Add shape with geometry and appearance."""
        mesh_data = data.get("mesh", {})
        materials = data.get("materials", {})

        # Transform node
        transform = ET.SubElement(scene, "Transform")
        transform.set("DEF", "MeshTransform")

        # Shape
        shape = ET.SubElement(transform, "Shape")

        # Appearance
        appearance = ET.SubElement(shape, "Appearance")

        # Material
        material = ET.SubElement(appearance, "Material")

        diffuse_color = materials.get("diffuse_color", [0.8, 0.8, 0.8])
        if len(diffuse_color) >= 3:
            material.set(
                "diffuseColor", f"{diffuse_color[0]} {diffuse_color[1]} {diffuse_color[2]}"
            )

        specular_color = materials.get("specular_color", [1.0, 1.0, 1.0])
        material.set(
            "specularColor", f"{specular_color[0]} {specular_color[1]} {specular_color[2]}"
        )

        ambient_intensity = materials.get("ambient_intensity", 0.2)
        material.set("ambientIntensity", str(ambient_intensity))

        shininess = materials.get("shininess", 0.2)
        # X3D shininess is 0-1, convert if needed
        if shininess > 1:
            shininess = shininess / 128.0
        material.set("shininess", str(min(1.0, shininess)))

        transparency = 1.0 - materials.get("opacity", 1.0)
        material.set("transparency", str(transparency))

        # Geometry - IndexedFaceSet
        await self._add_indexed_face_set(shape, mesh_data)

    async def _add_indexed_face_set(self, shape: ET.Element, mesh_data: dict[str, Any]) -> None:
        """Add IndexedFaceSet geometry."""
        vertices = np.array(mesh_data.get("vertices", []), dtype=np.float32)
        normals = np.array(mesh_data.get("normals", []), dtype=np.float32)
        uvs = np.array(mesh_data.get("uvs", []), dtype=np.float32)
        faces = mesh_data.get("faces", [])

        if len(vertices) == 0:
            # Add placeholder geometry
            box = ET.SubElement(shape, "Box")
            box.set("size", "1 1 1")
            return

        # Create IndexedFaceSet
        ifs = ET.SubElement(shape, "IndexedFaceSet")
        ifs.set("solid", "false")
        ifs.set("creaseAngle", "1.0")

        # Build coordIndex (face indices with -1 separators)
        coord_indices = []
        for face in faces:
            coord_indices.extend([str(i) for i in face])
            coord_indices.append("-1")

        if coord_indices:
            ifs.set("coordIndex", " ".join(coord_indices))

        # Normal indices (if normals provided per-vertex)
        if len(normals) > 0:
            ifs.set("normalPerVertex", "true")

        # Texture coordinate indices
        if len(uvs) > 0:
            tex_coord_indices = []
            for face in faces:
                tex_coord_indices.extend([str(i) for i in face])
                tex_coord_indices.append("-1")
            ifs.set("texCoordIndex", " ".join(tex_coord_indices))

        # Coordinate node
        coord = ET.SubElement(ifs, "Coordinate")
        coord.set("DEF", "MeshCoords")
        point_str = " ".join(f"{v[0]} {v[1]} {v[2]}" for v in vertices)
        coord.set("point", point_str)

        # Normal node (if available)
        if len(normals) > 0:
            normal = ET.SubElement(ifs, "Normal")
            normal.set("DEF", "MeshNormals")
            vector_str = " ".join(f"{n[0]} {n[1]} {n[2]}" for n in normals)
            normal.set("vector", vector_str)

        # TextureCoordinate node (if available)
        if len(uvs) > 0:
            tex_coord = ET.SubElement(ifs, "TextureCoordinate")
            tex_coord.set("DEF", "MeshTexCoords")
            point_str = " ".join(f"{uv[0]} {uv[1]}" for uv in uvs)
            tex_coord.set("point", point_str)

    async def _write_x3d_file(self, root: ET.Element) -> None:
        """Write X3D XML file."""
        if not self.config.output_path:
            raise ValueError("Output path not specified")

        # Add XML declaration and DOCTYPE
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")

        with open(self.config.output_path, "wb") as f:
            # Write XML declaration
            f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
            # Write DOCTYPE
            f.write(
                b'<!DOCTYPE X3D PUBLIC "ISO//Web3D//DTD X3D 3.3//EN" '
                b'"http://www.web3d.org/specifications/x3d-3.3.dtd">\n'
            )
            # Write the tree without declaration (we wrote it manually)
            tree.write(f, encoding="utf-8", xml_declaration=False)
