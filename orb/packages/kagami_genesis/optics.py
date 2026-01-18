"""Genesis optics + rendering config primitives.

This module is intentionally Genesis-import-free at import time.
It provides dataclasses that:
- represent RayTracer options (as documented in Genesis 0.3.10)
- represent Surface options (Glass/Water/Metal/etc.)
- can be converted to Genesis constructor kwargs at runtime

Forge uses these specs to expose a richer, testable control surface without
requiring the optional `genesis-world` dependency in unit tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal


class ReconBackend(str, Enum):
    """Surface reconstruction backend for particle-based entities."""

    SPLASHSURF = "splashsurf"
    OPENVDB = "openvdb"


class SurfaceKind(str, Enum):
    """High-level surface selection (maps to `gs.surfaces.*`)."""

    DEFAULT = "default"
    METAL = "metal"
    EMISSION = "emission"
    GLASS = "glass"
    WATER = "water"


@dataclass(frozen=True, slots=True)
class RayTracerLight:
    """RayTracer light (maps to dict accepted by `gs.renderers.RayTracer`)."""

    pos: tuple[float, float, float] = (0.0, 0.0, 10.0)
    color: tuple[float, float, float] = (1.0, 1.0, 1.0)
    intensity: float = 1.0
    radius: float = 0.1

    def to_dict(self) -> dict[str, Any]:
        return {
            "pos": tuple(float(x) for x in self.pos),
            "color": tuple(float(x) for x in self.color),
            "intensity": float(self.intensity),
            "radius": float(self.radius),
        }


@dataclass
class GenesisSurfaceSpec:
    """Portable surface specification.

    This is a *portable* spec that can be:
    - validated
    - converted to Genesis surface constructor kwargs
    - instantiated into a `gs.surfaces.*` object at runtime

    Notes:
    - Genesis supports more surface classes; Forge focuses on the ones it uses
      today (Default/Metal/Emission/Glass/Water).
    - Glass/Water support advanced parameters such as `ior`, simple BSSRDF
      `subsurface`, `thickness`, and particle surface reconstruction/foam.
    """

    # If None, the caller is expected to infer kind (e.g. merge-on-top-of-preset).
    kind: SurfaceKind | None = None

    # Common / shortcut attributes
    color: tuple[float, float, float] | None = None
    opacity: float | None = None
    roughness: float | None = None
    metallic: float | None = None
    emissive: tuple[float, float, float] | None = None

    # Refraction (Glass/Water)
    ior: float | None = None

    # Glass/Water advanced
    subsurface: bool | None = None
    thickness: float | None = None
    smooth: bool | None = None
    double_sided: bool | None = None
    cutoff: float | None = None
    normal_diff_clamp: float | None = None
    recon_backend: ReconBackend | str | None = None
    generate_foam: bool | None = None
    foam_options: Any | None = None

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.opacity is not None and not (0.0 <= float(self.opacity) <= 1.0):
            errors.append("surface.opacity must be in [0, 1]")
        if self.roughness is not None and not (0.0 <= float(self.roughness) <= 1.0):
            errors.append("surface.roughness must be in [0, 1]")
        if self.metallic is not None and not (0.0 <= float(self.metallic) <= 1.0):
            errors.append("surface.metallic must be in [0, 1]")
        if self.ior is not None and float(self.ior) <= 1.0:
            # Physics: n>=1; air ~1.0. We require >1.0 for "refractive" intent.
            errors.append("surface.ior must be > 1.0")
        if self.cutoff is not None and not (0.0 <= float(self.cutoff) <= 180.0):
            errors.append("surface.cutoff must be in [0, 180]")
        if self.normal_diff_clamp is not None and not (
            0.0 <= float(self.normal_diff_clamp) <= 180.0
        ):
            errors.append("surface.normal_diff_clamp must be in [0, 180]")
        if self.thickness is not None and float(self.thickness) < 0.0:
            errors.append("surface.thickness must be >= 0")
        return errors

    def to_constructor_kwargs(self) -> dict[str, Any]:
        """Return kwargs suitable for `gs.surfaces.<Kind>(**kwargs)`."""
        kwargs: dict[str, Any] = {}

        # Common shortcuts (supported broadly)
        if self.color is not None:
            kwargs["color"] = tuple(float(x) for x in self.color)
        if self.opacity is not None:
            kwargs["opacity"] = float(self.opacity)
        if self.roughness is not None:
            kwargs["roughness"] = float(self.roughness)
        if self.metallic is not None:
            kwargs["metallic"] = float(self.metallic)
        if self.emissive is not None:
            kwargs["emissive"] = tuple(float(x) for x in self.emissive)

        # Refraction
        if self.ior is not None:
            kwargs["ior"] = float(self.ior)

        # Glass/Water advanced
        if self.subsurface is not None:
            kwargs["subsurface"] = bool(self.subsurface)
        if self.thickness is not None:
            kwargs["thickness"] = float(self.thickness)
        if self.smooth is not None:
            kwargs["smooth"] = bool(self.smooth)
        if self.double_sided is not None:
            kwargs["double_sided"] = bool(self.double_sided)
        if self.cutoff is not None:
            kwargs["cutoff"] = float(self.cutoff)
        if self.normal_diff_clamp is not None:
            kwargs["normal_diff_clamp"] = float(self.normal_diff_clamp)
        if self.recon_backend is not None:
            kwargs["recon_backend"] = (
                self.recon_backend.value
                if isinstance(self.recon_backend, ReconBackend)
                else str(self.recon_backend)
            )
        if self.generate_foam is not None:
            kwargs["generate_foam"] = bool(self.generate_foam)
        if self.foam_options is not None:
            kwargs["foam_options"] = self.foam_options

        return kwargs

    def to_gs_surface(self, gs: Any) -> Any:
        """Instantiate a Genesis surface object from this spec."""
        errors = self.validate()
        if errors:
            raise ValueError(f"Invalid GenesisSurfaceSpec: {', '.join(errors)}")

        kwargs = self.to_constructor_kwargs()
        kind = self.kind or SurfaceKind.DEFAULT

        if kind == SurfaceKind.METAL:
            # Metal supports at least (color, roughness)
            return gs.surfaces.Metal(**kwargs)
        if kind == SurfaceKind.EMISSION:
            # Emission uses emissive radiance, not albedo.
            # If caller set only `color`, treat it as emissive as a convenience.
            if "emissive" not in kwargs and "color" in kwargs:
                kwargs["emissive"] = kwargs.pop("color")
            return gs.surfaces.Emission(**kwargs)
        if kind == SurfaceKind.GLASS:
            return gs.surfaces.Glass(**kwargs)
        if kind == SurfaceKind.WATER:
            return gs.surfaces.Water(**kwargs)
        # Default / fallback
        return gs.surfaces.Default(**kwargs)

    @classmethod
    def emission_env(cls, *, emissive: tuple[float, float, float]) -> GenesisSurfaceSpec:
        return cls(kind=SurfaceKind.EMISSION, emissive=emissive)


@dataclass
class RayTracerOptions:
    """Portable RayTracer option set (Genesis 0.3.10).

    Designed to map cleanly onto `gs.renderers.RayTracer(**kwargs)`.
    """

    # Logging + integrator
    logging_level: Literal["debug", "info", "warning"] = "warning"
    state_limit: int | None = None  # Defaults to 2**25 in Genesis

    # Path tracing
    tracing_depth: int | None = None  # Defaults to 32 in Genesis
    rr_depth: int | None = None  # Defaults to 0 in Genesis
    rr_threshold: float | None = None  # Defaults to 0.95 in Genesis

    # Environment
    env_surface: GenesisSurfaceSpec | None = None
    env_radius: float | None = None  # Defaults to 1000.0 in Genesis
    env_pos: tuple[float, float, float] | None = None
    env_euler: tuple[float, float, float] | None = None
    env_quat: tuple[float, float, float, float] | None = None

    # Lights
    lights: list[RayTracerLight] = field(default_factory=list)

    # Shading normal interpolation clamp
    normal_diff_clamp: float | None = None  # Defaults to 180

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.tracing_depth is not None and int(self.tracing_depth) <= 0:
            errors.append("raytracer.tracing_depth must be > 0")
        if self.rr_depth is not None and int(self.rr_depth) < 0:
            errors.append("raytracer.rr_depth must be >= 0")
        if self.rr_threshold is not None and not (0.0 < float(self.rr_threshold) <= 1.0):
            errors.append("raytracer.rr_threshold must be in (0, 1]")
        if self.env_radius is not None and float(self.env_radius) <= 0.0:
            errors.append("raytracer.env_radius must be > 0")
        if self.normal_diff_clamp is not None and not (
            0.0 <= float(self.normal_diff_clamp) <= 180.0
        ):
            errors.append("raytracer.normal_diff_clamp must be in [0, 180]")
        if self.state_limit is not None and int(self.state_limit) <= 0:
            errors.append("raytracer.state_limit must be > 0")
        if self.env_surface is not None:
            errors.extend(f"env_surface.{e}" for e in self.env_surface.validate())
        return errors

    def to_dict(self) -> dict[str, Any]:
        """Plain-Python representation (no Genesis dependency)."""
        return {
            "logging_level": self.logging_level,
            "state_limit": self.state_limit,
            "tracing_depth": self.tracing_depth,
            "rr_depth": self.rr_depth,
            "rr_threshold": self.rr_threshold,
            "env_surface": None if self.env_surface is None else self.env_surface.__dict__,
            "env_radius": self.env_radius,
            "env_pos": self.env_pos,
            "env_euler": self.env_euler,
            "env_quat": self.env_quat,
            "lights": [l.to_dict() for l in self.lights],
            "normal_diff_clamp": self.normal_diff_clamp,
        }

    def to_gs_kwargs(self, gs: Any) -> dict[str, Any]:
        """Genesis constructor kwargs for `gs.renderers.RayTracer`."""
        errors = self.validate()
        if errors:
            raise ValueError(f"Invalid RayTracerOptions: {', '.join(errors)}")

        kwargs: dict[str, Any] = {"logging_level": self.logging_level}

        if self.state_limit is not None:
            kwargs["state_limit"] = int(self.state_limit)
        if self.tracing_depth is not None:
            kwargs["tracing_depth"] = int(self.tracing_depth)
        if self.rr_depth is not None:
            kwargs["rr_depth"] = int(self.rr_depth)
        if self.rr_threshold is not None:
            kwargs["rr_threshold"] = float(self.rr_threshold)

        if self.env_surface is not None:
            kwargs["env_surface"] = self.env_surface.to_gs_surface(gs)
        if self.env_radius is not None:
            kwargs["env_radius"] = float(self.env_radius)
        if self.env_pos is not None:
            kwargs["env_pos"] = tuple(float(x) for x in self.env_pos)
        if self.env_euler is not None:
            kwargs["env_euler"] = tuple(float(x) for x in self.env_euler)
        if self.env_quat is not None:
            kwargs["env_quat"] = tuple(float(x) for x in self.env_quat)

        if self.lights:
            kwargs["lights"] = [l.to_dict() for l in self.lights]
        if self.normal_diff_clamp is not None:
            kwargs["normal_diff_clamp"] = float(self.normal_diff_clamp)

        return kwargs


__all__ = [
    "GenesisSurfaceSpec",
    "RayTracerLight",
    "RayTracerOptions",
    "ReconBackend",
    "SurfaceKind",
]
