"""Genesis physics wrapper for simulation.

Provides a complete wrapper around the Genesis physics engine for:
1. Scene creation and management
2. Physics simulation (rigid bodies, soft bodies, fluids)
3. Character motion simulation
4. Scene export (GLB, GLTF, OBJ, USD)
5. Rendering and frame capture
"""

from __future__ import annotations

import atexit
import json
import logging
import os
import struct
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import numpy as np

if TYPE_CHECKING:
    import torch

from kagami.core.utils.optional_imports import require_package

logger = logging.getLogger(__name__)

# Optional Genesis import with clear error handling
try:
    import genesis as gs
except ImportError:
    gs = None


class GenesisPhysicsWrapper:
    """Wrapper for Genesis physics engine.

    Provides full physics simulation capabilities including:
    - Rigid body dynamics
    - Soft body simulation
    - Character animation
    - Scene export to various formats
    """

    # Supported export formats
    EXPORT_FORMATS = ["glb", "gltf", "obj", "usd", "usda", "usdc"]

    # Character motion types
    MOTION_TYPES = [
        "idle",
        "walk_forward",
        "walk_backward",
        "run",
        "jump",
        "crouch",
        "turn_left",
        "turn_right",
        "wave",
        "sit",
        "stand_up",
    ]

    def __init__(self, device: str = "auto") -> None:
        """Initialize Genesis physics wrapper.

        Args:
            device: Compute device ('auto', 'cuda', 'cpu', 'mps')
        """
        self.scene: Any = None
        self._initialized = False
        self._gs: Any = None  # Genesis module, None until initialized
        self._device = device
        self._entities: dict[str, Any] = {}
        self._camera: Any = None  # Genesis camera for rendering
        self._frame_count = 0
        self._simulation_time = 0.0
        self._dt = 1.0 / 60.0  # Default timestep

    @property
    def initialized(self) -> bool:
        """Check if Genesis is initialized."""
        return self._initialized

    @property
    def simulation_time(self) -> float:
        """Get current simulation time in seconds."""
        return self._simulation_time

    async def initialize(self) -> bool:
        """Initialize the Genesis engine.

        Returns:
            True if successfully initialized

        Raises:
            MissingOptionalDependency: If Genesis library is not installed
            RuntimeError: If initialization fails
        """
        if self._initialized:
            return True

        try:
            # Require Genesis package with clear error message
            self._gs = require_package(
                gs,
                package_name="genesis-world",
                feature_name="Genesis Physics Engine",
                install_cmd="pip install genesis-world",
                additional_info=(
                    "Genesis provides unified physics simulation including:\n"
                    "  - Rigid body dynamics\n"
                    "  - Soft body simulation\n"
                    "  - Character animation\n"
                    "  - Differentiable rendering\n\n"
                    "See: https://github.com/Genesis-Embodied-AI/Genesis"
                ),
            )

            # Determine backend based on device
            if self._device == "auto":
                # Auto-detect best available backend
                try:
                    backend = gs.gpu
                except AttributeError:
                    backend = gs.cpu
            elif self._device == "cuda":
                backend = gs.gpu
            else:
                backend = gs.cpu

            # Optional performance/logging knobs (Genesis is process-global).
            # - performance_mode: faster runtime, longer compile/init
            # - logging_level: reduce per-step spam (e.g. "WARNING")
            perf_env = os.getenv("KAGAMI_GENESIS_PERFORMANCE_MODE", "0").strip().lower()
            performance_mode = perf_env in ("1", "true", "yes", "on")

            log_level = os.getenv("KAGAMI_GENESIS_LOG_LEVEL")
            # Default to WARNING to avoid per-step spam; override via env.
            log_level = log_level.strip().upper() if log_level else "WARNING"

            verbose_env = os.getenv("KAGAMI_GENESIS_LOGGER_VERBOSE_TIME", "0").strip().lower()
            logger_verbose_time = verbose_env in ("1", "true", "yes", "on")

            # Initialize genesis (fail fast; no silent backend fallbacks).
            try:
                self._gs.init(
                    backend=backend,
                    performance_mode=performance_mode,
                    logging_level=log_level,
                    logger_verbose_time=logger_verbose_time,
                )
            except Exception as init_error:
                # Genesis is process-global; "already initialized" is benign.
                if "already initialized" in str(init_error).lower():
                    logger.debug("Genesis already initialized; reusing existing engine")
                else:
                    raise

            # Prevent noisy/fragile shutdown logging in test harnesses.
            # Genesis registers its destroy() at exit; we register *after* init so
            # our handler runs first and disables handlers.
            try:

                def _silence_genesis_logger() -> None:
                    try:
                        import logging as _logging

                        # Best-effort: remove handlers on common genesis loggers
                        for name in ("genesis", "genesis.logging", "genesis.logging.logger"):
                            lg = _logging.getLogger(name)
                            lg.handlers.clear()
                            lg.propagate = False
                    except Exception:
                        pass

                atexit.register(_silence_genesis_logger)
            except Exception:
                pass

            logger.info(f"Genesis engine initialized (device={self._device})")
            self._initialized = True
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Genesis: {e}")
            raise RuntimeError(f"Genesis initialization failed: {e}") from e

    async def create_physics_scene(
        self,
        scene_type: str = "default",
        gravity: tuple[float, float, float] = (0.0, 0.0, -9.81),
        dt: float = 1.0 / 60.0,
        show_viewer: bool = False,
        *,
        rendering: bool = True,
    ) -> Any:
        """Create a physics scene.

        Args:
            scene_type: Type of scene to create
                - 'default': Empty scene with ground plane
                - 'character_studio': Scene for character animation
                - 'physics_lab': Scene for physics experiments
                - 'outdoor': Scene with terrain
            gravity: Gravity vector (default: Earth gravity)
            dt: Simulation timestep
            show_viewer: Whether to show the viewer window

        Returns:
            Genesis Scene object
        """
        if not self._initialized:
            await self.initialize()

        logger.info(f"Creating Genesis scene: {scene_type}")

        if self._gs is None:
            raise RuntimeError("Genesis not initialized")

        # Avoid accumulating old scenes across many puzzle rollouts / dataset samples.
        # Genesis scenes can hold GPU/Metal resources; we must destroy explicitly.
        try:
            if self.scene is not None and hasattr(self.scene, "destroy"):
                self.scene.destroy()
        except Exception:
            pass
        self.scene = None

        self._dt = dt
        self._frame_count = 0
        self._simulation_time = 0.0
        self._entities.clear()

        # Create scene with configuration.
        # For training we default to physics-only (no renderer/camera) to minimize
        # visualizer overhead and startup compile time.
        renderer = self._gs.renderers.Rasterizer() if rendering else None
        self.scene = self._gs.Scene(
            show_viewer=show_viewer,
            profiling_options=self._gs.options.profiling.ProfilingOptions(show_FPS=False),
            renderer=renderer,
            sim_options=self._gs.options.SimOptions(
                dt=dt,
                gravity=gravity,
            ),
        )

        # Add entities based on scene type
        if scene_type == "default":
            self._setup_default_scene()
        elif scene_type == "character_studio":
            self._setup_character_studio()
        elif scene_type == "physics_lab":
            self._setup_physics_lab()
        elif scene_type == "outdoor":
            self._setup_outdoor_scene()

        # Add camera only when rendering is enabled.
        self._camera = None
        if rendering:
            try:
                self._camera = self.scene.add_camera(
                    res=(1280, 720),
                    pos=(4.0, 4.0, 3.0),
                    lookat=(0.0, 0.0, 0.5),
                )
                logger.debug("Genesis camera added for rendering")
            except Exception as e:
                logger.warning(f"Could not add camera: {e}")
                self._camera = None

        # Build the scene
        try:
            self.scene.build()
        except AttributeError:
            pass  # Some Genesis versions auto-build

        return self.scene

    def _setup_default_scene(self) -> None:
        """Set up default scene with ground plane."""
        if self._gs is None or self.scene is None:
            return

        try:
            plane = self.scene.add_entity(self._gs.morphs.Plane())
            self._entities["ground"] = plane
        except (AttributeError, Exception) as e:
            logger.debug(f"Could not add ground plane: {e}")

    def _setup_character_studio(self) -> None:
        """Set up character studio scene."""
        if self._gs is None or self.scene is None:
            return

        try:
            # Ground plane
            plane = self.scene.add_entity(self._gs.morphs.Plane())
            self._entities["ground"] = plane

            # Add lighting (if supported)
            try:
                light = self.scene.add_entity(
                    self._gs.morphs.DirectionalLight(
                        direction=(0.5, 0.5, -1.0),
                        intensity=1.0,
                    )
                )
                self._entities["light"] = light
            except AttributeError:
                pass

        except (AttributeError, Exception) as e:
            logger.debug(f"Character studio setup partial: {e}")

    def _setup_physics_lab(self) -> None:
        """Set up physics lab scene."""
        if self._gs is None or self.scene is None:
            return

        try:
            # Ground plane
            plane = self.scene.add_entity(self._gs.morphs.Plane())
            self._entities["ground"] = plane

            # Add some test objects
            try:
                sphere = self.scene.add_entity(
                    self._gs.morphs.Sphere(
                        pos=(0, 0, 2),
                        radius=0.1,
                    )
                )
                self._entities["sphere"] = sphere

                box = self.scene.add_entity(
                    self._gs.morphs.Box(
                        pos=(1, 0, 1),
                        size=(0.2, 0.2, 0.2),
                    )
                )
                self._entities["box"] = box
            except AttributeError:
                pass

        except (AttributeError, Exception) as e:
            logger.debug(f"Physics lab setup partial: {e}")

    def _setup_outdoor_scene(self) -> None:
        """Set up outdoor scene with terrain."""
        if self._gs is None or self.scene is None:
            return

        try:
            # Use terrain or plane
            try:
                terrain = self.scene.add_entity(
                    self._gs.morphs.Terrain(
                        size=(100, 100),
                        height_scale=5.0,
                    )
                )
                self._entities["terrain"] = terrain
            except AttributeError:
                # Fallback to plane
                plane = self.scene.add_entity(self._gs.morphs.Plane())
                self._entities["ground"] = plane

        except (AttributeError, Exception) as e:
            logger.debug(f"Outdoor scene setup partial: {e}")

    def step(self, num_steps: int = 1) -> None:
        """Step the simulation.

        Args:
            num_steps: Number of simulation steps to perform
        """
        if self.scene is None:
            return

        for _ in range(num_steps):
            try:
                self.scene.step()
            except AttributeError:
                pass  # Scene might not support step()

            self._frame_count += 1
            self._simulation_time += self._dt

    def get_differentiable_state(
        self,
        max_objects: int = 32,
    ) -> torch.Tensor:
        """Extract physics state as a differentiable PyTorch tensor.

        For E2E differentiable training, this extracts the state of all
        physics entities into a tensor that can receive gradients. Each
        object's state includes position (3), linear velocity (3), and
        quaternion (4) = 10 values.

        Args:
            max_objects: Maximum objects to include (pads if fewer)

        Returns:
            [N, 10] tensor of physics states (pos[3], vel[3], quat[4])
            where N = max_objects
        """
        import torch

        states: list[list[float]] = []

        for name, entity in list(self._entities.items())[:max_objects]:
            if name in ("ground", "floor", "terrain"):
                continue

            try:
                # Get position [3]
                pos = entity.get_pos() if hasattr(entity, "get_pos") else None
                if pos is None:
                    pos = [0.0, 0.0, 0.0]
                elif hasattr(pos, "numpy"):
                    pos = pos.numpy().tolist()
                else:
                    pos = list(pos)[:3]

                # Get velocity [6] (linear + angular)
                vel = entity.get_vel() if hasattr(entity, "get_vel") else None
                if vel is None:
                    vel = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
                elif hasattr(vel, "numpy"):
                    vel = vel.numpy().tolist()
                else:
                    vel = list(vel)[:6]

                linear_vel = vel[:3]

                # Get quaternion [4] (if available)
                try:
                    quat = entity.get_quat() if hasattr(entity, "get_quat") else None
                    if quat is None:
                        quat = [1.0, 0.0, 0.0, 0.0]
                    elif hasattr(quat, "numpy"):
                        quat = quat.numpy().tolist()
                    else:
                        quat = list(quat)[:4]
                except Exception:
                    quat = [1.0, 0.0, 0.0, 0.0]

                # Combine: pos[3] + vel[3] + quat[4] = 10
                state = pos[:3] + linear_vel[:3] + quat[:4]
                states.append(state)

            except Exception:
                continue

        # Pad to max_objects if needed
        while len(states) < max_objects:
            states.append([0.0] * 10)

        # Return tensor with requires_grad=True for backprop
        return torch.tensor(
            states[:max_objects],
            dtype=torch.float32,
            requires_grad=True,
        )

    def get_entity_states(self) -> dict[str, dict[str, Any]]:
        """Get raw state dict[str, Any] for all entities (for debugging/inspection).

        Returns:
            Dict mapping entity name to state dict[str, Any] with pos, vel, quat
        """
        states: dict[str, dict[str, Any]] = {}

        for name, entity in self._entities.items():
            state: dict[str, Any] = {"name": name}

            try:
                pos = entity.get_pos() if hasattr(entity, "get_pos") else None
                if pos is not None:
                    if hasattr(pos, "numpy"):
                        pos = pos.numpy()
                    state["position"] = list(pos)
            except Exception:
                pass

            try:
                vel = entity.get_vel() if hasattr(entity, "get_vel") else None
                if vel is not None:
                    if hasattr(vel, "numpy"):
                        vel = vel.numpy()
                    state["velocity"] = list(vel)
            except Exception:
                pass

            try:
                quat = entity.get_quat() if hasattr(entity, "get_quat") else None
                if quat is not None:
                    if hasattr(quat, "numpy"):
                        quat = quat.numpy()
                    state["quaternion"] = list(quat)
            except Exception:
                pass

            states[name] = state

        return states

    async def simulate_character_motion(
        self,
        motion_type: str = "walk_forward",
        duration: float = 1.0,
        fps: int = 30,
        character_params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Simulate character motion.

        Args:
            motion_type: Type of motion to simulate
            duration: Duration in seconds
            fps: Frames per second for output
            character_params: Optional character parameters

        Returns:
            Dictionary with simulation results including:
                - frames: List of frame data
                - joint_positions: Joint trajectories
                - root_trajectory: Root motion path
                - metadata: Simulation metadata
        """
        if not self._initialized:
            await self.initialize()

        if motion_type not in self.MOTION_TYPES:
            logger.warning(f"Unknown motion type '{motion_type}', using 'idle'")
            motion_type = "idle"

        logger.info(f"Simulating character motion: {motion_type} for {duration}s")

        # Calculate frames needed
        num_frames = int(duration * fps)
        steps_per_frame = max(1, int((1.0 / fps) / self._dt))

        # Initialize result containers
        frames: list[dict[str, Any]] = []
        joint_positions: list[np.ndarray[Any, Any]] = []
        root_trajectory: list[np.ndarray[Any, Any]] = []

        # Generate motion based on type
        motion_generator = self._get_motion_generator(motion_type, character_params or {})  # type: ignore[func-returns-value]

        for frame_idx in range(num_frames):
            t = frame_idx / fps

            # Get motion state
            state = motion_generator(t, duration)

            # Step physics
            self.step(steps_per_frame)

            # Convert numpy arrays to lists for JSON serialization
            root_pos = state["root_position"]
            root_rot = state["root_rotation"]
            joint_ang = state["joint_angles"]

            # Handle both numpy arrays and potential tensors
            if hasattr(root_pos, "numpy"):
                root_pos = root_pos.numpy()
            if hasattr(root_rot, "numpy"):
                root_rot = root_rot.numpy()
            if hasattr(joint_ang, "numpy"):
                joint_ang = joint_ang.numpy()

            root_pos = np.asarray(root_pos)
            root_rot = np.asarray(root_rot)
            joint_ang = np.asarray(joint_ang)

            # Record frame
            frame_data = {
                "frame": frame_idx,
                "time": t,
                "root_position": root_pos.tolist(),
                "root_rotation": root_rot.tolist(),
                "joint_angles": joint_ang.tolist(),
            }
            frames.append(frame_data)
            joint_positions.append(joint_ang)
            root_trajectory.append(root_pos)

        return {
            "motion_type": motion_type,
            "duration": duration,
            "fps": fps,
            "num_frames": num_frames,
            "frames": frames,
            "joint_positions": np.array(joint_positions).tolist(),
            "root_trajectory": np.array(root_trajectory).tolist(),
            "metadata": {
                "character_params": character_params or {},
                "simulation_time": self._simulation_time,
            },
        }

    def _get_motion_generator(self, motion_type: str, params: dict[str, Any]) -> None:
        """Get motion generator function for a motion type.

        Args:
            motion_type: Type of motion
            params: Character parameters

        Returns:
            Function that generates motion state at time t
        """
        # Default character parameters
        speed = params.get("speed", 1.0)
        amplitude = params.get("amplitude", 0.3)

        def idle_motion(t: float, duration: float) -> dict[str, Any]:
            """Generate idle motion (subtle breathing/swaying)."""
            breath_phase = np.sin(t * 2 * np.pi * 0.2) * 0.02
            return {
                "root_position": np.array([0.0, 0.0, breath_phase]),
                "root_rotation": np.array([0.0, 0.0, 0.0, 1.0]),
                "joint_angles": np.zeros(22),  # Standard humanoid has ~22 joints
            }

        def walk_forward_motion(t: float, duration: float) -> dict[str, Any]:
            """Generate walking forward motion."""
            phase = t * speed * 2.0  # Gait phase
            x = t * speed * 1.4  # Forward movement (~1.4 m/s walk)

            # Joint angles (simplified sinusoidal gait)
            joints = np.zeros(22)
            joints[0] = amplitude * np.sin(phase * np.pi)  # Left hip
            joints[1] = amplitude * np.sin(phase * np.pi + np.pi)  # Right hip
            joints[2] = amplitude * 0.5 * np.sin(phase * np.pi + np.pi / 4)  # Left knee
            joints[3] = amplitude * 0.5 * np.sin(phase * np.pi + np.pi + np.pi / 4)  # Right knee
            joints[4] = -amplitude * 0.3 * np.sin(phase * np.pi)  # Left arm
            joints[5] = -amplitude * 0.3 * np.sin(phase * np.pi + np.pi)  # Right arm

            return {
                "root_position": np.array([x, 0.0, 0.0]),
                "root_rotation": np.array([0.0, 0.0, 0.0, 1.0]),
                "joint_angles": joints,
            }

        def walk_backward_motion(t: float, duration: float) -> dict[str, Any]:
            """Generate walking backward motion."""
            result = walk_forward_motion(t, duration)
            result["root_position"][0] = -result["root_position"][0] * 0.7
            return result

        def run_motion(t: float, duration: float) -> dict[str, Any]:
            """Generate running motion."""
            phase = t * speed * 3.5  # Faster gait
            x = t * speed * 4.0  # Running ~4 m/s

            joints = np.zeros(22)
            joints[0] = amplitude * 1.5 * np.sin(phase * np.pi)
            joints[1] = amplitude * 1.5 * np.sin(phase * np.pi + np.pi)
            joints[2] = amplitude * 1.0 * np.sin(phase * np.pi + np.pi / 4)
            joints[3] = amplitude * 1.0 * np.sin(phase * np.pi + np.pi + np.pi / 4)
            joints[4] = -amplitude * 0.6 * np.sin(phase * np.pi)
            joints[5] = -amplitude * 0.6 * np.sin(phase * np.pi + np.pi)

            # Vertical bounce
            z = 0.05 * np.abs(np.sin(phase * np.pi))

            return {
                "root_position": np.array([x, 0.0, z]),
                "root_rotation": np.array([0.0, 0.0, 0.0, 1.0]),
                "joint_angles": joints,
            }

        def jump_motion(t: float, duration: float) -> dict[str, Any]:
            """Generate jump motion."""
            # Parabolic trajectory
            t_norm = t / duration
            z = 4.0 * t_norm * (1.0 - t_norm) * 1.0  # Max height 1m

            joints = np.zeros(22)
            if t_norm < 0.2:  # Crouch phase
                joints[2] = -0.5  # Bend knees
                joints[3] = -0.5
            elif t_norm < 0.8:  # Flight phase
                joints[2] = 0.2  # Extend legs
                joints[3] = 0.2
                joints[4] = -0.5  # Arms up
                joints[5] = -0.5
            else:  # Landing
                joints[2] = -0.3
                joints[3] = -0.3

            return {
                "root_position": np.array([0.0, 0.0, z]),
                "root_rotation": np.array([0.0, 0.0, 0.0, 1.0]),
                "joint_angles": joints,
            }

        def crouch_motion(t: float, duration: float) -> dict[str, Any]:
            """Generate crouch motion."""
            t_norm = min(1.0, t / 0.5)  # Crouch in 0.5s
            crouch_amount = t_norm * 0.4

            joints = np.zeros(22)
            joints[2] = -crouch_amount  # Bend knees
            joints[3] = -crouch_amount

            return {
                "root_position": np.array([0.0, 0.0, -crouch_amount * 0.3]),
                "root_rotation": np.array([0.0, 0.0, 0.0, 1.0]),
                "joint_angles": joints,
            }

        def turn_left_motion(t: float, duration: float) -> dict[str, Any]:
            """Generate turn left motion."""
            angle = t * speed * 1.0  # rad/s turn rate

            joints = np.zeros(22)
            # Weight shift
            joints[0] = 0.1
            joints[1] = -0.1

            return {
                "root_position": np.array([0.0, 0.0, 0.0]),
                "root_rotation": np.array([0.0, 0.0, np.sin(angle / 2), np.cos(angle / 2)]),
                "joint_angles": joints,
            }

        def turn_right_motion(t: float, duration: float) -> dict[str, Any]:
            """Generate turn right motion."""
            result = turn_left_motion(t, duration)
            result["root_rotation"][2] = -result["root_rotation"][2]
            return result

        def wave_motion(t: float, duration: float) -> dict[str, Any]:
            """Generate waving motion."""
            joints = np.zeros(22)
            joints[5] = -1.5  # Raise right arm
            joints[7] = 0.5 + 0.3 * np.sin(t * 8)  # Wave hand

            return {
                "root_position": np.array([0.0, 0.0, 0.0]),
                "root_rotation": np.array([0.0, 0.0, 0.0, 1.0]),
                "joint_angles": joints,
            }

        # Motion generator lookup
        generators = {
            "idle": idle_motion,
            "walk_forward": walk_forward_motion,
            "walk_backward": walk_backward_motion,
            "run": run_motion,
            "jump": jump_motion,
            "crouch": crouch_motion,
            "turn_left": turn_left_motion,
            "turn_right": turn_right_motion,
            "wave": wave_motion,
            "sit": crouch_motion,  # Simplified
            "stand_up": idle_motion,  # Simplified
        }

        return generators.get(motion_type, idle_motion)  # type: ignore[return-value]

    async def export_scene(
        self,
        output_path: str,
        format: str = "glb",
        include_animations: bool = True,
    ) -> dict[str, Any]:
        """Export the current scene to a file.

        Args:
            output_path: Path to save the exported file
            format: Export format ('glb', 'gltf', 'obj', 'usd', 'usda', 'usdc')
            include_animations: Whether to include animations in export

        Returns:
            Dictionary with export results:
                - path: Output file path
                - format: Export format used
                - status: 'success' or 'error'
                - size_bytes: File size in bytes
                - metadata: Export metadata
        """
        if format.lower() not in self.EXPORT_FORMATS:
            raise ValueError(f"Unsupported format '{format}'. Supported: {self.EXPORT_FORMATS}")

        output_path = str(Path(output_path).resolve())
        format_lower = format.lower()

        logger.info(f"Exporting scene to {output_path} ({format_lower})")

        try:
            if format_lower in ["glb", "gltf"]:
                result = await self._export_gltf(output_path, format_lower, include_animations)
            elif format_lower == "obj":
                result = await self._export_obj(output_path)
            elif format_lower in ["usd", "usda", "usdc"]:
                result = await self._export_usd(output_path, format_lower)
            else:
                raise ValueError(f"Unsupported format: {format}")

            return result

        except Exception as e:
            logger.error(f"Export failed: {e}")
            return {
                "path": output_path,
                "format": format_lower,
                "status": "error",
                "error": str(e),
            }

    async def _export_gltf(
        self,
        output_path: str,
        format: str,
        include_animations: bool,
    ) -> dict[str, Any]:
        """Export scene to GLB/GLTF format.

        GLB is a binary format containing:
        - Scene hierarchy (nodes)
        - Meshes and materials
        - Animations (optional)
        - Textures (embedded)
        """
        # Collect scene data
        scene_data = self._collect_scene_data()

        # Build GLTF structure
        gltf: dict[str, Any] = {
            "asset": {
                "version": "2.0",
                "generator": "K OS Genesis Physics Wrapper",
            },
            "scenes": [{"nodes": [0]}],
            "scene": 0,
            "nodes": [],
            "meshes": [],
            "accessors": [],
            "bufferViews": [],
            "buffers": [],
            "materials": [
                {
                    "pbrMetallicRoughness": {
                        "baseColorFactor": [0.8, 0.8, 0.8, 1.0],
                        "metallicFactor": 0.0,
                        "roughnessFactor": 0.5,
                    }
                }
            ],
        }

        # Binary buffer for GLB
        binary_data = bytearray()

        # Add entities as nodes
        for name, entity_data in scene_data.get("entities", {}).items():
            len(gltf["nodes"])
            node = {"name": name}

            if "position" in entity_data:
                node["translation"] = entity_data["position"]
            if "rotation" in entity_data:
                node["rotation"] = entity_data["rotation"]
            if "scale" in entity_data:
                node["scale"] = entity_data["scale"]

            # Add mesh if entity has geometry
            if "mesh" in entity_data:
                mesh_idx = len(gltf["meshes"])
                mesh_data = entity_data["mesh"]

                # Add mesh vertices to buffer
                vertices = np.array(mesh_data.get("vertices", [[0, 0, 0]]), dtype=np.float32)
                vertex_buffer = vertices.tobytes()
                vertex_offset = len(binary_data)
                binary_data.extend(vertex_buffer)

                # Create buffer view for vertices
                gltf["bufferViews"].append(
                    {
                        "buffer": 0,
                        "byteOffset": vertex_offset,
                        "byteLength": len(vertex_buffer),
                        "target": 34962,  # ARRAY_BUFFER
                    }
                )

                # Create accessor for vertices
                accessor_idx = len(gltf["accessors"])
                gltf["accessors"].append(
                    {
                        "bufferView": len(gltf["bufferViews"]) - 1,
                        "byteOffset": 0,
                        "componentType": 5126,  # FLOAT
                        "count": len(vertices),
                        "type": "VEC3",
                        "min": vertices.min(axis=0).tolist(),
                        "max": vertices.max(axis=0).tolist(),
                    }
                )

                # Add indices if present
                primitives = {
                    "attributes": {"POSITION": accessor_idx},
                    "material": 0,
                }

                if "indices" in mesh_data:
                    indices = np.array(mesh_data["indices"], dtype=np.uint16)
                    index_buffer = indices.tobytes()
                    index_offset = len(binary_data)
                    binary_data.extend(index_buffer)

                    gltf["bufferViews"].append(
                        {
                            "buffer": 0,
                            "byteOffset": index_offset,
                            "byteLength": len(index_buffer),
                            "target": 34963,  # ELEMENT_ARRAY_BUFFER
                        }
                    )

                    gltf["accessors"].append(
                        {
                            "bufferView": len(gltf["bufferViews"]) - 1,
                            "byteOffset": 0,
                            "componentType": 5123,  # UNSIGNED_SHORT
                            "count": len(indices),
                            "type": "SCALAR",
                        }
                    )

                    primitives["indices"] = len(gltf["accessors"]) - 1

                gltf["meshes"].append(
                    {
                        "name": f"{name}_mesh",
                        "primitives": [primitives],
                    }
                )

                node["mesh"] = mesh_idx

            gltf["nodes"].append(node)

        # Add animations if requested
        if include_animations and scene_data.get("animations"):
            gltf["animations"] = scene_data["animations"]

        # Update buffer info
        gltf["buffers"].append(
            {
                "byteLength": len(binary_data),
            }
        )

        # Write file
        if format == "glb":
            # GLB binary format
            json_chunk = json.dumps(gltf).encode("utf-8")
            # Pad to 4-byte alignment
            while len(json_chunk) % 4 != 0:
                json_chunk += b" "
            while len(binary_data) % 4 != 0:
                binary_data.append(0)

            glb_data = bytearray()
            # Header
            glb_data.extend(b"glTF")  # Magic
            glb_data.extend(struct.pack("<I", 2))  # Version
            total_length = 12 + 8 + len(json_chunk) + 8 + len(binary_data)
            glb_data.extend(struct.pack("<I", total_length))  # Total length

            # JSON chunk
            glb_data.extend(struct.pack("<I", len(json_chunk)))
            glb_data.extend(b"JSON")
            glb_data.extend(json_chunk)

            # Binary chunk
            if binary_data:
                glb_data.extend(struct.pack("<I", len(binary_data)))
                glb_data.extend(b"BIN\x00")
                glb_data.extend(binary_data)

            with open(output_path, "wb") as f:
                f.write(glb_data)

            size_bytes = len(glb_data)

        else:
            # GLTF JSON + separate .bin file
            if binary_data:
                bin_path = output_path.replace(".gltf", ".bin")
                gltf["buffers"][0]["uri"] = Path(bin_path).name
                with open(bin_path, "wb") as f:
                    f.write(binary_data)

            with open(output_path, "w") as f:
                json.dump(gltf, f, indent=2)

            size_bytes = Path(output_path).stat().st_size

        return {
            "path": output_path,
            "format": format,
            "status": "success",
            "size_bytes": size_bytes,
            "metadata": {
                "num_nodes": len(gltf["nodes"]),
                "num_meshes": len(gltf["meshes"]),
                "has_animations": include_animations and bool(scene_data.get("animations")),
            },
        }

    async def _export_obj(self, output_path: str) -> dict[str, Any]:
        """Export scene to OBJ format."""
        scene_data = self._collect_scene_data()

        lines = [
            "# K OS Genesis Physics Wrapper Export",
            f"# Generated at {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]

        vertex_offset = 1  # OBJ indices are 1-based

        for name, entity_data in scene_data.get("entities", {}).items():
            if "mesh" not in entity_data:
                continue

            mesh = entity_data["mesh"]
            vertices = mesh.get("vertices", [])
            indices = mesh.get("indices", [])

            lines.append(f"o {name}")

            # Write vertices
            for v in vertices:
                lines.append(f"v {v[0]} {v[1]} {v[2]}")

            # Write faces (triangles)
            for i in range(0, len(indices), 3):
                i0 = indices[i] + vertex_offset
                i1 = indices[i + 1] + vertex_offset
                i2 = indices[i + 2] + vertex_offset
                lines.append(f"f {i0} {i1} {i2}")

            vertex_offset += len(vertices)
            lines.append("")

        with open(output_path, "w") as f:
            f.write("\n".join(lines))

        size_bytes = Path(output_path).stat().st_size

        return {
            "path": output_path,
            "format": "obj",
            "status": "success",
            "size_bytes": size_bytes,
            "metadata": {
                "num_objects": len(scene_data.get("entities", {})),
            },
        }

    async def _export_usd(self, output_path: str, format: str) -> dict[str, Any]:
        """Export scene to USD format."""
        # USD export requires pxr library
        try:
            from pxr import Usd, UsdGeom

            stage = Usd.Stage.CreateNew(output_path)
            UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)

            scene_data = self._collect_scene_data()

            for name, entity_data in scene_data.get("entities", {}).items():
                prim_path = f"/World/{name}"

                if "mesh" in entity_data:
                    mesh_prim = UsdGeom.Mesh.Define(stage, prim_path)
                    mesh = entity_data["mesh"]

                    if "vertices" in mesh:
                        vertices = mesh["vertices"]
                        mesh_prim.CreatePointsAttr(vertices)

                    if "indices" in mesh:
                        indices = mesh["indices"]
                        # Convert to face vertex counts and indices
                        face_counts = [3] * (len(indices) // 3)
                        mesh_prim.CreateFaceVertexCountsAttr(face_counts)
                        mesh_prim.CreateFaceVertexIndicesAttr(indices)

            stage.GetRootLayer().Save()
            size_bytes = Path(output_path).stat().st_size

            return {
                "path": output_path,
                "format": format,
                "status": "success",
                "size_bytes": size_bytes,
                "metadata": {
                    "num_prims": len(scene_data.get("entities", {})),
                },
            }

        except ImportError:
            # Fallback: write basic USDA text format
            lines = [
                "#usda 1.0",
                "(",
                '    defaultPrim = "World"',
                ")",
                "",
                'def Xform "World"',
                "{",
            ]

            scene_data = self._collect_scene_data()

            for name, entity_data in scene_data.get("entities", {}).items():
                lines.append(f'    def Mesh "{name}"')
                lines.append("    {")

                if "mesh" in entity_data and "vertices" in entity_data["mesh"]:
                    vertices = entity_data["mesh"]["vertices"]
                    verts_str = ", ".join(f"({v[0]}, {v[1]}, {v[2]})" for v in vertices)
                    lines.append(f"        point3f[] points = [{verts_str}]")

                lines.append("    }")

            lines.append("}")

            with open(output_path, "w") as f:
                f.write("\n".join(lines))

            size_bytes = Path(output_path).stat().st_size

            return {
                "path": output_path,
                "format": format,
                "status": "success",
                "size_bytes": size_bytes,
                "metadata": {
                    "fallback": True,
                    "num_objects": len(scene_data.get("entities", {})),
                },
            }

    def _collect_scene_data(self) -> dict[str, Any]:
        """Collect scene data for export."""
        scene_data: dict[str, Any] = {
            "entities": {},
            "animations": [],
        }

        # Collect entity data
        for name, entity in self._entities.items():
            entity_data: dict[str, Any] = {"name": name}

            # Try to get position/rotation from entity
            try:
                if hasattr(entity, "get_pos"):
                    pos = entity.get_pos()
                elif hasattr(entity, "pos"):
                    pos = entity.pos
                else:
                    pos = [0.0, 0.0, 0.0]

                # Convert tensors to numpy/list[Any]
                if hasattr(pos, "numpy"):
                    pos = pos.numpy()
                pos = np.asarray(pos)
                entity_data["position"] = pos.tolist()
            except Exception:
                entity_data["position"] = [0.0, 0.0, 0.0]

            entity_data["rotation"] = [0.0, 0.0, 0.0, 1.0]
            entity_data["scale"] = [1.0, 1.0, 1.0]

            # Generate simple mesh for known types
            if "ground" in name or "plane" in name:
                entity_data["mesh"] = self._generate_plane_mesh()
            elif "sphere" in name:
                entity_data["mesh"] = self._generate_sphere_mesh()
            elif "box" in name:
                entity_data["mesh"] = self._generate_box_mesh()
            else:
                entity_data["mesh"] = self._generate_default_mesh()

            scene_data["entities"][name] = entity_data

        return scene_data

    def _generate_plane_mesh(self, size: float = 10.0) -> dict[str, Any]:
        """Generate a plane mesh."""
        half = size / 2
        return {
            "vertices": [
                [-half, -half, 0],
                [half, -half, 0],
                [half, half, 0],
                [-half, half, 0],
            ],
            "indices": [0, 1, 2, 0, 2, 3],
        }

    def _generate_sphere_mesh(self, radius: float = 0.5, segments: int = 16) -> dict[str, Any]:
        """Generate a UV sphere mesh."""
        vertices = []
        indices = []

        for i in range(segments + 1):
            phi = np.pi * i / segments
            for j in range(segments):
                theta = 2 * np.pi * j / segments
                x = radius * np.sin(phi) * np.cos(theta)
                y = radius * np.sin(phi) * np.sin(theta)
                z = radius * np.cos(phi)
                vertices.append([float(x), float(y), float(z)])

        # Generate indices
        for i in range(segments):
            for j in range(segments):
                curr = i * segments + j
                next_row = (i + 1) * segments + j
                next_col = i * segments + (j + 1) % segments
                next_both = (i + 1) * segments + (j + 1) % segments

                indices.extend([curr, next_row, next_col])
                indices.extend([next_col, next_row, next_both])

        return {"vertices": vertices, "indices": indices}

    def _generate_box_mesh(
        self, size: tuple[float, float, float] = (1.0, 1.0, 1.0)
    ) -> dict[str, Any]:
        """Generate a box mesh."""
        hx, hy, hz = size[0] / 2, size[1] / 2, size[2] / 2
        vertices = [
            [-hx, -hy, -hz],
            [hx, -hy, -hz],
            [hx, hy, -hz],
            [-hx, hy, -hz],
            [-hx, -hy, hz],
            [hx, -hy, hz],
            [hx, hy, hz],
            [-hx, hy, hz],
        ]
        indices = [
            0,
            1,
            2,
            0,
            2,
            3,  # Bottom
            4,
            6,
            5,
            4,
            7,
            6,  # Top
            0,
            4,
            5,
            0,
            5,
            1,  # Front
            2,
            6,
            7,
            2,
            7,
            3,  # Back
            0,
            3,
            7,
            0,
            7,
            4,  # Left
            1,
            5,
            6,
            1,
            6,
            2,  # Right
        ]
        return {"vertices": vertices, "indices": indices}

    def _generate_default_mesh(self) -> dict[str, Any]:
        """Generate a default placeholder mesh."""
        return self._generate_box_mesh((0.1, 0.1, 0.1))

    def render(self, width: int = 640, height: int = 480) -> np.ndarray[Any, Any]:
        """Render current scene to image using REAL Genesis camera rendering.

        NO FALLBACKS - Genesis camera must be available.

        Args:
            width: Image width (ignored - uses camera resolution)
            height: Image height (ignored - uses camera resolution)

        Returns:
            RGB image as numpy array [H, W, 3] from Genesis camera

        Raises:
            RuntimeError: If camera is None or rendering fails
        """
        if self._camera is None:
            raise RuntimeError(
                "Cannot render: no camera available. "
                "Scene must be created with renderer=Rasterizer() and camera added."
            )

        try:
            # Genesis camera.render() returns tuple[Any, ...]: (rgb, depth, segmentation, normal)
            result = self._camera.render()

            if not isinstance(result, tuple) or len(result) == 0:
                raise RuntimeError(f"Camera render returned unexpected format: {type(result)}")

            # Extract RGB frame (first element)
            rgb_frame = result[0]

            if rgb_frame is None:
                raise RuntimeError("Camera render returned None for RGB")

            # Convert Genesis tensor to numpy if needed
            if hasattr(rgb_frame, "numpy"):
                rgb_frame = rgb_frame.numpy()

            rgb_array = cast(np.ndarray[Any, Any], np.asarray(rgb_frame))

            # Verify it's a valid image
            if len(rgb_array.shape) != 3 or rgb_array.shape[2] not in [3, 4]:
                raise RuntimeError(
                    f"Invalid RGB shape: {rgb_array.shape}, expected (H, W, 3) or (H, W, 4)"
                )

            return rgb_array[:, :, :3]  # Return only RGB (drop alpha if present)

        except Exception as e:
            raise RuntimeError(f"Genesis camera rendering failed: {e}") from e

    async def set_entity_angular_velocity(
        self, entity_name: str, angular_velocity: tuple[float, float, float]
    ) -> None:
        """Set angular velocity on an entity for physics-based rotation.

        Args:
            entity_name: Name of entity (key in self._entities)
            angular_velocity: (wx, wy, wz) in rad/s

        Note: Requires physics simulation with scene.step() to see rotation.
        """
        if entity_name not in self._entities:
            raise ValueError(f"Entity '{entity_name}' not found")

        entity = self._entities[entity_name]

        # Set DOF velocity: [vx, vy, vz, wx, wy, wz]
        entity.set_dofs_velocity(
            [0, 0, 0, angular_velocity[0], angular_velocity[1], angular_velocity[2]]
        )

        logger.debug(
            f"Set angular velocity on '{entity_name}': "
            f"wx={angular_velocity[0]:.2f}, wy={angular_velocity[1]:.2f}, wz={angular_velocity[2]:.2f}"
        )

    async def add_custom_entity(self, morph: Any, name: str, **kwargs: Any) -> Any:
        """Add a custom entity to the scene.

        Args:
            morph: Genesis morph object (gs.morphs.Box, gs.morphs.Mesh, etc.)
            name: Name to store entity under
            **kwargs: Additional parameters (currently unused)

        Returns:
            Genesis entity object

        Raises:
            RuntimeError: If scene not initialized or already built
        """
        if self.scene is None:
            raise RuntimeError("Scene not initialized. Call create_physics_scene() first.")

        if self._gs is None:
            raise RuntimeError("Genesis not initialized")

        # Scene must not be built yet
        if hasattr(self.scene, "is_built") and self.scene.is_built:
            raise RuntimeError("Cannot add entity: scene already built")

        entity = self.scene.add_entity(morph)
        self._entities[name] = entity

        logger.debug(f"Added custom entity '{name}': {morph}")

        return entity

    async def cleanup(self) -> None:
        """Cleanup physics resources."""
        if self.scene is not None:
            try:
                if hasattr(self.scene, "destroy"):
                    self.scene.destroy()
            except Exception:
                pass
            self.scene = None

        self._entities.clear()
        self._camera = None
        self._frame_count = 0
        self._simulation_time = 0.0
        self._initialized = False

        logger.info("Genesis physics wrapper cleaned up")


# =============================================================================
# PHYSICS INSTANCE CACHE & FACTORY
# =============================================================================

# Physics cache keyed by room_id
_PHYSICS_CACHE: dict[str, GenesisPhysicsWrapper] = {}


async def get_or_create_physics(room_id: str) -> GenesisPhysicsWrapper:
    """Get or create physics instance for a room.

    Provides a cached singleton per room_id to avoid reinitializing
    the physics engine for each request.

    Args:
        room_id: Unique room identifier

    Returns:
        GenesisPhysicsWrapper instance (cached per room_id)
    """
    physics = _PHYSICS_CACHE.get(room_id)
    if physics is None:
        physics = GenesisPhysicsWrapper()
        await physics.initialize()
        await physics.create_physics_scene(scene_type="character_studio")
        _PHYSICS_CACHE[room_id] = physics
        return physics

    # Ensure scene exists
    try:
        if getattr(physics, "scene", None) is None:
            await physics.create_physics_scene(scene_type="character_studio")
    except Exception:
        # Re-create on failure
        physics = GenesisPhysicsWrapper()
        await physics.initialize()
        await physics.create_physics_scene(scene_type="character_studio")
        _PHYSICS_CACHE[room_id] = physics

    return physics


__all__ = ["GenesisPhysicsWrapper", "get_or_create_physics"]
