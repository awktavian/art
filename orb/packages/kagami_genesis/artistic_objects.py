"""Artistic Object Generation for Genesis Physics.

Procedural generation of unique artistic physics objects with:
- Colony-inspired color palettes
- Golden ratio proportions
- Material/shape coherence
- Momentum characteristics

Colony: Forge (e2)
"""

from __future__ import annotations

import logging
import math
import random
from dataclasses import dataclass
from enum import Enum
from typing import Any

import numpy as np

from kagami_genesis.materials import (
    AcousticProperties,
    SurfaceType,
)

logger = logging.getLogger(__name__)

# Golden ratio for aesthetic proportions
PHI = 1.618033988749895


class ShapeType(Enum):
    """Available shape primitives."""

    SPHERE = "sphere"
    BOX = "box"
    CYLINDER = "cylinder"
    CAPSULE = "capsule"
    TORUS = "torus"
    CONE = "cone"


class MassDistribution(Enum):
    """Mass distribution patterns."""

    UNIFORM = "uniform"
    WEIGHTED_BOTTOM = "weighted_bottom"
    WEIGHTED_TOP = "weighted_top"
    HOLLOW = "hollow"
    DENSE_CORE = "dense_core"


class MomentumCharacter(Enum):
    """Physics behavior character."""

    HEAVY_SLOW = "heavy_slow"
    LIGHT_BOUNCY = "light_bouncy"
    SPINNING = "spinning"
    ROLLING = "rolling"
    TUMBLING = "tumbling"
    FLOATING = "floating"


class ColorHarmony(Enum):
    """Color harmony types."""

    COMPLEMENTARY = "complementary"
    ANALOGOUS = "analogous"
    TRIADIC = "triadic"
    SPLIT_COMPLEMENTARY = "split_complementary"
    MONOCHROMATIC = "monochromatic"


@dataclass
class ArtisticObjectSpec:
    """Specification for an artistically designed physics object."""

    name: str
    shape: ShapeType
    position: tuple[float, float, float]
    size: tuple[float, float, float]
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0)

    # Material
    material_type: SurfaceType = SurfaceType.DEFAULT
    color: tuple[float, float, float] = (0.8, 0.8, 0.8)
    roughness: float = 0.3
    metallic: float = 0.0
    ior: float = 1.0
    emissive: tuple[float, float, float] | None = None
    emissive_intensity: float = 100.0

    # Physics
    density: float = 2500.0
    mass_distribution: MassDistribution = MassDistribution.UNIFORM
    initial_velocity: tuple[float, float, float] = (0.0, 0.0, 0.0)
    initial_angular_velocity: tuple[float, float, float] = (0.0, 0.0, 0.0)
    momentum_character: MomentumCharacter = MomentumCharacter.HEAVY_SLOW

    # Aesthetic
    color_harmony: ColorHarmony = ColorHarmony.ANALOGOUS
    light_interaction: str = "absorb"

    # Acoustic
    acoustic: AcousticProperties | None = None

    def to_genesis_params(self) -> dict[str, Any]:
        """Convert to Genesis-compatible parameters."""
        return {
            "name": self.name,
            "shape": self.shape.value,
            "position": self.position,
            "size": self.size,
            "rotation": self.rotation,
            "material": self.material_type.value,
            "color": self.color,
            "roughness": self.roughness,
            "ior": self.ior,
            "emissive": self.emissive,
            "emissive_intensity": self.emissive_intensity,
            "density": self.density,
            "velocity": (*self.initial_velocity, *self.initial_angular_velocity),
        }


# Colony-inspired color palettes
COLONY_PALETTES: dict[str, list[tuple[float, float, float]]] = {
    "spark": [
        (1.0, 0.3, 0.0),  # Flame orange
        (1.0, 0.6, 0.0),  # Golden fire
        (1.0, 0.9, 0.5),  # Light flame
        (0.9, 0.2, 0.1),  # Deep ember
        (1.0, 0.5, 0.2),  # Warm amber
    ],
    "forge": [
        (0.3, 0.3, 0.35),  # Dark steel
        (0.9, 0.9, 0.95),  # Bright chrome
        (1.0, 0.85, 0.3),  # Gold accent
        (0.6, 0.6, 0.65),  # Mid steel
        (0.15, 0.15, 0.18),  # Deep iron
    ],
    "flow": [
        (0.0, 0.5, 1.0),  # Ocean blue
        (0.0, 0.8, 0.9),  # Cyan
        (0.7, 0.9, 1.0),  # Ice blue
        (0.2, 0.4, 0.8),  # Deep water
        (0.4, 0.7, 0.95),  # Sky blue
    ],
    "nexus": [
        (0.5, 0.0, 1.0),  # Deep violet
        (0.8, 0.3, 1.0),  # Bright purple
        (1.0, 0.5, 1.0),  # Pink
        (0.3, 0.0, 0.6),  # Dark purple
        (0.6, 0.2, 0.9),  # Mid violet
    ],
    "beacon": [
        (1.0, 1.0, 0.9),  # Warm white
        (1.0, 0.95, 0.7),  # Soft gold
        (0.9, 0.8, 0.5),  # Brass
        (1.0, 0.9, 0.6),  # Light gold
        (0.95, 0.85, 0.6),  # Antique gold
    ],
    "grove": [
        (0.0, 0.6, 0.3),  # Forest green
        (0.3, 0.8, 0.4),  # Spring green
        (0.6, 0.9, 0.5),  # Light green
        (0.1, 0.4, 0.2),  # Deep forest
        (0.4, 0.7, 0.3),  # Moss
    ],
    "crystal": [
        (0.8, 0.9, 1.0),  # Ice white
        (0.6, 0.7, 1.0),  # Crystal blue
        (0.9, 0.95, 1.0),  # Frost
        (0.5, 0.6, 0.9),  # Deep crystal
        (0.7, 0.8, 0.95),  # Light ice
    ],
}

# Shape-material affinity (what materials look good with what shapes)
SHAPE_MATERIAL_AFFINITY: dict[ShapeType, list[SurfaceType]] = {
    ShapeType.SPHERE: [SurfaceType.METAL, SurfaceType.GLASS, SurfaceType.DEFAULT],
    ShapeType.BOX: [SurfaceType.METAL, SurfaceType.DEFAULT, SurfaceType.EMISSION],
    ShapeType.CYLINDER: [SurfaceType.METAL, SurfaceType.DEFAULT],
    ShapeType.CAPSULE: [SurfaceType.DEFAULT, SurfaceType.GLASS],
    ShapeType.TORUS: [SurfaceType.METAL, SurfaceType.GLASS, SurfaceType.EMISSION],
    ShapeType.CONE: [SurfaceType.DEFAULT, SurfaceType.EMISSION],
}


class ArtisticObjectFactory:
    """Factory for generating unique artistic physics objects."""

    def __init__(self, seed: int | None = None) -> None:
        """Initialize factory with optional seed for reproducibility."""
        self._rng = random.Random(seed)
        self._np_rng = np.random.default_rng(seed)
        self._object_counter = 0

    def _generate_golden_size(
        self,
        base: float,
        variance: float = 0.2,
    ) -> tuple[float, float, float]:
        """Generate size with golden ratio proportions."""
        base = base * (1.0 + self._rng.uniform(-variance, variance))
        return (
            base,
            base * PHI,
            base / PHI,
        )

    def _select_material_for_shape(
        self,
        shape: ShapeType,
        color: tuple[float, float, float],
        theme: str,
    ) -> tuple[SurfaceType, float, float, float]:
        """Select appropriate material for shape and color.

        Returns (surface_type, roughness, metallic, ior).
        """
        affinities = SHAPE_MATERIAL_AFFINITY.get(shape, [SurfaceType.DEFAULT])
        surface = self._rng.choice(affinities)

        # Adjust properties based on surface type
        if surface == SurfaceType.METAL:
            roughness = self._rng.uniform(0.02, 0.15)
            metallic = 1.0
            ior = 1.0
        elif surface == SurfaceType.GLASS:
            roughness = 0.0
            metallic = 0.0
            ior = self._rng.uniform(1.4, 1.7)
        elif surface == SurfaceType.EMISSION:
            roughness = 0.5
            metallic = 0.0
            ior = 1.0
        else:
            roughness = self._rng.uniform(0.3, 0.7)
            metallic = 0.0
            ior = 1.0

        return surface, roughness, metallic, ior

    def _compute_momentum_character(
        self,
        material: SurfaceType,
        density: float,
        shape: ShapeType,
    ) -> MomentumCharacter:
        """Determine momentum character based on physical properties."""
        if density > 7000:
            return MomentumCharacter.HEAVY_SLOW
        if density < 1500:
            return MomentumCharacter.LIGHT_BOUNCY
        if shape == ShapeType.SPHERE:
            return MomentumCharacter.ROLLING
        if shape == ShapeType.CYLINDER:
            return self._rng.choice([MomentumCharacter.ROLLING, MomentumCharacter.TUMBLING])
        return MomentumCharacter.TUMBLING

    def _generate_initial_velocity(
        self,
        momentum: MomentumCharacter,
        position: tuple[float, float, float],
    ) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
        """Generate initial linear and angular velocity."""
        linear = (0.0, 0.0, 0.0)
        angular = (0.0, 0.0, 0.0)

        if momentum == MomentumCharacter.HEAVY_SLOW:
            linear = (
                self._rng.uniform(-0.3, 0.3),
                self._rng.uniform(-0.3, 0.3),
                self._rng.uniform(-0.5, 0.0),
            )
        elif momentum == MomentumCharacter.LIGHT_BOUNCY:
            linear = (
                self._rng.uniform(-1.0, 1.0),
                self._rng.uniform(-1.0, 1.0),
                self._rng.uniform(0.0, 2.0),
            )
        elif momentum == MomentumCharacter.SPINNING:
            angular = (
                self._rng.uniform(-5.0, 5.0),
                self._rng.uniform(-5.0, 5.0),
                self._rng.uniform(-5.0, 5.0),
            )
        elif momentum == MomentumCharacter.ROLLING:
            linear = (
                self._rng.uniform(-0.5, 0.5),
                self._rng.uniform(-0.5, 0.5),
                0.0,
            )
            angular = (
                self._rng.uniform(-3.0, 3.0),
                self._rng.uniform(-3.0, 3.0),
                0.0,
            )
        elif momentum == MomentumCharacter.TUMBLING:
            linear = (
                self._rng.uniform(-0.5, 0.5),
                self._rng.uniform(-0.5, 0.5),
                self._rng.uniform(-0.5, 0.0),
            )
            angular = (
                self._rng.uniform(-2.0, 2.0),
                self._rng.uniform(-2.0, 2.0),
                self._rng.uniform(-2.0, 2.0),
            )
        elif momentum == MomentumCharacter.FLOATING:
            linear = (
                self._rng.uniform(-0.1, 0.1),
                self._rng.uniform(-0.1, 0.1),
                self._rng.uniform(-0.1, 0.1),
            )

        return linear, angular

    def _get_acoustic_for_material(
        self,
        material: SurfaceType,
        density: float,
    ) -> AcousticProperties:
        """Generate acoustic properties based on material."""
        if material == SurfaceType.METAL:
            freqs = (800 + density / 10, 2400 + density / 5, 4800 + density / 3)
            return AcousticProperties(freqs, 0.92, 0.95, 0.9)
        if material == SurfaceType.GLASS:
            return AcousticProperties((2000, 5000, 8000), 0.85, 0.9, 0.85)
        if material == SurfaceType.WATER:
            return AcousticProperties((80, 200, 400), 0.2, 0.0, 0.15)
        return AcousticProperties((200, 600, 1200), 0.4, 0.55, 0.3)

    def generate_object(
        self,
        theme: str = "forge",
        position: tuple[float, float, float] | None = None,
        base_size: float | None = None,
        shape: ShapeType | None = None,
        name_prefix: str | None = None,
    ) -> ArtisticObjectSpec:
        """Generate a single artistic object.

        Args:
            theme: Colony theme for color palette
            position: Object position (random if None)
            base_size: Base size (random 0.1-0.4 if None)
            shape: Shape type (random if None)
            name_prefix: Prefix for object name

        Returns:
            ArtisticObjectSpec for the generated object
        """
        self._object_counter += 1
        palette = COLONY_PALETTES.get(theme, COLONY_PALETTES["forge"])

        # Position
        if position is None:
            position = (
                self._rng.uniform(-2.0, 2.0),
                self._rng.uniform(-2.0, 2.0),
                self._rng.uniform(0.5, 3.0),
            )

        # Shape
        if shape is None:
            shape = self._rng.choice(list(ShapeType))

        # Size with golden ratio
        if base_size is None:
            base_size = self._rng.uniform(0.1, 0.4)
        size = self._generate_golden_size(base_size)

        # Color from palette
        color = self._rng.choice(palette)

        # Material
        surface, roughness, metallic, ior = self._select_material_for_shape(shape, color, theme)

        # Density based on material
        if surface == SurfaceType.METAL:
            density = self._rng.uniform(7000, 8500)
        elif surface == SurfaceType.GLASS:
            density = self._rng.uniform(2300, 2700)
        elif surface == SurfaceType.WATER:
            density = 1000
        else:
            density = self._rng.uniform(1500, 3500)

        # Momentum character
        momentum = self._compute_momentum_character(surface, density, shape)

        # Initial velocity
        linear_vel, angular_vel = self._generate_initial_velocity(momentum, position)

        # Emission for emissive materials
        emissive = None
        emissive_intensity = 100.0
        if surface == SurfaceType.EMISSION:
            emissive = color
            emissive_intensity = self._rng.uniform(150, 350)

        # Acoustic properties
        acoustic = self._get_acoustic_for_material(surface, density)

        # Name
        prefix = name_prefix or theme
        name = f"{prefix}_{shape.value}_{self._object_counter}"

        return ArtisticObjectSpec(
            name=name,
            shape=shape,
            position=position,
            size=size,
            rotation=(
                self._rng.uniform(0, math.pi * 2),
                self._rng.uniform(0, math.pi * 2),
                self._rng.uniform(0, math.pi * 2),
            ),
            material_type=surface,
            color=color,
            roughness=roughness,
            metallic=metallic,
            ior=ior,
            emissive=emissive,
            emissive_intensity=emissive_intensity,
            density=density,
            mass_distribution=self._rng.choice(list(MassDistribution)),
            initial_velocity=linear_vel,
            initial_angular_velocity=angular_vel,
            momentum_character=momentum,
            color_harmony=ColorHarmony.ANALOGOUS,
            light_interaction=surface.value,
            acoustic=acoustic,
        )

    def generate_scene_objects(
        self,
        count: int,
        theme: str = "forge",
        physics_style: str = "dynamic",
        spawn_area: tuple[float, float, float, float, float, float] | None = None,
    ) -> list[ArtisticObjectSpec]:
        """Generate a coherent set of artistic objects for a scene.

        Args:
            count: Number of objects to generate
            theme: Colony theme for color palette
            physics_style: 'dynamic' for movement, 'static' for still
            spawn_area: (min_x, max_x, min_y, max_y, min_z, max_z)

        Returns:
            List of ArtisticObjectSpec objects
        """
        if spawn_area is None:
            spawn_area = (-2.0, 2.0, -2.0, 2.0, 0.5, 3.0)

        objects = []
        # Note: palette is used by generate_object internally
        _ = COLONY_PALETTES.get(theme, COLONY_PALETTES["forge"])

        # Ensure variety by cycling through shapes
        shapes = list(ShapeType)

        for i in range(count):
            # Position within spawn area
            position = (
                self._rng.uniform(spawn_area[0], spawn_area[1]),
                self._rng.uniform(spawn_area[2], spawn_area[3]),
                self._rng.uniform(spawn_area[4], spawn_area[5]),
            )

            # Cycle through shapes for variety
            shape = shapes[i % len(shapes)]

            # Size variation - larger objects spawn higher
            height_factor = (position[2] - spawn_area[4]) / (spawn_area[5] - spawn_area[4])
            base_size = 0.1 + height_factor * 0.3

            obj = self.generate_object(
                theme=theme,
                position=position,
                base_size=base_size,
                shape=shape,
                name_prefix=f"{theme}_{i}",
            )

            # Adjust velocity for physics style
            if physics_style == "static":
                obj.initial_velocity = (0.0, 0.0, 0.0)
                obj.initial_angular_velocity = (0.0, 0.0, 0.0)
            elif physics_style == "chaotic":
                # More extreme velocities
                obj.initial_velocity = tuple(v * 2.0 for v in obj.initial_velocity)  # type: ignore[assignment]
                obj.initial_angular_velocity = tuple(v * 2.0 for v in obj.initial_angular_velocity)  # type: ignore[assignment]

            objects.append(obj)

        return objects

    def generate_light_array(
        self,
        count: int,
        theme: str = "beacon",
        arrangement: str = "circle",
        center: tuple[float, float, float] = (0.0, 0.0, 1.5),
        radius: float = 2.5,
    ) -> list[ArtisticObjectSpec]:
        """Generate an array of emissive light objects.

        Args:
            count: Number of lights
            theme: Colony theme for colors
            arrangement: 'circle', 'line', 'grid'
            center: Center position
            radius: Radius for circle arrangement

        Returns:
            List of emissive ArtisticObjectSpec objects
        """
        palette = COLONY_PALETTES.get(theme, COLONY_PALETTES["beacon"])
        lights = []

        for i in range(count):
            # Position based on arrangement
            if arrangement == "circle":
                angle = (2 * math.pi * i) / count
                position = (
                    center[0] + radius * math.cos(angle),
                    center[1] + radius * math.sin(angle),
                    center[2],
                )
            elif arrangement == "line":
                offset = (i - count / 2) * (radius * 2 / count)
                position = (center[0] + offset, center[1], center[2])
            else:  # grid
                cols = int(math.sqrt(count))
                row = i // cols
                col = i % cols
                position = (
                    center[0] + (col - cols / 2) * 0.5,
                    center[1] + (row - cols / 2) * 0.5,
                    center[2],
                )

            color = palette[i % len(palette)]

            lights.append(
                ArtisticObjectSpec(
                    name=f"light_{theme}_{i}",
                    shape=ShapeType.BOX,
                    position=position,
                    size=(0.05, 0.05, 2.0),  # Tall thin neon bar
                    material_type=SurfaceType.EMISSION,
                    color=color,
                    emissive=color,
                    emissive_intensity=self._rng.uniform(200, 400),
                    density=100,  # Very light
                    mass_distribution=MassDistribution.UNIFORM,
                    initial_velocity=(0.0, 0.0, 0.0),
                    initial_angular_velocity=(0.0, 0.0, 0.0),
                    momentum_character=MomentumCharacter.FLOATING,
                    color_harmony=ColorHarmony.ANALOGOUS,
                    light_interaction="emit",
                ),
            )

        return lights


def create_neon_cathedral_objects(seed: int = 42) -> list[ArtisticObjectSpec]:
    """Create a complete Neon Cathedral scene with artistic objects.

    Returns:
        List of all scene objects
    """
    factory = ArtisticObjectFactory(seed=seed)
    objects = []

    # Central altar - large chrome box
    objects.append(
        ArtisticObjectSpec(
            name="altar",
            shape=ShapeType.BOX,
            position=(0.0, 0.0, 0.5),
            size=(0.8, 0.8, 1.0),
            material_type=SurfaceType.METAL,
            color=(0.9, 0.9, 0.95),
            roughness=0.05,
            metallic=1.0,
            density=7800,
            mass_distribution=MassDistribution.UNIFORM,
            momentum_character=MomentumCharacter.HEAVY_SLOW,
            acoustic=AcousticProperties((800, 2400, 4800), 0.92, 0.95, 0.9),
        ),
    )

    # Glass orb on altar
    objects.append(
        ArtisticObjectSpec(
            name="orb",
            shape=ShapeType.SPHERE,
            position=(0.0, 0.0, 1.3),
            size=(0.25, 0.25, 0.25),
            material_type=SurfaceType.GLASS,
            color=(0.95, 0.95, 1.0),
            roughness=0.0,
            ior=1.52,
            density=2500,
            momentum_character=MomentumCharacter.ROLLING,
            acoustic=AcousticProperties((2000, 5000, 8000), 0.85, 0.9, 0.85),
        ),
    )

    # Neon light bars (circular arrangement)
    neon_lights = factory.generate_light_array(
        count=4,
        theme="nexus",
        arrangement="circle",
        center=(0.0, 0.0, 1.5),
        radius=2.0,
    )
    objects.extend(neon_lights)

    # Flying chrome spheres
    flying_objects = factory.generate_scene_objects(
        count=4,
        theme="forge",
        physics_style="dynamic",
        spawn_area=(-1.5, 1.5, -1.5, 1.5, 1.5, 2.5),
    )
    objects.extend(flying_objects)

    # Gold accent spheres
    gold_spheres = factory.generate_scene_objects(
        count=2,
        theme="beacon",
        physics_style="dynamic",
        spawn_area=(-0.5, 0.5, -0.5, 0.5, 1.5, 2.0),
    )
    for obj in gold_spheres:
        obj.shape = ShapeType.SPHERE
        obj.material_type = SurfaceType.METAL
        obj.color = (1.0, 0.85, 0.3)
        obj.roughness = 0.1
        obj.metallic = 1.0
        obj.density = 19300  # Gold density
    objects.extend(gold_spheres)

    return objects


__all__ = [
    "COLONY_PALETTES",
    "ArtisticObjectFactory",
    "ArtisticObjectSpec",
    "ColorHarmony",
    "MassDistribution",
    "MomentumCharacter",
    "ShapeType",
    "create_neon_cathedral_objects",
]
