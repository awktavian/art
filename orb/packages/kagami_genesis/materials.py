"""Genesis Material Definitions — 40+ Physically-Based Material Presets.

This module provides a comprehensive library of material presets for the
Genesis real-time rendering engine. Each preset includes visual properties
(color, roughness, IOR) and physical properties (density, acoustic response)
for multi-modal simulation.

Material Categories (organized by Colony):
    - METALS (Forge, e₂): Chrome, gold, copper, titanium, etc.
    - GLASS & TRANSPARENT (Crystal, e₇): Diamond, sapphire, ice, etc.
    - FLUIDS (Flow, e₃): Water, mercury, honey, oil
    - NEON & EMISSIVE (Spark/Beacon, e₁/e₅): Neon colors, holograms, plasma
    - STONE & EARTH (Grove, e₆): Marble, granite, concrete, clay
    - SPECIAL (Nexus, e₄): Floors, rubber, leather, carbon fiber

Physical Properties:
    - Density: kg/m³ for mass calculation
    - Acoustic: Modal frequencies for physics-based audio synthesis
    - IOR: Index of refraction for glass/transparent materials
    - Roughness: Microfacet roughness (0=mirror, 1=diffuse)

Usage:
    >>> from kagami_genesis.materials import MaterialLibrary, MATERIAL_PRESETS
    >>> # List available presets
    >>> print(list(MATERIAL_PRESETS.keys()))
    >>> # Create a Genesis surface from preset
    >>> surface = MaterialLibrary.create_surface("chrome")
    >>> # Override specific properties
    >>> from kagami_genesis.optics import GenesisSurfaceSpec
    >>> custom = GenesisSurfaceSpec(roughness=0.1)
    >>> surface = MaterialLibrary.create_surface("gold", overrides=custom)

Colony: Forge (e₂) — Material creation and building
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from kagami_genesis.optics import GenesisSurfaceSpec, SurfaceKind


class SurfaceType(Enum):
    """Genesis surface shader types.

    Each surface type corresponds to a different rendering shader with
    distinct light transport behavior.

    Attributes:
        DEFAULT: Standard diffuse/specular material (Lambertian + GGX).
        GLASS: Dielectric with refraction (Snell's law + Fresnel).
        METAL: Conductor with complex IOR (no subsurface scattering).
        EMISSION: Self-luminous material (area light source).
        WATER: Specialized fluid surface with caustics support.
    """

    DEFAULT = "default"
    """Standard diffuse/specular surface (most common)."""
    GLASS = "glass"
    """Transparent dielectric with refraction."""
    METAL = "metal"
    """Metallic conductor with complex Fresnel."""
    EMISSION = "emission"
    """Self-luminous emissive surface."""
    WATER = "water"
    """Fluid surface with special caustics handling."""


@dataclass
class AcousticProperties:
    """Material acoustic properties for physics-based audio synthesis.

    These properties drive modal synthesis for impact/contact sounds,
    enabling realistic audio feedback when objects collide.

    Modal synthesis models:
        - Each frequency represents a resonant mode of the material
        - Damping controls how quickly vibrations decay
        - Hardness affects attack transient character
        - Resonance affects sustain/ring quality

    Attributes:
        modal_frequencies: Resonant mode frequencies in Hz.
            Typically 3 modes: fundamental, 3x, 6x.
        damping: Vibration decay rate (0=infinite sustain, 1=instant decay).
            Higher values = duller sound. Metal ~0.92, rubber ~0.1.
        hardness: Impact transient character (0=soft thud, 1=sharp click).
            Affects attack portion of sound.
        resonance: Sustain/ring quality (0=dead, 1=bell-like).
            Affects body of sound after initial transient.

    Example:
        >>> # Bell-like metal
        >>> bell = AcousticProperties(
        ...     modal_frequencies=(440, 1320, 2640),
        ...     damping=0.95,
        ...     hardness=0.9,
        ...     resonance=0.95,
        ... )
    """

    modal_frequencies: tuple[float, ...] = (800, 2400, 4800)
    """Resonant mode frequencies in Hz (fundamental + harmonics)."""
    damping: float = 0.92
    """Vibration decay rate (0=infinite sustain, 1=instant decay)."""
    hardness: float = 0.95
    """Impact transient character (0=soft, 1=hard)."""
    resonance: float = 0.9
    """Sustain/ring quality (0=dead, 1=bell-like)."""


@dataclass
class MaterialPreset:
    """Complete material preset with visual and physical properties.

    Combines rendering parameters (surface type, color, roughness, IOR)
    with physical simulation parameters (density, acoustic properties)
    for multi-modal realism.

    Attributes:
        surface_type: Genesis shader type to use.
        color: Base color as RGB tuple (0-1 range for each channel).
        roughness: Microfacet roughness (0=mirror, 1=fully diffuse).
        ior: Index of refraction for transparent materials.
            Air=1.0, Water=1.33, Glass=1.52, Diamond=2.42.
        emissive: RGB emission color for self-luminous materials.
            Values can exceed 1.0 for bright sources.
        density: Material density in kg/m³ for mass calculation.
        acoustic: Acoustic properties for physics audio, or None.

    Example:
        >>> chrome = MaterialPreset(
        ...     surface_type=SurfaceType.METAL,
        ...     color=(0.95, 0.95, 0.97),
        ...     roughness=0.05,
        ...     density=7800,
        ...     acoustic=AcousticProperties((800, 2400, 4800), 0.92, 0.95, 0.9),
        ... )
    """

    surface_type: SurfaceType
    """Genesis shader type for this material."""
    color: tuple[float, float, float]
    """Base color as RGB (0-1 range per channel)."""
    roughness: float = 0.3
    """Microfacet roughness (0=smooth mirror, 1=diffuse)."""
    ior: float = 1.0
    """Index of refraction (for glass/transparent materials)."""
    emissive: tuple[float, float, float] | None = None
    """Emission color RGB (can exceed 1.0 for brightness)."""
    density: int = 2500
    """Material density in kg/m³."""
    acoustic: AcousticProperties | None = None
    """Acoustic properties for physics audio synthesis."""


# =============================================================================
# MATERIAL PRESETS (30+ artistic materials)
# =============================================================================
# Organized by category for artistic scene composition

MATERIAL_PRESETS: dict[str, MaterialPreset] = {
    # =========================================================================
    # METALS - Colony: Forge (e₂)
    # =========================================================================
    "chrome": MaterialPreset(
        surface_type=SurfaceType.METAL,
        color=(0.95, 0.95, 0.97),
        roughness=0.05,
        density=7800,
        acoustic=AcousticProperties((800, 2400, 4800), 0.92, 0.95, 0.9),
    ),
    "gold": MaterialPreset(
        surface_type=SurfaceType.METAL,
        color=(1.0, 0.85, 0.3),
        roughness=0.1,
        density=19300,
        acoustic=AcousticProperties((600, 1800, 3600), 0.88, 0.9, 0.85),
    ),
    "rose_gold": MaterialPreset(
        surface_type=SurfaceType.METAL,
        color=(0.9, 0.7, 0.65),
        roughness=0.12,
        density=15000,
        acoustic=AcousticProperties((650, 1950, 3900), 0.87, 0.88, 0.84),
    ),
    "copper": MaterialPreset(
        surface_type=SurfaceType.METAL,
        color=(0.95, 0.55, 0.35),
        roughness=0.15,
        density=8960,
        acoustic=AcousticProperties((700, 2100, 4200), 0.90, 0.92, 0.88),
    ),
    "bronze": MaterialPreset(
        surface_type=SurfaceType.METAL,
        color=(0.8, 0.5, 0.2),
        roughness=0.2,
        density=8800,
        acoustic=AcousticProperties((750, 2250, 4500), 0.89, 0.91, 0.87),
    ),
    "brass": MaterialPreset(
        surface_type=SurfaceType.METAL,
        color=(0.9, 0.75, 0.3),
        roughness=0.15,
        density=8500,
        acoustic=AcousticProperties((720, 2160, 4320), 0.88, 0.90, 0.86),
    ),
    "silver": MaterialPreset(
        surface_type=SurfaceType.METAL,
        color=(0.92, 0.92, 0.95),
        roughness=0.08,
        density=10490,
        acoustic=AcousticProperties((850, 2550, 5100), 0.93, 0.96, 0.91),
    ),
    "platinum": MaterialPreset(
        surface_type=SurfaceType.METAL,
        color=(0.85, 0.85, 0.88),
        roughness=0.1,
        density=21450,
        acoustic=AcousticProperties((780, 2340, 4680), 0.91, 0.94, 0.90),
    ),
    "brushed_steel": MaterialPreset(
        surface_type=SurfaceType.METAL,
        color=(0.6, 0.6, 0.65),
        roughness=0.25,
        density=7850,
        acoustic=AcousticProperties((800, 2400, 4800), 0.90, 0.93, 0.88),
    ),
    "dark_iron": MaterialPreset(
        surface_type=SurfaceType.METAL,
        color=(0.2, 0.2, 0.22),
        roughness=0.3,
        density=7874,
        acoustic=AcousticProperties((850, 2550, 5100), 0.88, 0.90, 0.85),
    ),
    "titanium": MaterialPreset(
        surface_type=SurfaceType.METAL,
        color=(0.5, 0.5, 0.55),
        roughness=0.18,
        density=4500,
        acoustic=AcousticProperties((900, 2700, 5400), 0.91, 0.94, 0.89),
    ),
    # =========================================================================
    # GLASS & TRANSPARENT - Colony: Crystal (e₇)
    # =========================================================================
    "glass": MaterialPreset(
        surface_type=SurfaceType.GLASS,
        color=(0.98, 0.98, 1.0),
        ior=1.52,
        density=2500,
        acoustic=AcousticProperties((2000, 5000, 8000), 0.85, 0.9, 0.85),
    ),
    "crystal_clear": MaterialPreset(
        surface_type=SurfaceType.GLASS,
        color=(1.0, 1.0, 1.0),
        ior=1.54,
        density=2700,
        acoustic=AcousticProperties((2200, 5500, 8800), 0.87, 0.92, 0.87),
    ),
    "diamond": MaterialPreset(
        surface_type=SurfaceType.GLASS,
        color=(0.97, 0.97, 1.0),
        ior=2.42,
        density=3520,
        acoustic=AcousticProperties((3000, 7000, 11000), 0.95, 0.98, 0.93),
    ),
    "sapphire": MaterialPreset(
        surface_type=SurfaceType.GLASS,
        color=(0.6, 0.7, 0.95),
        ior=1.77,
        density=3980,
        acoustic=AcousticProperties((2500, 6000, 9500), 0.92, 0.95, 0.90),
    ),
    "emerald": MaterialPreset(
        surface_type=SurfaceType.GLASS,
        color=(0.3, 0.75, 0.4),
        ior=1.58,
        density=2700,
        acoustic=AcousticProperties((2100, 5200, 8300), 0.86, 0.91, 0.86),
    ),
    "amber": MaterialPreset(
        surface_type=SurfaceType.GLASS,
        color=(1.0, 0.7, 0.2),
        ior=1.55,
        density=1100,
        acoustic=AcousticProperties((1500, 4000, 7000), 0.70, 0.75, 0.65),
    ),
    "ice": MaterialPreset(
        surface_type=SurfaceType.GLASS,
        color=(0.9, 0.95, 1.0),
        ior=1.31,
        density=917,
        acoustic=AcousticProperties((1800, 4500, 7500), 0.60, 0.70, 0.55),
    ),
    "obsidian": MaterialPreset(
        surface_type=SurfaceType.GLASS,
        color=(0.05, 0.05, 0.08),
        ior=1.50,
        density=2400,
        acoustic=AcousticProperties((2000, 5000, 8000), 0.85, 0.90, 0.85),
    ),
    # =========================================================================
    # FLUIDS - Colony: Flow (e₃)
    # =========================================================================
    "water": MaterialPreset(
        surface_type=SurfaceType.WATER,
        color=(0.7, 0.85, 0.95),
        ior=1.33,
        density=1000,
        acoustic=AcousticProperties((80, 200, 400), 0.2, 0.0, 0.15),
    ),
    "mercury": MaterialPreset(
        surface_type=SurfaceType.METAL,
        color=(0.8, 0.8, 0.85),
        roughness=0.02,
        density=13546,
        acoustic=AcousticProperties((100, 250, 500), 0.15, 0.1, 0.1),
    ),
    "honey": MaterialPreset(
        surface_type=SurfaceType.GLASS,
        color=(1.0, 0.75, 0.2),
        ior=1.50,
        density=1420,
        acoustic=AcousticProperties((60, 150, 300), 0.1, 0.0, 0.05),
    ),
    "oil": MaterialPreset(
        surface_type=SurfaceType.GLASS,
        color=(0.3, 0.25, 0.15),
        ior=1.47,
        density=920,
        acoustic=AcousticProperties((70, 180, 350), 0.12, 0.0, 0.08),
    ),
    # =========================================================================
    # NEON & EMISSIVE - Colony: Spark (e₁) / Beacon (e₅)
    # =========================================================================
    "neon_pink": MaterialPreset(
        surface_type=SurfaceType.EMISSION,
        color=(1.0, 0.2, 0.6),
        emissive=(200, 40, 120),
        acoustic=AcousticProperties((2000, 5000, 8000), 0.85, 0.9, 0.85),
    ),
    "neon_cyan": MaterialPreset(
        surface_type=SurfaceType.EMISSION,
        color=(0.2, 1.0, 1.0),
        emissive=(40, 200, 220),
        acoustic=AcousticProperties((2000, 5000, 8000), 0.85, 0.9, 0.85),
    ),
    "neon_purple": MaterialPreset(
        surface_type=SurfaceType.EMISSION,
        color=(0.6, 0.2, 1.0),
        emissive=(120, 40, 200),
        acoustic=AcousticProperties((2000, 5000, 8000), 0.85, 0.9, 0.85),
    ),
    "neon_orange": MaterialPreset(
        surface_type=SurfaceType.EMISSION,
        color=(1.0, 0.5, 0.1),
        emissive=(220, 110, 22),
        acoustic=AcousticProperties((2000, 5000, 8000), 0.85, 0.9, 0.85),
    ),
    "neon_green": MaterialPreset(
        surface_type=SurfaceType.EMISSION,
        color=(0.2, 1.0, 0.3),
        emissive=(40, 220, 60),
        acoustic=AcousticProperties((2000, 5000, 8000), 0.85, 0.9, 0.85),
    ),
    "hologram_blue": MaterialPreset(
        surface_type=SurfaceType.EMISSION,
        color=(0.3, 0.6, 1.0),
        emissive=(60, 120, 200),
        acoustic=AcousticProperties((2500, 6000, 9000), 0.80, 0.85, 0.80),
    ),
    "lava_glow": MaterialPreset(
        surface_type=SurfaceType.EMISSION,
        color=(1.0, 0.3, 0.0),
        emissive=(250, 75, 0),
        density=2600,
        acoustic=AcousticProperties((50, 150, 300), 0.1, 0.2, 0.1),
    ),
    "plasma": MaterialPreset(
        surface_type=SurfaceType.EMISSION,
        color=(0.8, 0.4, 1.0),
        emissive=(160, 80, 200),
        density=0,  # Plasma has no density
        acoustic=AcousticProperties((100, 300, 600), 0.05, 0.0, 0.05),
    ),
    # =========================================================================
    # STONE & EARTH - Colony: Grove (e₆)
    # =========================================================================
    "marble_white": MaterialPreset(
        surface_type=SurfaceType.DEFAULT,
        color=(0.95, 0.95, 0.93),
        roughness=0.15,
        density=2700,
        acoustic=AcousticProperties((300, 800, 1500), 0.5, 0.8, 0.45),
    ),
    "marble_black": MaterialPreset(
        surface_type=SurfaceType.DEFAULT,
        color=(0.1, 0.1, 0.12),
        roughness=0.12,
        density=2700,
        acoustic=AcousticProperties((300, 800, 1500), 0.5, 0.8, 0.45),
    ),
    "granite": MaterialPreset(
        surface_type=SurfaceType.DEFAULT,
        color=(0.4, 0.35, 0.35),
        roughness=0.35,
        density=2750,
        acoustic=AcousticProperties((250, 700, 1300), 0.45, 0.75, 0.40),
    ),
    "concrete": MaterialPreset(
        surface_type=SurfaceType.DEFAULT,
        color=(0.6, 0.6, 0.58),
        roughness=0.5,
        density=2400,
        acoustic=AcousticProperties((200, 600, 1100), 0.35, 0.65, 0.30),
    ),
    "clay": MaterialPreset(
        surface_type=SurfaceType.DEFAULT,
        color=(0.7, 0.45, 0.3),
        roughness=0.6,
        density=1700,
        acoustic=AcousticProperties((150, 450, 900), 0.25, 0.50, 0.20),
    ),
    # =========================================================================
    # SPECIAL & FLOORS - Colony: Nexus (e₄)
    # =========================================================================
    "floor_dark": MaterialPreset(
        surface_type=SurfaceType.DEFAULT,
        color=(0.05, 0.05, 0.08),
        roughness=0.2,
        density=2500,
        acoustic=AcousticProperties((100, 300, 600), 0.3, 0.7, 0.2),
    ),
    "floor_reflective": MaterialPreset(
        surface_type=SurfaceType.METAL,
        color=(0.1, 0.1, 0.12),
        roughness=0.08,
        density=2500,
        acoustic=AcousticProperties((100, 300, 600), 0.3, 0.7, 0.2),
    ),
    "rubber": MaterialPreset(
        surface_type=SurfaceType.DEFAULT,
        color=(0.15, 0.15, 0.15),
        roughness=0.7,
        density=1100,
        acoustic=AcousticProperties((50, 150, 300), 0.1, 0.2, 0.05),
    ),
    "leather": MaterialPreset(
        surface_type=SurfaceType.DEFAULT,
        color=(0.4, 0.25, 0.15),
        roughness=0.55,
        density=950,
        acoustic=AcousticProperties((100, 300, 600), 0.2, 0.4, 0.15),
    ),
    "velvet": MaterialPreset(
        surface_type=SurfaceType.DEFAULT,
        color=(0.3, 0.05, 0.15),
        roughness=0.9,
        density=400,
        acoustic=AcousticProperties((50, 150, 300), 0.05, 0.1, 0.03),
    ),
    "carbon_fiber": MaterialPreset(
        surface_type=SurfaceType.DEFAULT,
        color=(0.1, 0.1, 0.12),
        roughness=0.25,
        density=1600,
        acoustic=AcousticProperties((600, 1800, 3600), 0.75, 0.85, 0.70),
    ),
}


class MaterialLibrary:
    """Factory for creating Genesis surface objects from material presets.

    Provides a simple interface to instantiate Genesis rendering surfaces
    from the predefined material presets, with optional property overrides.

    The library supports all 40+ material presets defined in MATERIAL_PRESETS,
    organized by category (metals, glass, fluids, neon, stone, special).

    Example:
        >>> # Create a chrome surface
        >>> chrome = MaterialLibrary.create_surface("chrome")

        >>> # Create gold with increased roughness
        >>> from kagami_genesis.optics import GenesisSurfaceSpec
        >>> rough_gold = MaterialLibrary.create_surface(
        ...     "gold",
        ...     overrides=GenesisSurfaceSpec(roughness=0.3),
        ... )

        >>> # Unknown preset falls back to gray default
        >>> unknown = MaterialLibrary.create_surface("mythril")
    """

    @staticmethod
    def create_surface(
        preset_name: str,
        *,
        overrides: GenesisSurfaceSpec | None = None,
    ) -> Any:
        """Create a Genesis surface object from a preset name.

        Looks up the preset in MATERIAL_PRESETS and creates a Genesis-compatible
        surface object. If the preset is not found, creates a neutral gray
        default surface.

        Args:
            preset_name: Key from MATERIAL_PRESETS dictionary.
                Available presets include: chrome, gold, glass, water,
                neon_pink, marble_white, etc.
            overrides: Optional GenesisSurfaceSpec with property overrides.
                Non-None fields in overrides will replace preset values.
                If overrides.kind is None, the preset's surface kind is preserved.

        Returns:
            A Genesis surface object (gs.surfaces.*) ready for scene attachment.

        Raises:
            ImportError: If genesis-world package is not installed.

        Example:
            >>> # Standard preset
            >>> surface = MaterialLibrary.create_surface("diamond")
            >>> # With override
            >>> surface = MaterialLibrary.create_surface(
            ...     "chrome",
            ...     overrides=GenesisSurfaceSpec(roughness=0.15),
            ... )
        """
        import genesis as gs

        preset = MATERIAL_PRESETS.get(preset_name)
        if not preset:
            # Unknown preset: fall back to neutral gray
            base = GenesisSurfaceSpec(kind=SurfaceKind.DEFAULT, color=(0.5, 0.5, 0.5))
            spec = _merge_surface_specs(base, overrides) if overrides is not None else base
            return spec.to_gs_surface(gs)

        base = _surface_spec_from_preset(preset)
        spec = _merge_surface_specs(base, overrides) if overrides is not None else base
        return spec.to_gs_surface(gs)


def _surface_spec_from_preset(preset: MaterialPreset) -> GenesisSurfaceSpec:
    """Convert a MaterialPreset to a GenesisSurfaceSpec.

    Maps the preset's surface type to the appropriate SurfaceKind and
    extracts the relevant rendering parameters.

    Args:
        preset: The material preset to convert.

    Returns:
        A GenesisSurfaceSpec with properties matching the preset.
    """
    if preset.surface_type == SurfaceType.METAL:
        return GenesisSurfaceSpec(
            kind=SurfaceKind.METAL,
            color=preset.color,
            roughness=preset.roughness,
        )
    if preset.surface_type == SurfaceType.GLASS:
        return GenesisSurfaceSpec(
            kind=SurfaceKind.GLASS,
            color=preset.color,
            roughness=preset.roughness,
            ior=preset.ior,
        )
    if preset.surface_type == SurfaceType.EMISSION:
        return GenesisSurfaceSpec(
            kind=SurfaceKind.EMISSION,
            emissive=preset.emissive,
        )
    if preset.surface_type == SurfaceType.WATER:
        return GenesisSurfaceSpec(
            kind=SurfaceKind.WATER,
            color=preset.color,
            roughness=preset.roughness,
            ior=preset.ior,
        )
    # DEFAULT surface type
    return GenesisSurfaceSpec(
        kind=SurfaceKind.DEFAULT,
        color=preset.color,
        roughness=preset.roughness,
    )


def _merge_surface_specs(
    base: GenesisSurfaceSpec,
    override: GenesisSurfaceSpec,
) -> GenesisSurfaceSpec:
    """Merge two surface specs, with override values taking precedence.

    Combines the fields from base and override specs. For each field,
    the override value is used if it is not None, otherwise the base
    value is preserved.

    Special handling for 'kind': Only overrides if explicitly set (not None),
    allowing presets to maintain their surface type unless explicitly changed.

    Args:
        base: The base surface spec providing default values.
        override: The override spec with values to apply on top.

    Returns:
        A new GenesisSurfaceSpec with merged properties.

    Example:
        >>> base = GenesisSurfaceSpec(kind=SurfaceKind.METAL, roughness=0.1)
        >>> override = GenesisSurfaceSpec(roughness=0.3)  # kind=None
        >>> result = _merge_surface_specs(base, override)
        >>> result.kind  # Preserved from base
        SurfaceKind.METAL
        >>> result.roughness  # From override
        0.3
    """
    merged: dict[str, Any] = dict(base.__dict__)
    for k, v in override.__dict__.items():
        if k == "kind":
            # Only override kind if explicitly specified
            if v is not None:
                merged["kind"] = v
            continue
        if v is not None:
            merged[k] = v
    return GenesisSurfaceSpec(**merged)


__all__ = [
    "MATERIAL_PRESETS",
    "AcousticProperties",
    "MaterialLibrary",
    "MaterialPreset",
    "SurfaceType",
]
