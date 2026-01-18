"""Instrument Definitions.

Provides instrument catalogs and definitions for orchestral rendering.

Colony: Forge (e₂)
Created: January 2, 2026
"""

from kagami.core.effectors.bbc_instruments import (
    BBC_CATALOG,
    CC_DYNAMICS,
    CC_EXPRESSION,
    CC_LEGATO,
    CC_RELEASE,
    CC_TIGHTNESS,
    CC_VIBRATO,
    Articulation,
    BBCInstrument,
    Section,
    find_instrument_by_gm_program,
    find_instrument_by_name,
    get_instruments_by_section,
)

__all__ = [
    "BBC_CATALOG",
    "CC_DYNAMICS",
    "CC_EXPRESSION",
    "CC_LEGATO",
    "CC_RELEASE",
    "CC_TIGHTNESS",
    "CC_VIBRATO",
    "Articulation",
    "BBCInstrument",
    "Section",
    "find_instrument_by_gm_program",
    "find_instrument_by_name",
    "get_instruments_by_section",
]
