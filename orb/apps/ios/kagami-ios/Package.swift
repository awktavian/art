// swift-tools-version: 5.9
//
// Kagami iOS — Native iOS Client
//
// Colony: Nexus (e4) — Integration
// h(x) >= 0. Always.
//

import PackageDescription

let package = Package(
    name: "KagamiIOS",
    platforms: [
        .iOS(.v17),
        .macOS(.v13)  // Required for SPM dependency resolution with KagamiDesign
    ],
    products: [
        .library(
            name: "KagamiIOS",
            targets: ["KagamiIOS"]
        ),
    ],
    dependencies: [
        .package(url: "https://github.com/pointfreeco/swift-snapshot-testing", from: "1.15.0"),
        .package(name: "KagamiDesign", path: "../../../packages/kagami-design-swift"),
        .package(name: "KagamiCore", path: "../../../packages/kagami-core-swift"),
        // CANONICAL SOURCE: Mesh SDK FFI bindings live in kagami-mesh-swift
        .package(name: "KagamiMesh", path: "../../../packages/kagami-mesh-swift"),
    ],
    targets: [
        // MARK: - Main Target
        //
        // KagamiMesh package provides all FFI bindings for kagami-mesh-sdk.
        // The compiled Rust library (libkagami_mesh_sdk.a) must be available in the
        // library search path. See packages/kagami-mesh-swift/README.md for build instructions.
        //
        .target(
            name: "KagamiIOS",
            dependencies: [
                .product(name: "KagamiDesign", package: "KagamiDesign"),
                .product(name: "KagamiCore", package: "KagamiCore"),
                .product(name: "KagamiMesh", package: "KagamiMesh"),
            ],
            path: "KagamiIOS",
            exclude: [
                // Keep README for documentation
                "Mesh/FFI/README.md",
            ],
            swiftSettings: [
                // Enable strict concurrency checking (Swift 6 readiness)
                .enableExperimentalFeature("StrictConcurrency"),
                // Treat concurrency warnings as errors for enforcement
                .unsafeFlags(["-Xfrontend", "-strict-concurrency=complete"], .when(configuration: .debug)),
            ]
        ),
        .testTarget(
            name: "KagamiIOSTests",
            dependencies: [
                "KagamiIOS",
                .product(name: "SnapshotTesting", package: "swift-snapshot-testing"),
            ],
            path: "Tests/KagamiIOSTests",
            swiftSettings: [
                .enableExperimentalFeature("StrictConcurrency"),
            ]
        ),
        .testTarget(
            name: "KagamiIOSUITests",
            dependencies: ["KagamiIOS"],
            path: "Tests/KagamiIOSUITests",
            swiftSettings: [
                .enableExperimentalFeature("StrictConcurrency"),
            ]
        ),
    ]
)

/*
 * Theory of Mind Design:
 *
 * Tim's iPhone Usage Patterns:
 *   - Glance for status
 *   - Quick actions from lock screen
 *   - Scene activation when arriving/leaving
 *   - Health data sync to Kagami
 *
 * UX Principles:
 *   1. Zero cognitive load — instant recognition
 *   2. Context-aware — actions adapt to time/location
 *   3. One tap — optimal outcome surfaces naturally
 *   4. Haptic feedback — confirm actions
 *
 * Mirror
 */
