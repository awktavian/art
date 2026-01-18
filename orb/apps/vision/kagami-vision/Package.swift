// swift-tools-version: 5.9
// Kagami Vision - visionOS Spatial Interface

import PackageDescription

let package = Package(
    name: "KagamiVision",
    defaultLocalization: "en",
    platforms: [
        .visionOS(.v1),
        .macOS(.v13)  // Required for SPM dependency resolution with KagamiDesign
    ],
    products: [
        .library(
            name: "KagamiVision",
            targets: ["KagamiVision"]
        ),
    ],
    dependencies: [
        // EmergeTools SnapshotPreviews for preview-based snapshot testing
        // NOTE: Temporarily disabled due to FlyingFox package path issue on visionOS
        // .package(url: "https://github.com/EmergeTools/SnapshotPreviews-iOS", from: "0.10.0"),
        .package(name: "KagamiDesign", path: "../../../packages/kagami-design-swift"),
        .package(name: "KagamiCore", path: "../../../packages/kagami-core-swift"),
        .package(name: "KagamiMesh", path: "../../../packages/kagami-mesh-swift"),
    ],
    targets: [
        .target(
            name: "KagamiVision",
            dependencies: [
                .product(name: "KagamiDesign", package: "KagamiDesign"),
                .product(name: "KagamiCore", package: "KagamiCore"),
                .product(name: "KagamiMesh", package: "KagamiMesh"),
            ],
            path: "KagamiVision"
        ),
        .testTarget(
            name: "KagamiVisionTests",
            dependencies: [
                "KagamiVision",
                // NOTE: SnapshotPreviewsCore temporarily disabled
            ],
            path: "Tests/KagamiVisionTests"
        ),
        .testTarget(
            name: "KagamiVisionUITests",
            dependencies: ["KagamiVision"],
            path: "Tests/KagamiVisionUITests"
        ),
    ]
)

/*
 * visionOS Spatial Design Principles:
 *   - 3D depth layers for UI hierarchy
 *   - Real-world anchors for persistent controls
 *   - Spatial audio for immersive feedback
 *   - Hand tracking for natural gestures
 *   - Eye gaze for intuitive selection
 *
 * Proxemic Zones (Hall, 1966):
 *   - Intimate (0-45cm): Private alerts
 *   - Personal (45cm-1.2m): Control panels
 *   - Social (1.2m-3.6m): Room visualizations
 *   - Public (3.6m+): Ambient awareness
 *
 */
