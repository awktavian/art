"""MIDI Catalogue — Curated Orchestral Masterpieces.

A carefully curated collection of PUBLIC DOMAIN orchestral works,
selected for their dramatic impact and showcase potential.

All composers died 70+ years ago (public domain worldwide).

Selection Criteria:
    1. Dramatic impact — moments that showcase full orchestra
    2. BBC Symphony Orchestra suitability — works well with samples
    3. Expression potential — benefits from CC1/CC11 dynamics
    4. Spatial interest — uses full orchestra sections for VBAP

Sources:
    - Kunst der Fuge (kunstderfuge.com) — highest quality
    - BitMidi (bitmidi.com) — good variety
    - Classical Archives — verified transcriptions
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class Composer(str, Enum):
    """Composers in catalogue (all public domain)."""

    WAGNER = "wagner"  # Died 1883 — Ring Cycle, Tristan
    BEETHOVEN = "beethoven"  # Died 1827 — Symphonies
    TCHAIKOVSKY = "tchaikovsky"  # Died 1893 — Ballets, Symphonies
    MAHLER = "mahler"  # Died 1911 — Massive symphonies
    DVORAK = "dvorak"  # Died 1904 — New World Symphony
    HOLST = "holst"  # Died 1934 — The Planets
    MUSSORGSKY = "mussorgsky"  # Died 1881 — Pictures, Night on Bald Mountain
    RIMSKY_KORSAKOV = "rimsky_korsakov"  # Died 1908 — Scheherazade
    STRAUSS_R = "strauss_r"  # Died 1949 — Also Sprach, Don Juan
    GRIEG = "grieg"  # Died 1907 — Peer Gynt, Piano Concerto
    VERDI = "verdi"  # Died 1901 — Requiem, Operas
    ORFF = "orff"  # Died 1982 — Carmina Burana (check local copyright)


class Era(str, Enum):
    """Musical era."""

    CLASSICAL = "classical"  # 1750-1820
    ROMANTIC = "romantic"  # 1820-1900
    LATE_ROMANTIC = "late_romantic"  # 1880-1920
    MODERN = "modern"  # 1900-1950


class Intensity(str, Enum):
    """Dramatic intensity level."""

    EPIC = "epic"  # Full orchestra, maximum drama
    DRAMATIC = "dramatic"  # Strong climaxes
    LYRICAL = "lyrical"  # Beautiful melodies
    MYSTICAL = "mystical"  # Atmospheric, ethereal


@dataclass
class HighlightMoment:
    """A specific impressive moment within a piece."""

    name: str  # "The Storm" or "Siegfried's Funeral March"
    start_bar: int  # Starting measure
    end_bar: int  # Ending measure
    start_time_approx: float  # Approximate start in seconds (at standard tempo)
    duration_approx: float  # Approximate duration in seconds
    description: str  # What makes this moment impressive
    intensity: Intensity = Intensity.EPIC
    showcase_features: list[str] = field(
        default_factory=list
    )  # ["brass fanfare", "string tremolo"]


@dataclass
class CataloguePiece:
    """A curated orchestral piece with metadata."""

    id: str  # Unique identifier
    title: str  # Full title
    composer: Composer
    era: Era
    year: int  # Year composed
    duration_min: float  # Total duration in minutes

    # Why this piece is impressive
    description: str
    showcase_reason: str  # Why it demos the orchestra system well

    # Technical details
    key: str  # Musical key
    tempo_range: tuple[int, int]  # BPM range (min, max)

    # Instrumentation requirements
    requires_strings: bool = True
    requires_brass: bool = True
    requires_woodwinds: bool = True
    requires_percussion: bool = True
    requires_choir: bool = False

    # Source
    midi_url: str | None = None  # Download URL
    midi_source: str = "kunst_der_fuge"  # Source name
    local_path: Path | None = None  # Local cached path

    # Highlight moments for rendering
    highlights: list[HighlightMoment] = field(default_factory=list)

    # Metadata
    intensity: Intensity = Intensity.EPIC
    film_score_influence: str = ""  # Which film scores this influenced
    tags: list[str] = field(default_factory=list)


# =============================================================================
# THE CATALOGUE — TOUR DE FORCE SELECTION
# =============================================================================

CATALOGUE: dict[str, CataloguePiece] = {
    # =========================================================================
    # WAGNER — The Father of Film Music
    # =========================================================================
    "wagner_ride_of_valkyries": CataloguePiece(
        id="wagner_ride_of_valkyries",
        title="Ride of the Valkyries (Walkürenritt)",
        composer=Composer.WAGNER,
        era=Era.ROMANTIC,
        year=1870,
        duration_min=5.5,
        description="The most iconic orchestral passage ever written. Brass fanfares, "
        "galloping strings, and soaring woodwinds depict warrior maidens riding to battle.",
        showcase_reason="Perfect BBC demo: brass power, string agility, full orchestra climax",
        key="B minor",
        tempo_range=(132, 144),
        requires_choir=False,
        midi_url="https://bitmidi.com/uploads/100212.mid",
        midi_source="bitmidi",
        intensity=Intensity.EPIC,
        film_score_influence="Apocalypse Now, countless action films",
        tags=["iconic", "brass", "galloping", "battle"],
        highlights=[
            HighlightMoment(
                name="Opening Horn Call",
                start_bar=1,
                end_bar=16,
                start_time_approx=0,
                duration_approx=30,
                description="The legendary brass fanfare that opens the piece",
                intensity=Intensity.EPIC,
                showcase_features=["horn section", "brass power", "iconic melody"],
            ),
            HighlightMoment(
                name="Full Orchestra Entry",
                start_bar=17,
                end_bar=48,
                start_time_approx=30,
                duration_approx=60,
                description="Strings join with galloping rhythm, full orchestra builds",
                intensity=Intensity.EPIC,
                showcase_features=["string tremolo", "brass fanfare", "timpani rolls"],
            ),
            HighlightMoment(
                name="The Gallop Climax",
                start_bar=80,
                end_bar=120,
                start_time_approx=150,
                duration_approx=80,
                description="Maximum intensity — all sections at full power",
                intensity=Intensity.EPIC,
                showcase_features=["full orchestra", "dynamic swells", "brass climax"],
            ),
        ],
    ),
    "wagner_tristan_prelude": CataloguePiece(
        id="wagner_tristan_prelude",
        title="Prelude to Tristan und Isolde",
        composer=Composer.WAGNER,
        era=Era.ROMANTIC,
        year=1859,
        duration_min=11,
        description="The most influential piece in Western music history. The 'Tristan chord' "
        "broke all harmonic rules and birthed modern music.",
        showcase_reason="Showcases expression engine: endless crescendos, CC1/CC11 dynamics",
        key="A minor",
        tempo_range=(50, 72),
        midi_source="kunst_der_fuge",
        intensity=Intensity.MYSTICAL,
        film_score_influence="Every romantic film score ever",
        tags=["yearning", "chromatic", "expressive", "revolutionary"],
        highlights=[
            HighlightMoment(
                name="The Tristan Chord",
                start_bar=1,
                end_bar=8,
                start_time_approx=0,
                duration_approx=45,
                description="The most famous chord in music history",
                intensity=Intensity.MYSTICAL,
                showcase_features=["chromatic harmony", "cello melody", "yearning"],
            ),
            HighlightMoment(
                name="The Great Crescendo",
                start_bar=60,
                end_bar=84,
                start_time_approx=300,
                duration_approx=120,
                description="Orchestra builds to shattering climax",
                intensity=Intensity.EPIC,
                showcase_features=["massive crescendo", "brass climax", "string passion"],
            ),
        ],
    ),
    "wagner_siegfrieds_funeral": CataloguePiece(
        id="wagner_siegfrieds_funeral",
        title="Siegfried's Funeral March (Götterdämmerung)",
        composer=Composer.WAGNER,
        era=Era.ROMANTIC,
        year=1876,
        duration_min=8,
        description="The death of the hero. Massive brass, thundering timpani, "
        "and the most profound grief in orchestral music.",
        showcase_reason="Maximum brass power, percussion impact, spatial drama",
        key="C minor",
        tempo_range=(40, 56),
        midi_source="kunst_der_fuge",
        intensity=Intensity.EPIC,
        film_score_influence="Every heroic death scene in film",
        tags=["funeral", "brass", "heroic", "grief", "timpani"],
        highlights=[
            HighlightMoment(
                name="Death Announcement",
                start_bar=1,
                end_bar=20,
                start_time_approx=0,
                duration_approx=90,
                description="Timpani and brass announce the hero's death",
                intensity=Intensity.DRAMATIC,
                showcase_features=["timpani rolls", "brass chorale", "grief"],
            ),
            HighlightMoment(
                name="Hero's Theme Transformed",
                start_bar=40,
                end_bar=80,
                start_time_approx=180,
                duration_approx=150,
                description="Siegfried's heroic themes return in funeral transformation",
                intensity=Intensity.EPIC,
                showcase_features=["leitmotif", "brass power", "full orchestra"],
            ),
        ],
    ),
    # =========================================================================
    # HOLST — The Planets (Direct Williams Influence)
    # =========================================================================
    "holst_mars": CataloguePiece(
        id="holst_mars",
        title="Mars, the Bringer of War (The Planets)",
        composer=Composer.HOLST,
        era=Era.MODERN,
        year=1916,
        duration_min=7.5,
        description="The blueprint for every sci-fi battle score. Relentless 5/4 rhythm, "
        "crushing brass, and pure aggression.",
        showcase_reason="John Williams studied this for Star Wars. THE template for film brass.",
        key="C major (modal)",
        tempo_range=(168, 184),
        midi_source="kunst_der_fuge",
        intensity=Intensity.EPIC,
        film_score_influence="Star Wars Imperial March, every sci-fi battle",
        tags=["war", "relentless", "brass", "5/4 time", "sci-fi"],
        highlights=[
            HighlightMoment(
                name="The Relentless March",
                start_bar=1,
                end_bar=32,
                start_time_approx=0,
                duration_approx=45,
                description="The iconic 5/4 ostinato that never stops",
                intensity=Intensity.EPIC,
                showcase_features=["5/4 rhythm", "col legno strings", "tension build"],
            ),
            HighlightMoment(
                name="Brass Assault",
                start_bar=80,
                end_bar=120,
                start_time_approx=120,
                duration_approx=60,
                description="Full brass section at maximum aggression",
                intensity=Intensity.EPIC,
                showcase_features=["brass ff", "percussion battery", "orchestral violence"],
            ),
            HighlightMoment(
                name="Final Devastation",
                start_bar=160,
                end_bar=200,
                start_time_approx=280,
                duration_approx=90,
                description="The final apocalyptic climax",
                intensity=Intensity.EPIC,
                showcase_features=["organ", "full orchestra", "crushing finale"],
            ),
        ],
    ),
    "holst_jupiter": CataloguePiece(
        id="holst_jupiter",
        title="Jupiter, the Bringer of Jollity (The Planets)",
        composer=Composer.HOLST,
        era=Era.MODERN,
        year=1916,
        duration_min=8,
        description="Joy, majesty, and one of the most beautiful melodies ever written. "
        "The central hymn became 'I Vow to Thee My Country'.",
        showcase_reason="Shows orchestral range: from playful to majestic to transcendent",
        key="C major",
        tempo_range=(84, 144),
        midi_source="kunst_der_fuge",
        intensity=Intensity.EPIC,
        film_score_influence="Every triumphant film moment",
        tags=["joy", "majesty", "hymn", "celebration"],
        highlights=[
            HighlightMoment(
                name="The Great Hymn",
                start_bar=108,
                end_bar=140,
                start_time_approx=180,
                duration_approx=90,
                description="The famous hymn tune — pure orchestral nobility",
                intensity=Intensity.LYRICAL,
                showcase_features=["string melody", "brass harmony", "transcendence"],
            ),
            HighlightMoment(
                name="Triumphant Finale",
                start_bar=180,
                end_bar=220,
                start_time_approx=360,
                duration_approx=90,
                description="Full orchestra celebration",
                intensity=Intensity.EPIC,
                showcase_features=["brass fanfare", "timpani", "joyful climax"],
            ),
        ],
    ),
    # =========================================================================
    # TCHAIKOVSKY — Master of Orchestral Drama
    # =========================================================================
    "tchaikovsky_1812": CataloguePiece(
        id="tchaikovsky_1812",
        title="1812 Overture (Finale)",
        composer=Composer.TCHAIKOVSKY,
        era=Era.ROMANTIC,
        year=1880,
        duration_min=15,
        description="Cannons. Church bells. Maximum orchestral firepower. "
        "The most bombastic finale in classical music.",
        showcase_reason="BBC brass at full power, percussion battery, bells",
        key="E♭ major",
        tempo_range=(104, 152),
        midi_source="kunst_der_fuge",
        intensity=Intensity.EPIC,
        film_score_influence="Every patriotic/triumphant film moment",
        tags=["cannons", "bells", "victory", "patriotic", "bombastic"],
        highlights=[
            HighlightMoment(
                name="The Battle Builds",
                start_bar=280,
                end_bar=320,
                start_time_approx=600,
                duration_approx=90,
                description="Tension builds toward the famous finale",
                intensity=Intensity.DRAMATIC,
                showcase_features=["string agitation", "brass fanfares", "building tension"],
            ),
            HighlightMoment(
                name="Victory and Cannons",
                start_bar=380,
                end_bar=420,
                start_time_approx=780,
                duration_approx=120,
                description="The explosive finale with bells and 'cannons'",
                intensity=Intensity.EPIC,
                showcase_features=["brass fff", "bells", "timpani thunder", "orchestral max"],
            ),
        ],
    ),
    "tchaikovsky_romeo_juliet": CataloguePiece(
        id="tchaikovsky_romeo_juliet",
        title="Romeo and Juliet Fantasy Overture",
        composer=Composer.TCHAIKOVSKY,
        era=Era.ROMANTIC,
        year=1880,
        duration_min=20,
        description="The greatest love theme ever written, surrounded by violent conflict. "
        "Perfect dramatic arc.",
        showcase_reason="Demonstrates full expression engine: PP to FFF dynamics",
        key="B minor",
        tempo_range=(48, 144),
        midi_source="kunst_der_fuge",
        intensity=Intensity.DRAMATIC,
        film_score_influence="Every romantic film score",
        tags=["love", "conflict", "passion", "drama"],
        highlights=[
            HighlightMoment(
                name="The Love Theme",
                start_bar=184,
                end_bar=220,
                start_time_approx=360,
                duration_approx=120,
                description="The most famous love theme in classical music",
                intensity=Intensity.LYRICAL,
                showcase_features=["string melody", "english horn", "romantic expression"],
            ),
            HighlightMoment(
                name="Battle Climax",
                start_bar=340,
                end_bar=400,
                start_time_approx=720,
                duration_approx=120,
                description="Violent conflict between families — full orchestra fury",
                intensity=Intensity.EPIC,
                showcase_features=["brass fanfares", "string fury", "percussion battle"],
            ),
        ],
    ),
    # =========================================================================
    # BEETHOVEN — The Revolutionary
    # =========================================================================
    "beethoven_symphony5_finale": CataloguePiece(
        id="beethoven_symphony5_finale",
        title="Symphony No. 5 - Fourth Movement",
        composer=Composer.BEETHOVEN,
        era=Era.CLASSICAL,
        year=1808,
        duration_min=11,
        description="From darkness to light. The most triumphant finale in music history. "
        "C minor becomes C major in glorious victory.",
        showcase_reason="Perfect expression arc: struggle → triumph",
        key="C major",
        tempo_range=(84, 120),
        midi_source="kunst_der_fuge",
        intensity=Intensity.EPIC,
        film_score_influence="Every underdog victory moment",
        tags=["triumph", "victory", "darkness to light", "iconic"],
        highlights=[
            HighlightMoment(
                name="The Triumphant Entry",
                start_bar=1,
                end_bar=40,
                start_time_approx=0,
                duration_approx=60,
                description="The explosive C major entry after C minor struggle",
                intensity=Intensity.EPIC,
                showcase_features=["brass fanfare", "timpani", "triumphant theme"],
            ),
            HighlightMoment(
                name="Presto Victory",
                start_bar=320,
                end_bar=400,
                start_time_approx=500,
                duration_approx=120,
                description="The accelerating finale to ultimate triumph",
                intensity=Intensity.EPIC,
                showcase_features=["presto tempo", "full orchestra", "C major glory"],
            ),
        ],
    ),
    "beethoven_symphony9_ode": CataloguePiece(
        id="beethoven_symphony9_ode",
        title="Symphony No. 9 - Ode to Joy (Orchestral)",
        composer=Composer.BEETHOVEN,
        era=Era.CLASSICAL,
        year=1824,
        duration_min=24,
        description="Universal brotherhood. The most important melody in Western civilization. "
        "Now the EU anthem.",
        showcase_reason="Shows orchestral build: simple theme → massive orchestration",
        key="D major",
        tempo_range=(60, 132),
        requires_choir=True,  # Original has choir, but orchestral version works
        midi_source="kunst_der_fuge",
        intensity=Intensity.EPIC,
        film_score_influence="Every scene of human unity and triumph",
        tags=["joy", "brotherhood", "iconic", "humanity", "anthem"],
        highlights=[
            HighlightMoment(
                name="Theme Introduction (Cellos)",
                start_bar=92,
                end_bar=116,
                start_time_approx=120,
                duration_approx=60,
                description="The Ode melody introduced softly by cellos",
                intensity=Intensity.LYRICAL,
                showcase_features=["cello melody", "simple beauty", "building"],
            ),
            HighlightMoment(
                name="Full Orchestra Joy",
                start_bar=164,
                end_bar=200,
                start_time_approx=300,
                duration_approx=90,
                description="The theme in full orchestral glory",
                intensity=Intensity.EPIC,
                showcase_features=["full orchestra", "brass fanfares", "triumphant"],
            ),
        ],
    ),
    # =========================================================================
    # MAHLER — The Maximalist
    # =========================================================================
    "mahler_symphony2_resurrection": CataloguePiece(
        id="mahler_symphony2_resurrection",
        title="Symphony No. 2 'Resurrection' - Finale",
        composer=Composer.MAHLER,
        era=Era.LATE_ROMANTIC,
        year=1894,
        duration_min=35,
        description="Death and resurrection. The largest orchestral forces imaginable. "
        "Offstage brass, organ, massive choir.",
        showcase_reason="Maximum BBC orchestra: 8 horns, 10 trumpets, percussion battery",
        key="C minor → E♭ major",
        tempo_range=(40, 120),
        requires_choir=True,
        midi_source="mahler_archives",
        intensity=Intensity.EPIC,
        film_score_influence="Every cosmic/spiritual film climax",
        tags=["resurrection", "cosmic", "massive", "spiritual", "organ"],
        highlights=[
            HighlightMoment(
                name="The Great Call",
                start_bar=472,
                end_bar=520,
                start_time_approx=1500,
                duration_approx=180,
                description="Offstage brass herald the resurrection",
                intensity=Intensity.MYSTICAL,
                showcase_features=["offstage brass", "spatial audio", "ethereal"],
            ),
            HighlightMoment(
                name="Resurrection Climax",
                start_bar=620,
                end_bar=680,
                start_time_approx=1800,
                duration_approx=240,
                description="Full forces: orchestra, choir, organ — transcendence",
                intensity=Intensity.EPIC,
                showcase_features=["organ", "full orchestra", "choir", "E♭ major glory"],
            ),
        ],
    ),
    "mahler_symphony1_funeral": CataloguePiece(
        id="mahler_symphony1_funeral",
        title="Symphony No. 1 'Titan' - Third Movement (Funeral March)",
        composer=Composer.MAHLER,
        era=Era.LATE_ROMANTIC,
        year=1888,
        duration_min=11,
        description="A hunter's funeral procession. Dark parody turning to heartbreak. "
        "The most eerily beautiful orchestral movement.",
        showcase_reason="Unique orchestration: solo bass, muted brass, klezmer influence",
        key="D minor",
        tempo_range=(54, 72),
        midi_source="mahler_archives",
        intensity=Intensity.MYSTICAL,
        film_score_influence="Every dark/ironic funeral scene",
        tags=["funeral", "ironic", "dark", "klezmer", "timpani"],
        highlights=[
            HighlightMoment(
                name="Frère Jacques Minor",
                start_bar=1,
                end_bar=32,
                start_time_approx=0,
                duration_approx=90,
                description="Frère Jacques transformed into funeral march",
                intensity=Intensity.MYSTICAL,
                showcase_features=["solo bass", "muted timpani", "dark transformation"],
            ),
            HighlightMoment(
                name="The Klezmer Outburst",
                start_bar=60,
                end_bar=90,
                start_time_approx=180,
                duration_approx=90,
                description="Bizarre klezmer band intrusion",
                intensity=Intensity.DRAMATIC,
                showcase_features=["clarinet", "oboe", "folk elements", "ironic"],
            ),
        ],
    ),
    # =========================================================================
    # MUSSORGSKY — Night on Bald Mountain
    # =========================================================================
    "mussorgsky_night_bald_mountain": CataloguePiece(
        id="mussorgsky_night_bald_mountain",
        title="Night on Bald Mountain",
        composer=Composer.MUSSORGSKY,
        era=Era.ROMANTIC,
        year=1867,
        duration_min=10,
        description="A witches' sabbath. Pure orchestral terror. Made famous by Disney's Fantasia.",
        showcase_reason="Demonic brass, shrieking woodwinds, orchestral chaos",
        key="G minor",
        tempo_range=(100, 168),
        midi_source="kunst_der_fuge",
        intensity=Intensity.EPIC,
        film_score_influence="Every horror/supernatural scene",
        tags=["demonic", "witches", "chaos", "fantasia", "terror"],
        highlights=[
            HighlightMoment(
                name="The Summoning",
                start_bar=1,
                end_bar=40,
                start_time_approx=0,
                duration_approx=45,
                description="Chernobog rises — thundering brass and strings",
                intensity=Intensity.EPIC,
                showcase_features=["brass power", "string tremolo", "timpani thunder"],
            ),
            HighlightMoment(
                name="Witches' Dance",
                start_bar=80,
                end_bar=140,
                start_time_approx=100,
                duration_approx=80,
                description="Frenzied dance of the demons",
                intensity=Intensity.EPIC,
                showcase_features=["woodwind shrieks", "brass fanfares", "percussion frenzy"],
            ),
            HighlightMoment(
                name="Dawn and Peace",
                start_bar=200,
                end_bar=240,
                start_time_approx=280,
                duration_approx=120,
                description="Church bells dispel the evil — transcendent calm",
                intensity=Intensity.LYRICAL,
                showcase_features=["bells", "strings ppp", "transformation"],
            ),
        ],
    ),
    # =========================================================================
    # DVORAK — New World Symphony
    # =========================================================================
    "dvorak_new_world_4": CataloguePiece(
        id="dvorak_new_world_4",
        title="Symphony No. 9 'New World' - Fourth Movement",
        composer=Composer.DVORAK,
        era=Era.ROMANTIC,
        year=1893,
        duration_min=12,
        description="The New World in all its power and glory. "
        "Brass fanfares, driving rhythms, triumphant finale.",
        showcase_reason="Perfect BBC showcase: brass fanfares, timpani, string passion",
        key="E minor → E major",
        tempo_range=(126, 160),
        midi_source="kunst_der_fuge",
        intensity=Intensity.EPIC,
        film_score_influence="Every 'arrival' or 'new beginning' scene",
        tags=["new world", "fanfare", "triumph", "adventure"],
        highlights=[
            HighlightMoment(
                name="Opening Fanfare",
                start_bar=1,
                end_bar=24,
                start_time_approx=0,
                duration_approx=30,
                description="The explosive brass opening",
                intensity=Intensity.EPIC,
                showcase_features=["brass fanfare", "timpani", "heroic theme"],
            ),
            HighlightMoment(
                name="Thematic Synthesis",
                start_bar=280,
                end_bar=340,
                start_time_approx=420,
                duration_approx=90,
                description="All four movements' themes combine",
                intensity=Intensity.EPIC,
                showcase_features=["thematic development", "full orchestra", "synthesis"],
            ),
            HighlightMoment(
                name="Final Triumph",
                start_bar=380,
                end_bar=420,
                start_time_approx=540,
                duration_approx=60,
                description="E major victory — the New World achieved",
                intensity=Intensity.EPIC,
                showcase_features=["brass fff", "timpani", "E major glory"],
            ),
        ],
    ),
    # =========================================================================
    # RIMSKY-KORSAKOV — Scheherazade
    # =========================================================================
    "rimsky_scheherazade_4": CataloguePiece(
        id="rimsky_scheherazade_4",
        title="Scheherazade - IV. Festival at Baghdad",
        composer=Composer.RIMSKY_KORSAKOV,
        era=Era.ROMANTIC,
        year=1888,
        duration_min=12,
        description="The ultimate orchestral showpiece. Every section gets to shine. "
        "Exotic colors, virtuosic passages, spectacular finale.",
        showcase_reason="Showcases EVERY section: violin solo, brass, woodwinds, percussion",
        key="E minor",
        tempo_range=(88, 168),
        midi_source="kunst_der_fuge",
        intensity=Intensity.EPIC,
        film_score_influence="Every 'exotic adventure' scene",
        tags=["exotic", "virtuosic", "festival", "arabian nights"],
        highlights=[
            HighlightMoment(
                name="Festival Opening",
                start_bar=1,
                end_bar=60,
                start_time_approx=0,
                duration_approx=60,
                description="The bustling festival begins",
                intensity=Intensity.DRAMATIC,
                showcase_features=["rhythmic drive", "brass fanfares", "exotic color"],
            ),
            HighlightMoment(
                name="The Shipwreck",
                start_bar=180,
                end_bar=240,
                start_time_approx=300,
                duration_approx=90,
                description="Storm at sea — orchestral fury",
                intensity=Intensity.EPIC,
                showcase_features=["brass storm", "string tremolo", "percussion crash"],
            ),
            HighlightMoment(
                name="Scheherazade's Triumph",
                start_bar=280,
                end_bar=320,
                start_time_approx=420,
                duration_approx=60,
                description="The storyteller wins — violin solo over orchestra",
                intensity=Intensity.LYRICAL,
                showcase_features=["solo violin", "orchestral shimmer", "resolution"],
            ),
        ],
    ),
}


# =============================================================================
# API FUNCTIONS
# =============================================================================


def get_piece(piece_id: str) -> CataloguePiece | None:
    """Get a piece from the catalogue."""
    return CATALOGUE.get(piece_id)


def list_pieces() -> list[str]:
    """List all piece IDs in the catalogue."""
    return list(CATALOGUE.keys())


def list_by_composer(composer: Composer | str) -> list[CataloguePiece]:
    """Get all pieces by a composer."""
    if isinstance(composer, str):
        composer = Composer(composer.lower())
    return [p for p in CATALOGUE.values() if p.composer == composer]


def list_by_intensity(intensity: Intensity | str) -> list[CataloguePiece]:
    """Get all pieces with a given intensity."""
    if isinstance(intensity, str):
        intensity = Intensity(intensity.lower())
    return [p for p in CATALOGUE.values() if p.intensity == intensity]


def get_all_highlights() -> list[tuple[CataloguePiece, HighlightMoment]]:
    """Get all highlight moments across all pieces."""
    highlights = []
    for piece in CATALOGUE.values():
        for moment in piece.highlights:
            highlights.append((piece, moment))
    return highlights


def get_epic_highlights() -> list[tuple[CataloguePiece, HighlightMoment]]:
    """Get only EPIC intensity highlights."""
    return [
        (piece, moment)
        for piece, moment in get_all_highlights()
        if moment.intensity == Intensity.EPIC
    ]


def describe_catalogue() -> str:
    """Generate a human-readable catalogue description."""
    lines = [
        "# MIDI CATALOGUE — Tour de Force Selection",
        "",
        f"**{len(CATALOGUE)} Pieces** from **{len({p.composer for p in CATALOGUE.values()})} Composers**",
        "",
        "All works are PUBLIC DOMAIN (composers died 70+ years ago).",
        "",
        "## By Composer:",
        "",
    ]

    for composer in Composer:
        pieces = list_by_composer(composer)
        if pieces:
            lines.append(f"### {composer.value.title().replace('_', '-')}")
            for p in pieces:
                lines.append(f"- **{p.title}** ({p.year}) — {p.showcase_reason}")
            lines.append("")

    lines.extend(
        [
            "## Highlight Moments:",
            "",
        ]
    )

    epic = get_epic_highlights()
    lines.append(f"**{len(epic)} EPIC moments** ready for rendering:")
    for piece, moment in epic[:10]:  # Top 10
        lines.append(f"- {piece.title}: **{moment.name}** — {moment.description[:60]}...")

    return "\n".join(lines)


__all__ = [
    "CATALOGUE",
    "CataloguePiece",
    "Composer",
    "Era",
    "HighlightMoment",
    "Intensity",
    "describe_catalogue",
    "get_all_highlights",
    "get_epic_highlights",
    "get_piece",
    "list_by_composer",
    "list_by_intensity",
    "list_pieces",
]
