//
// PreviewSnapshotTests.swift
// Kagami Watch - Snapshot Tests
//
// Leverages existing #Preview declarations for comprehensive visual testing.
// Uses EmergeTools SnapshotPreviews to automatically test all 17+ previews.
//
// h(x) >= 0. Always.
//

import XCTest
import SnapshotPreviewsTesting
@testable import KagamiWatch

// MARK: - Preview Snapshot Tests

/// Automatically snapshots all #Preview declarations in KagamiWatch
///
/// This test discovers and snapshots every preview in the module, including:
/// - ContentView (main view)
/// - ColonyStatusView (colony health indicators)
/// - VoiceCommandView (voice input interface)
/// - RoomsListView (room controls)
/// - ColonyBadge (3 variants: Badge, Dots, Activity)
/// - LoginView (3 states: Unauthenticated, Authenticated, Error)
/// - ModelSelectorView (AI model selection)
/// - ColonyComplication (3 variants: Circular, Rectangular, Corner)
/// - KagamiSmartStackWidget (Smart Stack widget)
final class PreviewSnapshotTests: XCTestCase {

    /// Snapshot all previews in the module
    ///
    /// Uses SnapshotPreviews to automatically discover and test all #Preview macros.
    /// This ensures visual consistency across all UI components.
    func testAllPreviews() throws {
        let snapshots = SnapshotPreviewsTesting.snapshots(
            type: .module("KagamiWatch"),
            configuration: PreviewConfiguration(
                deviceFamily: .watch,
                displayScale: 2.0
            )
        )

        guard !snapshots.isEmpty else {
            XCTFail("No previews found in KagamiWatch module. Ensure #Preview macros are defined.")
            return
        }
        assertSnapshots(snapshots)
    }

    /// Snapshot previews by category for organized test results
    func testViewPreviews() throws {
        let viewPreviews = [
            "ContentView",
            "ColonyStatusView",
            "VoiceCommandView",
            "RoomsListView",
            "ColonyBadge",
            "ModelSelectorView"
        ]

        for previewName in viewPreviews {
            let snapshots = SnapshotPreviewsTesting.snapshots(
                type: .preview(previewName),
                configuration: PreviewConfiguration(
                    deviceFamily: .watch,
                    displayScale: 2.0
                )
            )
            assertSnapshots(snapshots)
        }
    }

    /// Snapshot login flow states
    func testLoginStatesPreviews() throws {
        let loginPreviews = [
            "Unauthenticated",
            "Authenticated",
            "Error"
        ]

        for previewName in loginPreviews {
            let snapshots = SnapshotPreviewsTesting.snapshots(
                type: .preview(previewName),
                configuration: PreviewConfiguration(
                    deviceFamily: .watch,
                    displayScale: 2.0
                )
            )
            assertSnapshots(snapshots)
        }
    }

    /// Snapshot complication previews for watch face integration
    func testComplicationPreviews() throws {
        let complicationPreviews = [
            "Circular",
            "Rectangular",
            "Corner"
        ]

        for previewName in complicationPreviews {
            let snapshots = SnapshotPreviewsTesting.snapshots(
                type: .preview(previewName),
                configuration: PreviewConfiguration(
                    deviceFamily: .watch,
                    displayScale: 2.0
                )
            )
            assertSnapshots(snapshots)
        }
    }

    /// Snapshot Smart Stack widget preview
    func testSmartStackWidgetPreview() throws {
        let snapshots = SnapshotPreviewsTesting.snapshots(
            type: .preview("Smart Stack"),
            configuration: PreviewConfiguration(
                deviceFamily: .watch,
                displayScale: 2.0
            )
        )

        assertSnapshots(snapshots)
    }

}

// MARK: - Watch Device Variants

/// Tests previews across different watch sizes
final class WatchDeviceVariantTests: XCTestCase {

    /// Test on Apple Watch Ultra 2 (49mm)
    func testUltraDisplay() throws {
        let snapshots = SnapshotPreviewsTesting.snapshots(
            type: .module("KagamiWatch"),
            configuration: PreviewConfiguration(
                deviceFamily: .watch,
                device: .appleWatchUltra2_49mm,
                displayScale: 2.0
            )
        )

        assertSnapshots(snapshots)
    }

    /// Test on Apple Watch Series 9 (45mm)
    func testSeries9LargeDisplay() throws {
        let snapshots = SnapshotPreviewsTesting.snapshots(
            type: .module("KagamiWatch"),
            configuration: PreviewConfiguration(
                deviceFamily: .watch,
                device: .appleWatchSeries9_45mm,
                displayScale: 2.0
            )
        )

        assertSnapshots(snapshots)
    }

    /// Test on Apple Watch Series 9 (41mm) - smallest supported
    func testSeries9SmallDisplay() throws {
        let snapshots = SnapshotPreviewsTesting.snapshots(
            type: .module("KagamiWatch"),
            configuration: PreviewConfiguration(
                deviceFamily: .watch,
                device: .appleWatchSeries9_41mm,
                displayScale: 2.0
            )
        )

        assertSnapshots(snapshots)
    }
}

// MARK: - Colony Theme Tests

/// Tests colony-themed views for color accuracy
final class ColonyThemeTests: XCTestCase {

    /// Verify colony badge renders correctly for all colonies
    func testColonyBadgeAllColonies() throws {
        let snapshots = SnapshotPreviewsTesting.snapshots(
            type: .preview("Colony Badge"),
            configuration: PreviewConfiguration(
                deviceFamily: .watch,
                displayScale: 2.0
            )
        )

        assertSnapshots(snapshots)
    }

    /// Verify colony dots animation states
    func testColonyDotsStates() throws {
        let snapshots = SnapshotPreviewsTesting.snapshots(
            type: .preview("Colony Dots"),
            configuration: PreviewConfiguration(
                deviceFamily: .watch,
                displayScale: 2.0
            )
        )

        assertSnapshots(snapshots)
    }

    /// Verify colony activity glance
    func testColonyActivityGlance() throws {
        let snapshots = SnapshotPreviewsTesting.snapshots(
            type: .preview("Colony Activity"),
            configuration: PreviewConfiguration(
                deviceFamily: .watch,
                displayScale: 2.0
            )
        )

        assertSnapshots(snapshots)
    }
}

// MARK: - Accessibility Tests

/// Tests accessibility variants of previews
final class WatchAccessibilityTests: XCTestCase {

    /// Test with bold text enabled
    func testBoldTextAccessibility() throws {
        let snapshots = SnapshotPreviewsTesting.snapshots(
            type: .module("KagamiWatch"),
            configuration: PreviewConfiguration(
                deviceFamily: .watch,
                displayScale: 2.0,
                accessibility: .init(
                    isBoldTextEnabled: true
                )
            )
        )

        assertSnapshots(snapshots)
    }

    /// Test with larger text sizes
    func testLargerDynamicType() throws {
        let snapshots = SnapshotPreviewsTesting.snapshots(
            type: .module("KagamiWatch"),
            configuration: PreviewConfiguration(
                deviceFamily: .watch,
                displayScale: 2.0,
                accessibility: .init(
                    preferredContentSizeCategory: .accessibilityMedium
                )
            )
        )

        assertSnapshots(snapshots)
    }

    /// Test with reduced motion preference
    func testReducedMotion() throws {
        let snapshots = SnapshotPreviewsTesting.snapshots(
            type: .module("KagamiWatch"),
            configuration: PreviewConfiguration(
                deviceFamily: .watch,
                displayScale: 2.0,
                accessibility: .init(
                    isReduceMotionEnabled: true
                )
            )
        )

        assertSnapshots(snapshots)
    }
}

/*
 * Test Coverage Summary:
 *
 * Views (17+ previews):
 *   - ContentView
 *   - ColonyStatusView
 *   - VoiceCommandView
 *   - RoomsListView
 *   - ColonyBadge (Badge, Dots, Activity)
 *   - LoginView (Unauthenticated, Authenticated, Error)
 *   - ModelSelectorView
 *   - ColonyComplication (Circular, Rectangular, Corner)
 *   - KagamiSmartStackWidget
 *
 * Device Variants:
 *   - Apple Watch Ultra 2 (49mm)
 *   - Apple Watch Series 9 (45mm)
 *   - Apple Watch Series 9 (41mm)
 *
 * Accessibility:
 *   - Bold text
 *   - Larger dynamic type
 *   - Reduced motion
 *
 */
