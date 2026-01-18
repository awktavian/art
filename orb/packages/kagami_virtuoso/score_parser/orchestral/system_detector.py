"""System and instrument group detection for orchestral scores.

Detects musical systems (rows of staves played simultaneously) and
groups them by instrument family for tractable OMR processing.

The key insight: instead of processing 40 staves at once (which fails),
we detect system boundaries and process 2-8 staves at a time.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from PIL import Image

logger = logging.getLogger(__name__)


class InstrumentFamily(Enum):
    """Standard orchestral instrument families."""

    WOODWINDS = "woodwinds"
    BRASS = "brass"
    PERCUSSION = "percussion"
    KEYBOARDS = "keyboards"
    STRINGS = "strings"
    UNKNOWN = "unknown"


@dataclass
class BoundingBox:
    """Rectangular region in an image."""

    x: int
    y: int
    width: int
    height: int

    @property
    def x2(self) -> int:
        return self.x + self.width

    @property
    def y2(self) -> int:
        return self.y + self.height

    @property
    def center_y(self) -> int:
        return self.y + self.height // 2

    def expand(self, margin: int) -> BoundingBox:
        """Return expanded bounding box with margin."""
        return BoundingBox(
            x=max(0, self.x - margin),
            y=max(0, self.y - margin),
            width=self.width + 2 * margin,
            height=self.height + 2 * margin,
        )


@dataclass
class StaffLine:
    """A detected staff line (horizontal line group)."""

    y_positions: list[int]  # Y coordinates of the 5 lines
    x_start: int
    x_end: int
    confidence: float = 1.0

    @property
    def y_center(self) -> float:
        return sum(self.y_positions) / len(self.y_positions)

    @property
    def line_spacing(self) -> float:
        if len(self.y_positions) < 2:
            return 0
        return (self.y_positions[-1] - self.y_positions[0]) / (len(self.y_positions) - 1)


@dataclass
class InstrumentGroup:
    """A group of staves belonging to one instrument family.

    Examples:
        - Strings group: Violin I, Violin II, Viola, Cello, Bass (5 staves)
        - Brass group: Horns, Trumpets, Trombones, Tuba (8 staves for full brass)
        - Single instrument: Piano (2 staves with grand staff brace)
    """

    family: InstrumentFamily
    staff_indices: list[int]  # Indices within the system
    bbox: BoundingBox
    name: str | None = None  # OCR-detected name like "Violins"
    has_brace: bool = False  # Curly brace grouping
    has_bracket: bool = False  # Square bracket grouping

    @property
    def staff_count(self) -> int:
        return len(self.staff_indices)


@dataclass
class SystemRegion:
    """A musical system: all staves played simultaneously.

    In orchestral scores, a system typically contains all instrument parts
    for a few measures of music, arranged vertically on the page.
    """

    index: int  # System number on page (0-indexed)
    bbox: BoundingBox
    staff_lines: list[StaffLine] = field(default_factory=list)
    groups: list[InstrumentGroup] = field(default_factory=list)
    measure_start: int | None = None  # If detected
    measure_end: int | None = None

    @property
    def staff_count(self) -> int:
        return len(self.staff_lines)


@dataclass
class PageLayout:
    """Complete layout analysis of a score page."""

    page_number: int
    width: int
    height: int
    systems: list[SystemRegion] = field(default_factory=list)
    margin_left: int = 0
    margin_right: int = 0
    margin_top: int = 0
    margin_bottom: int = 0

    @property
    def system_count(self) -> int:
        return len(self.systems)

    @property
    def total_staves(self) -> int:
        return sum(s.staff_count for s in self.systems)


class SystemDetector:
    """Detect musical systems and instrument groups in orchestral scores.

    Uses a multi-stage approach:
    1. Horizontal projection to find staff-dense regions
    2. Staff line detection within regions
    3. Gap analysis to separate systems
    4. Brace/bracket detection to identify groups
    5. Optional OCR for instrument names

    Example:
        >>> detector = SystemDetector()
        >>> layout = detector.analyze(page_image)
        >>> for system in layout.systems:
        ...     print(f"System {system.index}: {system.staff_count} staves")
    """

    def __init__(
        self,
        min_system_gap: int = 50,
        min_staff_height: int = 20,
        projection_threshold: float = 0.3,
        use_ocr: bool = False,
    ) -> None:
        """Initialize the system detector.

        Args:
            min_system_gap: Minimum vertical gap between systems (pixels).
            min_staff_height: Minimum height of a staff (pixels).
            projection_threshold: Threshold for horizontal projection peaks.
            use_ocr: Whether to use OCR to detect instrument names.
        """
        self.min_system_gap = min_system_gap
        self.min_staff_height = min_staff_height
        self.projection_threshold = projection_threshold
        self.use_ocr = use_ocr

    def analyze(self, image: Image.Image) -> PageLayout:
        """Analyze a score page and return its layout.

        Args:
            image: PIL Image of the score page.

        Returns:
            PageLayout with detected systems and groups.
        """
        # Convert to grayscale numpy array
        if image.mode != "L":
            gray = image.convert("L")
        else:
            gray = image

        arr = np.array(gray)
        height, width = arr.shape

        logger.info(f"Analyzing page layout: {width}x{height}")

        # Step 1: Find page margins
        margins = self._detect_margins(arr)

        # Step 2: Detect system regions using horizontal projection
        system_regions = self._detect_system_regions(arr, margins)

        # Step 3: Detect staff lines within each system
        for system in system_regions:
            system.staff_lines = self._detect_staff_lines(arr, system.bbox)
            logger.debug(f"System {system.index}: {len(system.staff_lines)} staff lines detected")

        # Step 4: Detect instrument groups (braces/brackets)
        for system in system_regions:
            system.groups = self._detect_instrument_groups(arr, system)

        # Step 5: Optional OCR for instrument names
        if self.use_ocr:
            self._detect_instrument_names(arr, system_regions)

        layout = PageLayout(
            page_number=0,
            width=width,
            height=height,
            systems=system_regions,
            margin_left=margins["left"],
            margin_right=margins["right"],
            margin_top=margins["top"],
            margin_bottom=margins["bottom"],
        )

        logger.info(
            f"Layout analysis complete: {layout.system_count} systems, "
            f"{layout.total_staves} total staves"
        )

        return layout

    def _detect_margins(self, arr: np.ndarray) -> dict[str, int]:
        """Detect page margins (non-content areas).

        Args:
            arr: Grayscale image array.

        Returns:
            Dict with left, right, top, bottom margins in pixels.
        """
        height, width = arr.shape

        # Binarize
        threshold = np.mean(arr) - np.std(arr) * 0.5
        binary = (arr < threshold).astype(np.uint8)

        # Vertical projection for left/right margins
        v_proj = np.sum(binary, axis=0)
        v_threshold = np.max(v_proj) * 0.05

        left = 0
        for i in range(width):
            if v_proj[i] > v_threshold:
                left = max(0, i - 10)
                break

        right = width
        for i in range(width - 1, -1, -1):
            if v_proj[i] > v_threshold:
                right = min(width, i + 10)
                break

        # Horizontal projection for top/bottom margins
        h_proj = np.sum(binary, axis=1)
        h_threshold = np.max(h_proj) * 0.05

        top = 0
        for i in range(height):
            if h_proj[i] > h_threshold:
                top = max(0, i - 10)
                break

        bottom = height
        for i in range(height - 1, -1, -1):
            if h_proj[i] > h_threshold:
                bottom = min(height, i + 10)
                break

        return {"left": left, "right": right, "top": top, "bottom": bottom}

    def _detect_system_regions(
        self, arr: np.ndarray, margins: dict[str, int]
    ) -> list[SystemRegion]:
        """Detect system regions using horizontal projection analysis.

        Staff lines create strong horizontal patterns. Systems are separated
        by gaps in these patterns.

        Args:
            arr: Grayscale image array.
            margins: Page margins.

        Returns:
            List of SystemRegion objects.
        """
        from scipy.ndimage import uniform_filter1d

        _height, _width = arr.shape

        # Crop to content area
        left, right = margins["left"], margins["right"]
        top, bottom = margins["top"], margins["bottom"]

        content = arr[top:bottom, left:right]

        if content.size == 0:
            return []

        # Better binarization for scores with white backgrounds
        threshold = np.mean(content) - np.std(content) * 0.5
        binary = (content < threshold).astype(np.uint8)

        # Horizontal projection: sum of black pixels per row
        h_proj = np.sum(binary, axis=1)

        # Smooth with larger window to detect systems (not individual lines)
        h_proj_smooth = uniform_filter1d(h_proj.astype(float), size=15)

        # Use adaptive threshold
        proj_mean = np.mean(h_proj_smooth)
        proj_std = np.std(h_proj_smooth)
        proj_threshold = proj_mean + proj_std * 0.3  # Regions with above-average content

        # Find content regions using run-length analysis
        in_content = False
        region_start = 0
        regions = []

        for i, val in enumerate(h_proj_smooth):
            if val > proj_threshold and not in_content:
                in_content = True
                region_start = i
            elif val <= proj_threshold and in_content:
                in_content = False
                region_height = i - region_start
                # Only keep regions tall enough to contain staves (at least 40 pixels for 5 staff lines)
                if region_height >= max(40, self.min_staff_height):
                    regions.append((region_start, i))

        # Don't forget last region
        if in_content:
            region_height = len(h_proj_smooth) - region_start
            if region_height >= max(40, self.min_staff_height):
                regions.append((region_start, len(h_proj_smooth)))

        # Merge nearby regions that are likely part of the same system
        # (orchestral systems can have internal gaps between instrument groups)
        merged_regions = []
        if regions:
            current_start = regions[0][0]
            current_end = regions[0][1]

            for i in range(1, len(regions)):
                gap = regions[i][0] - current_end
                current_height = current_end - current_start

                # Decide if this is a new system or continuation
                # Large gap (>100px or > 30% of current height) = new system
                if gap > max(100, current_height * 0.3):
                    merged_regions.append((current_start, current_end))
                    current_start = regions[i][0]

                current_end = regions[i][1]

            # Add last region
            merged_regions.append((current_start, current_end))

        # Convert to SystemRegion objects
        systems = []
        for start, end in merged_regions:
            # Add small margins
            start_with_margin = max(0, start - 10)
            end_with_margin = min(len(h_proj_smooth), end + 10)

            systems.append(
                SystemRegion(
                    index=len(systems),
                    bbox=BoundingBox(
                        x=left,
                        y=top + start_with_margin,
                        width=right - left,
                        height=end_with_margin - start_with_margin,
                    ),
                )
            )

        logger.debug(f"Detected {len(systems)} system regions")
        return systems

    def _detect_staff_lines(self, arr: np.ndarray, bbox: BoundingBox) -> list[StaffLine]:
        """Detect individual staff lines within a system region.

        Args:
            arr: Full page grayscale array.
            bbox: Bounding box of the system.

        Returns:
            List of detected StaffLine objects.
        """
        from scipy.ndimage import uniform_filter1d

        # Crop to system region
        region = arr[bbox.y : bbox.y2, bbox.x : bbox.x2]

        if region.size == 0:
            return []

        # Better binarization for faint/thin staff lines
        # Use adaptive threshold: mean - std works better for scores with white backgrounds
        threshold = np.mean(region) - np.std(region) * 0.5
        binary = (region < threshold).astype(np.uint8)

        # Horizontal projection
        h_proj = np.sum(binary, axis=1)

        if len(h_proj) == 0:
            return []

        # Smooth to reduce noise
        h_proj_smooth = uniform_filter1d(h_proj.astype(float), size=3)

        # Adaptive peak threshold based on projection statistics
        proj_mean = np.mean(h_proj_smooth)
        proj_std = np.std(h_proj_smooth)
        peak_threshold = proj_mean + proj_std * 0.5  # More lenient

        # Find peaks using scipy for better detection
        try:
            from scipy.signal import find_peaks

            peaks, _ = find_peaks(
                h_proj_smooth,
                height=peak_threshold,
                distance=5,  # Minimum 5 pixels between staff lines
            )
            peaks = list(peaks)
        except ImportError:
            # Fallback to manual peak detection
            peaks = []
            for i in range(1, len(h_proj_smooth) - 1):
                if (
                    h_proj_smooth[i] > peak_threshold
                    and h_proj_smooth[i] >= h_proj_smooth[i - 1]
                    and h_proj_smooth[i] >= h_proj_smooth[i + 1]
                ):
                    peaks.append(i)

        if not peaks:
            return []

        # Group peaks into staff groups (5 lines each)
        # Staff lines are typically 8-25 pixels apart at standard resolutions
        staves = []
        current_group = [peaks[0]]

        for i in range(1, len(peaks)):
            gap = peaks[i] - peaks[i - 1]

            # Check if this peak belongs to the current staff
            if current_group:
                if len(current_group) >= 2:
                    # Use actual spacing from current group
                    avg_spacing = (current_group[-1] - current_group[0]) / (len(current_group) - 1)
                    min_gap = avg_spacing * 0.6
                    max_gap = avg_spacing * 1.5
                else:
                    # Initial guess for staff line spacing (8-25 pixels typical)
                    min_gap = 8
                    max_gap = 30

                if min_gap <= gap <= max_gap:
                    current_group.append(peaks[i])
                    continue

            # Gap too large - start new group
            if len(current_group) >= 4:  # Accept 4-5 lines as valid staff
                staves.append(current_group[:5])
            current_group = [peaks[i]]

        # Don't forget last group
        if len(current_group) >= 4:
            staves.append(current_group[:5])

        # Convert to StaffLine objects
        staff_lines = []
        for staff_peaks in staves:
            # Ensure exactly 5 lines (interpolate if needed)
            if len(staff_peaks) == 4:
                # Interpolate missing line (assume evenly spaced)
                spacing = (staff_peaks[-1] - staff_peaks[0]) / 3
                staff_peaks = [int(staff_peaks[0] + i * spacing) for i in range(5)]
            elif len(staff_peaks) > 5:
                # Take first 5
                staff_peaks = staff_peaks[:5]
            elif len(staff_peaks) < 4:
                continue  # Skip invalid

            staff_lines.append(
                StaffLine(
                    y_positions=[bbox.y + p for p in staff_peaks],
                    x_start=bbox.x,
                    x_end=bbox.x2,
                )
            )

        logger.debug(f"Detected {len(staff_lines)} staff lines in region")
        return staff_lines

    def _detect_instrument_groups(
        self, arr: np.ndarray, system: SystemRegion
    ) -> list[InstrumentGroup]:
        """Detect instrument groups using brace/bracket detection.

        Orchestral scores use curly braces {} to group families:
        - Strings (Vln I, Vln II, Vla, Vc, Cb)
        - Woodwinds (Fl, Ob, Cl, Bn)
        - Brass (Hn, Tpt, Tbn, Tba)

        Square brackets [] group within families or for divisi.

        Args:
            arr: Full page grayscale array.
            system: SystemRegion with detected staff lines.

        Returns:
            List of InstrumentGroup objects.
        """
        if not system.staff_lines:
            return []

        # For now, use a simple heuristic based on staff count and spacing
        # TODO: Implement actual brace detection using morphological operations

        staff_count = len(system.staff_lines)
        groups = []

        if staff_count >= 15:
            # Large orchestral score - assume standard layout
            # Woodwinds (top), Brass, Percussion, Strings (bottom)

            # Estimate group boundaries based on typical proportions
            # Strings usually take ~40% at bottom
            strings_start = int(staff_count * 0.6)
            brass_start = int(staff_count * 0.3)

            # Woodwinds
            if brass_start > 0:
                groups.append(
                    InstrumentGroup(
                        family=InstrumentFamily.WOODWINDS,
                        staff_indices=list(range(0, brass_start)),
                        bbox=self._get_group_bbox(system, 0, brass_start),
                        has_brace=True,
                    )
                )

            # Brass + Percussion
            if strings_start > brass_start:
                groups.append(
                    InstrumentGroup(
                        family=InstrumentFamily.BRASS,
                        staff_indices=list(range(brass_start, strings_start)),
                        bbox=self._get_group_bbox(system, brass_start, strings_start),
                        has_brace=True,
                    )
                )

            # Strings
            groups.append(
                InstrumentGroup(
                    family=InstrumentFamily.STRINGS,
                    staff_indices=list(range(strings_start, staff_count)),
                    bbox=self._get_group_bbox(system, strings_start, staff_count),
                    has_brace=True,
                )
            )

        elif staff_count >= 5:
            # Medium score - likely strings or small ensemble
            groups.append(
                InstrumentGroup(
                    family=InstrumentFamily.STRINGS,
                    staff_indices=list(range(staff_count)),
                    bbox=system.bbox,
                    has_brace=True,
                )
            )

        else:
            # Small score - treat as single group
            groups.append(
                InstrumentGroup(
                    family=InstrumentFamily.UNKNOWN,
                    staff_indices=list(range(staff_count)),
                    bbox=system.bbox,
                )
            )

        return groups

    def _get_group_bbox(self, system: SystemRegion, start_idx: int, end_idx: int) -> BoundingBox:
        """Get bounding box for a subset of staves in a system."""
        if not system.staff_lines:
            return system.bbox

        start_idx = max(0, min(start_idx, len(system.staff_lines) - 1))
        end_idx = max(1, min(end_idx, len(system.staff_lines)))

        y_start = system.staff_lines[start_idx].y_positions[0]
        y_end = system.staff_lines[end_idx - 1].y_positions[-1]

        # Add margin
        margin = 10
        return BoundingBox(
            x=system.bbox.x,
            y=max(0, y_start - margin),
            width=system.bbox.width,
            height=(y_end - y_start) + 2 * margin,
        )

    def _detect_instrument_names(self, arr: np.ndarray, systems: list[SystemRegion]) -> None:
        """Use OCR to detect instrument names in left margin.

        Args:
            arr: Full page grayscale array.
            systems: List of systems to annotate.
        """
        try:
            import pytesseract
        except ImportError:
            logger.warning("pytesseract not installed, skipping instrument name OCR")
            return

        if not systems:
            return

        # Only process first system (names usually only appear there)
        system = systems[0]

        for i, staff_line in enumerate(system.staff_lines):
            # Crop left margin region at staff height
            y_center = int(staff_line.y_center)
            margin_height = int(staff_line.line_spacing * 3)
            margin_width = system.bbox.x  # Everything left of staff

            if margin_width < 20:
                continue

            y_start = max(0, y_center - margin_height)
            y_end = min(arr.shape[0], y_center + margin_height)

            margin_region = arr[y_start:y_end, 0:margin_width]

            # Run OCR
            try:
                from PIL import Image

                margin_image = Image.fromarray(margin_region)
                text = pytesseract.image_to_string(margin_image, config="--psm 7").strip()

                if text and len(text) > 1:
                    # Try to match to known instrument names
                    instrument = self._match_instrument_name(text)
                    logger.debug(f"Staff {i}: OCR='{text}' → {instrument}")

                    # Update groups with instrument info
                    for group in system.groups:
                        if i in group.staff_indices:
                            if group.name is None:
                                group.name = text
                            break

            except Exception as e:
                logger.debug(f"OCR failed for staff {i}: {e}")

    def _match_instrument_name(self, text: str) -> str | None:
        """Match OCR text to known instrument names."""
        text_lower = text.lower().strip()

        instrument_patterns = {
            "flute": ["fl", "flute", "flauto", "flauti"],
            "oboe": ["ob", "oboe", "oboi"],
            "clarinet": ["cl", "clar", "clarinet", "clarinett"],
            "bassoon": ["bn", "bsn", "fag", "fagott", "bassoon"],
            "horn": ["hn", "cor", "horn", "horns", "corno"],
            "trumpet": ["tpt", "tr", "tromb", "trumpet"],
            "trombone": ["tbn", "trb", "trombone", "pos", "posaune"],
            "tuba": ["tba", "tuba"],
            "timpani": ["timp", "timpani", "pk", "pauken"],
            "violin": ["vl", "vln", "violin", "violini", "violino"],
            "viola": ["vla", "viola", "viole", "br", "bratsche"],
            "cello": ["vc", "vlc", "cello", "violoncello", "violoncelli"],
            "bass": ["cb", "kb", "bass", "contrabass", "kontraba"],
        }

        for instrument, patterns in instrument_patterns.items():
            for pattern in patterns:
                if pattern in text_lower:
                    return instrument

        return None

    def crop_system(self, image: Image.Image, system: SystemRegion) -> Image.Image:
        """Crop an image to a system region with margin.

        Args:
            image: Full page image.
            system: System to crop.

        Returns:
            Cropped image of just the system.
        """
        bbox = system.bbox.expand(20)  # Add margin for context

        # Clip to image bounds
        width, height = image.size
        x1 = max(0, bbox.x)
        y1 = max(0, bbox.y)
        x2 = min(width, bbox.x2)
        y2 = min(height, bbox.y2)

        return image.crop((x1, y1, x2, y2))

    def crop_group(
        self, image: Image.Image, system: SystemRegion, group: InstrumentGroup
    ) -> Image.Image:
        """Crop an image to an instrument group with margin.

        Args:
            image: Full page image.
            system: System containing the group.
            group: Group to crop.

        Returns:
            Cropped image of just the group.
        """
        bbox = group.bbox.expand(15)

        width, height = image.size
        x1 = max(0, bbox.x)
        y1 = max(0, bbox.y)
        x2 = min(width, bbox.x2)
        y2 = min(height, bbox.y2)

        return image.crop((x1, y1, x2, y2))
