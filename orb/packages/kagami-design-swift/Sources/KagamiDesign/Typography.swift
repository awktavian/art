//
// Typography.swift — Kagami Design System
//
// Semantic font definitions supporting Dynamic Type across all platforms.
// Source: packages/kagami_design_tokens/tokens.json
//
// Colony: Crystal (e7) — Verification & Polish
//

import SwiftUI

// MARK: - Font Size Tokens

/// Raw font size tokens from the design system
public enum KagamiFontSize {
    /// Extra small (12pt)
    public static let xs: CGFloat = 12

    /// Small (14pt)
    public static let sm: CGFloat = 14

    /// Medium/Base (16pt)
    public static let md: CGFloat = 16

    /// Large (18pt)
    public static let lg: CGFloat = 18

    /// Extra large (20pt)
    public static let xl: CGFloat = 20

    /// Extra extra large (24pt)
    public static let xxl: CGFloat = 24

    /// Display (32pt)
    public static let display: CGFloat = 32
}

// MARK: - Font Weight Tokens

/// Font weight tokens matching system standards
public enum KagamiFontWeight {
    /// Regular weight (400)
    public static let regular: Font.Weight = .regular

    /// Medium weight (500)
    public static let medium: Font.Weight = .medium

    /// Semibold weight (600)
    public static let semibold: Font.Weight = .semibold

    /// Bold weight (700)
    public static let bold: Font.Weight = .bold
}

// MARK: - Line Height Tokens

/// Line height multipliers for text legibility
public enum KagamiLineHeight {
    /// Tight line height (1.2x)
    public static let tight: CGFloat = 1.2

    /// Normal line height (1.5x)
    public static let normal: CGFloat = 1.5

    /// Relaxed line height (1.75x)
    public static let relaxed: CGFloat = 1.75
}

// MARK: - Semantic Font Styles

/// Pre-configured font styles that support Dynamic Type across all platforms.
/// Uses Apple's semantic text styles for automatic scaling.
public struct KagamiFont {
    /// Large title - scales from 34pt
    /// Use for main screen titles
    public static func largeTitle(weight: Font.Weight = .bold) -> Font {
        .system(.largeTitle, design: .default, weight: weight)
    }

    /// Title - scales from 28pt
    /// Use for section headers
    public static func title(weight: Font.Weight = .semibold) -> Font {
        .system(.title, design: .default, weight: weight)
    }

    /// Title 2 - scales from 22pt
    /// Use for card titles
    public static func title2(weight: Font.Weight = .semibold) -> Font {
        .system(.title2, design: .default, weight: weight)
    }

    /// Title 3 - scales from 20pt
    /// Use for list item titles
    public static func title3(weight: Font.Weight = .semibold) -> Font {
        .system(.title3, design: .default, weight: weight)
    }

    /// Headline - scales from 17pt semibold
    /// Use for emphasized body text
    public static func headline() -> Font {
        .system(.headline, design: .default, weight: .semibold)
    }

    /// Body - scales from 17pt
    /// Use for primary content
    public static func body(weight: Font.Weight = .regular) -> Font {
        .system(.body, design: .default, weight: weight)
    }

    /// Callout - scales from 16pt
    /// Use for secondary content
    public static func callout(weight: Font.Weight = .regular) -> Font {
        .system(.callout, design: .default, weight: weight)
    }

    /// Subheadline - scales from 15pt
    /// Use for supporting text
    public static func subheadline(weight: Font.Weight = .regular) -> Font {
        .system(.subheadline, design: .default, weight: weight)
    }

    /// Footnote - scales from 13pt
    /// Use for metadata
    public static func footnote(weight: Font.Weight = .regular) -> Font {
        .system(.footnote, design: .default, weight: weight)
    }

    /// Caption - scales from 12pt
    /// Use for labels and timestamps
    public static func caption(weight: Font.Weight = .regular) -> Font {
        .system(.caption, design: .default, weight: weight)
    }

    /// Caption 2 - scales from 11pt
    /// Use for fine print
    public static func caption2(weight: Font.Weight = .regular) -> Font {
        .system(.caption2, design: .default, weight: weight)
    }

    /// Monospaced body text
    /// Use for code, numbers, and technical data
    public static func mono(_ style: Font.TextStyle = .body, weight: Font.Weight = .regular) -> Font {
        .system(style, design: .monospaced, weight: weight)
    }

    /// Rounded design variant
    /// Use for friendly UI elements
    public static func rounded(_ style: Font.TextStyle = .body, weight: Font.Weight = .regular) -> Font {
        .system(style, design: .rounded, weight: weight)
    }
}

// MARK: - Static Font Extensions (Fixed Sizes)

extension Font {
    /// Display title for hero elements (32pt)
    public static let kagamiDisplay = Font.system(size: KagamiFontSize.display, weight: .bold, design: .default)

    /// Headline for section titles (24pt)
    public static let kagamiHeadline = Font.system(size: KagamiFontSize.xxl, weight: .semibold, design: .default)

    /// Body text (16pt)
    public static let kagamiBody = Font.system(size: KagamiFontSize.md, weight: .regular, design: .default)

    /// Caption for labels (12pt)
    public static let kagamiCaption = Font.system(size: KagamiFontSize.xs, weight: .regular, design: .default)

    /// Monospaced for data display (14pt)
    public static let kagamiMono = Font.system(size: KagamiFontSize.sm, weight: .medium, design: .monospaced)
}

// MARK: - Spatial Typography (visionOS-compatible)

extension Font {
    /// Spatial title - larger for 3D environments (32pt)
    public static let spatialTitle = Font.system(size: 32, weight: .semibold, design: .rounded)

    /// Spatial headline - medium size for spatial UI (24pt)
    public static let spatialHeadline = Font.system(size: 24, weight: .medium, design: .rounded)

    /// Spatial body - readable in 3D space (18pt)
    public static let spatialBody = Font.system(size: 18, weight: .regular)

    /// Spatial caption - minimum legible size in space (14pt)
    public static let spatialCaption = Font.system(size: 14, weight: .regular)

    /// Spatial mono - for data in 3D (16pt)
    public static let spatialMono = Font.system(size: 16, weight: .medium, design: .monospaced)
}

// MARK: - Watch Typography (watchOS-compatible)

/// Watch-optimized fonts designed for readability at arm's length
public struct WatchFonts {
    /// Extra large for hero elements - visible at arm's length
    public static func hero(_ textStyle: Font.TextStyle = .title) -> Font {
        .system(textStyle, design: .rounded).weight(.bold)
    }

    /// Primary action labels
    public static func primary(_ textStyle: Font.TextStyle = .headline) -> Font {
        .system(textStyle, design: .rounded).weight(.semibold)
    }

    /// Secondary text
    public static func secondary(_ textStyle: Font.TextStyle = .subheadline) -> Font {
        .system(textStyle, design: .rounded)
    }

    /// Caption text - still readable
    public static func caption(_ textStyle: Font.TextStyle = .caption) -> Font {
        .system(textStyle, design: .rounded)
    }

    /// Monospaced for data (safety scores, percentages)
    public static func mono(_ textStyle: Font.TextStyle = .caption) -> Font {
        .system(textStyle, design: .monospaced).weight(.medium)
    }
}
