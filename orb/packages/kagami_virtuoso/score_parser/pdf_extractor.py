"""PDF page extraction for score parsing.

Extracts high-resolution images from PDF files for OMR processing.
Uses PyMuPDF (fitz) for fast, high-quality extraction.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import fitz  # PyMuPDF

if TYPE_CHECKING:
    from PIL import Image

logger = logging.getLogger(__name__)


@dataclass
class PageInfo:
    """Metadata about an extracted page."""

    page_number: int
    width: int
    height: int
    dpi: int
    path: Path | None = None


@dataclass
class PDFInfo:
    """Metadata about the source PDF."""

    path: Path
    page_count: int
    title: str | None
    author: str | None
    creator: str | None
    creation_date: str | None


class PDFExtractor:
    """Extract high-resolution page images from PDF scores.

    Attributes:
        default_dpi: Default resolution for extraction (300 DPI standard).
        default_zoom: Zoom factor for higher resolution (2.0 = 600 DPI effective).

    Example:
        >>> extractor = PDFExtractor()
        >>> pages = extractor.extract_all("score.pdf", output_dir="pages/")
        >>> for page in pages:
        ...     print(f"Page {page.page_number}: {page.width}x{page.height}")
    """

    def __init__(self, default_dpi: int = 300, default_zoom: float = 2.0) -> None:
        """Initialize the PDF extractor.

        Args:
            default_dpi: Base DPI for extraction.
            default_zoom: Zoom multiplier for higher effective DPI.
        """
        self.default_dpi = default_dpi
        self.default_zoom = default_zoom

    def get_info(self, pdf_path: str | Path) -> PDFInfo:
        """Get metadata about a PDF file.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            PDFInfo with page count and metadata.
        """
        pdf_path = Path(pdf_path)
        doc = fitz.open(str(pdf_path))
        try:
            metadata = doc.metadata
            return PDFInfo(
                path=pdf_path,
                page_count=doc.page_count,
                title=metadata.get("title") or None,
                author=metadata.get("author") or None,
                creator=metadata.get("creator") or None,
                creation_date=metadata.get("creationDate") or None,
            )
        finally:
            doc.close()

    def extract_page(
        self,
        pdf_path: str | Path,
        page_number: int,
        output_path: str | Path | None = None,
        zoom: float | None = None,
    ) -> tuple[PageInfo, Image.Image]:
        """Extract a single page as an image.

        Args:
            pdf_path: Path to the PDF file.
            page_number: Zero-based page index.
            output_path: Optional path to save the image.
            zoom: Zoom factor (default uses self.default_zoom).

        Returns:
            Tuple of (PageInfo, PIL Image).
        """
        import io

        from PIL import Image

        pdf_path = Path(pdf_path)
        zoom = zoom or self.default_zoom

        doc = fitz.open(str(pdf_path))
        try:
            if page_number >= doc.page_count:
                raise ValueError(f"Page {page_number} out of range (0-{doc.page_count - 1})")

            page = doc[page_number]
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)

            # Convert to PIL Image
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))

            info = PageInfo(
                page_number=page_number,
                width=pix.width,
                height=pix.height,
                dpi=int(self.default_dpi * zoom),
            )

            if output_path:
                output_path = Path(output_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                img.save(str(output_path))
                info.path = output_path
                logger.info(f"Saved page {page_number} to {output_path}")

            return info, img

        finally:
            doc.close()

    def extract_all(
        self,
        pdf_path: str | Path,
        output_dir: str | Path | None = None,
        zoom: float | None = None,
        page_range: tuple[int, int] | None = None,
    ) -> list[tuple[PageInfo, Image.Image]]:
        """Extract all pages from a PDF.

        Args:
            pdf_path: Path to the PDF file.
            output_dir: Optional directory to save images.
            zoom: Zoom factor for extraction.
            page_range: Optional (start, end) range of pages.

        Returns:
            List of (PageInfo, PIL Image) tuples.
        """
        import io

        from PIL import Image

        pdf_path = Path(pdf_path)
        zoom = zoom or self.default_zoom

        if output_dir:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

        doc = fitz.open(str(pdf_path))
        results = []

        try:
            start = page_range[0] if page_range else 0
            end = page_range[1] if page_range else doc.page_count

            for page_num in range(start, end):
                page = doc[page_num]
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat)

                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))

                info = PageInfo(
                    page_number=page_num,
                    width=pix.width,
                    height=pix.height,
                    dpi=int(self.default_dpi * zoom),
                )

                if output_dir:
                    output_path = output_dir / f"page_{page_num:04d}.png"
                    img.save(str(output_path))
                    info.path = output_path

                results.append((info, img))
                logger.debug(f"Extracted page {page_num}/{end - 1}")

            logger.info(f"Extracted {len(results)} pages from {pdf_path}")
            return results

        finally:
            doc.close()

    def extract_page_batch(
        self,
        pdf_path: str | Path,
        page_numbers: list[int],
        output_dir: str | Path | None = None,
        zoom: float | None = None,
    ) -> list[tuple[PageInfo, Image.Image]]:
        """Extract specific pages from a PDF.

        Args:
            pdf_path: Path to the PDF file.
            page_numbers: List of page numbers to extract.
            output_dir: Optional directory to save images.
            zoom: Zoom factor for extraction.

        Returns:
            List of (PageInfo, PIL Image) tuples.
        """
        results = []
        for page_num in page_numbers:
            output_path = None
            if output_dir:
                output_path = Path(output_dir) / f"page_{page_num:04d}.png"
            info, img = self.extract_page(pdf_path, page_num, output_path, zoom)
            results.append((info, img))
        return results
