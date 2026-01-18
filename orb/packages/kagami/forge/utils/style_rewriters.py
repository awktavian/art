from __future__ import annotations

#!/usr/bin/env python3
"""
Centralized style prompt rewriters and sanitizers for K os content types.

Responsibilities:
- Parse machine-readable directives from docs/style/STYLE_GUIDE.md when present
- Build style prompts and core constraint lines per content type
- Sanitize final prompts to avoid anatomy/negative phrasing leakage for non-character

This module consolidates logic previously embedded in the style pipeline so
that all generators share consistent, audited behavior.
"""
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MACHINE_READABLE_HEADER = "## Machine‑Readable Directives"
logger = logging.getLogger(__name__)


def _extract_json_block(md_text: str) -> dict[str, Any]:
    """Extract the first fenced JSON block under the machine-readable header.

    The expected format in STYLE_GUIDE.md is:
    ## Machine‑Readable Directives
    ```json
    { ... }
    ```
    """
    if not md_text:
        return {}
    header_index = md_text.find(MACHINE_READABLE_HEADER)
    if header_index == -1:
        return {}
    fence_index = md_text.find("```json", header_index)
    if fence_index == -1:
        return {}
    start = fence_index + len("```json")
    end = md_text.find("```", start)
    if end == -1:
        return {}
    block = md_text[start:end].strip()
    try:
        data = json.loads(block)
        if isinstance(data, dict):
            return data
    except Exception:
        return {}
    return {}


def get_machine_readable_directives(
    guide_path: Path | str = "docs/style/STYLE_GUIDE.md",
) -> dict[str, Any]:
    """Load machine-readable directives from the style guide if present.

    Returns a dict[str, Any] with keys: version, content_types: { character|ui_component|brand_tile: { ... } }
    Missing or malformed data returns {}.
    """
    try:
        path = Path(guide_path)
        if not path.exists():
            logger.debug("Style rewriters: guide not found at %s", guide_path)
            return {}
        text = path.read_text(encoding="utf-8", errors="ignore")
        data = _extract_json_block(text)
        if isinstance(data, dict) and "content_types" in data:
            logger.debug(
                "Style rewriters: loaded machine-readable directives (version=%s) for types=%s",
                data.get("version"),
                ",".join(sorted(data.get("content_types", {}).keys())),
            )
            return data
    except Exception:
        logger.exception("Style rewriters: failed to parse directives from guide")
        return {}
    return {}


def _compose_lines_from_directives(entry: dict[str, Any]) -> tuple[str, list[str]]:
    """Compose a compact style_prompt and core_lines from a directives entry."""
    style_prompt_parts: list[str] = []
    core_lines: list[str] = []

    # Optional keys per our guide schema
    background = str(entry.get("background", "")).strip()
    notes = str(entry.get("notes", "")).strip()
    core: list[str] = list(entry.get("core", [])) if isinstance(entry.get("core", []), list) else []

    if background:
        style_prompt_parts.append(f"Background: {background}")
    if notes:
        style_prompt_parts.append(notes)
    if core:
        core_lines.extend(core)

    style_prompt = " ".join(style_prompt_parts).strip()
    return style_prompt, core_lines


@dataclass
class BuiltPrompts:
    style_prompt: str
    core_lines: list[str]


async def build_prompts_for_content_type(
    *,
    content_type: str,
    mascot_data: dict[str, Any],
    style_engine: Any | None,
    guide_path: Path | str = "docs/style/STYLE_GUIDE.md",
) -> BuiltPrompts:
    """Return style_prompt and core_lines for the given content_type.

    Prefers machine-readable directives from the style guide. Falls back to
    previous heuristics and style engine for character type.
    """
    directives = get_machine_readable_directives(guide_path)
    entry = None
    if directives:
        entry = (
            directives.get("content_types", {}).get(content_type, {})
            if isinstance(directives.get("content_types"), dict)
            else None
        )

    if isinstance(entry, dict) and entry:
        style_prompt, core_lines = _compose_lines_from_directives(entry)
        logger.info(
            "Style rewriters: using directives (content_type=%s, style_prompt=%s, core_count=%d)",
            content_type,
            bool(style_prompt),
            len(core_lines),
        )
    else:
        # Fallback behavior mirrors prior implementation
        logger.info("Style rewriters: using fallback rules (content_type=%s)", content_type)
        if content_type == "character":
            if style_engine is None or not hasattr(style_engine, "generate_style_prompt"):
                style_prompt = (
                    "K os Character Style: proportions/eyes/materials/lighting; white background"
                )
            else:
                style_prompt = await style_engine.generate_style_prompt(mascot_data)
            core_lines = [
                "Proportions: Head 45% / Body 35% / Limbs 20%",
                "Eyes: round pupils, triple highlights (~30% head)",
                "Surface: velvet-matte; gentle subsurface; soft rim light",
                f"Palette: Primary {mascot_data.get('color_palette', {}).get('primary', 'purple')}, Secondary {mascot_data.get('color_palette', {}).get('secondary', 'blue')}",
                "Background: pure white; even soft studio lighting; no shadows",
            ]
        elif content_type == "ui_component":
            style_prompt = (
                "K os UI Design: flat 2D, AA contrast, neutral cards/panels, "
                "soft rim for depth, pure white or transparent backgrounds, even lighting. "
                "No anatomy, faces, emoji, or iconography unless explicitly requested."
            )
            core_lines = [
                "UI component: flat 2D status ribbon/panel/button; anatomy‑free",
                "AA contrast; neutral backgrounds; subtle depth only via soft rim; icon‑free by default",
                "Motion cues ≤250ms; render static",
                "Background: white or transparent only; even lighting",
            ]
        elif content_type == "brand_tile":
            style_prompt = (
                "K os Brand Tiles: geometric/cosmic gradients, clean neutrals, focal anchor, minimal composition, white background; "
                "strictly graphic — no faces, emoji, clocks, or UI icons; no text."
            )
            core_lines = [
                "Brand tile: geometric/cosmic gradients; clean neutrals",
                "Legible focal anchor; anatomy‑free; icon‑free; emoji‑free; text‑free",
                "Background: pure white; soft shadows only if needed",
            ]
        elif content_type == "ar_overlay":
            # AR overlay assets used in world augmentations; anatomy‑free, legible, stable
            style_prompt = (
                "K os AR Overlay: anatomy‑free, high legibility on complex backgrounds, "
                "respect safe zones and stable horizon; pure graphic elements only; white/transparent base."
            )
            core_lines = [
                "Overlay: labels/icons/panels only; anatomy‑free",
                "Legibility on complex backgrounds (add soft halo if needed)",
                "Respect safe zones; avoid motion; render static",
                "Background: white or transparent only; even lighting",
            ]
        elif content_type == "world":
            # Prompts sent to world generator (panorama/scene). Avoid anatomy; enforce stability and composition.
            style_prompt = (
                "K os World Style: stable horizon, readable composition, clean neutrals with subtle gradients; "
                "optimize for panoramic/scene synthesis; no character anatomy."
            )
            core_lines = [
                "Scene: panoramic/room/environment; anatomy‑free",
                "Maintain stable horizon; avoid extreme perspective that harms legibility",
                "Use clean neutrals; subtle gradients; clear focal areas",
                "Ensure readability for later AR overlays",
            ]
        elif content_type == "motion":
            # Text-to-motion prompts should bias to clean, physically plausible, readable motion descriptions
            style_prompt = (
                "K os Motion Style: clear, physically plausible actions; readable intent; "
                "avoid character anatomy descriptors; describe action succinctly."
            )
            core_lines = [
                "Motion: natural, stable, readable",
                "Describe action and tempo concisely (e.g., walk forward at calm pace)",
                "Avoid camera/visual adjectives; focus on kinematics",
            ]
        elif content_type == "facial":
            # Facial animation prompts should inherit eye/proportion intent but avoid visual render language
            style_prompt = (
                "K os Facial Style: expressive yet readable; asymmetric micro-gestures; "
                "eyes anchor intent; velvet-matte material context only for consistency; no render jargon."
            )
            core_lines = [
                "Expressions: joy, curiosity, empathy; subtle asymmetry",
                "Keep durations and intensities within natural ranges",
                "Prioritize gaze anchoring and eyebrow/mouth interplay",
            ]
        else:
            # Unknown type -> safest graphic-only defaults
            style_prompt = (
                "K os Graphic Style: clean, minimal, anatomy‑free; white/transparent background"
            )
            core_lines = [
                "Graphic: anatomy‑free; text‑free",
                "Background: white or transparent",
            ]

    # Character-specific augmentations
    if content_type == "character":
        if bool(mascot_data.get("orthographic", False)):
            view = str(mascot_data.get("view", "front"))
            pose = str(mascot_data.get("pose", "A-pose"))
            core_lines.insert(
                1,
                f"View: {view} orthographic; Pose: {pose} (full body incl. feet, limb separation visible)",
            )

    return BuiltPrompts(style_prompt=style_prompt, core_lines=core_lines)


def sanitize_final_prompt_for_content_type(text: str, *, content_type: str) -> str:
    """Sanitize the final enforced prompt to avoid unwanted leakage.

    For non-character content types we remove disallowed terms inline instead of
    dropping entire lines, so that allowed constraints on the same line remain.
    """
    if content_type == "character" or not text:
        return text

    out = text

    # Remove negative phrasing cues (keep the rest of the sentence intact)
    neg_tokens = [
        "avoid",
        "must not",
        "must-not",
        "must‑not",
        "no ",
        "no‑",
        "no—",
    ]
    for tok in neg_tokens:
        out = re.sub(re.escape(tok), "", out, flags=re.IGNORECASE)

    # Terms to remove for non-character content
    drop_terms = [
        "glassy specular",
        "species",
        "orthographic",
        "pose",
        "pupils",
        "eyes",
        "mouth",
        "nose",
        "smile",
        "smiley",
        "emoji",
        "face",
        "Head 45%",
        "Body 35%",
        "Limbs 20%",
        "line-of-action",
        "mascot",
        "character",
        "anatomy",
        "hands",
        "limbs",
        "clock",
        "watch",
        "timepiece",
        "dial",
    ]
    for term in drop_terms:
        out = re.sub(re.escape(term), "", out, flags=re.IGNORECASE)

    # Normalize leftover punctuation/whitespace like duplicate semicolons, "and ;", etc.
    out = re.sub(r"\s*;\s*;", "; ", out)
    out = re.sub(r"\s*,\s*,", ", ", out)
    out = re.sub(r"\s*(?:,|and)\s*;", "; ", out, flags=re.IGNORECASE)
    out = re.sub(r"\s*;\s*", "; ", out)
    out = re.sub(r"\s{2,}", " ", out)
    out = out.replace(" ;", ";").strip()

    # Remove accidental double spaces around commas
    out = re.sub(r"\s*,\s*", ", ", out)
    return out
