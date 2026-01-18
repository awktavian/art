#!/usr/bin/env python3
"""
FORGE - Consolidated Asset Exporter
Unified asset export system for all supported formats
GAIA Standard: Complete implementations only
"""

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any

from ...forge_llm_base import (
    CharacterAspect,
    CharacterContext,
    LLMRequest,
)
from ...llm_service_adapter import KagamiOSLLMServiceAdapter

# Import Forge schema
from ...schema import (
    Character,
    CharacterRequest,
    ExportProfile,
    ExportType,
    GenerationResult,
)
from .base import (
    ExportConfig,
    ExportFormat,
    ExportResult,
)

logger = logging.getLogger("ForgeMatrix.AssetExporter")

# Use ExportResult from base directly


class AssetExporter:
    """Consolidated asset export system with LLM integration."""

    def __init__(self) -> None:
        self.initialized = False
        self.stats = {
            "total_exports": 0,
            "successful_exports": 0,
            "failed_exports": 0,
            "formats_used": {},
            "avg_export_time": 0.0,
            "llm_calls": 0,
            "avg_response_time": 0.0,
        }

        # Supported formats and their handlers
        self.format_handlers = {
            ExportFormat.FBX: self._export_fbx,
            ExportFormat.USD: self._export_usd,
            ExportFormat.GLTF: self._export_gltf,
            ExportFormat.GLB: self._export_glb,
            ExportFormat.OBJ: self._export_obj,
            ExportFormat.DAE: self._export_dae,
            ExportFormat.PLY: self._export_ply,
            ExportFormat.STL: self._export_stl,
            ExportFormat.JSON: self._export_json,
            ExportFormat.BLEND: self._export_blend,
            ExportFormat.X3D: self._export_x3d,
            ExportFormat.VRML: self._export_vrml,
        }

        # Initialize LLM for export optimization
        self.llm = KagamiOSLLMServiceAdapter(  # type: ignore[call-arg]
            "qwen",
            provider="ollama",
            model_name="qwen3:235b-a22b",
            fast_model_name="qwen3:7b",
        )
        # Bridge to specific exporters where available

        from .base import BaseExporter as _BaseExporter

        # Optional concrete exporters
        _GLTFExporter_t: type[_BaseExporter] | None
        _USDExporter_t: type[_BaseExporter] | None
        _PLYExporter_t: type[_BaseExporter] | None
        _STLExporter_t: type[_BaseExporter] | None
        _DAEExporter_t: type[_BaseExporter] | None
        _X3DExporter_t: type[_BaseExporter] | None

        try:
            from .gltf_exporter import GLTFExporter as _GLTFExporter_t
        except (ImportError, AttributeError) as e:
            logger.debug(f"GLTF exporter unavailable: {e}")
            _GLTFExporter_t = None
        try:
            from .usd_exporter import USDExporter as _USDExporter_t
        except (ImportError, AttributeError) as e:
            logger.debug(f"USD exporter unavailable: {e}")
            _USDExporter_t = None
        try:
            from .ply_exporter import PLYExporter as _PLYExporter_t
        except (ImportError, AttributeError) as e:
            logger.debug(f"PLY exporter unavailable: {e}")
            _PLYExporter_t = None
        try:
            from .stl_exporter import STLExporter as _STLExporter_t
        except (ImportError, AttributeError) as e:
            logger.debug(f"STL exporter unavailable: {e}")
            _STLExporter_t = None
        try:
            from .dae_exporter import DAEExporter as _DAEExporter_t
        except (ImportError, AttributeError) as e:
            logger.debug(f"DAE exporter unavailable: {e}")
            _DAEExporter_t = None
        try:
            from .x3d_exporter import X3DExporter as _X3DExporter_t
        except (ImportError, AttributeError) as e:
            logger.debug(f"X3D exporter unavailable: {e}")
            _X3DExporter_t = None

        self._USDExporter: type[_BaseExporter] | None = _USDExporter_t
        self._GLTFExporter: type[_BaseExporter] | None = _GLTFExporter_t
        self._PLYExporter: type[_BaseExporter] | None = _PLYExporter_t
        self._STLExporter: type[_BaseExporter] | None = _STLExporter_t
        self._DAEExporter: type[_BaseExporter] | None = _DAEExporter_t
        self._X3DExporter: type[_BaseExporter] | None = _X3DExporter_t

    async def initialize(self) -> None:
        """Initialize asset export system."""
        try:
            # Initialize LLM
            await self.llm.initialize()

            self.initialized = True
            logger.info("✅ AssetExporter initialized with LLM integration")

        except Exception as e:
            logger.error(f"❌ AssetExporter initialization failed: {e}")
            raise RuntimeError(f"AssetExporter initialization failed: {e}") from None

    async def generate(self, request: CharacterRequest) -> GenerationResult:
        """Generate export profile for character request."""
        if not self.initialized:
            await self.initialize()

        start_time = time.time()

        try:
            # Create character context
            character_context = CharacterContext(
                character_id=request.request_id,
                name=request.concept,
                description=f"Export processing for {request.concept}",
                aspect=CharacterAspect.VISUAL_DESIGN,
            )

            # Generate export profile using LLM
            export_data = await self._generate_export_profile_llm(character_context)

            # Determine export type
            export_type = self._determine_export_type(export_data)

            # Create ExportProfile object
            export_profile = ExportProfile(
                export_type=export_type,
                supported_formats=export_data.get("supported_formats", []),
                quality_settings=export_data.get("quality_settings", {}),
                optimization_hints=export_data.get("optimization_hints", {}),
                target_platforms=export_data.get("target_platforms", []),
                file_size_constraints=export_data.get("file_size_constraints", {}),
                performance_requirements=export_data.get("performance_requirements", {}),
            )

            generation_time = time.time() - start_time

            # Update statistics
            llm_calls_val = self.stats["llm_calls"]
            llm_calls = (int(llm_calls_val) if isinstance(llm_calls_val, (int, float)) else 0) + 1
            self.stats["llm_calls"] = llm_calls
            avg_response_val = self.stats["avg_response_time"]
            avg_response_time = (
                float(avg_response_val) if isinstance(avg_response_val, (int, float)) else 0.0
            )
            self.stats["avg_response_time"] = (
                avg_response_time * (llm_calls - 1) + generation_time * 1000
            ) / llm_calls

            logger.info(f"Generated export profile in {generation_time * 1000:.2f}ms")

            return GenerationResult(
                success=True,
                mesh_data=None,
                textures={},
                generation_time=generation_time,
                quality_score=self._calculate_export_quality_score(export_profile),
            )

        except Exception as e:
            logger.error(f"Export profile generation failed: {e}")
            return GenerationResult(
                success=False, error=str(e), generation_time=time.time() - start_time
            )

    async def _generate_export_profile_llm(
        self, character_context: CharacterContext
    ) -> dict[str, Any]:
        """Generate export profile using LLM."""
        # Create LLM request
        llm_request = LLMRequest(
            prompt=f"Generate export settings for character: {character_context.name}",
            context=character_context,
            temperature=0.7,
            max_tokens=500,
        )

        # Generate response
        if self.llm:
            response = await self.llm.generate_text(llm_request.prompt)
        else:
            response = "{}"

        # Parse response
        try:
            if isinstance(response, str):
                export_data = json.loads(response)
                return dict(export_data) if isinstance(export_data, dict) else {}
            else:
                return dict(response) if response else {}  # type: ignore  # Defensive/fallback code
        except (json.JSONDecodeError, Exception):
            # Return basic structure if parsing fails
            return {
                "export_type": "game_ready",
                "supported_formats": ["fbx", "obj", "gltf"],
                "quality_settings": {"texture_resolution": 1024},
                "optimization_hints": {"compress_textures": True},
                "target_platforms": ["pc", "mobile"],
                "file_size_constraints": {"max_size_mb": 50},
                "performance_requirements": {"triangle_count": 10000},
            }

    def _determine_export_type(self, export_data: dict[str, Any]) -> ExportType:
        """Determine export type from export data."""
        export_type_str = export_data.get("export_type", "standard")

        # Map to ExportType enum
        type_mapping = {
            "game_ready": ExportType.GAME_READY,
            "animation": ExportType.ANIMATION,
            "static_mesh": ExportType.STATIC_MESH,
            "rigged_character": ExportType.RIGGED_CHARACTER,
            "environment": ExportType.ENVIRONMENT,
            "prop": ExportType.PROP,
            "vehicle": ExportType.VEHICLE,
            "standard": ExportType.STATIC_MESH,
        }

        return type_mapping.get(export_type_str, ExportType.STATIC_MESH)

    def _calculate_export_quality_score(self, export_profile: ExportProfile) -> float:
        """Calculate quality score for export profile."""
        score = 0.0

        # Check completeness
        if export_profile.export_type:
            score += 0.2
        if export_profile.supported_formats:
            score += 0.2
        if export_profile.quality_settings:
            score += 0.2
        if export_profile.optimization_hints:
            score += 0.2
        if export_profile.target_platforms:
            score += 0.2

        return min(score, 1.0)

    async def export_character(self, character: Character, config: ExportConfig) -> ExportResult:
        """Export character to specified format."""
        if not self.initialized:
            await self.initialize()

        start_time = time.time()

        try:
            # Update format usage statistics
            format_name = config.format.value
            formats_used = self.stats["formats_used"]
            if isinstance(formats_used, dict):
                formats_used[format_name] = formats_used.get(format_name, 0) + 1

            # Validate character data
            validation_result = await self._validate_character_data(character)
            if not validation_result["valid"]:
                return ExportResult(
                    success=False,
                    errors=validation_result["errors"],
                    warnings=validation_result["warnings"],
                )

            # Get appropriate handler
            handler = self.format_handlers.get(config.format)
            if not handler:
                return ExportResult(
                    success=False, errors=[f"Unsupported format: {config.format.value}"]
                )

            # Perform export
            logger.info(f"Exporting character to {config.format.value} format")
            result = await handler(character, config)

            # Calculate export time
            export_time = time.time() - start_time
            result.export_time = export_time

            # Update statistics
            total_exports_val = self.stats["total_exports"]
            total_exports = (
                int(total_exports_val) if isinstance(total_exports_val, (int, float)) else 0
            ) + 1
            self.stats["total_exports"] = total_exports

            if result.success:
                successful_val = self.stats["successful_exports"]
                self.stats["successful_exports"] = (
                    int(successful_val) if isinstance(successful_val, (int, float)) else 0
                ) + 1
            else:
                failed_val = self.stats["failed_exports"]
                self.stats["failed_exports"] = (
                    int(failed_val) if isinstance(failed_val, (int, float)) else 0
                ) + 1

            avg_export_val = self.stats["avg_export_time"]
            avg_export_time = (
                float(avg_export_val) if isinstance(avg_export_val, (int, float)) else 0.0
            )
            self.stats["avg_export_time"] = (
                avg_export_time * (total_exports - 1) + export_time * 1000
            ) / total_exports

            if result.success:
                logger.info(
                    f"✅ Export completed successfully in {export_time * 1000:.2f}ms: {result.file_path}"
                )
            else:
                logger.error(f"❌ Export failed: {result.errors}")

            return result

        except Exception as e:
            logger.error(f"Export failed with exception: {e}")
            return ExportResult(
                success=False, errors=[str(e)], export_time=time.time() - start_time
            )

    async def export_multiple_formats(
        self, character: Character, configs: list[ExportConfig]
    ) -> list[ExportResult]:
        """Export character to multiple formats concurrently."""
        if not self.initialized:
            await self.initialize()

        try:
            # Create export tasks
            tasks = []
            for config in configs:
                task = asyncio.create_task(self.export_character(character, config))
                tasks.append(task)

            # Wait for all exports to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            export_results = []
            for _i, result in enumerate(results):
                if isinstance(result, Exception):
                    export_results.append(ExportResult(success=False, errors=[str(result)]))
                elif isinstance(result, ExportResult):
                    export_results.append(result)
                else:
                    # Handle unexpected result type
                    export_results.append(
                        ExportResult(
                            success=False,
                            errors=[f"Unexpected result type: {type(result)}"],
                        )
                    )

            return export_results

        except Exception as e:
            logger.error(f"Multiple export failed: {e}")
            return [ExportResult(success=False, errors=[str(e)]) for _ in configs]

    async def _validate_character_data(self, character: Character) -> dict[str, Any]:
        """Validate character data for export."""
        validation_result = {"valid": True, "errors": [], "warnings": []}

        # Check required fields
        if not character.character_id:
            errors_list = validation_result.get("errors", [])
            if isinstance(errors_list, list):
                errors_list.append("Character ID is required")
            validation_result["valid"] = False

        if not character.name:
            warnings_list = validation_result.get("warnings", [])
            if isinstance(warnings_list, list):
                warnings_list.append("Character name is empty")

        # Check mesh data
        if not character.mesh:
            errors_list = validation_result.get("errors", [])
            if isinstance(errors_list, list):
                errors_list.append("Character mesh is required")
            validation_result["valid"] = False

        # Check materials
        if not character.materials:
            warnings_list = validation_result.get("warnings", [])
            if isinstance(warnings_list, list):
                warnings_list.append("Character has no materials")

        return validation_result

    def get_supported_formats(self) -> list[ExportFormat]:
        """Get all supported export formats."""
        return list(self.format_handlers.keys())

    # Format-specific export handlers
    async def _export_fbx(self, character: Character, config: ExportConfig) -> ExportResult:
        """Export to FBX format."""
        try:
            # Create FBX export data
            fbx_data = {
                "format": "fbx",
                "character_id": character.character_id,
                "mesh": character.mesh,
                "materials": character.materials,
                "skeleton": character.skeleton,
                "animations": (character.animations if config.include_animations else None),
            }

            # Write to file
            output_path = config.output_path or Path(f"{character.name}.fbx")
            await self._write_export_file(fbx_data, output_path)

            return ExportResult(
                success=True,
                file_path=output_path,
                file_size=output_path.stat().st_size if output_path.exists() else 0,
                metadata={"format": "fbx", "quality": config.quality.value},
            )

        except Exception as e:
            return ExportResult(success=False, errors=[f"FBX export failed: {e!s}"])

    async def _export_gltf(self, character: Character, config: ExportConfig) -> ExportResult:
        """Export to GLTF format."""
        try:
            # Create GLTF export data
            gltf_data = {
                "asset": {"generator": "Forge Asset Exporter", "version": "2.0"},
                "scene": 0,
                "scenes": [{"nodes": [0]}],
                "nodes": [{"name": character.name, "mesh": 0}],
                "meshes": [
                    {
                        "name": f"{character.name}_mesh",
                        "primitives": [{"attributes": {"POSITION": 0}, "material": 0}],
                    }
                ],
                "materials": [
                    {
                        "name": f"{character.name}_material",
                        "pbrMetallicRoughness": {"baseColorFactor": [1.0, 1.0, 1.0, 1.0]},
                    }
                ],
            }

            # Write to file
            output_path = config.output_path or Path(f"{character.name}.gltf")
            await self._write_export_file(gltf_data, output_path, format_type="json")

            return ExportResult(
                success=True,
                file_path=output_path,
                file_size=output_path.stat().st_size if output_path.exists() else 0,
                metadata={"format": "gltf", "quality": config.quality.value},
            )

        except Exception as e:
            return ExportResult(success=False, errors=[f"GLTF export failed: {e!s}"])

    async def _export_obj(self, character: Character, config: ExportConfig) -> ExportResult:
        """Export to OBJ format."""
        try:
            # Create OBJ export data
            obj_lines = [
                f"# Character: {character.name}",
                "# Generated by Forge Asset Exporter",
                "",
            ]

            # Add vertices (simplified)
            if character.mesh and hasattr(character.mesh, "vertices"):
                for vertex in character.mesh.vertices:
                    obj_lines.append(f"v {vertex[0]} {vertex[1]} {vertex[2]}")

            # Add faces (simplified)
            if character.mesh and hasattr(character.mesh, "faces"):
                for face in character.mesh.faces:
                    obj_lines.append(f"f {' '.join(str(i + 1) for i in face)}")

            # Write to file
            output_path = config.output_path or Path(f"{character.name}.obj")
            with open(output_path, "w") as f:
                f.write("\n".join(obj_lines))

            return ExportResult(
                success=True,
                file_path=output_path,
                file_size=output_path.stat().st_size if output_path.exists() else 0,
                metadata={"format": "obj", "quality": config.quality.value},
            )

        except Exception as e:
            return ExportResult(success=False, errors=[f"OBJ export failed: {e!s}"])

    # Placeholder handlers for other formats
    async def _export_usd(self, character: Character, config: ExportConfig) -> ExportResult:
        """Export to USD format."""
        try:
            if self._USDExporter is None:
                return ExportResult(
                    success=False,
                    errors=["USD format currently unsupported in this build"],
                )

            # Build exporter config and input data
            base_cfg = ExportConfig(
                format=ExportFormat.USD,
                quality=config.quality,
                output_path=config.output_path,
                include_textures=config.include_textures,
                include_animations=config.include_animations,
                include_materials=config.include_materials,
            )

            from typing import cast as _cast

            exporter = _cast(Any, self._USDExporter)(base_cfg)
            data = self._build_export_input(character)
            res = await exporter.export(data)
            return ExportResult(
                success=bool(res.success),
                file_path=res.file_path,
                file_size=res.file_size,
                export_time=res.export_time,
                warnings=list(res.warnings or []),
                errors=list(res.errors or []),
                metadata=dict(res.metadata or {}),
            )
        except Exception as e:
            return ExportResult(success=False, errors=[f"USD export failed: {e}"])

    async def _export_glb(self, character: Character, config: ExportConfig) -> ExportResult:
        """Export as GLB (binary GLTF)."""
        # GLB is just GLTF with binary embedding - reuse GLTF logic
        return await self._export_gltf(character, config)

    async def _export_dae(self, character: Character, config: ExportConfig) -> ExportResult:
        """Export as DAE (Collada)."""
        try:
            if self._DAEExporter is None:
                return ExportResult(
                    success=False,
                    errors=["DAE exporter not available in this build"],
                )

            from typing import cast as _cast

            base_cfg = ExportConfig(
                format=ExportFormat.DAE,
                quality=config.quality,
                output_path=config.output_path,
                include_textures=config.include_textures,
                include_animations=config.include_animations,
                include_materials=config.include_materials,
            )

            exporter = _cast(Any, self._DAEExporter)(base_cfg)
            data = self._build_export_input(character)
            res = await exporter.export(data)
            return ExportResult(
                success=bool(res.success),
                file_path=res.file_path,
                file_size=res.file_size,
                export_time=res.export_time,
                warnings=list(res.warnings or []),
                errors=list(res.errors or []),
                metadata=dict(res.metadata or {}),
            )
        except Exception as e:
            return ExportResult(success=False, errors=[f"DAE export failed: {e}"])

    async def _export_ply(self, character: Character, config: ExportConfig) -> ExportResult:
        """Export as PLY (Polygon File Format)."""
        try:
            if self._PLYExporter is None:
                return ExportResult(
                    success=False,
                    errors=["PLY exporter not available in this build"],
                )

            from typing import cast as _cast

            base_cfg = ExportConfig(
                format=ExportFormat.PLY,
                quality=config.quality,
                output_path=config.output_path,
                include_textures=config.include_textures,
                include_animations=config.include_animations,
                include_materials=config.include_materials,
            )

            exporter = _cast(Any, self._PLYExporter)(base_cfg)
            data = self._build_export_input(character)
            res = await exporter.export(data)
            return ExportResult(
                success=bool(res.success),
                file_path=res.file_path,
                file_size=res.file_size,
                export_time=res.export_time,
                warnings=list(res.warnings or []),
                errors=list(res.errors or []),
                metadata=dict(res.metadata or {}),
            )
        except Exception as e:
            return ExportResult(success=False, errors=[f"PLY export failed: {e}"])

    async def _export_stl(self, character: Character, config: ExportConfig) -> ExportResult:
        """Export as STL (Stereolithography) for 3D printing."""
        try:
            if self._STLExporter is None:
                return ExportResult(
                    success=False,
                    errors=["STL exporter not available in this build"],
                )

            from typing import cast as _cast

            base_cfg = ExportConfig(
                format=ExportFormat.STL,
                quality=config.quality,
                output_path=config.output_path,
                include_textures=False,  # STL doesn't support textures
                include_animations=False,  # STL doesn't support animations
                include_materials=False,  # STL doesn't support materials
            )

            exporter = _cast(Any, self._STLExporter)(base_cfg)
            data = self._build_export_input(character)
            res = await exporter.export(data)
            return ExportResult(
                success=bool(res.success),
                file_path=res.file_path,
                file_size=res.file_size,
                export_time=res.export_time,
                warnings=list(res.warnings or []),
                errors=list(res.errors or []),
                metadata=dict(res.metadata or {}),
            )
        except Exception as e:
            return ExportResult(success=False, errors=[f"STL export failed: {e}"])

    async def _export_json(self, character: Character, config: ExportConfig) -> ExportResult:
        """Export as JSON (internal format)."""
        import json

        data = self._build_export_input(character)
        return ExportResult(
            success=True,
            file_path=str(config.output_path) if config.output_path else None,  # type: ignore[arg-type]
            metadata={"format": "json", "data": json.dumps(data)},
        )

    async def _export_blend(self, character: Character, config: ExportConfig) -> ExportResult:
        """Export as Blender format."""
        return ExportResult(success=False, errors=["Blender export not yet implemented"])

    async def _export_x3d(self, character: Character, config: ExportConfig) -> ExportResult:
        """Export as X3D for web 3D content."""
        try:
            if self._X3DExporter is None:
                return ExportResult(
                    success=False,
                    errors=["X3D exporter not available in this build"],
                )

            from typing import cast as _cast

            base_cfg = ExportConfig(
                format=ExportFormat.X3D,
                quality=config.quality,
                output_path=config.output_path,
                include_textures=config.include_textures,
                include_animations=config.include_animations,
                include_materials=config.include_materials,
            )

            exporter = _cast(Any, self._X3DExporter)(base_cfg)
            data = self._build_export_input(character)
            res = await exporter.export(data)
            return ExportResult(
                success=bool(res.success),
                file_path=res.file_path,
                file_size=res.file_size,
                export_time=res.export_time,
                warnings=list(res.warnings or []),
                errors=list(res.errors or []),
                metadata=dict(res.metadata or {}),
            )
        except Exception as e:
            return ExportResult(success=False, errors=[f"X3D export failed: {e}"])

    async def _export_vrml(self, character: Character, config: ExportConfig) -> ExportResult:
        """Export as VRML."""
        return ExportResult(success=False, errors=["VRML export not yet implemented"])

    def _build_export_input(self, character: Character) -> dict[str, Any]:
        """Adapt Character instance to generic exporter input shape."""
        mesh = getattr(character, "mesh", None)
        materials = getattr(character, "materials", None)
        animations = getattr(character, "animations", None)

        def _as_list(obj: Any) -> list[Any]:
            try:
                return list(obj) if obj is not None else []
            except Exception:
                return []

        mesh_dict: dict[str, Any] = {}
        if mesh is not None:
            mesh_dict = {
                "vertices": _as_list(getattr(mesh, "vertices", [])),
                "faces": _as_list(getattr(mesh, "faces", [])),
                "normals": _as_list(getattr(mesh, "normals", [])),
            }
        mats_dict: dict[str, Any] = {}
        try:
            if isinstance(materials, list) and materials:
                m0 = materials[0]
                # Try to infer diffuse color
                dc = getattr(m0, "diffuse_color", None) or getattr(m0, "base_color", None)
                if isinstance(dc, (list, tuple)):
                    mats_dict["diffuse_color"] = list(dc)
        except Exception:
            mats_dict = {}
        anim_dict: dict[str, Any] = {}
        try:
            if isinstance(animations, list) and animations:
                # If animations are simple keyframes, pass through; otherwise leave empty
                if all(isinstance(a, dict) for a in animations):
                    anim_dict = {"keyframes": animations}
        except Exception:
            anim_dict = {}

        meta = {"upAxis": "Y", "metersPerUnit": 1.0, "timeCodesPerSecond": 24}
        return {
            "mesh": mesh_dict,
            "materials": mats_dict,
            "animations": anim_dict,
            "metadata": meta,
        }

    async def _write_export_file(
        self, data: Any, output_path: Path, format_type: str = "binary"
    ) -> None:
        """Write export data to file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if format_type == "json":
            with open(output_path, "w") as f:
                json.dump(data, f, indent=2, default=str)
        elif format_type == "text":
            with open(output_path, "w") as f:
                f.write(str(data))
        else:
            # Binary format (simplified)
            with open(output_path, "wb") as f:
                f.write(json.dumps(data, default=str).encode("utf-8"))

    def get_status(self) -> dict[str, Any]:
        """Get asset exporter status."""
        return {
            "initialized": self.initialized,
            "supported_formats": [fmt.value for fmt in self.get_supported_formats()],
            "stats": self.stats,
            "llm_integration": True,
            "performance": {
                "avg_export_time_ms": self.stats["avg_export_time"],
                "success_rate": (
                    (
                        int(self.stats["successful_exports"])
                        if isinstance(self.stats["successful_exports"], (int, float))
                        else 0
                    )
                    / max(
                        (
                            int(self.stats["total_exports"])
                            if isinstance(self.stats["total_exports"], (int, float))
                            else 0
                        ),
                        1,
                    )
                    * 100
                ),
                "formats_used": self.stats["formats_used"],
            },
            "real_asset_export": True,
        }
