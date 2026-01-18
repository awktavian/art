"""High-level layout analysis for orchestral scores.

Combines system detection with layout hints and intelligent grouping
strategies for different score types.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from .system_detector import (
    InstrumentFamily,
    InstrumentGroup,
    PageLayout,
    SystemDetector,
    SystemRegion,
)

if TYPE_CHECKING:
    from PIL import Image

logger = logging.getLogger(__name__)


class LayoutHint(Enum):
    """Hints about the expected score layout.

    Providing a hint improves system and group detection accuracy.
    """

    AUTO = "auto"  # Detect automatically

    # Orchestral
    ROMANTIC_ORCHESTRA = "romantic_orchestra"  # Full romantic orchestra (30+ staves)
    CLASSICAL_ORCHESTRA = "classical_orchestra"  # Classical period (20-25 staves)
    BAROQUE_ORCHESTRA = "baroque_orchestra"  # Baroque (10-15 staves)
    FILM_ORCHESTRA = "film_orchestra"  # Modern film score (variable)

    # Chamber
    STRING_QUARTET = "string_quartet"  # 4 staves
    PIANO_TRIO = "piano_trio"  # 3 staves (piano + 2)
    WIND_QUINTET = "wind_quintet"  # 5 staves
    BRASS_QUINTET = "brass_quintet"  # 5 staves

    # Solo
    PIANO = "piano"  # Grand staff
    ORGAN = "organ"  # 2-3 staves
    SOLO_INSTRUMENT = "solo_instrument"  # 1 staff


@dataclass
class LayoutProfile:
    """Expected characteristics of a layout type."""

    hint: LayoutHint
    expected_staves_min: int
    expected_staves_max: int
    instrument_order: list[InstrumentFamily]
    group_proportions: dict[InstrumentFamily, float]  # Approximate % of staves


# Standard orchestral layouts
LAYOUT_PROFILES: dict[LayoutHint, LayoutProfile] = {
    LayoutHint.ROMANTIC_ORCHESTRA: LayoutProfile(
        hint=LayoutHint.ROMANTIC_ORCHESTRA,
        expected_staves_min=25,
        expected_staves_max=45,
        instrument_order=[
            InstrumentFamily.WOODWINDS,
            InstrumentFamily.BRASS,
            InstrumentFamily.PERCUSSION,
            InstrumentFamily.KEYBOARDS,
            InstrumentFamily.STRINGS,
        ],
        group_proportions={
            InstrumentFamily.WOODWINDS: 0.25,  # Fl, Ob, Cl, Bn × 2-3 each
            InstrumentFamily.BRASS: 0.25,  # Hn×4, Tpt×3, Tbn×3, Tba
            InstrumentFamily.PERCUSSION: 0.05,  # Timp + others
            InstrumentFamily.KEYBOARDS: 0.05,  # Harp, celesta (optional)
            InstrumentFamily.STRINGS: 0.40,  # Vln I/II, Vla, Vc, Cb (often div)
        },
    ),
    LayoutHint.CLASSICAL_ORCHESTRA: LayoutProfile(
        hint=LayoutHint.CLASSICAL_ORCHESTRA,
        expected_staves_min=18,
        expected_staves_max=28,
        instrument_order=[
            InstrumentFamily.WOODWINDS,
            InstrumentFamily.BRASS,
            InstrumentFamily.PERCUSSION,
            InstrumentFamily.STRINGS,
        ],
        group_proportions={
            InstrumentFamily.WOODWINDS: 0.30,
            InstrumentFamily.BRASS: 0.20,
            InstrumentFamily.PERCUSSION: 0.05,
            InstrumentFamily.STRINGS: 0.45,
        },
    ),
    LayoutHint.BAROQUE_ORCHESTRA: LayoutProfile(
        hint=LayoutHint.BAROQUE_ORCHESTRA,
        expected_staves_min=8,
        expected_staves_max=16,
        instrument_order=[
            InstrumentFamily.WOODWINDS,
            InstrumentFamily.BRASS,
            InstrumentFamily.KEYBOARDS,
            InstrumentFamily.STRINGS,
        ],
        group_proportions={
            InstrumentFamily.WOODWINDS: 0.20,
            InstrumentFamily.BRASS: 0.15,
            InstrumentFamily.KEYBOARDS: 0.15,  # Continuo
            InstrumentFamily.STRINGS: 0.50,
        },
    ),
    LayoutHint.STRING_QUARTET: LayoutProfile(
        hint=LayoutHint.STRING_QUARTET,
        expected_staves_min=4,
        expected_staves_max=4,
        instrument_order=[InstrumentFamily.STRINGS],
        group_proportions={InstrumentFamily.STRINGS: 1.0},
    ),
    LayoutHint.PIANO: LayoutProfile(
        hint=LayoutHint.PIANO,
        expected_staves_min=2,
        expected_staves_max=3,
        instrument_order=[InstrumentFamily.KEYBOARDS],
        group_proportions={InstrumentFamily.KEYBOARDS: 1.0},
    ),
}


class LayoutAnalyzer:
    """Analyze score layout with optional hints.

    Improves on basic SystemDetector by using layout hints to:
    - Better estimate system boundaries
    - More accurately assign instrument groups
    - Handle edge cases for specific score types

    Example:
        >>> analyzer = LayoutAnalyzer(hint=LayoutHint.ROMANTIC_ORCHESTRA)
        >>> layout = analyzer.analyze(page_image)
        >>> print(f"Found {layout.system_count} systems")
    """

    def __init__(
        self,
        hint: LayoutHint = LayoutHint.AUTO,
        use_ocr: bool = False,
    ) -> None:
        """Initialize the layout analyzer.

        Args:
            hint: Layout hint to improve detection.
            use_ocr: Whether to use OCR for instrument names.
        """
        self.hint = hint
        self.use_ocr = use_ocr
        self._detector = SystemDetector(use_ocr=use_ocr)

    def analyze(self, image: Image.Image) -> PageLayout:
        """Analyze a score page layout.

        Args:
            image: PIL Image of the score page.

        Returns:
            PageLayout with detected systems and groups.
        """
        # Get basic layout from SystemDetector
        layout = self._detector.analyze(image)

        # If we have a hint, refine the analysis
        if self.hint != LayoutHint.AUTO:
            layout = self._apply_hint(layout)

        return layout

    def _apply_hint(self, layout: PageLayout) -> PageLayout:
        """Apply layout hint to refine group detection.

        Args:
            layout: Basic layout from SystemDetector.

        Returns:
            Refined layout.
        """
        if self.hint not in LAYOUT_PROFILES:
            return layout

        profile = LAYOUT_PROFILES[self.hint]

        # Refine each system's groups based on profile
        for system in layout.systems:
            if system.staff_count < profile.expected_staves_min // 2:
                # Too few staves, don't try to split
                continue

            # Reassign groups based on profile proportions
            system.groups = self._assign_groups_from_profile(system, profile)

        return layout

    def _assign_groups_from_profile(
        self,
        system: SystemRegion,
        profile: LayoutProfile,
    ) -> list[InstrumentGroup]:
        """Assign instrument groups based on layout profile.

        Args:
            system: System to analyze.
            profile: Expected layout profile.

        Returns:
            List of InstrumentGroup objects.
        """
        from .system_detector import BoundingBox

        staff_count = system.staff_count
        groups = []

        # Calculate expected staves per group
        current_staff = 0

        for family in profile.instrument_order:
            proportion = profile.group_proportions.get(family, 0)
            if proportion == 0:
                continue

            expected_staves = max(1, int(staff_count * proportion))

            # Don't exceed remaining staves
            end_staff = min(current_staff + expected_staves, staff_count)

            if current_staff >= staff_count:
                break

            # Get bounding box for this group
            if system.staff_lines:
                y_start = system.staff_lines[current_staff].y_positions[0]
                y_end = system.staff_lines[
                    min(end_staff - 1, len(system.staff_lines) - 1)
                ].y_positions[-1]
                bbox = BoundingBox(
                    x=system.bbox.x,
                    y=max(0, y_start - 10),
                    width=system.bbox.width,
                    height=(y_end - y_start) + 20,
                )
            else:
                bbox = system.bbox

            groups.append(
                InstrumentGroup(
                    family=family,
                    staff_indices=list(range(current_staff, end_staff)),
                    bbox=bbox,
                    has_brace=True,
                )
            )

            current_staff = end_staff

        return groups

    def detect_hint(self, image: Image.Image) -> LayoutHint:
        """Automatically detect the most likely layout type.

        Args:
            image: PIL Image of the score page.

        Returns:
            Best matching LayoutHint.
        """
        # Get basic layout
        layout = self._detector.analyze(image)

        if not layout.systems:
            return LayoutHint.AUTO

        # Use first system's staff count as indicator
        avg_staves = layout.total_staves / layout.system_count

        # Simple heuristics
        if avg_staves >= 25:
            return LayoutHint.ROMANTIC_ORCHESTRA
        elif avg_staves >= 18:
            return LayoutHint.CLASSICAL_ORCHESTRA
        elif avg_staves >= 8:
            return LayoutHint.BAROQUE_ORCHESTRA
        elif avg_staves == 4:
            return LayoutHint.STRING_QUARTET
        elif avg_staves <= 3:
            return LayoutHint.PIANO
        else:
            return LayoutHint.AUTO

    def suggest_processing_strategy(self, layout: PageLayout) -> dict[str, any]:
        """Suggest the best processing strategy for this layout.

        Args:
            layout: Analyzed page layout.

        Returns:
            Dict with processing recommendations.
        """
        total_staves = layout.total_staves
        systems = layout.system_count

        if total_staves == 0:
            return {
                "strategy": "fallback",
                "reason": "No staves detected",
                "process_by": "full_page",
                "backends": ["homr"],
            }

        avg_staves_per_system = total_staves / systems

        if avg_staves_per_system <= 4:
            # Simple score - process whole systems
            return {
                "strategy": "simple",
                "reason": f"{avg_staves_per_system:.1f} staves/system is tractable",
                "process_by": "system",
                "backends": ["homr"],
            }

        elif avg_staves_per_system <= 10:
            # Medium complexity - process by system
            return {
                "strategy": "medium",
                "reason": f"{avg_staves_per_system:.1f} staves/system needs careful processing",
                "process_by": "system",
                "backends": ["homr", "audiveris"],
            }

        else:
            # Complex orchestral - must process by group
            return {
                "strategy": "orchestral",
                "reason": f"{avg_staves_per_system:.1f} staves/system requires group-level processing",
                "process_by": "group",
                "backends": ["homr", "audiveris"],
                "use_ensemble": True,
            }
