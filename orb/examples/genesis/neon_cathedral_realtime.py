#!/usr/bin/env python3
"""Neon Cathedral — Real-time via HAL with True Foveated Rendering.

Features:
- True foveated rendering (RayTracer foveal + Rasterizer peripheral)
- Motion-aware ATW with object momentum prediction
- Physics-based audio synthesis
- Artistic object generation with colony palettes
- E2E differentiable pipeline support

Colony: Forge (e₂) - Construction
"""

import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="%(message)s")

from kagami.forge.modules.genesis import (
    RealtimeConfig,
    FoveationConfig,
    RealtimeGenesisRenderer,
    FoveatedMultiCameraRenderer,
)
from kagami.forge.modules.genesis.artistic_objects import (
    ArtisticObjectFactory,
    ShapeType,
)


async def create_artistic_scene(renderer: RealtimeGenesisRenderer) -> None:
    """Create the Neon Cathedral scene with artistic objects."""

    # Create artistic object factory with seed for reproducibility
    factory = ArtisticObjectFactory(seed=42)

    # === FLOOR ===
    renderer.add_floor()

    # === CENTRAL ALTAR (Monument - Chrome with gold accents) ===
    renderer.add_rigid_body(
        "altar",
        shape="box",
        position=(0, 0, 0.5),
        size=(0.8, 0.8, 1.0),
        material="chrome",
        color=(0.9, 0.9, 0.95),
    )

    # === GLASS ORB on altar (Crystal clear with high IOR) ===
    renderer.add_rigid_body(
        "orb",
        shape="sphere",
        position=(0, 0, 1.3),
        size=0.25,
        material="crystal_clear",
        color=(0.97, 0.97, 1.0),
    )

    # === NEON LIGHT BARS (Colony-inspired palettes) ===
    # Using expanded material presets
    neon_configs = [
        ("neon_pink", (-2, 0, 1.5), (1.0, 0.2, 0.6)),  # Magenta left (Nexus)
        ("neon_cyan", (2, 0, 1.5), (0.2, 1.0, 1.0)),  # Cyan right (Flow)
        ("neon_purple", (0, -2, 1.5), (0.6, 0.2, 1.0)),  # Purple back (Spark)
        ("neon_orange", (0, 2, 1.5), (1.0, 0.5, 0.1)),  # Orange front (Beacon)
    ]

    for i, (_material, pos, color) in enumerate(neon_configs):
        renderer.add_emissive(
            f"neon_{i}",
            position=pos,
            size=(0.05, 0.05, 2.0),
            color=color,
            intensity=300.0,
        )

    # === ARTISTIC FLYING OBJECTS (Generated with factory) ===
    # Generate a set of artistic objects with Forge palette
    flying_objects = factory.generate_scene_objects(
        count=6,
        theme="forge",
        physics_style="dynamic",
        spawn_area=(-1.5, 1.5, -1.5, 1.5, 1.5, 2.5),
    )

    for obj in flying_objects:
        # Map shape to renderer format
        shape_map = {
            ShapeType.SPHERE: "sphere",
            ShapeType.BOX: "box",
            ShapeType.CYLINDER: "cylinder",
        }
        shape = shape_map.get(obj.shape, "sphere")

        # Get size (use first dimension for sphere)
        size = obj.size[0] if shape == "sphere" else obj.size

        # Combine linear and angular velocity
        velocity = (*obj.initial_velocity, *obj.initial_angular_velocity)

        renderer.add_rigid_body(
            obj.name,
            shape=shape,
            position=obj.position,
            size=size,
            material="chrome",  # Use chrome for metallic objects
            color=obj.color,
            velocity=velocity,
        )

    # === GOLD ACCENT SPHERES (Beacon palette) ===
    gold_objects = factory.generate_scene_objects(
        count=3,
        theme="beacon",
        physics_style="dynamic",
        spawn_area=(-0.8, 0.8, -0.8, 0.8, 1.5, 2.2),
    )

    for i, obj in enumerate(gold_objects):
        velocity = (*obj.initial_velocity, *obj.initial_angular_velocity)
        renderer.add_rigid_body(
            f"gold_{i}",
            shape="sphere",
            position=obj.position,
            size=0.1,
            material="gold",
            velocity=velocity,
        )

    # === CRYSTAL OBJECTS (Crystal palette - glass-like) ===
    crystal_objects = factory.generate_scene_objects(
        count=2,
        theme="crystal",
        physics_style="dynamic",
        spawn_area=(-1.0, 1.0, -1.0, 1.0, 2.0, 2.8),
    )

    for i, obj in enumerate(crystal_objects):
        velocity = (*obj.initial_velocity, *obj.initial_angular_velocity)
        renderer.add_rigid_body(
            f"crystal_{i}",
            shape="sphere",
            position=obj.position,
            size=0.12,
            material="sapphire",  # Use sapphire for crystal effect
            color=(0.6, 0.7, 0.95),
            velocity=velocity,
        )

    # === AMBIENT LIGHT BARS (Additional lighting) ===
    light_array = factory.generate_light_array(
        count=4,
        theme="nexus",
        arrangement="circle",
        center=(0.0, 0.0, 0.5),
        radius=3.5,
    )

    for light in light_array:
        renderer.add_emissive(
            light.name,
            position=light.position,
            size=light.size,
            color=light.color,
            intensity=light.emissive_intensity,
        )


async def main():
    """Main entry point for Neon Cathedral with real foveation."""

    # Configure real-time renderer with foveation
    foveation_config = FoveationConfig(
        gaze_x=0.5,
        gaze_y=0.5,
        foveal_spp=256,  # High quality center (RayTracer)
        mid_spp=64,  # Not used in dual-camera mode
        outer_spp=8,  # Not used in dual-camera mode
        foveal_radius=0.15,
    )

    config = RealtimeConfig(
        width=1280,
        height=720,
        render_fps=24,  # Lower for higher quality per frame
        display_fps=60,
        base_spp=128,  # Base quality for uniform rendering
        tracing_depth=12,  # More bounces for better GI
        physics_substeps=4,
        # Thin lens camera - REAL depth of field and bokeh
        camera_model="thinlens",  # Real DOF (vs "pinhole" for sharp)
        camera_fov=50.0,  # Field of view
        camera_aperture=1.8,  # f/1.8 - cinematic shallow DOF with beautiful bokeh
        camera_focus_dist=3.5,  # Focus on altar (3.5m from camera)
        # Foveation
        enable_foveation=True,  # Enable foveation (cursor tracking)
        foveation=foveation_config,
        enable_motion_reprojection=True,  # Motion-aware ATW
    )

    renderer = RealtimeGenesisRenderer(config)
    await renderer.initialize()

    # === CREATE ARTISTIC SCENE ===
    await create_artistic_scene(renderer)

    # Build the scene
    renderer.build()

    # === SETUP FOVEATED MULTI-CAMERA (Optional - True foveation) ===
    # This creates separate foveal and peripheral cameras for true quality difference
    # Note: Requires Genesis to support multiple cameras/renderers
    foveated_renderer = FoveatedMultiCameraRenderer(
        width=config.width,
        height=config.height,
        config=foveation_config,
        foveal_res=(512, 512),
    )

    # Try to initialize dual-camera foveation (may not work on all setups)
    try:
        foveated_renderer.initialize(renderer._scene)
        print("  True foveated rendering: ENABLED (RayTracer foveal + Rasterizer peripheral)")
    except Exception as e:
        logging.debug(f"Dual-camera foveation not available: {e}")
        print("  True foveated rendering: DISABLED (falling back to uniform)")

    print("\n" + "=" * 60)
    print("  NEON CATHEDRAL — Real-time RayTracer v2")
    print("  True Foveated Rendering + Motion-Aware ATW + Physics Audio")
    print("  Artistic Objects with Colony Palettes")
    print("=" * 60)
    print("\n  Controls:")
    print("    F - Toggle FPS overlay")
    print("    Mouse - Gaze tracking (foveal center follows cursor)")
    print("    Ctrl+C - Stop")
    print()
    print("  Materials used:")
    print("    - chrome, gold, sapphire, crystal_clear")
    print("    - neon_pink, neon_cyan, neon_purple, neon_orange")
    print()

    try:
        await renderer.run_realtime(duration=120.0)  # 2 minute demo
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        await renderer.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
