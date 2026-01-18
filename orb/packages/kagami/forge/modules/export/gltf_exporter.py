"""
glTF format exporter
"""

import asyncio
import base64
import json
from typing import Any

import numpy as np

from .base import BaseExporter, ExportFormat, ExportResult


class GLTFExporter(BaseExporter):
    """glTF format exporter

    Inherits all default methods from BaseExporter.
    Only overrides get_supported_formats() and export() for glTF-specific logic.
    """

    def get_supported_formats(self) -> list[ExportFormat]:
        return [ExportFormat.GLTF, ExportFormat.GLB]

    async def export(self, data: dict[str, Any]) -> ExportResult:
        """Export data to glTF format"""
        loop = asyncio.get_running_loop()
        start_time = loop.time()

        try:
            # Validate input data
            if not await self.validate_data(data):
                return ExportResult(success=False, errors=["Invalid input data for glTF export"])

            # Create glTF structure
            gltf_data = await self._create_gltf_structure(data)

            # Write glTF file
            if self.config.format == ExportFormat.GLTF:
                await self._write_gltf_file(gltf_data)
            else:
                await self._write_glb_file(gltf_data)

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
                metadata={"format": "glTF", "version": "2.0"},
            )

        except Exception as e:
            self.logger.error(f"glTF export failed: {e}")
            return ExportResult(success=False, errors=[str(e)])

    async def _create_gltf_structure(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create glTF structure"""
        # Create basic glTF structure
        gltf = {
            "asset": {"version": "2.0", "generator": "Forge Export System"},
            "scenes": [{"nodes": [0]}],
            "scene": 0,
            "nodes": [],
            "meshes": [],
            "materials": [],
            "accessors": [],
            "bufferViews": [],
            "buffers": [],
        }

        # Add mesh data
        mesh_data = data.get("mesh", {})
        if mesh_data:
            await self._add_mesh_to_gltf(gltf, mesh_data)

        # Add materials
        materials = data.get("materials", {})
        if materials:
            await self._add_materials_to_gltf(gltf, materials)

        # Add animations
        animations = data.get("animations", {})
        if animations:
            await self._add_animations_to_gltf(gltf, animations)

        return gltf

    async def _add_mesh_to_gltf(self, gltf: dict[str, Any], mesh_data: dict[str, Any]) -> None:
        """Add mesh data to glTF structure"""
        vertices = np.array(mesh_data.get("vertices", []), dtype=np.float32)
        faces = np.array(mesh_data.get("faces", []), dtype=np.uint16)
        normals = np.array(mesh_data.get("normals", []), dtype=np.float32)

        # Create buffer for vertex data
        buffer_data = b""

        # Add vertices
        vertex_buffer = vertices.tobytes()
        buffer_data += vertex_buffer

        # Add buffer view for vertices
        gltf["bufferViews"].append(
            {
                "buffer": 0,
                "byteOffset": 0,
                "byteLength": len(vertex_buffer),
                "target": 34962,  # ARRAY_BUFFER
            }
        )

        # Add accessor for vertices
        gltf["accessors"].append(
            {
                "bufferView": 0,
                "byteOffset": 0,
                "componentType": 5126,  # FLOAT
                "count": len(vertices),
                "type": "VEC3",
                "min": vertices.min(axis=0).tolist(),
                "max": vertices.max(axis=0).tolist(),
            }
        )

        # Add normals if available
        if len(normals) > 0:
            normal_buffer = normals.tobytes()
            buffer_data += normal_buffer

            gltf["bufferViews"].append(
                {
                    "buffer": 0,
                    "byteOffset": len(vertex_buffer),
                    "byteLength": len(normal_buffer),
                    "target": 34962,  # ARRAY_BUFFER
                }
            )

            gltf["accessors"].append(
                {
                    "bufferView": 1,
                    "byteOffset": 0,
                    "componentType": 5126,  # FLOAT
                    "count": len(normals),
                    "type": "VEC3",
                }
            )

        # Add indices
        if len(faces) > 0:
            index_buffer = faces.tobytes()
            buffer_data += index_buffer

            gltf["bufferViews"].append(
                {
                    "buffer": 0,
                    "byteOffset": (
                        len(vertex_buffer) + len(normal_buffer)
                        if len(normals) > 0
                        else len(vertex_buffer)
                    ),
                    "byteLength": len(index_buffer),
                    "target": 34963,  # ELEMENT_ARRAY_BUFFER
                }
            )

            gltf["accessors"].append(
                {
                    "bufferView": 2,
                    "byteOffset": 0,
                    "componentType": 5123,  # UNSIGNED_SHORT
                    "count": len(faces.flatten()),
                    "type": "SCALAR",
                }
            )

        # Add buffer
        gltf["buffers"].append(
            {
                "byteLength": len(buffer_data),
                "uri": "data:application/octet-stream;base64,"
                + base64.b64encode(buffer_data).decode("utf-8"),
            }
        )

        # Add mesh
        primitive: dict[str, Any] = {"attributes": {"POSITION": 0}}

        if len(normals) > 0:
            primitive["attributes"]["NORMAL"] = 1

        if len(faces) > 0:
            primitive["indices"] = 2

        gltf["meshes"].append({"primitives": [primitive]})

        # Add node
        gltf["nodes"].append({"mesh": 0})

    async def _add_materials_to_gltf(self, gltf: dict[str, Any], materials: dict[str, Any]) -> None:
        """Add materials to glTF structure"""
        material = {
            "pbrMetallicRoughness": {
                "baseColorFactor": materials.get("diffuse_color", [1.0, 1.0, 1.0, 1.0]),
                "metallicFactor": materials.get("metallic", 0.0),
                "roughnessFactor": materials.get("roughness", 1.0),
            }
        }

        gltf["materials"].append(material)

    async def _add_animations_to_gltf(
        self, gltf: dict[str, Any], animations: dict[str, Any]
    ) -> None:
        """Add animations to glTF structure"""
        if "animations" not in gltf:
            gltf["animations"] = []

        animation = {
            "name": animations.get("name", "Animation"),
            "channels": [],
            "samplers": [],
        }

        # Handle motion sequence data
        motion_sequence = animations.get("motion_sequence")
        if motion_sequence is not None:
            # Convert motion sequence to glTF animation
            motion_data = np.array(motion_sequence)

            if motion_data.ndim == 3:  # [frames, joints, xyz]
                num_frames, num_joints, _ = motion_data.shape
                fps = animations.get("fps", 20)

                # Create time array
                time_array = np.linspace(0, num_frames / fps, num_frames, dtype=np.float32)

                # Add time accessor
                time_buffer = time_array.tobytes()
                buffer_data = gltf["buffers"][0]["uri"]

                # Decode existing buffer data
                if buffer_data.startswith("data:application/octet-stream;base64,"):
                    existing_data = base64.b64decode(buffer_data.split(",")[1])
                    new_data = existing_data + time_buffer
                else:
                    new_data = time_buffer

                # Update buffer
                gltf["buffers"][0]["uri"] = (
                    "data:application/octet-stream;base64,"
                    + base64.b64encode(new_data).decode("utf-8")
                )
                gltf["buffers"][0]["byteLength"] = len(new_data)

                # Add time buffer view
                time_buffer_view_index = len(gltf["bufferViews"])
                gltf["bufferViews"].append(
                    {
                        "buffer": 0,
                        "byteOffset": len(existing_data),
                        "byteLength": len(time_buffer),
                        "target": 34962,  # ARRAY_BUFFER
                    }
                )

                # Add time accessor
                time_accessor_index = len(gltf["accessors"])
                gltf["accessors"].append(
                    {
                        "bufferView": time_buffer_view_index,
                        "byteOffset": 0,
                        "componentType": 5126,  # FLOAT
                        "count": num_frames,
                        "type": "SCALAR",
                        "min": [float(time_array.min())],
                        "max": [float(time_array.max())],
                    }
                )

                # Add animation for each joint
                for joint_idx in range(min(num_joints, 22)):  # Limit to reasonable joint count
                    joint_positions = motion_data[:, joint_idx, :].astype(np.float32)
                    pos_buffer = joint_positions.tobytes()

                    # Update buffer data
                    current_data = base64.b64decode(gltf["buffers"][0]["uri"].split(",")[1])
                    new_data = current_data + pos_buffer
                    gltf["buffers"][0]["uri"] = (
                        "data:application/octet-stream;base64,"
                        + base64.b64encode(new_data).decode("utf-8")
                    )
                    gltf["buffers"][0]["byteLength"] = len(new_data)

                    # Add position buffer view
                    pos_buffer_view_index = len(gltf["bufferViews"])
                    gltf["bufferViews"].append(
                        {
                            "buffer": 0,
                            "byteOffset": len(current_data),
                            "byteLength": len(pos_buffer),
                            "target": 34962,  # ARRAY_BUFFER
                        }
                    )

                    # Add position accessor
                    pos_accessor_index = len(gltf["accessors"])
                    gltf["accessors"].append(
                        {
                            "bufferView": pos_buffer_view_index,
                            "byteOffset": 0,
                            "componentType": 5126,  # FLOAT
                            "count": num_frames,
                            "type": "VEC3",
                            "min": joint_positions.min(axis=0).tolist(),
                            "max": joint_positions.max(axis=0).tolist(),
                        }
                    )

                    # Add sampler
                    sampler_index = len(animation["samplers"])
                    animation["samplers"].append(
                        {
                            "input": time_accessor_index,
                            "output": pos_accessor_index,
                            "interpolation": "LINEAR",
                        }
                    )

                    # Add channel
                    animation["channels"].append(
                        {
                            "sampler": sampler_index,
                            "target": {"node": joint_idx, "path": "translation"},
                        }
                    )

        # Handle simple keyframes
        elif animations.get("keyframes"):
            animation["samplers"].append(
                {
                    "input": len(gltf["accessors"]),
                    "output": len(gltf["accessors"]) + 1,
                    "interpolation": "LINEAR",
                }
            )

            animation["channels"].append(
                {"sampler": 0, "target": {"node": 0, "path": "translation"}}
            )

        if animation["channels"]:  # Only add if we have channels
            gltf["animations"].append(animation)

    async def _write_gltf_file(self, gltf_data: dict[str, Any]) -> None:
        """Write glTF file to disk"""
        if not self.config.output_path:
            raise ValueError("Output path not specified")
        with open(self.config.output_path, "w") as f:
            json.dump(gltf_data, f, indent=2)

    async def _write_glb_file(self, gltf_data: dict[str, Any]) -> None:
        """Write GLB file to disk"""
        import struct

        # Convert to binary format (simplified)
        json_data = json.dumps(gltf_data).encode("utf-8")

        if not self.config.output_path:
            raise ValueError("Output path not specified")
        with open(self.config.output_path, "wb") as f:
            # GLB header
            f.write(b"glTF")  # magic
            f.write(struct.pack("<I", 2))  # version
            f.write(struct.pack("<I", 20 + len(json_data)))  # length

            # JSON chunk
            f.write(struct.pack("<I", len(json_data)))  # chunk length
            f.write(b"JSON")  # chunk type
            f.write(json_data)  # chunk data
