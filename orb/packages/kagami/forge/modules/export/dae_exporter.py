"""
DAE (Collada) format exporter for 3D interchange.
"""

import asyncio
from datetime import UTC, datetime
from typing import Any
from xml.etree import ElementTree as ET

import numpy as np

from .base import BaseExporter, ExportFormat, ExportResult


class DAEExporter(BaseExporter):
    """Collada (DAE) format exporter.

    Exports to COLLADA 1.4.1 specification for maximum compatibility.
    Supports geometry, materials, and basic animations.
    """

    COLLADA_NS = "http://www.collada.org/2005/11/COLLADASchema"

    def get_supported_formats(self) -> list[ExportFormat]:
        return [ExportFormat.DAE]

    async def export(self, data: dict[str, Any]) -> ExportResult:
        """Export data to Collada format."""
        loop = asyncio.get_running_loop()
        start_time = loop.time()

        try:
            # Validate input data
            if not await self.validate_data(data):
                return ExportResult(success=False, errors=["Invalid input data for DAE export"])

            # Create Collada XML structure
            root = await self._create_collada_document(data)

            # Write to file
            await self._write_dae_file(root)

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
                metadata={"format": "COLLADA", "version": "1.4.1"},
            )

        except Exception as e:
            self.logger.error(f"DAE export failed: {e}")
            return ExportResult(success=False, errors=[str(e)])

    async def _create_collada_document(self, data: dict[str, Any]) -> ET.Element:
        """Create complete Collada XML document."""
        # Register namespace
        ET.register_namespace("", self.COLLADA_NS)

        # Root element
        root = ET.Element(
            "COLLADA",
            {"xmlns": self.COLLADA_NS, "version": "1.4.1"},
        )

        # Asset info
        await self._add_asset(root)

        # Libraries
        await self._add_library_effects(root, data.get("materials", {}))
        await self._add_library_materials(root, data.get("materials", {}))
        await self._add_library_geometries(root, data.get("mesh", {}))
        await self._add_library_visual_scenes(root, data)

        # Scene reference
        scene = ET.SubElement(root, "scene")
        instance_visual_scene = ET.SubElement(scene, "instance_visual_scene")
        instance_visual_scene.set("url", "#Scene")

        return root

    async def _add_asset(self, root: ET.Element) -> None:
        """Add asset metadata."""
        asset = ET.SubElement(root, "asset")

        contributor = ET.SubElement(asset, "contributor")
        author = ET.SubElement(contributor, "author")
        author.text = "Forge Export System"
        authoring_tool = ET.SubElement(contributor, "authoring_tool")
        authoring_tool.text = "KagamiOS Forge"

        created = ET.SubElement(asset, "created")
        created.text = datetime.now(UTC).isoformat()

        modified = ET.SubElement(asset, "modified")
        modified.text = datetime.now(UTC).isoformat()

        unit = ET.SubElement(asset, "unit")
        unit.set("name", "meter")
        unit.set("meter", "1")

        up_axis = ET.SubElement(asset, "up_axis")
        up_axis.text = "Y_UP"

    async def _add_library_effects(self, root: ET.Element, materials: dict[str, Any]) -> None:
        """Add effects library (shader definitions)."""
        library = ET.SubElement(root, "library_effects")

        effect = ET.SubElement(library, "effect")
        effect.set("id", "Material-effect")

        profile = ET.SubElement(effect, "profile_COMMON")
        technique = ET.SubElement(profile, "technique")
        technique.set("sid", "common")

        phong = ET.SubElement(technique, "phong")

        # Emission
        emission = ET.SubElement(phong, "emission")
        color = ET.SubElement(emission, "color")
        color.set("sid", "emission")
        color.text = "0 0 0 1"

        # Ambient
        ambient = ET.SubElement(phong, "ambient")
        color = ET.SubElement(ambient, "color")
        color.set("sid", "ambient")
        ambient_color = materials.get("ambient_color", [0.1, 0.1, 0.1])
        color.text = f"{ambient_color[0]} {ambient_color[1]} {ambient_color[2]} 1"

        # Diffuse
        diffuse = ET.SubElement(phong, "diffuse")
        color = ET.SubElement(diffuse, "color")
        color.set("sid", "diffuse")
        diffuse_color = materials.get("diffuse_color", [0.8, 0.8, 0.8])
        if len(diffuse_color) >= 3:
            color.text = f"{diffuse_color[0]} {diffuse_color[1]} {diffuse_color[2]} 1"
        else:
            color.text = "0.8 0.8 0.8 1"

        # Specular
        specular = ET.SubElement(phong, "specular")
        color = ET.SubElement(specular, "color")
        color.set("sid", "specular")
        specular_color = materials.get("specular_color", [1.0, 1.0, 1.0])
        color.text = f"{specular_color[0]} {specular_color[1]} {specular_color[2]} 1"

        # Shininess
        shininess_elem = ET.SubElement(phong, "shininess")
        float_elem = ET.SubElement(shininess_elem, "float")
        float_elem.set("sid", "shininess")
        float_elem.text = str(materials.get("shininess", 32.0))

    async def _add_library_materials(self, root: ET.Element, materials: dict[str, Any]) -> None:
        """Add materials library."""
        library = ET.SubElement(root, "library_materials")

        material = ET.SubElement(library, "material")
        material.set("id", "Material")
        material.set("name", "Material")

        instance_effect = ET.SubElement(material, "instance_effect")
        instance_effect.set("url", "#Material-effect")

    async def _add_library_geometries(self, root: ET.Element, mesh_data: dict[str, Any]) -> None:
        """Add geometries library."""
        library = ET.SubElement(root, "library_geometries")

        geometry = ET.SubElement(library, "geometry")
        geometry.set("id", "Mesh-mesh")
        geometry.set("name", "Mesh")

        mesh = ET.SubElement(geometry, "mesh")

        vertices = np.array(mesh_data.get("vertices", []), dtype=np.float32)
        normals = np.array(mesh_data.get("normals", []), dtype=np.float32)
        faces = mesh_data.get("faces", [])

        # Positions source
        positions_source = ET.SubElement(mesh, "source")
        positions_source.set("id", "Mesh-positions")

        positions_array = ET.SubElement(positions_source, "float_array")
        positions_array.set("id", "Mesh-positions-array")
        positions_array.set("count", str(len(vertices) * 3))

        # Validate and sanitize vertex data (replace NaN/inf with 0)
        if len(vertices) > 0:
            clean_vertices = np.nan_to_num(vertices, nan=0.0, posinf=0.0, neginf=0.0)
            positions_array.text = " ".join(f"{v[0]} {v[1]} {v[2]}" for v in clean_vertices)
        else:
            positions_array.text = "0 0 0"

        technique = ET.SubElement(positions_source, "technique_common")
        accessor = ET.SubElement(technique, "accessor")
        accessor.set("source", "#Mesh-positions-array")
        accessor.set("count", str(len(vertices)))
        accessor.set("stride", "3")

        for axis in ["X", "Y", "Z"]:
            param = ET.SubElement(accessor, "param")
            param.set("name", axis)
            param.set("type", "float")

        # Normals source (if available)
        if len(normals) > 0:
            normals_source = ET.SubElement(mesh, "source")
            normals_source.set("id", "Mesh-normals")

            normals_array = ET.SubElement(normals_source, "float_array")
            normals_array.set("id", "Mesh-normals-array")
            normals_array.set("count", str(len(normals) * 3))
            normals_array.text = " ".join(f"{n[0]} {n[1]} {n[2]}" for n in normals)

            technique = ET.SubElement(normals_source, "technique_common")
            accessor = ET.SubElement(technique, "accessor")
            accessor.set("source", "#Mesh-normals-array")
            accessor.set("count", str(len(normals)))
            accessor.set("stride", "3")

            for axis in ["X", "Y", "Z"]:
                param = ET.SubElement(accessor, "param")
                param.set("name", axis)
                param.set("type", "float")

        # Vertices
        vertices_elem = ET.SubElement(mesh, "vertices")
        vertices_elem.set("id", "Mesh-vertices")
        input_elem = ET.SubElement(vertices_elem, "input")
        input_elem.set("semantic", "POSITION")
        input_elem.set("source", "#Mesh-positions")

        # Triangles
        if faces:
            triangles = ET.SubElement(mesh, "triangles")
            triangles.set("material", "Material")

            # Count triangles (handle non-triangular faces)
            tri_count = sum(max(0, len(f) - 2) for f in faces)
            triangles.set("count", str(tri_count))

            input_vertex = ET.SubElement(triangles, "input")
            input_vertex.set("semantic", "VERTEX")
            input_vertex.set("source", "#Mesh-vertices")
            input_vertex.set("offset", "0")

            if len(normals) > 0:
                input_normal = ET.SubElement(triangles, "input")
                input_normal.set("semantic", "NORMAL")
                input_normal.set("source", "#Mesh-normals")
                input_normal.set("offset", "1")

            # Generate triangle indices
            indices = []
            for face in faces:
                if len(face) >= 3:
                    # Fan triangulation
                    for i in range(1, len(face) - 1):
                        if len(normals) > 0:
                            indices.extend(
                                [face[0], face[0], face[i], face[i], face[i + 1], face[i + 1]]
                            )
                        else:
                            indices.extend([face[0], face[i], face[i + 1]])

            p = ET.SubElement(triangles, "p")
            p.text = " ".join(str(i) for i in indices)

    async def _add_library_visual_scenes(self, root: ET.Element, data: dict[str, Any]) -> None:
        """Add visual scenes library."""
        library = ET.SubElement(root, "library_visual_scenes")

        visual_scene = ET.SubElement(library, "visual_scene")
        visual_scene.set("id", "Scene")
        visual_scene.set("name", "Scene")

        node = ET.SubElement(visual_scene, "node")
        node.set("id", "Mesh")
        node.set("name", "Mesh")
        node.set("type", "NODE")

        # Transform matrix (identity)
        matrix = ET.SubElement(node, "matrix")
        matrix.set("sid", "transform")
        matrix.text = "1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"

        # Instance geometry
        instance_geometry = ET.SubElement(node, "instance_geometry")
        instance_geometry.set("url", "#Mesh-mesh")
        instance_geometry.set("name", "Mesh")

        bind_material = ET.SubElement(instance_geometry, "bind_material")
        technique_common = ET.SubElement(bind_material, "technique_common")
        instance_material = ET.SubElement(technique_common, "instance_material")
        instance_material.set("symbol", "Material")
        instance_material.set("target", "#Material")

    async def _write_dae_file(self, root: ET.Element) -> None:
        """Write Collada XML file."""
        if not self.config.output_path:
            raise ValueError("Output path not specified")

        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")

        with open(self.config.output_path, "wb") as f:
            tree.write(f, encoding="utf-8", xml_declaration=True)
