// swift-tools-version: 5.9
//
// Package.swift — KagamiCore
//
// Shared Swift components for all Kagami Apple platforms:
// - iOS, watchOS, visionOS, tvOS, macOS
//
// Components:
// - CircuitBreaker: Graceful network degradation pattern
// - KeychainService: Secure credential storage
//
// h(x) >= 0. Always.
//

import PackageDescription

let package = Package(
    name: "KagamiCore",
    platforms: [
        .iOS(.v16),
        .watchOS(.v9),
        .visionOS(.v1),
        .tvOS(.v16),
        .macOS(.v13)
    ],
    products: [
        .library(
            name: "KagamiCore",
            targets: ["KagamiCore"]
        ),
    ],
    dependencies: [],
    targets: [
        .target(
            name: "KagamiCore",
            dependencies: [],
            path: "Sources/KagamiCore"
        ),
        .testTarget(
            name: "KagamiCoreTests",
            dependencies: ["KagamiCore"],
            path: "Tests/KagamiCoreTests"
        ),
    ]
)
