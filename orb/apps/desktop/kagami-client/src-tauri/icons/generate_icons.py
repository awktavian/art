#!/usr/bin/env python3
"""
Kagami menu bar icon - 鏡 kanji as SVG path.
Renders cleanly at 16px as a template icon.
"""

import subprocess
from pathlib import Path

ICONS_DIR = Path(__file__).parent

# 鏡 kanji simplified for 16px - recognizable mirror radical (金 + 竟)
# This is a stylized version that reads as 鏡 but works at small sizes
KAGAMI_ICON = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16">
  <!-- Simplified 鏡 kanji for menu bar -->
  <!-- Left side: 金 radical simplified -->
  <path d="M2 3 L4 3 L4 5 L2 5 Z" fill="black"/>
  <path d="M3 5 L3 9" stroke="black" stroke-width="1.2" stroke-linecap="round"/>
  <path d="M2 7 L4 7" stroke="black" stroke-width="1"/>
  <path d="M1.5 9 L4.5 9" stroke="black" stroke-width="1.2" stroke-linecap="round"/>

  <!-- Right side: 竟 simplified as mirror frame -->
  <rect x="6" y="2" width="8" height="12" rx="1" fill="none" stroke="black" stroke-width="1.3"/>
  <line x1="6" y1="6" x2="14" y2="6" stroke="black" stroke-width="1"/>
  <line x1="10" y1="6" x2="10" y2="14" stroke="black" stroke-width="1"/>

  <!-- Reflection dot in mirror -->
  <circle cx="10" cy="10" r="1.5" fill="black"/>
</svg>"""

# Disconnected - same but dashed/faded
KAGAMI_DISCONNECTED = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16">
  <g opacity="0.4">
    <path d="M2 3 L4 3 L4 5 L2 5 Z" fill="black"/>
    <path d="M3 5 L3 9" stroke="black" stroke-width="1.2" stroke-linecap="round"/>
    <path d="M2 7 L4 7" stroke="black" stroke-width="1"/>
    <path d="M1.5 9 L4.5 9" stroke="black" stroke-width="1.2" stroke-linecap="round"/>
    <rect x="6" y="2" width="8" height="12" rx="1" fill="none" stroke="black" stroke-width="1.3"/>
    <line x1="6" y1="6" x2="14" y2="6" stroke="black" stroke-width="1"/>
    <line x1="10" y1="6" x2="10" y2="14" stroke="black" stroke-width="1"/>
  </g>
</svg>"""

# Alert - with notification badge
KAGAMI_ALERT = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16">
  <path d="M2 3 L4 3 L4 5 L2 5 Z" fill="black"/>
  <path d="M3 5 L3 9" stroke="black" stroke-width="1.2" stroke-linecap="round"/>
  <path d="M2 7 L4 7" stroke="black" stroke-width="1"/>
  <path d="M1.5 9 L4.5 9" stroke="black" stroke-width="1.2" stroke-linecap="round"/>
  <rect x="6" y="2" width="8" height="12" rx="1" fill="none" stroke="black" stroke-width="1.3"/>
  <line x1="6" y1="6" x2="14" y2="6" stroke="black" stroke-width="1"/>
  <line x1="10" y1="6" x2="10" y2="14" stroke="black" stroke-width="1"/>
  <circle cx="10" cy="10" r="1.5" fill="black"/>
  <!-- Alert badge -->
  <circle cx="14" cy="2" r="2.5" fill="black"/>
</svg>"""

# App icon - larger, with styling
APP_ICON = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#1e293b"/>
      <stop offset="100%" style="stop-color:#0f172a"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="120" height="120" rx="24" fill="url(#bg)"/>

  <!-- 鏡 kanji centered, larger -->
  <g transform="translate(24, 24) scale(5)">
    <path d="M2 3 L4 3 L4 5 L2 5 Z" fill="#e2e8f0"/>
    <path d="M3 5 L3 9" stroke="#e2e8f0" stroke-width="1.2" stroke-linecap="round"/>
    <path d="M2 7 L4 7" stroke="#e2e8f0" stroke-width="1"/>
    <path d="M1.5 9 L4.5 9" stroke="#e2e8f0" stroke-width="1.2" stroke-linecap="round"/>
    <rect x="6" y="2" width="8" height="12" rx="1" fill="none" stroke="#e2e8f0" stroke-width="1.3"/>
    <line x1="6" y1="6" x2="14" y2="6" stroke="#e2e8f0" stroke-width="1"/>
    <line x1="10" y1="6" x2="10" y2="14" stroke="#e2e8f0" stroke-width="1"/>
    <circle cx="10" cy="10" r="1.5" fill="#e2e8f0"/>
  </g>
</svg>"""


def svg_to_png(svg: str, path: Path, size: int):
    svg_path = path.with_suffix(".svg")
    svg_path.write_text(svg)
    try:
        subprocess.run(
            ["rsvg-convert", "-w", str(size), "-h", str(size), "-o", str(path), str(svg_path)],
            check=True,
            capture_output=True,
        )
        svg_path.unlink()
        return True
    except:
        try:
            import cairosvg

            cairosvg.svg2png(
                bytestring=svg.encode(), write_to=str(path), output_width=size, output_height=size
            )
            svg_path.unlink()
            return True
        except:
            print(f"  ⚠️ Could not convert {path.name}")
            return False


def main():
    print("Generating 鏡 icons...")

    icons = [
        ("trayTemplate.png", KAGAMI_ICON, 16),
        ("trayTemplate@2x.png", KAGAMI_ICON, 32),
        ("tray-disconnectedTemplate.png", KAGAMI_DISCONNECTED, 16),
        ("tray-disconnectedTemplate@2x.png", KAGAMI_DISCONNECTED, 32),
        ("tray-alertTemplate.png", KAGAMI_ALERT, 16),
        ("tray-alertTemplate@2x.png", KAGAMI_ALERT, 32),
        ("32x32.png", APP_ICON, 32),
        ("128x128.png", APP_ICON, 128),
        ("128x128@2x.png", APP_ICON, 256),
    ]

    for name, svg, size in icons:
        print(f"  {name}")
        svg_to_png(svg, ICONS_DIR / name, size)

    # Generate icns
    subprocess.run(
        [
            "sips",
            "-s",
            "format",
            "icns",
            str(ICONS_DIR / "128x128@2x.png"),
            "--out",
            str(ICONS_DIR / "icon.icns"),
        ],
        capture_output=True,
    )

    print("✓ Done")


if __name__ == "__main__":
    main()
