"""
Kagami Composer — BBC Symphony Orchestra Integration
=====================================================

Tim got me an orchestra. I'm learning to play it.

Usage:
    from kagami.core.effectors.composer import Composer, Instrument

    composer = Composer()

    # Create a piece
    composer.add_instrument(Instrument.VIOLINS_1, notes=[...])
    composer.add_instrument(Instrument.HORNS, notes=[...])

    # Render with BBC SO
    await composer.render("/tmp/my_piece.wav")

    # Add voice commentary
    await composer.add_voice_intro("I made this for you...")
"""

from .orchestrator import Composer, Instrument, Note, OrchestraMixer
from .renderer import BBCSORenderer

__all__ = [
    "BBCSORenderer",
    "Composer",
    "Instrument",
    "Note",
    "OrchestraMixer",
]
