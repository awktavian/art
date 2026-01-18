"""Orchestral score parser: The main entry point.

Provides a unified interface for parsing complex orchestral scores using:
1. Layout analysis to detect systems and instrument groups
2. Group-level OMR processing (divide and conquer)
3. Optional ensemble OMR for higher accuracy
4. Timeline alignment and reconstruction
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from .ensemble_omr import EnsembleOMR, FusionStrategy
from .layout_analyzer import LayoutAnalyzer, LayoutHint
from .system_detector import PageLayout, SystemDetector

if TYPE_CHECKING:
    from PIL import Image

    from ..omr_engine import Note, OMRResult

logger = logging.getLogger(__name__)

# Progress callback type
ProgressCallback = Callable[[int, int, str], None]


@dataclass
class OrchestralParseResult:
    """Result of parsing an orchestral score."""

    source_path: Path | None
    page_results: list[PageLayout]
    omr_results: list[OMRResult]
    merged_result: OMRResult | None
    parse_time_seconds: float
    strategy_used: str
    errors: list[str] = field(default_factory=list)

    @property
    def note_count(self) -> int:
        return self.merged_result.note_count if self.merged_result else 0

    @property
    def success(self) -> bool:
        return self.note_count > 0 and not self.errors


class OrchestralParser:
    """Parse complex orchestral scores using hierarchical processing.

    This parser handles scores that fail with standard OMR by:
    1. Detecting system boundaries on each page
    2. Breaking systems into instrument groups
    3. Processing each group with manageable OMR
    4. Reconstructing the full score from parts

    Example:
        >>> parser = OrchestralParser(layout_hint=LayoutHint.ROMANTIC_ORCHESTRA)
        >>> result = await parser.parse("beethoven_5.pdf")
        >>> print(f"Extracted {result.note_count} notes")
    """

    def __init__(
        self,
        layout_hint: LayoutHint = LayoutHint.AUTO,
        use_ensemble: bool = False,
        backends: list[str] | None = None,
        fallback_full_page: bool = True,
    ) -> None:
        """Initialize the orchestral parser.

        Args:
            layout_hint: Expected score layout (helps detection).
            use_ensemble: Whether to use ensemble OMR.
            backends: OMR backends to use (default: ["homr"]).
            fallback_full_page: If group processing fails, try full page.
        """
        self.layout_hint = layout_hint
        self.use_ensemble = use_ensemble
        self.backends = backends or ["homr"]
        self.fallback_full_page = fallback_full_page

        self._layout_analyzer = LayoutAnalyzer(hint=layout_hint)
        self._omr: EnsembleOMR | None = None

    def _get_omr(self) -> EnsembleOMR:
        """Get or create OMR engine."""
        if self._omr is None:
            self._omr = EnsembleOMR(
                backends=self.backends,
                fusion_strategy=FusionStrategy.VOTE
                if self.use_ensemble
                else FusionStrategy.BEST_CONFIDENCE,
            )
        return self._omr

    async def parse(
        self,
        source: str | Path | Image.Image,
        progress_callback: ProgressCallback | None = None,
    ) -> OrchestralParseResult:
        """Parse an orchestral score.

        Args:
            source: PDF path or PIL Image.
            progress_callback: Optional callback for progress updates.

        Returns:
            OrchestralParseResult with extracted music.
        """
        start_time = time.perf_counter()
        errors: list[str] = []
        page_layouts: list[PageLayout] = []
        omr_results: list[OMRResult] = []

        # Handle different input types
        images: list[Image.Image] = []
        source_path: Path | None = None

        if isinstance(source, (str, Path)):
            source_path = Path(source)
            images = await self._load_images(source_path)
        else:
            images = [source]

        total_steps = len(images)
        strategy = "unknown"

        for page_idx, image in enumerate(images):
            if progress_callback:
                progress_callback(page_idx + 1, total_steps, f"Analyzing page {page_idx + 1}")

            try:
                # Step 1: Analyze layout
                layout = self._layout_analyzer.analyze(image)
                page_layouts.append(layout)

                # Step 2: Determine processing strategy
                strategy_info = self._layout_analyzer.suggest_processing_strategy(layout)
                strategy = strategy_info["strategy"]

                logger.info(
                    f"Page {page_idx + 1}: {layout.total_staves} staves in "
                    f"{layout.system_count} systems, using {strategy} strategy"
                )

                # Step 3: Process according to strategy
                if strategy == "orchestral" and strategy_info.get("process_by") == "group":
                    # Process by instrument group
                    page_result = await self._process_by_groups(image, layout)
                elif strategy in ("medium", "simple"):
                    # Process by system
                    page_result = await self._process_by_systems(image, layout)
                else:
                    # Fallback: full page
                    page_result = await self._process_full_page(image)

                omr_results.append(page_result)

                logger.info(f"Page {page_idx + 1}: {page_result.note_count} notes extracted")

            except Exception as e:
                logger.error(f"Failed to process page {page_idx + 1}: {e}")
                errors.append(f"Page {page_idx + 1}: {e!s}")

                if self.fallback_full_page:
                    try:
                        logger.info("Attempting full-page fallback...")
                        page_result = await self._process_full_page(image)
                        omr_results.append(page_result)
                    except Exception as e2:
                        logger.error(f"Fallback also failed: {e2}")

        # Merge all page results
        merged = self._merge_results(omr_results)

        parse_time = time.perf_counter() - start_time

        return OrchestralParseResult(
            source_path=source_path,
            page_results=page_layouts,
            omr_results=omr_results,
            merged_result=merged,
            parse_time_seconds=parse_time,
            strategy_used=strategy,
            errors=errors,
        )

    async def _load_images(self, pdf_path: Path) -> list[Image.Image]:
        """Load images from a PDF file.

        Args:
            pdf_path: Path to PDF.

        Returns:
            List of PIL Images (one per page).
        """
        from ..pdf_extractor import PDFExtractor

        extractor = PDFExtractor()
        pages = extractor.extract_all(pdf_path)
        return [img for _, img in pages]

    async def _process_by_groups(self, image: Image.Image, layout: PageLayout) -> OMRResult:
        """Process page by instrument groups.

        This is the key orchestral processing strategy:
        - Each instrument group (strings, brass, etc.) is processed separately
        - Results are merged with timeline alignment

        Args:
            image: Full page image.
            layout: Detected page layout.

        Returns:
            Combined OMRResult.
        """
        from ..omr_engine import OMRResult

        detector = SystemDetector()
        omr = self._get_omr()
        all_notes: list[Note] = []

        for system in layout.systems:
            logger.debug(f"Processing system {system.index} with {len(system.groups)} groups")

            system_notes: list[Note] = []

            for group in system.groups:
                # Crop to group region
                group_image = detector.crop_group(image, system, group)

                # Run OMR on this smaller region
                try:
                    result = await omr.recognize(group_image)

                    # Adjust staff indices to global positions
                    for note in result.notes:
                        # Map local staff to global staff
                        if group.staff_indices:
                            local_staff = note.staff % len(group.staff_indices)
                            note.staff = group.staff_indices[local_staff]

                        system_notes.append(note)

                    logger.debug(f"  Group {group.family.value}: {len(result.notes)} notes")

                except Exception as e:
                    logger.warning(f"  Group {group.family.value} failed: {e}")

            all_notes.extend(system_notes)

        return OMRResult(
            page_number=0,
            notes=all_notes,
            confidence=0.7,  # Lower confidence for reconstructed
            num_staves=layout.total_staves,
        )

    async def _process_by_systems(self, image: Image.Image, layout: PageLayout) -> OMRResult:
        """Process page by systems (simpler than by-group).

        Args:
            image: Full page image.
            layout: Detected page layout.

        Returns:
            Combined OMRResult.
        """
        from ..omr_engine import OMRResult

        detector = SystemDetector()
        omr = self._get_omr()
        all_notes: list[Note] = []

        for system in layout.systems:
            # Crop to system
            system_image = detector.crop_system(image, system)

            try:
                result = await omr.recognize(system_image)

                # Offset note times based on system position
                # (Systems are played sequentially, top to bottom on page)
                # For now, assume each system is consecutive measures
                all_notes.extend(result.notes)

            except Exception as e:
                logger.warning(f"System {system.index} failed: {e}")

        return OMRResult(
            page_number=0,
            notes=all_notes,
            confidence=0.8,
            num_staves=layout.total_staves,
        )

    async def _process_full_page(self, image: Image.Image) -> OMRResult:
        """Process the full page at once (fallback).

        Args:
            image: Full page image.

        Returns:
            OMRResult from direct OMR.
        """
        omr = self._get_omr()
        result = await omr.recognize(image)

        if hasattr(result, "notes"):
            from ..omr_engine import OMRResult

            return OMRResult(
                page_number=0,
                notes=result.notes,
                confidence=result.confidence,
            )

        return result

    def _merge_results(self, results: list[OMRResult]) -> OMRResult | None:
        """Merge multiple page results into one.

        Args:
            results: Results from each page.

        Returns:
            Combined OMRResult.
        """
        if not results:
            return None

        from ..omr_engine import Note, OMRResult

        # Calculate time offsets for each page
        # Assume each page follows the previous
        all_notes: list[Note] = []
        beat_offset = 0.0

        for result in results:
            if not result.notes:
                continue

            # Find max beat in this result
            max_beat = max((n.start_beat + n.duration for n in result.notes), default=0)

            for note in result.notes:
                all_notes.append(
                    Note(
                        pitch=note.pitch,
                        start_beat=note.start_beat + beat_offset,
                        duration=note.duration,
                        voice=note.voice,
                        staff=note.staff,
                        velocity=note.velocity,
                    )
                )

            beat_offset += max_beat

        avg_confidence = sum(r.confidence for r in results) / len(results) if results else 0

        return OMRResult(
            page_number=0,
            notes=all_notes,
            confidence=avg_confidence,
        )


async def parse_orchestral_score(
    source: str | Path,
    layout_hint: LayoutHint = LayoutHint.AUTO,
    use_ensemble: bool = False,
    backends: list[str] | None = None,
    progress_callback: ProgressCallback | None = None,
) -> OrchestralParseResult:
    """Convenience function to parse an orchestral score.

    Args:
        source: Path to PDF or image file.
        layout_hint: Expected layout type.
        use_ensemble: Whether to use multiple OMR backends.
        backends: Which OMR backends to use.
        progress_callback: Optional progress callback.

    Returns:
        OrchestralParseResult with extracted music.

    Example:
        >>> result = await parse_orchestral_score(
        ...     "beethoven_5_mvt1.pdf",
        ...     layout_hint=LayoutHint.ROMANTIC_ORCHESTRA,
        ... )
        >>> print(f"Extracted {result.note_count} notes")
    """
    parser = OrchestralParser(
        layout_hint=layout_hint,
        use_ensemble=use_ensemble,
        backends=backends,
    )
    return await parser.parse(source, progress_callback=progress_callback)
