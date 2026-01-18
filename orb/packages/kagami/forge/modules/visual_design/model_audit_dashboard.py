from __future__ import annotations

"""Render PNG dashboard for K os model audit

Reads `style_enforced_output/model_audit.json` and renders a 1920x1080 PNG
showing selected top picks and all models with telemetry, following style
guidance (AA contrast, neutral cards, clear hierarchy).
"""
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

_OUTPUT_DIR = Path("style_enforced_output")
_INPUT_JSON = _OUTPUT_DIR / "model_audit.json"


def _load_fonts() -> tuple[ImageFont.FreeTypeFont, ImageFont.FreeTypeFont, ImageFont.FreeTypeFont]:
    # Best-effort: use system fonts; fallback to PIL default
    try:
        title = ImageFont.truetype("/System/Library/Fonts/SFNS.ttf", 36)
        body = ImageFont.truetype("/System/Library/Fonts/SFNS.ttf", 20)
        mono = ImageFont.truetype("/System/Library/Fonts/SFNSMono.ttf", 16)
        return title, body, mono
    except Exception:
        return (  # type: ignore[return-value]
            ImageFont.load_default(),
            ImageFont.load_default(),
            ImageFont.load_default(),
        )


def _quality_color(q: str) -> tuple[int, int, int]:
    if q == "good":
        return (32, 158, 116)  # green
    if q == "mixed":
        return (241, 196, 15)  # yellow
    return (231, 76, 60)  # red


def _chip(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int, int, int],
    text: str,
    fill: tuple[int, int, int] = (230, 230, 230),
    text_color: tuple[int, int, int] = (30, 30, 30),
    font: ImageFont.FreeTypeFont | None = None,
) -> None:
    x0, y0, x1, y1 = xy
    r = (y1 - y0) // 2
    draw.rounded_rectangle(xy, radius=r, fill=fill, outline=None)
    if font is not None:
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
        except Exception:
            # Fallback for older Pillow
            try:
                tw, th = font.getsize(text)  # type: ignore[attr-defined]
            except Exception:
                tw, th = (len(text) * 8, 16)
        tx = x0 + (x1 - x0 - tw) // 2
        ty = y0 + (y1 - y0 - th) // 2 - 1
        draw.text((tx, ty), text, fill=text_color, font=font)


def render_model_audit_dashboard_png(
    outfile: str = "style_enforced_output/model_routing_dashboard.png",
    width: int = 1920,
    height: int = 1080,
) -> str:
    """Render dashboard PNG and return the file path."""
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {}
    if _INPUT_JSON.exists():
        try:
            data = json.loads(_INPUT_JSON.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            data = {}

    img = Image.new("RGB", (width, height), (248, 249, 251))
    draw = ImageDraw.Draw(img)
    title_font, body_font, mono_font = _load_fonts()

    # Header
    title = "K os Model Routing Dashboard"
    subtitle = data.get("env", {})
    subtitle_text = f"OLLAMA_HOST: {subtitle.get('OLLAMA_HOST', 'n/a')}  •  ollama: {subtitle.get('ollama_version', '')}"
    draw.text((40, 30), title, fill=(20, 20, 20), font=title_font)
    draw.text((40, 80), subtitle_text, fill=(90, 90, 90), font=body_font)

    # Columns
    margin = 40
    col_w = (width - 3 * margin) // 2
    left_x = margin
    right_x = margin * 2 + col_w
    y = 130

    # Left: Top picks
    draw.text((left_x, y), "Selected (Top Picks)", fill=(30, 30, 30), font=body_font)
    y += 10
    draw.line([(left_x, y + 28), (left_x + col_w, y + 28)], fill=(220, 220, 220), width=2)
    y += 40

    selected: list[str] = data.get("selected", []) or []
    telemetry: dict[str, Any] = data.get("telemetry", {}) or {}

    card_h = 90
    for name in selected:
        t = telemetry.get(name, {})
        q = str(t.get("quality", "poor"))
        p50 = int(t.get("p50", 0))
        p95 = int(t.get("p95", 0))
        wc = int(t.get("avg_words", 0))
        excerpt = str(t.get("excerpt", "")).replace("\n", "  ")
        card_y0 = y
        card_y1 = y + card_h
        draw.rounded_rectangle(
            (left_x, card_y0, left_x + col_w, card_y1), radius=12, fill=(255, 255, 255)
        )
        # status dot
        color = _quality_color(q)
        draw.ellipse((left_x + 16, card_y0 + 16, left_x + 32, card_y0 + 32), fill=color)
        draw.text((left_x + 44, card_y0 + 12), name, fill=(25, 25, 25), font=body_font)
        # telemetry line
        tele = f"p50 {p50} ms • p95 {p95} ms • ~{wc} words"
        draw.text((left_x + 44, card_y0 + 44), tele, fill=(90, 90, 90), font=mono_font)
        # chip
        _chip(
            draw,
            (left_x + col_w - 140, card_y0 + 18, left_x + col_w - 20, card_y0 + 44),
            "selected",
            fill=(225, 245, 233),
            text_color=(25, 90, 60),
            font=mono_font,
        )
        # excerpt (one line clipped)
        excerpt = (excerpt[:80] + "…") if len(excerpt) > 80 else excerpt
        draw.text((left_x + 44, card_y0 + 64), excerpt, fill=(60, 60, 60), font=mono_font)
        y += card_h + 16

    # Right: All models sorted by (quality then p50); reflect current selection policy
    y2 = 130
    draw.text((right_x, y2), "All Models", fill=(30, 30, 30), font=body_font)
    draw.line([(right_x, y2 + 28), (right_x + col_w, y2 + 28)], fill=(220, 220, 220), width=2)
    y2 += 40

    all_models = data.get("reconciled_models", []) or []

    # Sort by (quality rank, p50)
    def q_rank(q: str) -> int:
        return {"good": 0, "mixed": 1, "poor": 2}.get(q, 3)

    sortable = []
    for n in all_models:
        t = telemetry.get(n, {})
        q = str(t.get("quality", "poor"))
        p50 = int(t.get("p50", 0))
        # preference rank as tertiary tie-break for transparency with selection logic
        pref_rank = 999
        try:
            from .model_audit import _preference_rank

            pref_rank = _preference_rank(n)
        except Exception:
            pass
        sortable.append((q_rank(q), p50, pref_rank, n))
    sortable.sort()

    for _, _, _, name in sortable[:12]:  # show top 12 to avoid clutter
        t = telemetry.get(name, {})
        q = str(t.get("quality", "poor"))
        p50 = int(t.get("p50", 0))
        p95 = int(t.get("p95", 0))
        wc = int(t.get("avg_words", 0))
        card_y0 = y2
        card_y1 = y2 + card_h
        draw.rounded_rectangle(
            (right_x, card_y0, right_x + col_w, card_y1),
            radius=12,
            fill=(255, 255, 255),
        )
        color = _quality_color(q)
        draw.ellipse((right_x + 16, card_y0 + 16, right_x + 32, card_y0 + 32), fill=color)
        draw.text((right_x + 44, card_y0 + 12), name, fill=(25, 25, 25), font=body_font)
        tele = f"p50 {p50} ms • p95 {p95} ms • ~{wc} words"
        draw.text((right_x + 44, card_y0 + 44), tele, fill=(90, 90, 90), font=mono_font)
        chip_text = "selected" if name in selected else "deprioritized"
        chip_fill = (225, 245, 233) if name in selected else (235, 235, 235)
        chip_color = (25, 90, 60) if name in selected else (70, 70, 70)
        _chip(
            draw,
            (right_x + col_w - 170, card_y0 + 18, right_x + col_w - 20, card_y0 + 44),
            chip_text,
            fill=chip_fill,
            text_color=chip_color,
            font=mono_font,
        )
        y2 += card_h + 16

    # Empty state
    if not data.get("reconciled_models"):
        info = "No local models discovered. Ensure Ollama is installed and models are pulled."
        draw.text((left_x, height - 80), info, fill=(100, 100, 100), font=body_font)

    # Footer status line (single line)
    # Reflect the actual environment to avoid placeholder/fabricated ENV text
    try:
        import os as _os

        _env = (_os.getenv("ENVIRONMENT") or _os.getenv("ENV") or "dev").lower()
    except Exception:
        _env = "dev"
    footer = f"kagami@{_env} — Model audit visualization"
    draw.rectangle((0, height - 44, width, height), fill=(240, 240, 240))
    draw.text((40, height - 36), footer, fill=(60, 60, 60), font=mono_font)

    out_path = Path(outfile)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, format="PNG", compress_level=9)
    return str(out_path)


__all__ = ["render_model_audit_dashboard_png"]
