"""BBC Symphony Orchestra Instrument Catalog.

Complete catalog of all 45 instruments in BBC Symphony Orchestra Core,
extracted directly from the BBC SO v1.5.0 source patch files.

Source: /Spitfire Audio - BBC Symphony Orchestra/Patches/v1.5.0/*.zmulti
Pattern: BBCSOC_<prefix>___<InstrumentName>___<Articulation>.zmulti

Reference: BBC Symphony Orchestra User Manual
https://www.spitfireaudio.com/bbc-symphony-orchestra

Colony: Forge (e₂)
Updated: January 1, 2026 — Ground truth extraction from source files
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import ClassVar

from kagami.core.effectors.vbap_core import Pos3D

# =============================================================================
# Enums
# =============================================================================


class Section(Enum):
    """Orchestra sections."""

    STRINGS = "strings"
    WOODWINDS = "woodwinds"
    BRASS = "brass"
    PERCUSSION_TUNED = "percussion_tuned"
    PERCUSSION_UNTUNED = "percussion_untuned"


class Articulation(Enum):
    """Standard articulation types."""

    LONG = "long"
    LEGATO = "legato"
    SPICCATO = "spiccato"
    STACCATO = "staccato"
    STACCATISSIMO = "staccatissimo"
    PIZZICATO = "pizzicato"
    TREMOLO = "tremolo"
    TRILL = "trill"
    MARCATO = "marcato"
    TENUTO = "tenuto"


# =============================================================================
# MIDI CC Constants
# =============================================================================

CC_DYNAMICS = 1  # CC1: Dynamics (crossfades between dynamic layers)
CC_EXPRESSION = 11  # CC11: Expression (volume without timbre change)
CC_VIBRATO = 21  # CC21: Vibrato amount
CC_RELEASE = 64  # CC64: Sustain pedal (release trigger)
CC_LEGATO = 68  # CC68: Legato on/off
CC_TIGHTNESS = 20  # CC20: Tightness control


# =============================================================================
# Instrument Definition
# =============================================================================


@dataclass
class BBCInstrument:
    """BBC Symphony Orchestra instrument definition.

    Attributes:
        name: Display name (exact BBC SO name)
        key: Unique identifier (snake_case)
        section: Orchestra section
        players: Number of players in the section
        range_low: Lowest MIDI note
        range_high: Highest MIDI note
        articulations: Map of articulation name to keyswitch note
        default_articulation: Default articulation when none specified
        default_cc1: Default dynamics value (0-127)
        default_cc11: Default expression value (0-127)
        position: 3D position in orchestra layout
        mic_positions: Available microphone positions
        edition: Required edition ("core" or "professional")
    """

    name: str
    key: str
    section: Section
    players: int = 1
    range_low: int = 21
    range_high: int = 108
    articulations: dict[str, int] = field(default_factory=dict)
    default_articulation: str = "Long"
    default_cc1: int = 80
    default_cc11: int = 100
    position: Pos3D = field(default_factory=lambda: Pos3D(0, 0, 5))
    mic_positions: list[str] = field(
        default_factory=lambda: ["Close", "Tree", "Ambient", "Outriggers"]
    )
    edition: str = "core"  # "core" or "professional"

    # Class-level constants
    DEFAULT_CC1: ClassVar[int] = 80
    DEFAULT_CC11: ClassVar[int] = 100

    def get_keyswitch(self, articulation: str) -> int | None:
        """Get keyswitch MIDI note for an articulation."""
        return self.articulations.get(articulation)

    def get_articulation_list(self) -> list[str]:
        """Get list of all articulation names."""
        return list(self.articulations.keys())


# =============================================================================
# BBC SYMPHONY ORCHESTRA — COMPLETE INSTRUMENT CATALOG
# =============================================================================
# Extracted from: BBC SO v1.5.0 source patch files (467 files total)
# 45 instruments, 467 articulations

BBC_CATALOG: dict[str, BBCInstrument] = {
    # Bass_Clarinet (8 articulations)
    "bass_clarinet": BBCInstrument(
        name="Bass_Clarinet",
        key="bass_clarinet",
        section=Section.WOODWINDS,
        players=1,
        range_low=38,
        range_high=82,
        articulations={
            "Legato": 12,
            "Legato (Extended)": 13,
            "Long": 14,
            "Long Flutter": 15,
            "Short Staccatissimo": 16,
            "Short Marcato": 17,
            "Trill (Major 2nd)": 18,
            "Trill (Minor 2nd)": 19,
        },
        default_articulation="Legato",
    ),
    # Bass_Flute (7 articulations)
    "bass_flute": BBCInstrument(
        name="Bass_Flute",
        key="bass_flute",
        section=Section.WOODWINDS,
        players=1,
        range_low=48,
        range_high=84,
        edition="professional",
        articulations={
            "Long": 12,
            "Long Flutter": 13,
            "Short Staccatissimo": 14,
            "Short Marcato": 15,
            "Short Tenuto": 16,
            "Trill (Major 2nd)": 17,
            "Trill (Minor 2nd)": 18,
        },
        default_articulation="Long",
    ),
    # Bass_Leader (16 articulations)
    "bass_leader": BBCInstrument(
        name="Bass_Leader",
        key="bass_leader",
        section=Section.STRINGS,
        players=1,
        range_low=28,
        range_high=60,
        edition="professional",
        articulations={
            "Legato": 12,
            "Long": 13,
            "Long CS": 14,
            "Long Flautando": 15,
            "Long Sul Tasto": 16,
            "Long Harmonics": 17,
            "Short Spiccato": 18,
            "Short Staccato": 19,
            "Short Marcato": 20,
            "Short Pizzicato": 21,
            "Short Pizzicato Bartok": 22,
            "Short Col Legno": 23,
            "Short Harmonics": 24,
            "Tremolo": 25,
            "Trill (Major 2nd)": 26,
            "Trill (Minor 2nd)": 27,
        },
        default_articulation="Legato",
    ),
    # Bass_Trombones_a2 (11 articulations)
    "bass_trombones_a2": BBCInstrument(
        name="Bass_Trombones_a2",
        key="bass_trombones_a2",
        section=Section.BRASS,
        players=2,
        range_low=34,
        range_high=65,
        articulations={
            "Legato": 12,
            "Long": 13,
            "Long Cuivre": 14,
            "Long Sfz": 15,
            "Long Flutter": 16,
            "Long (Muted)": 17,
            "Short Staccatissimo": 18,
            "Short Marcato": 19,
            "Short Marcato (Muted)": 20,
            "Short Staccatissimo (Muted)": 21,
            "Multitongue": 22,
        },
        default_articulation="Legato",
    ),
    # Basses (20 articulations)
    "basses": BBCInstrument(
        name="Basses",
        key="basses",
        section=Section.STRINGS,
        players=8,
        range_low=28,
        range_high=60,
        articulations={
            "Legato": 12,
            "Long": 13,
            "Long CS": 14,
            "Long Flautando": 15,
            "Long Sul Tasto": 16,
            "Long Sul Pont": 17,
            "Long Harmonics": 18,
            "Long Marcato Attack": 19,
            "Short Spiccato": 20,
            "Short Spiccato CS": 21,
            "Short Staccato": 22,
            "Short Pizzicato": 23,
            "Short Pizzicato Bartok": 24,
            "Short Col Legno": 25,
            "Short Harmonics": 26,
            "Tremolo": 27,
            "Tremolo CS": 28,
            "Tremolo Sul Pont": 29,
            "Trill (Major 2nd)": 30,
            "Trill (Minor 2nd)": 31,
        },
        default_articulation="Legato",
    ),
    # Bassoon (9 articulations)
    "bassoon": BBCInstrument(
        name="Bassoon",
        key="bassoon",
        section=Section.WOODWINDS,
        players=1,
        range_low=34,
        range_high=75,
        articulations={
            "Legato": 12,
            "Legato (Extended)": 13,
            "Long": 14,
            "Long Flutter": 15,
            "Short Staccatissimo": 16,
            "Short Marcato": 17,
            "Short Tenuto": 18,
            "Trill (Major 2nd)": 19,
            "Trill (Minor 2nd)": 20,
        },
        default_articulation="Legato",
    ),
    # Bassoons_a3 (8 articulations)
    "bassoons_a3": BBCInstrument(
        name="Bassoons_a3",
        key="bassoons_a3",
        section=Section.WOODWINDS,
        players=3,
        range_low=34,
        range_high=72,
        articulations={
            "Legato": 12,
            "Long": 13,
            "Long Flutter": 14,
            "Short Staccatissimo": 15,
            "Short Marcato": 16,
            "Short Tenuto": 17,
            "Trill (Major 2nd)": 18,
            "Trill (Minor 2nd)": 19,
        },
        default_articulation="Legato",
    ),
    # Celeste (4 articulations)
    "celeste": BBCInstrument(
        name="Celeste",
        key="celeste",
        section=Section.PERCUSSION_TUNED,
        players=1,
        range_low=60,
        range_high=108,
        articulations={
            "Short Damped": 12,
            "Short Damped Medium": 13,
            "Short Sustained": 14,
            "Short Sustained Discover": 15,
        },
        default_articulation="Short Damped",
    ),
    # Celli (20 articulations)
    "celli": BBCInstrument(
        name="Celli",
        key="celli",
        section=Section.STRINGS,
        players=10,
        range_low=36,
        range_high=76,
        articulations={
            "Legato": 12,
            "Long": 13,
            "Long CS": 14,
            "Long Flautando": 15,
            "Long Sul Tasto": 16,
            "Long Sul Pont": 17,
            "Long Harmonics": 18,
            "Long Marcato Attack": 19,
            "Short Spiccato": 20,
            "Short Staccato": 21,
            "Short Pizzicato": 22,
            "Short Pizzicato Bartok": 23,
            "Short Col Legno": 24,
            "Short Harmonics": 25,
            "Tremolo": 26,
            "Tremolo CS": 27,
            "Tremolo Sul Pont": 28,
            "Trill (Major 2nd)": 29,
            "Trill (Minor 2nd)": 30,
            "Short Spicc CS": 31,
        },
        default_articulation="Legato",
    ),
    # Celli_Leader (16 articulations)
    "celli_leader": BBCInstrument(
        name="Celli_Leader",
        key="celli_leader",
        section=Section.STRINGS,
        players=1,
        range_low=36,
        range_high=76,
        edition="professional",
        articulations={
            "Legato": 12,
            "Long": 13,
            "Long CS": 14,
            "Long Flautando": 15,
            "Long Sul Tasto": 16,
            "Long Harmonics": 17,
            "Short Spiccato": 18,
            "Short Staccato": 19,
            "Short Marcato": 20,
            "Short Pizzicato": 21,
            "Short Pizzicato Bartok": 22,
            "Short Col Legno": 23,
            "Short Harmonics": 24,
            "Tremolo": 25,
            "Trill (Major 2nd)": 26,
            "Trill (Minor 2nd)": 27,
        },
        default_articulation="Legato",
    ),
    # Cimbasso (5 articulations)
    "cimbasso": BBCInstrument(
        name="Cimbasso",
        key="cimbasso",
        section=Section.BRASS,
        players=1,
        range_low=24,
        range_high=53,
        articulations={
            "Long": 12,
            "Long Cuivre": 13,
            "Long Sfz": 14,
            "Short Staccatissimo": 15,
            "Short Marcato": 16,
        },
        default_articulation="Long",
    ),
    # Clarinet (10 articulations)
    "clarinet": BBCInstrument(
        name="Clarinet",
        key="clarinet",
        section=Section.WOODWINDS,
        players=1,
        range_low=50,
        range_high=94,
        articulations={
            "Legato": 12,
            "Legato (Extended)": 13,
            "Long": 14,
            "Long Flutter": 15,
            "Short Staccatissimo": 16,
            "Short Marcato": 17,
            "Short Tenuto": 18,
            "Trill (Major 2nd)": 19,
            "Trill (Minor 2nd)": 20,
            "Multitongue": 21,
        },
        default_articulation="Legato",
    ),
    # Clarinets_a3 (9 articulations)
    "clarinets_a3": BBCInstrument(
        name="Clarinets_a3",
        key="clarinets_a3",
        section=Section.WOODWINDS,
        players=3,
        range_low=50,
        range_high=91,
        articulations={
            "Legato": 12,
            "Long": 13,
            "Long Flutter": 14,
            "Short Staccatissimo": 15,
            "Short Marcato": 16,
            "Short Tenuto": 17,
            "Trill (Major 2nd)": 18,
            "Trill (Minor 2nd)": 19,
            "Multitongue": 20,
        },
        default_articulation="Legato",
    ),
    # Contrabass_Clarinet (7 articulations)
    "contrabass_clarinet": BBCInstrument(
        name="Contrabass_Clarinet",
        key="contrabass_clarinet",
        section=Section.WOODWINDS,
        players=1,
        range_low=26,
        range_high=70,
        edition="professional",
        articulations={
            "Legato": 12,
            "Long": 13,
            "Long Flutter": 14,
            "Short Staccatissimo": 15,
            "Short Marcato": 16,
            "Trill (Major 2nd)": 17,
            "Trill (Minor 2nd)": 18,
        },
        default_articulation="Legato",
    ),
    # Contrabass_Trombone (6 articulations)
    "contrabass_trombone": BBCInstrument(
        name="Contrabass_Trombone",
        key="contrabass_trombone",
        section=Section.BRASS,
        players=1,
        range_low=28,
        range_high=58,
        articulations={
            "Legato": 12,
            "Long": 13,
            "Long Cuivre": 14,
            "Long Sfz": 15,
            "Short Staccatissimo": 16,
            "Short Marcato": 17,
        },
        default_articulation="Legato",
    ),
    # Contrabass_Tuba (6 articulations)
    "contrabass_tuba": BBCInstrument(
        name="Contrabass_Tuba",
        key="contrabass_tuba",
        section=Section.BRASS,
        players=1,
        range_low=24,
        range_high=53,
        articulations={
            "Legato": 12,
            "Long": 13,
            "Long Cuivre": 14,
            "Long Sfz": 15,
            "Short Staccatissimo": 16,
            "Short Marcato": 17,
        },
        default_articulation="Legato",
    ),
    # Contrabassoon (7 articulations)
    "contrabassoon": BBCInstrument(
        name="Contrabassoon",
        key="contrabassoon",
        section=Section.WOODWINDS,
        players=1,
        range_low=22,
        range_high=58,
        articulations={
            "Legato": 12,
            "Long": 13,
            "Long Flutter": 14,
            "Short Staccatissimo": 15,
            "Short Marcato": 16,
            "Trill (Major 2nd)": 17,
            "Trill (Minor 2nd)": 18,
        },
        default_articulation="Legato",
    ),
    # Cor_Anglais (8 articulations)
    "cor_anglais": BBCInstrument(
        name="Cor_Anglais",
        key="cor_anglais",
        section=Section.WOODWINDS,
        players=1,
        range_low=52,
        range_high=84,
        articulations={
            "Legato": 12,
            "Legato (Extended)": 13,
            "Long": 14,
            "Short Staccatissimo": 15,
            "Short Marcato": 16,
            "Short Tenuto": 17,
            "Trill (Major 2nd)": 18,
            "Trill (Minor 2nd)": 19,
        },
        default_articulation="Legato",
    ),
    # Crotales (2 articulations)
    "crotales": BBCInstrument(
        name="Crotales",
        key="crotales",
        section=Section.PERCUSSION_TUNED,
        players=1,
        range_low=84,
        range_high=108,
        articulations={
            "Short Hits": 12,
            "Short Hits Bowed": 13,
        },
        default_articulation="Short Hits",
    ),
    # Flute (10 articulations)
    "flute": BBCInstrument(
        name="Flute",
        key="flute",
        section=Section.WOODWINDS,
        players=1,
        range_low=60,
        range_high=96,
        articulations={
            "Legato": 12,
            "Legato (Extended)": 13,
            "Long": 14,
            "Long Flutter": 15,
            "Short Staccatissimo": 16,
            "Short Marcato": 17,
            "Short Tenuto": 18,
            "Trill (Major 2nd)": 19,
            "Trill (Minor 2nd)": 20,
            "Multitongue": 21,
        },
        default_articulation="Legato",
    ),
    # Flutes_a3 (10 articulations)
    "flutes_a3": BBCInstrument(
        name="Flutes_a3",
        key="flutes_a3",
        section=Section.WOODWINDS,
        players=3,
        range_low=60,
        range_high=96,
        articulations={
            "Legato": 12,
            "Legato (Extended)": 13,
            "Long": 14,
            "Long Flutter": 15,
            "Short Staccatissimo": 16,
            "Short Marcato": 17,
            "Short Tenuto": 18,
            "Trill (Major 2nd)": 19,
            "Trill (Minor 2nd)": 20,
            "Multitongue": 21,
        },
        default_articulation="Legato",
    ),
    # Glockenspiel (3 articulations)
    "glockenspiel": BBCInstrument(
        name="Glockenspiel",
        key="glockenspiel",
        section=Section.PERCUSSION_TUNED,
        players=1,
        range_low=79,
        range_high=108,
        articulations={
            "Long Trills": 12,
            "Short Hits": 13,
            "Short Hits Discover": 14,
        },
        default_articulation="Long Trills",
    ),
    # Harp (6 articulations)
    "harp": BBCInstrument(
        name="Harp",
        key="harp",
        section=Section.PERCUSSION_TUNED,
        players=1,
        range_low=24,
        range_high=103,
        articulations={
            "Long Bisbigliando Trem": 12,
            "Short Damped": 13,
            "Short Damped Medium": 14,
            "Short Gliss": 15,
            "Short Sustained": 16,
            "Short Sustained Discover": 17,
        },
        default_articulation="Long Bisbigliando Trem",
    ),
    # Horn (14 articulations)
    "horn": BBCInstrument(
        name="Horn",
        key="horn",
        section=Section.BRASS,
        players=1,
        range_low=41,
        range_high=77,
        articulations={
            "Legato": 12,
            "Legato (Extended)": 13,
            "Long": 14,
            "Long Cuivre": 15,
            "Long Sfz": 16,
            "Long Flutter": 17,
            "Long (Muted)": 18,
            "Short Staccatissimo": 19,
            "Short Marcato": 20,
            "Short Marcato (Muted)": 21,
            "Short Staccatissimo (Muted)": 22,
            "Trill (Major 2nd)": 23,
            "Trill (Minor 2nd)": 24,
            "Multitongue": 25,
        },
        default_articulation="Legato",
    ),
    # Horns_a4 (13 articulations)
    "horns_a4": BBCInstrument(
        name="Horns_a4",
        key="horns_a4",
        section=Section.BRASS,
        players=4,
        range_low=41,
        range_high=77,
        articulations={
            "Legato": 12,
            "Long": 13,
            "Long Cuivre": 14,
            "Long Sfz": 15,
            "Long Flutter": 16,
            "Long (Muted)": 17,
            "Short Staccatissimo": 18,
            "Short Marcato": 19,
            "Short Marcato (Muted)": 20,
            "Short Staccatissimo (Muted)": 21,
            "Trill (Major 2nd)": 22,
            "Trill (Minor 2nd)": 23,
            "Multitongue": 24,
        },
        default_articulation="Legato",
    ),
    # Marimba (3 articulations)
    "marimba": BBCInstrument(
        name="Marimba",
        key="marimba",
        section=Section.PERCUSSION_TUNED,
        players=1,
        range_low=45,
        range_high=96,
        articulations={
            "Long Trills": 12,
            "Short Hits": 13,
            "Short Hits Discover": 14,
        },
        default_articulation="Long Trills",
    ),
    # Oboe (9 articulations)
    "oboe": BBCInstrument(
        name="Oboe",
        key="oboe",
        section=Section.WOODWINDS,
        players=1,
        range_low=58,
        range_high=91,
        articulations={
            "Legato": 12,
            "Legato (Extended)": 13,
            "Long": 14,
            "Short Staccatissimo": 15,
            "Short Marcato": 16,
            "Short Tenuto": 17,
            "Trill (Major 2nd)": 18,
            "Trill (Minor 2nd)": 19,
            "Multitongue": 20,
        },
        default_articulation="Legato",
    ),
    # Oboes_a3 (8 articulations)
    "oboes_a3": BBCInstrument(
        name="Oboes_a3",
        key="oboes_a3",
        section=Section.WOODWINDS,
        players=3,
        range_low=58,
        range_high=88,
        articulations={
            "Legato": 12,
            "Long": 13,
            "Short Staccatissimo": 14,
            "Short Marcato": 15,
            "Short Tenuto": 16,
            "Trill (Major 2nd)": 17,
            "Trill (Minor 2nd)": 18,
            "Multitongue": 19,
        },
        default_articulation="Legato",
    ),
    # Piccolo (12 articulations)
    "piccolo": BBCInstrument(
        name="Piccolo",
        key="piccolo",
        section=Section.WOODWINDS,
        players=1,
        range_low=74,
        range_high=108,
        articulations={
            "Legato": 12,
            "Legato (Extended)": 13,
            "Long": 14,
            "Long Flutter": 15,
            "Short Staccatissimo": 16,
            "Short Marcato": 17,
            "Short Tenuto": 18,
            "Trill (Major 2nd)": 19,
            "Trill (Minor 2nd)": 20,
            "Multitongue": 21,
            "Falls": 22,
            "Rips": 23,
        },
        default_articulation="Legato",
    ),
    # Tenor_Trombone (12 articulations)
    "tenor_trombone": BBCInstrument(
        name="Tenor_Trombone",
        key="tenor_trombone",
        section=Section.BRASS,
        players=1,
        range_low=40,
        range_high=72,
        articulations={
            "Legato": 12,
            "Legato (Extended)": 13,
            "Long": 14,
            "Long Cuivre": 15,
            "Long Sfz": 16,
            "Long Flutter": 17,
            "Long (Muted)": 18,
            "Short Staccatissimo": 19,
            "Short Marcato": 20,
            "Short Marcato (Muted)": 21,
            "Short Staccatissimo (Muted)": 22,
            "Multitongue": 23,
        },
        default_articulation="Legato",
    ),
    # Tenor_Trombones_a3 (11 articulations)
    "tenor_trombones_a3": BBCInstrument(
        name="Tenor_Trombones_a3",
        key="tenor_trombones_a3",
        section=Section.BRASS,
        players=3,
        range_low=40,
        range_high=70,
        articulations={
            "Legato": 12,
            "Long": 13,
            "Long Cuivre": 14,
            "Long Sfz": 15,
            "Long Flutter": 16,
            "Long (Muted)": 17,
            "Short Staccatissimo": 18,
            "Short Marcato": 19,
            "Short Marcato (Muted)": 20,
            "Short Staccatissimo (Muted)": 21,
            "Multitongue": 22,
        },
        default_articulation="Legato",
    ),
    # Timpani (11 articulations)
    "timpani": BBCInstrument(
        name="Timpani",
        key="timpani",
        section=Section.PERCUSSION_TUNED,
        players=1,
        range_low=40,
        range_high=57,
        articulations={
            "Hotrods Hits Damped": 12,
            "Long Rolls": 13,
            "Long Rolls Hotrods": 14,
            "Long Rolls Soft": 15,
            "Short Hits": 16,
            "Short Hits Damped": 17,
            "Short Hits Damped Soft": 18,
            "Short Hits Discover": 19,
            "Short Hits Hotrods": 20,
            "Short Hits Soft": 21,
            "Short Hits Super Damped": 22,
        },
        default_articulation="Hotrods Hits Damped",
    ),
    # Trumpet (14 articulations)
    "trumpet": BBCInstrument(
        name="Trumpet",
        key="trumpet",
        section=Section.BRASS,
        players=1,
        range_low=55,
        range_high=84,
        articulations={
            "Legato": 12,
            "Legato (Extended)": 13,
            "Long": 14,
            "Long Cuivre": 15,
            "Long Sfz": 16,
            "Long Flutter": 17,
            "Long (Muted)": 18,
            "Short Staccatissimo": 19,
            "Short Marcato": 20,
            "Short Marcato (Muted)": 21,
            "Short Staccatissimo (Muted)": 22,
            "Trill (Major 2nd)": 23,
            "Trill (Minor 2nd)": 24,
            "Multitongue": 25,
        },
        default_articulation="Legato",
    ),
    # Trumpets_a2 (14 articulations)
    "trumpets_a2": BBCInstrument(
        name="Trumpets_a2",
        key="trumpets_a2",
        section=Section.BRASS,
        players=2,
        range_low=55,
        range_high=82,
        articulations={
            "Legato": 12,
            "Legato (Extended)": 13,
            "Long": 14,
            "Long Cuivre": 15,
            "Long Sfz": 16,
            "Long Flutter": 17,
            "Long (Muted)": 18,
            "Short Staccatissimo": 19,
            "Short Marcato": 20,
            "Short Marcato (Muted)": 21,
            "Short Staccatissimo (Muted)": 22,
            "Trill (Major 2nd)": 23,
            "Trill (Minor 2nd)": 24,
            "Multitongue": 25,
        },
        default_articulation="Legato",
    ),
    # Tuba (8 articulations)
    "tuba": BBCInstrument(
        name="Tuba",
        key="tuba",
        section=Section.BRASS,
        players=1,
        range_low=28,
        range_high=58,
        articulations={
            "Legato": 12,
            "Long": 13,
            "Long Cuivre": 14,
            "Long Sfz": 15,
            "Long Flutter": 16,
            "Short Staccatissimo": 17,
            "Short Marcato": 18,
            "Multitongue": 19,
        },
        default_articulation="Legato",
    ),
    # Tubular_bells (4 articulations)
    "tubular_bells": BBCInstrument(
        name="Tubular_bells",
        key="tubular_bells",
        section=Section.PERCUSSION_TUNED,
        players=1,
        range_low=60,
        range_high=77,
        articulations={
            "Long Rolls": 12,
            "Short Hits": 13,
            "Short Hits Damped": 14,
            "Short Hits Discover": 15,
        },
        default_articulation="Long Rolls",
    ),
    # Untuned_Percussion (14 articulations)
    "untuned_percussion": BBCInstrument(
        name="Untuned_Percussion",
        key="untuned_percussion",
        section=Section.PERCUSSION_UNTUNED,
        players=1,
        range_low=36,
        range_high=84,
        articulations={
            "Anvil": 12,
            "Bass Drum 1": 13,
            "Bass Drum 2": 14,
            "Cymbal": 15,
            "Hits": 16,
            "Military Drum": 17,
            "Piatti": 18,
            "Snare 1": 19,
            "Snare 2": 20,
            "Tam Tam": 21,
            "Tambourine": 22,
            "Tenor Drum": 23,
            "Toys": 24,
            "Triangle": 25,
        },
        default_articulation="Anvil",
    ),
    # Vibraphone (1 articulations)
    "vibraphone": BBCInstrument(
        name="Vibraphone",
        key="vibraphone",
        section=Section.PERCUSSION_TUNED,
        players=1,
        range_low=53,
        range_high=89,
        articulations={
            "Short Hits": 12,
        },
        default_articulation="Short Hits",
    ),
    # Viola_Leader (16 articulations)
    "viola_leader": BBCInstrument(
        name="Viola_Leader",
        key="viola_leader",
        section=Section.STRINGS,
        players=1,
        range_low=48,
        range_high=88,
        edition="professional",
        articulations={
            "Legato": 12,
            "Long": 13,
            "Long CS": 14,
            "Long Flautando": 15,
            "Long Sul Tasto": 16,
            "Long Harmonics": 17,
            "Short Spiccato": 18,
            "Short Staccato": 19,
            "Short Marcato": 20,
            "Short Pizzicato": 21,
            "Short Pizzicato Bartok": 22,
            "Short Col Legno": 23,
            "Short Harmonics": 24,
            "Tremolo": 25,
            "Trill (Major 2nd)": 26,
            "Trill (Minor 2nd)": 27,
        },
        default_articulation="Legato",
    ),
    # Violas (20 articulations)
    "violas": BBCInstrument(
        name="Violas",
        key="violas",
        section=Section.STRINGS,
        players=12,
        range_low=48,
        range_high=88,
        articulations={
            "Legato": 12,
            "Long": 13,
            "Long CS": 14,
            "Long Flautando": 15,
            "Long Sul Tasto": 16,
            "Long Sul Pont": 17,
            "Long Harmonics": 18,
            "Long Marcato Attack": 19,
            "Short Spiccato": 20,
            "Short Spiccato CS": 21,
            "Short Staccato": 22,
            "Short Pizzicato": 23,
            "Short Pizzicato Bartok": 24,
            "Short Col Legno": 25,
            "Short Harmonics": 26,
            "Tremolo": 27,
            "Tremolo CS": 28,
            "Tremolo Sul Pont": 29,
            "Trill (Major 2nd)": 30,
            "Trill (Minor 2nd)": 31,
        },
        default_articulation="Legato",
    ),
    # Violin_1_Leader (16 articulations)
    "violin_1_leader": BBCInstrument(
        name="Violin_1_Leader",
        key="violin_1_leader",
        section=Section.STRINGS,
        players=1,
        range_low=55,
        range_high=96,
        edition="professional",
        articulations={
            "Legato": 12,
            "Long": 13,
            "Long CS": 14,
            "Long Flautando": 15,
            "Long Sul Tasto": 16,
            "Long Harmonics": 17,
            "Short Spiccato": 18,
            "Short Staccato": 19,
            "Short Marcato": 20,
            "Short Pizzicato": 21,
            "Short Pizzicato Bartok": 22,
            "Short Col Legno": 23,
            "Short Harmonics": 24,
            "Tremolo": 25,
            "Trill (Major 2nd)": 26,
            "Trill (Minor 2nd)": 27,
        },
        default_articulation="Legato",
    ),
    # Violin_2_Leader (16 articulations)
    "violin_2_leader": BBCInstrument(
        name="Violin_2_Leader",
        key="violin_2_leader",
        section=Section.STRINGS,
        players=1,
        range_low=55,
        range_high=96,
        edition="professional",
        articulations={
            "Legato": 12,
            "Long": 13,
            "Long CS": 14,
            "Long Flautando": 15,
            "Long Sul Tasto": 16,
            "Long Harmonics": 17,
            "Short Spiccato": 18,
            "Short Staccato": 19,
            "Short Marcato": 20,
            "Short Pizzicato": 21,
            "Short Pizzicato Bartok": 22,
            "Short Col Legno": 23,
            "Short Harmonics": 24,
            "Tremolo": 25,
            "Trill (Major 2nd)": 26,
            "Trill (Minor 2nd)": 27,
        },
        default_articulation="Legato",
    ),
    # Violins_1 (20 articulations)
    "violins_1": BBCInstrument(
        name="Violins_1",
        key="violins_1",
        section=Section.STRINGS,
        players=16,
        range_low=55,
        range_high=96,
        articulations={
            "Legato": 12,
            "Long": 13,
            "Long CS": 14,
            "Long Flautando": 15,
            "Long Sul Tasto": 16,
            "Long Sul Pont": 17,
            "Long Harmonics": 18,
            "Long Marcato Attack": 19,
            "Short Spiccato": 20,
            "Short Spiccato CS": 21,
            "Short Staccato": 22,
            "Short Pizzicato": 23,
            "Short Pizzicato Bartok": 24,
            "Short Col Legno": 25,
            "Short Harmonics": 26,
            "Tremolo": 27,
            "Tremolo CS": 28,
            "Tremolo Sul Pont": 29,
            "Trill (Major 2nd)": 30,
            "Trill (Minor 2nd)": 31,
        },
        default_articulation="Legato",
    ),
    # Violins_2 (20 articulations)
    "violins_2": BBCInstrument(
        name="Violins_2",
        key="violins_2",
        section=Section.STRINGS,
        players=14,
        range_low=55,
        range_high=96,
        articulations={
            "Legato": 12,
            "Long": 13,
            "Long CS": 14,
            "Long Flautando": 15,
            "Long Sul Tasto": 16,
            "Long Sul Pont": 17,
            "Long Harmonics": 18,
            "Long Marcato Attack": 19,
            "Short Spiccato": 20,
            "Short Spiccato CS": 21,
            "Short Staccato": 22,
            "Short Pizzicato": 23,
            "Short Pizzicato Bartok": 24,
            "Short Col Legno": 25,
            "Short Harmonics": 26,
            "Tremolo": 27,
            "Tremolo CS": 28,
            "Tremolo Sul Pont": 29,
            "Trill (Major 2nd)": 30,
            "Trill (Minor 2nd)": 31,
        },
        default_articulation="Legato",
    ),
    # Xylophone (3 articulations)
    "xylophone": BBCInstrument(
        name="Xylophone",
        key="xylophone",
        section=Section.PERCUSSION_TUNED,
        players=1,
        range_low=65,
        range_high=108,
        articulations={
            "Long Trills": 12,
            "Short Hits": 13,
            "Short Hits Discover": 14,
        },
        default_articulation="Long Trills",
    ),
}


# =============================================================================
# Section Lists (for backwards compatibility)
# =============================================================================

BBC_STRINGS = [k for k, v in BBC_CATALOG.items() if v.section == Section.STRINGS]
BBC_WOODWINDS = [k for k, v in BBC_CATALOG.items() if v.section == Section.WOODWINDS]
BBC_BRASS = [k for k, v in BBC_CATALOG.items() if v.section == Section.BRASS]
BBC_PERCUSSION_TUNED = [k for k, v in BBC_CATALOG.items() if v.section == Section.PERCUSSION_TUNED]
BBC_PERCUSSION_UNTUNED = [
    k for k, v in BBC_CATALOG.items() if v.section == Section.PERCUSSION_UNTUNED
]

BBC_SECTIONS = {
    Section.STRINGS: BBC_STRINGS,
    Section.WOODWINDS: BBC_WOODWINDS,
    Section.BRASS: BBC_BRASS,
    Section.PERCUSSION_TUNED: BBC_PERCUSSION_TUNED,
    Section.PERCUSSION_UNTUNED: BBC_PERCUSSION_UNTUNED,
}


# =============================================================================
# Helper Functions
# =============================================================================


def get_instrument(key: str) -> BBCInstrument | None:
    """Get instrument by key."""
    return BBC_CATALOG.get(key)


def get_instruments_by_section(section: Section) -> list[BBCInstrument]:
    """Get all instruments in a section."""
    return [i for i in BBC_CATALOG.values() if i.section == section]


def get_all_keys() -> list[str]:
    """Get all instrument keys."""
    return list(BBC_CATALOG.keys())


def find_instrument_by_gm_program(program: int) -> BBCInstrument | None:
    """Find BBC instrument matching a General MIDI program number.

    This provides a rough mapping from GM programs to BBC SO instruments.
    """
    # GM Program -> BBC SO key mapping
    gm_map = {
        # Solo Strings (40-47)
        40: "violins_1",  # Violin
        41: "violas",  # Viola
        42: "celli",  # Cello
        43: "basses",  # Contrabass
        44: "violins_1",  # Tremolo Strings
        45: "violins_1",  # Pizzicato Strings
        46: "harp",  # Orchestral Harp
        47: "timpani",  # Timpani
        # String Ensembles (48-55)
        48: "violins_1",  # String Ensemble 1
        49: "violins_2",  # String Ensemble 2
        50: "violins_1",  # Synth Strings 1
        51: "violins_2",  # Synth Strings 2
        52: "violins_1",  # Choir Aahs -> Strings
        53: "violins_1",  # Voice Oohs -> Strings
        54: "violins_1",  # Synth Voice -> Strings
        55: "violins_1",  # Orchestra Hit -> Strings
        # Brass (56-63)
        56: "trumpets_a2",  # Trumpet
        57: "tenor_trombones_a3",  # Trombone
        58: "tuba",  # Tuba
        59: "horn",  # Muted Trumpet -> Horn
        60: "horns_a4",  # French Horn
        61: "bass_trombones_a2",  # Brass Section
        62: "trumpets_a2",  # Synth Brass 1
        63: "horns_a4",  # Synth Brass 2
        # Woodwinds (64-79)
        72: "piccolo",  # Piccolo
        73: "flute",  # Flute
        74: "flute",  # Recorder -> Flute
        75: "flute",  # Pan Flute -> Flute
        68: "oboe",  # Oboe
        69: "cor_anglais",  # English Horn
        70: "bassoon",  # Bassoon
        71: "clarinet",  # Clarinet
        # Pitched Percussion
        8: "celeste",  # Celesta
        9: "glockenspiel",  # Glockenspiel
        10: "glockenspiel",  # Music Box -> Glock
        11: "vibraphone",  # Vibraphone
        12: "marimba",  # Marimba
        13: "xylophone",  # Xylophone
        14: "tubular_bells",  # Tubular Bells
    }
    key = gm_map.get(program)
    return BBC_CATALOG.get(key) if key else None


def find_instrument_for_note(note: int, section: Section | None = None) -> BBCInstrument | None:
    """Find the best BBC instrument for a given MIDI note.

    Args:
        note: MIDI note number
        section: Optional section to restrict search

    Returns:
        Best matching instrument or None
    """
    candidates = []
    for inst in BBC_CATALOG.values():
        if section and inst.section != section:
            continue
        if inst.range_low <= note <= inst.range_high:
            # Prefer instruments where the note is in the comfortable middle range
            middle = (inst.range_low + inst.range_high) // 2
            distance = abs(note - middle)
            candidates.append((distance, inst))

    if candidates:
        candidates.sort(key=lambda x: x[0])
        return candidates[0][1]
    return None


def get_articulation_for_note_pattern(
    durations: list[float],
    velocities: list[int],
    instrument: BBCInstrument,
) -> str:
    """Determine best articulation based on note pattern.

    Args:
        durations: Note durations in beats
        velocities: Note velocities (0-127)
        instrument: Target instrument

    Returns:
        Articulation name
    """
    arts = instrument.articulations
    avg_duration = sum(durations) / len(durations) if durations else 1.0
    # Note: velocities parameter reserved for future dynamic articulation selection
    _ = velocities  # Suppress unused warning

    # Short notes
    if avg_duration < 0.25:
        if "Short Staccatissimo" in arts:
            return "Short Staccatissimo"
        if "Short Spiccato" in arts:
            return "Short Spiccato"
        if "Short Staccato" in arts:
            return "Short Staccato"

    # Medium notes
    if avg_duration < 1.0:
        if "Short Marcato" in arts:
            return "Short Marcato"
        if "Short Spiccato" in arts:
            return "Short Spiccato"

    # Long notes - check for legato potential
    if avg_duration >= 1.0:
        if "Legato" in arts:
            return "Legato"
        if "Long" in arts:
            return "Long"

    # Fallback to default
    return instrument.default_articulation


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "BBC_BRASS",
    # Catalog
    "BBC_CATALOG",
    "BBC_PERCUSSION_TUNED",
    "BBC_PERCUSSION_UNTUNED",
    "BBC_SECTIONS",
    # Section lists
    "BBC_STRINGS",
    "BBC_WOODWINDS",
    # MIDI CC constants
    "CC_DYNAMICS",
    "CC_EXPRESSION",
    "CC_LEGATO",
    "CC_RELEASE",
    "CC_TIGHTNESS",
    "CC_VIBRATO",
    "Articulation",
    # Classes
    "BBCInstrument",
    # Enums
    "Section",
    "find_instrument_by_gm_program",
    "find_instrument_for_note",
    "get_all_keys",
    "get_articulation_for_note_pattern",
    # Functions
    "get_instrument",
    "get_instruments_by_section",
]
