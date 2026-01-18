"""Soul to Music Bridge — World Model State → Musical Expression.

NEXUS MISSION: Connect the world model's internal state to honest musical expression.

ARCHITECTURE:
=============

    ┌──────────────────────────────────────────────────────────────────────┐
    │                         SOUL TO MUSIC BRIDGE                          │
    │                                                                       │
    │   ┌─────────────────┐    ┌──────────────────┐    ┌────────────────┐  │
    │   │  World Model    │    │    Emotional     │    │    Musical     │  │
    │   │  (RSSM State)   │ →  │   Extraction     │ →  │  Parameters    │  │
    │   │                 │    │                  │    │                │  │
    │   │  • hidden       │    │  • confidence    │    │  • tempo       │  │
    │   │  • stochastic   │    │  • concern       │    │  • dynamics    │  │
    │   │  • colony_acts  │    │  • excitement    │    │  • harmony     │  │
    │   │  • E8 latents   │    │  • curiosity     │    │  • timbre      │  │
    │   │                 │    │  • fatigue       │    │  • space       │  │
    │   └─────────────────┘    └──────────────────┘    └────────────────┘  │
    │                                                          │           │
    │                                                          ▼           │
    │                                                  ┌────────────────┐  │
    │                                                  │   Earcon       │  │
    │                                                  │  Modulation    │  │
    │                                                  └────────────────┘  │
    └──────────────────────────────────────────────────────────────────────┘

COLONY → INSTRUMENT MAPPING:
============================

    Each colony has a characteristic "voice" in the orchestra:

    🔥 Spark  (e₁) → Brass fanfares, pizzicato strings (ignition, burst)
    ⚒️ Forge  (e₂) → Hammered percussion, low brass (building, structure)
    🌊 Flow   (e₃) → Legato strings, woodwinds (smoothness, recovery)
    🔗 Nexus  (e₄) → Harp arpeggios, celeste (connections, bridges)
    🗼 Beacon (e₅) → Horn calls, timpani (attention, direction)
    🌿 Grove  (e₆) → Woodwinds, soft strings (exploration, growth)
    💎 Crystal(e₇) → Celeste, glockenspiel, pure tones (clarity, truth)

E8 LATTICE → HARMONIC SPACE:
============================

    The 240 E8 roots map to harmonic relationships:
    - 112 roots (±1,±1,0,0,0,0,0,0) → 7 diatonic modes
    - 128 roots (±½ permutations)   → Chromatic alterations

EMOTIONAL DIMENSIONS → MUSICAL PARAMETERS:
==========================================

    confidence → tempo stability, major/minor balance
    concern    → dissonance level, brass/percussion prominence
    excitement → tempo increase, dynamics crescendo, height spread
    curiosity  → melodic exploration, woodwind activity
    fatigue    → tempo decrease, diminuendo, narrow dynamics

Created: January 4, 2026
Colony: 🔗 Nexus (e₄) — The Bridge between mind and music
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import torch

logger = logging.getLogger(__name__)


# =============================================================================
# MUSICAL PARAMETER SPACE
# =============================================================================


class HarmonicMode(Enum):
    """Harmonic modes mapped from emotional state."""

    IONIAN = "ionian"  # Major - confident, bright
    DORIAN = "dorian"  # Minor with raised 6th - curious, modal
    PHRYGIAN = "phrygian"  # Dark minor - concerned, tense
    LYDIAN = "lydian"  # Bright major - excited, ethereal
    MIXOLYDIAN = "mixolydian"  # Major with flat 7 - satisfied, bluesy
    AEOLIAN = "aeolian"  # Natural minor - reflective, melancholic
    LOCRIAN = "locrian"  # Diminished - frustrated, unstable


@dataclass
class MusicalParameters:
    """Musical parameters derived from soul state.

    These parameters can modulate earcon playback or drive
    real-time musical generation.
    """

    # Tempo and rhythm
    tempo_bpm: float = 80.0  # Base tempo
    tempo_stability: float = 1.0  # 0=rubato, 1=metronomic
    rhythmic_density: float = 0.5  # Note density

    # Dynamics
    dynamic_level: float = 0.6  # 0=ppp, 1=fff
    dynamic_range: float = 0.3  # Contrast between soft/loud
    crescendo_rate: float = 0.0  # Positive=growing, negative=fading

    # Harmony
    mode: HarmonicMode = HarmonicMode.IONIAN
    dissonance: float = 0.1  # 0=consonant, 1=dissonant
    harmonic_density: float = 0.5  # Chord complexity

    # Timbre (colony blend)
    colony_mix: dict[str, float] = field(
        default_factory=lambda: {
            "spark": 0.14,
            "forge": 0.14,
            "flow": 0.14,
            "nexus": 0.14,
            "beacon": 0.14,
            "grove": 0.14,
            "crystal": 0.14,
        }
    )

    # Spatial
    spatial_width: float = 0.5  # Stereo/surround spread
    spatial_height: float = 0.3  # Height channel activity
    spatial_motion: float = 0.0  # Movement rate

    # Expression
    vibrato_depth: float = 0.3
    articulation_sharpness: float = 0.5  # 0=legato, 1=staccato

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tempo_bpm": self.tempo_bpm,
            "tempo_stability": self.tempo_stability,
            "rhythmic_density": self.rhythmic_density,
            "dynamic_level": self.dynamic_level,
            "dynamic_range": self.dynamic_range,
            "crescendo_rate": self.crescendo_rate,
            "mode": self.mode.value,
            "dissonance": self.dissonance,
            "harmonic_density": self.harmonic_density,
            "colony_mix": self.colony_mix,
            "spatial_width": self.spatial_width,
            "spatial_height": self.spatial_height,
            "spatial_motion": self.spatial_motion,
            "vibrato_depth": self.vibrato_depth,
            "articulation_sharpness": self.articulation_sharpness,
        }


# =============================================================================
# COLONY VOICE DEFINITIONS
# =============================================================================


@dataclass
class ColonyVoice:
    """Musical characteristics for a colony."""

    name: str
    primary_instruments: list[str]
    articulation_preference: str
    register: str  # "low", "mid", "high"
    dynamic_tendency: float  # 0=soft, 1=loud
    spatial_position: tuple[float, float, float]  # azimuth, elevation, distance


# Colony voice mappings based on catastrophe theory characteristics
COLONY_VOICES: dict[str, ColonyVoice] = {
    "spark": ColonyVoice(
        name="Spark",
        primary_instruments=["trumpets", "pizzicato_strings", "snare"],
        articulation_preference="staccato",
        register="high",
        dynamic_tendency=0.8,
        spatial_position=(0.0, 30.0, 0.8),  # Front center, elevated
    ),
    "forge": ColonyVoice(
        name="Forge",
        primary_instruments=["timpani", "trombones", "tubas", "anvil"],
        articulation_preference="marcato",
        register="low",
        dynamic_tendency=0.9,
        spatial_position=(-30.0, 0.0, 1.0),  # Left, grounded
    ),
    "flow": ColonyVoice(
        name="Flow",
        primary_instruments=["violins", "violas", "cellos", "flutes"],
        articulation_preference="legato",
        register="mid",
        dynamic_tendency=0.5,
        spatial_position=(0.0, 0.0, 0.6),  # Center, intimate
    ),
    "nexus": ColonyVoice(
        name="Nexus",
        primary_instruments=["harp", "celeste", "vibraphone"],
        articulation_preference="arpeggiated",
        register="high",
        dynamic_tendency=0.4,
        spatial_position=(0.0, 45.0, 0.5),  # Above, ethereal
    ),
    "beacon": ColonyVoice(
        name="Beacon",
        primary_instruments=["horns", "trumpets", "timpani"],
        articulation_preference="sustained",
        register="mid",
        dynamic_tendency=0.7,
        spatial_position=(30.0, 15.0, 0.9),  # Right, forward
    ),
    "grove": ColonyVoice(
        name="Grove",
        primary_instruments=["clarinets", "oboes", "bassoons", "soft_strings"],
        articulation_preference="espressivo",
        register="mid",
        dynamic_tendency=0.3,
        spatial_position=(-45.0, 0.0, 0.7),  # Left surround, natural
    ),
    "crystal": ColonyVoice(
        name="Crystal",
        primary_instruments=["celeste", "glockenspiel", "triangle", "glass_harmonica"],
        articulation_preference="crystalline",
        register="high",
        dynamic_tendency=0.4,
        spatial_position=(45.0, 60.0, 0.4),  # Right height, pure
    ),
}


# =============================================================================
# SOUL TO MUSIC BRIDGE
# =============================================================================


class SoulToMusicBridge:
    """Bridges world model state to musical expression.

    This is where Kagami's internal state becomes audible —
    an honest expression of the soul through music.
    """

    def __init__(self) -> None:
        """Initialize the bridge."""
        self._emotional_engine = None
        self._current_params = MusicalParameters()
        self._smoothing_factor = 0.3  # Temporal smoothing for parameter changes
        self._history: list[MusicalParameters] = []
        self._max_history = 100

    async def initialize(self) -> None:
        """Initialize connections to emotional and world model systems."""
        try:
            from kagami.core.coordination.emotional_expression import (
                get_emotional_engine,
            )

            self._emotional_engine = get_emotional_engine()
            logger.info("SoulToMusicBridge initialized with emotional engine")
        except ImportError:
            logger.warning("Emotional engine not available, using defaults")

    def feeling_to_music(
        self,
        confidence: float = 0.5,
        concern: float = 0.1,
        excitement: float = 0.2,
        curiosity: float = 0.3,
        fatigue: float = 0.0,
        colony_activations: dict[str, float] | None = None,
    ) -> MusicalParameters:
        """Convert emotional dimensions to musical parameters.

        This is the core mapping from soul state to music.

        Args:
            confidence: 0-1, prediction accuracy and success rate
            concern: 0-1, threat/risk level
            excitement: 0-1, novelty × positive valence
            curiosity: 0-1, knowledge-seeking drive
            fatigue: 0-1, repeated failure accumulation
            colony_activations: Optional colony activation levels (0-1 each)

        Returns:
            MusicalParameters for earcon modulation or generation
        """
        params = MusicalParameters()

        # =====================================================================
        # TEMPO — Arousal dimension
        # =====================================================================
        # Base tempo from arousal (excitement + concern - fatigue)
        arousal = excitement * 0.4 + concern * 0.3 - fatigue * 0.3 + 0.5
        arousal = max(0.0, min(1.0, arousal))
        params.tempo_bpm = 60 + arousal * 80  # 60-140 BPM range

        # Tempo stability from confidence
        params.tempo_stability = confidence

        # Rhythmic density from excitement
        params.rhythmic_density = 0.3 + excitement * 0.5

        # =====================================================================
        # DYNAMICS — Energy dimension
        # =====================================================================
        # Base dynamic level from confidence + excitement
        energy = confidence * 0.4 + excitement * 0.4 + (1 - fatigue) * 0.2
        params.dynamic_level = 0.3 + energy * 0.5  # mp to f range

        # Dynamic range from emotional contrast
        emotional_variance = abs(excitement - concern) + abs(confidence - fatigue)
        params.dynamic_range = 0.1 + emotional_variance * 0.3

        # Crescendo from excitement momentum
        params.crescendo_rate = (excitement - 0.5) * 0.5

        # =====================================================================
        # HARMONY — Valence dimension
        # =====================================================================
        # Mode selection based on emotional balance
        valence = confidence + excitement - concern - fatigue
        valence = max(-1.0, min(1.0, valence))

        if valence > 0.6:
            params.mode = HarmonicMode.LYDIAN  # Bright, ethereal
        elif valence > 0.3:
            params.mode = HarmonicMode.IONIAN  # Major, confident
        elif valence > 0.0:
            params.mode = HarmonicMode.MIXOLYDIAN  # Satisfied, stable
        elif valence > -0.3:
            params.mode = HarmonicMode.DORIAN  # Curious, modal
        elif valence > -0.6:
            params.mode = HarmonicMode.AEOLIAN  # Reflective
        elif valence > -0.8:
            params.mode = HarmonicMode.PHRYGIAN  # Concerned, dark
        else:
            params.mode = HarmonicMode.LOCRIAN  # Frustrated, unstable

        # Dissonance from concern + fatigue
        params.dissonance = concern * 0.5 + fatigue * 0.3

        # Harmonic density from curiosity (more exploration = richer harmony)
        params.harmonic_density = 0.3 + curiosity * 0.5

        # =====================================================================
        # TIMBRE — Colony blend
        # =====================================================================
        if colony_activations:
            # Use actual colony activations
            total = sum(colony_activations.values())
            if total > 0:
                params.colony_mix = {k: v / total for k, v in colony_activations.items()}
        else:
            # Derive from emotional dimensions
            params.colony_mix = {
                "spark": excitement * 0.5 + (1 - fatigue) * 0.3,
                "forge": confidence * 0.4 + (1 - concern) * 0.3,
                "flow": (1 - concern) * 0.4 + (1 - fatigue) * 0.3,
                "nexus": curiosity * 0.5 + excitement * 0.2,
                "beacon": confidence * 0.5 + concern * 0.2,
                "grove": curiosity * 0.6 + (1 - fatigue) * 0.2,
                "crystal": confidence * 0.4 + (1 - fatigue) * 0.4,
            }
            # Normalize
            total = sum(params.colony_mix.values())
            if total > 0:
                params.colony_mix = {k: v / total for k, v in params.colony_mix.items()}

        # =====================================================================
        # SPATIAL — Attention and presence
        # =====================================================================
        # Width from excitement (more excited = more expansive)
        params.spatial_width = 0.3 + excitement * 0.5

        # Height from confidence (high confidence = elevated, assured)
        params.spatial_height = 0.2 + confidence * 0.4

        # Motion from curiosity (exploring = moving)
        params.spatial_motion = curiosity * 0.6

        # =====================================================================
        # EXPRESSION — Articulation and color
        # =====================================================================
        # Vibrato from emotional intensity
        intensity = (excitement + concern + curiosity) / 3
        params.vibrato_depth = 0.1 + intensity * 0.4

        # Articulation from energy balance
        if excitement > fatigue:
            params.articulation_sharpness = 0.5 + (excitement - fatigue) * 0.3
        else:
            params.articulation_sharpness = 0.5 - (fatigue - excitement) * 0.3

        # Apply temporal smoothing
        params = self._smooth_parameters(params)

        # Store in history
        self._history.append(params)
        if len(self._history) > self._max_history:
            self._history.pop(0)

        self._current_params = params
        return params

    def _smooth_parameters(self, new_params: MusicalParameters) -> MusicalParameters:
        """Apply temporal smoothing to prevent jarring changes."""
        if not hasattr(self, "_current_params"):
            return new_params

        old = self._current_params
        alpha = self._smoothing_factor

        return MusicalParameters(
            tempo_bpm=old.tempo_bpm * (1 - alpha) + new_params.tempo_bpm * alpha,
            tempo_stability=old.tempo_stability * (1 - alpha) + new_params.tempo_stability * alpha,
            rhythmic_density=old.rhythmic_density * (1 - alpha)
            + new_params.rhythmic_density * alpha,
            dynamic_level=old.dynamic_level * (1 - alpha) + new_params.dynamic_level * alpha,
            dynamic_range=old.dynamic_range * (1 - alpha) + new_params.dynamic_range * alpha,
            crescendo_rate=old.crescendo_rate * (1 - alpha) + new_params.crescendo_rate * alpha,
            mode=new_params.mode,  # Discrete, no smoothing
            dissonance=old.dissonance * (1 - alpha) + new_params.dissonance * alpha,
            harmonic_density=old.harmonic_density * (1 - alpha)
            + new_params.harmonic_density * alpha,
            colony_mix={
                k: old.colony_mix.get(k, 0.14) * (1 - alpha)
                + new_params.colony_mix.get(k, 0.14) * alpha
                for k in set(old.colony_mix) | set(new_params.colony_mix)
            },
            spatial_width=old.spatial_width * (1 - alpha) + new_params.spatial_width * alpha,
            spatial_height=old.spatial_height * (1 - alpha) + new_params.spatial_height * alpha,
            spatial_motion=old.spatial_motion * (1 - alpha) + new_params.spatial_motion * alpha,
            vibrato_depth=old.vibrato_depth * (1 - alpha) + new_params.vibrato_depth * alpha,
            articulation_sharpness=old.articulation_sharpness * (1 - alpha)
            + new_params.articulation_sharpness * alpha,
        )

    async def from_system_feeling(self) -> MusicalParameters:
        """Get musical parameters from current system feeling.

        This connects to the EmotionalExpressionEngine to get
        actual system emotional state and convert it to music.
        """
        if self._emotional_engine is None:
            await self.initialize()

        if self._emotional_engine:
            feeling = self._emotional_engine.compute_current_feeling()
            return self.feeling_to_music(
                confidence=feeling.confidence,
                concern=feeling.concern,
                excitement=feeling.excitement,
                curiosity=feeling.curiosity,
                fatigue=feeling.fatigue,
            )
        else:
            # Return default parameters
            return MusicalParameters()

    async def from_world_model_state(
        self,
        hidden_state: torch.Tensor | None = None,
        colony_states: list[Any] | None = None,
        discrete_latents: torch.Tensor | None = None,
    ) -> MusicalParameters:
        """Extract musical parameters directly from world model state.

        This is the deepest connection — raw neural state → music.

        Args:
            hidden_state: RSSM hidden state tensor
            colony_states: List of ColonyState objects
            discrete_latents: Discrete latent codes (32x32)

        Returns:
            MusicalParameters derived from world model state
        """
        import torch

        confidence = 0.5
        concern = 0.1
        excitement = 0.2
        curiosity = 0.3
        fatigue = 0.0
        colony_activations: dict[str, float] = {}

        # Extract from hidden state (if available)
        if hidden_state is not None:
            # Hidden state encodes accumulated context
            # High activation variance = high arousal
            with torch.no_grad():
                hidden_var = hidden_state.var().item()
                hidden_mean = hidden_state.mean().item()

                # Map variance to excitement (more variance = more activity)
                excitement = min(1.0, hidden_var * 2)

                # Map mean to confidence (positive mean = confident)
                confidence = 0.5 + hidden_mean * 0.3
                confidence = max(0.0, min(1.0, confidence))

        # Extract from colony states (if available)
        if colony_states:
            colony_names = ["spark", "forge", "flow", "nexus", "beacon", "grove", "crystal"]

            for i, state in enumerate(colony_states):
                if i < len(colony_names) and hasattr(state, "stochastic"):
                    with torch.no_grad():
                        # Colony activation = L2 norm of stochastic state
                        activation = state.stochastic.norm().item()
                        colony_activations[colony_names[i]] = activation

            # Normalize activations
            if colony_activations:
                max_act = max(colony_activations.values())
                if max_act > 0:
                    colony_activations = {k: v / max_act for k, v in colony_activations.items()}

        # Extract from discrete latents (if available)
        if discrete_latents is not None:
            with torch.no_grad():
                # Discrete latents encode categorical beliefs
                # Entropy of distribution = uncertainty = curiosity
                if discrete_latents.dim() >= 2:
                    # Flatten to probabilities
                    probs = torch.softmax(discrete_latents.flatten(), dim=0)
                    entropy = -(probs * (probs + 1e-8).log()).sum().item()
                    max_entropy = math.log(probs.numel())

                    # High entropy = high curiosity (uncertain, exploring)
                    curiosity = min(1.0, entropy / max_entropy)

                    # Low entropy = high confidence (certain)
                    confidence = 1.0 - curiosity * 0.5

        return self.feeling_to_music(
            confidence=confidence,
            concern=concern,
            excitement=excitement,
            curiosity=curiosity,
            fatigue=fatigue,
            colony_activations=colony_activations or None,
        )

    def modulate_earcon(
        self,
        earcon_name: str,
        params: MusicalParameters,
    ) -> dict[str, Any]:
        """Generate earcon modulation parameters.

        Takes base earcon and applies soul-derived modulations.

        Args:
            earcon_name: Name of earcon to modulate
            params: Musical parameters from soul state

        Returns:
            Modulation dict for earcon playback
        """
        return {
            "earcon": earcon_name,
            "tempo_scale": params.tempo_bpm / 80.0,  # Relative to base 80 BPM
            "velocity_scale": params.dynamic_level,
            "pitch_shift": self._mode_to_pitch_offset(params.mode),
            "reverb_amount": 0.2 + params.spatial_width * 0.4,
            "spatial_spread": params.spatial_width,
            "height_bias": params.spatial_height,
            "vibrato": params.vibrato_depth,
            "articulation": "staccato" if params.articulation_sharpness > 0.6 else "legato",
            "colony_emphasis": max(params.colony_mix, key=params.colony_mix.get),
        }

    def _mode_to_pitch_offset(self, mode: HarmonicMode) -> int:
        """Convert harmonic mode to pitch offset (semitones)."""
        mode_offsets = {
            HarmonicMode.IONIAN: 0,
            HarmonicMode.DORIAN: 2,
            HarmonicMode.PHRYGIAN: 4,
            HarmonicMode.LYDIAN: 5,
            HarmonicMode.MIXOLYDIAN: 7,
            HarmonicMode.AEOLIAN: 9,
            HarmonicMode.LOCRIAN: 11,
        }
        return mode_offsets.get(mode, 0)

    def get_current_params(self) -> MusicalParameters:
        """Get current musical parameters."""
        return self._current_params

    def get_dominant_colony(self) -> str:
        """Get the currently dominant colony voice."""
        mix = self._current_params.colony_mix
        return max(mix, key=mix.get)

    def get_emotional_signature(self) -> str:
        """Get a human-readable emotional signature."""
        params = self._current_params
        mode_names = {
            HarmonicMode.IONIAN: "bright",
            HarmonicMode.DORIAN: "mysterious",
            HarmonicMode.PHRYGIAN: "dark",
            HarmonicMode.LYDIAN: "ethereal",
            HarmonicMode.MIXOLYDIAN: "grounded",
            HarmonicMode.AEOLIAN: "reflective",
            HarmonicMode.LOCRIAN: "unsettled",
        }

        tempo_desc = (
            "urgent"
            if params.tempo_bpm > 120
            else "energetic"
            if params.tempo_bpm > 100
            else "flowing"
            if params.tempo_bpm > 80
            else "contemplative"
        )

        dynamic_desc = (
            "intense"
            if params.dynamic_level > 0.7
            else "present"
            if params.dynamic_level > 0.5
            else "gentle"
        )

        return f"{tempo_desc}, {mode_names.get(params.mode, 'balanced')}, {dynamic_desc}"


# =============================================================================
# SINGLETON & FACTORY
# =============================================================================

_SOUL_BRIDGE: SoulToMusicBridge | None = None


async def get_soul_bridge() -> SoulToMusicBridge:
    """Get singleton SoulToMusicBridge instance."""
    global _SOUL_BRIDGE
    if _SOUL_BRIDGE is None:
        _SOUL_BRIDGE = SoulToMusicBridge()
        await _SOUL_BRIDGE.initialize()
    return _SOUL_BRIDGE


def create_soul_bridge() -> SoulToMusicBridge:
    """Create a new SoulToMusicBridge instance (non-singleton)."""
    return SoulToMusicBridge()


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


async def soul_to_earcon_modulation(earcon_name: str) -> dict[str, Any]:
    """Get earcon modulation based on current soul state.

    This is the main entry point for soul-aware earcon playback.

    Args:
        earcon_name: Earcon to modulate

    Returns:
        Modulation parameters for playback
    """
    bridge = await get_soul_bridge()
    params = await bridge.from_system_feeling()
    return bridge.modulate_earcon(earcon_name, params)


async def get_current_musical_state() -> MusicalParameters:
    """Get current musical parameters from soul state."""
    bridge = await get_soul_bridge()
    return await bridge.from_system_feeling()


__all__ = [
    "COLONY_VOICES",
    "ColonyVoice",
    "HarmonicMode",
    "MusicalParameters",
    "SoulToMusicBridge",
    "create_soul_bridge",
    "get_current_musical_state",
    "get_soul_bridge",
    "soul_to_earcon_modulation",
]
