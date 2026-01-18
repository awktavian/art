"""BBC Symphony Orchestra Virtuoso Test Generator.

Creates expressive MIDI test pieces that showcase each instrument's capabilities,
inspired by the techniques used in famous orchestral passages.

Each test demonstrates:
- Full dynamic range (pp to ff via CC1/CC11)
- Multiple articulations via keyswitches
- Idiomatic register and phrasing
- Expressive techniques specific to each instrument
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pretty_midi

from kagami.core.effectors.bbc_instruments import BBC_CATALOG


@dataclass
class VirtuosoTest:
    """Definition of a virtuoso test piece."""

    instrument_key: str
    title: str
    inspiration: str  # Famous piece that inspired the technique
    tempo: float
    duration: float
    generator: Callable[["VirtuosoTest", pretty_midi.Instrument], None]


def add_crescendo(
    track: pretty_midi.Instrument,
    start: float,
    end: float,
    cc1_start: int,
    cc1_end: int,
    cc11_start: int = 100,
    cc11_end: int = 127,
):
    """Add smooth crescendo via CC1 (dynamics) and CC11 (expression)."""
    steps = int((end - start) * 20)  # 20 steps per second
    for i in range(steps + 1):
        t = start + (end - start) * i / steps
        cc1 = int(cc1_start + (cc1_end - cc1_start) * i / steps)
        cc11 = int(cc11_start + (cc11_end - cc11_start) * i / steps)
        track.control_changes.append(pretty_midi.ControlChange(1, cc1, t))
        track.control_changes.append(pretty_midi.ControlChange(11, cc11, t))


def add_diminuendo(
    track: pretty_midi.Instrument, start: float, end: float, cc1_start: int = 127, cc1_end: int = 40
):
    """Add smooth diminuendo."""
    add_crescendo(track, start, end, cc1_start, cc1_end, 127, 80)


def add_vibrato_swell(track: pretty_midi.Instrument, start: float, end: float):
    """Add expressive vibrato swell (common in romantic string/wind solos)."""
    # Start with less vibrato, swell to more
    steps = int((end - start) * 10)
    for i in range(steps + 1):
        t = start + (end - start) * i / steps
        # Vibrato depth via modulation (CC1 in BBC SO controls dynamics/vibrato blend)
        intensity = int(60 + 67 * (i / steps))  # 60 -> 127
        track.control_changes.append(pretty_midi.ControlChange(1, intensity, t))


# =============================================================================
# STRING VIRTUOSO TESTS
# =============================================================================


def gen_violins_1_scheherazade(test: VirtuosoTest, track: pretty_midi.Instrument):
    """Expressive solo passage in the style of Scheherazade's violin solos.

    Demonstrates: Legato, expressive dynamics, high register singing tone.
    """
    inst = BBC_CATALOG[test.instrument_key]

    # Keyswitch to Legato
    track.notes.append(pretty_midi.Note(100, inst.articulations.get("Legato", 12), 0.0, 0.1))

    # Opening: soft, mysterious - ascending phrase
    add_crescendo(track, 0.5, 4.0, 40, 100, 80, 120)

    # Lyrical melody in upper register (violin sweet spot: E5-A6)
    melody = [
        (76, 0.5, 1.5),  # E5 - opening note, sustained
        (79, 2.0, 0.8),  # G5
        (81, 2.8, 0.6),  # A5
        (83, 3.4, 1.2),  # B5 - peak, longer
        (81, 4.6, 0.5),  # A5 - descending
        (79, 5.1, 0.5),  # G5
        (76, 5.6, 1.8),  # E5 - return, with diminuendo
    ]

    for pitch, start, dur in melody:
        track.notes.append(pretty_midi.Note(90, pitch, start, start + dur))

    add_diminuendo(track, 5.5, 7.5)


def gen_violins_2_brahms(test: VirtuosoTest, track: pretty_midi.Instrument):
    """Warm accompaniment figure in Brahms style.

    Demonstrates: Sustained harmonies, gentle pulsing, middle register warmth.
    """
    inst = BBC_CATALOG[test.instrument_key]
    # Use Legato for sustained string playing
    track.notes.append(pretty_midi.Note(100, inst.articulations.get("Legato", 12), 0.0, 0.1))

    add_crescendo(track, 0.5, 3.0, 60, 90, 90, 110)

    # Warm sustained chords (violin 2 typically plays inner harmonies)
    # D4-A4 range, characteristic of second violin parts
    notes = [
        (62, 0.5, 2.5),  # D4
        (65, 0.5, 2.5),  # F4 (harmony)
        (69, 3.0, 2.5),  # A4
        (67, 3.0, 2.5),  # G4
        (64, 5.5, 2.0),  # E4
        (67, 5.5, 2.0),  # G4
    ]

    for pitch, start, dur in notes:
        track.notes.append(pretty_midi.Note(85, pitch, start, start + dur))


def gen_violas_don_quixote(test: VirtuosoTest, track: pretty_midi.Instrument):
    """Character passage in Don Quixote style (Sancho Panza theme).

    Demonstrates: Characteristic viola tone, humorous phrasing, middle register.
    """
    inst = BBC_CATALOG[test.instrument_key]
    track.notes.append(pretty_midi.Note(100, inst.articulations.get("Legato", 12), 0.0, 0.1))

    # Viola's characteristic warm, slightly nasal tone in C3-C5 range
    add_crescendo(track, 0.5, 2.0, 70, 100, 90, 115)

    melody = [
        (60, 0.5, 0.4),  # C4 - quick start
        (62, 0.9, 0.4),  # D4
        (64, 1.3, 0.8),  # E4 - slightly longer
        (67, 2.1, 0.3),  # G4 - quick
        (65, 2.4, 0.3),  # F4
        (64, 2.7, 1.0),  # E4 - sustained
        (60, 3.7, 0.5),  # C4
        (62, 4.2, 1.5),  # D4 - ending
    ]

    for pitch, start, dur in melody:
        track.notes.append(pretty_midi.Note(88, pitch, start, start + dur))

    add_diminuendo(track, 4.0, 6.0)


def gen_celli_dvorak(test: VirtuosoTest, track: pretty_midi.Instrument):
    """Romantic singing passage in Dvorak concerto style.

    Demonstrates: Rich cello tone, emotional expression, tenor register.
    """
    inst = BBC_CATALOG[test.instrument_key]
    track.notes.append(pretty_midi.Note(100, inst.articulations.get("Legato", 12), 0.0, 0.1))

    # Start soft, build emotionally
    add_crescendo(track, 0.5, 4.0, 50, 120, 85, 127)

    # Cello's singing register (A2-D4)
    melody = [
        (57, 0.5, 1.5),  # A3 - opening, sustained
        (60, 2.0, 0.8),  # C4
        (62, 2.8, 0.6),  # D4 - reaching up
        (64, 3.4, 1.5),  # E4 - emotional peak
        (62, 4.9, 0.6),  # D4
        (60, 5.5, 0.8),  # C4
        (57, 6.3, 2.0),  # A3 - return home
    ]

    for pitch, start, dur in melody:
        track.notes.append(pretty_midi.Note(95, pitch, start, start + dur))

    add_vibrato_swell(track, 3.0, 5.0)
    add_diminuendo(track, 6.0, 8.0)


def gen_basses_beethoven(test: VirtuosoTest, track: pretty_midi.Instrument):
    """Recitative passage in Beethoven 9 style.

    Demonstrates: Speaking quality, dramatic pauses, low register power.
    """
    inst = BBC_CATALOG[test.instrument_key]
    track.notes.append(pretty_midi.Note(100, inst.articulations.get("Legato", 12), 0.0, 0.1))

    # Dramatic recitative style
    add_crescendo(track, 0.5, 1.5, 80, 110, 100, 120)

    # Bass recitative (E1-G3 range)
    phrases = [
        (40, 0.5, 0.8),  # E2 - dramatic opening
        (43, 1.5, 0.6),  # G2
        (45, 2.3, 1.0),  # A2 - question
        # pause
        (43, 4.0, 0.5),  # G2 - response
        (40, 4.7, 0.4),  # E2
        (38, 5.3, 1.5),  # D2 - descending
        (36, 7.0, 2.0),  # C2 - powerful low note
    ]

    for pitch, start, dur in phrases:
        track.notes.append(pretty_midi.Note(100, pitch, start, start + dur))


# =============================================================================
# WOODWIND VIRTUOSO TESTS
# =============================================================================


def gen_flute_debussy(test: VirtuosoTest, track: pretty_midi.Instrument):
    """Floating chromatic passage in Debussy style (Afternoon of a Faun).

    Demonstrates: Ethereal tone, chromatic wandering, breath-like phrasing.
    """
    inst = BBC_CATALOG[test.instrument_key]
    track.notes.append(pretty_midi.Note(100, inst.articulations.get("Legato", 12), 0.0, 0.1))

    # Soft, dreamy dynamics
    add_crescendo(track, 0.5, 3.0, 45, 75, 80, 100)

    # Flute's sweet spot (D4-D6), chromatic wandering
    melody = [
        (78, 0.5, 1.2),  # F#5 - opening
        (77, 1.7, 0.8),  # F5 - chromatic
        (76, 2.5, 0.6),  # E5
        (74, 3.1, 1.0),  # D5 - lingering
        (76, 4.1, 0.5),  # E5
        (78, 4.6, 0.8),  # F#5
        (81, 5.4, 1.5),  # A5 - floating up
        (79, 6.9, 1.5),  # G5 - settling
    ]

    for pitch, start, dur in melody:
        track.notes.append(pretty_midi.Note(75, pitch, start, start + dur))

    add_diminuendo(track, 6.5, 8.5, 75, 35)


def gen_oboe_brahms(test: VirtuosoTest, track: pretty_midi.Instrument):
    """Singing melody in Brahms Violin Concerto slow movement style.

    Demonstrates: Plaintive oboe tone, long phrases, expressive swells.
    """
    inst = BBC_CATALOG[test.instrument_key]
    track.notes.append(pretty_midi.Note(100, inst.articulations.get("Legato", 12), 0.0, 0.1))

    add_crescendo(track, 0.5, 4.0, 55, 95, 85, 115)

    # Oboe's expressive range (Bb3-G5)
    melody = [
        (67, 0.5, 2.0),  # G4 - long opening
        (69, 2.5, 1.0),  # A4
        (71, 3.5, 0.8),  # B4
        (74, 4.3, 1.5),  # D5 - soaring
        (72, 5.8, 0.8),  # C5
        (71, 6.6, 0.6),  # B4
        (69, 7.2, 0.6),  # A4
        (67, 7.8, 2.0),  # G4 - return
    ]

    for pitch, start, dur in melody:
        track.notes.append(pretty_midi.Note(88, pitch, start, start + dur))

    add_vibrato_swell(track, 3.5, 5.5)


def gen_clarinet_rachmaninoff(test: VirtuosoTest, track: pretty_midi.Instrument):
    """Romantic solo in Rachmaninoff Symphony 2 style.

    Demonstrates: Warm clarinet tone, long melodic lines, emotional expression.
    """
    inst = BBC_CATALOG[test.instrument_key]
    track.notes.append(pretty_midi.Note(100, inst.articulations.get("Legato", 12), 0.0, 0.1))

    # Very expressive, start soft and build
    add_crescendo(track, 0.5, 5.0, 40, 110, 80, 125)

    # Clarinet's beautiful chalumeau to clarion register
    melody = [
        (58, 0.5, 2.0),  # Bb3 - warm low register opening
        (62, 2.5, 1.0),  # D4
        (65, 3.5, 1.2),  # F4
        (70, 4.7, 2.0),  # Bb4 - soaring into clarion
        (72, 6.7, 1.0),  # C5
        (70, 7.7, 0.8),  # Bb4
        (67, 8.5, 1.0),  # G4
        (65, 9.5, 2.0),  # F4 - settling
    ]

    for pitch, start, dur in melody:
        track.notes.append(pretty_midi.Note(90, pitch, start, start + dur))

    add_diminuendo(track, 8.0, 11.5)


def gen_bassoon_stravinsky(test: VirtuosoTest, track: pretty_midi.Instrument):
    """High register solo in Rite of Spring opening style.

    Demonstrates: Haunting high register, folk-like melody, unusual color.
    """
    inst = BBC_CATALOG[test.instrument_key]
    track.notes.append(pretty_midi.Note(100, inst.articulations.get("Legato", 12), 0.0, 0.1))

    # Mysterious, somewhat static dynamics
    add_crescendo(track, 0.5, 2.0, 60, 80, 90, 105)

    # Bassoon's haunting high register (around C4-G4)
    melody = [
        (60, 0.5, 1.5),  # C4 - modal opening
        (62, 2.0, 0.6),  # D4
        (60, 2.6, 0.4),  # C4
        (58, 3.0, 0.8),  # Bb3
        (60, 3.8, 1.2),  # C4
        (64, 5.0, 0.5),  # E4
        (62, 5.5, 0.5),  # D4
        (60, 6.0, 2.0),  # C4 - return
    ]

    for pitch, start, dur in melody:
        track.notes.append(pretty_midi.Note(82, pitch, start, start + dur))


def gen_piccolo_stars_stripes(test: VirtuosoTest, track: pretty_midi.Instrument):
    """Brilliant high passage in march style.

    Demonstrates: Piercing brilliance, agility, high register clarity.
    """
    inst = BBC_CATALOG[test.instrument_key]
    track.notes.append(pretty_midi.Note(100, inst.articulations.get("Long", 13), 0.0, 0.1))

    # Bright and bold
    add_crescendo(track, 0.5, 1.5, 90, 120, 110, 127)

    # Piccolo's brilliant register (C6-C8)
    melody = [
        (84, 0.5, 0.25),  # C6
        (86, 0.75, 0.25),  # D6
        (88, 1.0, 0.25),  # E6
        (91, 1.25, 0.5),  # G6 - accent
        (88, 1.75, 0.25),  # E6
        (86, 2.0, 0.25),  # D6
        (84, 2.25, 0.5),  # C6
        (88, 2.75, 0.25),  # E6
        (91, 3.0, 0.75),  # G6 - held
        (93, 3.75, 1.0),  # A6 - peak
    ]

    for pitch, start, dur in melody:
        track.notes.append(pretty_midi.Note(100, pitch, start, start + dur))


def gen_cor_anglais_dvorak(test: VirtuosoTest, track: pretty_midi.Instrument):
    """Plaintive melody in New World Symphony Largo style.

    Demonstrates: Melancholic beauty, singing tone, emotional depth.
    """
    inst = BBC_CATALOG[test.instrument_key]
    track.notes.append(pretty_midi.Note(100, inst.articulations.get("Legato", 12), 0.0, 0.1))

    # Very expressive, mournful
    add_crescendo(track, 0.5, 4.0, 50, 90, 85, 115)

    # Cor anglais range (E3-A5), but sounds a 5th lower
    melody = [
        (64, 0.5, 2.5),  # E4 - long opening note
        (66, 3.0, 1.0),  # F#4
        (68, 4.0, 0.8),  # G#4
        (69, 4.8, 2.0),  # A4 - emotional peak
        (68, 6.8, 0.8),  # G#4
        (66, 7.6, 0.8),  # F#4
        (64, 8.4, 3.0),  # E4 - return, sustained
    ]

    for pitch, start, dur in melody:
        track.notes.append(pretty_midi.Note(85, pitch, start, start + dur))

    add_vibrato_swell(track, 4.0, 7.0)
    add_diminuendo(track, 8.0, 11.5)


def gen_contrabassoon_deep(test: VirtuosoTest, track: pretty_midi.Instrument):
    """Ominous low passage showcasing the contrabassoon's unique depth.

    Demonstrates: Subterranean tone, orchestral foundation, dark color.
    """
    inst = BBC_CATALOG[test.instrument_key]
    track.notes.append(pretty_midi.Note(100, inst.articulations.get("Long", 13), 0.0, 0.1))

    add_crescendo(track, 0.5, 3.0, 70, 100, 95, 120)

    # Contrabassoon's deep range (Bb0-Bb3)
    notes = [
        (34, 0.5, 2.0),  # Bb1 - rumbling low
        (36, 2.5, 1.5),  # C2
        (38, 4.0, 1.5),  # D2
        (41, 5.5, 2.0),  # F2
        (38, 7.5, 1.5),  # D2
        (34, 9.0, 2.5),  # Bb1 - return to depths
    ]

    for pitch, start, dur in notes:
        track.notes.append(pretty_midi.Note(95, pitch, start, start + dur))


# =============================================================================
# BRASS VIRTUOSO TESTS
# =============================================================================


def gen_horn_strauss(test: VirtuosoTest, track: pretty_midi.Instrument):
    """Heroic call in Till Eulenspiegel style.

    Demonstrates: Noble horn tone, leaping intervals, heroic character.
    """
    inst = BBC_CATALOG[test.instrument_key]
    track.notes.append(pretty_midi.Note(100, inst.articulations.get("Legato", 12), 0.0, 0.1))

    add_crescendo(track, 0.5, 2.0, 70, 110, 100, 125)

    # Horn's noble range (F3-F5)
    melody = [
        (53, 0.5, 0.8),  # F3 - opening
        (60, 1.3, 0.4),  # C4 - leap up
        (65, 1.7, 0.6),  # F4 - continuing up
        (67, 2.3, 0.4),  # G4
        (69, 2.7, 1.0),  # A4 - ringing high note
        (65, 3.7, 0.5),  # F4 - descending
        (60, 4.2, 0.5),  # C4
        (53, 4.7, 1.5),  # F3 - return
    ]

    for pitch, start, dur in melody:
        track.notes.append(pretty_midi.Note(95, pitch, start, start + dur))

    add_diminuendo(track, 4.5, 6.5)


def gen_trumpet_mahler(test: VirtuosoTest, track: pretty_midi.Instrument):
    """Dramatic fanfare in Mahler 5 opening style.

    Demonstrates: Brilliant attack, rhythmic precision, heroic power.
    """
    inst = BBC_CATALOG[test.instrument_key]
    track.notes.append(pretty_midi.Note(100, inst.articulations.get("Long", 13), 0.0, 0.1))

    # Bold, powerful
    add_crescendo(track, 0.5, 1.0, 100, 127, 115, 127)

    # Trumpet's brilliant range (G3-C6)
    fanfare = [
        (67, 0.5, 0.3),  # G4 - short
        (67, 0.9, 0.3),  # G4 - repeated
        (67, 1.3, 0.3),  # G4
        (72, 1.7, 0.8),  # C5 - longer
        (71, 2.6, 0.2),  # B4
        (72, 2.9, 0.2),  # C5
        (74, 3.2, 1.0),  # D5 - accent
        (72, 4.3, 0.8),  # C5
        (67, 5.2, 1.5),  # G4 - ending
    ]

    for pitch, start, dur in fanfare:
        track.notes.append(pretty_midi.Note(110, pitch, start, start + dur))


def gen_trombone_bolero(test: VirtuosoTest, track: pretty_midi.Instrument):
    """Singing melody in Ravel Bolero style.

    Demonstrates: Lyrical trombone, smooth legato, expressive slides.
    """
    inst = BBC_CATALOG[test.instrument_key]
    track.notes.append(pretty_midi.Note(100, inst.articulations.get("Legato", 12), 0.0, 0.1))

    add_crescendo(track, 0.5, 4.0, 60, 100, 90, 120)

    # Trombone's singing range (E2-Bb4)
    melody = [
        (55, 0.5, 1.5),  # G3 - opening
        (57, 2.0, 0.8),  # A3
        (59, 2.8, 0.6),  # B3
        (60, 3.4, 1.2),  # C4 - peak
        (59, 4.6, 0.5),  # B3
        (57, 5.1, 0.5),  # A3
        (55, 5.6, 2.0),  # G3 - return
    ]

    for pitch, start, dur in melody:
        track.notes.append(pretty_midi.Note(90, pitch, start, start + dur))


def gen_tuba_bydlo(test: VirtuosoTest, track: pretty_midi.Instrument):
    """Heavy, plodding theme in Pictures at Exhibition (Bydlo) style.

    Demonstrates: Weight, power, sustained low notes.
    """
    inst = BBC_CATALOG[test.instrument_key]
    track.notes.append(pretty_midi.Note(100, inst.articulations.get("Legato", 12), 0.0, 0.1))

    # Start soft, build to heavy
    add_crescendo(track, 0.5, 4.0, 50, 110, 90, 125)

    # Tuba's powerful range (D1-F4)
    melody = [
        (41, 0.5, 1.5),  # F2 - heavy opening
        (43, 2.0, 1.0),  # G2
        (45, 3.0, 0.8),  # A2
        (48, 3.8, 2.0),  # C3 - reaching up
        (45, 5.8, 0.8),  # A2 - descending
        (43, 6.6, 0.8),  # G2
        (41, 7.4, 2.5),  # F2 - return, very sustained
    ]

    for pitch, start, dur in melody:
        track.notes.append(pretty_midi.Note(100, pitch, start, start + dur))

    add_diminuendo(track, 7.0, 10.0)


# =============================================================================
# PERCUSSION VIRTUOSO TESTS
# =============================================================================


def gen_timpani_beethoven(test: VirtuosoTest, track: pretty_midi.Instrument):
    """Dramatic roll with crescendo in Beethoven style.

    Demonstrates: Power, dramatic rolls, orchestral foundation.
    """
    inst = BBC_CATALOG[test.instrument_key]
    # Use "Long Rolls" articulation (keyswitch 13)
    track.notes.append(pretty_midi.Note(100, inst.articulations.get("Long Rolls", 13), 0.0, 0.1))

    # Dramatic crescendo roll
    add_crescendo(track, 0.5, 4.0, 40, 127, 80, 127)

    # Timpani notes - range is 40-57 (E2-A3)
    # Typical tuning: D2=50, A2=45, F2=41 (all within range)
    notes = [
        (45, 0.5, 3.5),  # A2 - sustained roll
        (50, 4.0, 0.5),  # D3 - accent
        (45, 4.5, 0.3),  # A2 - quick
        (50, 5.0, 2.0),  # D3 - final
    ]

    for pitch, start, dur in notes:
        track.notes.append(pretty_midi.Note(100, pitch, start, start + dur))


def gen_harp_nutcracker(test: VirtuosoTest, track: pretty_midi.Instrument):
    """Cascading arpeggios in Waltz of the Flowers cadenza style.

    Demonstrates: Glissandos, arpeggios, ethereal quality.
    """
    inst = BBC_CATALOG[test.instrument_key]
    track.notes.append(pretty_midi.Note(100, inst.articulations.get("Long", 13), 0.0, 0.1))

    add_crescendo(track, 0.5, 2.0, 60, 100, 90, 120)

    # Harp arpeggio (C major across octaves)
    arpeggio = [48, 52, 55, 60, 64, 67, 72, 76, 79, 84]  # C3 to C6

    for i, pitch in enumerate(arpeggio):
        start = 0.5 + i * 0.15
        track.notes.append(pretty_midi.Note(85, pitch, start, start + 0.8))

    # Descending arpeggio
    for i, pitch in enumerate(reversed(arpeggio)):
        start = 2.5 + i * 0.15
        track.notes.append(pretty_midi.Note(80, pitch, start, start + 0.6))

    add_diminuendo(track, 3.5, 5.0)


def gen_celeste_sugar_plum(test: VirtuosoTest, track: pretty_midi.Instrument):
    """Delicate, magical melody in Dance of Sugar Plum Fairy style.

    Demonstrates: Bell-like tone, delicate touch, magical quality.
    """
    inst = BBC_CATALOG[test.instrument_key]
    track.notes.append(
        pretty_midi.Note(100, inst.articulations.get("Short Sustained", 12), 0.0, 0.1)
    )

    add_crescendo(track, 0.5, 2.0, 50, 80, 85, 105)

    # Celeste's crystalline register (C4-C7)
    melody = [
        (76, 0.5, 0.3),  # E5
        (79, 0.8, 0.3),  # G5
        (84, 1.1, 0.4),  # C6
        (83, 1.5, 0.3),  # B5
        (84, 1.8, 0.5),  # C6
        (88, 2.3, 0.3),  # E6
        (84, 2.6, 0.4),  # C6
        (79, 3.0, 0.6),  # G5
        (76, 3.6, 0.8),  # E5
    ]

    for pitch, start, dur in melody:
        track.notes.append(pretty_midi.Note(70, pitch, start, start + dur))


def gen_glockenspiel_magic_flute(test: VirtuosoTest, track: pretty_midi.Instrument):
    """Sparkling bell passage in Magic Flute style.

    Demonstrates: Bright, penetrating tone, magical character.
    """
    inst = BBC_CATALOG[test.instrument_key]
    track.notes.append(pretty_midi.Note(100, inst.articulations.get("Short Hits", 12), 0.0, 0.1))

    add_crescendo(track, 0.5, 1.5, 70, 100, 100, 120)

    # Glockenspiel's bright register (G5-C8)
    notes = [
        (79, 0.5, 0.2),  # G5
        (84, 0.7, 0.2),  # C6
        (88, 0.9, 0.2),  # E6
        (91, 1.1, 0.3),  # G6 - accent
        (88, 1.4, 0.2),  # E6
        (84, 1.6, 0.2),  # C6
        (91, 1.8, 0.4),  # G6
        (96, 2.2, 0.5),  # C7 - high ring
    ]

    for pitch, start, dur in notes:
        track.notes.append(pretty_midi.Note(90, pitch, start, start + dur))


def gen_xylophone_danse_macabre(test: VirtuosoTest, track: pretty_midi.Instrument):
    """Skeletal rattling in Saint-Saëns Danse Macabre style.

    Demonstrates: Dry, brittle sound, rhythmic precision.
    """
    inst = BBC_CATALOG[test.instrument_key]
    track.notes.append(pretty_midi.Note(100, inst.articulations.get("Short Hits", 12), 0.0, 0.1))

    add_crescendo(track, 0.5, 2.0, 80, 110, 100, 120)

    # Xylophone's characteristic dry sound
    pattern = [
        (72, 0.5, 0.15),  # C5
        (74, 0.65, 0.15),  # D5
        (76, 0.8, 0.15),  # E5
        (72, 0.95, 0.15),  # C5
        (79, 1.1, 0.2),  # G5
        (76, 1.3, 0.15),  # E5
        (72, 1.45, 0.15),  # C5
        (79, 1.6, 0.3),  # G5 - accent
        (84, 1.9, 0.25),  # C6
        (79, 2.15, 0.25),  # G5
        (72, 2.4, 0.4),  # C5
    ]

    for pitch, start, dur in pattern:
        track.notes.append(pretty_midi.Note(95, pitch, start, start + dur))


def gen_marimba_warm(test: VirtuosoTest, track: pretty_midi.Instrument):
    """Warm, resonant passage showcasing marimba's mellow tone.

    Demonstrates: Warm resonance, smooth rolls, rich low register.
    """
    inst = BBC_CATALOG[test.instrument_key]
    track.notes.append(pretty_midi.Note(100, inst.articulations.get("Short Hits", 12), 0.0, 0.1))

    add_crescendo(track, 0.5, 3.0, 60, 95, 90, 115)

    # Marimba's warm range (C2-C7)
    notes = [
        (48, 0.5, 0.8),  # C3 - warm low
        (52, 1.3, 0.5),  # E3
        (55, 1.8, 0.5),  # G3
        (60, 2.3, 0.8),  # C4 - middle
        (64, 3.1, 0.5),  # E4
        (67, 3.6, 0.5),  # G4
        (72, 4.1, 1.0),  # C5 - high singing tone
        (67, 5.1, 0.5),  # G4
        (60, 5.6, 1.0),  # C4
    ]

    for pitch, start, dur in notes:
        track.notes.append(pretty_midi.Note(85, pitch, start, start + dur))


def gen_vibraphone_cool(test: VirtuosoTest, track: pretty_midi.Instrument):
    """Jazz-influenced passage in West Side Story style.

    Demonstrates: Shimmering vibrato, sustained tones, modern color.
    """
    inst = BBC_CATALOG[test.instrument_key]
    track.notes.append(pretty_midi.Note(100, inst.articulations.get("Short Hits", 12), 0.0, 0.1))

    add_crescendo(track, 0.5, 2.0, 55, 85, 85, 110)

    # Vibraphone's shimmering range
    notes = [
        (60, 0.5, 1.0),  # C4
        (63, 0.5, 1.0),  # Eb4 - jazz minor
        (67, 0.5, 1.0),  # G4
        (72, 1.5, 0.8),  # C5
        (70, 2.3, 0.8),  # Bb4
        (67, 3.1, 0.8),  # G4
        (63, 3.9, 1.2),  # Eb4
        (60, 5.1, 1.5),  # C4
    ]

    for pitch, start, dur in notes:
        track.notes.append(pretty_midi.Note(75, pitch, start, start + dur))


def gen_crotales_shimmer(test: VirtuosoTest, track: pretty_midi.Instrument):
    """High, shimmering passage showcasing crotales' brilliance.

    Demonstrates: Extreme high register, bell-like sustain.
    """
    inst = BBC_CATALOG[test.instrument_key]
    track.notes.append(pretty_midi.Note(100, inst.articulations.get("Short Hits", 12), 0.0, 0.1))

    add_crescendo(track, 0.5, 1.5, 60, 90, 90, 115)

    # Crotales (very high pitched bells)
    notes = [
        (84, 0.5, 0.5),  # C6
        (88, 1.0, 0.5),  # E6
        (91, 1.5, 0.6),  # G6
        (96, 2.1, 0.8),  # C7 - high
        (91, 2.9, 0.4),  # G6
        (88, 3.3, 0.4),  # E6
        (84, 3.7, 1.0),  # C6
    ]

    for pitch, start, dur in notes:
        track.notes.append(pretty_midi.Note(80, pitch, start, start + dur))


def gen_tubular_bells_dramatic(test: VirtuosoTest, track: pretty_midi.Instrument):
    """Majestic bell passage with church-like resonance.

    Demonstrates: Deep resonance, dramatic impact, ceremonial quality.
    """
    inst = BBC_CATALOG[test.instrument_key]
    track.notes.append(pretty_midi.Note(100, inst.articulations.get("Short Hits", 12), 0.0, 0.1))

    add_crescendo(track, 0.5, 2.0, 70, 110, 100, 125)

    # Tubular bells range (C4-G5)
    bells = [
        (60, 0.5, 2.0),  # C4 - first toll
        (67, 2.5, 2.0),  # G4 - second toll
        (64, 4.5, 2.0),  # E4 - third
        (60, 6.5, 3.0),  # C4 - final, resonant
    ]

    for pitch, start, dur in bells:
        track.notes.append(pretty_midi.Note(100, pitch, start, start + dur))


def gen_untuned_percussion_rhythm(test: VirtuosoTest, track: pretty_midi.Instrument):
    """Rhythmic passage showcasing various untuned percussion.

    Demonstrates: Rhythmic variety, different timbres, orchestral color.
    """
    inst = BBC_CATALOG[test.instrument_key]
    # Keyswitch to Anvil (first articulation)
    track.notes.append(pretty_midi.Note(100, inst.articulations.get("Anvil", 12), 0.0, 0.1))

    add_crescendo(track, 0.5, 2.0, 80, 110, 100, 120)

    # Various hits in rhythm
    hits = [
        (60, 0.5, 0.3),  # Hit
        (60, 1.0, 0.3),  # Hit
        (60, 1.3, 0.2),  # Short
        (60, 1.5, 0.2),  # Short
        (60, 1.8, 0.5),  # Accent
        (60, 2.5, 0.3),  # Hit
        (60, 3.0, 0.8),  # Long
    ]

    for pitch, start, dur in hits:
        track.notes.append(pretty_midi.Note(100, pitch, start, start + dur))


# =============================================================================
# ENSEMBLE TESTS (a2, a3, a4 sections)
# =============================================================================


def gen_ensemble_unison(test: VirtuosoTest, track: pretty_midi.Instrument):
    """Generic powerful unison passage for ensemble instruments.

    Demonstrates: Section power, blend, unified attack.
    """
    inst = BBC_CATALOG[test.instrument_key]
    track.notes.append(pretty_midi.Note(100, inst.articulations.get("Legato", 12), 0.0, 0.1))

    add_crescendo(track, 0.5, 3.0, 70, 115, 95, 125)

    mid = (inst.range_low + inst.range_high) // 2

    notes = [
        (mid, 0.5, 1.5),
        (mid + 2, 2.0, 1.0),
        (mid + 4, 3.0, 1.0),
        (mid + 5, 4.0, 2.0),
        (mid + 4, 6.0, 0.8),
        (mid + 2, 6.8, 0.8),
        (mid, 7.6, 2.0),
    ]

    for pitch, start, dur in notes:
        track.notes.append(pretty_midi.Note(100, pitch, start, start + dur))

    add_diminuendo(track, 7.0, 9.5)


# =============================================================================
# VIRTUOSO TEST CATALOG
# =============================================================================

VIRTUOSO_TESTS: dict[str, VirtuosoTest] = {
    # Strings
    "violins_1": VirtuosoTest(
        "violins_1",
        "Scheherazade Solo",
        "Rimsky-Korsakov: Scheherazade",
        72,
        8.0,
        gen_violins_1_scheherazade,
    ),
    "violins_2": VirtuosoTest(
        "violins_2", "Brahms Warmth", "Brahms: Symphony No. 1", 66, 8.0, gen_violins_2_brahms
    ),
    "violas": VirtuosoTest(
        "violas",
        "Don Quixote Character",
        "R. Strauss: Don Quixote",
        80,
        6.0,
        gen_violas_don_quixote,
    ),
    "celli": VirtuosoTest(
        "celli", "Dvorak Emotion", "Dvorak: Cello Concerto", 60, 9.0, gen_celli_dvorak
    ),
    "basses": VirtuosoTest(
        "basses", "Beethoven Recitative", "Beethoven: Symphony No. 9", 54, 9.0, gen_basses_beethoven
    ),
    # Woodwinds (solo)
    "flute": VirtuosoTest(
        "flute",
        "Afternoon Faun",
        "Debussy: Prélude à l'après-midi d'un faune",
        48,
        9.0,
        gen_flute_debussy,
    ),
    "oboe": VirtuosoTest(
        "oboe", "Brahms Adagio", "Brahms: Violin Concerto, II", 56, 10.0, gen_oboe_brahms
    ),
    "clarinet": VirtuosoTest(
        "clarinet",
        "Rachmaninoff Romance",
        "Rachmaninoff: Symphony No. 2, III",
        52,
        12.0,
        gen_clarinet_rachmaninoff,
    ),
    "bassoon": VirtuosoTest(
        "bassoon",
        "Rite of Spring",
        "Stravinsky: The Rite of Spring",
        60,
        8.0,
        gen_bassoon_stravinsky,
    ),
    "piccolo": VirtuosoTest(
        "piccolo",
        "Stars and Stripes",
        "Sousa: Stars and Stripes Forever",
        120,
        5.0,
        gen_piccolo_stars_stripes,
    ),
    "cor_anglais": VirtuosoTest(
        "cor_anglais",
        "New World Largo",
        "Dvorak: Symphony No. 9, II",
        46,
        12.0,
        gen_cor_anglais_dvorak,
    ),
    "bass_clarinet": VirtuosoTest(
        "bass_clarinet",
        "Dark Depths",
        "Original: Dark orchestral passage",
        60,
        8.0,
        gen_clarinet_rachmaninoff,  # Reuse clarinet style, transposed
    ),
    "contrabassoon": VirtuosoTest(
        "contrabassoon",
        "Subterranean",
        "Original: Deep foundation passage",
        54,
        12.0,
        gen_contrabassoon_deep,
    ),
    # Woodwinds (ensemble)
    "flutes_a3": VirtuosoTest(
        "flutes_a3",
        "Ensemble Shimmer",
        "Original: Flute section passage",
        60,
        10.0,
        gen_ensemble_unison,
    ),
    "oboes_a3": VirtuosoTest(
        "oboes_a3",
        "Pastoral Ensemble",
        "Original: Oboe section passage",
        66,
        10.0,
        gen_ensemble_unison,
    ),
    "clarinets_a3": VirtuosoTest(
        "clarinets_a3",
        "Warm Blend",
        "Original: Clarinet section passage",
        60,
        10.0,
        gen_ensemble_unison,
    ),
    "bassoons_a3": VirtuosoTest(
        "bassoons_a3",
        "Dark Choir",
        "Original: Bassoon section passage",
        56,
        10.0,
        gen_ensemble_unison,
    ),
    # Brass (solo)
    "horn": VirtuosoTest(
        "horn", "Till Eulenspiegel", "R. Strauss: Till Eulenspiegel", 88, 7.0, gen_horn_strauss
    ),
    "trumpet": VirtuosoTest(
        "trumpet", "Mahler Fanfare", "Mahler: Symphony No. 5", 72, 7.0, gen_trumpet_mahler
    ),
    "tenor_trombone": VirtuosoTest(
        "tenor_trombone", "Bolero Song", "Ravel: Boléro", 72, 8.0, gen_trombone_bolero
    ),
    "tuba": VirtuosoTest(
        "tuba", "Bydlo", "Mussorgsky/Ravel: Pictures at an Exhibition", 56, 10.0, gen_tuba_bydlo
    ),
    "cimbasso": VirtuosoTest(
        "cimbasso",
        "Dark Power",
        "Original: Low brass foundation",
        54,
        10.0,
        gen_tuba_bydlo,  # Similar style
    ),
    "contrabass_trombone": VirtuosoTest(
        "contrabass_trombone",
        "Deep Brass",
        "Original: Powerful low passage",
        54,
        10.0,
        gen_tuba_bydlo,  # Similar style
    ),
    "contrabass_tuba": VirtuosoTest(
        "contrabass_tuba",
        "Foundation",
        "Original: Orchestral foundation",
        54,
        10.0,
        gen_tuba_bydlo,  # Similar style
    ),
    # Brass (ensemble)
    "horns_a4": VirtuosoTest(
        "horns_a4",
        "Horn Section Power",
        "Original: Four-horn passage",
        72,
        10.0,
        gen_ensemble_unison,
    ),
    "trumpets_a2": VirtuosoTest(
        "trumpets_a2", "Fanfare Duo", "Original: Two-trumpet fanfare", 96, 8.0, gen_ensemble_unison
    ),
    "tenor_trombones_a3": VirtuosoTest(
        "tenor_trombones_a3",
        "Trombone Choir",
        "Original: Trombone section",
        66,
        10.0,
        gen_ensemble_unison,
    ),
    "bass_trombones_a2": VirtuosoTest(
        "bass_trombones_a2",
        "Bass Trombone Power",
        "Original: Low brass section",
        60,
        10.0,
        gen_ensemble_unison,
    ),
    # Percussion (tuned)
    "timpani": VirtuosoTest(
        "timpani", "Beethoven Drama", "Beethoven: Symphony No. 9", 72, 7.0, gen_timpani_beethoven
    ),
    "harp": VirtuosoTest(
        "harp", "Waltz of Flowers", "Tchaikovsky: Nutcracker", 84, 5.5, gen_harp_nutcracker
    ),
    "celeste": VirtuosoTest(
        "celeste", "Sugar Plum Fairy", "Tchaikovsky: Nutcracker", 76, 5.0, gen_celeste_sugar_plum
    ),
    "glockenspiel": VirtuosoTest(
        "glockenspiel",
        "Magic Bells",
        "Mozart: The Magic Flute",
        96,
        3.0,
        gen_glockenspiel_magic_flute,
    ),
    "xylophone": VirtuosoTest(
        "xylophone",
        "Danse Macabre",
        "Saint-Saëns: Danse Macabre",
        120,
        3.0,
        gen_xylophone_danse_macabre,
    ),
    "marimba": VirtuosoTest(
        "marimba", "Warm Resonance", "Original: Marimba showcase", 72, 7.0, gen_marimba_warm
    ),
    "vibraphone": VirtuosoTest(
        "vibraphone", "Cool Jazz", "Bernstein: West Side Story", 66, 7.0, gen_vibraphone_cool
    ),
    "crotales": VirtuosoTest(
        "crotales", "High Shimmer", "Original: Crotales showcase", 72, 5.0, gen_crotales_shimmer
    ),
    "tubular_bells": VirtuosoTest(
        "tubular_bells",
        "Cathedral Bells",
        "Original: Ceremonial bells",
        60,
        10.0,
        gen_tubular_bells_dramatic,
    ),
    # Percussion (untuned)
    "untuned_percussion": VirtuosoTest(
        "untuned_percussion",
        "Orchestral Color",
        "Original: Percussion showcase",
        90,
        4.0,
        gen_untuned_percussion_rhythm,
    ),
}


def generate_virtuoso_midi(instrument_key: str, output_dir: Path) -> Path:
    """Generate a virtuoso test MIDI file for the given instrument.

    Args:
        instrument_key: The instrument key from BBC_CATALOG
        output_dir: Directory to save the MIDI file

    Returns:
        Path to the generated MIDI file
    """
    if instrument_key not in VIRTUOSO_TESTS:
        raise ValueError(f"No virtuoso test defined for {instrument_key}")

    test = VIRTUOSO_TESTS[instrument_key]

    # GM program mapping for instrument detection during render
    # Ensures the correct RfxChain is selected
    GM_PROGRAMS = {
        # Strings
        "violins_1": 40,
        "violins_2": 40,
        "violas": 41,
        "celli": 42,
        "basses": 43,
        # Woodwinds
        "flute": 73,
        "oboe": 68,
        "clarinet": 71,
        "bassoon": 70,
        "piccolo": 72,
        "cor_anglais": 69,
        "bass_clarinet": 71,
        "contrabassoon": 70,
        "flutes_a3": 73,
        "oboes_a3": 68,
        "clarinets_a3": 71,
        "bassoons_a3": 70,
        # Brass
        "horn": 60,
        "trumpet": 56,
        "tenor_trombone": 57,
        "tuba": 58,
        "cimbasso": 58,
        "contrabass_trombone": 57,
        "contrabass_tuba": 58,
        "horns_a4": 60,
        "trumpets_a2": 56,
        "tenor_trombones_a3": 57,
        "bass_trombones_a2": 57,
        # Percussion
        "timpani": 47,
        "harp": 46,
        "celeste": 8,
        "glockenspiel": 9,
        "xylophone": 13,
        "marimba": 12,
        "vibraphone": 11,
        "crotales": 14,
        "tubular_bells": 14,
        "untuned_percussion": 0,
    }

    gm_program = GM_PROGRAMS.get(instrument_key, 0)

    midi = pretty_midi.PrettyMIDI(initial_tempo=test.tempo)
    track = pretty_midi.Instrument(program=gm_program, name=test.title)

    # Generate the passage
    test.generator(test, track)

    midi.instruments.append(track)

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{instrument_key}_virtuoso.mid"
    midi.write(str(output_path))

    return output_path


def generate_all_virtuoso_midi(output_dir: Path) -> dict[str, Path]:
    """Generate virtuoso test MIDI files for all instruments.

    Returns:
        Dict mapping instrument key to generated MIDI path
    """
    results = {}

    for inst_key in VIRTUOSO_TESTS:
        try:
            path = generate_virtuoso_midi(inst_key, output_dir)
            results[inst_key] = path
        except Exception as e:
            print(f"Error generating {inst_key}: {e}")

    return results
