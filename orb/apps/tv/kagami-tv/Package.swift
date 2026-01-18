// swift-tools-version: 5.9
//
// Package.swift — KagamiTV
//
// tvOS home automation on the big screen.
// Uses KagamiCore for shared components (CircuitBreaker, KeychainService).
//
// h(x) >= 0. Always.
//

import PackageDescription

let package = Package(
    name: "KagamiTV",
    platforms: [
        .tvOS(.v17),
        .macOS(.v13)  // Required for SPM dependency resolution
    ],
    products: [
        .library(
            name: "KagamiTV",
            targets: ["KagamiTV"]
        ),
    ],
    dependencies: [
        .package(path: "../../../packages/kagami-core-swift"),
        .package(name: "KagamiDesign", path: "../../../packages/kagami-design-swift"),
        .package(name: "KagamiMesh", path: "../../../packages/kagami-mesh-swift"),
    ],
    targets: [
        .target(
            name: "KagamiTV",
            dependencies: [
                .product(name: "KagamiCore", package: "kagami-core-swift"),
                .product(name: "KagamiDesign", package: "KagamiDesign"),
                .product(name: "KagamiMesh", package: "KagamiMesh"),
            ],
            path: "KagamiTV"
        ),
        .testTarget(
            name: "KagamiTVTests",
            dependencies: ["KagamiTV"],
            path: "Tests/KagamiTVTests"
        ),
    ]
)
