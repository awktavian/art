"""OMR Engine - Neural network based music recognition.

Wraps multiple OMR backends (homr, oemer, Audiveris) with a unified interface.
Optimized for orchestral full scores with multi-staff systems.

Primary backend: homr (transformer-based, best accuracy)
Fallback: oemer (CNN-based, faster but less accurate)
"""

from __future__ import annotations

import logging
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from PIL import Image

logger = logging.getLogger(__name__)


class OMRBackend(Enum):
    """Available OMR backends."""

    HOMR = "homr"
    OEMER = "oemer"
    AUDIVERIS = "audiveris"
    AUTO = "auto"  # Automatically select best backend


@dataclass
class Note:
    """A single musical note.

    Attributes:
        pitch: MIDI pitch number (60 = middle C).
        start_beat: Start time in beats.
        duration: Duration in beats.
        voice: Voice number within staff.
        staff: Staff index.
        velocity: MIDI velocity (1-127).
    """

    pitch: int
    start_beat: float
    duration: float
    voice: int = 0
    staff: int = 0
    velocity: int = 80


@dataclass
class Rest:
    """A musical rest."""

    start_beat: float
    duration: float
    voice: int = 0
    staff: int = 0


@dataclass
class TimeSignature:
    """Time signature."""

    numerator: int
    denominator: int
    measure: int = 0


@dataclass
class KeySignature:
    """Key signature."""

    fifths: int
    mode: str = "major"
    measure: int = 0


@dataclass
class Tempo:
    """Tempo marking."""

    bpm: float
    beat_unit: int = 4
    measure: int = 0
    beat: float = 0


@dataclass
class Dynamic:
    """Dynamic marking."""

    marking: str
    measure: int
    beat: float
    staff: int = 0


@dataclass
class OMRResult:
    """Result of OMR recognition on a single page.

    Contains all musical elements detected on the page.
    """

    page_number: int
    notes: list[Note] = field(default_factory=list)
    rests: list[Rest] = field(default_factory=list)
    time_signatures: list[TimeSignature] = field(default_factory=list)
    key_signatures: list[KeySignature] = field(default_factory=list)
    tempos: list[Tempo] = field(default_factory=list)
    dynamics: list[Dynamic] = field(default_factory=list)
    musicxml: str | None = None
    musicxml_path: Path | None = None
    errors: list[str] = field(default_factory=list)
    confidence: float = 0.0
    num_staves: int = 0
    num_voices: int = 0

    @property
    def note_count(self) -> int:
        """Total number of notes detected."""
        return len(self.notes)

    def to_midi_events(self) -> list[dict[str, Any]]:
        """Convert notes to MIDI event format."""
        events = []
        for note in self.notes:
            events.append(
                {
                    "type": "note_on",
                    "pitch": note.pitch,
                    "velocity": note.velocity,
                    "time": note.start_beat,
                }
            )
            events.append(
                {
                    "type": "note_off",
                    "pitch": note.pitch,
                    "velocity": 0,
                    "time": note.start_beat + note.duration,
                }
            )
        events.sort(key=lambda e: (e["time"], e["type"] == "note_on"))
        return events


class BaseOMRBackend(ABC):
    """Abstract base class for OMR backends."""

    @abstractmethod
    def recognize(self, image: Image.Image, output_dir: Path | None = None) -> OMRResult:
        """Recognize music in an image."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this backend is available."""
        pass


def _patch_homr_title_detection() -> None:
    """Patch homr's title detection to handle None OCR results."""
    try:
        import homr.title_detection

        original_func = homr.title_detection._detect_title_task

        def patched_detect_title_task(debug, top_staff):
            try:
                return original_func(debug, top_staff)
            except (TypeError, ValueError, AttributeError):
                return ""

        homr.title_detection._detect_title_task = patched_detect_title_task
        logger.debug("Patched homr.title_detection")
    except Exception as e:
        logger.warning(f"Could not patch homr title detection: {e}")


class HomrBackend(BaseOMRBackend):
    """Homr deep learning OMR backend.

    Uses transformer models for high-accuracy music recognition.
    Best for printed scores, orchestral full scores.

    On Apple Silicon, uses CoreMLExecutionProvider for GPU acceleration.
    """

    def __init__(self, tempo: int = 120, use_mps: bool = True) -> None:
        """Initialize the Homr backend.

        Args:
            tempo: Default tempo in BPM for output.
            use_mps: Whether to apply MPS/CoreML patches on Apple Silicon.
        """
        self.tempo = tempo
        self._patched = False
        self._mps_patched = False

        # Apply MPS/CoreML patches for Apple Silicon acceleration
        if use_mps:
            self._apply_mps_patches()

    def is_available(self) -> bool:
        """Check if homr is installed."""
        try:
            import homr

            return True
        except ImportError:
            return False

    def _apply_mps_patches(self) -> None:
        """Apply MPS/CoreML patches for Apple Silicon acceleration."""
        if self._mps_patched:
            return

        try:
            from kagami_virtuoso.score_parser.mps_patch import (
                is_apple_silicon,
                patch_homr_for_mps,
            )

            if is_apple_silicon():
                patch_homr_for_mps()
                self._mps_patched = True
            else:
                logger.debug("Not Apple Silicon, skipping MPS patches")

        except ImportError as e:
            logger.warning(f"Could not import mps_patch module: {e}")
        except Exception as e:
            logger.warning(f"Failed to apply MPS patches: {e}")

    def _ensure_patched(self) -> None:
        """Ensure title detection is patched."""
        if not self._patched:
            _patch_homr_title_detection()
            self._patched = True

    def recognize(self, image: Image.Image, output_dir: Path | None = None) -> OMRResult:
        """Recognize music using homr.

        Args:
            image: PIL Image of a score page.
            output_dir: Optional directory for output files.

        Returns:
            OMRResult with detected musical elements.
        """
        self._ensure_patched()

        from homr.main import ProcessingConfig, process_image
        from homr.xml_generator import XmlGeneratorArguments

        # Save image to temp file
        if output_dir:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            temp_path = output_dir / "input.png"
            image.save(str(temp_path))
        else:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                image.save(f.name)
                temp_path = Path(f.name)

        try:
            config = ProcessingConfig(
                enable_debug=False,
                enable_cache=False,
                write_staff_positions=False,
                read_staff_positions=False,
                selected_staff=-1,
            )

            xml_args = XmlGeneratorArguments(
                large_page=False,
                metronome=None,
                tempo=self.tempo,
            )

            logger.info(f"Running homr on {temp_path}")
            result_staffs = process_image(str(temp_path), config, xml_args)

            # Find the output MusicXML file
            musicxml_path = temp_path.with_suffix(".musicxml")

            if musicxml_path.exists():
                with open(musicxml_path) as f:
                    musicxml_content = f.read()

                result = self._parse_musicxml(musicxml_content, page_number=0)
                result.musicxml_path = musicxml_path
                result.num_voices = len(result_staffs)
                result.num_staves = sum(staff.number_of_new_lines() for staff in result_staffs)

                logger.info(
                    f"Homr recognized {result.note_count} notes across {result.num_voices} voices"
                )
                return result
            else:
                return OMRResult(
                    page_number=0,
                    errors=["No MusicXML output from homr"],
                )

        except Exception as e:
            logger.error(f"Homr error: {e}")
            import traceback

            traceback.print_exc()
            return OMRResult(page_number=0, errors=[str(e)])

        finally:
            # Cleanup temp file only if we created it
            if not output_dir and temp_path.exists():
                temp_path.unlink()
                musicxml_path = temp_path.with_suffix(".musicxml")
                if musicxml_path.exists():
                    musicxml_path.unlink()

    def _parse_musicxml(self, musicxml_content: str, page_number: int) -> OMRResult:
        """Parse MusicXML into OMRResult."""
        try:
            import music21

            score = music21.converter.parse(musicxml_content)
            result = OMRResult(page_number=page_number, musicxml=musicxml_content)

            for part_idx, part in enumerate(score.parts):
                for element in part.flatten().notesAndRests:
                    if isinstance(element, music21.note.Note):
                        result.notes.append(
                            Note(
                                pitch=element.pitch.midi,
                                start_beat=float(element.offset),
                                duration=float(element.duration.quarterLength),
                                staff=part_idx,
                                velocity=80,
                            )
                        )
                    elif isinstance(element, music21.chord.Chord):
                        for pitch in element.pitches:
                            result.notes.append(
                                Note(
                                    pitch=pitch.midi,
                                    start_beat=float(element.offset),
                                    duration=float(element.duration.quarterLength),
                                    staff=part_idx,
                                    velocity=80,
                                )
                            )
                    elif isinstance(element, music21.note.Rest):
                        result.rests.append(
                            Rest(
                                start_beat=float(element.offset),
                                duration=float(element.duration.quarterLength),
                                staff=part_idx,
                            )
                        )

            # Extract time signatures
            for ts in score.flatten().getElementsByClass(music21.meter.TimeSignature):
                result.time_signatures.append(
                    TimeSignature(
                        numerator=ts.numerator,
                        denominator=ts.denominator,
                        measure=int(ts.measureNumber) if ts.measureNumber else 0,
                    )
                )

            # Extract key signatures
            for ks in score.flatten().getElementsByClass(music21.key.KeySignature):
                result.key_signatures.append(
                    KeySignature(
                        fifths=ks.sharps,
                        mode="major",
                        measure=int(ks.measureNumber) if ks.measureNumber else 0,
                    )
                )

            result.confidence = 0.85
            return result

        except Exception as e:
            logger.error(f"MusicXML parse error: {e}")
            return OMRResult(
                page_number=page_number,
                musicxml=musicxml_content,
                errors=[f"MusicXML parse error: {e}"],
            )


class OemerBackend(BaseOMRBackend):
    """Oemer deep learning OMR backend (fallback).

    Note: May have compatibility issues with newer NumPy versions.
    """

    def is_available(self) -> bool:
        """Check if oemer is installed and working."""
        try:
            # Check numpy compatibility
            import numpy as np
            import oemer

            if not hasattr(np, "int"):
                logger.warning("Oemer incompatible with NumPy 2.x")
                return False
            return True
        except ImportError:
            return False

    def recognize(self, image: Image.Image, output_dir: Path | None = None) -> OMRResult:
        """Recognize music using oemer."""
        return OMRResult(
            page_number=0,
            errors=["Oemer backend not fully implemented"],
        )


class OMREngine:
    """Unified OMR engine with multiple backend support.

    Provides a consistent interface for music recognition
    regardless of the underlying OMR library.

    Example:
        >>> engine = OMREngine(backend=OMRBackend.HOMR)
        >>> result = engine.recognize(image)
        >>> print(f"Found {result.note_count} notes")
    """

    def __init__(
        self,
        backend: OMRBackend = OMRBackend.AUTO,
        tempo: int = 120,
    ) -> None:
        """Initialize the OMR engine.

        Args:
            backend: Which OMR backend to use.
            tempo: Default tempo for output.
        """
        self.backend_type = backend
        self.tempo = tempo
        self._backend: BaseOMRBackend | None = None
        self._initialize_backend()

    def _initialize_backend(self) -> None:
        """Initialize the selected backend."""
        if self.backend_type in (OMRBackend.HOMR, OMRBackend.AUTO):
            homr = HomrBackend(tempo=self.tempo)
            if homr.is_available():
                self._backend = homr
                logger.info("Using Homr OMR backend (transformer-based)")
                return

        if self.backend_type in (OMRBackend.OEMER, OMRBackend.AUTO):
            oemer = OemerBackend()
            if oemer.is_available():
                self._backend = oemer
                logger.info("Using Oemer OMR backend (CNN-based)")
                return

        if self._backend is None:
            raise RuntimeError("No OMR backend available. Install homr: pip install homr")

    def recognize(
        self,
        image: Image.Image,
        page_number: int = 0,
        output_dir: Path | None = None,
    ) -> OMRResult:
        """Recognize music in an image.

        Args:
            image: PIL Image of a score page.
            page_number: Page number for tracking.
            output_dir: Optional directory for output files.

        Returns:
            OMRResult with detected musical elements.
        """
        if self._backend is None:
            raise RuntimeError("No OMR backend initialized")

        result = self._backend.recognize(image, output_dir)
        result.page_number = page_number
        return result

    def recognize_batch(
        self,
        images: list[Image.Image],
        start_page: int = 0,
        output_dir: Path | None = None,
    ) -> list[OMRResult]:
        """Recognize music in multiple images.

        Args:
            images: List of PIL Images.
            start_page: Starting page number.
            output_dir: Optional directory for output files.

        Returns:
            List of OMRResults.
        """
        results = []
        for i, image in enumerate(images):
            page_num = start_page + i
            logger.info(f"Processing page {page_num + 1}/{len(images)}")

            page_output_dir = None
            if output_dir:
                page_output_dir = Path(output_dir) / f"page_{page_num:04d}"

            result = self.recognize(image, page_number=page_num, output_dir=page_output_dir)
            results.append(result)

        return results

    @property
    def backend_name(self) -> str:
        """Get the name of the active backend."""
        if self._backend is None:
            return "none"
        return self._backend.__class__.__name__
