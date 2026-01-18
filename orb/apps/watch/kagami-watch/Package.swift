// swift-tools-version: 5.9
//
// Kagami Watch - Context-Aware Wrist Interface
//
// Package.swift
//

import PackageDescription

let package = Package(
    name: "KagamiWatch",
    defaultLocalization: "en",
    platforms: [
        .watchOS(.v10),
        .macOS(.v13)  // Required for SPM dependency resolution with KagamiDesign
    ],
    products: [
        .library(
            name: "KagamiWatch",
            targets: ["KagamiWatch"]
        ),
    ],
    dependencies: [
        // EmergeTools SnapshotPreviews for preview-based snapshot testing
        .package(url: "https://github.com/EmergeTools/SnapshotPreviews-iOS", from: "0.10.0"),
        .package(name: "KagamiDesign", path: "../../../packages/kagami-design-swift"),
        .package(name: "KagamiCore", path: "../../../packages/kagami-core-swift"),
        .package(name: "KagamiMesh", path: "../../../packages/kagami-mesh-swift"),
    ],
    targets: [
        .target(
            name: "KagamiWatch",
            dependencies: [
                .product(name: "KagamiDesign", package: "KagamiDesign"),
                .product(name: "KagamiCore", package: "KagamiCore"),
                .product(name: "KagamiMesh", package: "KagamiMesh"),
            ],
            path: "KagamiWatch"
        ),
        .testTarget(
            name: "KagamiWatchTests",
            dependencies: [
                "KagamiWatch",
                .product(name: "SnapshotPreviewsCore", package: "SnapshotPreviews-iOS"),
            ],
            path: "Tests/KagamiWatchTests"
        ),
    ]
)

/*
 * Theory of Mind Design:
 *
 * Tim's Watch Usage Patterns:
 *   - Morning (6-9am): Quick status check, start day
 *   - Working (9am-5pm): Occasional glances, minimal interaction
 *   - Evening (5-10pm): Coming home, movie mode, relax
 *   - Night (10pm+): Goodnight routine
 *   - Away: Security status, Tesla location
 *
 * UX Principles:
 *   1. Zero cognitive load - instant recognition
 *   2. Context-aware - actions adapt to time/location
 *   3. One tap - optimal outcome surfaces naturally
 *   4. Glance - full understanding without interaction
 *
 * Complication Philosophy:
 *   - Color = current state/mode
 *   - Icon = suggested action or active colony
 *   - Safety score always visible
 *   - Time-adaptive suggestions
 *
 * Haptic Patterns:
 *   - Success: Single confirmation tap
 *   - Scene activated: Three ascending taps
 *   - Warning: Strong pulse
 *   - Connected: Subtle double tap
 *   - Error: Two hard taps
 *   - Listening: Soft start
 *
 *
 */
