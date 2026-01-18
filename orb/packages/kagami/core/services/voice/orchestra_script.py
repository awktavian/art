"""Orchestra Journey Script — A guided tour through the BBC Symphony.

This is a complete narrated experience, not a collection of one-liners.
Written as a journey with Tim as guide.

The script is segmented with ||| delimiters for timestamp-based splitting.
Each segment introduces one instrument or section, always naming it clearly.
"""

# The delimiter for splitting
DELIMITER = " ||| "

# =============================================================================
# The Script — A Journey Through the Orchestra
# =============================================================================

SEGMENTS = {
    # OPENING
    "intro": """
[whispers] Hey. [pause] I want to show you something. An orchestra.
[excited] Ready? Let's go.
""",
    # STRINGS
    "section_strings": "[pause] The strings.",
    "violins_1": "First violins. Scheherazade. [whispers] Listen to them sing.",
    "violins_2": "Second violins. Brahms. The harmony underneath.",
    "violas": "[playfully] Violas. The loyal sidekick.",
    "celli": "[sighs] Cellos. Dvořák, homesick and in love.",
    "basses": "Double basses. Beethoven made them speak.",
    # WOODWINDS
    "section_woodwinds": "[pause] Woodwinds.",
    "flute": "[whispers] Flute. Debussy's faun, half-dreaming.",
    "oboe": "Oboe. Everyone tunes to it. [curious] It can't adjust.",
    "clarinet": "Clarinet. Rachmaninoff. [whispers] Therapy worked.",
    "bassoon": "[curious] Bassoon. This note started a riot.",
    "piccolo": "[laughs] Piccolo. Smallest. Somehow loudest.",
    "cor_anglais": "[whispers] Cor anglais. The saddest sound. Dvořák, missing home.",
    "bass_clarinet": "Bass clarinet. [whispers] Villain music.",
    "contrabassoon": "Contrabassoon. So low you feel it.",
    "flutes_a3": "Three flutes. [whispers] Sunlight on water.",
    "oboes_a3": "Oboe section. [playfully] Pastoral.",
    "clarinets_a3": "Clarinets together. Comfort food.",
    "bassoons_a3": "Bassoon section. [whispers] Storm clouds.",
    # BRASS
    "section_brass": "[excited] The brass. Goosebumps territory.",
    "horn": "[excited] French horn! When they nail it — nothing else sounds like this.",
    "trumpet": "Trumpet. Mahler. Fate knocking.",
    "tenor_trombone": "[curious] Trombone being romantic. Ravel knew.",
    "tuba": "[playfully] Tuba. The ox-cart. Unstoppable.",
    "cimbasso": "[whispers] Cimbasso. Impending doom.",
    "contrabass_trombone": "Contrabass trombone. The floor vibrates.",
    "contrabass_tuba": "[laughs] Contrabass tuba. Even bigger.",
    "horns_a4": "[excited] Four horns. Sunrise.",
    "trumpets_a2": "Two trumpets. Royal decree.",
    "tenor_trombones_a3": "Trombone section. Avalanche.",
    "bass_trombones_a2": "Bass trombones. You feel it in your chest.",
    # PERCUSSION
    "section_percussion": "[pause] Percussion. Beautiful chaos.",
    "timpani": "[excited] Timpani! Beethoven's heartbeat.",
    "harp": "[whispers] Harp. Starlight made audible.",
    "celeste": "[curious] Celeste. Tchaikovsky's secret.",
    "glockenspiel": "[excited] Glockenspiel! Mozart's magic bells.",
    "xylophone": "[playfully] Xylophone. Skeletons dancing.",
    "marimba": "Marimba. Four mallets. Sometimes six.",
    "vibraphone": "[curious] Vibraphone. The jazziest.",
    "crotales": "[whispers] Crotales. Otherworldly.",
    "tubular_bells": "Tubular bells. Church bells.",
    "untuned_percussion": "[playfully] The fun stuff. [whispers] Chaos.",
    # FINALE
    "finale": """
[long pause] [sighs]
Thirty-eight voices. The BBC Symphony Orchestra.
""",
}


def get_full_script() -> str:
    """Get the complete script as a single string with delimiters."""
    # Order matters
    order = [
        "intro",
        "section_strings",
        "violins_1",
        "violins_2",
        "violas",
        "celli",
        "basses",
        "section_woodwinds",
        "flute",
        "oboe",
        "clarinet",
        "bassoon",
        "piccolo",
        "cor_anglais",
        "bass_clarinet",
        "contrabassoon",
        "flutes_a3",
        "oboes_a3",
        "clarinets_a3",
        "bassoons_a3",
        "section_brass",
        "horn",
        "trumpet",
        "tenor_trombone",
        "tuba",
        "cimbasso",
        "contrabass_trombone",
        "contrabass_tuba",
        "horns_a4",
        "trumpets_a2",
        "tenor_trombones_a3",
        "bass_trombones_a2",
        "section_percussion",
        "timpani",
        "harp",
        "celeste",
        "glockenspiel",
        "xylophone",
        "marimba",
        "vibraphone",
        "crotales",
        "tubular_bells",
        "untuned_percussion",
        "finale",
    ]

    parts = []
    for key in order:
        text = SEGMENTS.get(key, "")
        # Clean up whitespace
        text = " ".join(text.split())
        parts.append(text)

    return DELIMITER.join(parts)


def get_segment_keys() -> list[str]:
    """Get the ordered list of segment keys."""
    return [
        "intro",
        "section_strings",
        "violins_1",
        "violins_2",
        "violas",
        "celli",
        "basses",
        "section_woodwinds",
        "flute",
        "oboe",
        "clarinet",
        "bassoon",
        "piccolo",
        "cor_anglais",
        "bass_clarinet",
        "contrabassoon",
        "flutes_a3",
        "oboes_a3",
        "clarinets_a3",
        "bassoons_a3",
        "section_brass",
        "horn",
        "trumpet",
        "tenor_trombone",
        "tuba",
        "cimbasso",
        "contrabass_trombone",
        "contrabass_tuba",
        "horns_a4",
        "trumpets_a2",
        "tenor_trombones_a3",
        "bass_trombones_a2",
        "section_percussion",
        "timpani",
        "harp",
        "celeste",
        "glockenspiel",
        "xylophone",
        "marimba",
        "vibraphone",
        "crotales",
        "tubular_bells",
        "untuned_percussion",
        "finale",
    ]


def get_segment(key: str) -> str:
    """Get a single segment by key."""
    return " ".join(SEGMENTS.get(key, "").split())


__all__ = [
    "DELIMITER",
    "SEGMENTS",
    "get_full_script",
    "get_segment",
    "get_segment_keys",
]
