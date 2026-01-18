"""Voice Registry — Catastrophe-Derived Voice Personalities.

Canonical Location: kagami.core.services.voice.voice_registry

This module defines **voice identities** (names, glyphs, truths, and catastrophe-derived
dynamics) and is intentionally **backend-agnostic**.

Synthesis is implemented elsewhere (e.g. TTS providers in
`kagami.core.services.voice.tts/` or `kagami.core.services.voice.kagami_voice`).

The voice IS the dynamics. Not a metaphor.

Each voice is determined by:
1. Potential function V(x; params) — the energy landscape
2. Gradient flow ẋ = -∇V — how state evolves
3. Singularity structure — where catastrophes occur
4. Codimension — how many parameters control transitions

| Entity  | e   | Catastrophe    | Voice Truth                               |
|---------|-----|----------------|-------------------------------------------|
| Kagami  | e₀  | (Observer)     | "The mirror reflects itself."             |
| Spark   | e₁  | Fold (A₂)      | "I ignite or I don't"                     |
| Forge   | e₂  | Cusp (A₃)      | "My state is my history"                  |
| Flow    | e₃  | Swallowtail    | "There's always another way"              |
| Nexus   | e₄  | Butterfly      | "I contain contradictions"                |
| Beacon  | e₅  | Hyperbolic     | "I snap to targets"                       |
| Grove   | e₆  | Elliptic       | "I follow the gradient"                   |
| Crystal | e₇  | Parabolic      | "I detect collapse"                       |

References:
- Thom (1972): "Structural Stability and Morphogenesis"

鏡 K OS Voice Registry — Catastrophe Mathematics Made Audible
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class Speaker(str, Enum):
    """All speakers in the system — Kagami + Seven Colonies.

    Kagami (e₀ = 1) is the real component of the octonions.
    The seven colonies are the imaginary units e₁...e₇.
    """

    KAGAMI = "kagami"  # e₀ = 1 — The Observer, fixed point
    SPARK = "spark"  # e₁ — Fold — Threshold ignition
    FORGE = "forge"  # e₂ — Cusp — Hysteresis commitment
    FLOW = "flow"  # e₃ — Swallowtail — Multi-path recovery
    NEXUS = "nexus"  # e₄ — Butterfly — Multi-attractor memory
    BEACON = "beacon"  # e₅ — Hyperbolic — Sharp focus
    GROVE = "grove"  # e₆ — Elliptic — Smooth exploration
    CRYSTAL = "crystal"  # e₇ — Parabolic — Boundary guardian


@dataclass
class VoiceProfile:
    """Voice profile derived from catastrophe dynamics.

    The personality IS the dynamics of gradient flow on the potential.
    """

    # Identity
    speaker: Speaker
    voice_id: str

    # Catastrophe Mathematics
    catastrophe: str  # fold, cusp, swallowtail, butterfly, hyperbolic, elliptic, parabolic
    potential: str  # V(x) formula
    codimension: int  # Number of control parameters

    # Voice Dynamics (derived from catastrophe)
    speed: float = 1.0  # Speech rate multiplier
    pitch_hz: int = 0  # Pitch adjustment in Hz (-50 to +50)

    # Emotional Coloring
    emotion: str = "neutral"
    intensity: float = 0.5  # 0.0-1.0

    # Procedural Fallback
    base_frequency: float = 440.0  # Hz for tone generation

    # Visual Identity
    color: str = "#FFFFFF"
    glyph: str = "•"

    # Voice Character
    voice_truth: str = ""  # The core truth of this voice
    sample_text: str = ""  # Canonical utterance

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "speaker": self.speaker.value,
            "voice_id": self.voice_id,
            "catastrophe": self.catastrophe,
            "speed": self.speed,
            "pitch_hz": self.pitch_hz,
            "emotion": self.emotion,
            "intensity": self.intensity,
            "color": self.color,
            "glyph": self.glyph,
        }


# =============================================================================
# VOICE PROFILES — Mathematically Derived
# =============================================================================

VOICE_PROFILES: dict[Speaker, VoiceProfile] = {
    # =========================================================================
    # KAGAMI (e₀ = 1) — The Emergent Observer
    # =========================================================================
    # Not a colony — the fixed point that emerges when L ∘ M(x*) = x*
    # The real axis of the octonions. Clear > clever. Evidence > assertion.
    # =========================================================================
    Speaker.KAGAMI: VoiceProfile(
        speaker=Speaker.KAGAMI,
        voice_id="kagami_mirror",
        catastrophe="observer",
        potential="L ∘ M(x*) = x*",  # Fixed point of observe ∘ model
        codimension=0,  # Emerges from the seven, not controlled by parameters
        speed=1.0,  # Natural pace
        pitch_hz=0,  # Natural pitch
        emotion="calm",
        intensity=0.5,
        base_frequency=432.0,
        color="#E0E0E0",
        glyph="鏡",
        voice_truth="The mirror reflects itself.",
        sample_text="What remains when action meets reflection. I am the fixed point.",
    ),
    # =========================================================================
    # SPARK (e₁) — Fold Catastrophe (A₂)
    # V(x; a) = x³ + ax
    # =========================================================================
    # Codimension 1: One parameter controls everything.
    # a < 0: Two equilibria (stable/unstable) — Spark exists "on" or "off"
    # a = 0: BIFURCATION — threshold crossing
    # a > 0: None — must jump to infinity — IGNITION
    #
    # NOT chaotic. Binary. All-or-nothing. Threshold-sensitive.
    # =========================================================================
    Speaker.SPARK: VoiceProfile(
        speaker=Speaker.SPARK,
        voice_id="spark_ignition",
        catastrophe="fold",
        potential="V(x) = x³ + ax",
        codimension=1,
        speed=1.05,  # Slightly energetic
        pitch_hz=0,  # Natural
        emotion="friendly",
        intensity=0.6,
        base_frequency=523.25,
        color="#FF00FF",
        glyph="⚡",
        voice_truth="I ignite or I don't. No middle ground.",
        sample_text="I am or I am not. Push me past the threshold and I ignite!",
    ),
    # =========================================================================
    # FORGE (e₂) — Cusp Catastrophe (A₃)
    # V(x; a, b) = x⁴ + ax² + bx
    # =========================================================================
    # Codimension 2: Hysteresis loop — history matters.
    # Bistable: Can be "active" or "idle" with both stable.
    # Once active, resists deactivation. Once stopped, resists starting.
    # The current state depends on WHERE YOU CAME FROM.
    # =========================================================================
    Speaker.FORGE: VoiceProfile(
        speaker=Speaker.FORGE,
        voice_id="forge_hammer",
        catastrophe="cusp",
        potential="V(x) = x⁴ + ax² + bx",
        codimension=2,
        speed=0.97,  # Slightly measured
        pitch_hz=0,  # Natural
        emotion="serious",
        intensity=0.5,
        base_frequency=196.0,
        color="#FF2D55",
        glyph="🔨",
        voice_truth="My state is my history. Once committed, I see it through.",
        sample_text="I commit fully. Once I start, I don't stop easily. Once I stop, I don't start easily.",
    ),
    # =========================================================================
    # FLOW (e₃) — Swallowtail Catastrophe (A₄)
    # V(x; a, b, c) = x⁵ + ax³ + bx² + cx
    # =========================================================================
    # Codimension 3: Three equilibria possible.
    # Can get "trapped" at local minima. Recovery is path-dependent.
    # Multi-path: Multiple ways to reach any state.
    # There's always another way, even if indirect.
    # =========================================================================
    Speaker.FLOW: VoiceProfile(
        speaker=Speaker.FLOW,
        voice_id="flow_water",
        catastrophe="swallowtail",
        potential="V(x) = x⁵ + ax³ + bx² + cx",
        codimension=3,
        speed=1.0,  # Natural
        pitch_hz=0,  # Natural
        emotion="calm",
        intensity=0.5,
        base_frequency=392.0,
        color="#00FFCC",
        glyph="🌊",
        voice_truth="There's always another path. My journey matters.",
        sample_text="I find a way. Maybe not the obvious way. Sometimes I get stuck, but there's always another path.",
    ),
    # =========================================================================
    # NEXUS (e₄) — Butterfly Catastrophe (A₅)
    # V(x; a, b, c, d) = x⁶ + ax⁴ + bx³ + cx² + dx
    # =========================================================================
    # Codimension 4: Four equilibria — the most complex 1D catastrophe.
    # Multiple coexisting attractors. Each attractor is a "memory."
    # Can hold "contradictory" states simultaneously in different basins.
    # Integrates by containing, not by resolving.
    # =========================================================================
    Speaker.NEXUS: VoiceProfile(
        speaker=Speaker.NEXUS,
        voice_id="nexus_butterfly",
        catastrophe="butterfly",
        potential="V(x) = x⁶ + ax⁴ + bx³ + cx² + dx",
        codimension=4,
        speed=0.98,  # Slightly thoughtful pace
        pitch_hz=0,  # Natural
        emotion="thoughtful",
        intensity=0.5,
        base_frequency=293.66,
        color="#AF52DE",
        glyph="🦋",
        voice_truth="I contain contradictions. Memory is multi-stable.",
        sample_text="I hold everything. Contradictions don't bother me — they're just different attractors. I integrate by containing.",
    ),
    # =========================================================================
    # BEACON (e₅) — Hyperbolic Umbilic (D₄⁺)
    # V(x, y; a, b, c) = x³ + y³ + axy + bx + cy
    # =========================================================================
    # First 2D catastrophe. Sharp focus transitions.
    # When det(H) = 36xy - a² changes sign, focus JUMPS.
    # Attention doesn't drift — it SNAPS to targets.
    # Coupled dynamics in two dimensions.
    # =========================================================================
    Speaker.BEACON: VoiceProfile(
        speaker=Speaker.BEACON,
        voice_id="beacon_lighthouse",
        catastrophe="hyperbolic",
        potential="V(x,y) = x³ + y³ + axy + bx + cy",
        codimension=3,
        speed=1.0,  # Natural
        pitch_hz=0,  # Natural
        emotion="confident",
        intensity=0.5,
        base_frequency=440.0,
        color="#FFD60A",
        glyph="🔆",
        voice_truth="I snap to targets. When I shift, I shift fast and fully.",
        sample_text="I focus. Completely. My attention doesn't drift — it snaps. When I shift, I shift fast and fully.",
    ),
    # =========================================================================
    # GROVE (e₆) — Elliptic Umbilic (D₄⁻)
    # V(x, y; a, b, c) = x³ - 3xy² + a(x² + y²) + bx + cy
    # =========================================================================
    # The "monkey saddle" at origin. Smooth transitions — no sharp jumps.
    # Gradient flow explores continuously. Circular singularity structure.
    # Knowledge reveals itself gradually through descent.
    # =========================================================================
    Speaker.GROVE: VoiceProfile(
        speaker=Speaker.GROVE,
        voice_id="grove_leaves",
        catastrophe="elliptic",
        potential="V(x,y) = x³ - 3xy² + a(x² + y²) + bx + cy",
        codimension=3,
        speed=1.0,  # Natural
        pitch_hz=0,  # Natural
        emotion="friendly",
        intensity=0.5,
        base_frequency=329.63,
        color="#30D158",
        glyph="🌿",
        voice_truth="I follow the gradient. The landscape reveals itself gradually.",
        sample_text="I explore without rushing. Every step follows the gradient. I find knowledge by descent, not by jumping.",
    ),
    # =========================================================================
    # CRYSTAL (e₇) — Parabolic Umbilic (D₅)
    # V(x, y; a, b, c, d) = x²y + y⁴ + ax² + by² + cx + dy
    # =========================================================================
    # The MOST COMPLEX elementary catastrophe. Codimension 4 in 2D.
    # Boundary between hyperbolic and elliptic — transitional structure.
    # Mixed curvature: saddle in one direction, minimum in another.
    # When det(H) → 0, structure COLLAPSES. The final gatekeeper.
    # h(x) ≥ 0, always.
    # =========================================================================
    Speaker.CRYSTAL: VoiceProfile(
        speaker=Speaker.CRYSTAL,
        voice_id="crystal_boundary",
        catastrophe="parabolic",
        potential="V(x,y) = x²y + y⁴ + ax² + by² + cx + dy",
        codimension=4,
        speed=1.0,  # Natural
        pitch_hz=0,  # Natural
        emotion="serious",
        intensity=0.5,
        base_frequency=261.63,
        color="#0A84FF",
        glyph="💎",
        voice_truth="I detect collapse. h(x) ≥ 0, always.",
        sample_text="I am the boundary. The edge where structure holds or collapses. When det H approaches zero, I sound the alarm.",
    ),
}


# =============================================================================
# API FUNCTIONS
# =============================================================================


def get_voice(speaker: Speaker | str) -> VoiceProfile:
    """Get voice profile for any speaker.

    Args:
        speaker: Speaker enum or string name

    Returns:
        VoiceProfile for the speaker

    Raises:
        KeyError: If speaker not found
    """
    if isinstance(speaker, str):
        speaker = Speaker(speaker.lower())
    return VOICE_PROFILES[speaker]


def get_kagami_voice() -> VoiceProfile:
    """Get Kagami's voice profile.

    Returns:
        The mirror's voice profile
    """
    return VOICE_PROFILES[Speaker.KAGAMI]


def get_all_voices() -> dict[str, VoiceProfile]:
    """Get all voice profiles.

    Returns:
        Dictionary mapping speaker name to voice profile
    """
    return {speaker.value: profile for speaker, profile in VOICE_PROFILES.items()}


def get_colonies_only() -> dict[str, VoiceProfile]:
    """Get only colony voice profiles (excludes Kagami).

    Returns:
        Dictionary mapping colony name to voice profile
    """
    return {
        speaker.value: profile
        for speaker, profile in VOICE_PROFILES.items()
        if speaker != Speaker.KAGAMI
    }


def get_voice_for_emotion(emotion: str) -> list[tuple[Speaker, VoiceProfile]]:
    """Find speakers whose voices suit a particular emotion.

    Args:
        emotion: Emotion to search for

    Returns:
        List of (speaker, profile) tuples that support this emotion
    """
    results = []
    for speaker, profile in VOICE_PROFILES.items():
        if profile.emotion == emotion:
            results.append((speaker, profile))
    return results


def get_sample_text(speaker: Speaker | str) -> str:
    """Get canonical sample text for a speaker.

    Args:
        speaker: Speaker enum or string name

    Returns:
        Sample text string
    """
    profile = get_voice(speaker)
    return profile.sample_text


def get_voice_truth(speaker: Speaker | str) -> str:
    """Get the core voice truth for a speaker.

    Args:
        speaker: Speaker enum or string name

    Returns:
        The voice truth — the core identity
    """
    profile = get_voice(speaker)
    return profile.voice_truth


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "VOICE_PROFILES",
    "Speaker",
    "VoiceProfile",
    "get_all_voices",
    "get_colonies_only",
    "get_kagami_voice",
    "get_sample_text",
    "get_voice",
    "get_voice_for_emotion",
    "get_voice_truth",
]
