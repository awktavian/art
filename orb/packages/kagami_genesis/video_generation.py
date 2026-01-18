"""Genesis Video Generation Pipeline — Complete Scene-to-Video Production.

This module provides an end-to-end pipeline for generating high-quality
physics-based rendered videos using the Genesis simulation engine. It
combines multi-physics simulation, ray-traced rendering, physics-based
audio synthesis, and professional cinematography into a unified workflow.

Core Capabilities:
    - Multi-physics simulation (Rigid, MPM, SPH, FEM, PBD solvers)
    - 40+ physically-accurate material presets with acoustic properties
    - Professional cinematography API (shots, sequences, camera movements)
    - Physics-based spatial audio synthesis (VBAP panning)
    - Intel OIDN denoising with Metal/CPU fallback
    - FFmpeg video assembly with configurable codecs

Physics Solvers:
    - RIGID: Traditional rigid body dynamics for hard objects
    - MPM_ELASTIC: Material Point Method for soft/bouncy materials
    - MPM_SNOW: Snow simulation with fracture
    - MPM_SAND: Granular material dynamics
    - SPH_LIQUID: Smoothed Particle Hydrodynamics for fluids
    - FEM_ELASTIC: Accurate soft body with stress/strain
    - FEM_MUSCLE: Actuatable soft bodies
    - PBD_CLOTH: Real-time fabric simulation

Pipeline Stages:
    1. Scene specification (VideoSpec with entities, lights, camera)
    2. Genesis scene construction (solver initialization, material assignment)
    3. Physics simulation loop with collision detection
    4. Ray-traced rendering with OIDN denoising
    5. Physics-based audio synthesis for collisions
    6. FFmpeg video/audio assembly

Usage:
    >>> from kagami_genesis.video_generation import VideoSpec, VideoGenerator
    >>> spec = VideoSpec(
    ...     output_dir="./output",
    ...     name="my_video",
    ...     duration=10.0,
    ...     fps=24,
    ... )
    >>> # Add physics entities
    >>> spec.entities.append(PhysicsEntitySpec(
    ...     name="ball",
    ...     solver=PhysicsSolver.RIGID,
    ...     shape="sphere",
    ...     position=(0, 0, 2),
    ...     size=0.1,
    ...     material_preset="chrome",
    ... ))
    >>> # Generate video
    >>> generator = VideoGenerator(spec)
    >>> await generator.generate()

Colony: Forge (e₂) × Spark (e₁) × Crystal (e₇)
Created: 2025
"""

from __future__ import annotations

import atexit
import logging
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np

from kagami_genesis.artistic_objects import (
    COLONY_PALETTES,
    ArtisticObjectFactory,
    create_neon_cathedral_objects,
)
from kagami_genesis.cinematography import (
    Cinematographer,
    Sequence,
    Shot,
)
from kagami_genesis.materials import (
    MATERIAL_PRESETS,
    AcousticProperties,
    MaterialLibrary,
    SurfaceType,
)
from kagami_genesis.optics import GenesisSurfaceSpec, RayTracerOptions
from kagami_genesis.realtime_renderer import (
    CollisionAudioSystem,
    RealtimeAudioEngine,
    RenderPreset,
    get_preset_config,
)
from kagami_genesis.solver_options import (
    FEMOptionsSpec,
    MPMOptionsSpec,
    PBDOptionsSpec,
    SPHOptionsSpec,
)

logger = logging.getLogger(__name__)


# =============================================================================
# PHYSICS SOLVERS (Genesis Diversity)
# =============================================================================


class PhysicsSolver(Enum):
    """Available Genesis physics solvers for different material behaviors.

    Genesis provides multiple physics backends optimized for different
    material types. Choosing the right solver is critical for visual
    realism and simulation performance.

    Solver Selection Guide:
        - RIGID: Hard objects (metal, wood, stone) - fastest
        - MPM_ELASTIC: Soft bouncy materials (rubber, jelly)
        - MPM_SNOW: Snow with compression and fracture
        - MPM_SAND: Loose granular materials (sand, gravel)
        - SPH_LIQUID: Incompressible fluids (water, oil)
        - FEM_ELASTIC: Accurate soft bodies with stress analysis
        - FEM_MUSCLE: Actuatable tissues (characters, creatures)
        - PBD_CLOTH: Real-time fabric and cloth

    Performance (relative):
        - RIGID: 1x (baseline, fastest)
        - PBD_CLOTH: 2x
        - MPM_*: 5-10x
        - SPH_LIQUID: 10x
        - FEM_*: 20x (most accurate, slowest)
    """

    RIGID = "rigid"
    """Traditional rigid body dynamics — hard objects with collision."""
    MPM_ELASTIC = "mpm_elastic"
    """Material Point Method with elastic constitutive model — soft/bouncy."""
    MPM_SNOW = "mpm_snow"
    """MPM with snow constitutive model — compressible with fracture."""
    MPM_SAND = "mpm_sand"
    """MPM with Drucker-Prager plasticity — granular materials."""
    SPH_LIQUID = "sph_liquid"
    """Smoothed Particle Hydrodynamics — incompressible fluids."""
    FEM_ELASTIC = "fem_elastic"
    """Finite Element Method — accurate deformable solids."""
    FEM_MUSCLE = "fem_muscle"
    """FEM with muscle activation — actuatable soft bodies."""
    PBD_CLOTH = "pbd_cloth"
    """Position-Based Dynamics — real-time cloth and fabric."""


@dataclass
class PhysicsEntitySpec:
    """Complete specification for a physics-simulated entity.

    Defines all properties needed to instantiate a physics object in
    Genesis, including geometry, material appearance, physics behavior,
    and acoustic properties for audio synthesis.

    Attributes:
        name: Unique identifier for this entity in the scene.
        solver: Physics solver type (determines simulation behavior).
        shape: Geometry type: "box", "sphere", "cylinder", "mesh", "plane".
        position: Initial position (x, y, z) in world coordinates.
        size: Dimensions — tuple (x, y, z) for boxes, float for sphere radius.
        material_preset: Key from MATERIAL_PRESETS for appearance/acoustics.
        surface: Optional GenesisSurfaceSpec to override material appearance.

        density: Mass density in kg/m³ (affects inertia and collisions).
        velocity: Initial linear velocity (x, y, z) in m/s.
        angular_velocity: Initial angular velocity (x, y, z) in rad/s.
        fixed: If True, entity is static (infinite mass, no movement).

        elastic_modulus: Young's modulus for MPM/FEM solvers (Pa).
            Higher = stiffer. Rubber ~1e6, Steel ~2e11.
        poisson_ratio: Lateral strain ratio for MPM/FEM (0-0.5).
            0 = no lateral expansion, 0.5 = incompressible.
        viscosity: Dynamic viscosity for SPH fluids (Pa·s).
            Water ~0.001, Honey ~2-10.
        surface_tension: Surface tension coefficient for SPH (N/m).
        friction_angle: Internal friction for granular materials (degrees).
            Sand ~30-35°.

        acoustic: Acoustic properties for collision sound synthesis.
            Auto-populated from material_preset if not specified.

    Example:
        >>> ball = PhysicsEntitySpec(
        ...     name="chrome_ball",
        ...     solver=PhysicsSolver.RIGID,
        ...     shape="sphere",
        ...     position=(0, 0, 2),
        ...     size=0.1,  # 10cm radius
        ...     material_preset="chrome",
        ...     velocity=(1.0, 0, 0),  # Moving right at 1 m/s
        ... )
    """

    name: str
    """Unique identifier for this entity."""
    solver: PhysicsSolver
    """Physics solver determining simulation behavior."""
    shape: str
    """Geometry: "box", "sphere", "cylinder", "mesh", "plane"."""
    position: tuple[float, float, float]
    """Initial world position (x, y, z) in meters."""
    size: tuple[float, float, float] | float
    """Dimensions: (x, y, z) for boxes, float radius for spheres."""
    material_preset: str | None = None
    """Material preset key from MATERIAL_PRESETS."""
    surface: GenesisSurfaceSpec | None = None
    """Optional surface overrides for appearance."""

    # Physics properties
    density: float = 2500.0
    """Mass density in kg/m³."""
    velocity: tuple[float, float, float] = (0.0, 0.0, 0.0)
    """Initial linear velocity (x, y, z) in m/s."""
    angular_velocity: tuple[float, float, float] = (0.0, 0.0, 0.0)
    """Initial angular velocity (x, y, z) in rad/s."""
    fixed: bool = False
    """If True, entity is immovable (static collider)."""

    # Solver-specific parameters
    elastic_modulus: float = 1e5
    """Young's modulus for soft body solvers (Pa)."""
    poisson_ratio: float = 0.3
    """Poisson's ratio for soft body solvers."""
    viscosity: float = 0.001
    """Dynamic viscosity for SPH fluids (Pa·s)."""
    surface_tension: float = 0.01
    """Surface tension for SPH fluids (N/m)."""
    friction_angle: float = 35.0
    """Internal friction angle for sand/granular (degrees)."""

    # Acoustic (auto-populated from material)
    acoustic: AcousticProperties | None = None
    """Acoustic properties for collision audio synthesis."""


@dataclass
class LightSpec:
    """Specification for a scene light source.

    Defines light position, color, and intensity for ray-traced rendering.
    Genesis uses physically-based lighting with emissive geometry.

    Note: Keep intensity low (1-10) to avoid overexposure. The ray tracer
    uses physically-correct light transport, so high values cause blowout.

    Attributes:
        name: Unique identifier for this light.
        position: World position (x, y, z) in meters.
        color: RGB color (0-1 range per channel). (1,1,1) = white.
        intensity: Light power multiplier. Keep in range 1-10.
        radius: Size of the emissive sphere in meters.
            Larger = softer shadows but slower rendering.
        type: Light type: "point" (omnidirectional), "spot", or "area".

    Example:
        >>> key_light = LightSpec(
        ...     name="key",
        ...     position=(2, -3, 4),
        ...     color=(1.0, 0.95, 0.9),  # Warm white
        ...     intensity=8.0,
        ...     radius=0.2,
        ... )
    """

    name: str
    """Unique identifier for this light."""
    position: tuple[float, float, float]
    """World position (x, y, z) in meters."""
    color: tuple[float, float, float] = (1.0, 1.0, 1.0)
    """RGB color (0-1 range). Default: white."""
    intensity: float = 5.0
    """Light power multiplier (keep 1-10 to avoid blowout)."""
    radius: float = 0.1
    """Emissive sphere radius (larger = softer shadows)."""
    type: str = "point"
    """Light type: "point", "spot", or "area"."""


@dataclass
class VideoSpec:
    """Complete specification for video generation.

    This is the top-level configuration object that defines everything
    needed to generate a physics-simulated video: output settings,
    quality parameters, scene content, camera setup, physics options,
    and audio configuration.

    Quality Presets:
        - PROOF: Fast preview (480p, 1 spp, no denoising)
        - PREVIEW: Better preview (720p, 4 spp, denoising)
        - DRAFT: Good quality (1080p, 16 spp, denoising)
        - FINAL: High quality (1080p, 64 spp, denoising)
        - MASTER: Maximum quality (4K, 256 spp, denoising)

    Attributes:
        output_dir: Directory for rendered frames and final video.
        name: Base name for output files (without extension).

        preset: Quality preset determining resolution/samples.
        width: Override preset width (pixels).
        height: Override preset height (pixels).
        fps: Frames per second for video output.
        duration: Total video duration in seconds.
        spp: Override samples per pixel for ray tracing.
        raytracer: Override ray tracer configuration.

        entities: List of physics entities in the scene.
        lights: List of light sources.
        ambient_light: RGB ambient light color (0-1 range).

        sequence: Cinematography sequence for camera animation.
        camera_pos: Default camera position (x, y, z).
        camera_lookat: Default camera look-at point (x, y, z).
        camera_fov: Field of view in degrees.
        camera_aperture: F-stop for depth of field (lower = more blur).
        camera_focus: Focus distance in meters.

    Example:
        >>> spec = VideoSpec(
        ...     output_dir="./renders",
        ...     name="bouncing_balls",
        ...     preset=RenderPreset.DRAFT,
        ...     duration=5.0,
        ...     fps=30,
        ... )
    """

    # Output configuration
    output_dir: str | Path
    """Directory for output files (frames, video, audio)."""
    name: str = "genesis_video"
    """Base name for output files."""

    # Quality settings
    preset: RenderPreset = RenderPreset.PROOF
    """Quality preset for resolution and sampling."""
    width: int | None = None
    """Override preset width in pixels."""
    height: int | None = None
    """Override preset height in pixels."""
    fps: int = 24
    """Frames per second for video output."""
    duration: float = 10.0
    """Total video duration in seconds."""
    spp: int | None = None
    """Override samples per pixel for ray tracing."""
    raytracer: RayTracerOptions | None = None
    """Override ray tracer configuration."""

    # Scene content
    entities: list[PhysicsEntitySpec] = field(default_factory=list)
    """Physics entities to simulate."""
    lights: list[LightSpec] = field(default_factory=list)
    """Light sources in the scene."""
    ambient_light: tuple[float, float, float] = (0.15, 0.15, 0.18)
    """Ambient light RGB (0-1 range)."""

    # Camera configuration
    sequence: Sequence | None = None
    """Cinematography sequence for animated camera."""
    camera_pos: tuple[float, float, float] = (0.0, -3.0, 1.5)
    """Default camera position (x, y, z) in meters."""
    camera_lookat: tuple[float, float, float] = (0.0, 0.0, 0.5)
    """Default camera look-at target (x, y, z)."""
    camera_fov: float = 45.0
    """Camera field of view in degrees."""
    camera_aperture: float = 2.8
    """F-stop for depth of field (lower = more blur)."""
    camera_focus: float = 4.0
    """Focus distance in meters."""

    # Physics
    gravity: tuple[float, float, float] = (0.0, 0.0, -9.81)
    dt: float = 1 / 60
    substeps: int = 4

    # SPH domain (for fluids)
    sph_bounds: tuple[tuple[float, float, float], tuple[float, float, float]] | None = None
    sph_particle_size: float = 0.02
    sph_options: SPHOptionsSpec | None = None
    mpm_options: MPMOptionsSpec | None = None
    fem_options: FEMOptionsSpec | None = None
    pbd_options: PBDOptionsSpec | None = None

    # Audio
    enable_audio: bool = True
    audio_sample_rate: int = 44100

    # Post-processing
    enable_denoising: bool = True
    assemble_video: bool = True


# =============================================================================
# VIDEO GENERATOR
# =============================================================================


class GenesisVideoGenerator:
    """End-to-end video generation with full Genesis diversity."""

    def __init__(self) -> None:
        """Initialize the video generator."""
        self._scene = None
        self._camera = None
        self._audio_engine: RealtimeAudioEngine | None = None
        self._collision_audio: CollisionAudioSystem | None = None
        self._denoiser = None
        self._entities: dict[str, Any] = {}

    def _cleanup(self) -> None:
        """Cleanup Genesis resources."""
        try:
            import genesis as gs

            gs.destroy()
        except Exception:
            pass

    def generate(
        self,
        spec: VideoSpec,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> Path:
        """Generate a video from specification.

        Args:
            spec: Complete video specification
            progress_callback: Optional (frame, total, message) callback

        Returns:
            Path to output directory
        """
        import genesis as gs

        # Register cleanup
        atexit.register(self._cleanup)

        # Setup output
        output_dir = Path(spec.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        frames_dir = output_dir / "frames"
        frames_dir.mkdir(exist_ok=True)

        # Get preset config
        preset_cfg = get_preset_config(spec.preset)
        width = spec.width or preset_cfg.width
        height = spec.height or preset_cfg.height
        spp = spec.spp or preset_cfg.spp

        logger.info(f"Video: {width}x{height} @ {spec.fps}fps, {spp} SPP")

        # Initialize audio
        if spec.enable_audio:
            self._audio_engine = RealtimeAudioEngine(
                sample_rate=spec.audio_sample_rate,
                buffer_ms=50,
            )
            self._collision_audio = CollisionAudioSystem(self._audio_engine)

        # Initialize Genesis
        gs.init(backend=gs.metal, precision="32", logging_level="warning")

        # Build scene options
        default_rt = RayTracerOptions(
            tracing_depth=preset_cfg.tracing_depth,
            rr_depth=4,
            env_radius=100.0,
        )
        rt = (
            self._merge_raytracer_options(default_rt, spec.raytracer)
            if spec.raytracer
            else default_rt
        )
        scene_opts = {
            "show_viewer": False,
            "renderer": gs.renderers.RayTracer(**rt.to_gs_kwargs(gs)),
            "sim_options": gs.options.SimOptions(
                dt=spec.dt,
                substeps=spec.substeps,
                gravity=spec.gravity,
            ),
            "vis_options": gs.options.VisOptions(
                ambient_light=spec.ambient_light,
            ),
        }

        # --- Solver option blocks (SPH/MPM/FEM/PBD) ---
        has_sph = bool(
            spec.sph_options
            or spec.sph_bounds
            or any(e.solver == PhysicsSolver.SPH_LIQUID for e in spec.entities),
        )
        if has_sph:
            bounds = spec.sph_bounds or ((-2.0, -2.0, 0.0), (2.0, 2.0, 3.0))
            base_sph = SPHOptionsSpec(
                lower_bound=bounds[0],
                upper_bound=bounds[1],
                particle_size=spec.sph_particle_size,
            )
            sph = base_sph.merged_with(spec.sph_options) if spec.sph_options else base_sph
            scene_opts["sph_options"] = gs.options.SPHOptions(**sph.to_gs_kwargs())

        has_mpm = bool(
            spec.mpm_options
            or any(
                e.solver
                in (
                    PhysicsSolver.MPM_ELASTIC,
                    PhysicsSolver.MPM_SNOW,
                    PhysicsSolver.MPM_SAND,
                )
                for e in spec.entities
            ),
        )
        if has_mpm:
            lower, upper = _infer_domain_bounds(
                [e for e in spec.entities if e.solver.name.startswith("MPM")],
                default_lower=(-1.0, -1.0, 0.0),
                default_upper=(1.0, 1.0, 1.0),
                padding=0.5,
            )
            base_mpm = MPMOptionsSpec(lower_bound=lower, upper_bound=upper)
            mpm = base_mpm.merged_with(spec.mpm_options) if spec.mpm_options else base_mpm
            scene_opts["mpm_options"] = gs.options.MPMOptions(**mpm.to_gs_kwargs())

        has_fem = bool(
            spec.fem_options
            or any(
                e.solver in (PhysicsSolver.FEM_ELASTIC, PhysicsSolver.FEM_MUSCLE)
                for e in spec.entities
            ),
        )
        if has_fem and spec.fem_options:
            scene_opts["fem_options"] = gs.options.FEMOptions(**spec.fem_options.to_gs_kwargs())

        has_pbd = bool(
            spec.pbd_options or any(e.solver == PhysicsSolver.PBD_CLOTH for e in spec.entities),
        )
        if has_pbd and spec.pbd_options:
            scene_opts["pbd_options"] = gs.options.PBDOptions(**spec.pbd_options.to_gs_kwargs())

        self._scene = gs.Scene(**scene_opts)

        # Add floor
        self._scene.add_entity(
            morph=gs.morphs.Plane(),
            material=gs.materials.Rigid(rho=2500),
            surface=gs.surfaces.Default(color=(0.2, 0.2, 0.22), roughness=0.3),
        )

        # Add entities
        for entity_spec in spec.entities:
            self._add_entity(entity_spec, gs)

        # Add lights
        for light_spec in spec.lights:
            self._add_light(light_spec, gs)

        # Add camera
        self._camera = self._scene.add_camera(
            model="thinlens",
            res=(width, height),
            pos=spec.camera_pos,
            lookat=spec.camera_lookat,
            fov=spec.camera_fov,
            aperture=spec.camera_aperture,
            focus_dist=spec.camera_focus,
            spp=spp,
        )

        # Build scene
        self._scene.build()

        # Initialize denoiser
        if spec.enable_denoising:
            self._init_denoiser()

        # Render loop
        total_frames = int(spec.fps * spec.duration)
        frames_rendered = 0

        for frame_idx in range(total_frames):
            t = frame_idx / spec.fps

            # Update camera from sequence
            if spec.sequence:
                cam_state = spec.sequence.get_camera_at(t)
                self._camera.set_pose(pos=cam_state.position, lookat=cam_state.lookat)

            # Physics step
            self._scene.step()

            # Audio update
            if self._collision_audio:
                cam_pos = spec.camera_pos
                if spec.sequence:
                    cam_pos = spec.sequence.get_camera_at(t).position
                self._collision_audio.update(t, cam_pos)

            # Render
            result = self._camera.render()
            rgb = result[0] if isinstance(result, tuple) else result
            if hasattr(rgb, "numpy"):
                rgb = rgb.numpy()

            # Process frame
            if rgb is not None:
                rgb = self._process_frame(rgb)
                frame_path = frames_dir / f"frame_{frame_idx:04d}.png"
                from PIL import Image

                Image.fromarray(rgb).save(frame_path)
                frames_rendered += 1

            # Callback
            if progress_callback:
                shot_name = ""
                if spec.sequence:
                    shot, _ = spec.sequence.get_shot_at(t)
                    shot_name = shot.name
                progress_callback(frame_idx + 1, total_frames, shot_name)

        # Cleanup Genesis
        gs.destroy()

        # Save audio
        audio_path = None
        if self._audio_engine and self._collision_audio:
            audio_buffer = self._collision_audio.get_audio()
            if audio_buffer is not None and len(audio_buffer) > 0:
                audio_path = output_dir / "audio.wav"
                self._audio_engine.save_audio(audio_buffer, audio_path)

        # Assemble video
        if spec.assemble_video:
            self._assemble_video(
                frames_dir,
                audio_path,
                output_dir / f"{spec.name}.mp4",
                spec.fps,
                spec.preset,
            )

        return output_dir

    def _add_entity(self, spec: PhysicsEntitySpec, gs: Any) -> None:
        """Add a physics entity to the scene."""
        # Get material preset if specified
        material_info = MATERIAL_PRESETS.get(spec.material_preset) if spec.material_preset else None

        # Create morph
        if spec.shape == "box":
            size = spec.size if isinstance(spec.size, tuple) else (spec.size,) * 3
            morph = gs.morphs.Box(pos=spec.position, size=size)
        elif spec.shape == "sphere":
            radius = spec.size if isinstance(spec.size, int | float) else spec.size[0]
            morph = gs.morphs.Sphere(pos=spec.position, radius=radius)
        elif spec.shape == "cylinder":
            size = (
                spec.size if isinstance(spec.size, tuple) else (spec.size, spec.size, spec.size * 2)
            )
            morph = gs.morphs.Cylinder(pos=spec.position, radius=size[0], height=size[2])
        else:
            morph = gs.morphs.Box(pos=spec.position, size=(0.1, 0.1, 0.1))

        # Create material based on solver
        if spec.solver == PhysicsSolver.RIGID:
            material = gs.materials.Rigid(rho=spec.density)
        elif spec.solver == PhysicsSolver.MPM_ELASTIC:
            material = gs.materials.MPM.Elastic(
                E=spec.elastic_modulus,
                nu=spec.poisson_ratio,
                rho=spec.density,
            )
        elif spec.solver == PhysicsSolver.MPM_SNOW:
            material = gs.materials.MPM.Snow(
                E=spec.elastic_modulus,
                nu=spec.poisson_ratio,
                rho=spec.density,
            )
        elif spec.solver == PhysicsSolver.MPM_SAND:
            material = gs.materials.MPM.Sand(
                rho=spec.density,
                friction_angle=spec.friction_angle,
            )
        elif spec.solver == PhysicsSolver.SPH_LIQUID:
            material = gs.materials.SPH.Liquid(
                rho=spec.density,
                mu=spec.viscosity,
                gamma=spec.surface_tension,
                sampler="regular",
            )
        elif spec.solver == PhysicsSolver.FEM_ELASTIC:
            material = gs.materials.FEM.Elastic(
                E=spec.elastic_modulus,
                nu=spec.poisson_ratio,
                rho=spec.density,
            )
        elif spec.solver == PhysicsSolver.FEM_MUSCLE:
            material = gs.materials.FEM.Muscle(
                E=spec.elastic_modulus,
                nu=spec.poisson_ratio,
                rho=spec.density,
                n_groups=1,
            )
        elif spec.solver == PhysicsSolver.PBD_CLOTH:
            material = gs.materials.PBD.Cloth()
        else:
            material = gs.materials.Rigid(rho=spec.density)

        # Create surface
        if material_info and spec.material_preset:
            surface = MaterialLibrary.create_surface(spec.material_preset, overrides=spec.surface)
        else:
            surface = gs.surfaces.Default(color=(0.5, 0.5, 0.5), roughness=0.3)

        # Add entity
        entity = self._scene.add_entity(
            morph=morph,
            material=material,
            surface=surface,
        )
        self._entities[spec.name] = entity

        # Register for collision audio
        if self._collision_audio and spec.material_preset:
            self._collision_audio.register_entity(
                spec.name,
                spec.material_preset,
                entity,
            )

    @staticmethod
    def _merge_raytracer_options(
        base: RayTracerOptions,
        override: RayTracerOptions,
    ) -> RayTracerOptions:
        """Merge override fields on top of base.

        Only non-None scalar fields win. `lights` is replaced if provided non-empty.
        `env_surface` is replaced if override provides it.
        """
        merged = dict(base.__dict__)
        for k, v in override.__dict__.items():
            if k == "lights":
                if v:
                    merged["lights"] = v
                continue
            if v is not None:
                merged[k] = v
        return RayTracerOptions(**merged)

    def _add_light(self, spec: LightSpec, gs: Any) -> None:
        """Add a light source to the scene."""
        emissive = tuple(c * spec.intensity for c in spec.color)
        self._scene.add_entity(
            morph=gs.morphs.Sphere(pos=spec.position, radius=spec.radius),
            material=gs.materials.Rigid(rho=100),
            surface=gs.surfaces.Emission(emissive=emissive),
        )

    def _init_denoiser(self) -> None:
        """Initialize OIDN denoiser."""
        try:
            from kagami.core.multimodal.vision.oidn_denoiser import OIDNDenoiser

            for device in ["metal", "cpu"]:
                try:
                    self._denoiser = OIDNDenoiser(device=device, quality="high")  # type: ignore[assignment]
                    logger.info(f"OIDN denoiser ready ({device})")
                    break
                except Exception:
                    continue
        except ImportError:
            logger.warning("OIDN denoiser not available")

    def _process_frame(self, rgb: np.ndarray) -> np.ndarray:
        """Process a rendered frame (denoise, tonemap)."""
        # Convert to float32
        if rgb.dtype == np.uint8:
            rgb_float = rgb.astype(np.float32) / 255.0
        else:
            rgb_float = rgb.astype(np.float32)
            if rgb_float.max() > 1.0:
                rgb_float /= 255.0

        # Denoise
        if self._denoiser:
            rgb_float = np.clip(rgb_float, 0.0, 1.0)
            rgb_float = self._denoiser.denoise(rgb_float)

        # Convert back to uint8
        return (rgb_float * 255).clip(0, 255).astype(np.uint8)

    def _assemble_video(
        self,
        frames_dir: Path,
        audio_path: Path | None,
        output_path: Path,
        fps: int,
        preset: RenderPreset,
    ) -> None:
        """Assemble frames into video with FFmpeg."""
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            logger.warning("ffmpeg not found")
            return

        crf = {RenderPreset.DAILIES: "23", RenderPreset.PROOF: "20", RenderPreset.FINAL: "18"}
        preset_flag = {
            RenderPreset.DAILIES: "veryfast",
            RenderPreset.PROOF: "medium",
            RenderPreset.FINAL: "slow",
        }

        cmd = [
            ffmpeg,
            "-y",
            "-framerate",
            str(fps),
            "-i",
            str(frames_dir / "frame_%04d.png"),
        ]

        if audio_path and audio_path.exists():
            cmd += ["-i", str(audio_path)]

        cmd += [
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-crf",
            crf.get(preset, "20"),
            "-preset",
            preset_flag.get(preset, "medium"),
        ]

        if audio_path and audio_path.exists():
            cmd += ["-c:a", "aac", "-b:a", "192k", "-shortest"]

        cmd.append(str(output_path))

        subprocess.run(cmd, check=True, capture_output=True)
        logger.info(f"Video assembled: {output_path}")


def _infer_domain_bounds(
    entities: list[PhysicsEntitySpec],
    *,
    default_lower: tuple[float, float, float],
    default_upper: tuple[float, float, float],
    padding: float = 0.0,
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """Infer a tight-ish domain bounding box from entity specs."""
    if not entities:
        return default_lower, default_upper

    min_x, min_y, min_z = float("inf"), float("inf"), float("inf")
    max_x, max_y, max_z = float("-inf"), float("-inf"), float("-inf")

    for e in entities:
        px, py, pz = e.position
        if e.shape == "sphere":
            r = float(e.size if isinstance(e.size, int | float) else e.size[0])
            hx, hy, hz = r, r, r
        elif e.shape == "cylinder":
            sz = (
                e.size
                if isinstance(e.size, tuple)
                else (float(e.size), float(e.size), float(e.size) * 2.0)
            )
            hx, hy, hz = float(sz[0]), float(sz[0]), float(sz[2]) / 2.0
        else:  # box (default)
            sz = e.size if isinstance(e.size, tuple) else (float(e.size),) * 3
            hx, hy, hz = float(sz[0]) / 2.0, float(sz[1]) / 2.0, float(sz[2]) / 2.0

        min_x = min(min_x, px - hx)
        min_y = min(min_y, py - hy)
        min_z = min(min_z, pz - hz)
        max_x = max(max_x, px + hx)
        max_y = max(max_y, py + hy)
        max_z = max(max_z, pz + hz)

    return (
        (min_x - padding, min_y - padding, min_z - padding),
        (max_x + padding, max_y + padding, max_z + padding),
    )


# =============================================================================
# PRESET SCENE GENERATORS
# =============================================================================


def create_material_showcase_spec(
    output_dir: str | Path,
    materials: list[str] | None = None,
) -> VideoSpec:
    """Create a spec showcasing material diversity.

    Args:
        output_dir: Output directory
        materials: List of material preset names (all if None)
    """
    if materials is None:
        materials = list(MATERIAL_PRESETS.keys())[:12]  # First 12

    entities = []
    cols = 4
    for i, mat_name in enumerate(materials):
        row, col = divmod(i, cols)
        x = (col - cols / 2 + 0.5) * 0.6
        y = row * 0.6 + 0.5

        entities.append(
            PhysicsEntitySpec(
                name=f"mat_{mat_name}",
                solver=PhysicsSolver.RIGID,
                shape="sphere",
                position=(x, y, 0.2),
                size=0.15,
                material_preset=mat_name,
            ),
        )

    lights = [
        LightSpec("key", (2, -2, 3), (1, 0.95, 0.9), 4.0),
        LightSpec("fill", (-2, -1, 2), (0.9, 0.95, 1.0), 2.0),
        LightSpec("rim", (0, 3, 2), (1, 1, 1), 3.0),
    ]

    return VideoSpec(
        output_dir=output_dir,
        name="material_showcase",
        preset=RenderPreset.PROOF,
        duration=5.0,
        entities=entities,
        lights=lights,
        camera_pos=(0, -3, 2),
        camera_lookat=(0, 1, 0.2),
        camera_fov=50,
    )


def create_physics_diversity_spec(
    output_dir: str | Path,
) -> VideoSpec:
    """Create a spec showcasing physics solver diversity."""
    entities = [
        # Rigid balls
        PhysicsEntitySpec(
            name="rigid_chrome",
            solver=PhysicsSolver.RIGID,
            shape="sphere",
            position=(-0.5, 0, 1.5),
            size=0.15,
            material_preset="chrome",
            velocity=(0.5, 0, 0),
        ),
        # MPM elastic (jelly)
        PhysicsEntitySpec(
            name="mpm_jelly",
            solver=PhysicsSolver.MPM_ELASTIC,
            shape="box",
            position=(0.5, 0.5, 1.0),
            size=(0.2, 0.2, 0.2),
            elastic_modulus=5e4,
            density=1200,
        ),
        # SPH water
        PhysicsEntitySpec(
            name="sph_water",
            solver=PhysicsSolver.SPH_LIQUID,
            shape="box",
            position=(0, -0.5, 0.8),
            size=(0.3, 0.3, 0.2),
            material_preset="water",
            viscosity=0.001,
            surface_tension=0.01,
        ),
        # Glass obstacle
        PhysicsEntitySpec(
            name="glass_prism",
            solver=PhysicsSolver.RIGID,
            shape="box",
            position=(0, 0, 0.15),
            size=(0.3, 0.3, 0.3),
            material_preset="glass",
            fixed=True,
        ),
    ]

    lights = [
        LightSpec("main", (2, -2, 3), (1, 1, 1), 5.0, 0.2),
        LightSpec("fill", (-1, 0, 2), (0.9, 0.95, 1.0), 2.0),
    ]

    return VideoSpec(
        output_dir=output_dir,
        name="physics_diversity",
        preset=RenderPreset.PROOF,
        duration=8.0,
        entities=entities,
        lights=lights,
        sph_bounds=((-1, -1, 0), (1, 1, 2)),
        camera_pos=(0, -3, 2),
        camera_lookat=(0, 0, 0.5),
    )


def create_neon_cathedral_spec(
    output_dir: str | Path,
    seed: int = 42,
) -> VideoSpec:
    """Create a Neon Cathedral scene spec."""
    artistic_objects = create_neon_cathedral_objects(seed)

    entities = []
    lights = []

    for obj in artistic_objects:
        if obj.material_type == SurfaceType.EMISSION:
            lights.append(
                LightSpec(
                    name=obj.name,
                    position=obj.position,
                    color=obj.emissive or obj.color,
                    intensity=obj.emissive_intensity / 50,  # Scale down
                    radius=min(obj.size) if isinstance(obj.size, tuple) else obj.size,
                ),
            )
        else:
            entities.append(
                PhysicsEntitySpec(
                    name=obj.name,
                    solver=PhysicsSolver.RIGID,
                    shape=obj.shape.value,
                    position=obj.position,
                    size=obj.size,
                    material_preset=None,  # Custom
                    density=obj.density,
                    velocity=obj.initial_velocity,
                    angular_velocity=obj.initial_angular_velocity,
                ),
            )

    # Camera arc
    sequence = Sequence(
        name="Neon Cathedral",
        shots=[
            Cinematographer.create_arc_shot(
                name="Orbit",
                center=(0, 0, 0.8),
                radius=3.0,
                start_angle=0,
                end_angle=180,
                height=1.2,
                duration=10.0,
                fov=50,
            ),
        ],
    )

    return VideoSpec(
        output_dir=output_dir,
        name="neon_cathedral",
        preset=RenderPreset.PROOF,
        duration=10.0,
        entities=entities,
        lights=lights,
        sequence=sequence,
    )


__all__ = [
    "COLONY_PALETTES",
    # Re-exports for convenience
    "MATERIAL_PRESETS",
    "ArtisticObjectFactory",
    "Cinematographer",
    # Generator
    "GenesisVideoGenerator",
    "LightSpec",
    "PhysicsEntitySpec",
    "PhysicsSolver",
    "RenderPreset",
    "Sequence",
    "Shot",
    # Core types
    "VideoSpec",
    # Preset scene generators
    "create_material_showcase_spec",
    "create_neon_cathedral_spec",
    "create_physics_diversity_spec",
]
