#!/usr/bin/env python3
"""
Kagami Design Token Generator

Generates platform-specific design token files from a single source of truth.

Outputs:
- CSS custom properties (Desktop/Web)
- Swift extensions (iOS/watchOS/visionOS)
- Kotlin objects (Android/Wear OS)
- Rust constants (Hub)

Usage:
    python generate.py [--output-dir <path>]
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

# Default output paths relative to project root
PROJECT_ROOT = Path(__file__).parent.parent.parent
OUTPUT_PATHS = {
    "css": PROJECT_ROOT / "apps/desktop/kagami-client/src/css/design-tokens.generated.css",
    "swift": PROJECT_ROOT / "apps/ios/kagami-ios/KagamiIOS/DesignTokens.generated.swift",
    "kotlin": PROJECT_ROOT
    / "apps/android/kagami-android/app/src/main/java/com/kagami/ui/theme/DesignTokens.generated.kt",
    "rust": PROJECT_ROOT / "apps/hub/kagami-hub/src/design_tokens.generated.rs",
}


def load_tokens() -> dict[str, Any]:
    """Load all token JSON files."""
    tokens_dir = Path(__file__).parent
    return {
        "colors": json.loads((tokens_dir / "colors.json").read_text()),
        "motion": json.loads((tokens_dir / "motion.json").read_text()),
        "spacing": json.loads((tokens_dir / "spacing.json").read_text()),
        "effects": json.loads((tokens_dir / "effects.json").read_text()),
    }


# =============================================================================
# CSS GENERATOR
# =============================================================================


def generate_css(tokens: dict[str, Any]) -> str:
    """Generate CSS custom properties."""
    lines = [
        "/**",
        " * Kagami Design Tokens — Auto-generated",
        f" * Generated: {datetime.now().isoformat()}",
        " * DO NOT EDIT MANUALLY — Edit config/design-tokens/*.json instead",
        " */",
        "",
        ":root {",
    ]

    # Void palette
    lines.append("  /* Void Palette */")
    for name, value in tokens["colors"]["void"].items():
        if name != "description":
            lines.append(f"  --kagami-{name}: {value};")

    # Colony colors
    lines.append("")
    lines.append("  /* Colony Colors (Octonion Basis) */")
    for name, data in tokens["colors"]["colony"].items():
        if isinstance(data, dict):
            lines.append(f"  --kagami-{name}: {data['hex']};")
            r, g, b = data["rgb"]
            lines.append(f"  --kagami-{name}-rgb: {r}, {g}, {b};")

    # Status colors
    lines.append("")
    lines.append("  /* Status Colors */")
    for name, value in tokens["colors"]["status"].items():
        if name != "description":
            lines.append(f"  --kagami-status-{name}: {value};")

    # Text colors
    lines.append("")
    lines.append("  /* Text Colors */")
    text = tokens["colors"]["text"]
    lines.append(f"  --kagami-text-primary: {text['primary']};")
    lines.append(f"  --kagami-text-secondary: rgba(245, 240, 232, {text['secondary']['opacity']});")
    lines.append(f"  --kagami-text-tertiary: rgba(245, 240, 232, {text['tertiary']['opacity']});")

    # Motion - Durations
    lines.append("")
    lines.append("  /* Motion — Durations (ms) */")
    for name, value in tokens["motion"]["duration"].items():
        if name != "description":
            lines.append(f"  --kagami-dur-{name}: {value}ms;")

    # Motion - Easings
    lines.append("")
    lines.append("  /* Motion — Easings */")
    for name, data in tokens["motion"]["easing"].items():
        if isinstance(data, dict):
            b = data["bezier"]
            lines.append(f"  --kagami-ease-{name}: cubic-bezier({b[0]}, {b[1]}, {b[2]}, {b[3]});")

    # Spacing
    lines.append("")
    lines.append("  /* Spacing (8px grid) */")
    for name, value in tokens["spacing"]["spacing"].items():
        if name != "description":
            lines.append(f"  --kagami-space-{name}: {value}px;")

    # Radius
    lines.append("")
    lines.append("  /* Border Radius */")
    for name, value in tokens["spacing"]["radius"].items():
        if name != "description":
            unit = "" if value == 9999 else "px"
            lines.append(f"  --kagami-radius-{name}: {value}{unit};")

    # Glass effects
    lines.append("")
    lines.append("  /* Glass Effects */")
    glass = tokens["effects"]["glass"]
    for name, value in glass["blur"].items():
        lines.append(f"  --kagami-blur-{name}: {value}px;")
    lines.append(f"  --kagami-glass-opacity: {glass['transparency']['default']};")

    # Spectral effects
    lines.append("")
    lines.append("  /* Spectral Effects */")
    spectral = tokens["effects"]["spectral"]
    lines.append(f"  --kagami-shimmer-dur: {spectral['shimmer']['duration']}ms;")
    lines.append(f"  --kagami-spectral-border-dur: {spectral['border']['duration']}ms;")

    lines.append("}")
    lines.append("")

    return "\n".join(lines)


# =============================================================================
# SWIFT GENERATOR
# =============================================================================


def generate_swift(tokens: dict[str, Any]) -> str:
    """Generate Swift extensions for iOS/watchOS/visionOS."""
    lines = [
        "//",
        "// DesignTokens.generated.swift — Kagami Design System",
        f"// Generated: {datetime.now().isoformat()}",
        "// DO NOT EDIT MANUALLY — Edit config/design-tokens/*.json instead",
        "//",
        "",
        "import SwiftUI",
        "",
        "// MARK: - Color Tokens",
        "",
        "extension Color {",
    ]

    # Void palette
    lines.append("    // Void Palette")
    for name, value in tokens["colors"]["void"].items():
        if name != "description":
            swift_name = name[0].lower() + name[1:] if name[0].isupper() else name
            lines.append(f'    static let {swift_name} = Color(hex: "{value}")')

    # Colony colors
    lines.append("")
    lines.append("    // Colony Colors (Octonion Basis e₁-e₇)")
    for name, data in tokens["colors"]["colony"].items():
        if isinstance(data, dict):
            lines.append(
                f'    static let {name} = Color(hex: "{data["hex"]}")  // {data["basis"]} — {data["name"]}'
            )

    # Status colors
    lines.append("")
    lines.append("    // Status Colors")
    for name, value in tokens["colors"]["status"].items():
        if name != "description":
            lines.append(f'    static let status{name.capitalize()} = Color(hex: "{value}")')

    # Text colors
    lines.append("")
    lines.append("    // Text Colors")
    text = tokens["colors"]["text"]
    lines.append(f'    static let textPrimary = Color(hex: "{text["primary"]}")')
    lines.append(
        f'    static let textSecondary = Color(hex: "{text["secondary"]["base"]}").opacity({text["secondary"]["opacity"]})'
    )
    lines.append(
        f'    static let textTertiary = Color(hex: "{text["tertiary"]["base"]}").opacity({text["tertiary"]["opacity"]})'
    )

    lines.append("}")
    lines.append("")

    # Motion tokens
    lines.append("// MARK: - Motion Tokens")
    lines.append("")
    lines.append("enum KagamiDuration {")
    for name, value in tokens["motion"]["duration"].items():
        if name != "description":
            lines.append(f"    static let {name}: Double = {value / 1000}")
    lines.append("}")
    lines.append("")

    lines.append("enum KagamiEasing {")
    for name, data in tokens["motion"]["easing"].items():
        if isinstance(data, dict):
            b = data["bezier"]
            lines.append(
                f"    static let {name} = Animation.timingCurve({b[0]}, {b[1]}, {b[2]}, {b[3]}, duration: KagamiDuration.normal)"
            )
    lines.append("}")
    lines.append("")

    # Spacing tokens
    lines.append("// MARK: - Spacing Tokens")
    lines.append("")
    lines.append("enum KagamiSpacing {")
    for name, value in tokens["spacing"]["spacing"].items():
        if name != "description":
            lines.append(f"    static let {name}: CGFloat = {value}")
    lines.append("}")
    lines.append("")

    lines.append("enum KagamiRadius {")
    for name, value in tokens["spacing"]["radius"].items():
        if name != "description":
            lines.append(f"    static let {name}: CGFloat = {value}")
    lines.append("}")
    lines.append("")

    # Effect tokens
    lines.append("// MARK: - Effect Tokens")
    lines.append("")
    lines.append("enum KagamiGlass {")
    glass = tokens["effects"]["glass"]
    for name, value in glass["blur"].items():
        lines.append(f"    static let blur{name.capitalize()}: CGFloat = {value}")
    lines.append(f"    static let defaultOpacity: Double = {glass['transparency']['default']}")
    lines.append("}")
    lines.append("")

    lines.append("enum KagamiSpectral {")
    spectral = tokens["effects"]["spectral"]
    lines.append(f"    static let phaseCount: Int = {spectral['phases']['count']}")
    lines.append(
        f"    static let shimmerDuration: Double = {spectral['shimmer']['duration'] / 1000}"
    )
    lines.append(
        f"    static let shimmerHoverOpacity: Double = {spectral['shimmer']['opacity']['hover']}"
    )
    lines.append(f"    static let borderDuration: Double = {spectral['border']['duration'] / 1000}")
    lines.append("}")
    lines.append("")

    return "\n".join(lines)


# =============================================================================
# KOTLIN GENERATOR
# =============================================================================


def generate_kotlin(tokens: dict[str, Any]) -> str:
    """Generate Kotlin objects for Android/Wear OS."""
    lines = [
        "/**",
        " * DesignTokens.generated.kt — Kagami Design System",
        f" * Generated: {datetime.now().isoformat()}",
        " * DO NOT EDIT MANUALLY — Edit config/design-tokens/*.json instead",
        " */",
        "",
        "package com.kagami.ui.theme",
        "",
        "import androidx.compose.ui.graphics.Color",
        "import androidx.compose.animation.core.CubicBezierEasing",
        "import androidx.compose.ui.unit.dp",
        "",
        "// =============================================================================",
        "// COLOR TOKENS",
        "// =============================================================================",
        "",
    ]

    # Void palette
    lines.append("// Void Palette")
    for name, value in tokens["colors"]["void"].items():
        if name != "description":
            kotlin_name = name[0].upper() + name[1:]
            hex_val = value.replace("#", "0xFF")
            lines.append(f"val {kotlin_name} = Color({hex_val})")

    # Colony colors
    lines.append("")
    lines.append("// Colony Colors (Octonion Basis e₁-e₇)")
    for name, data in tokens["colors"]["colony"].items():
        if isinstance(data, dict):
            kotlin_name = name[0].upper() + name[1:]
            hex_val = data["hex"].replace("#", "0xFF")
            lines.append(
                f'val {kotlin_name} = Color({hex_val})  // {data["basis"]} — {data["name"]}'
            )

    # Status colors
    lines.append("")
    lines.append("// Status Colors")
    for name, value in tokens["colors"]["status"].items():
        if name != "description":
            kotlin_name = f"Status{name.capitalize()}"
            hex_val = value.replace("#", "0xFF")
            lines.append(f"val {kotlin_name} = Color({hex_val})")

    # Text colors
    lines.append("")
    lines.append("// Text Colors")
    text = tokens["colors"]["text"]
    hex_val = text["primary"].replace("#", "0xFF")
    lines.append(f"val TextPrimary = Color({hex_val})")
    lines.append(
        f"val TextSecondary = Color({hex_val}).copy(alpha = {text['secondary']['opacity']}f)"
    )
    lines.append(
        f"val TextTertiary = Color({hex_val}).copy(alpha = {text['tertiary']['opacity']}f)"
    )

    # Motion tokens
    lines.append("")
    lines.append("// =============================================================================")
    lines.append("// MOTION TOKENS")
    lines.append("// =============================================================================")
    lines.append("")
    lines.append("object KagamiDurations {")
    for name, value in tokens["motion"]["duration"].items():
        if name != "description":
            lines.append(f"    const val {name} = {value}")
    lines.append("}")
    lines.append("")

    lines.append("object KagamiEasing {")
    for name, data in tokens["motion"]["easing"].items():
        if isinstance(data, dict):
            b = data["bezier"]
            lines.append(f"    val {name} = CubicBezierEasing({b[0]}f, {b[1]}f, {b[2]}f, {b[3]}f)")
    lines.append("}")
    lines.append("")

    # Spacing tokens
    lines.append("// =============================================================================")
    lines.append("// SPACING TOKENS")
    lines.append("// =============================================================================")
    lines.append("")
    lines.append("object KagamiSpacing {")
    for name, value in tokens["spacing"]["spacing"].items():
        if name != "description":
            lines.append(f"    val {name} = {value}.dp")
    lines.append("}")
    lines.append("")

    lines.append("object KagamiRadius {")
    for name, value in tokens["spacing"]["radius"].items():
        if name != "description":
            lines.append(f"    val {name} = {value}.dp")
    lines.append("}")
    lines.append("")

    # Effect tokens
    lines.append("// =============================================================================")
    lines.append("// EFFECT TOKENS")
    lines.append("// =============================================================================")
    lines.append("")
    lines.append("object KagamiGlass {")
    glass = tokens["effects"]["glass"]
    for name, value in glass["blur"].items():
        lines.append(f"    val blur{name.capitalize()} = {value}.dp")
    lines.append(f"    const val defaultOpacity = {glass['transparency']['default']}f")
    lines.append("}")
    lines.append("")

    lines.append("object KagamiSpectral {")
    spectral = tokens["effects"]["spectral"]
    lines.append(f"    const val phaseCount = {spectral['phases']['count']}")
    lines.append(f"    const val shimmerDuration = {spectral['shimmer']['duration']}")
    lines.append(f"    const val shimmerHoverOpacity = {spectral['shimmer']['opacity']['hover']}f")
    lines.append(f"    const val borderDuration = {spectral['border']['duration']}")
    lines.append("}")
    lines.append("")

    return "\n".join(lines)


# =============================================================================
# RUST GENERATOR
# =============================================================================


def generate_rust(tokens: dict[str, Any]) -> str:
    """Generate Rust constants for Hub."""
    lines = [
        "//!",
        "//! design_tokens.generated.rs — Kagami Design System",
        f"//! Generated: {datetime.now().isoformat()}",
        "//! DO NOT EDIT MANUALLY — Edit config/design-tokens/*.json instead",
        "//!",
        "",
        "#![allow(dead_code)]",
        "",
        "// =============================================================================",
        "// COLOR TOKENS",
        "// =============================================================================",
        "",
    ]

    # Void palette
    lines.append("/// Void Palette (Backgrounds)")
    lines.append("pub mod void {")
    for name, value in tokens["colors"]["void"].items():
        if name != "description":
            rust_name = (
                "".join(f"_{c.lower()}" if c.isupper() else c for c in name).lstrip("_").upper()
            )
            hex_val = value.replace("#", "")
            lines.append(f"    pub const {rust_name}: u32 = 0x{hex_val};")
    lines.append("}")
    lines.append("")

    # Colony colors
    lines.append("/// Colony Colors (Octonion Basis e₁-e₇)")
    lines.append("pub mod colony {")
    for name, data in tokens["colors"]["colony"].items():
        if isinstance(data, dict):
            rust_name = name.upper()
            hex_val = data["hex"].replace("#", "")
            r, g, b = data["rgb"]
            lines.append(f"    pub const {rust_name}: u32 = 0x{hex_val};")
            lines.append(f"    pub const {rust_name}_RGB: (u8, u8, u8) = ({r}, {g}, {b});")
    lines.append("}")
    lines.append("")

    # Status colors
    lines.append("/// Status Colors")
    lines.append("pub mod status {")
    for name, value in tokens["colors"]["status"].items():
        if name != "description":
            rust_name = name.upper()
            hex_val = value.replace("#", "")
            lines.append(f"    pub const {rust_name}: u32 = 0x{hex_val};")
    lines.append("}")
    lines.append("")

    # Motion tokens
    lines.append("// =============================================================================")
    lines.append("// MOTION TOKENS")
    lines.append("// =============================================================================")
    lines.append("")
    lines.append("/// Duration in milliseconds")
    lines.append("pub mod duration {")
    for name, value in tokens["motion"]["duration"].items():
        if name != "description":
            rust_name = name.upper()
            lines.append(f"    pub const {rust_name}: u32 = {value};")
    lines.append("}")
    lines.append("")

    # Spacing tokens
    lines.append("// =============================================================================")
    lines.append("// SPACING TOKENS")
    lines.append("// =============================================================================")
    lines.append("")
    lines.append("/// Spacing in pixels (8px grid)")
    lines.append("pub mod spacing {")
    for name, value in tokens["spacing"]["spacing"].items():
        if name != "description":
            rust_name = name.upper()
            lines.append(f"    pub const {rust_name}: u32 = {value};")
    lines.append("}")
    lines.append("")

    lines.append("/// Border radius in pixels")
    lines.append("pub mod radius {")
    for name, value in tokens["spacing"]["radius"].items():
        if name != "description":
            rust_name = name.upper()
            lines.append(f"    pub const {rust_name}: u32 = {value};")
    lines.append("}")
    lines.append("")

    # Effect tokens
    lines.append("// =============================================================================")
    lines.append("// EFFECT TOKENS")
    lines.append("// =============================================================================")
    lines.append("")
    lines.append("/// Spectral effect parameters")
    lines.append("pub mod spectral {")
    spectral = tokens["effects"]["spectral"]
    lines.append(f"    pub const PHASE_COUNT: u32 = {spectral['phases']['count']};")
    lines.append(f"    pub const SHIMMER_DURATION_MS: u32 = {spectral['shimmer']['duration']};")
    lines.append(f"    pub const BORDER_DURATION_MS: u32 = {spectral['border']['duration']};")
    lines.append("}")
    lines.append("")

    return "\n".join(lines)


# =============================================================================
# MAIN
# =============================================================================


def main():
    parser = argparse.ArgumentParser(description="Generate platform-specific design tokens")
    parser.add_argument("--output-dir", type=Path, help="Override output directory")
    parser.add_argument(
        "--platform", choices=["css", "swift", "kotlin", "rust", "all"], default="all"
    )
    args = parser.parse_args()

    tokens = load_tokens()

    generators = {
        "css": (generate_css, OUTPUT_PATHS["css"]),
        "swift": (generate_swift, OUTPUT_PATHS["swift"]),
        "kotlin": (generate_kotlin, OUTPUT_PATHS["kotlin"]),
        "rust": (generate_rust, OUTPUT_PATHS["rust"]),
    }

    platforms = list(generators.keys()) if args.platform == "all" else [args.platform]

    for platform in platforms:
        generator, output_path = generators[platform]
        if args.output_dir:
            output_path = args.output_dir / output_path.name

        output_path.parent.mkdir(parents=True, exist_ok=True)
        content = generator(tokens)
        output_path.write_text(content)
        print(f"✅ Generated {output_path}")

    print(f"\n✨ Generated {len(platforms)} token file(s)")


if __name__ == "__main__":
    main()
