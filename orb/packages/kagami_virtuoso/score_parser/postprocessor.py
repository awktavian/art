"""Post-processing for OMR results.

Cleans up, validates, and enhances OMR output:
- Error correction
- Note timing alignment
- Voice separation
- Instrument assignment
- MusicXML generation
- MIDI export
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from midiutil import MIDIFile

    from .omr_engine import Note, OMRResult

logger = logging.getLogger(__name__)


@dataclass
class InstrumentPart:
    """A single instrument part from the score.

    Attributes:
        name: Instrument name.
        abbreviation: Short name.
        staff_indices: Which staves belong to this instrument.
        midi_program: General MIDI program number.
        transposition: Transposition in semitones.
    """

    name: str
    abbreviation: str
    staff_indices: list[int]
    midi_program: int = 0
    transposition: int = 0


# Standard orchestral instrument mappings
ORCHESTRAL_INSTRUMENTS = {
    "Flute": InstrumentPart("Flute", "Fl.", [], 73, 0),
    "Oboe": InstrumentPart("Oboe", "Ob.", [], 68, 0),
    "Clarinet": InstrumentPart("Clarinet in Bb", "Cl.", [], 71, -2),
    "Bassoon": InstrumentPart("Bassoon", "Bsn.", [], 70, 0),
    "Horn": InstrumentPart("Horn in F", "Hn.", [], 60, -7),
    "Trumpet": InstrumentPart("Trumpet in Bb", "Tpt.", [], 56, -2),
    "Trombone": InstrumentPart("Trombone", "Tbn.", [], 57, 0),
    "Tuba": InstrumentPart("Tuba", "Tba.", [], 58, 0),
    "Timpani": InstrumentPart("Timpani", "Timp.", [], 47, 0),
    "Violin I": InstrumentPart("Violin I", "Vln. I", [], 40, 0),
    "Violin II": InstrumentPart("Violin II", "Vln. II", [], 40, 0),
    "Viola": InstrumentPart("Viola", "Vla.", [], 41, 0),
    "Cello": InstrumentPart("Violoncello", "Vc.", [], 42, 0),
    "Bass": InstrumentPart("Contrabass", "Cb.", [], 43, 0),
}


class PostProcessor:
    """Post-process OMR results for improved accuracy.

    Applies heuristics and rules to clean up raw OMR output.

    Example:
        >>> processor = PostProcessor()
        >>> cleaned = processor.process(raw_result)
    """

    def __init__(
        self,
        quantize_timing: bool = True,
        fix_overlaps: bool = True,
        assign_instruments: bool = True,
    ) -> None:
        """Initialize the post-processor.

        Args:
            quantize_timing: Snap note timings to grid.
            fix_overlaps: Fix overlapping notes in same voice.
            assign_instruments: Try to identify instruments from context.
        """
        self.quantize_timing = quantize_timing
        self.fix_overlaps = fix_overlaps
        self.assign_instruments = assign_instruments

    def process(self, result: OMRResult) -> OMRResult:
        """Process an OMR result.

        Args:
            result: Raw OMR result.

        Returns:
            Cleaned OMR result.
        """
        # Make a copy of notes to modify
        notes = list(result.notes)

        if self.quantize_timing:
            notes = self._quantize_timing(notes)

        if self.fix_overlaps:
            notes = self._fix_overlaps(notes)

        # Update the result
        result.notes = notes
        return result

    def _quantize_timing(self, notes: list[Note], grid: float = 0.125) -> list[Note]:
        """Quantize note timings to a grid.

        Args:
            notes: List of notes.
            grid: Grid size in beats (0.125 = 32nd note).

        Returns:
            Quantized notes.
        """
        for note in notes:
            note.start_beat = round(note.start_beat / grid) * grid
            note.duration = max(grid, round(note.duration / grid) * grid)
        return notes

    def _fix_overlaps(self, notes: list[Note]) -> list[Note]:
        """Fix overlapping notes in the same voice.

        Args:
            notes: List of notes.

        Returns:
            Notes with overlaps resolved.
        """
        # Group by staff and voice
        from collections import defaultdict

        groups: dict[tuple[int, int], list[Note]] = defaultdict(list)
        for note in notes:
            groups[(note.staff, note.voice)].append(note)

        # Fix overlaps within each group
        for _key, group in groups.items():
            group.sort(key=lambda n: n.start_beat)
            for i in range(len(group) - 1):
                current = group[i]
                next_note = group[i + 1]
                # If current note extends past next note start, truncate it
                max_duration = next_note.start_beat - current.start_beat
                if current.duration > max_duration:
                    current.duration = max(0.125, max_duration)

        return notes

    def merge_pages(self, results: list[OMRResult]) -> OMRResult:
        """Merge results from multiple pages into one.

        Args:
            results: List of page results.

        Returns:
            Combined result.
        """
        if not results:
            from .omr_engine import OMRResult

            return OMRResult(page_number=0)

        # Calculate beat offset for each page
        beat_offset = 0.0
        all_notes = []
        all_rests = []

        for result in results:
            # Find max beat in this page
            max_beat = 0.0
            for note in result.notes:
                all_notes.append(
                    type(note)(
                        pitch=note.pitch,
                        start_beat=note.start_beat + beat_offset,
                        duration=note.duration,
                        voice=note.voice,
                        staff=note.staff,
                        velocity=note.velocity,
                    )
                )
                max_beat = max(max_beat, note.start_beat + note.duration)

            for rest in result.rests:
                all_rests.append(
                    type(rest)(
                        start_beat=rest.start_beat + beat_offset,
                        duration=rest.duration,
                        voice=rest.voice,
                        staff=rest.staff,
                    )
                )
                max_beat = max(max_beat, rest.start_beat + rest.duration)

            beat_offset += max_beat

        from .omr_engine import OMRResult

        return OMRResult(
            page_number=0,
            notes=all_notes,
            rests=all_rests,
            time_signatures=results[0].time_signatures if results else [],
            key_signatures=results[0].key_signatures if results else [],
            tempos=results[0].tempos if results else [],
            confidence=sum(r.confidence for r in results) / len(results),
        )


class MIDIExporter:
    """Export OMR results to MIDI files.

    Supports:
    - Basic MIDI export (one track per staff)
    - Instrument-mapped export with BBC SO keyswitches
    - CC data for dynamics (CC1) and expression (CC11)

    Example:
        >>> exporter = MIDIExporter()
        >>> exporter.export(result, "output.mid")

        # With instrument mapping
        >>> exporter.export_with_instruments(result, "output.mid", mappings)
    """

    # BBC Symphony Orchestra CC constants
    CC_DYNAMICS = 1  # CC1: Controls timbre/dynamics layer
    CC_EXPRESSION = 11  # CC11: Expression/volume
    CC_VIBRATO = 21  # CC21: Vibrato intensity

    def __init__(self, default_tempo: int = 120) -> None:
        """Initialize the MIDI exporter.

        Args:
            default_tempo: Default tempo in BPM.
        """
        self.default_tempo = default_tempo

    def export(self, result: OMRResult, output_path: str | Path) -> Path:
        """Export OMR result to MIDI file.

        Args:
            result: OMR result to export.
            output_path: Path for output MIDI file.

        Returns:
            Path to the created MIDI file.
        """
        from midiutil import MIDIFile

        output_path = Path(output_path)

        # Determine number of tracks (one per staff)
        staff_indices = {note.staff for note in result.notes}
        num_tracks = max(staff_indices) + 1 if staff_indices else 1

        midi = MIDIFile(num_tracks)

        # Set tempo
        tempo = self.default_tempo
        if result.tempos:
            tempo = result.tempos[0].bpm
        midi.addTempo(0, 0, tempo)

        # Add notes
        for note in result.notes:
            track = min(note.staff, num_tracks - 1)
            midi.addNote(
                track=track,
                channel=track % 16,
                pitch=note.pitch,
                time=note.start_beat,
                duration=note.duration,
                volume=note.velocity,
            )

        # Write to file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            midi.writeFile(f)

        logger.info(f"Exported MIDI to {output_path}")
        return output_path

    def export_with_instruments(
        self,
        result: OMRResult,
        output_path: str | Path,
        instrument_mappings: list,
        add_expression: bool = True,
    ) -> Path:
        """Export OMR result to MIDI with instrument mappings.

        Creates a multi-track MIDI with:
        - One track per instrument mapping
        - GM program changes for each instrument
        - CC1/CC11 expression data based on velocity
        - BBC SO compatible keyswitch commands

        Args:
            result: OMR result to export.
            output_path: Path for output MIDI file.
            instrument_mappings: List of InstrumentMapping objects.
            add_expression: Whether to add CC1/CC11 expression curves.

        Returns:
            Path to the created MIDI file.
        """
        from midiutil import MIDIFile

        output_path = Path(output_path)

        # One track per instrument
        num_tracks = len(instrument_mappings)
        if num_tracks == 0:
            return self.export(result, output_path)

        midi = MIDIFile(num_tracks)

        # Set tempo
        tempo = self.default_tempo
        if result.tempos:
            tempo = result.tempos[0].bpm
        midi.addTempo(0, 0, tempo)

        # Create staff-to-track mapping
        staff_to_track: dict[
            int, tuple[int, int, int]
        ] = {}  # staff -> (track, channel, transposition)
        for track_idx, mapping in enumerate(instrument_mappings):
            channel = track_idx % 16
            # Skip channel 10 (drums)
            if channel == 9:
                channel = track_idx % 15
                if channel >= 9:
                    channel += 1

            # Set track name
            midi.addTrackName(track_idx, 0, mapping.name)

            # Set program change
            midi.addProgramChange(track_idx, channel, 0, mapping.gm_program)

            # Add initial CC values for BBC SO
            if add_expression:
                midi.addControllerEvent(track_idx, channel, 0, self.CC_DYNAMICS, 80)
                midi.addControllerEvent(track_idx, channel, 0, self.CC_EXPRESSION, 100)

            # Map all staffs in this instrument to this track
            for staff_idx in mapping.staff_indices:
                staff_to_track[staff_idx] = (track_idx, channel, mapping.transposition)

            logger.debug(
                f"Track {track_idx}: {mapping.name} (GM {mapping.gm_program}, "
                f"staffs {mapping.staff_indices})"
            )

        # Group notes by staff
        from collections import defaultdict

        staff_notes: dict[int, list[Note]] = defaultdict(list)
        for note in result.notes:
            staff_notes[note.staff].append(note)

        # Add notes with expression curves
        for staff_idx, notes in staff_notes.items():
            if staff_idx not in staff_to_track:
                # Unmapped staff - add to track 0
                track_idx = 0
                channel = 0
                transposition = 0
                logger.warning(f"Staff {staff_idx} not mapped, using track 0")
            else:
                track_idx, channel, transposition = staff_to_track[staff_idx]

            # Sort notes by time
            notes = sorted(notes, key=lambda n: n.start_beat)

            # Add expression data based on note velocities
            if add_expression:
                self._add_expression_curve(midi, track_idx, channel, notes)

            # Add notes
            for note in notes:
                pitch = note.pitch + transposition
                midi.addNote(
                    track=track_idx,
                    channel=channel,
                    pitch=pitch,
                    time=note.start_beat,
                    duration=note.duration,
                    volume=note.velocity,
                )

        # Write to file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            midi.writeFile(f)

        logger.info(f"Exported MIDI with {num_tracks} instruments to {output_path}")
        return output_path

    def _add_expression_curve(
        self,
        midi: MIDIFile,
        track: int,
        channel: int,
        notes: list[Note],
    ) -> None:
        """Add CC1/CC11 expression curves based on note velocities.

        Creates smooth expression curves that BBC SO can use for
        dynamics layer crossfades.

        Args:
            midi: MIDIFile to add CC events to.
            track: Track index.
            channel: MIDI channel.
            notes: Notes to analyze for expression.
        """
        if not notes:
            return

        # Sample expression every beat
        max_time = max(n.start_beat + n.duration for n in notes)
        sample_interval = 1.0  # Sample every beat

        time = 0.0
        while time <= max_time:
            # Find notes active at this time
            active_notes = [n for n in notes if n.start_beat <= time < n.start_beat + n.duration]

            if active_notes:
                # Use max velocity of active notes
                max_vel = max(n.velocity for n in active_notes)

                # Map velocity to CC1 (dynamics) - center around 80
                cc1_value = min(127, max(1, int(max_vel * 0.7) + 20))

                # CC11 (expression) - slightly higher
                cc11_value = min(127, max(1, int(max_vel * 0.9)))

                midi.addControllerEvent(track, channel, time, self.CC_DYNAMICS, cc1_value)
                midi.addControllerEvent(track, channel, time, self.CC_EXPRESSION, cc11_value)

            time += sample_interval


class MusicXMLExporter:
    """Export OMR results to MusicXML files.

    Example:
        >>> exporter = MusicXMLExporter()
        >>> exporter.export(result, "output.musicxml")
    """

    def export(self, result: OMRResult, output_path: str | Path) -> Path:
        """Export OMR result to MusicXML file.

        Args:
            result: OMR result to export.
            output_path: Path for output file.

        Returns:
            Path to the created file.
        """
        output_path = Path(output_path)

        # If we have raw MusicXML, write it directly
        if result.musicxml:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w") as f:
                f.write(result.musicxml)
            logger.info(f"Exported MusicXML to {output_path}")
            return output_path

        # Otherwise, generate from notes using music21
        import music21

        score = music21.stream.Score()

        # Group notes by staff
        from collections import defaultdict

        staff_notes: dict[int, list] = defaultdict(list)
        for note in result.notes:
            staff_notes[note.staff].append(note)

        # Create parts
        for staff_idx in sorted(staff_notes.keys()):
            part = music21.stream.Part()
            notes = sorted(staff_notes[staff_idx], key=lambda n: n.start_beat)

            for note in notes:
                m21_note = music21.note.Note(note.pitch)
                m21_note.quarterLength = note.duration
                m21_note.offset = note.start_beat
                part.append(m21_note)

            score.append(part)

        # Write to file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        score.write("musicxml", fp=str(output_path))
        logger.info(f"Exported MusicXML to {output_path}")
        return output_path
