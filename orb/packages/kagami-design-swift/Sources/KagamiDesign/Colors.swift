//
// Colors.swift — Kagami Design System
//
// Canonical color definitions for all Apple platforms.
// Source: packages/kagami_design_tokens/tokens.json
//
// Colony: Crystal (e7) — Verification & Polish
//

import SwiftUI

// MARK: - Hex Color Initializer

extension Color {
    /// Initialize Color from hex string. Supports 3, 6, and 8 character hex codes.
    /// - Parameter hex: Hex color string (e.g., "#FF6B35", "FF6B35", "#FFF")
    public init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let a, r, g, b: UInt64
        switch hex.count {
        case 3: // RGB (12-bit)
            (a, r, g, b) = (255, (int >> 8) * 17, (int >> 4 & 0xF) * 17, (int & 0xF) * 17)
        case 6: // RGB (24-bit)
            (a, r, g, b) = (255, int >> 16, int >> 8 & 0xFF, int & 0xFF)
        case 8: // ARGB (32-bit)
            (a, r, g, b) = (int >> 24, int >> 16 & 0xFF, int >> 8 & 0xFF, int & 0xFF)
        default:
            (a, r, g, b) = (255, 0, 0, 0)
        }
        self.init(
            .sRGB,
            red: Double(r) / 255,
            green: Double(g) / 255,
            blue: Double(b) / 255,
            opacity: Double(a) / 255
        )
    }
}

// MARK: - Void Palette (Backgrounds)

extension Color {
    /// Primary background - warm black (#07060B)
    public static let void = Color(hex: "#07060B")

    /// Tinted background (#0D0A0F)
    public static let voidWarm = Color(hex: "#0D0A0F")

    /// Card background (#12101A)
    public static let obsidian = Color(hex: "#12101A")

    /// Light void (#1a1820)
    public static let voidLight = Color(hex: "#1a1820")

    /// Carbon - elevated surface (#252330)
    public static let carbon = Color(hex: "#252330")

    /// Elevated surface (#1f1d24)
    public static let surfaceElevated = Color(hex: "#1f1d24")
}

// MARK: - Colony Colors (Octonion Basis e1-e7)

extension Color {
    /// e1 - Ideation (#ff6b35) - Spark
    public static let spark = Color(hex: "#ff6b35")

    /// e2 - Implementation (#FF9500) - Forge (Apple orange)
    public static let forge = Color(hex: "#FF9500")

    /// e3 - Adaptation (#5AC8FA) - Flow (Apple blue, water)
    public static let flow = Color(hex: "#5AC8FA")

    /// e4 - Integration (#AF52DE) - Nexus (Apple purple, bridge)
    public static let nexus = Color(hex: "#AF52DE")

    /// e5 - Planning (#FFD60A) - Beacon (Apple yellow, light)
    public static let beacon = Color(hex: "#FFD60A")

    /// e6 - Research (#32D74B) - Grove (Apple green, nature)
    public static let grove = Color(hex: "#32D74B")

    /// e7 - Verification (#64D2FF) - Crystal (Apple cyan, clarity)
    public static let crystal = Color(hex: "#64D2FF")
}

// MARK: - Colony Enum

/// The seven cognitive colonies mapped to octonion basis vectors
public enum Colony: String, CaseIterable, Sendable {
    case spark   // e1 - Ideation
    case forge   // e2 - Implementation
    case flow    // e3 - Adaptation
    case nexus   // e4 - Integration
    case beacon  // e5 - Planning
    case grove   // e6 - Research
    case crystal // e7 - Verification

    /// The color associated with this colony
    public var color: Color {
        switch self {
        case .spark: return .spark
        case .forge: return .forge
        case .flow: return .flow
        case .nexus: return .nexus
        case .beacon: return .beacon
        case .grove: return .grove
        case .crystal: return .crystal
        }
    }

    /// The octonion basis index (1-7)
    public var basisIndex: Int {
        switch self {
        case .spark: return 1
        case .forge: return 2
        case .flow: return 3
        case .nexus: return 4
        case .beacon: return 5
        case .grove: return 6
        case .crystal: return 7
        }
    }

    /// Display name for the colony
    public var displayName: String {
        rawValue.capitalized
    }

    /// Description of the colony's function
    public var function: String {
        switch self {
        case .spark: return "Ideation"
        case .forge: return "Implementation"
        case .flow: return "Adaptation"
        case .nexus: return "Integration"
        case .beacon: return "Planning"
        case .grove: return "Research"
        case .crystal: return "Verification"
        }
    }
}

// MARK: - Mode Colors (Colony-Aligned)

extension Color {
    /// Ask mode - Grove (research)
    public static let modeAsk = Color.grove

    /// Plan mode - Beacon (planning)
    public static let modePlan = Color.beacon

    /// Agent mode - Forge (implementation)
    public static let modeAgent = Color.forge
}

// MARK: - Status Colors

extension Color {
    /// Success status (#00ff88)
    public static let statusSuccess = Color(hex: "#00ff88")

    /// Error status (#ff4444)
    public static let statusError = Color(hex: "#ff4444")

    /// Warning status (#ffd700)
    public static let statusWarning = Color(hex: "#ffd700")
}

// MARK: - Safety Colors (CBF)

extension Color {
    /// Safety OK - h(x) >= 0.5 (#4ADE80)
    public static let safetyOk = Color(hex: "#4ADE80")

    /// Safety Caution - 0 <= h(x) < 0.5 (#FBBF24)
    public static let safetyCaution = Color(hex: "#FBBF24")

    /// Safety Violation - h(x) < 0 (#F87171)
    public static let safetyViolation = Color(hex: "#F87171")

    /// Returns the appropriate safety color for a given score
    public static func safetyColor(for score: Double?) -> Color {
        guard let score = score else { return .secondary }
        if score >= 0.5 { return .safetyOk }
        if score >= 0 { return .safetyCaution }
        return .safetyViolation
    }
}

// MARK: - Accessible Text Colors (WCAG 2.1 AAA Target)

extension Color {
    /// Primary text - ~15:1 contrast ratio (exceeds AAA) (#F5F0E8)
    public static let accessibleTextPrimary = Color(hex: "#F5F0E8")

    /// Secondary text - ~8:1 contrast ratio (AAA compliant) (#C4C0B8)
    public static let accessibleTextSecondary = Color(hex: "#C4C0B8")

    /// Tertiary text - ~7:1 contrast ratio (AAA compliant) (#A8A49C)
    /// Upgraded from #8A8680 (~4.6:1) to meet AAA requirements
    public static let accessibleTextTertiary = Color(hex: "#A8A49C")

    /// Primary text - white with sufficient contrast (21:1)
    public static let textPrimary = Color.white

    /// Secondary text - lightened for readability (7.5:1)
    public static let textSecondary = Color(hex: "#A0A0A0")

    /// Tertiary text - minimum compliant (4.6:1)
    public static let textTertiary = Color(hex: "#808080")

    /// Disabled text
    public static let textDisabled = Color(hex: "#444444")
}

// MARK: - Glass/Spatial Colors

extension Color {
    /// Glass highlight for spatial interfaces
    public static let glassHighlight = Color.white.opacity(0.15)

    /// Glass border for spatial interfaces
    public static let glassBorder = Color.white.opacity(0.2)

    /// Enhanced contrast glass highlight (accessibility)
    public static let glassHighlightAccessible = Color.white.opacity(0.35)

    /// Enhanced contrast glass border (accessibility)
    public static let glassBorderAccessible = Color.white.opacity(0.45)
}

// MARK: - Contrast Ratio Utilities

/// WCAG 2.1 contrast ratio utilities
public struct ContrastRatio {
    /// Calculate luminance for a color (sRGB)
    public static func luminance(red: CGFloat, green: CGFloat, blue: CGFloat) -> CGFloat {
        func adjust(_ value: CGFloat) -> CGFloat {
            value <= 0.03928 ? value / 12.92 : pow((value + 0.055) / 1.055, 2.4)
        }
        return 0.2126 * adjust(red) + 0.7152 * adjust(green) + 0.0722 * adjust(blue)
    }

    /// Calculate contrast ratio between two luminances
    public static func ratio(l1: CGFloat, l2: CGFloat) -> CGFloat {
        let lighter = max(l1, l2)
        let darker = min(l1, l2)
        return (lighter + 0.05) / (darker + 0.05)
    }

    /// WCAG AA minimum for normal text
    public static let wcagAANormal: CGFloat = 4.5

    /// WCAG AA minimum for large text (18pt+ or 14pt bold)
    public static let wcagAALarge: CGFloat = 3.0

    /// WCAG AAA minimum for normal text
    public static let wcagAAANormal: CGFloat = 7.0

    /// WCAG AAA minimum for large text
    public static let wcagAAALarge: CGFloat = 4.5
}
