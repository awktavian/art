"""Main Score Parser - Unified interface for PDF to MIDI/MusicXML.

Orchestrates the full pipeline:
    PDF → Extract → Preprocess → OMR → Postprocess → Export

Features:
    - Batch processing with progress tracking
    - Error recovery (skip failed pages, continue parsing)
    - Page-level caching to resume interrupted parsing
    - Instrument mapping integration

Example:
    >>> from kagami_virtuoso.score_parser import parse_score
    >>> result = await parse_score("beethoven_5.pdf")
    >>> result.to_midi("beethoven_5.mid")
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from .omr_engine import OMRBackend, OMREngine, OMRResult
from .pdf_extractor import PDFExtractor, PDFInfo
from .postprocessor import MIDIExporter, MusicXMLExporter, PostProcessor
from .preprocessor import ImagePreprocessor

if TYPE_CHECKING:
    from PIL import Image

    from .instrument_mapper import InstrumentMapping

logger = logging.getLogger(__name__)


# =============================================================================
# Progress Callback Type
# =============================================================================

ProgressCallback = Callable[[int, int, str], None]


@dataclass
class ParsedScore:
    """Complete parsed score with all pages combined.

    Attributes:
        source_path: Path to the source PDF.
        pdf_info: Metadata about the source PDF.
        omr_result: Combined OMR result from all pages.
        page_results: Individual results per page.
        instrument_mappings: Optional instrument mappings.
        parse_time_seconds: Total parsing time.
        failed_pages: List of page numbers that failed to parse.
    """

    source_path: Path
    pdf_info: PDFInfo
    omr_result: OMRResult
    page_results: list[OMRResult] = field(default_factory=list)
    instrument_mappings: list[InstrumentMapping] = field(default_factory=list)
    parse_time_seconds: float = 0.0
    failed_pages: list[int] = field(default_factory=list)

    @property
    def note_count(self) -> int:
        """Total notes in the score."""
        return self.omr_result.note_count

    @property
    def page_count(self) -> int:
        """Number of pages processed."""
        return len(self.page_results)

    @property
    def success_rate(self) -> float:
        """Percentage of pages successfully parsed."""
        total = self.page_count + len(self.failed_pages)
        if total == 0:
            return 0.0
        return self.page_count / total

    @property
    def confidence(self) -> float:
        """Average confidence across all pages."""
        return self.omr_result.confidence

    def to_midi(
        self,
        output_path: str | Path,
        tempo: int = 120,
        use_instrument_mapping: bool = True,
    ) -> Path:
        """Export to MIDI file.

        Args:
            output_path: Path for output file.
            tempo: Tempo in BPM (used if not in score).
            use_instrument_mapping: Whether to apply instrument mappings.

        Returns:
            Path to created MIDI file.
        """
        exporter = MIDIExporter(default_tempo=tempo)
        if use_instrument_mapping and self.instrument_mappings:
            return exporter.export_with_instruments(
                self.omr_result, output_path, self.instrument_mappings
            )
        return exporter.export(self.omr_result, output_path)

    def to_musicxml(self, output_path: str | Path) -> Path:
        """Export to MusicXML file.

        Args:
            output_path: Path for output file.

        Returns:
            Path to created MusicXML file.
        """
        exporter = MusicXMLExporter()
        return exporter.export(self.omr_result, output_path)

    def get_notes_for_staff(self, staff: int) -> list:
        """Get notes for a specific staff.

        Args:
            staff: Staff index.

        Returns:
            List of notes on that staff.
        """
        return [n for n in self.omr_result.notes if n.staff == staff]

    def get_staff_count(self) -> int:
        """Get number of unique staves in the score."""
        if not self.omr_result.notes:
            return 0
        return max(n.staff for n in self.omr_result.notes) + 1

    def map_instruments(self, movement: int = 1) -> ParsedScore:
        """Apply instrument mapping to the score.

        Args:
            movement: Movement number (affects instrumentation).

        Returns:
            Self with mappings applied.
        """
        from .instrument_mapper import map_beethoven_5

        self.instrument_mappings = map_beethoven_5(self.omr_result, movement)
        return self


class ScoreParser:
    """Main score parser with configurable pipeline.

    Provides fine-grained control over the parsing process with:
    - Batch processing with progress tracking
    - Error recovery (skip failed pages, continue parsing)
    - Page-level caching to resume interrupted parsing

    Example:
        >>> parser = ScoreParser()
        >>> parser.set_page_range(0, 10)  # First 10 pages only
        >>> result = await parser.parse("score.pdf", progress_callback=print_progress)
    """

    def __init__(
        self,
        backend: OMRBackend = OMRBackend.AUTO,
        preprocess: bool = True,
        postprocess: bool = True,
        cache_dir: Path | None = None,
        skip_on_error: bool = True,
    ) -> None:
        """Initialize the parser.

        Args:
            backend: OMR backend to use.
            preprocess: Whether to preprocess images.
            postprocess: Whether to postprocess results.
            cache_dir: Directory for caching page results.
            skip_on_error: Whether to skip pages that fail and continue.
        """
        self.backend = backend
        self.preprocess = preprocess
        self.postprocess = postprocess
        self.cache_dir = cache_dir
        self.skip_on_error = skip_on_error

        self._page_range: tuple[int, int] | None = None
        self._specific_pages: list[int] | None = None

        # Initialize components
        self._pdf_extractor = PDFExtractor()
        self._preprocessor = ImagePreprocessor() if preprocess else None
        self._omr_engine: OMREngine | None = None  # Lazy init
        self._postprocessor = PostProcessor() if postprocess else None

    def set_page_range(self, start: int, end: int) -> ScoreParser:
        """Set range of pages to process.

        Args:
            start: First page (0-indexed).
            end: Last page (exclusive).

        Returns:
            Self for chaining.
        """
        self._page_range = (start, end)
        self._specific_pages = None
        return self

    def set_pages(self, pages: list[int]) -> ScoreParser:
        """Set specific pages to process.

        Args:
            pages: List of page numbers (0-indexed).

        Returns:
            Self for chaining.
        """
        self._specific_pages = pages
        self._page_range = None
        return self

    def set_cache_dir(self, cache_dir: Path | str) -> ScoreParser:
        """Set cache directory for resumable parsing.

        Args:
            cache_dir: Directory to store cached page results.

        Returns:
            Self for chaining.
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        return self

    def _get_cache_key(self, pdf_path: Path, page_num: int) -> str:
        """Generate cache key for a page."""
        # Hash based on filename and page number
        content = f"{pdf_path.name}:{page_num}:{pdf_path.stat().st_mtime}"
        return hashlib.md5(content.encode()).hexdigest()

    def _load_cached_result(self, pdf_path: Path, page_num: int) -> OMRResult | None:
        """Load cached OMR result if available."""
        if not self.cache_dir:
            return None

        cache_key = self._get_cache_key(pdf_path, page_num)
        cache_file = self.cache_dir / f"{cache_key}.json"

        if cache_file.exists():
            try:
                with open(cache_file) as f:
                    data = json.load(f)
                # Reconstruct OMRResult from cached data
                from .omr_engine import Dynamic, KeySignature, Note, Rest, Tempo, TimeSignature

                result = OMRResult(
                    page_number=data["page_number"],
                    notes=[Note(**n) for n in data.get("notes", [])],
                    rests=[Rest(**r) for r in data.get("rests", [])],
                    time_signatures=[TimeSignature(**ts) for ts in data.get("time_signatures", [])],
                    key_signatures=[KeySignature(**ks) for ks in data.get("key_signatures", [])],
                    tempos=[Tempo(**t) for t in data.get("tempos", [])],
                    dynamics=[Dynamic(**d) for d in data.get("dynamics", [])],
                    confidence=data.get("confidence", 0.0),
                    num_staves=data.get("num_staves", 0),
                    num_voices=data.get("num_voices", 0),
                )
                logger.debug(f"Loaded cached result for page {page_num}")
                return result
            except Exception as e:
                logger.warning(f"Failed to load cache for page {page_num}: {e}")
        return None

    def _save_cached_result(self, pdf_path: Path, page_num: int, result: OMRResult) -> None:
        """Save OMR result to cache."""
        if not self.cache_dir:
            return

        cache_key = self._get_cache_key(pdf_path, page_num)
        cache_file = self.cache_dir / f"{cache_key}.json"

        try:
            from dataclasses import asdict

            data = {
                "page_number": result.page_number,
                "notes": [asdict(n) for n in result.notes],
                "rests": [asdict(r) for r in result.rests],
                "time_signatures": [asdict(ts) for ts in result.time_signatures],
                "key_signatures": [asdict(ks) for ks in result.key_signatures],
                "tempos": [asdict(t) for t in result.tempos],
                "dynamics": [asdict(d) for d in result.dynamics],
                "confidence": result.confidence,
                "num_staves": result.num_staves,
                "num_voices": result.num_voices,
            }
            with open(cache_file, "w") as f:
                json.dump(data, f)
            logger.debug(f"Cached result for page {page_num}")
        except Exception as e:
            logger.warning(f"Failed to cache page {page_num}: {e}")

    async def parse(
        self,
        pdf_path: str | Path,
        progress_callback: ProgressCallback | None = None,
    ) -> ParsedScore:
        """Parse a PDF score with progress tracking and error recovery.

        Args:
            pdf_path: Path to the PDF file.
            progress_callback: Optional callback for progress updates.
                Signature: (current_page, total_pages, status_message) -> None

        Returns:
            ParsedScore with all recognized content.
        """
        start_time = time.perf_counter()
        pdf_path = Path(pdf_path)
        logger.info(f"Parsing score: {pdf_path}")

        # Get PDF info
        pdf_info = self._pdf_extractor.get_info(pdf_path)
        logger.info(f"PDF has {pdf_info.page_count} pages")

        # Determine which pages to process
        if self._specific_pages:
            pages_to_process = self._specific_pages
        elif self._page_range:
            pages_to_process = list(range(self._page_range[0], self._page_range[1]))
        else:
            pages_to_process = list(range(pdf_info.page_count))

        # Filter to valid pages
        pages_to_process = [p for p in pages_to_process if 0 <= p < pdf_info.page_count]
        total_pages = len(pages_to_process)

        # Initialize OMR engine (lazy)
        if self._omr_engine is None:
            self._omr_engine = OMREngine(backend=self.backend)

        # Process each page with error recovery
        page_results: list[OMRResult] = []
        failed_pages: list[int] = []

        for i, page_num in enumerate(pages_to_process):
            status_msg = f"Processing page {page_num + 1}/{pdf_info.page_count}"
            logger.info(status_msg)

            # Call progress callback
            if progress_callback:
                progress_callback(i + 1, total_pages, status_msg)

            try:
                # Check cache first
                cached_result = self._load_cached_result(pdf_path, page_num)
                if cached_result:
                    logger.info(
                        f"Page {page_num + 1}: loaded from cache ({cached_result.note_count} notes)"
                    )
                    page_results.append(cached_result)
                    continue

                # Extract page image
                _page_info, image = self._pdf_extractor.extract_page(pdf_path, page_num)

                # Preprocess if enabled
                if self._preprocessor:
                    preprocess_result = self._preprocessor.process(image)
                    image = preprocess_result.image
                    logger.debug(
                        f"Preprocessed: skew={preprocess_result.skew_angle:.2f}°, "
                        f"staff_spacing={preprocess_result.staff_line_spacing}"
                    )

                # Run OMR
                omr_result = self._omr_engine.recognize(image, page_number=page_num)
                logger.info(f"Page {page_num + 1}: {omr_result.note_count} notes detected")

                # Postprocess if enabled
                if self._postprocessor:
                    omr_result = self._postprocessor.process(omr_result)

                # Cache the result
                self._save_cached_result(pdf_path, page_num, omr_result)

                page_results.append(omr_result)

            except Exception as e:
                logger.error(f"Failed to process page {page_num + 1}: {e}")
                failed_pages.append(page_num)

                if not self.skip_on_error:
                    raise

                # Create empty result for failed page
                page_results.append(
                    OMRResult(
                        page_number=page_num,
                        errors=[str(e)],
                    )
                )

        # Merge all pages
        # Filter out empty results from failed pages for merging
        valid_results = [r for r in page_results if r.note_count > 0 or not r.errors]

        if self._postprocessor and valid_results:
            merged_result = self._postprocessor.merge_pages(valid_results)
        elif valid_results:
            merged_result = valid_results[0]
        else:
            merged_result = OMRResult(page_number=0)

        parse_time = time.perf_counter() - start_time

        logger.info(
            f"Parsing complete: {merged_result.note_count} total notes "
            f"from {len(valid_results)} pages in {parse_time:.1f}s"
        )
        if failed_pages:
            logger.warning(f"Failed pages: {failed_pages}")

        return ParsedScore(
            source_path=pdf_path,
            pdf_info=pdf_info,
            omr_result=merged_result,
            page_results=page_results,
            parse_time_seconds=parse_time,
            failed_pages=failed_pages,
        )

    def parse_image(self, image: Image.Image) -> OMRResult:
        """Parse a single image directly.

        Args:
            image: PIL Image of a score page.

        Returns:
            OMRResult for the page.
        """
        if self._omr_engine is None:
            self._omr_engine = OMREngine(backend=self.backend)

        if self._preprocessor:
            preprocess_result = self._preprocessor.process(image)
            image = preprocess_result.image

        result = self._omr_engine.recognize(image)

        if self._postprocessor:
            result = self._postprocessor.process(result)

        return result


async def parse_score(
    pdf_path: str | Path,
    backend: OMRBackend = OMRBackend.AUTO,
    page_range: tuple[int, int] | None = None,
    cache_dir: Path | str | None = None,
    skip_on_error: bool = True,
    progress_callback: ProgressCallback | None = None,
) -> ParsedScore:
    """Convenience function to parse a score.

    For simple scores (piano, chamber music). For complex orchestral
    scores, consider using smart_parse() or the orchestral module directly.

    Args:
        pdf_path: Path to PDF file.
        backend: OMR backend to use.
        page_range: Optional (start, end) page range.
        cache_dir: Optional directory for caching page results.
        skip_on_error: Whether to skip failed pages and continue.
        progress_callback: Optional callback for progress updates.

    Returns:
        ParsedScore with all content.

    Example:
        >>> result = await parse_score("beethoven_5.pdf")
        >>> result.to_midi("beethoven_5.mid")

        # With progress tracking
        >>> def progress(current, total, msg):
        ...     print(f"[{current}/{total}] {msg}")
        >>> result = await parse_score("beethoven_5.pdf", progress_callback=progress)
    """
    parser = ScoreParser(
        backend=backend,
        skip_on_error=skip_on_error,
    )
    if page_range:
        parser.set_page_range(page_range[0], page_range[1])
    if cache_dir:
        parser.set_cache_dir(cache_dir)
    return await parser.parse(pdf_path, progress_callback=progress_callback)


async def smart_parse(
    source: str | Path,
    layout_hint: str | None = None,
    use_orchestral: bool = True,
    fallback_standard: bool = True,
    cache_dir: Path | str | None = None,
    progress_callback: ProgressCallback | None = None,
) -> ParsedScore:
    """Smart score parser that automatically selects the best approach.

    Tries orchestral parser first for complex scores, falls back to
    standard parser if needed.

    Args:
        source: Path to PDF or image file.
        layout_hint: Layout hint (romantic_orchestra, classical, etc.)
        use_orchestral: Try orchestral parser first (default True).
        fallback_standard: Fall back to standard if orchestral fails.
        cache_dir: Cache directory for results.
        progress_callback: Progress callback.

    Returns:
        ParsedScore with all content.

    Example:
        >>> # Auto-detect and parse
        >>> result = await smart_parse("symphony.pdf")

        >>> # With layout hint for orchestral score
        >>> result = await smart_parse(
        ...     "beethoven_5.pdf",
        ...     layout_hint="romantic_orchestra"
        ... )
    """
    source = Path(source)

    # Try orchestral parser first if enabled
    if use_orchestral:
        try:
            from .orchestral import LayoutHint, parse_orchestral_score

            hint = LayoutHint.AUTO
            if layout_hint:
                try:
                    hint = LayoutHint(layout_hint.lower())
                except ValueError:
                    pass

            logger.info(f"Trying orchestral parser with hint={hint.value}")

            result = await parse_orchestral_score(
                source,
                layout_hint=hint,
                progress_callback=progress_callback,
            )

            if result.success and result.note_count > 0:
                logger.info(
                    f"Orchestral parser succeeded: {result.note_count} notes, "
                    f"strategy={result.strategy_used}"
                )

                # Convert to ParsedScore format
                from .pdf_extractor import PDFInfo

                return ParsedScore(
                    source_path=source,
                    pdf_info=PDFInfo(
                        path=source,
                        page_count=len(result.page_results),
                        title=None,
                        author=None,
                        creator=None,
                        creation_date=None,
                    ),
                    omr_result=result.merged_result,
                    page_results=[r.merged_result for r in [result] if r.merged_result],
                    parse_time_seconds=result.parse_time_seconds,
                )

            else:
                logger.warning("Orchestral parser found no notes")

        except Exception as e:
            logger.warning(f"Orchestral parser failed: {e}")

    # Fall back to standard parser
    if fallback_standard:
        logger.info("Using standard parser")
        return await parse_score(
            source,
            cache_dir=cache_dir,
            progress_callback=progress_callback,
        )

    # No fallback, return empty
    from .omr_engine import OMRResult
    from .pdf_extractor import PDFInfo

    return ParsedScore(
        source_path=source,
        pdf_info=PDFInfo(
            path=source,
            page_count=0,
            title=None,
            author=None,
            creator=None,
            creation_date=None,
        ),
        omr_result=OMRResult(page_number=0),
        failed_pages=[0],
    )


def parse_score_sync(
    pdf_path: str | Path,
    backend: OMRBackend = OMRBackend.AUTO,
    page_range: tuple[int, int] | None = None,
    cache_dir: Path | str | None = None,
    skip_on_error: bool = True,
    progress_callback: ProgressCallback | None = None,
) -> ParsedScore:
    """Synchronous version of parse_score.

    Args:
        pdf_path: Path to PDF file.
        backend: OMR backend to use.
        page_range: Optional (start, end) page range.
        cache_dir: Optional directory for caching page results.
        skip_on_error: Whether to skip failed pages and continue.
        progress_callback: Optional callback for progress updates.

    Returns:
        ParsedScore with all content.
    """
    return asyncio.run(
        parse_score(pdf_path, backend, page_range, cache_dir, skip_on_error, progress_callback)
    )


def parse_beethoven_5(
    pdf_path: str | Path = "assets/scores/beethoven_5/symphony_no5_full_score.pdf",
    movement: int = 1,
    cache_dir: Path | str | None = "assets/scores/beethoven_5/cache",
    progress_callback: ProgressCallback | None = None,
) -> ParsedScore:
    """Parse Beethoven's 5th Symphony with instrument mapping.

    Convenience function specifically for Beethoven 5th with:
    - Appropriate instrumentation mapping
    - Default cache directory
    - Movement-aware parsing

    Args:
        pdf_path: Path to the PDF (defaults to standard location).
        movement: Which movement (1-4) for instrumentation.
        cache_dir: Cache directory for resumable parsing.
        progress_callback: Optional progress callback.

    Returns:
        ParsedScore with instrument mappings applied.

    Example:
        >>> result = parse_beethoven_5(movement=1)
        >>> print(f"Found {len(result.instrument_mappings)} instruments")
        >>> result.to_midi("beethoven_5_mvt1.mid")
    """
    result = parse_score_sync(
        pdf_path,
        cache_dir=cache_dir,
        skip_on_error=True,
        progress_callback=progress_callback,
    )

    # Apply instrument mapping for the movement
    result.map_instruments(movement=movement)

    return result
