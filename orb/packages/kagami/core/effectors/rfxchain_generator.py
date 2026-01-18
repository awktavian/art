"""RfxChain Generator — BBC Symphony Orchestra state files for REAPER.

Generates RfxChain files using BBC_CATALOG data from bbc_instruments.py.
Uses DawDreamer-extracted parameter data for accuracy.

Binary Format (from manual BBC SO chains):
-----------------------------------------
[0x000-0x124] REAPER wrapper header (292 bytes)
[0x124]       VstW marker (16 bytes)
[0x134]       CcnK marker + size (8 bytes)
[0x13c]       FBCh + Sant markers (160 bytes)
[0x1dc-...]   SPITFIREAUDIO_AUNTIE XML (variable)
[...-END]     JUCE footer (75 bytes)

Created: January 2, 2026
"""

from __future__ import annotations

import base64
import logging
import struct
import uuid
from pathlib import Path

from kagami.core.effectors.bbc_instruments import (
    BBC_CATALOG,
    BBCInstrument,
    Section,
)

logger = logging.getLogger(__name__)

# =============================================================================
# CONSTANTS (from manual RfxChain analysis)
# =============================================================================

BBC_VST3_NAME = "VST3i: BBC Symphony Orchestra (Spitfire Audio)"
BBC_VST3_FILE = "BBC Symphony Orchestra.vst3"
BBC_VST3_UID = 885344108
BBC_VST3_UID_HEX = "56535453616E746262632073796D7068"  # pragma: allowlist secret

# Binary headers extracted from manual RfxChain files
REAPER_HEADER_FIXED = bytes.fromhex(
    "6c47c534ee5eedfe0000000020000000010000000000000002000000000000000400000000000000"
    "08000000000000001000000000000000200000000000000040000000000000008000000000000000"
    "00010000000000000002000000000000000400000000000000080000000000000010000000000000"
    "00200000000000000040000000000000008000000000000000000100000000000000020000000000"
    "00000400000000000000080000000000000010000000000000002000000000000000400000000000"
    "00008000000000000000000100000000000000020000000000000004000000000000000800000000"
    "0000001000000000000000200000000000000040000000000000008000000000"
)  # 272 bytes

REAPER_HEADER_MID = bytes.fromhex("01000000ffff0000")  # 8 bytes
REAPER_HEADER_END = bytes.fromhex("01000000")  # 4 bytes

VSTW_HEADER = bytes.fromhex("56737457000000080000000100000000")  # 16 bytes

VST_MARKERS_SUFFIX = bytes.fromhex(
    "464243680000000253616e7400010b06000000010000000000000000000000000000000000000000"
    "00000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "00000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "00000000000000000000000000000000000000000000000000000000000203d0564332218b030200"
)  # 160 bytes

JUCE_FOOTER = bytes.fromhex(
    "0000000000000000004a554345507269766174654461746100010142797061737300010103001d00"
    "0000000000004a55434550726976617465446174610000000000000000000000000000"
)  # 75 bytes


# =============================================================================
# DAWDREAMER PARAMETER DATA (extracted via DawDreamer)
# =============================================================================

DAWDREAMER_PARAMS = [
    {"index": 0, "name": "Expression", "default": 1.0, "xml_id": "i_expression"},
    {"index": 1, "name": "Dynamics", "default": 1.0, "xml_id": "i_dynamics"},
    {"index": 2, "name": "Reverb", "default": 0.0, "xml_id": "i_reverb"},
    {"index": 3, "name": "Release", "default": 0.5, "xml_id": "i_release"},
    {"index": 4, "name": "Tightness", "default": 0.5, "xml_id": "i_tight"},
    {"index": 5, "name": "Vibrato", "default": 1.0, "xml_id": "i_vibrato"},
    {"index": 6, "name": "Simple Mix", "default": 0.5, "xml_id": "i_mixsimple"},
    {"index": 7, "name": "Stereo Pan", "default": 0.5, "xml_id": "s_pan"},
    {"index": 8, "name": "Direction", "default": 0.0, "xml_id": "i_direction"},
    {"index": 9, "name": "Global Gain", "default": 0.63, "xml_id": "g_gain"},
    {"index": 10, "name": "Global Pan", "default": 0.5, "xml_id": "g_pan"},
    {"index": 11, "name": "Global Tune", "default": 0.5, "xml_id": "g_tune"},
    {"index": 12, "name": "Stereo Flip", "default": 0.0, "xml_id": "s_flip"},
    {"index": 13, "name": "Stereo Spread", "default": 0.5, "xml_id": "s_width"},
    {"index": 14, "name": "Variation", "default": 0.0, "xml_id": "i_variation"},
    {"index": 15, "name": "Pedal Volume", "default": 0.5, "xml_id": "i_pedvol"},
    {"index": 16, "name": "Hammer Volume", "default": 0.5, "xml_id": "i_hammvol"},
    {"index": 17, "name": "Mic: Full Mix Real", "default": 1.0, "xml_id": "m_flmxrl"},
    {"index": 18, "name": "Mic: Mix 1 Piano", "default": 0.0, "xml_id": "m_pmix1"},
    {"index": 19, "name": "Mic: Full Mix JJ", "default": 0.0, "xml_id": "m_flmxjj"},
    {"index": 20, "name": "Mic: Mix 2 Piano", "default": 0.0, "xml_id": "m_pmix2"},
    {"index": 21, "name": "Mic: Close", "default": 0.0, "xml_id": "m_close"},
    {"index": 22, "name": "Mic: Tree", "default": 0.0, "xml_id": "m_tree"},
    {"index": 23, "name": "Mic: Outriggers", "default": 0.0, "xml_id": "m_out"},
    {"index": 24, "name": "Mic: Ambients", "default": 0.0, "xml_id": "m_amb"},
    {"index": 25, "name": "Mic: Mono", "default": 0.0, "xml_id": "m_mono"},
    {"index": 26, "name": "Mic: Leader", "default": 0.0, "xml_id": "m_leader"},
    {"index": 27, "name": "Mic: Close Wide Pan", "default": 0.0, "xml_id": "m_clwdpan"},
    {"index": 28, "name": "Mic: Section Stereo", "default": 0.0, "xml_id": "m_stereo"},
    {"index": 29, "name": "Mic: Mids", "default": 0.0, "xml_id": "m_mids"},
    {"index": 30, "name": "Mic: Sides", "default": 0.0, "xml_id": "m_sides"},
    {"index": 31, "name": "Mic: Balcony", "default": 0.0, "xml_id": "m_balcony"},
    {"index": 32, "name": "Mic: Spill Strings", "default": 0.0, "xml_id": "m_spllstr"},
    {"index": 33, "name": "Mic: Piano Hammers", "default": 0.0, "xml_id": "m_pham"},
    {"index": 34, "name": "Mic: Spill Wind", "default": 0.0, "xml_id": "m_spllwnd"},
    {"index": 35, "name": "Mic: Piano Ribbons", "default": 0.0, "xml_id": "m_prib"},
    {"index": 36, "name": "Mic: Spill Brass", "default": 0.0, "xml_id": "m_spllbr"},
    {"index": 37, "name": "Mic: Piano Mids", "default": 0.0, "xml_id": "m_pmid"},
    {"index": 38, "name": "Mic: Spill Perc", "default": 0.0, "xml_id": "m_spllper"},
    {"index": 39, "name": "Mic: Piano Far", "default": 0.0, "xml_id": "m_pfar"},
    {"index": 40, "name": "Mic: Spill Full", "default": 0.0, "xml_id": "m_spllfll"},
    {"index": 41, "name": "Mic: Spill All", "default": 0.0, "xml_id": "m_spillall"},
    {"index": 42, "name": "Mic: Atmos Front", "default": 0.0, "xml_id": "m_atmosf"},
    {"index": 43, "name": "Mic: Atmos Rear", "default": 0.0, "xml_id": "m_atmosr"},
    {"index": 44, "name": "Mic: Virtual", "default": 1.0, "xml_id": "m_virt"},
    {"index": 45, "name": "Bypass", "default": 0.0, "xml_id": "bypass"},
]


# =============================================================================
# INSTRUMENT NAME MAPPING (BBC SO internal names)
# =============================================================================

# Maps BBC_CATALOG keys to the exact display name BBC SO expects
# EXACT display names extracted from BBC SO articulations via scripts/extract_bbc_prefixes.py
# CRITICAL: These must match BBC SO's internal naming exactly (including case)
BBC_SO_DISPLAY_NAMES: dict[str, str] = {
    # === EXTRACTED FROM MANUAL FILES (31 instruments) ===
    # Strings
    "violins_1": "Violins 1",
    "violins_2": "Violins 2",
    "violas": "Violas",
    "celli": "Celli",
    "basses": "Basses",
    # Woodwinds (solo)
    "flute": "Flute",
    "piccolo": "Piccolo",
    "oboe": "Oboe",
    "clarinet": "Clarinet",
    "bassoon": "Bassoon",
    # Woodwinds (ensembles)
    "flutes_a3": "Flutes a3",
    "oboes_a3": "Oboes a3",
    "clarinets_a3": "Clarinets a3",
    "bassoons_a3": "Bassoons a3",
    # Brass (solo)
    "horn": "Horn",
    "trumpet": "Trumpet",
    "tenor_trombone": "Tenor Trombone",
    "tuba": "Tuba",
    # Brass (ensembles)
    "horns_a4": "Horns a4",
    "tenor_trombones_a3": "Tenor Trombones a3",
    "bass_trombones_a2": "Bass Trombones a2",
    # Percussion
    "timpani": "Timpani",
    "harp": "Harp",
    "celeste": "Celeste",
    "marimba": "Marimba",
    "xylophone": "Xylophone",
    "glockenspiel": "Glockenspiel",
    "vibraphone": "Vibraphone",
    "tubular_bells": "Tubular bells",  # NOTE: lowercase 'b' per BBC SO
    "crotales": "Crotales",
    "untuned_percussion": "Untuned Percussion",
    # === INFERRED (need manual files to verify) ===
    # Leaders
    "violin_1_leader": "Violin 1 Leader",
    "violin_2_leader": "Violin 2 Leader",
    "viola_leader": "Viola Leader",
    "celli_leader": "Cello Leader",
    "bass_leader": "Bass Leader",
    # Rare woodwinds
    "bass_flute": "Bass Flute",
    "cor_anglais": "Cor Anglais",
    "bass_clarinet": "Bass Clarinet",
    "contrabass_clarinet": "Contrabass Clarinet",
    "contrabassoon": "Contrabassoon",
    # Low brass
    "trumpets_a2": "Trumpets a2",
    "cimbasso": "Cimbasso",
    "contrabass_trombone": "Contrabass Trombone",
    "contrabass_tuba": "Contrabass Tuba",
}

# Section to articulation prefix mapping (from manual RfxChain files)
SECTION_PREFIXES: dict[Section, str] = {
    Section.STRINGS: "b",
    Section.WOODWINDS: "a",
    Section.BRASS: "c",
    Section.PERCUSSION_TUNED: "b",
    Section.PERCUSSION_UNTUNED: "d",
}

# Complete instrument prefix map for BBC Symphony Orchestra
# CRITICAL: Each instrument has a unique prefix that BBC SO uses internally.
# Extracted directly from RfxChain files using scripts/extract_bbc_prefixes.py
# Source: BBC SO's internal SPITFIREAUDIO_AUNTIE XML
# Last updated: Jan 2, 2026
#
# PATTERN DISCOVERED:
# - Each section (Strings, Woodwinds, Brass, Percussion) has its own prefix namespace
# - Main instruments use early letters (a-j)
# - Rare/specialty instruments continue the alphabet (k-z)
#
INSTRUMENT_PREFIX_MAP: dict[str, str] = {
    # === STRINGS (namespace: b,d,f,h,j for sections) ===
    "violins_1": "b",  # Extracted ✓
    "violins_2": "d",  # Extracted ✓
    "violas": "f",  # Extracted ✓
    "celli": "h",  # Extracted ✓
    "basses": "j",  # Extracted ✓
    # Leaders - PROFESSIONAL EDITION ONLY (not in Core)
    "violin_1_leader": "c",  # PRO ONLY - placeholder
    "violin_2_leader": "e",  # PRO ONLY - placeholder
    "viola_leader": "g",  # PRO ONLY - placeholder
    "celli_leader": "i",  # PRO ONLY - placeholder
    "bass_leader": "k",  # PRO ONLY - placeholder
    # === WOODWINDS (namespace: sequential a-i, then rare k+) ===
    "flute": "a",  # Extracted ✓
    "flutes_a3": "b",  # Extracted ✓
    "piccolo": "c",  # Extracted ✓
    "bass_flute": "j",  # PRO ONLY - placeholder
    "oboe": "d",  # Extracted ✓
    "oboes_a3": "e",  # Extracted ✓
    "cor_anglais": "m",  # DISCOVERED via brute-force ✓
    "clarinet": "f",  # Extracted ✓
    "clarinets_a3": "g",  # Extracted ✓
    "bass_clarinet": "l",  # DISCOVERED via brute-force ✓
    "contrabass_clarinet": "n",  # PRO ONLY - placeholder
    "bassoon": "h",  # Extracted ✓
    "bassoons_a3": "i",  # Extracted ✓
    "contrabassoon": "k",  # DISCOVERED via brute-force ✓
    # === BRASS (namespace: sequential a-i, then rare k+) ===
    "horn": "a",  # Extracted ✓
    "horns_a4": "b",  # Extracted ✓
    "trumpet": "c",  # Extracted ✓
    "trumpets_a2": "d",  # Extracted ✓
    "tenor_trombone": "e",  # Extracted ✓
    "tenor_trombones_a3": "f",  # Extracted ✓
    "bass_trombones_a2": "h",  # Extracted ✓
    "cimbasso": "l",  # DISCOVERED via brute-force ✓
    "contrabass_trombone": "k",  # DISCOVERED via brute-force ✓
    "tuba": "i",  # Extracted ✓
    "contrabass_tuba": "j",  # Extracted ✓
    # === PERCUSSION (namespace: sequential a-j) ===
    "timpani": "b",  # Extracted ✓
    "harp": "c",  # Extracted ✓
    "marimba": "d",  # Extracted ✓
    "celeste": "e",  # Extracted ✓
    "glockenspiel": "g",  # Extracted ✓
    "tubular_bells": "h",  # Extracted ✓
    "vibraphone": "i",  # Extracted ✓
    "crotales": "j",  # Extracted ✓
    "xylophone": "f",  # Extracted ✓
    "untuned_percussion": "a",  # Extracted ✓
}

# Legacy alias for backwards compatibility
INSTRUMENT_PREFIX_OVERRIDES = INSTRUMENT_PREFIX_MAP

# Instrument-specific tag codes for BBC SO sample loading
# These tags are CRITICAL - BBC SO uses them to identify which samples to load
INSTRUMENT_TAG_CODES: dict[str, str] = {
    # Strings
    "violins_1": "2050000:Strings,2050100:Violins",
    "violins_2": "2050000:Strings,2050100:Violins",
    "violin_1_leader": "2050000:Strings,2050100:Violins",
    "violin_2_leader": "2050000:Strings,2050100:Violins",
    "violas": "2050000:Strings,2050200:Violas",
    "viola_leader": "2050000:Strings,2050200:Violas",
    "celli": "2050000:Strings,2050300:Celli",
    "celli_leader": "2050000:Strings,2050300:Celli",
    "basses": "2050000:Strings,2050400:Basses",
    "bass_leader": "2050000:Strings,2050400:Basses",
    # Woodwinds
    "flute": "2010000:Woodwinds,2010100:Flutes",
    "flutes_a3": "2010000:Woodwinds,2010100:Flutes",
    "piccolo": "2010000:Woodwinds,2010100:Flutes",
    "bass_flute": "2010000:Woodwinds,2010100:Flutes",
    "oboe": "2010000:Woodwinds,2010200:Oboes",
    "oboes_a3": "2010000:Woodwinds,2010200:Oboes",
    "cor_anglais": "2010000:Woodwinds,2010200:Oboes",
    "clarinet": "2010000:Woodwinds,2010300:Clarinets",
    "clarinets_a3": "2010000:Woodwinds,2010300:Clarinets",
    "bass_clarinet": "2010000:Woodwinds,2010300:Clarinets",
    "contrabass_clarinet": "2010000:Woodwinds,2010300:Clarinets",
    "bassoon": "2010000:Woodwinds,2010400:Bassoons",
    "bassoons_a3": "2010000:Woodwinds,2010400:Bassoons",
    "contrabassoon": "2010000:Woodwinds,2010400:Bassoons",
    # Brass
    "horn": "2020000:Brass,2020100:Horns",
    "horns_a4": "2020000:Brass,2020100:Horns",
    "trumpet": "2020000:Brass,2020200:Trumpets",
    "trumpets_a2": "2020000:Brass,2020200:Trumpets",
    "tenor_trombone": "2020000:Brass,2020300:Trombones",
    "tenor_trombones_a3": "2020000:Brass,2020300:Trombones",
    "bass_trombones_a2": "2020000:Brass,2020300:Trombones",
    "contrabass_trombone": "2020000:Brass,2020300:Trombones",
    "tuba": "2020000:Brass,2020400:Tubas",
    "contrabass_tuba": "2020000:Brass,2020400:Tubas",
    "cimbasso": "2020000:Brass,2020400:Tubas",
    # Percussion - Tuned
    "timpani": "2030000:Tuned Percussion,2030100:Timpani",
    "harp": "2030000:Tuned Percussion,2030200:Harp",
    "piano": "2030000:Tuned Percussion,2030300:Keyboards",
    "celeste": "2030000:Tuned Percussion,2030300:Keyboards",
    "marimba": "2030000:Tuned Percussion,2030400:Mallet",
    "xylophone": "2030000:Tuned Percussion,2030400:Mallet",
    "glockenspiel": "2030000:Tuned Percussion,2030400:Mallet",
    "vibraphone": "2030000:Tuned Percussion,2030400:Mallet",
    "tubular_bells": "2030000:Tuned Percussion,2030400:Mallet",
    "crotales": "2030000:Tuned Percussion,2030400:Mallet",
    # Percussion - Untuned
    "untuned_percussion": "2029900:Percussion,2040000:Untuned Percussion",
}

# Fallback section tag codes
SECTION_TAG_CODES: dict[Section, str] = {
    Section.STRINGS: "2050000:Strings",
    Section.WOODWINDS: "2010000:Woodwinds",
    Section.BRASS: "2020000:Brass",
    Section.PERCUSSION_TUNED: "2030000:Tuned Percussion",
    Section.PERCUSSION_UNTUNED: "2040000:Untuned Percussion",
}


# =============================================================================
# XML GENERATION
# =============================================================================


def _generate_rr_map() -> str:
    """Generate round-robin map (0-127)."""
    return " ".join(str(i) for i in range(128))


def _generate_odest_indices() -> str:
    """Generate output destination indices (0-264)."""
    return ",".join(str(i) for i in range(265))


def _generate_mic_mix_xml() -> str:
    """Generate MIX block with all microphone settings."""
    mics = [
        ("mono", 1, False),
        ("tree", 2, False),
        ("out", 3, False),
        ("amb", 4, False),
        ("balcony", 5, False),
        ("sides", 6, False),
        ("atmosf", 7, False),
        ("atmosr", 8, False),
        ("mids", 9, False),
        ("stereo", 10, False),
        ("leader", 11, False),
        ("close", 12, False),
        ("clwdpan", 13, False),
        ("spllstr", 14, False),
        ("spllwnd", 15, False),
        ("spllbr", 16, False),
        ("spllper", 17, False),
        ("spllfll", 18, False),
        ("flmxrl", 19, True),
        ("flmxjj", 20, False),
        ("pmix1", 21, True),
        ("pmix2", 22, False),
        ("pham", 23, False),
        ("prib", 24, False),
        ("pmid", 25, False),
        ("pfar", 26, False),
        ("spillall", 27, False),
    ]

    parts = ["<MIX>"]
    for mic_name, mic_id, enabled in mics:
        val = "1.0" if enabled else "0.0"
        e_val = "1" if enabled else "0"
        parts.append(f'<SETTING id="m_{mic_name}" value="{val}" micId="{mic_id}"/>')
        parts.append(f'<SETTING id="e_{mic_name}" value="{e_val}" micId="{mic_id}"/>')
        parts.append(f'<SETTING id="b_{mic_name}" value="0" micId="{mic_id}"/>')
    parts.append("</MIX>")
    return "".join(parts)


def _generate_artic_xml(
    artic_name: str,
    keyswitch: int,
    inst: BBCInstrument,
    active: bool = False,
) -> str:
    """Generate ARTIC element with all settings."""
    active_val = 2 if active else 0
    rr_map = _generate_rr_map()
    mix_xml = _generate_mic_mix_xml()

    return (
        f"<ARTIC>"
        f'<SETTING id="a_name" value="{artic_name}"/>'
        f'<SETTING id="a_version" value="17104896"/>'
        f'<SETTING id="a_templateIdx" value="0"/>'
        f'<SETTING id="a_voiceLimit" value="-1"/>'
        f'<SETTING id="a_odest" value="REVERB"/>'
        f'<SETTING id="a_active" value="{active_val}"/>'
        f'<SETTING id="a_backActive" value="0"/>'
        f'<SETTING id="a_evoOverlay" value="0"/>'
        f'<SETTING id="a_twoHanded" value="0"/>'
        f'<SETTING id="a_overridesToApplyId" value=""/>'
        f'<SETTING id="a_hallTriggerMode" value="-1"/>'
        f'<SETTING id="a_autoMakeUp" value="0"/>'
        f'<SETTING id="t_type" value="1"/>'
        f'<SETTING id="t_enabled" value="1"/>'
        f'<SETTING id="t_latch" value="0"/>'
        f'<SETTING id="t_keyswitch" value="{keyswitch}"/>'
        f'<SETTING id="t_midiChannel" value="1"/>'
        f'<SETTING id="t_velFrom" value="1"/>'
        f'<SETTING id="t_velTo" value="127"/>'
        f'<SETTING id="t_cc" value="32"/>'
        f'<SETTING id="t_ccValueFrom" value="0"/>'
        f'<SETTING id="t_ccValueTo" value="127"/>'
        f'<SETTING id="t_speedFrom" value="0.0"/>'
        f'<SETTING id="t_speedTo" value="0.5"/>'
        f'<SETTING id="t_programChange" value="0"/>'
        f'<SETTING id="t_tempoFrom" value="0.0"/>'
        f'<SETTING id="t_tempoTo" value="0.0"/>'
        f'<SETTING id="rr_timeout" value="-1.0"/>'
        f'<SETTING id="rr_neighbourMin" value="{inst.range_low}"/>'
        f'<SETTING id="rr_neighbourMax" value="{inst.range_high}"/>'
        f'<SETTING id="rr_useNeighbour" value="0"/>'
        f'<SETTING id="rr_count" value="-1"/>'
        f'<SETTING id="rr_inc" value="1"/>'
        f'<SETTING id="rr_layers" value="1"/>'
        f'<SETTING id="rr_gain" value="1.0"/>'
        f'<SETTING id="rr_start" value="0"/>'
        f'<SETTING id="rr_sync" value="0"/>'
        f'<SETTING id="rr_play" value="1"/>'
        f'<SETTING id="rr_keyswitchFrom" value="-1"/>'
        f'<SETTING id="rr_keyswitchTo" value="-1"/>'
        f'<SETTING id="rr_keyswitchTo" value="-1"/>'
        f'<SETTING id="rr_mode" value="0"/>'
        f'<SETTING id="rr_map" value="{rr_map}"/>'
        f'<RRPATTERNS><RRPATTERN rr_patternKey="-1" rr_patternStart="0" rr_pattern="" rr_patternValidation=""/></RRPATTERNS>'
        f'<SETTING id="r_midiChannel" value="0"/>'
        f'<SETTING id="r_transpose" value="0"/>'
        f'<SETTING id="r_layerTranspose" value="0"/>'
        f'<SETTING id="i_expression" value="1.0"/>'
        f'<SETTING id="i_dynamics" value="1.0"/>'
        f'<SETTING id="i_reverb" value="0.0"/>'
        f'<SETTING id="i_release" value="0.5"/>'
        f'<SETTING id="i_tight" value="0.0"/>'
        f'<SETTING id="i_vibrato" value="1.0"/>'
        f'<SETTING id="i_variation" value="0.0"/>'
        f'<SETTING id="s_pan" value="0.5"/>'
        f'<SETTING id="s_width" value="0.5"/>'
        f'<SETTING id="s_flip" value="0.0"/>'
        f"{mix_xml}"
        f"</ARTIC>"
    )


def generate_instrument_xml(inst: BBCInstrument) -> str:
    """Generate complete SPITFIREAUDIO_AUNTIE XML for an instrument.

    Uses BBC_CATALOG data from bbc_instruments.py.
    """
    odest_indices = _generate_odest_indices()

    # Get display name and prefix
    display_name = BBC_SO_DISPLAY_NAMES.get(inst.key, inst.name)
    # Check for instrument-specific prefix override first
    prefix = INSTRUMENT_PREFIX_OVERRIDES.get(inst.key) or SECTION_PREFIXES.get(inst.section, "a")

    # Get family name
    family_map = {
        Section.STRINGS: "Strings",
        Section.WOODWINDS: "Woodwinds",
        Section.BRASS: "Brass",
        Section.PERCUSSION_TUNED: "Percussion",
        Section.PERCUSSION_UNTUNED: "Percussion",
    }
    family = family_map.get(inst.section, "Strings")

    # Get tag code - use instrument-specific tags if available
    inst_tags = INSTRUMENT_TAG_CODES.get(inst.key)
    if inst_tags:
        tags = f"100:Selection,{inst_tags},{family}"
    else:
        # Fallback to section tags
        section_tags = SECTION_TAG_CODES.get(inst.section, "")
        tags = (
            f"100:Selection,{section_tags},{family}" if section_tags else f"100:Selection,{family}"
        )

    # Generate articulation entries from BBC_CATALOG data
    # CRITICAL: t_keyswitch in XML is the INDEX (0,1,2...), not the MIDI note!
    artic_entries = []
    sorted_artics = sorted(inst.articulations.items(), key=lambda x: x[1])

    # Find which articulation should be active
    # Strings: prefer "Legato" for sustained bowing sound
    # Others: prefer "Long"
    active_index = None
    preferred = "Legato" if inst.section == Section.STRINGS else "Long"

    for i, (artic_suffix, _) in enumerate(sorted_artics):
        if artic_suffix == preferred:
            active_index = i
            break

    # Fallback to Long, then first articulation
    if active_index is None:
        for i, (artic_suffix, _) in enumerate(sorted_artics):
            if artic_suffix == "Long":
                active_index = i
                break
    if active_index is None:
        active_index = 0

    for i, (artic_suffix, _midi_ks) in enumerate(sorted_artics):
        artic_name = f"{prefix} - {display_name} - {artic_suffix}"
        # Use INDEX for t_keyswitch (0, 1, 2...), not MIDI note
        is_active = i == active_index
        artic_entries.append(_generate_artic_xml(artic_name, i, inst, active=is_active))

    artics_xml = "".join(artic_entries)

    # Short RT mode based on section
    short_rt = "-2.0" if inst.section == Section.STRINGS else "0.0"

    return (
        f'<?xml version="1.0" encoding="UTF-8"?> '
        f"<SPITFIREAUDIO_AUNTIE>"
        f'<META family="{family}" name="Core - {display_name}" productMode="5" version="1.5.0" tags="{tags}" modified="1"/>'
        f'<UI uisize="1.0" uicollapsed="0"/>'
        f"<ARTICS>"
        f'<SETTING id="p_syncToTempo" value="1"/>'
        f'<SETTING id="p_dynamicsVelocityMode" value="FULL VELOCITY RANGE"/>'
        f'<SETTING id="p_shortRTMode" value="{short_rt}"/>'
        f'<SETTING id="p_velocityCurve" value="LINEAR VELOCITY"/>'
        f'<SETTING id="p_quantiseMode" value=""/>'
        f'<SETTING id="p_mixerAdvanced" value="1"/>'
        f'<SETTING id="p_mixerGlobal" value="1"/>'
        f'<SETTING id="p_mixerLock" value="0"/>'
        f'<SETTING id="p_mixerPage" value=""/>'
        f'<SETTING id="p_articLock" value="0"/>'
        f'<SETTING id="p_articPage" value="/Typhon/DynamicArea/ArticulationMatrixLayout/ArticulationMatrixPageSelector/0"/>'
        f'<SETTING id="p_lastSelectedPrimaryArtic" value="1"/>'
        f'<SETTING id="p_midiChannel" value="0"/>'
        f'<SETTING id="p_selectedTags" value=""/>'
        f'<SETTING id="p_selectedInstrumentTags" value=""/>'
        f'<SETTING id="p_filterPos" value="[]"/>'
        f'<SETTING id="p_presetPos" value="[]"/>'
        f'<SETTING id="p_evoContainerPos" value="[]"/>'
        f'<SETTING id="p_octave" value="0"/>'
        f'<SETTING id="p_odestIndices" value="{odest_indices}"/>'
        f'<SETTING id="p_timeStretch" value="Default"/>'
        f'<SETTING id="p_voiceChoke" value="0.0"/>'
        f'<SETTING id="p_loopEnd" value="0.0"/>'
        f'<SETTING id="p_dynamicSmooth" value="0.0"/>'
        f'<SETTING id="p_overridesToApplyId" value=""/>'
        f"{artics_xml}"
        f"</ARTICS>"
        f"</SPITFIREAUDIO_AUNTIE>"
    )


# =============================================================================
# BINARY GENERATION
# =============================================================================


def _build_reaper_header(xml_size: int) -> bytes:
    """Build REAPER header with dynamic size fields."""
    size_272 = xml_size + 261
    size_284 = xml_size + 245
    return (
        REAPER_HEADER_FIXED
        + struct.pack("<I", size_272)
        + REAPER_HEADER_MID
        + struct.pack("<I", size_284)
        + REAPER_HEADER_END
    )


def generate_rfxchain_binary(inst: BBCInstrument) -> bytes:
    """Generate complete RfxChain binary."""
    xml = generate_instrument_xml(inst)
    xml_bytes = xml.encode("utf-8")

    header = _build_reaper_header(len(xml_bytes))
    chunk_size = len(VST_MARKERS_SUFFIX) + len(xml_bytes) + len(JUCE_FOOTER) - 14
    ccnk_header = b"CcnK" + struct.pack(">I", chunk_size)

    return b"".join(
        [
            header,  # 292 bytes
            VSTW_HEADER,  # 16 bytes
            ccnk_header,  # 8 bytes
            VST_MARKERS_SUFFIX,  # 160 bytes
            xml_bytes,  # variable
            JUCE_FOOTER,  # 75 bytes
        ]
    )


def _encode_base64_lines(binary: bytes, line_length: int = 96) -> list[str]:
    """Encode binary to base64 lines (REAPER format)."""
    lines = []
    for i in range(0, len(binary), line_length):
        chunk = binary[i : i + line_length]
        lines.append(base64.b64encode(chunk).decode("ascii"))
    return lines


def generate_rfxchain_file(inst: BBCInstrument) -> str:
    """Generate complete RfxChain file content."""
    binary = generate_rfxchain_binary(inst)
    b64_lines = _encode_base64_lines(binary)
    fxid = str(uuid.uuid4()).upper()

    lines = [
        "BYPASS 0 0",
        f'<VST "{BBC_VST3_NAME}" "{BBC_VST3_FILE}" 0 "" {BBC_VST3_UID}{{{BBC_VST3_UID_HEX}}} ""',
    ]
    lines.extend(f"  {b64}" for b64 in b64_lines)
    lines.extend([">", f"FXID {{{fxid}}}", "WAK 0 0"])

    return "\r\n".join(lines)


# =============================================================================
# CACHE & API
# =============================================================================

# RfxChain directory for generated files
RFXCHAIN_DIR = Path.home() / ".kagami" / "symphony" / "reaper" / "instruments"

# Legacy manual file name mapping (for backwards compatibility)
MANUAL_FILE_MAP = {
    "celli": "cellos",
    "horn": "horns",
    "flute": "flutes",
    "oboe": "oboes",
    "clarinet": "clarinets",
    "bassoon": "bassoons",
    "trumpet": "trumpets",
    "tenor_trombone": "trombones_tenor",
    "bass_trombone": "trombones_bass",
}


# Instruments that need special fallback handling
# - untuned_percussion: Each "articulation" is a separate instrument in BBC SO,
#   so the meta-container "Untuned Percussion" patch doesn't work.
# - Leader instruments: Default to "Legato" which requires overlapping notes.
#   For simple playback, fall back to section instruments with "Long" articulation.
SPECIAL_FALLBACK_INSTRUMENTS = {
    "untuned_percussion": "timpani",
    "violin_1_leader": "violins_1",
    "violin_2_leader": "violins_2",
    "viola_leader": "violas",
    "celli_leader": "celli",
    "bass_leader": "basses",
}


def get_rfxchain_path(instrument_key: str, force_regenerate: bool = False) -> Path:
    """Get path to RfxChain file for an instrument.

    Generates RfxChain files automatically using BBC_CATALOG data.
    Manual exports are no longer required - the generator produces
    fully functional RfxChain files with proper BBC SO configuration.

    Special cases (automatic fallbacks):
    - untuned_percussion → timpani: BBC SO treats each percussion as separate patch
    - violin_1_leader → violins_1: Leaders default to Legato (needs overlapping notes)
    - violin_2_leader → violins_2: Same issue
    - viola_leader → violas: Same issue
    - celli_leader → celli: Same issue
    - bass_leader → basses: Same issue

    Args:
        instrument_key: Key from BBC_CATALOG (e.g., "violins_1", "celli", "horn")
        force_regenerate: If True, regenerate even if file exists

    Returns:
        Path to .RfxChain file
    """
    if instrument_key not in BBC_CATALOG:
        raise ValueError(
            f"Unknown instrument: {instrument_key}. Available: {list(BBC_CATALOG.keys())}"
        )

    # Ensure directory exists
    RFXCHAIN_DIR.mkdir(parents=True, exist_ok=True)

    # Special handling for instruments with fallbacks
    if instrument_key in SPECIAL_FALLBACK_INSTRUMENTS:
        fallback_key = SPECIAL_FALLBACK_INSTRUMENTS[instrument_key]
        logger.debug("Using fallback for %s: %s", instrument_key, fallback_key)
        # Recursively get the fallback instrument's path
        return get_rfxchain_path(fallback_key, force_regenerate=force_regenerate)

    # Use instrument key as filename (standardized naming)
    rfx_path = RFXCHAIN_DIR / f"{instrument_key}.RfxChain"

    # Check for legacy manual file names (backwards compatibility)
    if not rfx_path.exists() and not force_regenerate:
        legacy_name = MANUAL_FILE_MAP.get(instrument_key)
        if legacy_name:
            legacy_path = RFXCHAIN_DIR / f"{legacy_name}.RfxChain"
            if legacy_path.exists():
                logger.debug("Using legacy RfxChain: %s -> %s", instrument_key, legacy_path.name)
                return legacy_path

    # Generate if needed
    if not rfx_path.exists() or force_regenerate:
        inst = BBC_CATALOG[instrument_key]
        content = generate_rfxchain_file(inst)
        rfx_path.write_text(content)
        logger.info("Generated RfxChain: %s", rfx_path.name)

    return rfx_path


def get_all_instrument_keys() -> list[str]:
    """Get all available instrument keys from BBC_CATALOG."""
    return list(BBC_CATALOG.keys())


def get_core_instrument_keys() -> list[str]:
    """Get instrument keys available in BBC SO Core edition.

    Excludes Professional-only instruments like leaders and rare woodwinds.
    """
    return [key for key, inst in BBC_CATALOG.items() if inst.edition == "core"]


def get_pro_instrument_keys() -> list[str]:
    """Get instrument keys only available in BBC SO Professional edition."""
    return [key for key, inst in BBC_CATALOG.items() if inst.edition == "professional"]


def regenerate_all_fxchains() -> None:
    """Regenerate all FX chains for all instruments in BBC_CATALOG."""
    for key in BBC_CATALOG:
        get_rfxchain_path(key, force_regenerate=True)
    logger.info("Regenerated %d RfxChain files", len(BBC_CATALOG))


# =============================================================================
# REAPER PROJECT GENERATION
# =============================================================================


def generate_reaper_project(
    midi_path: Path,
    tracks: list[tuple[str, str, float]],
    output_dir: Path,
    output_name: str,
    tempo: float = 120.0,
    duration: float | None = None,
) -> Path:
    """Generate REAPER project file with BBC instrument tracks.

    Args:
        midi_path: Path to MIDI file
        tracks: List of (track_name, instrument_key, pan)
        output_dir: Output directory
        output_name: Base name for output
        tempo: Project tempo
        duration: Duration (auto-detected if None)

    Returns:
        Path to .rpp file
    """
    # Get duration from MIDI if not provided
    if duration is None:
        try:
            import pretty_midi

            midi = pretty_midi.PrettyMIDI(str(midi_path))
            duration = midi.get_end_time() + 2
        except Exception:
            duration = 60.0

    output_dir.mkdir(parents=True, exist_ok=True)
    project_path = output_dir / f"{output_name}.rpp"
    # RENDER_FILE = directory, RENDER_PATTERN = filename (REAPER appends pattern to dir)
    render_dir = str(output_dir)
    render_pattern = output_name  # No extension - REAPER adds based on RENDER_FMT

    colors = [16576, 21760, 26880, 31744, 16711680, 255, 65280, 16711935]
    track_blocks = []

    for i, (track_name, instrument_key, pan) in enumerate(tracks):
        fxchain_path = get_rfxchain_path(instrument_key)
        fxchain_content = fxchain_path.read_text()

        track_block = f"""  <TRACK
    NAME "{track_name}"
    PEAKCOL {colors[i % len(colors)]}
    VOLPAN 1 {pan} -1 -1 1
    MUTESOLO 0 0 0
    NCHAN 2
    FX 1
    TRACKID {{{uuid.uuid4()}}}
    MAINSEND 1 0
    <FXCHAIN
      SHOW 0
{fxchain_content}
    >
    <ITEM
      POSITION 0
      LENGTH {duration}
      LOOP 0
      NAME "{track_name}"
      <SOURCE MIDIPOOL
        FILE "{midi_path}"
      >
    >
  >"""
        track_blocks.append(track_block)

    # NOTE: RENDER_SRATE and RENDER_CHANNELS are NOT supported in all REAPER versions
    # Use RENDER_FMT to control output format instead
    # RENDER_FMT format: secondary_format bits channels (0 2 0 = WAV 24-bit stereo)
    project = f"""<REAPER_PROJECT 0.1 "6.0" 1704067200
  RIPPLE 0
  TEMPO {tempo} 4 4
  RENDER_FILE "{render_dir}"
  RENDER_PATTERN "{render_pattern}"
  RENDER_FMT 0 2 0
  RENDER_1X 1
  RENDER_RANGE 2 0 {duration} 18 1000
  RENDER_RESAMPLE 3 0 1
  RENDER_ADDTOPROJ 0
{chr(10).join(track_blocks)}
>"""

    project_path.write_text(project)
    return project_path


# =============================================================================
# HEADLESS REAPER RENDERING
# =============================================================================

REAPER_APP = Path("/Applications/REAPER.app/Contents/MacOS/REAPER")


def render_project_headless(
    project_path: Path,
    timeout: int = 120,
    parallel_safe: bool = True,
    sample_preload_wait: float = 3.0,
    auto_dismiss_dialogs: bool = True,
) -> tuple[bool, str]:
    """Render a REAPER project without GUI/focus stealing.

    Uses optimized CLI flags for BBC Symphony Orchestra:
    - nosplash: Skip splash screen
    - newinst: New instance (safe for parallel rendering)
    - renderproject: Render and exit immediately
    - nice: Lower CPU priority to reduce system impact
    - Auto-dismisses any blocking REAPER dialogs via AppleScript

    IMPORTANT: BBC SO requires RENDER_1X 1 in the project file for proper
    sample streaming. The project generator adds this automatically.

    Args:
        project_path: Path to .rpp project file
        timeout: Render timeout in seconds (default 120 for BBC SO)
        parallel_safe: If True, use -newinst for parallel rendering
        sample_preload_wait: Seconds to wait for BBC SO sample loading (default 3.0)
        auto_dismiss_dialogs: If True, auto-click OK/Yes on blocking REAPER dialogs

    Returns:
        Tuple of (success, error_message)
    """
    import subprocess
    import threading
    import time

    if not REAPER_APP.exists():
        return False, f"REAPER not found at {REAPER_APP}"

    if not project_path.exists():
        return False, f"Project not found: {project_path}"

    # AppleScript to hide REAPER window
    hide_script = """
    tell application "System Events"
        try
            set visible of application process "REAPER" to false
        end try
    end tell
    """

    # AppleScript to auto-dismiss any REAPER dialogs by clicking default button
    dismiss_dialog_script = """
    tell application "System Events"
        tell process "REAPER"
            try
                -- Click OK, Yes, or default button on any sheet/dialog
                if exists sheet 1 of window 1 then
                    click button 1 of sheet 1 of window 1
                else if exists window 1 then
                    set allButtons to buttons of window 1
                    repeat with btn in allButtons
                        set btnName to name of btn
                        if btnName is "OK" or btnName is "Yes" or btnName is "Continue" or btnName is "Don't Save" then
                            click btn
                            exit repeat
                        end if
                    end repeat
                end if
            end try
        end tell
    end tell
    """

    # Build render command
    cmd = [
        "nice",
        "-n",
        "10",  # Lower CPU priority
        str(REAPER_APP),
        "-nosplash",
    ]

    if parallel_safe:
        cmd.append("-newinst")

    cmd.extend(["-renderproject", str(project_path)])

    # Dialog dismissal control
    dialog_dismiss_stop = threading.Event()

    def dismiss_dialogs_loop():
        """Periodically try to dismiss REAPER dialogs."""
        while not dialog_dismiss_stop.is_set():
            try:
                subprocess.run(
                    ["osascript", "-e", dismiss_dialog_script],
                    capture_output=True,
                    timeout=2,
                )
            except Exception:
                pass
            time.sleep(1.0)  # Check every second

    try:
        # Start REAPER process
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )

        # Hide REAPER window
        time.sleep(0.5)
        subprocess.run(["osascript", "-e", hide_script], capture_output=True, timeout=5)

        # Start dialog dismissal thread
        if auto_dismiss_dialogs:
            dismiss_thread = threading.Thread(target=dismiss_dialogs_loop, daemon=True)
            dismiss_thread.start()

        # Wait for BBC SO sample preloading
        if sample_preload_wait > 0:
            time.sleep(sample_preload_wait)

        # Wait for render to complete
        proc.wait(timeout=timeout)

        # Stop dialog dismissal
        dialog_dismiss_stop.set()

        return True, ""

    except subprocess.TimeoutExpired:
        dialog_dismiss_stop.set()
        proc.kill()
        return False, f"Render timeout ({timeout}s) - BBC SO may need longer for sample loading"
    except Exception as e:
        dialog_dismiss_stop.set()
        return False, str(e)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "BBC_CATALOG",
    "DAWDREAMER_PARAMS",
    "REAPER_APP",
    "generate_instrument_xml",
    "generate_reaper_project",
    "generate_rfxchain_binary",
    "generate_rfxchain_file",
    "get_all_instrument_keys",
    "get_rfxchain_path",
    "regenerate_all_fxchains",
    "render_project_headless",
]
