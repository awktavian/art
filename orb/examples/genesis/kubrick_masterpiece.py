#!/usr/bin/env python3
"""THE SYMMETRY OF COLLAPSE — A Kubrick-Inspired Genesis Masterpiece.

A 5-act film using:
- One-point perspective corridor (The Shining)
- Domino cascade (chain reaction)
- Dolly zoom at moment of collapse (Vertigo)
- Rack focus between order and chaos
- Arc shot finale

Materials: chrome, marble, obsidian, gold, neon
Cinematography: Full Kubrick toolkit
Audio: Physics-based modal synthesis

USAGE:
    python kubrick_masterpiece.py              # Dailies (10s, 12fps)
    python kubrick_masterpiece.py --proof      # Proof (15s, 24fps)
    python kubrick_masterpiece.py --final      # Full (15s, 24fps, high SPP)

Colony: Spark (e₁) × Forge (e₂) × Crystal (e₇)
"""

from __future__ import annotations

import os

os.environ["MPLBACKEND"] = "Agg"

import argparse
import atexit
import sys
from pathlib import Path

import numpy as np
from PIL import Image

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import Forge cinematography, materials, and audio
from kagami.forge.modules.genesis.cinematography import (
    Cinematographer,
    Sequence,
)
from kagami.forge.modules.genesis import (
    RealtimeAudioEngine,
    CollisionAudioSystem,
)
from kagami.core.multimodal.vision.oidn_denoiser import OIDNDenoiser

# Force unbuffered output
import functools

print = functools.partial(print, flush=True)


def _cleanup_genesis():
    """Safety cleanup for Genesis at exit."""
    try:
        import genesis as gs

        gs.destroy()
    except Exception:
        pass


atexit.register(_cleanup_genesis)


def render_kubrick(preset: str = "dailies") -> Path:
    """Render the Kubrick masterpiece with physics audio."""
    import genesis as gs

    # === PRESETS (with DOF settings for bokeh + OIDN denoising) ===
    # NOTE: Keep emission values LOW (~1-5) - raytracer accumulates light!
    PRESETS = {
        "dailies": {
            "width": 960,
            "height": 540,
            "fps": 12,
            "spp": 16,
            "duration": 10.0,
            "aperture": 4.0,  # f/4.0 - moderate DOF, less noise
            "denoise": True,  # Enable OIDN even for dailies
        },
        "proof": {
            "width": 1280,
            "height": 720,
            "fps": 24,
            "spp": 64,
            "duration": 15.0,
            "aperture": 2.8,  # f/2.8 - balanced bokeh
            "denoise": True,  # OIDN denoising
        },
        "final": {
            "width": 1920,
            "height": 1080,
            "fps": 24,
            "spp": 128,
            "duration": 15.0,
            "aperture": 2.0,  # f/2.0 - cinematic (not extreme)
            "denoise": True,  # OIDN denoising
        },
    }
    cfg = PRESETS.get(preset, PRESETS["dailies"])

    print("\n" + "═" * 70)
    print("   T H E   S Y M M E T R Y   O F   C O L L A P S E")
    print("   ─────────────────────────────────────────────────")
    print("   A Kubrick-Inspired Genesis Film")
    print(f"   {preset.upper()} MODE")
    print("═" * 70)
    denoise_label = "OIDN (mandatory)"  # Always denoise - no fallback path
    print(f"\n  Resolution: {cfg['width']}×{cfg['height']} @ {cfg['fps']}fps")
    print(f"  Quality: {cfg['spp']} SPP | Aperture: f/{cfg['aperture']} | Denoise: {denoise_label}")
    print(f"  Duration: {cfg['duration']}s")

    # Output directories
    output_dir = Path(f"/tmp/kubrick_{preset}")
    output_dir.mkdir(exist_ok=True)
    frames_dir = output_dir / "frames"
    frames_dir.mkdir(exist_ok=True)

    # === AUDIO ENGINE (with automatic collision detection) ===
    print("\n▶ Initializing audio engine with VBAP spatialization...")
    audio_engine = RealtimeAudioEngine(sample_rate=44100, buffer_ms=50)
    collision_audio = CollisionAudioSystem(audio_engine)

    # === INITIALIZE GENESIS ===
    print("▶ Initializing Genesis...")
    gs.init(backend=gs.metal, precision="32", logging_level="warning")

    # Scene with RayTracer for caustics/refraction
    print("▶ Creating scene with RayTracer...")
    scene = gs.Scene(
        show_viewer=False,
        renderer=gs.renderers.RayTracer(
            tracing_depth=12,  # Higher for better caustics/refraction
            rr_depth=4,  # More bounces for glass
            env_radius=100.0,
        ),
        sim_options=gs.options.SimOptions(
            dt=1 / 60,  # Standard timestep (SPH stable with large particles)
            substeps=4,
            gravity=(0, 0, -9.81),
        ),
        vis_options=gs.options.VisOptions(
            ambient_light=(0.15, 0.15, 0.18),  # Good ambient - nothing pitch black
        ),
        # SPH fluid domain for water splash (STABLE - per Genesis recommendation)
        sph_options=gs.options.SPHOptions(
            lower_bound=(-1.5, 0.0, 0.0),
            upper_bound=(1.5, 12.0, 3.0),
            particle_size=0.08,  # Large particles for stability with dt=1/120
        ),
    )

    # === BUILD THE CORRIDOR (THE SHINING) ===
    print("\n" + "─" * 50)
    print("ACT I: THE CORRIDOR OF SYMMETRY")
    print("─" * 50)

    # Floor - polished dark with reflections
    print("  ◆ Floor (polished obsidian)")
    scene.add_entity(
        morph=gs.morphs.Plane(),
        material=gs.materials.Rigid(rho=2500),
        surface=gs.surfaces.Metal(
            color=(0.12, 0.12, 0.14),  # Dark but visible
            roughness=0.08,  # Polished - good reflections
        ),
    )

    # Corridor parameters
    CORRIDOR_LENGTH = 12.0
    CORRIDOR_WIDTH = 2.5
    WALL_HEIGHT = 3.0

    # Corridor walls - medium gray (balanced)
    print("  ◆ Corridor walls (medium gray)")
    for side in [-1, 1]:
        scene.add_entity(
            morph=gs.morphs.Box(
                pos=(side * CORRIDOR_WIDTH / 2, CORRIDOR_LENGTH / 2, WALL_HEIGHT / 2),
                size=(0.1, CORRIDOR_LENGTH, WALL_HEIGHT),
            ),
            material=gs.materials.Rigid(rho=2700),
            surface=gs.surfaces.Default(
                color=(0.5, 0.5, 0.52),  # Medium gray
                roughness=0.4,  # Semi-matte
            ),
        )

    # Back wall (closes the corridor)
    print("  ◆ Back wall")
    scene.add_entity(
        morph=gs.morphs.Box(
            pos=(0.0, CORRIDOR_LENGTH + 0.05, WALL_HEIGHT / 2),
            size=(CORRIDOR_WIDTH, 0.1, WALL_HEIGHT),
        ),
        material=gs.materials.Rigid(rho=2700),
        surface=gs.surfaces.Default(
            color=(0.45, 0.45, 0.48),  # Medium gray
            roughness=0.5,
        ),
    )

    # === THE DOMINOES ===
    print("\n" + "─" * 50)
    print("ACT II: THE DOMINOES (PERFECT ORDER)")
    print("─" * 50)

    DOMINO_ROWS = 20
    DOMINO_SPACING = 0.20  # Closer together for reliable cascade
    DOMINO_SIZE = (0.08, 0.03, 0.18)  # width, depth, height

    print(f"  ◆ Placing {DOMINO_ROWS} crystal dominoes (caustics + bokeh)...")

    # Physically accurate IOR values for beautiful refraction/caustics
    domino_materials = [
        {"color": (0.98, 0.98, 1.0), "ior": 1.55},  # Quartz crystal (1.544-1.553)
        {"color": (1.0, 0.88, 0.92), "ior": 1.54},  # Rose quartz
        {"color": (0.92, 0.96, 1.0), "ior": 1.31},  # Ice (accurate!)
        {"color": (1.0, 0.92, 0.75), "ior": 1.54},  # Amber (1.539-1.545)
    ]

    dominoes = []
    for i in range(DOMINO_ROWS):
        y = 1.0 + i * DOMINO_SPACING
        mat = domino_materials[i % len(domino_materials)]

        domino = scene.add_entity(
            morph=gs.morphs.Box(
                pos=(0.0, y, DOMINO_SIZE[2] / 2),
                size=DOMINO_SIZE,
            ),
            material=gs.materials.Rigid(rho=2500),
            surface=gs.surfaces.Glass(
                color=mat["color"],
                ior=mat["ior"],
            ),
        )
        dominoes.append(domino)
        # Register for automatic collision audio (glass material)
        collision_audio.register_entity(f"domino_{i}", "glass", domino)

    # === HERO ELEMENTS ===
    print("\n" + "─" * 50)
    print("ACT III: THE HERO ELEMENTS")
    print("─" * 50)

    SPHERE_POS = (0.0, CORRIDOR_LENGTH - 1.5, 0.4)

    # Gold sphere - mirror finish for reflections
    print("  ◆ Gold sphere (mirror polish)")
    gold_sphere = scene.add_entity(
        morph=gs.morphs.Sphere(pos=SPHERE_POS, radius=0.35),
        material=gs.materials.Rigid(rho=19300),
        surface=gs.surfaces.Metal(
            color=(1.0, 0.85, 0.35),
            roughness=0.015,  # Mirror polish!
        ),
    )
    collision_audio.register_entity("gold_sphere", "metal", gold_sphere)

    # Diamond orb above - maximum refraction (physically accurate IOR)
    print("  ◆ Diamond orb (IOR 2.417 - accurate)")
    diamond_orb = scene.add_entity(
        morph=gs.morphs.Sphere(
            pos=(0.0, CORRIDOR_LENGTH - 1.5, 1.2),
            radius=0.18,
        ),
        material=gs.materials.Rigid(rho=3520),  # Diamond density
        surface=gs.surfaces.Glass(
            color=(0.98, 0.98, 1.0),
            ior=2.417,  # Diamond: accurate 2.417
        ),
    )
    collision_audio.register_entity("diamond_orb", "glass", diamond_orb)

    # Ruby accent (corundum crystal)
    print("  ◆ Ruby sphere (IOR 1.77 - corundum)")
    ruby_sphere = scene.add_entity(
        morph=gs.morphs.Sphere(
            pos=(0.3, CORRIDOR_LENGTH - 1.8, 0.2),
            radius=0.1,
        ),
        material=gs.materials.Rigid(rho=4000),  # Corundum density
        surface=gs.surfaces.Glass(
            color=(0.92, 0.12, 0.18),
            ior=1.77,  # Ruby (corundum): 1.757-1.779
        ),
    )
    collision_audio.register_entity("ruby_sphere", "glass", ruby_sphere)

    # === WATER SPLASH (SPH with STABLE parameters + Water surface) ===
    # Per Genesis: stable_dt ∝ particle_size² / mu
    # Using large particles (0.08) and low viscosity (0.02) for stability
    print("  ◆ Water splash (SPH fluid with refraction)")
    _water_splash = scene.add_entity(
        morph=gs.morphs.Box(
            pos=(0.0, 4.5, 0.8),  # Above dominoes
            size=(0.4, 0.4, 0.25),
        ),
        material=gs.materials.SPH.Liquid(
            rho=1000.0,  # Water density
            mu=0.02,  # Low viscosity (water-like, stable with large particles)
            gamma=0.01,  # Low surface tension
            sampler="regular",
        ),
        surface=gs.surfaces.Water(
            color=(0.5, 0.8, 0.95),  # Light blue water
            ior=1.333,  # Water refraction
            roughness=0.03,  # Smooth water surface
            vis_mode="recon",  # Surface reconstruction for proper water
            recon_backend="splashsurf",
            smooth=True,
        ),
    )

    # === LIGHTING (Distributed + Three-Point) ===
    print("\n" + "─" * 50)
    print("LIGHTING: Corridor + Three-Point")
    print("─" * 50)

    # CEILING LIGHTS along corridor (balanced - not blown out)
    print("  ◆ Ceiling lights (every 2m)")
    for y_pos in [1.0, 3.0, 5.0, 7.0, 9.0, 11.0]:
        scene.add_entity(
            morph=gs.morphs.Sphere(pos=(0.0, y_pos, WALL_HEIGHT - 0.3), radius=0.12),
            material=gs.materials.Rigid(rho=100),
            surface=gs.surfaces.Emission(emissive=(2.5, 2.5, 2.8)),  # Subtle ceiling
        )

    # Key light (warm) near hero elements
    print("  ◆ Key light (warm)")
    scene.add_entity(
        morph=gs.morphs.Sphere(pos=(0.5, CORRIDOR_LENGTH - 3.0, 2.5), radius=0.25),
        material=gs.materials.Rigid(rho=100),
        surface=gs.surfaces.Emission(emissive=(4.0, 3.5, 2.5)),  # Warm, not blown
    )

    # Fill light (cool)
    print("  ◆ Fill light (cool)")
    scene.add_entity(
        morph=gs.morphs.Sphere(pos=(-0.8, CORRIDOR_LENGTH - 2.0, 2.0), radius=0.2),
        material=gs.materials.Rigid(rho=100),
        surface=gs.surfaces.Emission(emissive=(1.5, 2.0, 3.0)),  # Subtle cool fill
    )

    # Back light (rim)
    print("  ◆ Back light (rim)")
    scene.add_entity(
        morph=gs.morphs.Sphere(pos=(0.0, CORRIDOR_LENGTH - 0.5, 1.8), radius=0.15),
        material=gs.materials.Rigid(rho=100),
        surface=gs.surfaces.Emission(emissive=(2.5, 2.5, 2.8)),  # Subtle rim
    )

    # === NEON LIGHTS (creates colored bokeh circles) ===
    print("  ◆ Neon bars (bokeh generators)")

    # Neon colors - subtle (not blown out)
    neon_colors = [
        (2.0, 0.3, 2.5),  # Violet
        (0.3, 2.2, 2.8),  # Cyan
        (2.8, 0.8, 1.5),  # Pink
        (0.3, 2.5, 1.0),  # Green
    ]

    # Overhead neons
    for i, y in enumerate([2.0, 4.5, 7.0, 9.5]):
        color = neon_colors[i % len(neon_colors)]
        scene.add_entity(
            morph=gs.morphs.Box(
                pos=(0.0, y, WALL_HEIGHT - 0.15),
                size=(CORRIDOR_WIDTH - 0.4, 0.08, 0.05),
            ),
            material=gs.materials.Rigid(rho=100),
            surface=gs.surfaces.Emission(emissive=color),
        )

    # Side neon strips
    print("  ◆ Side neon strips")
    for side in [-1, 1]:
        x = side * (CORRIDOR_WIDTH / 2 - 0.1)
        for i, y in enumerate([1.5, 4.0, 6.5, 9.0, 11.0]):
            # Left = cool, Right = warm
            color = neon_colors[(i + (1 if side > 0 else 0)) % len(neon_colors)]
            scene.add_entity(
                morph=gs.morphs.Box(
                    pos=(x, y, 1.5),
                    size=(0.04, 0.04, 2.5),
                ),
                material=gs.materials.Rigid(rho=100),
                surface=gs.surfaces.Emission(emissive=color),
            )

    # === CAMERA (thinlens for bokeh) ===
    # Note: Genesis built-in denoise=True doesn't work on Metal
    # We use external OIDN denoiser in post-processing instead
    print(f"  ◆ Camera (thinlens f/{cfg['aperture']})")
    camera = scene.add_camera(
        model="thinlens",
        res=(cfg["width"], cfg["height"]),
        pos=(0.0, -2.0, 1.2),
        lookat=(0.0, 8.0, 1.0),
        fov=35.0,
        aperture=cfg["aperture"],  # Low f-stop = shallow DOF = more bokeh!
        focus_dist=6.0,
        spp=cfg["spp"],
    )

    # === BUILD SCENE ===
    print("\n▶ Building physics simulation...")
    scene.build()

    # === TRIGGER DOMINO CASCADE ===
    # Push the first domino to start the chain reaction
    print("  ◆ Pushing first domino...")
    if dominoes:
        dominoes[0].set_dofs_velocity([0.0, 0.8, 0.0, 2.0, 0.0, 0.0])  # Push forward + rotate

    # === OIDN DENOISER (MANDATORY - always denoise, no fallback) ===
    print("▶ Initializing OIDN denoiser...")
    denoiser = None
    # Try Metal first (GPU accelerated), then CPU
    for device in ["metal", "cpu"]:
        try:
            denoiser = OIDNDenoiser(device=device, quality="high")
            print(f"  ✓ OIDN ready ({device.upper()})")
            break
        except Exception as e:
            if device == "cpu":
                raise RuntimeError(f"OIDN denoiser required but unavailable: {e}") from e
            continue  # Try CPU next

    # === CINEMATOGRAPHY ===
    print("\n" + "─" * 50)
    print("CINEMATOGRAPHY: 5 ACTS")
    print("─" * 50)

    DURATION = cfg["duration"]
    FPS = cfg["fps"]
    TOTAL_FRAMES = int(FPS * DURATION)

    # Create shot sequence with per-shot aperture/focus for bokeh control
    sequence = Sequence(
        name="The Symmetry of Collapse",
        shots=[
            # ACT 1: One-point perspective (deep DOF for architecture)
            Cinematographer.create_one_point_perspective_shot(
                name="ACT 1: The Corridor",
                corridor_start=(0.0, -2.0, 1.2),
                corridor_end=(0.0, CORRIDOR_LENGTH, 1.2),
                duration=DURATION * 0.25,
                fov=32.0,
                steps=30,
            ),
            # ACT 2: Rack focus (shallow DOF, dramatic bokeh)
            Cinematographer.create_rack_focus_shot(
                name="ACT 2: Rack Focus",
                camera_pos=(0.0, 0.5, 0.8),
                lookat=(0.0, 5.0, 0.5),
                focus_near=1.0,
                focus_far=9.0,
                duration=DURATION * 0.15,
                fov=45.0,
                aperture=1.4,  # Maximum bokeh during rack
            ),
            # ACT 3: Dolly zoom (vertigo)
            Cinematographer.create_dolly_zoom_shot(
                name="ACT 3: Dolly Zoom (Vertigo)",
                subject_pos=(0.0, 4.0, 0.5),
                start_distance=4.0,
                end_distance=1.5,
                start_fov=30.0,
                end_fov=70.0,
                duration=DURATION * 0.25,
                height=1.0,
                steps=30,
            ),
            # ACT 4: Steadicam (medium DOF)
            Cinematographer.create_steadicam_follow_shot(
                name="ACT 4: Steadicam",
                path_points=[
                    (0.8, 2.0, 0.7),
                    (0.6, 4.0, 0.9),
                    (0.3, 6.0, 1.0),
                    (-0.2, 8.0, 0.8),
                ],
                lookat=(0.0, 5.0, 0.4),
                duration=DURATION * 0.2,
                fov=50.0,
                aperture=2.8,
            ),
            # ACT 5: Arc around dominoes (staying inside corridor, looking forward)
            Cinematographer.create_arc_shot(
                name="ACT 5: Arc Finale",
                center=(0.0, 4.0, 0.5),  # Center on dominoes, not back of corridor
                radius=1.2,  # Smaller radius to stay inside walls
                start_angle=250,  # Start from front-left
                end_angle=290,  # End at front-right (only 40° sweep)
                height=0.8,
                duration=DURATION * 0.15,
                fov=50.0,
                steps=24,
            ),
        ],
    )

    print(f"  Total: {sequence.total_duration:.1f}s across {len(sequence.shots)} shots")
    for shot in sequence.shots:
        print(f"    • {shot.name} ({shot.duration:.1f}s)")

    # === RENDER LOOP ===
    print("\n" + "═" * 50)
    print(f"  RENDERING: {TOTAL_FRAMES} frames")
    print("═" * 50 + "\n")

    frames_rendered = 0
    try:
        for frame_idx in range(TOTAL_FRAMES):
            t = frame_idx / FPS

            # Get camera state
            cam_state = sequence.get_camera_at(t)

            # Update camera pose
            camera.set_pose(
                pos=cam_state.position,
                lookat=cam_state.lookat,
            )

            # Step physics with automatic collision audio detection
            # Uses camera position as microphone for VBAP spatialization
            scene.step()

            # Process collision audio - detects velocity changes (impulses)
            # and generates spatialized audio using camera as listener
            _ = collision_audio.update(t, cam_state.position)

            # Render
            result = camera.render()
            rgb = result[0] if isinstance(result, tuple) else result
            if hasattr(rgb, "numpy"):
                rgb = rgb.numpy()

            # Save frame
            if rgb is not None and len(rgb.shape) == 3:
                # Convert to float32 for denoising (HDR pipeline)
                if rgb.dtype == np.uint8:
                    rgb_float = rgb.astype(np.float32) / 255.0
                elif rgb.max() <= 1.0:
                    rgb_float = rgb.astype(np.float32)
                else:
                    rgb_float = rgb.astype(np.float32) / 255.0

                # Apply OIDN denoising (MANDATORY - always denoise)
                rgb_float = np.clip(rgb_float, 0.0, 1.0).astype(np.float32)
                rgb_float = denoiser.denoise(rgb_float)  # type: ignore[union-attr]

                # Convert to uint8 for saving
                rgb = (rgb_float * 255).clip(0, 255).astype(np.uint8)

                frame_path = frames_dir / f"frame_{frame_idx:04d}.png"
                Image.fromarray(rgb).save(frame_path)
                frames_rendered += 1

            # Progress
            if frame_idx % 10 == 0 or frame_idx == TOTAL_FRAMES - 1:
                shot, _ = sequence.get_shot_at(t)
                pct = (frame_idx + 1) / TOTAL_FRAMES * 100
                print(f"  [{frame_idx + 1:4d}/{TOTAL_FRAMES}] {pct:5.1f}%  {shot.name}")

    except Exception as e:
        print(f"\n⚠ Render interrupted at frame {frames_rendered}: {e}")

    # Cleanup
    gs.destroy()

    # === SAVE AUDIO (automatic collision audio) ===
    print("\n▶ Saving spatialized collision audio...")
    print("  Camera position was used as microphone throughout render")
    audio_buffer = collision_audio.get_audio()
    if audio_buffer is not None and len(audio_buffer) > 0:
        audio_path = output_dir / "audio.wav"
        audio_engine.save_audio(audio_buffer, audio_path)
        duration_sec = len(audio_buffer) / 44100
        print(f"  ✓ Audio: {audio_path}")
        print(f"  Duration: {duration_sec:.1f}s | VBAP spatialized | Room acoustics applied")
    else:
        print("  ⚠ No collisions detected - check physics simulation")

    # === ASSEMBLE VIDEO (E2E) ===
    print("\n▶ Assembling video (mp4)...")
    mp4_path = output_dir / "film.mp4"
    try:
        import shutil
        import subprocess

        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            print("  ⚠ ffmpeg not found; leaving frames + audio as-is")
        else:
            # Quality knobs: keep minimal + robust
            crf = {"dailies": "23", "proof": "20", "final": "18"}.get(preset, "20")
            preset_flag = {"dailies": "veryfast", "proof": "medium", "final": "slow"}.get(
                preset, "medium"
            )

            cmd = [
                ffmpeg,
                "-y",
                "-framerate",
                str(FPS),
                "-i",
                str(frames_dir / "frame_%04d.png"),
            ]

            audio_path = output_dir / "audio.wav"
            have_audio = audio_path.exists()
            if have_audio:
                cmd += ["-i", str(audio_path)]

            cmd += [
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-crf",
                crf,
                "-preset",
                preset_flag,
            ]

            if have_audio:
                cmd += ["-c:a", "aac", "-b:a", "192k", "-shortest"]

            cmd += [str(mp4_path)]

            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
            print(f"  ✓ Video: {mp4_path}")
    except Exception as e:
        print(f"  ⚠ Video assembly failed: {e}")

    print("\n" + "═" * 50)
    print("  ✓ RENDER COMPLETE")
    print(f"  Frames: {frames_dir}")
    print(f"  Rendered: {frames_rendered}/{TOTAL_FRAMES}")
    print("═" * 50 + "\n")

    return output_dir


def main():
    parser = argparse.ArgumentParser(description="Kubrick Masterpiece Renderer")
    parser.add_argument("--dailies", action="store_true", help="Quick dailies (default)")
    parser.add_argument("--proof", action="store_true", help="Medium quality proof")
    parser.add_argument("--final", action="store_true", help="Full production quality")

    args = parser.parse_args()

    if args.final:
        preset = "final"
    elif args.proof:
        preset = "proof"
    else:
        preset = "dailies"

    render_kubrick(preset)


if __name__ == "__main__":
    main()
