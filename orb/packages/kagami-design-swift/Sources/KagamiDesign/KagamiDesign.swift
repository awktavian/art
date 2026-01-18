//
// KagamiDesign.swift — Shared Design System
//
// Public exports for the Kagami Design System.
// Import this package to access all shared design tokens.
//
// Colony: Crystal (e7) — Verification & Polish
//

import SwiftUI

// This file provides the main entry point for the KagamiDesign module.
// All public types and extensions are exported from their respective files:
//
// - Colors.swift: Color tokens (colony, void, status, safety, text)
// - Typography.swift: Font tokens (KagamiFont, WatchFonts)
// - Spacing.swift: Spacing tokens (KagamiSpacing, KagamiRadius, KagamiLayout)
// - Motion.swift: Animation tokens (KagamiMotion, KagamiDuration, KagamiEasing)
//
// Usage:
//   import KagamiDesign
//
//   Text("Hello")
//       .foregroundColor(.crystal)
//       .font(KagamiFont.headline())
//       .padding(KagamiSpacing.md)
//       .animation(KagamiMotion.smooth, value: isActive)

// MARK: - Version Info

/// Design system version information
public enum KagamiDesignVersion {
    /// Current version of the design system
    public static let version = "1.0.0"

    /// Build date
    public static let buildDate = "2025-01-02"

    /// Source token file
    public static let tokenSource = "packages/kagami_design_tokens/tokens.json"
}
