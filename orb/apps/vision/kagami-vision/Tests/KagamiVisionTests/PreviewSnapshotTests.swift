//
// PreviewSnapshotTests.swift
// Kagami Vision - Snapshot Tests
//
// Leverages existing #Preview declarations for comprehensive visual testing.
// Uses EmergeTools SnapshotPreviews to automatically test all 14+ previews.
//
// Spatial Design Principles tested:
//   - 3D depth layers for UI hierarchy
//   - Window styles (plain, volumetric)
//   - Immersive space elements
//
// h(x) >= 0. Always.
//

import XCTest
import SnapshotPreviewsTesting
@testable import KagamiVision

// MARK: - Preview Snapshot Tests

/// Automatically snapshots all #Preview declarations in KagamiVision
///
/// This test discovers and snapshots every preview in the module, including:
/// - ContentView (main window)
/// - FullSpatialExperienceView (immersive home experience)
/// - VisionLoginView (authentication flow)
/// - VoiceCommandView (voice input interface)
/// - ImmersiveHomeView (3D home visualization)
/// - OnboardingView (first-run experience)
/// - CommandPaletteView (quick actions)
/// - RoomVisualizationView (individual room 3D view)
/// - Spatial3DRoomView (spatial room control)
/// - RoomsView (room list)
/// - SettingsView (preferences)
/// - KagamiPresenceView (ambient orb)
/// - SpatialControlPanel (volumetric controls)
final class PreviewSnapshotTests: XCTestCase {

    /// Snapshot all previews in the module
    ///
    /// Uses SnapshotPreviews to automatically discover and test all #Preview macros.
    /// This ensures visual consistency across all UI components.
    func testAllPreviews() throws {
        let snapshots = SnapshotPreviewsTesting.snapshots(
            type: .module("KagamiVision"),
            configuration: PreviewConfiguration(
                deviceFamily: .vision,
                displayScale: 2.0
            )
        )

        guard !snapshots.isEmpty else {
            XCTFail("No previews found in KagamiVision module. Ensure #Preview macros are defined.")
            return
        }
        assertSnapshots(snapshots)
    }

    /// Snapshot main window previews
    func testMainWindowPreviews() throws {
        let windowPreviews = [
            "ContentView",
            "VoiceCommandView",
            "RoomsView",
            "SettingsView",
            "CommandPaletteView"
        ]

        for previewName in windowPreviews {
            let snapshots = SnapshotPreviewsTesting.snapshots(
                type: .preview(previewName),
                configuration: PreviewConfiguration(
                    deviceFamily: .vision,
                    displayScale: 2.0
                )
            )
            assertSnapshots(snapshots)
        }
    }

    /// Snapshot immersive space previews
    func testImmersiveSpacePreviews() throws {
        let immersivePreviews = [
            "FullSpatialExperienceView",
            "ImmersiveHomeView",
            "KagamiPresenceView",
            "Spatial3DRoomView"
        ]

        for previewName in immersivePreviews {
            let snapshots = SnapshotPreviewsTesting.snapshots(
                type: .preview(previewName),
                configuration: PreviewConfiguration(
                    deviceFamily: .vision,
                    displayScale: 2.0
                )
            )
            assertSnapshots(snapshots)
        }
    }

    /// Snapshot volumetric window previews
    func testVolumetricPreviews() throws {
        let snapshots = SnapshotPreviewsTesting.snapshots(
            type: .preview("SpatialControlPanel"),
            configuration: PreviewConfiguration(
                deviceFamily: .vision,
                displayScale: 2.0
            )
        )

        assertSnapshots(snapshots)
    }

    /// Snapshot onboarding flow
    func testOnboardingPreview() throws {
        let snapshots = SnapshotPreviewsTesting.snapshots(
            type: .preview("OnboardingView"),
            configuration: PreviewConfiguration(
                deviceFamily: .vision,
                displayScale: 2.0
            )
        )

        assertSnapshots(snapshots)
    }

    /// Snapshot login flow
    func testLoginPreview() throws {
        let snapshots = SnapshotPreviewsTesting.snapshots(
            type: .preview("VisionLoginView"),
            configuration: PreviewConfiguration(
                deviceFamily: .vision,
                displayScale: 2.0
            )
        )

        assertSnapshots(snapshots)
    }

    /// Snapshot room visualization
    func testRoomVisualizationPreview() throws {
        let snapshots = SnapshotPreviewsTesting.snapshots(
            type: .preview("RoomVisualizationView"),
            configuration: PreviewConfiguration(
                deviceFamily: .vision,
                displayScale: 2.0
            )
        )

        assertSnapshots(snapshots)
    }

}

// MARK: - Window Style Tests

/// Tests previews with different window styles
final class WindowStyleTests: XCTestCase {

    /// Test plain window style previews
    func testPlainWindowStylePreviews() throws {
        // These previews use windowStyle: .plain
        let plainWindowPreviews = [
            "ContentView",
            "VoiceCommandView",
            "RoomsView",
            "SettingsView",
            "CommandPaletteView"
        ]

        for previewName in plainWindowPreviews {
            let snapshots = SnapshotPreviewsTesting.snapshots(
                type: .preview(previewName),
                configuration: PreviewConfiguration(
                    deviceFamily: .vision,
                    displayScale: 2.0
                )
            )
            assertSnapshots(snapshots)
        }
    }
}

// MARK: - Spatial UI Component Tests

/// Tests spatial UI components for correct rendering
final class SpatialUIComponentTests: XCTestCase {

    /// Test 3D room visualization renders correctly
    func testRoomVisualization() throws {
        let snapshots = SnapshotPreviewsTesting.snapshots(
            type: .preview("RoomVisualizationView"),
            configuration: PreviewConfiguration(
                deviceFamily: .vision,
                displayScale: 2.0
            )
        )

        assertSnapshots(snapshots)
    }

    /// Test spatial control panel renders correctly
    func testSpatialControlPanel() throws {
        let snapshots = SnapshotPreviewsTesting.snapshots(
            type: .preview("SpatialControlPanel"),
            configuration: PreviewConfiguration(
                deviceFamily: .vision,
                displayScale: 2.0
            )
        )

        assertSnapshots(snapshots)
    }

    /// Test Kagami presence orb renders correctly
    func testKagamiPresence() throws {
        let snapshots = SnapshotPreviewsTesting.snapshots(
            type: .preview("KagamiPresenceView"),
            configuration: PreviewConfiguration(
                deviceFamily: .vision,
                displayScale: 2.0
            )
        )

        assertSnapshots(snapshots)
    }
}

// MARK: - Accessibility Tests

/// Tests accessibility variants of previews
final class VisionAccessibilityTests: XCTestCase {

    /// Test with bold text enabled
    func testBoldTextAccessibility() throws {
        let snapshots = SnapshotPreviewsTesting.snapshots(
            type: .module("KagamiVision"),
            configuration: PreviewConfiguration(
                deviceFamily: .vision,
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
            type: .module("KagamiVision"),
            configuration: PreviewConfiguration(
                deviceFamily: .vision,
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
            type: .module("KagamiVision"),
            configuration: PreviewConfiguration(
                deviceFamily: .vision,
                displayScale: 2.0,
                accessibility: .init(
                    isReduceMotionEnabled: true
                )
            )
        )

        assertSnapshots(snapshots)
    }

    /// Test with increased contrast
    func testIncreasedContrast() throws {
        let snapshots = SnapshotPreviewsTesting.snapshots(
            type: .module("KagamiVision"),
            configuration: PreviewConfiguration(
                deviceFamily: .vision,
                displayScale: 2.0,
                accessibility: .init(
                    isIncreaseContrastEnabled: true
                )
            )
        )

        assertSnapshots(snapshots)
    }
}

// MARK: - App Model Tests

/// Unit tests for AppModel
@MainActor
final class AppModelTests: XCTestCase {

    func testAppModelInitialization() {
        let appModel = AppModel()

        XCTAssertFalse(appModel.isConnected)
        XCTAssertTrue(appModel.safetyScore > 0)
        XCTAssertTrue(appModel.activeColonies.isEmpty)
        XCTAssertFalse(appModel.isPresenceActive)
    }
}

/*
 * Test Coverage Summary:
 *
 * Views (14+ previews):
 *   - ContentView (windowStyle: .plain)
 *   - FullSpatialExperienceView
 *   - VisionLoginView
 *   - VoiceCommandView (windowStyle: .plain)
 *   - ImmersiveHomeView
 *   - OnboardingView
 *   - CommandPaletteView (windowStyle: .plain)
 *   - RoomVisualizationView
 *   - Spatial3DRoomView
 *   - RoomsView (windowStyle: .plain)
 *   - SettingsView (windowStyle: .plain)
 *   - KagamiPresenceView
 *   - SpatialControlPanel
 *
 * Window Styles:
 *   - Plain (2D windows with glass backdrop)
 *   - Volumetric (3D volumetric controls)
 *
 * Immersion Styles:
 *   - Mixed (overlay on real world)
 *   - Progressive (gradual immersion)
 *
 * Accessibility:
 *   - Bold text
 *   - Larger dynamic type
 *   - Reduced motion
 *   - Increased contrast
 *
 */
