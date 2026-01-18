// swift-tools-version: 5.9
//
// Package.swift — KagamiMesh
//
// Unified Swift wrapper for kagami-mesh-sdk UniFFI bindings.
// Provides Ed25519 identity, XChaCha20 encryption, X25519 key exchange,
// vector clocks, and CRDTs across ALL Apple platforms.
//
// h(x) >= 0. Always.
//

import PackageDescription

let package = Package(
    name: "KagamiMesh",
    platforms: [
        .iOS(.v16),
        .watchOS(.v9),
        .visionOS(.v1),
        .tvOS(.v16),
        .macOS(.v13)
    ],
    products: [
        .library(
            name: "KagamiMesh",
            targets: ["KagamiMesh"]
        ),
    ],
    dependencies: [],
    targets: [
        // MARK: - FFI System Library Target
        //
        // This target wraps the Rust-generated UniFFI bindings for kagami-mesh-sdk.
        // The compiled static library must be built for each target architecture.
        //
        // Build commands (from packages/kagami-mesh-sdk/):
        //   # iOS
        //   cargo build --release --target aarch64-apple-ios
        //   cargo build --release --target aarch64-apple-ios-sim
        //
        //   # watchOS
        //   cargo build --release --target aarch64-apple-watchos
        //   cargo build --release --target aarch64-apple-watchos-sim
        //
        //   # tvOS
        //   cargo build --release --target aarch64-apple-tvos
        //   cargo build --release --target aarch64-apple-tvos-sim
        //
        //   # visionOS
        //   cargo build --release --target aarch64-apple-xros
        //   cargo build --release --target aarch64-apple-xros-sim
        //
        //   # macOS
        //   cargo build --release --target aarch64-apple-darwin
        //   cargo build --release --target x86_64-apple-darwin
        //
        .systemLibrary(
            name: "kagami_mesh_sdkFFI",
            path: "Sources/FFI"
        ),

        .target(
            name: "KagamiMesh",
            dependencies: [
                "kagami_mesh_sdkFFI",
            ],
            path: "Sources/KagamiMesh",
            swiftSettings: [
                // Enable strict concurrency checking (Swift 6 readiness)
                .enableExperimentalFeature("StrictConcurrency"),
            ]
        ),

        .testTarget(
            name: "KagamiMeshTests",
            dependencies: ["KagamiMesh"],
            path: "Tests/KagamiMeshTests"
        ),
    ]
)

/*
 * DRY Philosophy:
 *
 * Write cryptography once in Rust. Generate bindings. Every platform gets:
 * - Ed25519 signatures with zeroize on drop
 * - X25519 key exchange with HKDF salt "kagami-mesh-sdk-v1"
 * - XChaCha20-Poly1305 with OsRng nonces
 * - Vector clocks with automatic merge
 * - CRDTs for offline-first state sync
 *
 * One crate. All platforms. Zero duplication.
 *
 * 鏡
 */
