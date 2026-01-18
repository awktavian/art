"""
USD format exporter
"""

import asyncio
from pathlib import Path
from typing import Any

import numpy as np

from .base import BaseExporter, ExportFormat, ExportResult


class USDExporter(BaseExporter):
    """USD format exporter

    Inherits all default methods from BaseExporter.
    Only overrides get_supported_formats() and export() for USD-specific logic.
    """

    def get_supported_formats(self) -> list[ExportFormat]:
        return [ExportFormat.USD]

    async def export(self, data: dict[str, Any]) -> ExportResult:
        """Export data to USD format"""
        loop = asyncio.get_running_loop()
        start_time = loop.time()

        try:
            # Validate input data
            if not await self.validate_data(data):
                return ExportResult(success=False, errors=["Invalid input data for USD export"])

            # Create USD structure
            usd_data = await self._create_usd_structure(data)

            # Write USD file
            await self._write_usd_file(usd_data)

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
                metadata={"format": "USD", "version": "22.11"},
            )

        except Exception as e:
            self.logger.error(f"USD export failed: {e}")
            return ExportResult(success=False, errors=[str(e)])

    async def _create_usd_structure(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create USD structure"""
        usd_content: list[str] = []

        # Stage metadata
        up_axis = data.get("metadata", {}).get("upAxis", "Y")
        meters_per_unit = float(data.get("metadata", {}).get("metersPerUnit", 1.0))
        tps = int(data.get("metadata", {}).get("timeCodesPerSecond", 24))

        # Add USD header and stage metadata
        usd_content.extend(
            [
                "#usda 1.0",
                "(",
                '    defaultPrim = "Model"',
                f'    upAxis = "{up_axis}"',
                f"    metersPerUnit = {meters_per_unit}",
                f"    timeCodesPerSecond = {tps}",
                ")",
                "",
            ]
        )

        # Add mesh data
        mesh_data = data.get("mesh", {})
        if mesh_data:
            mesh_lines = await self._convert_mesh_to_usd(mesh_data)
            usd_content.extend(mesh_lines)

        # Add materials
        materials = data.get("materials", {})
        if materials:
            material_lines = await self._convert_materials_to_usd(materials)
            usd_content.extend(material_lines)

        # Add animations
        animations = data.get("animations", {})
        if animations:
            animation_lines = await self._convert_animations_to_usd(animations)
            usd_content.extend(animation_lines)

        return {"content": usd_content}

    async def _convert_mesh_to_usd(self, mesh_data: dict[str, Any]) -> list[str]:
        """Convert mesh data to USD format"""
        vertices = self._to_ndarray(mesh_data.get("vertices", []))
        faces = self._to_ndarray(mesh_data.get("faces", []))
        normals = self._to_ndarray(mesh_data.get("normals", []))

        # Compute extent if possible
        extent_lines: list[str] = []
        if vertices.size > 0:
            vmin = vertices.min(axis=0)
            vmax = vertices.max(axis=0)
            extent_lines = [
                f"        point3f[2] extent = [({vmin[0]:.6g}, {vmin[1]:.6g}, {vmin[2]:.6g}), ({vmax[0]:.6g}, {vmax[1]:.6g}, {vmax[2]:.6g})]",
            ]

        usd_lines = [
            'def Xform "Model"',
            "{",
            '    def Mesh "Mesh"',
            "    {",
            f"        point3f[] points = {self._format_points(vertices)}",
            f"        int[] faceVertexCounts = {self._format_face_counts(faces)}",
            f"        int[] faceVertexIndices = {self._format_face_indices(faces)}",
        ]

        if extent_lines:
            usd_lines.extend(extent_lines)

        if normals.size > 0:
            usd_lines.append(f"        normal3f[] normals = {self._format_points(normals)}")

        # Bind material if present
        usd_lines.append("        rel material:binding = </Material>")

        usd_lines.extend(["    }", "}"])

        return usd_lines

    async def _convert_materials_to_usd(self, materials: dict[str, Any]) -> list[str]:
        """Convert materials to USD format"""
        diffuse_color = materials.get("diffuse_color", [1.0, 1.0, 1.0])
        dc = (
            tuple(float(x) for x in diffuse_color[:3])
            if isinstance(diffuse_color, (list, tuple, np.ndarray))
            else (1.0, 1.0, 1.0)
        )

        return [
            'def Material "Material"',
            "{",
            "    token outputs:surface.connect = </Material/PreviewSurface.outputs:surface>",
            '    def Shader "PreviewSurface"',
            "    {",
            '        uniform token info:id = "UsdPreviewSurface"',
            f"        color3f inputs:diffuseColor = {dc}",
            "        token outputs:surface",
            "    }",
            "}",
        ]

    async def _convert_animations_to_usd(self, animations: dict[str, Any]) -> list[str]:
        """Convert animations to USD format

        Expects animations like { "keyframes": [ {"time": <float_or_int>, "translate": [x,y,z]} ... ] }
        """
        keyframes = animations.get("keyframes", [])

        if not keyframes:
            return []

        # Build timeSamples dict[str, Any] lines
        samples: list[str] = []
        for kf in keyframes:
            t = kf.get("time", 0)
            tr = kf.get("translate", [0, 0, 0])
            tr = [
                float(tr[0] if len(tr) > 0 else 0),
                float(tr[1] if len(tr) > 1 else 0),
                float(tr[2] if len(tr) > 2 else 0),
            ]
            # USD requires integer or float time keys; format compactly
            if float(t).is_integer():
                t_str = f"{int(t)}"
            else:
                t_str = f"{float(t):.6g}"
            samples.append(f"        {t_str}: ({tr[0]:.6g}, {tr[1]:.6g}, {tr[2]:.6g}),")

        if samples:
            # Remove trailing comma from last sample for cleaner output
            samples[-1] = samples[-1].rstrip(",")

        return [
            'def Xform "AnimatedTransform"',
            "{",
            "    double3 xformOp:translate.timeSamples = {",
            *samples,
            "    }",
            '    uniform token[] xformOpOrder = ["xformOp:translate"]',
            "}",
        ]

    def _format_points(self, points: Any) -> str:
        """Format points for USD"""
        arr = self._to_ndarray(points)
        if arr.size == 0:
            return "[]"
        # Ensure Nx3
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        formatted = []
        for row in arr:
            x = float(row[0]) if row.size > 0 else 0.0
            y = float(row[1]) if row.size > 1 else 0.0
            z = float(row[2]) if row.size > 2 else 0.0
            formatted.append(f"({x:.6g}, {y:.6g}, {z:.6g})")
        return f"[{', '.join(formatted)}]"

    def _format_face_counts(self, faces: Any) -> str:
        """Format face vertex counts for USD"""
        arr = self._to_ndarray(faces)
        if arr.size == 0:
            return "[]"
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        counts = [arr.shape[1]] * arr.shape[0]
        return f"[{', '.join(str(c) for c in counts)}]"

    def _format_face_indices(self, faces: Any) -> str:
        """Format face vertex indices for USD"""
        arr = self._to_ndarray(faces)
        if arr.size == 0:
            return "[]"
        flat = arr.reshape(-1)
        return f"[{', '.join(str(int(v)) for v in flat)}]"

    def _to_ndarray(self, value: Any) -> np.ndarray:
        """Safely convert lists or arrays to numpy ndarray[Any, Any] with float64 or int64 as appropriate."""
        if isinstance(value, np.ndarray):
            return value
        try:
            arr = np.asarray(value)
            return arr
        except Exception:
            return np.array([])

    async def _write_usd_file(self, usd_data: dict[str, Any]) -> None:
        """Write USD file to disk"""
        if not self.config.output_path:
            raise ValueError("Output path not specified") from None
        output_path: Path = self.config.output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            for line in usd_data["content"]:
                f.write(line + "\n")
