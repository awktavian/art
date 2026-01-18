"""Orchestra Presets — Ready-to-Use Orchestral Configurations.

Pre-configured settings for common orchestral styles and use cases.

Example:
    from kagami.core.effectors.orchestra_presets import (
        get_preset,
        PRESETS,
        apply_preset,
    )

    # Get a preset
    preset = get_preset("film_score")

    # Apply to orchestra
    orchestra = await get_orchestra()
    apply_preset(orchestra, "baroque")

Colony: Forge (e₂)
Created: January 1, 2026
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from kagami.core.effectors.expression_engine import ExpressionStyle
from kagami.core.effectors.orchestra import Config, RenderMode

if TYPE_CHECKING:
    from kagami.core.effectors.orchestra import Orchestra


# =============================================================================
# Preset Definition
# =============================================================================


@dataclass
class OrchestraPreset:
    """Complete orchestra configuration preset."""

    name: str
    description: str

    # Orchestra config
    render_mode: RenderMode = RenderMode.AUTO
    prefer_bbc: bool = True
    tempo: int = 100
    gain: float = 0.55
    track_norm: float = 0.42
    master_norm: float = 0.82
    lfe_level: float = 0.20

    # Expression style
    expression_style: ExpressionStyle = ExpressionStyle.ROMANTIC

    # Instrument selection (for multi-track)
    use_strings: bool = True
    use_brass: bool = True
    use_woodwinds: bool = True
    use_percussion: bool = True

    # Spatial settings
    render_spatial: bool = True
    room_reverb: float = 0.3

    # Tags for discovery
    tags: list[str] = field(default_factory=list)


# =============================================================================
# Preset Library
# =============================================================================

PRESETS: dict[str, OrchestraPreset] = {
    # === Film/Cinematic ===
    "film_score": OrchestraPreset(
        name="Film Score",
        description="Dramatic cinematic orchestration with sweeping dynamics",
        render_mode=RenderMode.BBC,
        prefer_bbc=True,
        tempo=100,
        gain=0.6,
        track_norm=0.45,
        master_norm=0.85,
        lfe_level=0.25,
        expression_style=ExpressionStyle.FILM_SCORE,
        room_reverb=0.35,
        tags=["cinematic", "dramatic", "epic", "trailer"],
    ),
    "epic_trailer": OrchestraPreset(
        name="Epic Trailer",
        description="Massive sound for trailers and epic moments",
        render_mode=RenderMode.BBC,
        prefer_bbc=True,
        tempo=120,
        gain=0.7,
        track_norm=0.5,
        master_norm=0.9,
        lfe_level=0.35,
        expression_style=ExpressionStyle.FILM_SCORE,
        room_reverb=0.4,
        tags=["epic", "trailer", "massive", "powerful"],
    ),
    "emotional_underscore": OrchestraPreset(
        name="Emotional Underscore",
        description="Subtle, emotional background scoring",
        render_mode=RenderMode.AUTO,
        prefer_bbc=True,
        tempo=70,
        gain=0.4,
        track_norm=0.35,
        master_norm=0.7,
        lfe_level=0.1,
        expression_style=ExpressionStyle.ROMANTIC,
        room_reverb=0.45,
        use_percussion=False,
        tags=["emotional", "subtle", "underscore", "sad"],
    ),
    # === Classical Periods ===
    "baroque": OrchestraPreset(
        name="Baroque",
        description="Bach/Handel style with terraced dynamics",
        render_mode=RenderMode.AUTO,
        prefer_bbc=True,
        tempo=110,
        gain=0.5,
        track_norm=0.4,
        master_norm=0.75,
        lfe_level=0.08,
        expression_style=ExpressionStyle.BAROQUE,
        room_reverb=0.2,
        use_percussion=False,
        tags=["baroque", "bach", "handel", "classical", "period"],
    ),
    "classical": OrchestraPreset(
        name="Classical",
        description="Mozart/Haydn style with balanced dynamics",
        render_mode=RenderMode.AUTO,
        prefer_bbc=True,
        tempo=100,
        gain=0.5,
        track_norm=0.4,
        master_norm=0.78,
        lfe_level=0.1,
        expression_style=ExpressionStyle.CLASSICAL,
        room_reverb=0.25,
        tags=["classical", "mozart", "haydn", "period", "elegant"],
    ),
    "romantic": OrchestraPreset(
        name="Romantic",
        description="Brahms/Tchaikovsky style with expressive dynamics",
        render_mode=RenderMode.BBC,
        prefer_bbc=True,
        tempo=90,
        gain=0.55,
        track_norm=0.42,
        master_norm=0.82,
        lfe_level=0.18,
        expression_style=ExpressionStyle.ROMANTIC,
        room_reverb=0.35,
        tags=["romantic", "brahms", "tchaikovsky", "expressive", "sweeping"],
    ),
    "impressionist": OrchestraPreset(
        name="Impressionist",
        description="Debussy/Ravel style with colorful textures",
        render_mode=RenderMode.AUTO,
        prefer_bbc=True,
        tempo=80,
        gain=0.45,
        track_norm=0.38,
        master_norm=0.75,
        lfe_level=0.12,
        expression_style=ExpressionStyle.ROMANTIC,
        room_reverb=0.5,
        tags=["impressionist", "debussy", "ravel", "colorful", "ethereal"],
    ),
    # === Modern Styles ===
    "minimalist": OrchestraPreset(
        name="Minimalist",
        description="Reich/Glass style with subtle dynamics",
        render_mode=RenderMode.AUTO,
        prefer_bbc=True,
        tempo=120,
        gain=0.4,
        track_norm=0.35,
        master_norm=0.7,
        lfe_level=0.05,
        expression_style=ExpressionStyle.MINIMALIST,
        room_reverb=0.2,
        use_brass=False,
        tags=["minimalist", "reich", "glass", "meditative", "repetitive"],
    ),
    "contemporary": OrchestraPreset(
        name="Contemporary",
        description="Modern orchestral with varied textures",
        render_mode=RenderMode.BBC,
        prefer_bbc=True,
        tempo=95,
        gain=0.55,
        track_norm=0.42,
        master_norm=0.8,
        lfe_level=0.2,
        expression_style=ExpressionStyle.MODERN,
        room_reverb=0.3,
        tags=["contemporary", "modern", "varied", "experimental"],
    ),
    # === Specific Ensembles ===
    "string_quartet": OrchestraPreset(
        name="String Quartet",
        description="Intimate chamber strings",
        render_mode=RenderMode.AUTO,
        prefer_bbc=True,
        tempo=100,
        gain=0.5,
        track_norm=0.4,
        master_norm=0.75,
        lfe_level=0.05,
        expression_style=ExpressionStyle.CLASSICAL,
        room_reverb=0.15,
        use_strings=True,
        use_brass=False,
        use_woodwinds=False,
        use_percussion=False,
        tags=["chamber", "intimate", "quartet", "strings"],
    ),
    "brass_fanfare": OrchestraPreset(
        name="Brass Fanfare",
        description="Powerful brass with timpani",
        render_mode=RenderMode.AUTO,
        prefer_bbc=True,
        tempo=120,
        gain=0.65,
        track_norm=0.48,
        master_norm=0.88,
        lfe_level=0.28,
        expression_style=ExpressionStyle.FILM_SCORE,
        room_reverb=0.35,
        use_strings=False,
        use_brass=True,
        use_woodwinds=False,
        use_percussion=True,
        tags=["fanfare", "brass", "powerful", "ceremonial"],
    ),
    "woodwind_ensemble": OrchestraPreset(
        name="Woodwind Ensemble",
        description="Pastoral woodwind chamber music",
        render_mode=RenderMode.AUTO,
        prefer_bbc=True,
        tempo=90,
        gain=0.45,
        track_norm=0.38,
        master_norm=0.72,
        lfe_level=0.02,
        expression_style=ExpressionStyle.CLASSICAL,
        room_reverb=0.2,
        use_strings=False,
        use_brass=False,
        use_woodwinds=True,
        use_percussion=False,
        tags=["chamber", "woodwinds", "pastoral", "light"],
    ),
    # === Quality Tiers ===
    "standard": OrchestraPreset(
        name="Standard",
        description="Standard BBC Symphony Orchestra rendering",
        render_mode=RenderMode.BBC,
        prefer_bbc=True,
        tempo=100,
        gain=0.55,
        track_norm=0.42,
        master_norm=0.82,
        lfe_level=0.2,
        expression_style=ExpressionStyle.ROMANTIC,
        room_reverb=0.3,
        tags=["standard", "default", "bbc"],
    ),
    "high_quality": OrchestraPreset(
        name="High Quality",
        description="Maximum quality multi-track BBC rendering with stems",
        render_mode=RenderMode.BBC,
        prefer_bbc=True,
        tempo=100,
        gain=0.55,
        track_norm=0.42,
        master_norm=0.82,
        lfe_level=0.2,
        expression_style=ExpressionStyle.ROMANTIC,
        room_reverb=0.35,
        tags=["quality", "best", "bbc", "premium", "multitrack"],
    ),
}


# =============================================================================
# API Functions
# =============================================================================


def get_preset(name: str) -> OrchestraPreset | None:
    """Get preset by name.

    Args:
        name: Preset name (case-insensitive)

    Returns:
        OrchestraPreset or None if not found
    """
    return PRESETS.get(name.lower().replace(" ", "_"))


def list_presets(tag: str | None = None) -> list[str]:
    """List available preset names.

    Args:
        tag: Optional tag to filter by

    Returns:
        List of preset names
    """
    if tag is None:
        return list(PRESETS.keys())

    return [
        name for name, preset in PRESETS.items() if tag.lower() in [t.lower() for t in preset.tags]
    ]


def get_preset_config(name: str) -> Config | None:
    """Get Orchestra Config from preset.

    Args:
        name: Preset name

    Returns:
        Config object or None
    """
    preset = get_preset(name)
    if preset is None:
        return None

    return Config(
        gain=preset.gain,
        track_norm=preset.track_norm,
        master_norm=preset.master_norm,
        lfe_level=preset.lfe_level,
        prefer_bbc=preset.prefer_bbc,
        render_mode=preset.render_mode,
        tempo=preset.tempo,
    )


def apply_preset(orchestra: Orchestra, name: str) -> bool:
    """Apply preset to Orchestra instance.

    Args:
        orchestra: Orchestra instance to configure
        name: Preset name

    Returns:
        True if applied, False if preset not found
    """
    config = get_preset_config(name)
    if config is None:
        return False

    orchestra.cfg = config
    return True


def describe_preset(name: str) -> str:
    """Get human-readable preset description.

    Args:
        name: Preset name

    Returns:
        Description string
    """
    preset = get_preset(name)
    if preset is None:
        return f"Preset '{name}' not found"

    instruments = []
    if preset.use_strings:
        instruments.append("strings")
    if preset.use_brass:
        instruments.append("brass")
    if preset.use_woodwinds:
        instruments.append("woodwinds")
    if preset.use_percussion:
        instruments.append("percussion")

    return f"""
{preset.name}
{"=" * len(preset.name)}
{preset.description}

Settings:
- Render mode: {preset.render_mode.value}
- Tempo: {preset.tempo} BPM
- Expression: {preset.expression_style.value}
- Instruments: {", ".join(instruments)}
- Room reverb: {preset.room_reverb:.0%}
- LFE level: {preset.lfe_level:.0%}

Tags: {", ".join(preset.tags)}
""".strip()


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "PRESETS",
    "OrchestraPreset",
    "apply_preset",
    "describe_preset",
    "get_preset",
    "get_preset_config",
    "list_presets",
]
