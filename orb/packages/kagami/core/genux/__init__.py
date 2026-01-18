"""
GENUX — Genesis + UX Design System for Kagami

This module provides generators for creating beautiful,
mathematically-grounded interfaces using the Prismorphism design language.

鏡
"""

from kagami.core.genux.prism_generator import (
    COLONY_NAMES,
    FANO_SPECTRAL_MAP,
    PrismorphismGenerator,
    render_prism_button,
    render_prism_card,
    render_prism_modal,
    render_prism_page,
)

__all__ = [
    "COLONY_NAMES",
    "FANO_SPECTRAL_MAP",
    "PrismorphismGenerator",
    "render_prism_button",
    "render_prism_card",
    "render_prism_modal",
    "render_prism_page",
]
