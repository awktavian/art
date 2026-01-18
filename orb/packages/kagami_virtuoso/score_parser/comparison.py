"""Compare OMR output against reference MIDI files.

Provides accuracy metrics and detailed comparison reports for validating
OMR quality against known-good expressive MIDI files.

Metrics:
    - Note accuracy: Correct pitches at correct times
    - Timing accuracy: How close note timings are
    - Missing notes: Notes in reference but not in OMR
    - Extra notes: Notes in OMR but not in reference
    - Structural match: Same measures, parts, voices

Usage:
    >>> from kagami_virtuoso.score_parser.comparison import compare_midi_files
    >>> report = compare_midi_files("omr_output.mid", "reference.mid")
    >>> print(f"Note accuracy: {report.note_accuracy:.1%}")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .omr_engine import OMRResult

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class NoteMatch:
    """A matched pair of notes between OMR and reference."""

    omr_pitch: int
    ref_pitch: int
    omr_start: float
    ref_start: float
    omr_duration: float
    ref_duration: float
    pitch_match: bool
    timing_error: float  # In beats


@dataclass
class ComparisonReport:
    """Detailed comparison report between OMR and reference MIDI.

    Attributes:
        omr_path: Path to OMR MIDI file.
        reference_path: Path to reference MIDI file.
        note_accuracy: Percentage of notes correctly transcribed.
        timing_accuracy: Average timing error in beats.
        pitch_errors: Number of wrong pitches.
        timing_errors: Number of notes with timing > threshold.
        missing_notes: Notes in reference but not in OMR.
        extra_notes: Notes in OMR but not in reference.
        structural_match: Whether overall structure matches.
        omr_note_count: Total notes in OMR output.
        ref_note_count: Total notes in reference.
        matched_notes: List of matched note pairs.
        unmatched_omr: Notes only in OMR.
        unmatched_ref: Notes only in reference.
    """

    omr_path: Path | None = None
    reference_path: Path | None = None
    note_accuracy: float = 0.0
    timing_accuracy: float = 0.0
    pitch_errors: int = 0
    timing_errors: int = 0
    missing_notes: int = 0
    extra_notes: int = 0
    structural_match: bool = False
    omr_note_count: int = 0
    ref_note_count: int = 0
    matched_notes: list[NoteMatch] = field(default_factory=list)
    unmatched_omr: list[tuple[int, float, float]] = field(
        default_factory=list
    )  # pitch, start, duration
    unmatched_ref: list[tuple[int, float, float]] = field(default_factory=list)

    @property
    def precision(self) -> float:
        """Precision: What fraction of OMR notes are correct."""
        if self.omr_note_count == 0:
            return 0.0
        return len(self.matched_notes) / self.omr_note_count

    @property
    def recall(self) -> float:
        """Recall: What fraction of reference notes were found."""
        if self.ref_note_count == 0:
            return 0.0
        return len(self.matched_notes) / self.ref_note_count

    @property
    def f1_score(self) -> float:
        """F1 score: Harmonic mean of precision and recall."""
        if self.precision + self.recall == 0:
            return 0.0
        return 2 * (self.precision * self.recall) / (self.precision + self.recall)

    def summary(self) -> str:
        """Generate a human-readable summary."""
        lines = [
            "=" * 50,
            "OMR Comparison Report",
            "=" * 50,
            f"OMR Notes: {self.omr_note_count}",
            f"Reference Notes: {self.ref_note_count}",
            "",
            f"Note Accuracy: {self.note_accuracy:.1%}",
            f"Precision: {self.precision:.1%}",
            f"Recall: {self.recall:.1%}",
            f"F1 Score: {self.f1_score:.3f}",
            "",
            f"Timing Accuracy: {self.timing_accuracy:.3f} beats avg error",
            f"Pitch Errors: {self.pitch_errors}",
            f"Timing Errors: {self.timing_errors} (>0.125 beats off)",
            f"Missing Notes: {self.missing_notes}",
            f"Extra Notes: {self.extra_notes}",
            f"Structural Match: {'Yes' if self.structural_match else 'No'}",
            "=" * 50,
        ]
        return "\n".join(lines)


# =============================================================================
# Note Extraction
# =============================================================================


@dataclass
class SimpleNote:
    """Simplified note for comparison."""

    pitch: int
    start: float
    duration: float
    track: int = 0

    def __hash__(self) -> int:
        return hash((self.pitch, round(self.start, 3)))


def extract_notes_from_midi(midi_path: Path) -> list[SimpleNote]:
    """Extract notes from a MIDI file.

    Args:
        midi_path: Path to MIDI file.

    Returns:
        List of SimpleNote objects.
    """
    import pretty_midi

    midi = pretty_midi.PrettyMIDI(str(midi_path))
    notes = []

    for track_idx, instrument in enumerate(midi.instruments):
        if instrument.is_drum:
            continue

        for note in instrument.notes:
            # Convert time to beats (assuming 120 BPM default)
            tempo = 120.0
            if midi.get_tempo_changes()[1].size > 0:
                tempo = midi.get_tempo_changes()[1][0]

            start_beats = note.start * tempo / 60.0
            duration_beats = (note.end - note.start) * tempo / 60.0

            notes.append(
                SimpleNote(
                    pitch=note.pitch,
                    start=start_beats,
                    duration=duration_beats,
                    track=track_idx,
                )
            )

    return notes


def extract_notes_from_omr(result: OMRResult) -> list[SimpleNote]:
    """Extract notes from an OMR result.

    Args:
        result: OMR recognition result.

    Returns:
        List of SimpleNote objects.
    """
    notes = []
    for note in result.notes:
        notes.append(
            SimpleNote(
                pitch=note.pitch,
                start=note.start_beat,
                duration=note.duration,
                track=note.staff,
            )
        )
    return notes


# =============================================================================
# Comparison Algorithm
# =============================================================================


def match_notes(
    omr_notes: list[SimpleNote],
    ref_notes: list[SimpleNote],
    timing_tolerance: float = 0.25,  # Quarter beat tolerance
    pitch_tolerance: int = 0,  # Must be exact pitch
) -> tuple[list[NoteMatch], list[SimpleNote], list[SimpleNote]]:
    """Match OMR notes to reference notes using Hungarian algorithm.

    Args:
        omr_notes: Notes from OMR output.
        ref_notes: Notes from reference MIDI.
        timing_tolerance: Maximum timing difference (in beats) for a match.
        pitch_tolerance: Maximum pitch difference (in semitones) for a match.

    Returns:
        Tuple of (matched_pairs, unmatched_omr, unmatched_ref).
    """
    matched: list[NoteMatch] = []
    unmatched_omr: list[SimpleNote] = []
    unmatched_ref: list[SimpleNote] = list(ref_notes)  # Copy for tracking

    # Sort both by start time
    omr_sorted = sorted(omr_notes, key=lambda n: (n.start, n.pitch))
    ref_sorted = sorted(ref_notes, key=lambda n: (n.start, n.pitch))

    # Create a map of ref notes for faster lookup
    ref_by_time: dict[int, list[SimpleNote]] = {}
    for note in ref_sorted:
        time_key = int(note.start * 4)  # Quantize to 16th notes
        if time_key not in ref_by_time:
            ref_by_time[time_key] = []
        ref_by_time[time_key].append(note)

    # Match each OMR note to nearest reference note
    for omr_note in omr_sorted:
        best_match = None
        best_distance = float("inf")

        # Look in nearby time buckets
        time_key = int(omr_note.start * 4)
        for offset in range(-1, 2):  # Check adjacent buckets
            bucket = ref_by_time.get(time_key + offset, [])
            for ref_note in bucket:
                if ref_note not in unmatched_ref:
                    continue  # Already matched

                # Calculate distance
                time_diff = abs(omr_note.start - ref_note.start)
                pitch_diff = abs(omr_note.pitch - ref_note.pitch)

                if time_diff <= timing_tolerance and pitch_diff <= pitch_tolerance:
                    distance = time_diff + pitch_diff * 0.1
                    if distance < best_distance:
                        best_distance = distance
                        best_match = ref_note

        if best_match:
            # Found a match
            unmatched_ref.remove(best_match)
            matched.append(
                NoteMatch(
                    omr_pitch=omr_note.pitch,
                    ref_pitch=best_match.pitch,
                    omr_start=omr_note.start,
                    ref_start=best_match.start,
                    omr_duration=omr_note.duration,
                    ref_duration=best_match.duration,
                    pitch_match=(omr_note.pitch == best_match.pitch),
                    timing_error=abs(omr_note.start - best_match.start),
                )
            )
        else:
            unmatched_omr.append(omr_note)

    return matched, unmatched_omr, unmatched_ref


# =============================================================================
# Main Comparison Functions
# =============================================================================


def compare_midi_files(
    omr_path: str | Path,
    reference_path: str | Path,
    timing_tolerance: float = 0.25,
) -> ComparisonReport:
    """Compare an OMR-generated MIDI file against a reference MIDI.

    Args:
        omr_path: Path to OMR output MIDI file.
        reference_path: Path to reference MIDI file.
        timing_tolerance: Maximum timing difference for note matching.

    Returns:
        ComparisonReport with detailed metrics.
    """
    omr_path = Path(omr_path)
    reference_path = Path(reference_path)

    logger.info(f"Comparing: {omr_path.name} vs {reference_path.name}")

    # Extract notes
    omr_notes = extract_notes_from_midi(omr_path)
    ref_notes = extract_notes_from_midi(reference_path)

    logger.info(f"OMR notes: {len(omr_notes)}, Reference notes: {len(ref_notes)}")

    # Match notes
    matched, unmatched_omr, unmatched_ref = match_notes(omr_notes, ref_notes, timing_tolerance)

    # Calculate metrics
    report = ComparisonReport(
        omr_path=omr_path,
        reference_path=reference_path,
        omr_note_count=len(omr_notes),
        ref_note_count=len(ref_notes),
        matched_notes=matched,
        unmatched_omr=[(n.pitch, n.start, n.duration) for n in unmatched_omr],
        unmatched_ref=[(n.pitch, n.start, n.duration) for n in unmatched_ref],
        missing_notes=len(unmatched_ref),
        extra_notes=len(unmatched_omr),
    )

    if matched:
        # Note accuracy
        correct_pitches = sum(1 for m in matched if m.pitch_match)
        report.note_accuracy = correct_pitches / len(ref_notes) if ref_notes else 0

        # Pitch errors
        report.pitch_errors = sum(1 for m in matched if not m.pitch_match)

        # Timing accuracy
        timing_errors = [m.timing_error for m in matched]
        report.timing_accuracy = sum(timing_errors) / len(timing_errors)

        # Count significant timing errors (> 1/8 beat)
        report.timing_errors = sum(1 for e in timing_errors if e > 0.125)

    # Structural match (rough check - same number of parts)
    omr_tracks = len({n.track for n in omr_notes})
    ref_tracks = len({n.track for n in ref_notes})
    report.structural_match = omr_tracks == ref_tracks

    return report


def compare_omr_result(
    omr_result: OMRResult,
    reference_path: str | Path,
    timing_tolerance: float = 0.25,
) -> ComparisonReport:
    """Compare an OMRResult directly against a reference MIDI.

    Args:
        omr_result: OMR recognition result.
        reference_path: Path to reference MIDI file.
        timing_tolerance: Maximum timing difference for note matching.

    Returns:
        ComparisonReport with detailed metrics.
    """
    reference_path = Path(reference_path)

    # Extract notes
    omr_notes = extract_notes_from_omr(omr_result)
    ref_notes = extract_notes_from_midi(reference_path)

    logger.info(f"OMR notes: {len(omr_notes)}, Reference notes: {len(ref_notes)}")

    # Match notes
    matched, unmatched_omr, unmatched_ref = match_notes(omr_notes, ref_notes, timing_tolerance)

    # Build report
    report = ComparisonReport(
        reference_path=reference_path,
        omr_note_count=len(omr_notes),
        ref_note_count=len(ref_notes),
        matched_notes=matched,
        unmatched_omr=[(n.pitch, n.start, n.duration) for n in unmatched_omr],
        unmatched_ref=[(n.pitch, n.start, n.duration) for n in unmatched_ref],
        missing_notes=len(unmatched_ref),
        extra_notes=len(unmatched_omr),
    )

    if matched:
        correct_pitches = sum(1 for m in matched if m.pitch_match)
        report.note_accuracy = correct_pitches / len(ref_notes) if ref_notes else 0
        report.pitch_errors = sum(1 for m in matched if not m.pitch_match)

        timing_errors = [m.timing_error for m in matched]
        report.timing_accuracy = sum(timing_errors) / len(timing_errors)
        report.timing_errors = sum(1 for e in timing_errors if e > 0.125)

    omr_tracks = len({n.track for n in omr_notes})
    ref_tracks = len({n.track for n in ref_notes})
    report.structural_match = omr_tracks == ref_tracks

    return report


def compare_beethoven_5_showcase(
    omr_result: OMRResult,
    showcase_dir: str | Path = "assets/audio/showcase/beethoven_5/temp",
) -> dict[str, ComparisonReport]:
    """Compare OMR result against all Beethoven 5th showcase MIDI files.

    Args:
        omr_result: OMR recognition result.
        showcase_dir: Directory containing expressive MIDI files.

    Returns:
        Dict mapping filename to ComparisonReport.
    """
    showcase_dir = Path(showcase_dir)
    reports = {}

    for midi_file in showcase_dir.glob("*.expr.mid"):
        try:
            report = compare_omr_result(omr_result, midi_file)
            reports[midi_file.stem] = report
            logger.info(f"{midi_file.stem}: {report.note_accuracy:.1%} accuracy")
        except Exception as e:
            logger.error(f"Failed to compare with {midi_file.name}: {e}")

    return reports


__all__ = [
    "ComparisonReport",
    "NoteMatch",
    "compare_beethoven_5_showcase",
    "compare_midi_files",
    "compare_omr_result",
    "extract_notes_from_midi",
    "extract_notes_from_omr",
]
