// swift-tools-version: 5.9
//
// KagamiDesign — Shared Design System for iOS, watchOS, visionOS
//
// Colony: Crystal (e7) — Verification & Polish
//
// Single source of truth for design tokens across all Apple platforms.
// Platform-specific extensions remain in each app.
//

import PackageDescription

let package = Package(
    name: "KagamiDesign",
    platforms: [
        .iOS(.v16),    // Required for Font.system(_:design:weight:)
        .tvOS(.v17),   // Apple TV with focus-based navigation
        .watchOS(.v9), // Required for Font.system(_:design:weight:)
        .visionOS(.v1),
        .macOS(.v13)   // Ventura - required for Font.system(_:design:weight:)
    ],
    products: [
        .library(
            name: "KagamiDesign",
            targets: ["KagamiDesign"]
        ),
    ],
    targets: [
        .target(
            name: "KagamiDesign",
            path: "Sources/KagamiDesign",
            swiftSettings: [
                .enableExperimentalFeature("StrictConcurrency"),
            ]
        ),
        .testTarget(
            name: "KagamiDesignTests",
            dependencies: ["KagamiDesign"],
            path: "Tests/KagamiDesignTests"
        ),
    ]
)

/*
 * Design Token Philosophy:
 *
 * This package contains ONLY cross-platform compatible tokens:
 *   - Colors (colony colors, void palette, status colors)
 *   - Typography (font definitions, semantic font styles)
 *   - Spacing (8pt grid system)
 *   - Motion (Fibonacci durations, catastrophe-inspired easings)
 *   - Radius (corner radius tokens)
 *
 * Platform-specific code stays in each app:
 *   - iOS: UIKit-specific extensions, haptic feedback
 *   - watchOS: WatchKit haptics, Always-On Display
 *   - visionOS: RealityKit materials, spatial audio, hand tracking
 *
 * Token source: packages/kagami_design_tokens/tokens.json
 */
