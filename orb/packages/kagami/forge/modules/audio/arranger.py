"""LLM-Powered Arranger — Intelligent Orchestration and Arrangement.

Uses LLM to analyze musical content and generate intelligent orchestrations:
- Instrument assignment based on timbre and range
- Voicing and doubling decisions
- Dynamic orchestration choices
- Style-appropriate arrangements

Pipeline:
    MIDI → Analysis → LLM Orchestration → BBC SO Mapping → Enriched MIDI

Usage:
    from kagami.forge.modules.audio.arranger import arrange

    result = await arrange(
        "melody.mid",
        style="romantic",
        target_ensemble="full_orchestra"
    )

Colony: Forge (e₂)
Created: January 2, 2026
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


class ArrangementStyle(Enum):
    """Orchestration style."""

    ROMANTIC = "romantic"  # Lush doublings, rich harmonies (Brahms, Tchaikovsky)
    BAROQUE = "baroque"  # Light, transparent, contrapuntal (Bach, Vivaldi)
    CLASSICAL = "classical"  # Balanced, clear voicings (Mozart, Haydn)
    IMPRESSIONIST = "impressionist"  # Colorful, unusual combinations (Debussy, Ravel)
    FILM_SCORE = "film_score"  # Dramatic, powerful (Williams, Zimmer)
    MINIMALIST = "minimalist"  # Sparse, focused (Glass, Reich)
    JAZZ = "jazz"  # Voiced harmonies, walking bass (Ellington)
    CHAMBER = "chamber"  # Intimate, soloistic (string quartet style)


class TargetEnsemble(Enum):
    """Target ensemble size and composition."""

    FULL_ORCHESTRA = "full"  # All sections
    STRINGS_ONLY = "strings"  # String orchestra
    BRASS_BAND = "brass"  # Brass and percussion
    WIND_ENSEMBLE = "winds"  # Woodwinds and brass
    CHAMBER = "chamber"  # Small ensemble (8-15)
    STRING_QUARTET = "quartet"  # 2vn, va, vc
    PIANO_TRIO = "trio"  # pn, vn, vc


# BBC Symphony Orchestra instrument mapping
BBC_INSTRUMENTS = {
    # Strings
    "violin_1": {"program": 40, "range": (55, 96), "family": "strings", "section": "violin"},
    "violin_2": {"program": 40, "range": (55, 93), "family": "strings", "section": "violin"},
    "viola": {"program": 41, "range": (48, 84), "family": "strings", "section": "viola"},
    "cello": {"program": 42, "range": (36, 72), "family": "strings", "section": "cello"},
    "bass": {"program": 43, "range": (28, 55), "family": "strings", "section": "bass"},
    # Woodwinds
    "flute": {"program": 73, "range": (60, 96), "family": "woodwinds", "section": "flute"},
    "piccolo": {"program": 72, "range": (74, 108), "family": "woodwinds", "section": "flute"},
    "oboe": {"program": 68, "range": (58, 91), "family": "woodwinds", "section": "oboe"},
    "clarinet": {"program": 71, "range": (50, 91), "family": "woodwinds", "section": "clarinet"},
    "bassoon": {"program": 70, "range": (34, 72), "family": "woodwinds", "section": "bassoon"},
    # Brass
    "horn": {"program": 60, "range": (34, 77), "family": "brass", "section": "horn"},
    "trumpet": {"program": 56, "range": (55, 82), "family": "brass", "section": "trumpet"},
    "trombone": {"program": 57, "range": (40, 72), "family": "brass", "section": "trombone"},
    "tuba": {"program": 58, "range": (28, 58), "family": "brass", "section": "tuba"},
    # Percussion
    "timpani": {"program": 47, "range": (36, 60), "family": "percussion", "section": "timpani"},
    "harp": {"program": 46, "range": (24, 96), "family": "strings", "section": "harp"},
}


@dataclass
class ArrangerConfig:
    """Arranger configuration."""

    style: ArrangementStyle = ArrangementStyle.FILM_SCORE
    target_ensemble: TargetEnsemble = TargetEnsemble.FULL_ORCHESTRA

    # Orchestration options
    use_doublings: bool = True  # Double melodies in octaves
    use_tutti: bool = True  # Full orchestra moments
    preserve_original_voicing: bool = False  # Keep original instrument assignments

    # LLM settings
    use_llm: bool = True  # Use LLM for intelligent decisions
    llm_model: str = "claude-3-haiku-20240307"  # Fast model for arrangement

    # Output
    output_separate_parts: bool = False  # Create individual part files


@dataclass
class InstrumentAssignment:
    """Assignment of musical content to an instrument."""

    instrument: str  # BBC instrument key
    track_index: int  # Source track
    voice: int  # Voice within instrument (for divisi)
    start_measure: int
    end_measure: int
    role: str  # "melody", "harmony", "bass", "countermelody", "doubling"
    dynamics: str  # "pp", "p", "mp", "mf", "f", "ff"
    articulation: str  # "legato", "staccato", "marcato", etc.


@dataclass
class ArrangementPlan:
    """Complete orchestration plan."""

    assignments: list[InstrumentAssignment]
    doublings: list[tuple[str, str]]  # Pairs of doubled instruments
    tutti_sections: list[tuple[int, int]]  # Measure ranges for tutti
    solo_sections: list[tuple[str, int, int]]  # Instrument, start, end
    dynamic_changes: list[tuple[int, str]]  # Measure, dynamic
    style_notes: str  # LLM-generated style guidance


@dataclass
class ArrangementResult:
    """Result of arrangement process."""

    success: bool
    output_path: Path | None = None
    plan: ArrangementPlan | None = None
    instruments_used: list[str] = field(default_factory=list)
    total_tracks: int = 0
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# MIDI Analysis for Arrangement
# =============================================================================


@dataclass
class MusicalAnalysis:
    """Analysis of musical content for arrangement decisions."""

    # Range analysis
    lowest_pitch: int
    highest_pitch: int
    avg_pitch: float
    pitch_range: int

    # Rhythm analysis
    note_density: float  # Notes per beat
    has_fast_passages: bool
    has_sustained_notes: bool

    # Texture analysis
    is_melodic: bool  # Single line
    is_chordal: bool  # Block chords
    is_contrapuntal: bool  # Multiple independent voices
    voice_count: int

    # Character
    intensity: float  # 0-1 based on velocity
    variability: float  # Dynamic range


def analyze_for_arrangement(midi_path: Path) -> tuple[list[MusicalAnalysis], dict]:
    """Analyze MIDI file for arrangement decisions.

    Args:
        midi_path: Path to MIDI file

    Returns:
        Tuple of (per-track analyses, global metadata)
    """
    import pretty_midi

    midi = pretty_midi.PrettyMIDI(str(midi_path))
    analyses = []

    for inst in midi.instruments:
        if not inst.notes or inst.is_drum:
            continue

        notes = inst.notes
        pitches = [n.pitch for n in notes]
        velocities = [n.velocity for n in notes]
        durations = [n.end - n.start for n in notes]

        # Range
        lowest = min(pitches)
        highest = max(pitches)
        avg = sum(pitches) / len(pitches)

        # Rhythm
        total_duration = max(n.end for n in notes) - min(n.start for n in notes)
        density = len(notes) / total_duration if total_duration > 0 else 0
        has_fast = any(d < 0.1 for d in durations)
        has_sustained = any(d > 1.0 for d in durations)

        # Texture detection
        # Check for simultaneous notes (chordal)
        note_starts = sorted(n.start for n in notes)
        simultaneous_count = sum(
            1 for i in range(len(note_starts) - 1) if note_starts[i + 1] - note_starts[i] < 0.05
        )
        is_chordal = simultaneous_count > len(notes) * 0.3

        # Count distinct pitch levels sounding together
        voice_count = _estimate_voice_count(notes)
        is_melodic = voice_count <= 1
        is_contrapuntal = voice_count > 1 and not is_chordal

        # Character
        avg_vel = sum(velocities) / len(velocities)
        intensity = avg_vel / 127.0
        vel_range = max(velocities) - min(velocities)
        variability = vel_range / 127.0

        analyses.append(
            MusicalAnalysis(
                lowest_pitch=lowest,
                highest_pitch=highest,
                avg_pitch=avg,
                pitch_range=highest - lowest,
                note_density=density,
                has_fast_passages=has_fast,
                has_sustained_notes=has_sustained,
                is_melodic=is_melodic,
                is_chordal=is_chordal,
                is_contrapuntal=is_contrapuntal,
                voice_count=voice_count,
                intensity=intensity,
                variability=variability,
            )
        )

    # Global metadata
    tempo = midi.get_tempo_changes()[1][0] if midi.get_tempo_changes()[1].size > 0 else 120
    duration = midi.get_end_time()

    metadata = {
        "tempo": tempo,
        "duration": duration,
        "track_count": len(analyses),
        "total_notes": sum(len(inst.notes) for inst in midi.instruments if not inst.is_drum),
    }

    return analyses, metadata


def _estimate_voice_count(notes: list) -> int:
    """Estimate number of simultaneous voices in a track."""
    if not notes:
        return 0

    # Sample time points
    times = np.linspace(min(n.start for n in notes), max(n.end for n in notes), 100)

    max_simultaneous = 0
    for t in times:
        count = sum(1 for n in notes if n.start <= t < n.end)
        max_simultaneous = max(max_simultaneous, count)

    return max_simultaneous


# =============================================================================
# Rule-Based Orchestration
# =============================================================================


def get_suitable_instruments(
    analysis: MusicalAnalysis,
    ensemble: TargetEnsemble,
    role: str = "auto",
) -> list[str]:
    """Get suitable instruments for given musical content.

    Args:
        analysis: Musical analysis of the content
        ensemble: Target ensemble
        role: Musical role (melody, harmony, bass, auto)

    Returns:
        List of suitable BBC instrument keys
    """
    suitable = []

    # Get available instruments for ensemble
    available = _get_ensemble_instruments(ensemble)

    for inst_key in available:
        inst = BBC_INSTRUMENTS.get(inst_key)
        if not inst:
            continue

        low, high = inst["range"]

        # Range check - instrument must cover most of the content
        range_ok = low <= analysis.lowest_pitch and high >= analysis.highest_pitch
        partial_ok = low <= analysis.avg_pitch <= high and analysis.pitch_range < (high - low) * 0.8

        if not (range_ok or partial_ok):
            continue

        # Character matching
        family = inst["family"]

        # Fast passages better on strings/woodwinds
        if analysis.has_fast_passages and family == "brass":
            continue

        # Sustained melodies great on strings/winds
        if analysis.is_melodic and analysis.has_sustained_notes:
            if family in ("strings", "woodwinds"):
                suitable.insert(0, inst_key)  # Prefer these
                continue

        # Low bass lines
        if analysis.avg_pitch < 48:
            if inst_key in ("bass", "cello", "bassoon", "tuba"):
                suitable.insert(0, inst_key)
                continue

        suitable.append(inst_key)

    return suitable


def _get_ensemble_instruments(ensemble: TargetEnsemble) -> list[str]:
    """Get instruments available for an ensemble."""
    if ensemble == TargetEnsemble.FULL_ORCHESTRA:
        return list(BBC_INSTRUMENTS.keys())

    elif ensemble == TargetEnsemble.STRINGS_ONLY:
        return ["violin_1", "violin_2", "viola", "cello", "bass", "harp"]

    elif ensemble == TargetEnsemble.BRASS_BAND:
        return ["trumpet", "horn", "trombone", "tuba", "timpani"]

    elif ensemble == TargetEnsemble.WIND_ENSEMBLE:
        return [
            "flute",
            "piccolo",
            "oboe",
            "clarinet",
            "bassoon",
            "trumpet",
            "horn",
            "trombone",
            "tuba",
        ]

    elif ensemble == TargetEnsemble.CHAMBER:
        return [
            "violin_1",
            "violin_2",
            "viola",
            "cello",
            "flute",
            "oboe",
            "clarinet",
            "bassoon",
            "horn",
        ]

    elif ensemble == TargetEnsemble.STRING_QUARTET:
        return ["violin_1", "violin_2", "viola", "cello"]

    elif ensemble == TargetEnsemble.PIANO_TRIO:
        return ["violin_1", "cello"]  # Piano handled separately

    return list(BBC_INSTRUMENTS.keys())


def create_rule_based_plan(
    analyses: list[MusicalAnalysis],
    config: ArrangerConfig,
    metadata: dict,
) -> ArrangementPlan:
    """Create orchestration plan using rule-based approach.

    Args:
        analyses: Per-track musical analyses
        config: Arranger configuration
        metadata: Global MIDI metadata

    Returns:
        ArrangementPlan with instrument assignments
    """
    assignments = []
    doublings = []
    tutti_sections = []
    solo_sections = []
    dynamic_changes = []

    # Sort tracks by role: melody (highest avg pitch), bass (lowest), harmony (middle)
    indexed_analyses = list(enumerate(analyses))
    indexed_analyses.sort(key=lambda x: x[1].avg_pitch, reverse=True)

    # Assign roles
    melody_idx = indexed_analyses[0][0] if indexed_analyses else None
    bass_idx = indexed_analyses[-1][0] if len(indexed_analyses) > 1 else None
    harmony_indices = [i for i, _ in indexed_analyses[1:-1]] if len(indexed_analyses) > 2 else []

    # Assign melody
    if melody_idx is not None:
        analysis = analyses[melody_idx]
        suitable = get_suitable_instruments(analysis, config.target_ensemble, "melody")

        if suitable:
            # Primary melody instrument
            primary = suitable[0]
            assignments.append(
                InstrumentAssignment(
                    instrument=primary,
                    track_index=melody_idx,
                    voice=0,
                    start_measure=0,
                    end_measure=-1,  # All measures
                    role="melody",
                    dynamics="mf",
                    articulation="legato",
                )
            )

            # Optional doubling (romantic style)
            if config.use_doublings and config.style == ArrangementStyle.ROMANTIC:
                if len(suitable) > 1:
                    doubling = suitable[1]
                    assignments.append(
                        InstrumentAssignment(
                            instrument=doubling,
                            track_index=melody_idx,
                            voice=0,
                            start_measure=0,
                            end_measure=-1,
                            role="doubling",
                            dynamics="mp",
                            articulation="legato",
                        )
                    )
                    doublings.append((primary, doubling))

    # Assign bass
    if bass_idx is not None:
        analysis = analyses[bass_idx]
        suitable = get_suitable_instruments(analysis, config.target_ensemble, "bass")

        if suitable:
            assignments.append(
                InstrumentAssignment(
                    instrument=suitable[0],
                    track_index=bass_idx,
                    voice=0,
                    start_measure=0,
                    end_measure=-1,
                    role="bass",
                    dynamics="mf",
                    articulation="legato",
                )
            )

    # Assign harmony parts
    for i, harm_idx in enumerate(harmony_indices):
        analysis = analyses[harm_idx]
        suitable = get_suitable_instruments(analysis, config.target_ensemble, "harmony")

        if suitable:
            # Cycle through available instruments
            inst = suitable[i % len(suitable)]
            assignments.append(
                InstrumentAssignment(
                    instrument=inst,
                    track_index=harm_idx,
                    voice=0,
                    start_measure=0,
                    end_measure=-1,
                    role="harmony",
                    dynamics="mp",
                    articulation="legato",
                )
            )

    # Style-specific notes
    style_notes = _get_style_notes(config.style)

    return ArrangementPlan(
        assignments=assignments,
        doublings=doublings,
        tutti_sections=tutti_sections,
        solo_sections=solo_sections,
        dynamic_changes=dynamic_changes,
        style_notes=style_notes,
    )


def _get_style_notes(style: ArrangementStyle) -> str:
    """Get style-specific orchestration guidance."""
    notes = {
        ArrangementStyle.ROMANTIC: (
            "Romantic orchestration: Use rich string doublings, horn calls, "
            "sweeping dynamic arcs. Cellos double bass in octaves. "
            "Woodwinds provide color, brass for climaxes."
        ),
        ArrangementStyle.BAROQUE: (
            "Baroque orchestration: Light, transparent textures. "
            "Avoid heavy doublings. Terraced dynamics. "
            "Basso continuo (cello + bass). Harpsichord fills."
        ),
        ArrangementStyle.CLASSICAL: (
            "Classical orchestration: Clear, balanced voices. "
            "Winds as soloists, strings as foundation. "
            "Horns sustain harmonies. Timpani on tonic/dominant."
        ),
        ArrangementStyle.IMPRESSIONIST: (
            "Impressionist orchestration: Colorful timbres, divided strings, "
            "harp and celesta. Muted brass. Solo woodwind colors. "
            "Avoid heavy tutti, prefer delicate textures."
        ),
        ArrangementStyle.FILM_SCORE: (
            "Film score orchestration: Epic brass fanfares, "
            "sweeping string lines, powerful percussion. "
            "French horns for heroic themes, low brass for weight."
        ),
        ArrangementStyle.MINIMALIST: (
            "Minimalist orchestration: Sparse, focused textures. "
            "Solo instruments or small groups. Steady rhythms. "
            "Gradual additive processes. Avoid thick doublings."
        ),
        ArrangementStyle.JAZZ: (
            "Jazz orchestration: Voiced brass section, walking bass, "
            "piano comping. Saxophone section for color. "
            "Muted brass effects. Swing feel."
        ),
        ArrangementStyle.CHAMBER: (
            "Chamber orchestration: Intimate, soloistic writing. "
            "Each instrument has distinct lines. Conversation between voices. "
            "Balance through dynamic marking, not doublings."
        ),
    }
    return notes.get(style, "Standard orchestration principles apply.")


# =============================================================================
# LLM-Powered Orchestration
# =============================================================================


async def create_llm_plan(
    analyses: list[MusicalAnalysis],
    config: ArrangerConfig,
    metadata: dict,
) -> ArrangementPlan:
    """Create orchestration plan using LLM intelligence.

    Args:
        analyses: Per-track musical analyses
        config: Arranger configuration
        metadata: Global MIDI metadata

    Returns:
        ArrangementPlan with LLM-guided assignments
    """
    # Build analysis summary for LLM
    analysis_summary = []
    for i, a in enumerate(analyses):
        summary = {
            "track": i,
            "range": f"{a.lowest_pitch}-{a.highest_pitch}",
            "avg_pitch": round(a.avg_pitch, 1),
            "character": _get_character_description(a),
            "texture": _get_texture_description(a),
        }
        analysis_summary.append(summary)

    # Get available instruments
    available = _get_ensemble_instruments(config.target_ensemble)

    # Build prompt
    prompt = f"""You are an expert orchestrator. Analyze this musical content and create an orchestration plan.

STYLE: {config.style.value}
ENSEMBLE: {config.target_ensemble.value}
TEMPO: {metadata["tempo"]} BPM
DURATION: {metadata["duration"]:.1f} seconds

AVAILABLE INSTRUMENTS:
{json.dumps({k: BBC_INSTRUMENTS[k]["range"] for k in available}, indent=2)}

TRACK ANALYSIS:
{json.dumps(analysis_summary, indent=2)}

Create an orchestration plan as JSON:
{{
  "assignments": [
    {{"track": 0, "instrument": "violin_1", "role": "melody", "dynamics": "mf", "articulation": "legato"}},
    ...
  ],
  "doublings": [["violin_1", "flute"]],  // Optional octave doublings
  "tutti_sections": [[0, 16]],  // Measure ranges for full orchestra
  "solo_sections": [["oboe", 8, 16]],  // Solo highlights
  "style_notes": "Brief notes on this arrangement"
}}

Consider:
1. Range compatibility (instrument must cover the notes)
2. Style-appropriate timbres (romantic = rich strings, baroque = transparent)
3. Balance between sections
4. Climax building through orchestration
5. Color and variety

Return ONLY valid JSON, no explanation."""

    try:
        # Try to use Kagami's LLM service
        from kagami.core.services.llm.frozen_llm_service import get_frozen_llm_service

        llm = get_frozen_llm_service()
        response = await llm.generate(
            prompt,
            max_tokens=2000,
            temperature=0.7,
        )

        # Parse JSON response
        # Find JSON in response (handle markdown code blocks)
        json_str = response
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0]
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0]

        plan_data = json.loads(json_str.strip())

        # Convert to ArrangementPlan
        assignments = []
        for a in plan_data.get("assignments", []):
            assignments.append(
                InstrumentAssignment(
                    instrument=a["instrument"],
                    track_index=a.get("track", 0),
                    voice=a.get("voice", 0),
                    start_measure=a.get("start_measure", 0),
                    end_measure=a.get("end_measure", -1),
                    role=a.get("role", "harmony"),
                    dynamics=a.get("dynamics", "mf"),
                    articulation=a.get("articulation", "legato"),
                )
            )

        return ArrangementPlan(
            assignments=assignments,
            doublings=plan_data.get("doublings", []),
            tutti_sections=plan_data.get("tutti_sections", []),
            solo_sections=plan_data.get("solo_sections", []),
            dynamic_changes=plan_data.get("dynamic_changes", []),
            style_notes=plan_data.get("style_notes", ""),
        )

    except Exception as e:
        logger.warning(f"LLM orchestration failed: {e}, falling back to rules")
        return create_rule_based_plan(analyses, config, metadata)


def _get_character_description(analysis: MusicalAnalysis) -> str:
    """Get human-readable character description."""
    chars = []

    if analysis.intensity > 0.7:
        chars.append("intense")
    elif analysis.intensity < 0.3:
        chars.append("gentle")

    if analysis.has_fast_passages:
        chars.append("virtuosic")
    if analysis.has_sustained_notes:
        chars.append("lyrical")

    if analysis.variability > 0.5:
        chars.append("dynamic")

    return ", ".join(chars) if chars else "neutral"


def _get_texture_description(analysis: MusicalAnalysis) -> str:
    """Get human-readable texture description."""
    if analysis.is_melodic:
        return "melodic line"
    elif analysis.is_chordal:
        return f"chordal ({analysis.voice_count} voices)"
    elif analysis.is_contrapuntal:
        return f"polyphonic ({analysis.voice_count} voices)"
    return "mixed"


# =============================================================================
# MIDI Transformation
# =============================================================================


async def apply_arrangement(
    midi_path: Path,
    plan: ArrangementPlan,
    output_path: Path,
) -> bool:
    """Apply orchestration plan to MIDI file.

    Args:
        midi_path: Input MIDI file
        plan: Orchestration plan
        output_path: Output MIDI file

    Returns:
        True if successful
    """
    import pretty_midi

    midi = pretty_midi.PrettyMIDI(str(midi_path))
    output = pretty_midi.PrettyMIDI()

    for assignment in plan.assignments:
        if assignment.track_index >= len(midi.instruments):
            continue

        source = midi.instruments[assignment.track_index]
        inst_info = BBC_INSTRUMENTS.get(assignment.instrument)

        if not inst_info:
            continue

        # Create new instrument
        new_inst = pretty_midi.Instrument(
            program=inst_info["program"],
            name=assignment.instrument,
        )

        # Copy and transform notes
        low, high = inst_info["range"]
        for note in source.notes:
            # Transpose if out of range
            pitch = note.pitch
            while pitch < low:
                pitch += 12
            while pitch > high:
                pitch -= 12

            # Adjust velocity based on dynamics
            vel = _dynamics_to_velocity(assignment.dynamics, note.velocity)

            new_note = pretty_midi.Note(
                velocity=vel,
                pitch=pitch,
                start=note.start,
                end=note.end,
            )
            new_inst.notes.append(new_note)

        output.instruments.append(new_inst)

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output.write(str(output_path))

    return True


def _dynamics_to_velocity(dynamics: str, base_velocity: int) -> int:
    """Convert dynamic marking to velocity modifier."""
    modifiers = {
        "pp": 0.4,
        "p": 0.55,
        "mp": 0.7,
        "mf": 0.85,
        "f": 1.0,
        "ff": 1.1,
    }
    mod = modifiers.get(dynamics, 0.85)
    return max(1, min(127, int(base_velocity * mod)))


# =============================================================================
# Main Arranger
# =============================================================================


class Arranger:
    """LLM-powered orchestral arranger.

    Analyzes musical content and creates intelligent orchestrations
    based on style, ensemble, and musical characteristics.
    """

    def __init__(self, config: ArrangerConfig | None = None):
        self.config = config or ArrangerConfig()

    async def arrange(
        self,
        midi_path: Path | str,
        output_path: Path | str | None = None,
    ) -> ArrangementResult:
        """Arrange MIDI file for target ensemble.

        Args:
            midi_path: Input MIDI file
            output_path: Output MIDI file (auto-generated if None)

        Returns:
            ArrangementResult with orchestrated MIDI
        """
        midi_path = Path(midi_path)

        if not midi_path.exists():
            return ArrangementResult(
                success=False,
                error=f"MIDI file not found: {midi_path}",
            )

        # Determine output path
        if output_path is None:
            output_path = midi_path.parent / f"{midi_path.stem}_arranged.mid"
        else:
            output_path = Path(output_path)

        try:
            # Analyze MIDI
            logger.info(f"🎻 Analyzing for arrangement: {midi_path}")
            analyses, metadata = analyze_for_arrangement(midi_path)

            if not analyses:
                return ArrangementResult(
                    success=False,
                    error="No analyzable tracks in MIDI",
                )

            # Create orchestration plan
            if self.config.use_llm:
                logger.info("   Creating LLM-guided orchestration plan...")
                plan = await create_llm_plan(analyses, self.config, metadata)
            else:
                logger.info("   Creating rule-based orchestration plan...")
                plan = create_rule_based_plan(analyses, self.config, metadata)

            logger.info(
                f"   Plan: {len(plan.assignments)} assignments, {len(plan.doublings)} doublings"
            )

            # Apply arrangement
            logger.info("   Applying orchestration...")
            success = await apply_arrangement(midi_path, plan, output_path)

            if success:
                instruments = list({a.instrument for a in plan.assignments})
                logger.info(f"✓ Arranged: {output_path}")
                logger.info(f"   Instruments: {', '.join(instruments)}")

                return ArrangementResult(
                    success=True,
                    output_path=output_path,
                    plan=plan,
                    instruments_used=instruments,
                    total_tracks=len(analyses),
                    metadata=metadata,
                )
            else:
                return ArrangementResult(
                    success=False,
                    error="Failed to apply arrangement",
                    plan=plan,
                )

        except Exception as e:
            logger.error(f"Arrangement failed: {e}", exc_info=True)
            return ArrangementResult(
                success=False,
                error=str(e),
            )


# =============================================================================
# API Functions
# =============================================================================

_arranger: Arranger | None = None


def get_arranger(config: ArrangerConfig | None = None) -> Arranger:
    """Get or create arranger singleton."""
    global _arranger
    if _arranger is None or config is not None:
        _arranger = Arranger(config)
    return _arranger


async def arrange(
    midi_path: Path | str,
    output_path: Path | str | None = None,
    style: str | ArrangementStyle = "film_score",
    target_ensemble: str | TargetEnsemble = "full",
    use_llm: bool = True,
    **kwargs,
) -> ArrangementResult:
    """Arrange MIDI file for orchestra.

    This is the main API for arrangement.

    Args:
        midi_path: Input MIDI file
        output_path: Output MIDI file (auto-generated if None)
        style: Orchestration style
        target_ensemble: Target ensemble type
        use_llm: Use LLM for intelligent orchestration
        **kwargs: Additional ArrangerConfig options

    Returns:
        ArrangementResult with orchestrated MIDI

    Examples:
        # Full orchestra, film style
        result = await arrange("melody.mid", style="film_score")

        # String quartet arrangement
        result = await arrange(
            "theme.mid",
            target_ensemble="quartet",
            style="classical"
        )

        # Rule-based (no LLM)
        result = await arrange("piece.mid", use_llm=False)
    """
    # Parse enums
    if isinstance(style, str):
        style = ArrangementStyle(style.lower())
    if isinstance(target_ensemble, str):
        target_ensemble = TargetEnsemble(target_ensemble.lower())

    config = ArrangerConfig(
        style=style,
        target_ensemble=target_ensemble,
        use_llm=use_llm,
        **kwargs,
    )

    arranger = get_arranger(config)
    return await arranger.arrange(midi_path, output_path)


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "BBC_INSTRUMENTS",
    "ArrangementPlan",
    "ArrangementResult",
    # Enums
    "ArrangementStyle",
    # Arranger
    "Arranger",
    # Config
    "ArrangerConfig",
    # Data classes
    "InstrumentAssignment",
    "MusicalAnalysis",
    "TargetEnsemble",
    # Functions
    "analyze_for_arrangement",
    "apply_arrangement",
    "arrange",
    "create_llm_plan",
    "create_rule_based_plan",
    "get_arranger",
    "get_suitable_instruments",
]
