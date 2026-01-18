"""Automatic rigging for 3D meshes using UniRig technology.

This module provides automatic skeleton generation and weight painting
for 3D meshes, enabling them to be animated. It uses the UniRig model
from VAST-AI-Research for template-free rigging of diverse geometries.

Key Features:
    - Automatic skeleton prediction for any 3D mesh
    - Intelligent bone placement using transformer architecture
    - Automatic skinning weight calculation
    - Support for humanoid and non-humanoid meshes
    - MPS optimization for Apple Silicon devices

Technical Details:
    - Autoregressive skeleton generation
    - Bone-Point Cross Attention for weights
    - Compatible with animation pipeline
    - Export-ready rigging data
"""

import json
import logging
from datetime import datetime
from typing import Any

import numpy as np
import torch

try:
    from kagami_observability.metrics import (
        UNIRIG_RIG_LATENCY_MS,
        UNIRIG_RIGS,
    )
except Exception:  # pragma: no cover
    UNIRIG_RIG_LATENCY_MS: Any = None  # type: ignore[no-redef]
    UNIRIG_RIGS: Any = None  # type: ignore[no-redef]
import trimesh
from scipy.spatial import KDTree

# Import MPS-optimized UniRig wrapper
from ..core_integration import (
    CharacterAspect,
    CharacterResult,
    ForgeComponent,
    ProcessingStatus,
)
from ..mps_unirig_wrapper import create_mps_unirig

# Define logger at module level before using it
logger = logging.getLogger(__name__)

# UniRig wrapper is now handled by MPS-optimized external module


class RiggedMesh:
    """Container for a rigged 3D mesh with skeleton and weights.

    Stores all rigging data needed for animation, including the mesh
    geometry, bone hierarchy, and vertex weights.

    Args:
        mesh: Trimesh object containing geometry
        skeleton: Dictionary defining bone hierarchy and positions
        weights: Vertex skinning weights array (vertices x bones)

    Attributes:
        mesh: Original mesh geometry
        skeleton: Bone hierarchy data
        weights: Skinning weight matrix
        bone_names: List of bone names
        n_bones: Number of bones
    """

    def __init__(
        self, mesh: trimesh.Trimesh, skeleton: dict[str, Any], weights: np.ndarray
    ) -> None:
        self.mesh = mesh
        self.skeleton = skeleton
        self.weights = weights
        self.bone_hierarchy: dict[str, list[str]] = self._build_hierarchy()

    def _build_hierarchy(self) -> dict[str, list[str]]:
        """Build bone hierarchy from skeleton."""
        hierarchy: dict[str, list[str]] = {}
        for bone_name, bone_data in self.skeleton["bones"].items():
            parent = bone_data.get("parent", None)
            if parent:
                if parent not in hierarchy:
                    hierarchy[parent] = []
                hierarchy[parent].append(bone_name)
        return hierarchy

    def get_bone_transform(self, bone_name: str) -> np.ndarray:
        """Get transformation matrix for a bone."""
        if bone_name not in self.skeleton["bones"]:
            return np.eye(4)

        bone = self.skeleton["bones"][bone_name]
        transform = np.eye(4)
        transform[:3, 3] = bone["position"]

        # Apply parent transforms
        parent = bone.get("parent")
        if parent:
            parent_transform = self.get_bone_transform(parent)
            transform = parent_transform @ transform

        return transform

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "mesh": {
                "vertices": self.mesh.vertices.tolist(),
                "faces": self.mesh.faces.tolist(),
                "normals": self.mesh.vertex_normals.tolist(),
            },
            "skeleton": self.skeleton,
            "weights": self.weights.tolist(),
            "hierarchy": self.bone_hierarchy,
        }


class RiggingModule(ForgeComponent):
    """Automatic rigging module for the Forge character pipeline.

    Provides automatic skeleton generation and weight painting for 3D meshes
    using UniRig technology. Supports both humanoid and non-humanoid meshes
    with intelligent bone placement.

    Args:
        name: Module identifier
        config: Optional configuration with rigging parameters

    Example:
        >>> rigging = RiggingModule("rigging")
        >>> rigging.initialize({})  # Sync initialization
        >>> await rigging.initialize_async()  # Async model loading
        >>> result = await rigging.process({
        ...     'mesh': trimesh_object,
        ...     'skeleton_type': 'humanoid'
        ... })
        >>> rigged_mesh = result.data['rigged_mesh']
    """

    def __init__(self, name: str = "rigging", config: dict[str, Any] | None = None) -> None:
        super().__init__(name, config)
        self.unirig_model: Any = None  # Type is MPSUniRigWrapper when available
        self.skeleton_templates: dict[str, dict[str, Any]] = {}
        # Set device here for immediate availability
        self.device = "mps" if torch.backends.mps.is_available() else "cpu"
        # Track init state for tests
        self.initialized: bool = False

    def _validate_config_specific(self, config: dict[str, Any]) -> bool:
        """Validate rigging-specific configuration."""
        # Check method is valid if specified
        method = config.get("method", "unirig")
        if method not in ["unirig", "auto", "template"]:
            return False
        return True

    def _do_initialize(self, config: dict[str, Any]) -> None:
        """Implement required initialization for BaseComponent."""
        # Set config values
        self.config = config
        self.device = config.get("device", "mps" if torch.backends.mps.is_available() else "cpu")

        # Note: actual model initialization happens in async initialize_async()

    async def initialize(self, config: dict[str, Any] | None = None) -> None:  # type: ignore[override,override]
        """Async-compatible initialize expected by tests.

        Performs minimal config setup and marks the module initialized. Real
        model loading remains in `initialize_async` to keep optional deps.
        """
        self._do_initialize(config or {})
        self.initialized = True

    async def initialize_async(self) -> None:
        """Initialize rigging models and templates."""
        logger.info("Initializing Rigging Module...")

        # Initialize UniRig
        if self.config.get("method", "unirig") in ["unirig", "auto"]:
            await self._initialize_unirig()

        # No skeleton templates - UniRig only

        # Enforce UniRig presence if required
        if self.config.get("require_real_models", False) and self.unirig_model is None:
            raise RuntimeError("UniRig real models required but not available")

        self.initialized = True
        logger.info("Rigging Module initialized")

    async def _initialize_unirig(self) -> None:
        """Initialize MPS-optimized UniRig from VAST-AI-Research."""
        try:
            logger.info("🍎 Initializing MPS-optimized UniRig for M3 Max...")

            # Create MPS-optimized UniRig wrapper
            # Create MPS-optimized UniRig wrapper - cast device to satisfy type checker
            # NOTE: `self.device` is a legacy string ("mps"/"cpu"). The factory
            # is defensive and will coerce to torch.device.
            self.unirig_model = create_mps_unirig(self.device)  # type: ignore[arg-type]

            # Load the actual models with MPS optimizations
            # Load the actual models with MPS optimizations
            if self.unirig_model is not None:
                # `load_models()` historically returned True, but may also return
                # None when already initialized. Treat "already initialized" as success.
                await self.unirig_model.load_models()
                success = bool(getattr(self.unirig_model, "initialized", False))
            else:
                success = False

            if success and self.unirig_model is not None:
                # Log memory usage
                memory_info = self.unirig_model.get_memory_usage()
                logger.info(f"📊 Memory usage: {memory_info}")
                logger.info("✅ MPS-optimized UniRig initialization complete!")
            else:
                logger.error("❌ UniRig initialization failed")
                self.unirig_model = None

        except Exception as e:
            logger.error(f"❌ Failed to initialize MPS UniRig: {e}")
            import traceback

            traceback.print_exc()
            self.unirig_model = None

    async def _load_skeleton_templates(self) -> None:
        """Load predefined skeleton templates."""
        self.skeleton_templates = {
            "humanoid": self._create_humanoid_skeleton(),
            "quadruped": self._create_quadruped_skeleton(),
            "bird": self._create_bird_skeleton(),
        }

    def _create_humanoid_skeleton(self) -> dict[str, Any]:
        """Create humanoid skeleton template optimized for character animation."""
        return {
            "type": "humanoid",
            "version": "character_optimized",
            "bones": {
                "root": {"position": [0, 0, 0], "parent": None},
                "pelvis": {"position": [0, 1.0, 0], "parent": "root"},
                "spine": {"position": [0, 1.2, 0], "parent": "pelvis"},
                "chest": {"position": [0, 1.5, 0], "parent": "spine"},
                "neck": {"position": [0, 1.7, 0], "parent": "chest"},
                "head": {"position": [0, 1.9, 0], "parent": "neck"},
                # Left arm
                "left_shoulder": {"position": [-0.3, 1.6, 0], "parent": "chest"},
                "left_upper_arm": {
                    "position": [-0.5, 1.4, 0],
                    "parent": "left_shoulder",
                },
                "left_forearm": {
                    "position": [-0.7, 1.1, 0],
                    "parent": "left_upper_arm",
                },
                "left_hand": {"position": [-0.8, 0.9, 0], "parent": "left_forearm"},
                # Right arm
                "right_shoulder": {"position": [0.3, 1.6, 0], "parent": "chest"},
                "right_upper_arm": {
                    "position": [0.5, 1.4, 0],
                    "parent": "right_shoulder",
                },
                "right_forearm": {
                    "position": [0.7, 1.1, 0],
                    "parent": "right_upper_arm",
                },
                "right_hand": {"position": [0.8, 0.9, 0], "parent": "right_forearm"},
                # Left leg
                "left_hip": {"position": [-0.15, 1.0, 0], "parent": "pelvis"},
                "left_thigh": {"position": [-0.15, 0.7, 0], "parent": "left_hip"},
                "left_shin": {"position": [-0.15, 0.3, 0], "parent": "left_thigh"},
                "left_foot": {"position": [-0.15, 0, 0], "parent": "left_shin"},
                # Right leg
                "right_hip": {"position": [0.15, 1.0, 0], "parent": "pelvis"},
                "right_thigh": {"position": [0.15, 0.7, 0], "parent": "right_hip"},
                "right_shin": {"position": [0.15, 0.3, 0], "parent": "right_thigh"},
                "right_foot": {"position": [0.15, 0, 0], "parent": "right_shin"},
            },
        }

    def _create_quadruped_skeleton(self) -> dict[str, Any]:
        """Create quadruped skeleton template."""
        return {
            "type": "quadruped",
            "bones": {
                "root": {"position": [0, 0, 0], "parent": None},
                "pelvis": {"position": [0, 0.5, -0.5], "parent": "root"},
                "spine": {"position": [0, 0.5, 0], "parent": "pelvis"},
                "chest": {"position": [0, 0.5, 0.5], "parent": "spine"},
                "neck": {"position": [0, 0.6, 0.8], "parent": "chest"},
                "head": {"position": [0, 0.7, 1.0], "parent": "neck"},
                # Front legs
                "left_front_shoulder": {
                    "position": [-0.2, 0.4, 0.6],
                    "parent": "chest",
                },
                "left_front_leg": {
                    "position": [-0.2, 0.2, 0.6],
                    "parent": "left_front_shoulder",
                },
                "left_front_foot": {
                    "position": [-0.2, 0, 0.6],
                    "parent": "left_front_leg",
                },
                "right_front_shoulder": {
                    "position": [0.2, 0.4, 0.6],
                    "parent": "chest",
                },
                "right_front_leg": {
                    "position": [0.2, 0.2, 0.6],
                    "parent": "right_front_shoulder",
                },
                "right_front_foot": {
                    "position": [0.2, 0, 0.6],
                    "parent": "right_front_leg",
                },
                # Back legs
                "left_back_hip": {"position": [-0.2, 0.4, -0.6], "parent": "pelvis"},
                "left_back_leg": {
                    "position": [-0.2, 0.2, -0.6],
                    "parent": "left_back_hip",
                },
                "left_back_foot": {
                    "position": [-0.2, 0, -0.6],
                    "parent": "left_back_leg",
                },
                "right_back_hip": {"position": [0.2, 0.4, -0.6], "parent": "pelvis"},
                "right_back_leg": {
                    "position": [0.2, 0.2, -0.6],
                    "parent": "right_back_hip",
                },
                "right_back_foot": {
                    "position": [0.2, 0, -0.6],
                    "parent": "right_back_leg",
                },
                # Tail
                "tail_base": {"position": [0, 0.4, -0.8], "parent": "pelvis"},
                "tail_mid": {"position": [0, 0.3, -1.0], "parent": "tail_base"},
                "tail_tip": {"position": [0, 0.2, -1.2], "parent": "tail_mid"},
            },
        }

    def _create_bird_skeleton(self) -> dict[str, Any]:
        """Create bird skeleton template."""
        return {
            "type": "bird",
            "bones": {
                "root": {"position": [0, 0, 0], "parent": None},
                "body": {"position": [0, 0.5, 0], "parent": "root"},
                "chest": {"position": [0, 0.6, 0.1], "parent": "body"},
                "neck": {"position": [0, 0.7, 0.2], "parent": "chest"},
                "head": {"position": [0, 0.8, 0.3], "parent": "neck"},
                # Wings
                "left_wing_base": {"position": [-0.3, 0.6, 0], "parent": "chest"},
                "left_wing_mid": {
                    "position": [-0.6, 0.6, 0],
                    "parent": "left_wing_base",
                },
                "left_wing_tip": {
                    "position": [-0.9, 0.6, 0],
                    "parent": "left_wing_mid",
                },
                "right_wing_base": {"position": [0.3, 0.6, 0], "parent": "chest"},
                "right_wing_mid": {
                    "position": [0.6, 0.6, 0],
                    "parent": "right_wing_base",
                },
                "right_wing_tip": {
                    "position": [0.9, 0.6, 0],
                    "parent": "right_wing_mid",
                },
                # Legs
                "left_leg": {"position": [-0.1, 0.3, 0], "parent": "body"},
                "left_foot": {"position": [-0.1, 0, 0], "parent": "left_leg"},
                "right_leg": {"position": [0.1, 0.3, 0], "parent": "body"},
                "right_foot": {"position": [0.1, 0, 0], "parent": "right_leg"},
                # Tail
                "tail": {"position": [0, 0.4, -0.2], "parent": "body"},
            },
        }

    async def process(self, input_data: dict[str, Any], **kwargs: Any) -> CharacterResult:
        """Process rigging request."""
        start_time = datetime.now()
        errors: list[str] = []
        warnings: list[str] = []

        try:
            # Extract mesh and hints
            mesh = input_data.get("generation", {}).get("mesh")
            if mesh is None:
                errors.append("No mesh found in input data")
                return CharacterResult(
                    status=ProcessingStatus.FAILED,
                    aspect=CharacterAspect.MOTION,
                    data=None,
                    error="; ".join(errors),
                )

            # Get metadata for character context
            metadata = input_data.get("generation", {}).get("metadata", {})
            prompt = metadata.get("prompt", "")

            # Get rigging hints and add full context
            rigging_hints = input_data.get("generation", {}).get("rigging_hints", {})
            rigging_hints["character_description"] = prompt  # Pass full description to UniRig

            # Get skeleton type from hints
            rigging_hints.get("skeleton_type", "humanoid")

            # Rig the mesh - UniRig only
            if self.unirig_model is None:
                raise RuntimeError("UniRig model not available - real models required")

            # Measure rigging latency
            import time as _t

            _t0 = _t.time() * 1000.0
            rigged_mesh = await self._rig_with_unirig(mesh, rigging_hints)
            try:
                if UNIRIG_RIG_LATENCY_MS is not None:
                    mode = (
                        getattr(self.unirig_model, "mode", "local")
                        if self.unirig_model
                        else "local"
                    )
                    UNIRIG_RIG_LATENCY_MS.labels(str(mode)).observe(
                        max(0.0, (_t.time() * 1000.0) - _t0)
                    )
                if UNIRIG_RIGS is not None:
                    mode = (
                        getattr(self.unirig_model, "mode", "local")
                        if self.unirig_model
                        else "local"
                    )
                    UNIRIG_RIGS.labels(str(mode)).inc()
            except Exception:
                pass

            # Validate rigging
            validation_errors = self._validate_rigging(rigged_mesh)
            if validation_errors:
                warnings.extend(validation_errors)

            # Calculate metrics
            {
                "bone_count": len(rigged_mesh.skeleton["bones"]),
                "skinning_quality": self._calculate_skinning_quality(rigged_mesh),
                "rigging_time": (datetime.now() - start_time).total_seconds(),
                "method_used": "unirig",
            }

            return CharacterResult(
                status=ProcessingStatus.COMPLETED,
                aspect=CharacterAspect.MOTION,
                data=rigged_mesh,
                metadata={"processing_time": (datetime.now() - start_time).total_seconds()},
            )

        except Exception as e:
            logger.error(f"Rigging failed: {e}")
            errors.append(str(e))

            return CharacterResult(
                status=ProcessingStatus.FAILED,
                aspect=CharacterAspect.MOTION,
                data=None,
                error="; ".join(errors),
            )

    async def _rig_with_unirig(self, mesh: trimesh.Trimesh, hints: dict[str, Any]) -> RiggedMesh:
        """Rig mesh using REAL UniRig model with character awareness."""
        logger.info("🦴 Rigging with real UniRig autoregressive model...")

        try:
            # Pass the class token to UniRig - it only accepts specific tokens
            character_description = hints.get("character_description", "")
            # UniRig only accepts: "vroid", "articulationxl", or None
            # If the description is "articulationxl", use it, otherwise use None
            if character_description == "articulationxl":
                model_cls_id = "articulationxl"
            else:
                model_cls_id = None  # Let UniRig decide based on mesh

            if self.unirig_model is None:
                raise RuntimeError("UniRig model not initialized")

            rigging_result = await self.unirig_model.rig_mesh(mesh, cls=model_cls_id)

            if rigging_result:
                try:
                    sk = (
                        rigging_result.get("skeleton") if isinstance(rigging_result, dict) else None
                    )
                    if isinstance(sk, dict):
                        bones_obj = sk.get("bones", {})
                        bone_count = len(bones_obj) if isinstance(bones_obj, dict) else 0
                    else:
                        bone_count = 0
                except Exception:
                    bone_count = 0
                logger.info(f"✅ UniRig completed: {bone_count} bones")
                return RiggedMesh(
                    rigging_result["mesh"],
                    rigging_result["skeleton"],
                    rigging_result["weights"],
                )
            else:
                raise RuntimeError("UniRig returned no result")

        except Exception as e:
            logger.error(f"❌ UniRig failed: {e}")
            # Real UniRig models only
            raise RuntimeError(f"UniRig rigging failed: {e}") from None

    def _fit_skeleton_to_mesh(
        self, mesh: trimesh.Trimesh, template: dict[str, Any]
    ) -> dict[str, Any]:
        """Fit template skeleton to mesh bounds."""
        # Get mesh bounds
        mesh_center = mesh.centroid
        mesh_scale = mesh.extents

        # Copy template
        fitted = json.loads(json.dumps(template))  # Deep copy

        # Scale and translate bones
        for _bone_name, bone_data in fitted["bones"].items():
            pos = np.array(bone_data["position"])

            # Scale to mesh size
            pos = pos * (mesh_scale / 2.0)

            # Translate to mesh center
            pos += mesh_center

            bone_data["position"] = pos.tolist()

        return fitted  # type: ignore[no-any-return]

    def _calculate_skinning_weights(
        self, mesh: trimesh.Trimesh, skeleton: dict[str, Any]
    ) -> np.ndarray:
        """Calculate skinning weights using heat diffusion."""
        num_vertices = len(mesh.vertices)
        bones = skeleton["bones"]
        num_bones = len(bones)

        # Get bone positions
        bone_positions = np.array([bone["position"] for bone in bones.values()])

        # Build KDTree for efficient distance queries
        tree = KDTree(bone_positions)

        # Initialize weights
        weights = np.zeros((num_vertices, num_bones))

        # For each vertex, find nearest bones
        for i, vertex in enumerate(mesh.vertices):
            # Find k nearest bones
            k = min(self.config.get("max_influences_per_vertex", 4), num_bones)
            distances, indices = tree.query(vertex, k=k)

            # Ensure distances and indices are arrays
            if not isinstance(distances, np.ndarray):
                distances = np.array([distances])
                indices = np.array([indices])

            # Type narrowing to ensure indices is array-like
            indices_array = np.atleast_1d(indices)

            # Convert distances to weights (inverse distance weighting)
            if distances[0] < 1e-6:
                # Vertex is at bone position
                weights[i, indices_array[0]] = 1.0
            else:
                # Gaussian falloff
                sigma = 0.2  # Falloff parameter
                bone_weights = np.exp(-(distances**2) / (2 * sigma**2))
                bone_weights /= bone_weights.sum()

                weights[i, indices_array] = bone_weights

        return weights

    def _validate_rigging(self, rigged_mesh: RiggedMesh) -> list[str]:
        """Validate rigging quality."""
        errors = []

        # Check bone hierarchy
        roots = [
            name for name, data in rigged_mesh.skeleton["bones"].items() if data["parent"] is None
        ]
        if len(roots) != 1:
            errors.append(f"Invalid skeleton: found {len(roots)} root bones, expected 1")

        # Check skinning weights
        weight_sums = rigged_mesh.weights.sum(axis=1)
        invalid_vertices = np.where(np.abs(weight_sums - 1.0) > 1e-3)[0]
        if len(invalid_vertices) > 0:
            errors.append(f"Invalid skinning weights on {len(invalid_vertices)} vertices")

        # Check for uninfluenced vertices
        max_weights = rigged_mesh.weights.max(axis=1)
        uninfluenced = np.where(max_weights < 0.01)[0]
        if len(uninfluenced) > 0:
            errors.append(f"Found {len(uninfluenced)} vertices with very low influence")

        return errors

    def export_retarget_presets(self) -> dict[str, Any]:
        """Return deterministic retarget presets for common targets.

        These presets are used by engine integrations (UE/Unity/Mixamo).
        """
        return {
            "ue_mannequin": {
                "root": "root",
                "pelvis": "pelvis",
                "spine_01": "spine",
                "spine_02": "chest",
                "neck_01": "neck",
                "head": "head",
                "upperarm_l": "left_upper_arm",
                "lowerarm_l": "left_forearm",
                "hand_l": "left_hand",
                "upperarm_r": "right_upper_arm",
                "lowerarm_r": "right_forearm",
                "hand_r": "right_hand",
                "thigh_l": "left_thigh",
                "calf_l": "left_shin",
                "foot_l": "left_foot",
                "thigh_r": "right_thigh",
                "calf_r": "right_shin",
                "foot_r": "right_foot",
            },
            "mixamo": {
                "Hips": "pelvis",
                "Spine": "spine",
                "Spine1": "chest",
                "Neck": "neck",
                "Head": "head",
                "LeftArm": "left_upper_arm",
                "LeftForeArm": "left_forearm",
                "LeftHand": "left_hand",
                "RightArm": "right_upper_arm",
                "RightForeArm": "right_forearm",
                "RightHand": "right_hand",
                "LeftUpLeg": "left_thigh",
                "LeftLeg": "left_shin",
                "LeftFoot": "left_foot",
                "RightUpLeg": "right_thigh",
                "RightLeg": "right_shin",
                "RightFoot": "right_foot",
            },
        }

    def _calculate_skinning_quality(self, rigged_mesh: RiggedMesh) -> float:
        """Calculate skinning quality metric (0-1)."""
        weights = rigged_mesh.weights

        # Check weight distribution
        weight_variance = weights.var(axis=0).mean()

        # Check smoothness (neighboring vertices should have similar weights)
        # This is simplified - in production would use mesh connectivity
        quality = 1.0 - min(weight_variance * 2, 1.0)

        return float(quality)

    def _check_health(self) -> bool:
        """Check component health status."""
        try:
            # For unirig/auto, consider healthy once initialized unless real models are explicitly required
            if self.config.get("method", "unirig") in ["unirig", "auto"]:
                if self.config.get("require_real_models", False) and self.unirig_model is None:
                    return False

            # Check if skeleton templates are available
            if not self.skeleton_templates and self.config.get("method") == "template":
                return False

            # Component is healthy if initialized
            return self.initialized
        except Exception:
            return False

    def _get_status_specific(self) -> dict[str, Any]:
        """Get rigging module specific status information."""
        return {
            "unirig_available": self.unirig_model is not None,
            "skeleton_templates": list(self.skeleton_templates.keys()),
            "rigging_method": self.config.get("method", "unirig"),
            "max_influences_per_vertex": self.config.get("max_influences_per_vertex", 4),
        }
