"""BBC Symphony Orchestra — Virtuoso Integration System.

This module implements a virtuoso-informed approach to BBC SO orchestration,
drawing on the techniques and philosophies of legendary musicians and conductors.

The system evaluates each instrument from 8 perspectives and generates
demonstration samples that showcase the full expressive capabilities.

Reference Musicians:
    Strings: Heifetz, Perlman, Hahn, du Pré, Rostropovich, Primrose, Bashmet
    Woodwinds: Galway, Pahud, Holliger, Mayer, Sabine Meyer, Thunemann
    Brass: Dennis Brain, Tuckwell, André, Hardenberger, Lindberg, Bobo
    Percussion: Saul Goodman, Salzedo

Reference Conductors:
    Karajan (legato), Bernstein (dramatic), Kleiber (precise),
    Rattle (clarity), Abbado (transparent), Solti (power)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .bbc_database import BBC_INSTRUMENTS_DATABASE

# =============================================================================
# VIRTUOSO REFERENCE DATABASE
# =============================================================================


class VirtuosoStyle(Enum):
    """Playing styles inspired by legendary musicians."""

    HEIFETZ = "heifetz"  # Precision, clean tone, controlled vibrato
    PERLMAN = "perlman"  # Warm, singing tone, expressive vibrato
    DU_PRE = "du_pre"  # Passionate, wide vibrato, emotional extremes
    ROSTROPOVICH = "rostropovich"  # Noble, powerful, commanding presence
    GALWAY = "galway"  # Golden tone, breath control, Irish lilt
    BRAIN = "brain"  # Seamless legato, noble character, perfect intonation
    ANDRE = "andre"  # Brilliant, clean, precise articulation


class ConductorPhilosophy(Enum):
    """Orchestration philosophies from legendary conductors."""

    KARAJAN = "karajan"  # Legato strings, blended sound, long phrases
    BERNSTEIN = "bernstein"  # Dramatic dynamics, emotional extremes
    KLEIBER = "kleiber"  # Precise articulation, dancing rhythm
    RATTLE = "rattle"  # Modern clarity, balanced sections
    ABBADO = "abbado"  # Transparent textures, chamber-like detail
    SOLTI = "solti"  # Power, brilliance, brass-forward


@dataclass
class VirtuosoReference:
    """Reference data for a legendary musician."""

    name: str
    instrument: str
    signature_traits: list[str]
    cc1_curve: str  # "linear", "exponential", "s_curve"
    cc1_range: tuple[int, int]  # (min, max) for dynamic range
    vibrato_style: str  # "tight", "wide", "delayed", "continuous"
    vibrato_depth: int  # CC21 typical value (0-127)
    attack_style: str  # "precise", "soft", "accented"
    legato_overlap: int  # Ticks of note overlap for legato (-20 to +30)
    release_style: str  # "short", "natural", "long"


# Legendary musicians by instrument family
VIRTUOSO_DATABASE: dict[str, VirtuosoReference] = {
    # STRINGS - Violin
    "heifetz": VirtuosoReference(
        name="Jascha Heifetz",
        instrument="violin",
        signature_traits=["precision", "controlled_vibrato", "clean_tone", "fast_passages"],
        cc1_curve="linear",
        cc1_range=(30, 115),
        vibrato_style="tight",
        vibrato_depth=45,
        attack_style="precise",
        legato_overlap=5,
        release_style="natural",
    ),
    "perlman": VirtuosoReference(
        name="Itzhak Perlman",
        instrument="violin",
        signature_traits=["warm_tone", "singing_quality", "expressive_vibrato", "emotional"],
        cc1_curve="s_curve",
        cc1_range=(25, 120),
        vibrato_style="wide",
        vibrato_depth=70,
        attack_style="soft",
        legato_overlap=12,
        release_style="long",
    ),
    "hahn": VirtuosoReference(
        name="Hilary Hahn",
        instrument="violin",
        signature_traits=["clarity", "modern_precision", "intellectual", "balanced"],
        cc1_curve="linear",
        cc1_range=(35, 110),
        vibrato_style="delayed",
        vibrato_depth=55,
        attack_style="precise",
        legato_overlap=8,
        release_style="natural",
    ),
    # STRINGS - Viola
    "primrose": VirtuosoReference(
        name="William Primrose",
        instrument="viola",
        signature_traits=["dark_tone", "viola_as_solo", "inner_voice_mastery"],
        cc1_curve="s_curve",
        cc1_range=(30, 115),
        vibrato_style="wide",
        vibrato_depth=60,
        attack_style="soft",
        legato_overlap=10,
        release_style="natural",
    ),
    "bashmet": VirtuosoReference(
        name="Yuri Bashmet",
        instrument="viola",
        signature_traits=["intense", "russian_school", "dramatic", "powerful"],
        cc1_curve="exponential",
        cc1_range=(20, 125),
        vibrato_style="continuous",
        vibrato_depth=75,
        attack_style="accented",
        legato_overlap=8,
        release_style="long",
    ),
    # STRINGS - Cello
    "du_pre": VirtuosoReference(
        name="Jacqueline du Pré",
        instrument="cello",
        signature_traits=["passionate", "wide_vibrato", "emotional_extremes", "singing"],
        cc1_curve="exponential",
        cc1_range=(15, 127),
        vibrato_style="wide",
        vibrato_depth=85,
        attack_style="accented",
        legato_overlap=15,
        release_style="long",
    ),
    "rostropovich": VirtuosoReference(
        name="Mstislav Rostropovich",
        instrument="cello",
        signature_traits=["noble", "commanding", "powerful", "authoritative"],
        cc1_curve="s_curve",
        cc1_range=(25, 120),
        vibrato_style="continuous",
        vibrato_depth=65,
        attack_style="precise",
        legato_overlap=10,
        release_style="natural",
    ),
    "yo_yo_ma": VirtuosoReference(
        name="Yo-Yo Ma",
        instrument="cello",
        signature_traits=["versatile", "warm", "communicative", "accessible"],
        cc1_curve="s_curve",
        cc1_range=(30, 115),
        vibrato_style="wide",
        vibrato_depth=60,
        attack_style="soft",
        legato_overlap=12,
        release_style="long",
    ),
    # STRINGS - Bass
    "karr": VirtuosoReference(
        name="Gary Karr",
        instrument="bass",
        signature_traits=["singing_bass", "solo_virtuoso", "lyrical"],
        cc1_curve="s_curve",
        cc1_range=(35, 110),
        vibrato_style="wide",
        vibrato_depth=50,
        attack_style="soft",
        legato_overlap=8,
        release_style="natural",
    ),
    "meyer": VirtuosoReference(
        name="Edgar Meyer",
        instrument="bass",
        signature_traits=["clarity", "rhythmic", "crossover", "precise"],
        cc1_curve="linear",
        cc1_range=(40, 105),
        vibrato_style="tight",
        vibrato_depth=35,
        attack_style="precise",
        legato_overlap=5,
        release_style="short",
    ),
    # WOODWINDS - Flute
    "galway": VirtuosoReference(
        name="James Galway",
        instrument="flute",
        signature_traits=["golden_tone", "breath_control", "irish_warmth", "singing"],
        cc1_curve="s_curve",
        cc1_range=(30, 115),
        vibrato_style="continuous",
        vibrato_depth=55,
        attack_style="soft",
        legato_overlap=10,
        release_style="natural",
    ),
    "pahud": VirtuosoReference(
        name="Emmanuel Pahud",
        instrument="flute",
        signature_traits=["color_changes", "modern", "versatile", "brilliant"],
        cc1_curve="linear",
        cc1_range=(35, 120),
        vibrato_style="delayed",
        vibrato_depth=50,
        attack_style="precise",
        legato_overlap=8,
        release_style="natural",
    ),
    # WOODWINDS - Oboe
    "holliger": VirtuosoReference(
        name="Heinz Holliger",
        instrument="oboe",
        signature_traits=["expressive", "extended_techniques", "modern", "intense"],
        cc1_curve="exponential",
        cc1_range=(25, 120),
        vibrato_style="tight",
        vibrato_depth=40,
        attack_style="precise",
        legato_overlap=6,
        release_style="natural",
    ),
    "mayer": VirtuosoReference(
        name="Albrecht Mayer",
        instrument="oboe",
        signature_traits=["singing", "warm", "romantic", "expressive"],
        cc1_curve="s_curve",
        cc1_range=(30, 115),
        vibrato_style="wide",
        vibrato_depth=55,
        attack_style="soft",
        legato_overlap=10,
        release_style="long",
    ),
    # WOODWINDS - Clarinet
    "sabine_meyer": VirtuosoReference(
        name="Sabine Meyer",
        instrument="clarinet",
        signature_traits=["dynamic_range", "legato", "german_school", "controlled"],
        cc1_curve="s_curve",
        cc1_range=(20, 125),
        vibrato_style="tight",
        vibrato_depth=25,
        attack_style="soft",
        legato_overlap=12,
        release_style="natural",
    ),
    "frost": VirtuosoReference(
        name="Martin Fröst",
        instrument="clarinet",
        signature_traits=["theatrical", "expressive", "modern", "dynamic"],
        cc1_curve="exponential",
        cc1_range=(15, 127),
        vibrato_style="delayed",
        vibrato_depth=35,
        attack_style="precise",
        legato_overlap=8,
        release_style="natural",
    ),
    # WOODWINDS - Bassoon
    "thunemann": VirtuosoReference(
        name="Klaus Thunemann",
        instrument="bassoon",
        signature_traits=["character", "staccato_precision", "german_school", "warm"],
        cc1_curve="linear",
        cc1_range=(35, 110),
        vibrato_style="tight",
        vibrato_depth=30,
        attack_style="precise",
        legato_overlap=6,
        release_style="short",
    ),
    # BRASS - Horn
    "brain": VirtuosoReference(
        name="Dennis Brain",
        instrument="horn",
        signature_traits=["seamless_legato", "noble", "perfect_intonation", "golden_age"],
        cc1_curve="s_curve",
        cc1_range=(30, 115),
        vibrato_style="tight",
        vibrato_depth=20,
        attack_style="soft",
        legato_overlap=15,
        release_style="long",
    ),
    "tuckwell": VirtuosoReference(
        name="Barry Tuckwell",
        instrument="horn",
        signature_traits=["brilliant", "powerful", "commanding", "australian"],
        cc1_curve="linear",
        cc1_range=(35, 120),
        vibrato_style="tight",
        vibrato_depth=25,
        attack_style="precise",
        legato_overlap=10,
        release_style="natural",
    ),
    # BRASS - Trumpet
    "andre": VirtuosoReference(
        name="Maurice André",
        instrument="trumpet",
        signature_traits=["brilliant", "clean", "baroque_master", "precise"],
        cc1_curve="linear",
        cc1_range=(40, 115),
        vibrato_style="tight",
        vibrato_depth=30,
        attack_style="precise",
        legato_overlap=5,
        release_style="short",
    ),
    "hardenberger": VirtuosoReference(
        name="Håkan Hardenberger",
        instrument="trumpet",
        signature_traits=["modern", "versatile", "powerful", "extended_range"],
        cc1_curve="s_curve",
        cc1_range=(30, 125),
        vibrato_style="delayed",
        vibrato_depth=35,
        attack_style="precise",
        legato_overlap=8,
        release_style="natural",
    ),
    # BRASS - Trombone
    "lindberg": VirtuosoReference(
        name="Christian Lindberg",
        instrument="trombone",
        signature_traits=["power", "finesse", "virtuoso", "theatrical"],
        cc1_curve="exponential",
        cc1_range=(25, 127),
        vibrato_style="wide",
        vibrato_depth=40,
        attack_style="accented",
        legato_overlap=10,
        release_style="natural",
    ),
    # BRASS - Tuba
    "bobo": VirtuosoReference(
        name="Roger Bobo",
        instrument="tuba",
        signature_traits=["foundation", "agility", "solo_virtuoso", "lyrical"],
        cc1_curve="s_curve",
        cc1_range=(35, 110),
        vibrato_style="wide",
        vibrato_depth=35,
        attack_style="soft",
        legato_overlap=8,
        release_style="natural",
    ),
    # PERCUSSION - Timpani
    "goodman": VirtuosoReference(
        name="Saul Goodman",
        instrument="timpani",
        signature_traits=["precision", "musicality", "nyphil_legend", "rolls"],
        cc1_curve="linear",
        cc1_range=(40, 120),
        vibrato_style="tight",
        vibrato_depth=0,
        attack_style="precise",
        legato_overlap=0,
        release_style="natural",
    ),
    # PERCUSSION - Harp
    "salzedo": VirtuosoReference(
        name="Carlos Salzedo",
        instrument="harp",
        signature_traits=["color", "extended_techniques", "french_school", "pedal_master"],
        cc1_curve="s_curve",
        cc1_range=(30, 115),
        vibrato_style="tight",
        vibrato_depth=0,
        attack_style="soft",
        legato_overlap=5,
        release_style="long",
    ),
}


# =============================================================================
# CONDUCTOR PHILOSOPHY PRESETS
# =============================================================================


@dataclass
class ConductorPreset:
    """Orchestration preset based on a conductor's philosophy."""

    name: str
    philosophy: str
    string_balance: float  # 0.8-1.2 relative to default
    brass_balance: float
    woodwind_balance: float
    percussion_balance: float
    overall_dynamics: str  # "compressed", "natural", "wide"
    legato_emphasis: float  # 0.5-1.5 multiplier for legato overlap
    articulation_precision: float  # 0.5-1.5 multiplier for attack tightness
    reverb_amount: int  # CC19 base value
    tempo_rubato: float  # 0.9-1.1 tempo flexibility


CONDUCTOR_PRESETS: dict[str, ConductorPreset] = {
    "karajan": ConductorPreset(
        name="Herbert von Karajan",
        philosophy="Legato strings, blended sound, long phrases",
        string_balance=1.1,
        brass_balance=0.9,
        woodwind_balance=0.95,
        percussion_balance=0.85,
        overall_dynamics="compressed",
        legato_emphasis=1.4,
        articulation_precision=0.8,
        reverb_amount=70,
        tempo_rubato=1.05,
    ),
    "bernstein": ConductorPreset(
        name="Leonard Bernstein",
        philosophy="Dramatic dynamics, emotional extremes",
        string_balance=1.0,
        brass_balance=1.1,
        woodwind_balance=1.0,
        percussion_balance=1.1,
        overall_dynamics="wide",
        legato_emphasis=1.1,
        articulation_precision=1.0,
        reverb_amount=55,
        tempo_rubato=1.15,
    ),
    "kleiber": ConductorPreset(
        name="Carlos Kleiber",
        philosophy="Precise articulation, dancing rhythm",
        string_balance=1.0,
        brass_balance=0.95,
        woodwind_balance=1.05,
        percussion_balance=0.9,
        overall_dynamics="natural",
        legato_emphasis=0.9,
        articulation_precision=1.3,
        reverb_amount=50,
        tempo_rubato=0.95,
    ),
    "rattle": ConductorPreset(
        name="Sir Simon Rattle",
        philosophy="Modern clarity, balanced sections",
        string_balance=1.0,
        brass_balance=1.0,
        woodwind_balance=1.0,
        percussion_balance=1.0,
        overall_dynamics="natural",
        legato_emphasis=1.0,
        articulation_precision=1.1,
        reverb_amount=45,
        tempo_rubato=1.0,
    ),
    "abbado": ConductorPreset(
        name="Claudio Abbado",
        philosophy="Transparent textures, chamber-like detail",
        string_balance=0.95,
        brass_balance=0.85,
        woodwind_balance=1.1,
        percussion_balance=0.8,
        overall_dynamics="natural",
        legato_emphasis=1.0,
        articulation_precision=1.2,
        reverb_amount=40,
        tempo_rubato=1.02,
    ),
    "solti": ConductorPreset(
        name="Georg Solti",
        philosophy="Power, brilliance, brass-forward",
        string_balance=1.05,
        brass_balance=1.2,
        woodwind_balance=0.95,
        percussion_balance=1.15,
        overall_dynamics="wide",
        legato_emphasis=0.85,
        articulation_precision=1.15,
        reverb_amount=60,
        tempo_rubato=0.98,
    ),
}


# =============================================================================
# 8-PERSPECTIVE GRADING SYSTEM
# =============================================================================


class GradingPerspective(Enum):
    """The 8 perspectives for evaluating instrument integration."""

    VIRTUOSO = "virtuoso"  # Can it play like Heifetz/Perlman?
    CONDUCTOR = "conductor"  # Does it blend and balance?
    COMPOSER = "composer"  # Does it realize the written score?
    ENGINEER = "engineer"  # Recording quality, mic options
    FILM_SCORER = "film_scorer"  # Cinematic impact, emotion
    ORCHESTRATOR = "orchestrator"  # Section combinations, doublings
    PERFORMER = "performer"  # Playability, controller response
    LISTENER = "listener"  # Realism, emotional impact


PERSPECTIVE_WEIGHTS: dict[GradingPerspective, float] = {
    GradingPerspective.VIRTUOSO: 0.15,
    GradingPerspective.CONDUCTOR: 0.15,
    GradingPerspective.COMPOSER: 0.15,
    GradingPerspective.ENGINEER: 0.10,
    GradingPerspective.FILM_SCORER: 0.15,
    GradingPerspective.ORCHESTRATOR: 0.10,
    GradingPerspective.PERFORMER: 0.10,
    GradingPerspective.LISTENER: 0.10,
}


@dataclass
class PerspectiveGrade:
    """Grade for a single perspective."""

    perspective: GradingPerspective
    score: int  # 0-100
    strengths: list[str]
    weaknesses: list[str]
    recommendations: list[str]


@dataclass
class InstrumentGrade:
    """Complete grading for an instrument across all perspectives."""

    instrument_key: str
    instrument_name: str
    family: str
    perspective_grades: dict[GradingPerspective, PerspectiveGrade]
    weighted_total: float
    articulation_count: int
    has_legato: bool
    has_muted: bool
    has_extended: bool

    @property
    def needs_improvement(self) -> bool:
        """Check if any perspective is below 85."""
        return any(g.score < 85 for g in self.perspective_grades.values())

    @property
    def lowest_perspective(self) -> GradingPerspective:
        """Get the perspective with the lowest score."""
        return min(self.perspective_grades, key=lambda p: self.perspective_grades[p].score)


def grade_instrument(instrument_key: str) -> InstrumentGrade:
    """Grade an instrument from all 8 perspectives.

    Args:
        instrument_key: Key from BBC_INSTRUMENTS_DATABASE

    Returns:
        Complete InstrumentGrade with all perspective scores
    """
    info = BBC_INSTRUMENTS_DATABASE.get(instrument_key)
    if not info:
        raise ValueError(f"Unknown instrument: {instrument_key}")

    arts = info["articulations"]
    family = info["family"]
    name = info["bbc_name"]

    # Analyze articulation capabilities
    has_legato = any("Legato" in a for a in arts)
    has_muted = any("Muted" in a for a in arts)
    has_tremolo = any("Tremolo" in a for a in arts)
    has_trill = any("Trill" in a for a in arts)
    has_extended = (
        has_muted
        or has_tremolo
        or any(
            x in str(arts) for x in ["Sul Pont", "Col Legno", "Harmonics", "Flutter", "Multitongue"]
        )
    )
    has_shorts = sum(1 for a in arts if "Short" in a or "Spicc" in a or "Stac" in a)
    has_longs = sum(1 for a in arts if "Long" in a)

    grades: dict[GradingPerspective, PerspectiveGrade] = {}

    # VIRTUOSO perspective
    virt_score = 70
    virt_strengths = []
    virt_weaknesses = []
    virt_recs = []

    if has_legato:
        virt_score += 10
        virt_strengths.append("True legato available")
    else:
        virt_weaknesses.append("No legato articulation")
        virt_recs.append("Use overlapping notes to simulate legato")

    if has_shorts >= 3:
        virt_score += 8
        virt_strengths.append("Multiple short articulations for variety")
    if has_trill:
        virt_score += 5
        virt_strengths.append("Trills available for ornaments")
    if len(arts) >= 15:
        virt_score += 7
        virt_strengths.append("Rich articulation palette")

    grades[GradingPerspective.VIRTUOSO] = PerspectiveGrade(
        perspective=GradingPerspective.VIRTUOSO,
        score=min(100, virt_score),
        strengths=virt_strengths,
        weaknesses=virt_weaknesses,
        recommendations=virt_recs,
    )

    # CONDUCTOR perspective
    cond_score = 75
    cond_strengths = ["Recorded at Maida Vale with proper orchestral seating"]
    cond_weaknesses = []
    cond_recs = []

    if family == "Strings":
        cond_score += 10
        cond_strengths.append("Strings blend well in ensemble")
    if has_muted:
        cond_score += 5
        cond_strengths.append("Muted variants for color")
    if has_longs >= 3:
        cond_score += 5
        cond_strengths.append("Multiple sustain options for blending")

    grades[GradingPerspective.CONDUCTOR] = PerspectiveGrade(
        perspective=GradingPerspective.CONDUCTOR,
        score=min(100, cond_score),
        strengths=cond_strengths,
        weaknesses=cond_weaknesses,
        recommendations=cond_recs,
    )

    # COMPOSER perspective
    comp_score = 80
    comp_strengths = ["All standard articulations present"]
    comp_weaknesses = []
    comp_recs = []

    if has_legato:
        comp_score += 8
    if has_shorts >= 2:
        comp_score += 5
    if has_extended:
        comp_score += 7
        comp_strengths.append("Extended techniques available")

    grades[GradingPerspective.COMPOSER] = PerspectiveGrade(
        perspective=GradingPerspective.COMPOSER,
        score=min(100, comp_score),
        strengths=comp_strengths,
        weaknesses=comp_weaknesses,
        recommendations=comp_recs,
    )

    # ENGINEER perspective
    eng_score = 85  # BBC SO has excellent recording quality
    eng_strengths = ["8 microphone positions", "Maida Vale Studio recording", "Professional mixing"]
    eng_weaknesses = []
    eng_recs = []

    if family == "Percussion":
        eng_score += 5
        eng_strengths.append("Excellent close mic options for percussion")

    grades[GradingPerspective.ENGINEER] = PerspectiveGrade(
        perspective=GradingPerspective.ENGINEER,
        score=min(100, eng_score),
        strengths=eng_strengths,
        weaknesses=eng_weaknesses,
        recommendations=eng_recs,
    )

    # FILM_SCORER perspective
    film_score = 75
    film_strengths = []
    film_weaknesses = []
    film_recs = []

    if has_tremolo:
        film_score += 10
        film_strengths.append("Tremolo for tension/drama")
    if has_muted:
        film_score += 8
        film_strengths.append("Muted variants for intimate scenes")
    if family == "Brass":
        film_score += 7
        film_strengths.append("Powerful brass for heroic themes")
    if "Sul Pont" in str(arts) or "Harmonics" in str(arts):
        film_score += 5
        film_strengths.append("Eerie textures available")

    grades[GradingPerspective.FILM_SCORER] = PerspectiveGrade(
        perspective=GradingPerspective.FILM_SCORER,
        score=min(100, film_score),
        strengths=film_strengths,
        weaknesses=film_weaknesses,
        recommendations=film_recs,
    )

    # ORCHESTRATOR perspective
    orch_score = 80
    orch_strengths = ["Standard orchestral registration"]
    orch_weaknesses = []
    orch_recs = []

    if "a2" in instrument_key or "a3" in instrument_key or "a4" in instrument_key:
        orch_score += 10
        orch_strengths.append("Section unison available")
    if "Leader" in name:
        orch_score += 5
        orch_strengths.append("Solo voice for exposed passages")

    grades[GradingPerspective.ORCHESTRATOR] = PerspectiveGrade(
        perspective=GradingPerspective.ORCHESTRATOR,
        score=min(100, orch_score),
        strengths=orch_strengths,
        weaknesses=orch_weaknesses,
        recommendations=orch_recs,
    )

    # PERFORMER perspective
    perf_score = 80
    perf_strengths = ["CC1 dynamics responsive", "CC11 expression available"]
    perf_weaknesses = []
    perf_recs = []

    if has_legato:
        perf_score += 10
        perf_strengths.append("Real-time legato switching")
    if len(arts) > 10:
        perf_weaknesses.append("Many articulations require keyswitch management")
        perf_recs.append("Use CC32 for articulation switching in performance")

    grades[GradingPerspective.PERFORMER] = PerspectiveGrade(
        perspective=GradingPerspective.PERFORMER,
        score=min(100, perf_score),
        strengths=perf_strengths,
        weaknesses=perf_weaknesses,
        recommendations=perf_recs,
    )

    # LISTENER perspective
    list_score = 85  # BBC SO is high quality
    list_strengths = ["World-class recording quality", "Natural room sound"]
    list_weaknesses = []
    list_recs = []

    if "Leader" in name:
        list_score -= 5
        list_weaknesses.append("Solo instruments more exposed, harder to fake")
        list_recs.append("Pay extra attention to CC1/CC21 curves for realism")
    if family == "Strings" and len(arts) >= 15:
        list_score += 5
        list_strengths.append("Rich sample variety for natural sound")

    grades[GradingPerspective.LISTENER] = PerspectiveGrade(
        perspective=GradingPerspective.LISTENER,
        score=min(100, list_score),
        strengths=list_strengths,
        weaknesses=list_weaknesses,
        recommendations=list_recs,
    )

    # Calculate weighted total
    weighted_total = sum(grades[p].score * PERSPECTIVE_WEIGHTS[p] for p in GradingPerspective)

    return InstrumentGrade(
        instrument_key=instrument_key,
        instrument_name=name,
        family=family,
        perspective_grades=grades,
        weighted_total=weighted_total,
        articulation_count=len(arts),
        has_legato=has_legato,
        has_muted=has_muted,
        has_extended=has_extended,
    )


def grade_all_instruments() -> dict[str, InstrumentGrade]:
    """Grade all instruments in the BBC SO database.

    Returns:
        Dict mapping instrument_key to InstrumentGrade
    """
    return {key: grade_instrument(key) for key in BBC_INSTRUMENTS_DATABASE}


# =============================================================================
# INSTRUMENT-SPECIFIC TUNING PRESETS
# =============================================================================


@dataclass
class TuningPreset:
    """MIDI CC and expression tuning preset for an instrument."""

    instrument_key: str
    virtuoso_reference: str | None  # Key into VIRTUOSO_DATABASE
    cc1_curve: str  # "linear", "exponential", "s_curve"
    cc1_min: int  # Minimum CC1 value to use
    cc1_max: int  # Maximum CC1 value to use
    cc11_offset: int  # Base expression offset
    cc17_release: int  # Release time (30-90)
    cc18_tightness: int  # Attack tightness (20-80)
    cc21_vibrato_base: int  # Base vibrato level
    cc21_vibrato_swell: bool  # Whether to add vibrato swells
    velocity_curve: str  # "linear", "soft", "hard"
    legato_overlap_ticks: int  # Note overlap for legato (-20 to +30)
    default_articulation: str  # Preferred starting articulation


def get_default_tuning(instrument_key: str) -> TuningPreset:
    """Get the default tuning preset for an instrument.

    Args:
        instrument_key: Key from BBC_INSTRUMENTS_DATABASE

    Returns:
        TuningPreset with recommended settings
    """
    info = BBC_INSTRUMENTS_DATABASE.get(instrument_key)
    if not info:
        raise ValueError(f"Unknown instrument: {instrument_key}")

    family = info["family"]
    arts = info["articulations"]

    # Default settings by family
    if family == "Strings":
        return TuningPreset(
            instrument_key=instrument_key,
            virtuoso_reference="perlman" if "violin" in instrument_key.lower() else "rostropovich",
            cc1_curve="s_curve",
            cc1_min=25,
            cc1_max=120,
            cc11_offset=20,
            cc17_release=65,
            cc18_tightness=50,
            cc21_vibrato_base=55,
            cc21_vibrato_swell=True,
            velocity_curve="soft",
            legato_overlap_ticks=10,
            default_articulation="Legato" if "Legato" in arts else "Long",
        )
    elif family == "Woodwinds":
        return TuningPreset(
            instrument_key=instrument_key,
            virtuoso_reference="galway" if "flute" in instrument_key.lower() else "holliger",
            cc1_curve="linear",
            cc1_min=30,
            cc1_max=115,
            cc11_offset=25,
            cc17_release=55,
            cc18_tightness=55,
            cc21_vibrato_base=40,
            cc21_vibrato_swell=True,
            velocity_curve="linear",
            legato_overlap_ticks=8,
            default_articulation="Legato" if "Legato" in arts else "Long",
        )
    elif family == "Brass":
        return TuningPreset(
            instrument_key=instrument_key,
            virtuoso_reference="brain" if "horn" in instrument_key.lower() else "andre",
            cc1_curve="s_curve",
            cc1_min=35,
            cc1_max=120,
            cc11_offset=30,
            cc17_release=50,
            cc18_tightness=60,
            cc21_vibrato_base=25,
            cc21_vibrato_swell=False,
            velocity_curve="linear",
            legato_overlap_ticks=8,
            default_articulation="Legato" if "Legato" in arts else "Long",
        )
    else:  # Percussion
        return TuningPreset(
            instrument_key=instrument_key,
            virtuoso_reference="goodman" if "timpani" in instrument_key.lower() else "salzedo",
            cc1_curve="linear",
            cc1_min=40,
            cc1_max=120,
            cc11_offset=20,
            cc17_release=45,
            cc18_tightness=65,
            cc21_vibrato_base=0,
            cc21_vibrato_swell=False,
            velocity_curve="linear",
            legato_overlap_ticks=0,
            default_articulation=arts[0] if arts else "Short Hits",
        )


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "CONDUCTOR_PRESETS",
    "PERSPECTIVE_WEIGHTS",
    # Databases
    "VIRTUOSO_DATABASE",
    "ConductorPhilosophy",
    "ConductorPreset",
    "GradingPerspective",
    "InstrumentGrade",
    "PerspectiveGrade",
    "TuningPreset",
    # Dataclasses
    "VirtuosoReference",
    # Enums
    "VirtuosoStyle",
    "get_default_tuning",
    "grade_all_instruments",
    # Functions
    "grade_instrument",
]
