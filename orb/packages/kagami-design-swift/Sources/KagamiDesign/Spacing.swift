//
// Spacing.swift — Kagami Design System
//
// 8pt grid-based spacing system for consistent layouts.
// Source: packages/kagami_design_tokens/tokens.json
//
// Colony: Crystal (e7) — Verification & Polish
//

import SwiftUI

// MARK: - Spacing Tokens

/// 8pt grid-based spacing system
public enum KagamiSpacing {
    /// Base unit (8pt)
    public static let unit: CGFloat = 8

    /// Extra small spacing (4pt) - tight elements
    public static let xs: CGFloat = 4

    /// Small spacing (8pt) - compact elements
    public static let sm: CGFloat = 8

    /// Medium spacing (16pt) - default padding
    public static let md: CGFloat = 16

    /// Large spacing (24pt) - section gaps
    public static let lg: CGFloat = 24

    /// Extra large spacing (32pt) - major sections
    public static let xl: CGFloat = 32

    /// Extra extra large spacing (48pt) - page margins
    public static let xxl: CGFloat = 48
}

// MARK: - Radius Tokens

/// Corner radius tokens for consistent rounded corners
public enum KagamiRadius {
    /// Extra small radius (4pt) - subtle rounding
    public static let xs: CGFloat = 4

    /// Small radius (8pt) - buttons, tags
    public static let sm: CGFloat = 8

    /// Medium radius (12pt) - cards, inputs
    public static let md: CGFloat = 12

    /// Large radius (16pt) - modals, sheets
    public static let lg: CGFloat = 16

    /// Extra large radius (20pt) - large cards
    public static let xl: CGFloat = 20

    /// Full radius (9999pt) - pills, circles
    public static let full: CGFloat = 9999
}

// MARK: - Layout Tokens

/// Common layout dimensions
public enum KagamiLayout {
    /// Standard iOS tab bar height (49pt)
    public static let tabBarHeight: CGFloat = 49

    /// Minimum touch target size for accessibility (44pt)
    /// WCAG 2.1 AA compliant
    public static let minTouchTarget: CGFloat = 44

    /// Safe area bottom padding for iPhones with home indicator (34pt)
    public static let homeIndicatorPadding: CGFloat = 34

    /// Standard navigation bar height (44pt)
    public static let navBarHeight: CGFloat = 44

    /// Large navigation bar height (96pt)
    public static let largeNavBarHeight: CGFloat = 96

    /// Toolbar height (49pt)
    public static let toolbarHeight: CGFloat = 49

    /// Standard icon size (24pt)
    public static let iconSize: CGFloat = 24

    /// Large icon size (32pt)
    public static let iconSizeLarge: CGFloat = 32

    /// Small icon size (16pt)
    public static let iconSizeSmall: CGFloat = 16
}

// MARK: - Glass Effect Tokens

/// Glass/blur effect tokens for frosted glass UIs
public enum KagamiGlass {
    /// Thin blur radius (10pt)
    public static let blurThin: CGFloat = 10

    /// Regular blur radius (20pt)
    public static let blurRegular: CGFloat = 20

    /// Thick blur radius (40pt)
    public static let blurThick: CGFloat = 40

    /// Default glass opacity (80%)
    public static let defaultOpacity: Double = 0.8
}

// MARK: - Spectral Effect Tokens

/// Spectral/shimmer effect tokens for animations
public enum KagamiSpectral {
    /// Number of phases in spectral animation
    public static let phaseCount: Int = 7

    /// Shimmer animation duration (8s)
    public static let shimmerDuration: Double = 8.0

    /// Shimmer hover opacity (30%)
    public static let shimmerHoverOpacity: Double = 0.3

    /// Border animation duration (6s)
    public static let borderDuration: Double = 6.0
}

// MARK: - Spatial Spacing (visionOS)

/// Spacing tokens for spatial/3D interfaces (in meters)
public struct SpatialSpacing {
    /// Near distance - intimate zone (0.5m)
    public static let near: Float = 0.5

    /// Arm's reach distance (0.75m)
    public static let arm: Float = 0.75

    /// Comfortable viewing distance (1.0m)
    public static let comfort: Float = 1.0

    /// Room-scale distance (2.0m)
    public static let room: Float = 2.0

    /// Ambient/background distance (5.0m)
    public static let ambient: Float = 5.0
}

// MARK: - Spatial Window Sizes (visionOS)

/// Window size configurations for spatial viewing comfort
public struct SpatialWindowSize {
    /// Compact window for quick actions and alerts
    public static let compact = CGSize(width: 320, height: 240)

    /// Default window size optimized for spatial viewing
    public static let defaultSize = CGSize(width: 400, height: 300)

    /// Medium window for detail views
    public static let medium = CGSize(width: 500, height: 400)

    /// Large window for immersive content
    public static let large = CGSize(width: 700, height: 500)

    /// Full detail view
    public static let full = CGSize(width: 900, height: 700)
}

// MARK: - View Extensions

extension View {
    /// Applies standard Kagami padding
    public func kagamiPadding(_ edge: Edge.Set = .all, _ size: CGFloat = KagamiSpacing.md) -> some View {
        padding(edge, size)
    }

    /// Ensures minimum touch target size (44pt) for accessibility
    /// WCAG 2.1 AA compliant
    public func minimumTouchTarget() -> some View {
        frame(minWidth: KagamiLayout.minTouchTarget, minHeight: KagamiLayout.minTouchTarget)
    }

    /// Applies standard corner radius
    public func kagamiCornerRadius(_ radius: CGFloat = KagamiRadius.md) -> some View {
        clipShape(RoundedRectangle(cornerRadius: radius))
    }
}
