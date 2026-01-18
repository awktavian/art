"""Creator-facing Forge API helpers.

This module is intentionally **Genesis-import-free at import time**.
It provides:
- dict[str, Any] → strongly-typed Genesis `VideoSpec` parsing (with fail-fast validation)
- async wrappers to run Genesis generation without blocking the event loop

Physical accuracy note:
We only expose controls that Genesis can simulate *physically* in its model
(raytraced refraction/caustics, roughness, IOR, simple glass subsurface,
particle surface reconstruction + foam, solver options).
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from pathlib import Path
from typing import Any

from kagami_genesis.optics import (
    GenesisSurfaceSpec,
    RayTracerLight,
    RayTracerOptions,
    ReconBackend,
    SurfaceKind,
)
from kagami_genesis.solver_options import (
    FEMOptionsSpec,
    MPMOptionsSpec,
    PBDOptionsSpec,
    SPHOptionsSpec,
)
from kagami_genesis.video_generation import (
    GenesisVideoGenerator,
    LightSpec,
    PhysicsEntitySpec,
    PhysicsSolver,
    RenderPreset,
    VideoSpec,
    create_material_showcase_spec,
    create_neon_cathedral_spec,
    create_physics_diversity_spec,
)

from kagami.forge.exceptions import ModuleNotAvailableError, ValidationError

_VIDEO_TEMPLATES: dict[str, Any] = {
    "material_showcase": create_material_showcase_spec,
    "physics_diversity": create_physics_diversity_spec,
    "neon_cathedral": create_neon_cathedral_spec,
}


def _err(msg: str, *, context: dict[str, Any] | None = None) -> ValidationError:
    return ValidationError(msg, context=context or {})


def _as_tuple3(value: Any, name: str) -> tuple[float, float, float]:
    if isinstance(value, (tuple, list)) and len(value) == 3:
        return (float(value[0]), float(value[1]), float(value[2]))
    raise _err(
        f"{name} must be a 3-tuple[Any, ...]/list[Any]", context={"field": name, "value": value}
    )


def _as_tuple_float(value: Any, name: str) -> tuple[float, ...]:
    if isinstance(value, (tuple, list)):
        return tuple(float(x) for x in value)
    raise _err(
        f"{name} must be a tuple[Any, ...]/list[Any]", context={"field": name, "value": value}
    )


def _parse_enum(enum_cls: Any, value: Any, name: str) -> Any:
    if isinstance(value, enum_cls):
        return value
    if isinstance(value, str):
        try:
            return enum_cls(value)
        except Exception:
            # Also support case-insensitive by value.name
            lowered = value.strip().lower()
            for item in enum_cls:  # pragma: no branch
                if str(item.value).lower() == lowered or str(item.name).lower() == lowered:
                    return item
    raise _err(f"Invalid {name}: {value}", context={"field": name, "value": value})


def _parse_surface_spec(payload: Any) -> GenesisSurfaceSpec:
    if payload is None:
        return GenesisSurfaceSpec()
    if isinstance(payload, GenesisSurfaceSpec):
        return GenesisSurfaceSpec(**payload.__dict__)
    if not isinstance(payload, dict):
        raise _err("surface must be an object", context={"field": "surface", "value": payload})

    allowed = {
        "kind",
        "color",
        "opacity",
        "roughness",
        "metallic",
        "emissive",
        "ior",
        "subsurface",
        "thickness",
        "smooth",
        "double_sided",
        "cutoff",
        "normal_diff_clamp",
        "recon_backend",
        "generate_foam",
        "foam_options",
    }
    extra = set(payload) - allowed
    if extra:
        raise _err(
            "Unsupported surface fields",
            context={"unknown_fields": sorted(extra), "allowed_fields": sorted(allowed)},
        )

    kind = payload.get("kind")
    recon = payload.get("recon_backend")
    return GenesisSurfaceSpec(
        kind=None if kind is None else _parse_enum(SurfaceKind, kind, "surface.kind"),
        color=payload.get("color"),
        opacity=payload.get("opacity"),
        roughness=payload.get("roughness"),
        metallic=payload.get("metallic"),
        emissive=payload.get("emissive"),
        ior=payload.get("ior"),
        subsurface=payload.get("subsurface"),
        thickness=payload.get("thickness"),
        smooth=payload.get("smooth"),
        double_sided=payload.get("double_sided"),
        cutoff=payload.get("cutoff"),
        normal_diff_clamp=payload.get("normal_diff_clamp"),
        recon_backend=None
        if recon is None
        else _parse_enum(ReconBackend, recon, "surface.recon_backend"),
        generate_foam=payload.get("generate_foam"),
        foam_options=payload.get("foam_options"),
    )


def _parse_raytracer_light(payload: Any) -> RayTracerLight:
    if isinstance(payload, RayTracerLight):
        return payload
    if not isinstance(payload, dict):
        raise _err("raytracer.light must be an object", context={"value": payload})
    allowed = {"pos", "color", "intensity", "radius"}
    extra = set(payload) - allowed
    if extra:
        raise _err(
            "Unsupported raytracer light fields",
            context={"unknown_fields": sorted(extra), "allowed_fields": sorted(allowed)},
        )
    return RayTracerLight(
        pos=_as_tuple3(payload.get("pos"), "raytracer.light.pos"),
        color=_as_tuple3(payload.get("color", (1.0, 1.0, 1.0)), "raytracer.light.color"),
        intensity=float(payload.get("intensity", 1.0)),
        radius=float(payload.get("radius", 0.1)),
    )


def _parse_raytracer_options(payload: Any) -> RayTracerOptions:
    if payload is None:
        return RayTracerOptions()
    if isinstance(payload, RayTracerOptions):
        return RayTracerOptions(**payload.__dict__)
    if not isinstance(payload, dict):
        raise _err("raytracer must be an object", context={"field": "raytracer", "value": payload})

    allowed = {
        "logging_level",
        "state_limit",
        "tracing_depth",
        "rr_depth",
        "rr_threshold",
        "env_surface",
        "env_radius",
        "env_pos",
        "env_euler",
        "env_quat",
        "lights",
        "light",  # Genesis docs use `light` (singular) for list[Any]-of-lights
        "normal_diff_clamp",
    }
    extra = set(payload) - allowed
    if extra:
        raise _err(
            "Unsupported raytracer fields",
            context={"unknown_fields": sorted(extra), "allowed_fields": sorted(allowed)},
        )

    # Genesis docs use `light` (singular) for the list[Any]; accept both.
    lights_payload = payload.get("lights", payload.get("light", []))
    lights = []
    if lights_payload:
        if not isinstance(lights_payload, list):
            raise _err("raytracer.lights must be a list[Any]", context={"value": lights_payload})
        lights = [_parse_raytracer_light(x) for x in lights_payload]

    env_surface = payload.get("env_surface")
    return RayTracerOptions(
        logging_level=str(payload.get("logging_level", "warning")),
        state_limit=payload.get("state_limit"),
        tracing_depth=payload.get("tracing_depth"),
        rr_depth=payload.get("rr_depth"),
        rr_threshold=payload.get("rr_threshold"),
        env_surface=None if env_surface is None else _parse_surface_spec(env_surface),
        env_radius=payload.get("env_radius"),
        env_pos=payload.get("env_pos"),
        env_euler=payload.get("env_euler"),
        env_quat=payload.get("env_quat"),
        lights=lights,
        normal_diff_clamp=payload.get("normal_diff_clamp"),
    )


def _parse_solver_options(payload: Any, cls: Any, name: str) -> Any:
    if payload is None:
        return None
    if isinstance(payload, cls):
        return cls(**payload.__dict__)
    if not isinstance(payload, dict):
        raise _err(f"{name} must be an object", context={"field": name, "value": payload})
    return cls(**payload)


def _parse_entity(payload: Any) -> PhysicsEntitySpec:
    if isinstance(payload, PhysicsEntitySpec):
        return PhysicsEntitySpec(**payload.__dict__)
    if not isinstance(payload, dict):
        raise _err("entities[] must be an object", context={"value": payload})

    allowed = {
        "name",
        "solver",
        "shape",
        "position",
        "size",
        "material_preset",
        "surface",
        "density",
        "velocity",
        "angular_velocity",
        "fixed",
        "elastic_modulus",
        "poisson_ratio",
        "viscosity",
        "surface_tension",
        "friction_angle",
    }
    extra = set(payload) - allowed
    if extra:
        raise _err(
            "Unsupported entity fields",
            context={"unknown_fields": sorted(extra), "allowed_fields": sorted(allowed)},
        )

    solver = _parse_enum(PhysicsSolver, payload.get("solver"), "entities[].solver")
    surface = payload.get("surface")
    size_raw = payload.get("size")
    if isinstance(size_raw, (list, tuple)):
        size = _as_tuple_float(size_raw, "entities[].size")
    elif isinstance(size_raw, (int, float)):
        size = float(size_raw)  # type: ignore[assignment]
    else:
        size = (1.0, 1.0, 1.0)  # Default size for unknown type
    return PhysicsEntitySpec(
        name=str(payload.get("name", "")),
        solver=solver,
        shape=str(payload.get("shape", "box")),
        position=_as_tuple3(payload.get("position"), "entities[].position"),
        size=size,
        material_preset=payload.get("material_preset"),
        surface=None if surface is None else _parse_surface_spec(surface),
        density=float(payload.get("density", 2500.0)),
        velocity=_as_tuple3(payload.get("velocity", (0.0, 0.0, 0.0)), "entities[].velocity"),
        angular_velocity=_as_tuple3(
            payload.get("angular_velocity", (0.0, 0.0, 0.0)), "entities[].angular_velocity"
        ),
        fixed=bool(payload.get("fixed", False)),
        elastic_modulus=float(payload.get("elastic_modulus", 1e5)),
        poisson_ratio=float(payload.get("poisson_ratio", 0.3)),
        viscosity=float(payload.get("viscosity", 0.001)),
        surface_tension=float(payload.get("surface_tension", 0.01)),
        friction_angle=float(payload.get("friction_angle", 35.0)),
    )


def _parse_light(payload: Any) -> LightSpec:
    if isinstance(payload, LightSpec):
        return LightSpec(**payload.__dict__)
    if not isinstance(payload, dict):
        raise _err("lights[] must be an object", context={"value": payload})
    allowed = {"name", "position", "color", "intensity", "radius", "type"}
    extra = set(payload) - allowed
    if extra:
        raise _err(
            "Unsupported light fields",
            context={"unknown_fields": sorted(extra), "allowed_fields": sorted(allowed)},
        )
    return LightSpec(
        name=str(payload.get("name", "light")),
        position=_as_tuple3(payload.get("position"), "lights[].position"),
        color=_as_tuple3(payload.get("color", (1.0, 1.0, 1.0)), "lights[].color"),
        intensity=float(payload.get("intensity", 5.0)),
        radius=float(payload.get("radius", 0.1)),
        type=str(payload.get("type", "point")),
    )


def parse_genesis_video_spec(payload: dict[str, Any]) -> VideoSpec:
    """Parse a dict[str, Any] payload into a `VideoSpec`.

    Supports:
    - template mode: {template: "...", output_dir: "...", ...overrides}
    - explicit mode: {output_dir: "...", entities: [...], ...}
    """
    if not isinstance(payload, dict):
        raise _err("payload must be an object", context={"value": payload})

    allowed_top = {
        # Wrapper key (service layer accepts it; this parser ignores it unless caller passes only `spec`)
        "spec",
        "template",
        "template_args",
        "output_dir",
        "name",
        "preset",
        "width",
        "height",
        "fps",
        "duration",
        "spp",
        "camera_pos",
        "camera_lookat",
        "camera_fov",
        "camera_aperture",
        "camera_focus",
        "ambient_light",
        "gravity",
        "dt",
        "substeps",
        "sph_bounds",
        "sph_particle_size",
        "raytracer",
        "entities",
        "lights",
        "sph_options",
        "mpm_options",
        "fem_options",
        "pbd_options",
        # Allowed but ignored by this parser (ForgeRequest.metadata carries tracing info separately)
        "metadata",
    }
    extra_top = set(payload) - allowed_top
    if extra_top:
        raise _err(
            "Unsupported genesis.video fields",
            context={"unknown_fields": sorted(extra_top), "allowed_fields": sorted(allowed_top)},
        )

    # Convenience: accept {"spec": {...}} wrapper (merge-free: wrapper-only).
    if set(payload.keys()) == {"spec"} and isinstance(payload.get("spec"), dict):
        payload = payload["spec"]

    template = payload.get("template")
    output_dir = payload.get("output_dir")
    if not output_dir:
        raise _err("output_dir is required", context={"field": "output_dir"})

    # Template path: build a base spec and apply overrides.
    if isinstance(template, str) and template.strip():
        fn = _VIDEO_TEMPLATES.get(template.strip())
        if fn is None:
            raise _err(
                f"Unknown template: {template}",
                context={"template": template, "available": sorted(_VIDEO_TEMPLATES)},
            )
        # Allow template-specific args
        template_args = payload.get("template_args") or {}
        if template_args and not isinstance(template_args, dict):
            raise _err("template_args must be an object", context={"value": template_args})
        base: VideoSpec = fn(output_dir=output_dir, **template_args)

        spec = VideoSpec(**base.__dict__)
    else:
        spec = VideoSpec(output_dir=output_dir)

    # Apply common overrides (explicit fields win)
    if "name" in payload:
        spec.name = str(payload["name"])
    if "preset" in payload:
        spec.preset = _parse_enum(RenderPreset, payload["preset"], "preset")
    if "width" in payload:
        spec.width = None if payload["width"] is None else int(payload["width"])
    if "height" in payload:
        spec.height = None if payload["height"] is None else int(payload["height"])
    if "fps" in payload:
        spec.fps = int(payload["fps"])
    if "duration" in payload:
        spec.duration = float(payload["duration"])
    if "spp" in payload:
        spec.spp = None if payload["spp"] is None else int(payload["spp"])

    if "camera_pos" in payload:
        spec.camera_pos = _as_tuple3(payload["camera_pos"], "camera_pos")
    if "camera_lookat" in payload:
        spec.camera_lookat = _as_tuple3(payload["camera_lookat"], "camera_lookat")
    if "camera_fov" in payload:
        spec.camera_fov = float(payload["camera_fov"])
    if "camera_aperture" in payload:
        spec.camera_aperture = float(payload["camera_aperture"])
    if "camera_focus" in payload:
        spec.camera_focus = float(payload["camera_focus"])

    if "ambient_light" in payload:
        spec.ambient_light = _as_tuple3(payload["ambient_light"], "ambient_light")

    if "gravity" in payload:
        spec.gravity = _as_tuple3(payload["gravity"], "gravity")
    if "dt" in payload:
        spec.dt = float(payload["dt"])
    if "substeps" in payload:
        spec.substeps = int(payload["substeps"])

    if "sph_bounds" in payload and payload["sph_bounds"] is not None:
        bounds = payload["sph_bounds"]
        if not (isinstance(bounds, (list, tuple)) and len(bounds) == 2):
            raise _err("sph_bounds must be [lower, upper]", context={"value": bounds})
        spec.sph_bounds = (
            _as_tuple3(bounds[0], "sph_bounds[0]"),
            _as_tuple3(bounds[1], "sph_bounds[1]"),
        )
    if "sph_particle_size" in payload:
        spec.sph_particle_size = float(payload["sph_particle_size"])

    if "raytracer" in payload:
        spec.raytracer = _parse_raytracer_options(payload["raytracer"])

    # Entities / lights replacement
    if "entities" in payload and payload["entities"] is not None:
        if not isinstance(payload["entities"], list):
            raise _err("entities must be a list[Any]", context={"value": payload["entities"]})
        spec.entities = [_parse_entity(e) for e in payload["entities"]]
    if "lights" in payload and payload["lights"] is not None:
        if not isinstance(payload["lights"], list):
            raise _err("lights must be a list[Any]", context={"value": payload["lights"]})
        spec.lights = [_parse_light(l) for l in payload["lights"]]

    # Solver option blocks
    if "sph_options" in payload:
        spec.sph_options = _parse_solver_options(
            payload["sph_options"], SPHOptionsSpec, "sph_options"
        )
    if "mpm_options" in payload:
        spec.mpm_options = _parse_solver_options(
            payload["mpm_options"], MPMOptionsSpec, "mpm_options"
        )
    if "fem_options" in payload:
        spec.fem_options = _parse_solver_options(
            payload["fem_options"], FEMOptionsSpec, "fem_options"
        )
    if "pbd_options" in payload:
        spec.pbd_options = _parse_solver_options(
            payload["pbd_options"], PBDOptionsSpec, "pbd_options"
        )

    # Validate optics fields we can validate without Genesis
    if spec.raytracer is not None:
        rt_errors = spec.raytracer.validate()
        if rt_errors:
            raise _err("Invalid raytracer options", context={"errors": rt_errors})
    for ent in spec.entities:
        if ent.surface is not None:
            s_errors = ent.surface.validate()
            if s_errors:
                raise _err(
                    "Invalid entity surface", context={"entity": ent.name, "errors": s_errors}
                )

    return spec


async def generate_genesis_video(payload: dict[str, Any]) -> dict[str, Any]:
    """Async creator API: generate a Genesis video from a dict[str, Any] spec."""
    spec = parse_genesis_video_spec(payload)

    # Run the heavy synchronous generator in a thread to avoid blocking.
    gen = GenesisVideoGenerator()

    def _run() -> Path:
        try:
            return gen.generate(spec)
        except ImportError as e:
            # Common case: `genesis-world` not installed.
            raise ModuleNotAvailableError("genesis-world") from e

    out_dir = await asyncio.to_thread(_run)
    return {
        "output_dir": str(out_dir),
        "spec": asdict(spec),
    }


__all__ = [
    "generate_genesis_video",
    "parse_genesis_video_spec",
]
