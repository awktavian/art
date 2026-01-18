"""Ensemble OMR: Multiple backends with result fusion.

Runs multiple OMR backends on the same image and combines their results
using voting/fusion strategies to improve accuracy.

The key insight: different backends have different failure modes.
By combining them, we can often get better results than any single backend.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL import Image

    from ..omr_engine import Note, OMRResult

logger = logging.getLogger(__name__)


class FusionStrategy(Enum):
    """Strategies for combining multiple OMR results."""

    VOTE = "vote"  # Accept notes that appear in multiple backends
    BEST_CONFIDENCE = "best_confidence"  # Use result with highest confidence
    UNION = "union"  # Include all detected notes
    INTERSECTION = "intersection"  # Only notes all backends agree on


@dataclass
class NoteMatch:
    """A note detected by one or more backends."""

    pitch: int
    start_beat: float
    duration: float
    detections: list[tuple[str, float]]  # (backend_name, confidence)

    @property
    def vote_count(self) -> int:
        return len(self.detections)

    @property
    def avg_confidence(self) -> float:
        if not self.detections:
            return 0.0
        return sum(c for _, c in self.detections) / len(self.detections)


@dataclass
class EnsembleResult:
    """Result of ensemble OMR processing."""

    notes: list[Note]
    backend_results: dict[str, OMRResult]
    agreement_score: float  # 0-1, how much backends agreed
    fusion_strategy: FusionStrategy
    confidence: float

    @property
    def note_count(self) -> int:
        return len(self.notes)


class EnsembleOMR:
    """Run multiple OMR backends and fuse results.

    Example:
        >>> ensemble = EnsembleOMR(backends=["homr", "audiveris"])
        >>> result = await ensemble.recognize(image)
        >>> print(f"Agreement: {result.agreement_score:.1%}")
    """

    # Tolerance for matching notes between backends
    PITCH_TOLERANCE = 0  # Must match exactly
    TIME_TOLERANCE = 0.125  # 32nd note tolerance
    DURATION_TOLERANCE = 0.25  # Quarter note tolerance

    def __init__(
        self,
        backends: list[str] | None = None,
        fusion_strategy: FusionStrategy = FusionStrategy.VOTE,
        min_votes: int = 1,
    ) -> None:
        """Initialize ensemble OMR.

        Args:
            backends: List of backend names to use (default: all available).
            fusion_strategy: How to combine results.
            min_votes: Minimum votes needed to accept a note (for VOTE strategy).
        """
        self.backend_names = backends or ["homr"]
        self.fusion_strategy = fusion_strategy
        self.min_votes = min_votes
        self._backends: dict = {}
        self._initialize_backends()

    def _initialize_backends(self) -> None:
        """Initialize requested backends."""
        from ..omr_engine import HomrBackend, OemerBackend

        available = {
            "homr": HomrBackend,
            "oemer": OemerBackend,
            # "audiveris": AudiverisBackend,  # TODO: Implement
            # "smt": SMTBackend,  # TODO: Implement
        }

        for name in self.backend_names:
            if name in available:
                try:
                    backend = available[name]()
                    if backend.is_available():
                        self._backends[name] = backend
                        logger.info(f"Initialized {name} backend")
                    else:
                        logger.warning(f"{name} backend not available")
                except Exception as e:
                    logger.warning(f"Failed to initialize {name}: {e}")

        if not self._backends:
            raise RuntimeError("No OMR backends available")

    async def recognize(
        self,
        image: Image.Image,
        page_number: int = 0,
    ) -> EnsembleResult:
        """Run all backends and fuse results.

        Args:
            image: PIL Image of score page.
            page_number: Page number for tracking.

        Returns:
            EnsembleResult with fused notes.
        """
        # Run all backends (could be parallel with proper async backends)
        backend_results: dict[str, OMRResult] = {}

        for name, backend in self._backends.items():
            try:
                logger.info(f"Running {name} backend...")
                result = backend.recognize(image)
                backend_results[name] = result
                logger.info(f"{name}: {result.note_count} notes detected")
            except Exception as e:
                logger.error(f"{name} failed: {e}")

        if not backend_results:
            return EnsembleResult(
                notes=[],
                backend_results={},
                agreement_score=0.0,
                fusion_strategy=self.fusion_strategy,
                confidence=0.0,
            )

        # Fuse results
        fused_notes, agreement = self._fuse_results(backend_results)

        # Calculate overall confidence
        confidences = [r.confidence for r in backend_results.values() if r.confidence > 0]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.5

        return EnsembleResult(
            notes=fused_notes,
            backend_results=backend_results,
            agreement_score=agreement,
            fusion_strategy=self.fusion_strategy,
            confidence=avg_confidence * agreement,
        )

    def _fuse_results(self, backend_results: dict[str, OMRResult]) -> tuple[list[Note], float]:
        """Fuse results from multiple backends.

        Args:
            backend_results: Results from each backend.

        Returns:
            Tuple of (fused notes, agreement score).
        """
        if self.fusion_strategy == FusionStrategy.BEST_CONFIDENCE:
            return self._fuse_best_confidence(backend_results)
        elif self.fusion_strategy == FusionStrategy.UNION:
            return self._fuse_union(backend_results)
        elif self.fusion_strategy == FusionStrategy.INTERSECTION:
            return self._fuse_intersection(backend_results)
        else:  # VOTE
            return self._fuse_vote(backend_results)

    def _fuse_vote(self, backend_results: dict[str, OMRResult]) -> tuple[list[Note], float]:
        """Fuse using voting: accept notes that appear in multiple backends.

        Args:
            backend_results: Results from each backend.

        Returns:
            Tuple of (fused notes, agreement score).
        """
        # Collect all notes with their sources
        all_matches: list[NoteMatch] = []

        for name, result in backend_results.items():
            for note in result.notes:
                # Try to match with existing
                matched = False
                for match in all_matches:
                    if self._notes_match(note, match):
                        match.detections.append((name, result.confidence))
                        matched = True
                        break

                if not matched:
                    # New note
                    all_matches.append(
                        NoteMatch(
                            pitch=note.pitch,
                            start_beat=note.start_beat,
                            duration=note.duration,
                            detections=[(name, result.confidence)],
                        )
                    )

        # Filter by vote count
        from ..omr_engine import Note

        fused = []
        total_matches = len(all_matches)
        agreed_matches = 0

        for match in all_matches:
            if match.vote_count >= self.min_votes:
                fused.append(
                    Note(
                        pitch=match.pitch,
                        start_beat=match.start_beat,
                        duration=match.duration,
                        velocity=int(80 * match.avg_confidence),
                    )
                )
                if match.vote_count > 1:
                    agreed_matches += 1

        # Agreement score: proportion of notes that multiple backends agreed on
        agreement = agreed_matches / total_matches if total_matches > 0 else 0.0

        return fused, agreement

    def _fuse_best_confidence(
        self, backend_results: dict[str, OMRResult]
    ) -> tuple[list[Note], float]:
        """Use result from backend with highest confidence.

        Args:
            backend_results: Results from each backend.

        Returns:
            Tuple of (notes, agreement score).
        """
        best_name = None
        best_confidence = -1

        for name, result in backend_results.items():
            if result.confidence > best_confidence:
                best_confidence = result.confidence
                best_name = name

        if best_name and best_name in backend_results:
            result = backend_results[best_name]
            return list(result.notes), 1.0

        return [], 0.0

    def _fuse_union(self, backend_results: dict[str, OMRResult]) -> tuple[list[Note], float]:
        """Include all detected notes (after deduplication).

        Args:
            backend_results: Results from each backend.

        Returns:
            Tuple of (notes, agreement score).
        """
        # Use vote fusion but with min_votes=1
        original_min = self.min_votes
        self.min_votes = 1
        result = self._fuse_vote(backend_results)
        self.min_votes = original_min
        return result

    def _fuse_intersection(self, backend_results: dict[str, OMRResult]) -> tuple[list[Note], float]:
        """Only include notes that all backends agree on.

        Args:
            backend_results: Results from each backend.

        Returns:
            Tuple of (notes, agreement score).
        """
        # Use vote fusion but require all backends
        original_min = self.min_votes
        self.min_votes = len(backend_results)
        result = self._fuse_vote(backend_results)
        self.min_votes = original_min
        return result

    def _notes_match(self, note: Note, match: NoteMatch) -> bool:
        """Check if a note matches an existing NoteMatch.

        Args:
            note: Note to check.
            match: Existing match to compare against.

        Returns:
            True if they represent the same note.
        """
        pitch_match = abs(note.pitch - match.pitch) <= self.PITCH_TOLERANCE
        time_match = abs(note.start_beat - match.start_beat) <= self.TIME_TOLERANCE
        duration_match = abs(note.duration - match.duration) <= self.DURATION_TOLERANCE

        return pitch_match and time_match and duration_match


class AudiverisBackend:
    """Audiveris OMR backend (Java subprocess).

    Audiveris is a mature open-source OMR with good handling of complex layouts.
    Requires Java and Audiveris to be installed separately.

    TODO: Full implementation.
    """

    def __init__(self, audiveris_path: str | None = None) -> None:
        """Initialize Audiveris backend.

        Args:
            audiveris_path: Path to Audiveris executable.
        """
        self.audiveris_path = audiveris_path or "audiveris"

    def is_available(self) -> bool:
        """Check if Audiveris is available."""
        import shutil

        return shutil.which(self.audiveris_path) is not None

    def recognize(self, image: Image.Image) -> OMRResult:
        """Run Audiveris on an image.

        TODO: Implement subprocess call and result parsing.
        """
        from ..omr_engine import OMRResult

        logger.warning("Audiveris backend not fully implemented")
        return OMRResult(page_number=0, errors=["Audiveris not implemented"])


class SMTBackend:
    """Sheet Music Transformer backend.

    SMT is a transformer-based OMR that handles polyphony well.
    Requires the SMT model to be installed.

    TODO: Full implementation when SMT is available.
    """

    def __init__(self) -> None:
        """Initialize SMT backend."""
        self.model = None

    def is_available(self) -> bool:
        """Check if SMT is available."""
        try:
            # import smt  # Not yet released
            return False
        except ImportError:
            return False

    def recognize(self, image: Image.Image) -> OMRResult:
        """Run SMT on an image."""
        from ..omr_engine import OMRResult

        logger.warning("SMT backend not available")
        return OMRResult(page_number=0, errors=["SMT not available"])
