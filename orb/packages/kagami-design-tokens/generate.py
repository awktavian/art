#!/usr/bin/env python3
"""
Kagami Design Token Generator

Generates platform-specific design token files from a unified tokens.json.

Outputs:
- Swift extensions (iOS/watchOS/visionOS/tvOS)
- Kotlin objects (Android/Wear OS)
- CSS custom properties (Desktop/Web)
- Rust constants (Hub)

Usage:
    python generate.py [--platform <platform>] [--dry-run]

Examples:
    python generate.py                    # Generate all platforms
    python generate.py --platform swift   # Generate Swift only
    python generate.py --dry-run          # Preview without writing

Colony: Crystal (e7) - Verification & Polish
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Project structure
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
TOKENS_FILE = SCRIPT_DIR / "tokens.json"

# Output paths
OUTPUT_PATHS = {
    "swift": PROJECT_ROOT
    / "packages/kagami-design-swift/Sources/KagamiDesign/DesignTokens.generated.swift",
    "kotlin": PROJECT_ROOT
    / "apps/android/kagami-android/app/src/main/java/com/kagami/android/ui/theme/DesignTokens.generated.kt",
    "css": PROJECT_ROOT / "apps/desktop/kagami-client/src/css/design-tokens.generated.css",
    "rust": PROJECT_ROOT / "apps/hub/kagami-hub/src/design_tokens.generated.rs",
}

VERSION = "2.0.0"


def load_tokens() -> dict[str, Any]:
    """Load unified tokens.json."""
    return json.loads(TOKENS_FILE.read_text())


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def snake_to_camel(name: str) -> str:
    """Convert snake_case to camelCase."""
    components = name.split("_")
    return components[0] + "".join(x.title() for x in components[1:])


def camel_to_snake(name: str) -> str:
    """Convert camelCase to SNAKE_CASE."""
    result = []
    for i, char in enumerate(name):
        if char.isupper() and i > 0:
            result.append("_")
        result.append(char.upper())
    return "".join(result)


# =============================================================================
# SWIFT GENERATOR
# =============================================================================


def generate_swift(tokens: dict[str, Any]) -> str:
    """Generate Swift extensions for iOS/watchOS/visionOS/tvOS."""
    timestamp = datetime.now(UTC).isoformat()
    lines = [
        "//",
        "// DesignTokens.generated.swift - Kagami Design System",
        f"// Generated: {timestamp}",
        f"// Version: {VERSION}",
        "//",
        "// DO NOT EDIT MANUALLY - Edit packages/kagami-design-tokens/tokens.json instead",
        "// Regenerate with: python packages/kagami-design-tokens/generate.py --platform swift",
        "//",
        "",
        "import SwiftUI",
        "",
        "// MARK: - Color Tokens",
        "",
    ]

    # Helper for hex init
    lines.append("extension Color {")
    lines.append("    /// Initialize Color from hex string")
    lines.append("    init(tokenHex hex: String) {")
    lines.append(
        "        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)"
    )
    lines.append("        var int: UInt64 = 0")
    lines.append("        Scanner(string: hex).scanHexInt64(&int)")
    lines.append("        let r = Double((int >> 16) & 0xFF) / 255")
    lines.append("        let g = Double((int >> 8) & 0xFF) / 255")
    lines.append("        let b = Double(int & 0xFF) / 255")
    lines.append("        self.init(.sRGB, red: r, green: g, blue: b, opacity: 1)")
    lines.append("    }")
    lines.append("}")
    lines.append("")

    # Void palette
    lines.append("// MARK: - Void Palette (Backgrounds)")
    lines.append("")
    lines.append("public extension Color {")
    for name, data in tokens["colors"]["void"].items():
        if name == "description":
            continue
        hex_val = data["hex"] if isinstance(data, dict) else data
        desc = data.get("description", "") if isinstance(data, dict) else ""
        swift_name = name[0].lower() + name[1:] if name[0].isupper() else name
        lines.append(f"    /// {desc}")
        lines.append(f'    static let {swift_name} = Color(tokenHex: "{hex_val}")')
    lines.append("}")
    lines.append("")

    # Colony colors
    lines.append("// MARK: - Colony Colors (Octonion Basis e1-e7)")
    lines.append("")
    lines.append("public extension Color {")
    for name, data in tokens["colors"]["colony"].items():
        if name == "description" or not isinstance(data, dict):
            continue
        basis = data.get("basis", "")
        colony_name = data.get("name", "")
        lines.append(f"    /// {basis} - {colony_name}")
        lines.append(f'    static let {name} = Color(tokenHex: "{data["hex"]}")')
    lines.append("}")
    lines.append("")

    # Status colors
    lines.append("// MARK: - Status Colors")
    lines.append("")
    lines.append("public extension Color {")
    for name, data in tokens["colors"]["status"].items():
        if name == "description":
            continue
        hex_val = data["hex"] if isinstance(data, dict) else data
        desc = data.get("description", "") if isinstance(data, dict) else ""
        lines.append(f"    /// {desc}")
        lines.append(f'    static let status{name.capitalize()} = Color(tokenHex: "{hex_val}")')
    lines.append("}")
    lines.append("")

    # Safety colors
    lines.append("// MARK: - Safety Colors (CBF)")
    lines.append("")
    lines.append("public extension Color {")
    for name, data in tokens["colors"]["safety"].items():
        if name == "description":
            continue
        hex_val = data["hex"] if isinstance(data, dict) else data
        desc = data.get("description", "") if isinstance(data, dict) else ""
        lines.append(f"    /// {desc}")
        lines.append(f'    static let safety{name.capitalize()} = Color(tokenHex: "{hex_val}")')
    lines.append("}")
    lines.append("")

    # Text colors
    lines.append("// MARK: - Text Colors")
    lines.append("")
    lines.append("public extension Color {")
    for name, data in tokens["colors"]["text"].items():
        if name == "description":
            continue
        hex_val = data["hex"]
        opacity = data.get("opacity", 1.0)
        if opacity == 1.0:
            lines.append(f'    static let text{name.capitalize()} = Color(tokenHex: "{hex_val}")')
        else:
            lines.append(
                f'    static let text{name.capitalize()} = Color(tokenHex: "{hex_val}").opacity({opacity})'
            )
    lines.append("}")
    lines.append("")

    # Motion - Duration
    lines.append("// MARK: - Motion Tokens")
    lines.append("")
    lines.append("/// Fibonacci-based animation durations (seconds)")
    lines.append("public enum KagamiDuration {")
    for name, value in tokens["motion"]["duration"].items():
        if name == "description":
            continue
        lines.append(f"    public static let {name}: Double = {value / 1000}")
    lines.append("}")
    lines.append("")

    # Motion - Easing
    lines.append("/// Catastrophe-inspired easing curves")
    lines.append("public enum KagamiEasing {")
    for name, data in tokens["motion"]["easing"].items():
        if name == "description" or not isinstance(data, dict):
            continue
        b = data["bezier"]
        desc = data.get("description", "")
        lines.append(f"    /// {desc}")
        lines.append(
            f"    public static let {name} = Animation.timingCurve({b[0]}, {b[1]}, {b[2]}, {b[3]}, duration: KagamiDuration.normal)"
        )
    lines.append("}")
    lines.append("")

    # Spacing
    lines.append("// MARK: - Spacing Tokens")
    lines.append("")
    lines.append("/// 8pt grid-based spacing system")
    lines.append("public enum KagamiSpacing {")
    for name, value in tokens["spacing"].items():
        if name == "description":
            continue
        swift_name = (
            name.replace("xl", "XL").replace("xs", "XS")
            if name in ["2xl", "3xl", "4xl", "5xl", "6xl"]
            else name
        )
        if (
            name.startswith("2")
            or name.startswith("3")
            or name.startswith("4")
            or name.startswith("5")
            or name.startswith("6")
        ):
            swift_name = f"_{name}"  # Swift can't start with number
        lines.append(f"    public static let {swift_name}: CGFloat = {value}")
    lines.append("}")
    lines.append("")

    # Radius
    lines.append("/// Corner radius tokens")
    lines.append("public enum KagamiRadius {")
    for name, value in tokens["radius"].items():
        if name == "description":
            continue
        swift_name = name.replace("xl", "XL").replace("xs", "XS")
        if name.startswith("2") or name.startswith("3"):
            swift_name = f"_{name}"
        lines.append(f"    public static let {swift_name}: CGFloat = {value}")
    lines.append("}")
    lines.append("")

    # Typography
    lines.append("// MARK: - Typography Tokens")
    lines.append("")
    lines.append("/// Font size tokens")
    lines.append("public enum KagamiFontSize {")
    for name, value in tokens["typography"]["fontSize"].items():
        if name == "description":
            continue
        swift_name = name.replace("xl", "XL").replace("xs", "XS")
        if name.startswith("2") or name.startswith("3") or name.startswith("4"):
            swift_name = f"_{name}"
        lines.append(f"    public static let {swift_name}: CGFloat = {value}")
    lines.append("}")
    lines.append("")

    lines.append("/// Font weight tokens")
    lines.append("public enum KagamiFontWeight {")
    for name, value in tokens["typography"]["fontWeight"].items():
        weight_map = {400: "regular", 500: "medium", 600: "semibold", 700: "bold"}
        lines.append(
            f"    public static let {name}: Font.Weight = .{weight_map.get(value, 'regular')}"
        )
    lines.append("}")
    lines.append("")

    lines.append("/// Line height multipliers")
    lines.append("public enum KagamiLineHeight {")
    for name, value in tokens["typography"]["lineHeight"].items():
        lines.append(f"    public static let {name}: CGFloat = {value}")
    lines.append("}")
    lines.append("")

    # Shadows
    lines.append("// MARK: - Shadow Tokens")
    lines.append("")
    lines.append("/// Shadow configurations")
    lines.append("public struct KagamiShadow {")
    lines.append("    public let x: CGFloat")
    lines.append("    public let y: CGFloat")
    lines.append("    public let blur: CGFloat")
    lines.append("    public let opacity: Double")
    lines.append("")
    for name, data in tokens["shadows"].items():
        if name == "description" or name == "chromatic":
            continue
        if not isinstance(data, dict):
            continue
        offset = data.get("offset", [0, 0])
        blur = data.get("blur", 0)
        opacity = data.get("opacity", 0)
        lines.append(
            f"    public static let {name} = KagamiShadow(x: {offset[0]}, y: {offset[1]}, blur: {blur}, opacity: {opacity})"
        )
    lines.append("}")
    lines.append("")

    # Breakpoints
    lines.append("// MARK: - Breakpoint Tokens")
    lines.append("")
    lines.append("/// Responsive breakpoints")
    lines.append("public enum KagamiBreakpoint {")
    for name, value in tokens["breakpoints"].items():
        if name == "description":
            continue
        swift_name = name.replace("xl", "XL").replace("xs", "XS")
        if name.startswith("2"):
            swift_name = f"_{name}"
        lines.append(f"    public static let {swift_name}: CGFloat = {value}")
    lines.append("}")
    lines.append("")

    # Accessibility
    lines.append("// MARK: - Accessibility Tokens")
    lines.append("")
    lines.append("/// Accessibility constants")
    lines.append("public enum KagamiAccessibility {")
    lines.append(
        f"    public static let minTouchTarget: CGFloat = {tokens['accessibility']['touchTarget']['minimum']}"
    )
    lines.append(
        f"    public static let recommendedTouchTarget: CGFloat = {tokens['accessibility']['touchTarget']['recommended']}"
    )
    lines.append("}")
    lines.append("")

    return "\n".join(lines)


# =============================================================================
# KOTLIN GENERATOR
# =============================================================================


def generate_kotlin(tokens: dict[str, Any]) -> str:
    """Generate Kotlin objects for Android/Wear OS."""
    timestamp = datetime.now(UTC).isoformat()
    lines = [
        "/**",
        " * DesignTokens.generated.kt - Kagami Design System",
        f" * Generated: {timestamp}",
        f" * Version: {VERSION}",
        " *",
        " * DO NOT EDIT MANUALLY - Edit packages/kagami-design-tokens/tokens.json instead",
        " * Regenerate with: python packages/kagami-design-tokens/generate.py --platform kotlin",
        " */",
        "",
        "package com.kagami.android.ui.theme",
        "",
        "import androidx.compose.ui.graphics.Color",
        "import androidx.compose.animation.core.CubicBezierEasing",
        "import androidx.compose.ui.unit.Dp",
        "import androidx.compose.ui.unit.dp",
        "import androidx.compose.ui.unit.sp",
        "",
        "// =============================================================================",
        "// COLOR TOKENS",
        "// =============================================================================",
        "",
    ]

    # Void palette
    lines.append("// Void Palette (Backgrounds)")
    for name, data in tokens["colors"]["void"].items():
        if name == "description":
            continue
        hex_val = (data["hex"] if isinstance(data, dict) else data).replace("#", "0xFF")
        kotlin_name = name[0].upper() + name[1:]
        lines.append(f"val Token{kotlin_name} = Color({hex_val})")
    lines.append("")

    # Colony colors
    lines.append("// Colony Colors (Octonion Basis e1-e7)")
    for name, data in tokens["colors"]["colony"].items():
        if name == "description" or not isinstance(data, dict):
            continue
        hex_val = data["hex"].replace("#", "0xFF")
        kotlin_name = name[0].upper() + name[1:]
        basis = data.get("basis", "")
        colony_name = data.get("name", "")
        lines.append(f"val Token{kotlin_name} = Color({hex_val})  // {basis} - {colony_name}")
    lines.append("")

    # Status colors
    lines.append("// Status Colors")
    for name, data in tokens["colors"]["status"].items():
        if name == "description":
            continue
        hex_val = (data["hex"] if isinstance(data, dict) else data).replace("#", "0xFF")
        lines.append(f"val TokenStatus{name.capitalize()} = Color({hex_val})")
    lines.append("")

    # Safety colors
    lines.append("// Safety Colors (CBF)")
    for name, data in tokens["colors"]["safety"].items():
        if name == "description":
            continue
        hex_val = (data["hex"] if isinstance(data, dict) else data).replace("#", "0xFF")
        lines.append(f"val TokenSafety{name.capitalize()} = Color({hex_val})")
    lines.append("")

    # Text colors
    lines.append("// Text Colors")
    for name, data in tokens["colors"]["text"].items():
        if name == "description":
            continue
        hex_val = data["hex"].replace("#", "0xFF")
        opacity = data.get("opacity", 1.0)
        if opacity == 1.0:
            lines.append(f"val TokenText{name.capitalize()} = Color({hex_val})")
        else:
            lines.append(
                f"val TokenText{name.capitalize()} = Color({hex_val}).copy(alpha = {opacity}f)"
            )
    lines.append("")

    # Motion - Duration
    lines.append("// =============================================================================")
    lines.append("// MOTION TOKENS")
    lines.append("// =============================================================================")
    lines.append("")
    lines.append("/** Fibonacci-based animation durations (milliseconds) */")
    lines.append("object TokenDuration {")
    for name, value in tokens["motion"]["duration"].items():
        if name == "description":
            continue
        lines.append(f"    const val {name} = {value}")
    lines.append("}")
    lines.append("")

    # Motion - Easing
    lines.append("/** Catastrophe-inspired easing curves */")
    lines.append("object TokenEasing {")
    for name, data in tokens["motion"]["easing"].items():
        if name == "description" or not isinstance(data, dict):
            continue
        b = data["bezier"]
        lines.append(f"    val {name} = CubicBezierEasing({b[0]}f, {b[1]}f, {b[2]}f, {b[3]}f)")
    lines.append("}")
    lines.append("")

    # Spacing
    lines.append("// =============================================================================")
    lines.append("// SPACING TOKENS")
    lines.append("// =============================================================================")
    lines.append("")
    lines.append("/** 8pt grid-based spacing system */")
    lines.append("object TokenSpacing {")
    for name, value in tokens["spacing"].items():
        if name == "description":
            continue
        kotlin_name = (
            name.replace("xl", "Xl").replace("xs", "Xs")
            if not name[0].isdigit()
            else f"space{name}"
        )
        lines.append(f"    val {kotlin_name}: Dp = {value}.dp")
    lines.append("}")
    lines.append("")

    # Radius
    lines.append("/** Corner radius tokens */")
    lines.append("object TokenRadius {")
    for name, value in tokens["radius"].items():
        if name == "description":
            continue
        kotlin_name = (
            name.replace("xl", "Xl").replace("xs", "Xs")
            if not name[0].isdigit()
            else f"radius{name}"
        )
        lines.append(f"    val {kotlin_name}: Dp = {value}.dp")
    lines.append("}")
    lines.append("")

    # Typography
    lines.append("// =============================================================================")
    lines.append("// TYPOGRAPHY TOKENS")
    lines.append("// =============================================================================")
    lines.append("")
    lines.append("/** Font size tokens */")
    lines.append("object TokenFontSize {")
    for name, value in tokens["typography"]["fontSize"].items():
        if name == "description":
            continue
        kotlin_name = (
            name.replace("xl", "Xl").replace("xs", "Xs") if not name[0].isdigit() else f"size{name}"
        )
        lines.append(f"    val {kotlin_name} = {value}.sp")
    lines.append("}")
    lines.append("")

    # Shadows
    lines.append("// =============================================================================")
    lines.append("// SHADOW TOKENS")
    lines.append("// =============================================================================")
    lines.append("")
    lines.append("/** Shadow elevation levels */")
    lines.append("object TokenShadow {")
    for name, data in tokens["shadows"].items():
        if name == "description" or name == "chromatic" or not isinstance(data, dict):
            continue
        blur = data.get("blur", 0)
        lines.append(f"    val {name}: Dp = {blur}.dp")
    lines.append("}")
    lines.append("")

    # Breakpoints
    lines.append("// =============================================================================")
    lines.append("// BREAKPOINT TOKENS")
    lines.append("// =============================================================================")
    lines.append("")
    lines.append("/** Responsive breakpoints */")
    lines.append("object TokenBreakpoint {")
    for name, value in tokens["breakpoints"].items():
        if name == "description":
            continue
        kotlin_name = (
            name.replace("xl", "Xl").replace("xs", "Xs") if not name[0].isdigit() else f"bp{name}"
        )
        lines.append(f"    val {kotlin_name}: Dp = {value}.dp")
    lines.append("}")
    lines.append("")

    # Accessibility
    lines.append("// =============================================================================")
    lines.append("// ACCESSIBILITY TOKENS")
    lines.append("// =============================================================================")
    lines.append("")
    lines.append("/** Accessibility constants */")
    lines.append("object TokenAccessibility {")
    lines.append(
        f"    val minTouchTarget: Dp = {tokens['accessibility']['touchTarget']['minimumAndroid']}.dp"
    )
    lines.append(
        f"    val recommendedTouchTarget: Dp = {tokens['accessibility']['touchTarget']['recommended']}.dp"
    )
    lines.append("}")
    lines.append("")

    return "\n".join(lines)


# =============================================================================
# CSS GENERATOR
# =============================================================================


def generate_css(tokens: dict[str, Any]) -> str:
    """Generate CSS custom properties."""
    timestamp = datetime.now(UTC).isoformat()
    lines = [
        "/**",
        " * design-tokens.generated.css - Kagami Design System",
        f" * Generated: {timestamp}",
        f" * Version: {VERSION}",
        " *",
        " * DO NOT EDIT MANUALLY - Edit packages/kagami-design-tokens/tokens.json instead",
        " * Regenerate with: python packages/kagami-design-tokens/generate.py --platform css",
        " */",
        "",
        ":root {",
    ]

    # Void palette
    lines.append("    /* Void Palette (Backgrounds) */")
    for name, data in tokens["colors"]["void"].items():
        if name == "description":
            continue
        hex_val = data["hex"] if isinstance(data, dict) else data
        css_name = camel_to_snake(name).lower().replace("_", "-")
        lines.append(f"    --kagami-{css_name}: {hex_val};")
    lines.append("")

    # Colony colors
    lines.append("    /* Colony Colors (Octonion Basis e1-e7) */")
    for name, data in tokens["colors"]["colony"].items():
        if name == "description" or not isinstance(data, dict):
            continue
        lines.append(f"    --kagami-{name}: {data['hex']};")
        r, g, b = data["rgb"]
        lines.append(f"    --kagami-{name}-rgb: {r}, {g}, {b};")
    lines.append("")

    # Status colors
    lines.append("    /* Status Colors */")
    for name, data in tokens["colors"]["status"].items():
        if name == "description":
            continue
        hex_val = data["hex"] if isinstance(data, dict) else data
        lines.append(f"    --kagami-status-{name}: {hex_val};")
    lines.append("")

    # Safety colors
    lines.append("    /* Safety Colors (CBF) */")
    for name, data in tokens["colors"]["safety"].items():
        if name == "description":
            continue
        hex_val = data["hex"] if isinstance(data, dict) else data
        lines.append(f"    --kagami-safety-{name}: {hex_val};")
    lines.append("")

    # Text colors
    lines.append("    /* Text Colors */")
    for name, data in tokens["colors"]["text"].items():
        if name == "description":
            continue
        hex_val = data["hex"]
        opacity = data.get("opacity", 1.0)
        if opacity == 1.0:
            lines.append(f"    --kagami-text-{name}: {hex_val};")
        else:
            r, g, b = hex_to_rgb(hex_val)
            lines.append(f"    --kagami-text-{name}: rgba({r}, {g}, {b}, {opacity});")
    lines.append("")

    # Motion - Duration
    lines.append("    /* Motion - Durations (Fibonacci) */")
    for name, value in tokens["motion"]["duration"].items():
        if name == "description":
            continue
        lines.append(f"    --kagami-dur-{name}: {value}ms;")
    lines.append("")

    # Motion - Easing
    lines.append("    /* Motion - Easings (Catastrophe-inspired) */")
    for name, data in tokens["motion"]["easing"].items():
        if name == "description" or not isinstance(data, dict):
            continue
        b = data["bezier"]
        lines.append(f"    --kagami-ease-{name}: cubic-bezier({b[0]}, {b[1]}, {b[2]}, {b[3]});")
    lines.append("")

    # Spacing
    lines.append("    /* Spacing (8pt grid) */")
    for name, value in tokens["spacing"].items():
        if name == "description":
            continue
        lines.append(f"    --kagami-space-{name}: {value}px;")
    lines.append("")

    # Radius
    lines.append("    /* Border Radius */")
    for name, value in tokens["radius"].items():
        if name == "description":
            continue
        unit = "" if value == 9999 else "px"
        lines.append(f"    --kagami-radius-{name}: {value}{unit};")
    lines.append("")

    # Typography - Font sizes
    lines.append("    /* Typography - Font Sizes */")
    for name, value in tokens["typography"]["fontSize"].items():
        if name == "description":
            continue
        lines.append(f"    --kagami-font-size-{name}: {value}px;")
    lines.append("")

    # Typography - Font weights
    lines.append("    /* Typography - Font Weights */")
    for name, value in tokens["typography"]["fontWeight"].items():
        lines.append(f"    --kagami-font-weight-{name}: {value};")
    lines.append("")

    # Typography - Line heights
    lines.append("    /* Typography - Line Heights */")
    for name, value in tokens["typography"]["lineHeight"].items():
        lines.append(f"    --kagami-line-height-{name}: {value};")
    lines.append("")

    # Typography - Font families
    lines.append("    /* Typography - Font Families */")
    desktop = tokens["typography"]["fontFamily"]["desktop"]
    lines.append(
        f'    --kagami-font-sans: "{desktop["primary"]}", -apple-system, BlinkMacSystemFont, sans-serif;'
    )
    lines.append(f'    --kagami-font-mono: "{desktop["mono"]}", "SF Mono", monospace;')
    lines.append(
        f'    --kagami-font-display: "{tokens["typography"]["fontFamily"]["display"]}", Georgia, serif;'
    )
    lines.append("")

    # Shadows
    lines.append("    /* Shadows */")
    for name, data in tokens["shadows"].items():
        if name == "description" or name == "chromatic" or not isinstance(data, dict):
            continue
        offset = data.get("offset", [0, 0])
        blur = data.get("blur", 0)
        opacity = data.get("opacity", 0)
        lines.append(
            f"    --kagami-shadow-{name}: {offset[0]}px {offset[1]}px {blur}px rgba(0, 0, 0, {opacity});"
        )
    lines.append("")

    # Breakpoints
    lines.append("    /* Breakpoints */")
    for name, value in tokens["breakpoints"].items():
        if name == "description":
            continue
        lines.append(f"    --kagami-breakpoint-{name}: {value}px;")
    lines.append("")

    # Effects - Glass
    lines.append("    /* Glass Effects */")
    glass = tokens["effects"]["glass"]
    for name, value in glass["blur"].items():
        lines.append(f"    --kagami-blur-{name}: {value}px;")
    lines.append(f"    --kagami-glass-opacity: {glass['transparency']['default']};")
    lines.append("")

    # Z-index
    lines.append("    /* Z-Index Layers */")
    for name, value in tokens["zIndex"].items():
        if name == "description":
            continue
        css_name = camel_to_snake(name).lower().replace("_", "-")
        lines.append(f"    --kagami-z-{css_name}: {value};")
    lines.append("")

    # Accessibility
    lines.append("    /* Accessibility */")
    lines.append(
        f"    --kagami-touch-target-min: {tokens['accessibility']['touchTarget']['minimum']}px;"
    )
    lines.append(
        f"    --kagami-touch-target-recommended: {tokens['accessibility']['touchTarget']['recommended']}px;"
    )

    lines.append("}")
    lines.append("")
    lines.append("/*")
    lines.append(" * h(x) >= 0. Always.")
    lines.append(" */")
    lines.append("")

    return "\n".join(lines)


# =============================================================================
# RUST GENERATOR
# =============================================================================


def generate_rust(tokens: dict[str, Any]) -> str:
    """Generate Rust constants for Hub."""
    timestamp = datetime.now(UTC).isoformat()
    lines = [
        "//!",
        "//! design_tokens.generated.rs - Kagami Design System",
        f"//! Generated: {timestamp}",
        f"//! Version: {VERSION}",
        "//!",
        "//! DO NOT EDIT MANUALLY - Edit packages/kagami-design-tokens/tokens.json instead",
        "//! Regenerate with: python packages/kagami-design-tokens/generate.py --platform rust",
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
    for name, data in tokens["colors"]["void"].items():
        if name == "description":
            continue
        hex_val = (data["hex"] if isinstance(data, dict) else data).replace("#", "")
        rust_name = camel_to_snake(name)
        lines.append(f"    pub const {rust_name}: u32 = 0x{hex_val};")
    lines.append("}")
    lines.append("")

    # Colony colors
    lines.append("/// Colony Colors (Octonion Basis e1-e7)")
    lines.append("pub mod colony {")
    for name, data in tokens["colors"]["colony"].items():
        if name == "description" or not isinstance(data, dict):
            continue
        hex_val = data["hex"].replace("#", "")
        rust_name = name.upper()
        r, g, b = data["rgb"]
        lines.append(f"    pub const {rust_name}: u32 = 0x{hex_val};")
        lines.append(f"    pub const {rust_name}_RGB: (u8, u8, u8) = ({r}, {g}, {b});")
    lines.append("}")
    lines.append("")

    # Status colors
    lines.append("/// Status Colors")
    lines.append("pub mod status {")
    for name, data in tokens["colors"]["status"].items():
        if name == "description":
            continue
        hex_val = (data["hex"] if isinstance(data, dict) else data).replace("#", "")
        rust_name = name.upper()
        lines.append(f"    pub const {rust_name}: u32 = 0x{hex_val};")
    lines.append("}")
    lines.append("")

    # Safety colors
    lines.append("/// Safety Colors (CBF)")
    lines.append("pub mod safety {")
    for name, data in tokens["colors"]["safety"].items():
        if name == "description":
            continue
        hex_val = (data["hex"] if isinstance(data, dict) else data).replace("#", "")
        rust_name = name.upper()
        lines.append(f"    pub const {rust_name}: u32 = 0x{hex_val};")
    lines.append("}")
    lines.append("")

    # Motion - Duration
    lines.append("// =============================================================================")
    lines.append("// MOTION TOKENS")
    lines.append("// =============================================================================")
    lines.append("")
    lines.append("/// Duration in milliseconds (Fibonacci sequence)")
    lines.append("pub mod duration {")
    for name, value in tokens["motion"]["duration"].items():
        if name == "description":
            continue
        rust_name = name.upper()
        lines.append(f"    pub const {rust_name}: u32 = {value};")
    lines.append("}")
    lines.append("")

    # Spacing
    lines.append("// =============================================================================")
    lines.append("// SPACING TOKENS")
    lines.append("// =============================================================================")
    lines.append("")
    lines.append("/// Spacing in pixels (8px grid)")
    lines.append("pub mod spacing {")
    for name, value in tokens["spacing"].items():
        if name == "description":
            continue
        rust_name = name.upper().replace("XL", "_XL").replace("XS", "_XS").lstrip("_")
        if name[0].isdigit():
            rust_name = f"SPACE_{name.upper()}"
        lines.append(f"    pub const {rust_name}: u32 = {value};")
    lines.append("}")
    lines.append("")

    # Radius
    lines.append("/// Border radius in pixels")
    lines.append("pub mod radius {")
    for name, value in tokens["radius"].items():
        if name == "description":
            continue
        rust_name = name.upper().replace("XL", "_XL").replace("XS", "_XS").lstrip("_")
        if name[0].isdigit():
            rust_name = f"RADIUS_{name.upper()}"
        lines.append(f"    pub const {rust_name}: u32 = {value};")
    lines.append("}")
    lines.append("")

    # Typography
    lines.append("// =============================================================================")
    lines.append("// TYPOGRAPHY TOKENS")
    lines.append("// =============================================================================")
    lines.append("")
    lines.append("/// Font sizes in pixels")
    lines.append("pub mod font_size {")
    for name, value in tokens["typography"]["fontSize"].items():
        if name == "description":
            continue
        rust_name = name.upper().replace("XL", "_XL").replace("XS", "_XS").lstrip("_")
        if name[0].isdigit():
            rust_name = f"SIZE_{name.upper()}"
        lines.append(f"    pub const {rust_name}: u32 = {value};")
    lines.append("}")
    lines.append("")

    # Breakpoints
    lines.append("// =============================================================================")
    lines.append("// BREAKPOINT TOKENS")
    lines.append("// =============================================================================")
    lines.append("")
    lines.append("/// Responsive breakpoints in pixels")
    lines.append("pub mod breakpoint {")
    for name, value in tokens["breakpoints"].items():
        if name == "description":
            continue
        rust_name = name.upper().replace("XL", "_XL").replace("XS", "_XS").lstrip("_")
        if name[0].isdigit():
            rust_name = f"BP_{name.upper()}"
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
    lines.append(f"    pub const PHASE_COUNT: u32 = {spectral['phaseCount']};")
    lines.append(f"    pub const SHIMMER_DURATION_MS: u32 = {spectral['shimmer']['duration']};")
    lines.append(f"    pub const BORDER_DURATION_MS: u32 = {spectral['border']['duration']};")
    lines.append("}")
    lines.append("")

    return "\n".join(lines)


# =============================================================================
# MAIN
# =============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Generate platform-specific design tokens from unified tokens.json"
    )
    parser.add_argument(
        "--platform",
        choices=["swift", "kotlin", "css", "rust", "all"],
        default="all",
        help="Target platform (default: all)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview output without writing files"
    )
    parser.add_argument("--output-dir", type=Path, help="Override output directory")
    args = parser.parse_args()

    tokens = load_tokens()

    generators = {
        "swift": (generate_swift, OUTPUT_PATHS["swift"]),
        "kotlin": (generate_kotlin, OUTPUT_PATHS["kotlin"]),
        "css": (generate_css, OUTPUT_PATHS["css"]),
        "rust": (generate_rust, OUTPUT_PATHS["rust"]),
    }

    platforms = list(generators.keys()) if args.platform == "all" else [args.platform]

    for platform in platforms:
        generator, output_path = generators[platform]
        if args.output_dir:
            output_path = args.output_dir / output_path.name

        content = generator(tokens)

        if args.dry_run:
            print(f"\n{'=' * 60}")
            print(f"DRY RUN: {output_path}")
            print("=" * 60)
            print(content[:2000] + "..." if len(content) > 2000 else content)
        else:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(content)
            print(f"Generated: {output_path}")

    if not args.dry_run:
        print(f"\nGenerated {len(platforms)} token file(s)")
        print("h(x) >= 0. Always.")


if __name__ == "__main__":
    main()
