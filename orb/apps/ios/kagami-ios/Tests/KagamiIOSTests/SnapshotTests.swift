//
// SnapshotTests.swift -- Visual Regression Tests for Kagami iOS
//
// Colony: Crystal (e7) -- Verification & Polish
//
// Uses swift-snapshot-testing to capture screenshots of SwiftUI views.
// Snapshots are compared against baseline images in __Snapshots__/
//
// Run tests:
//   swift test --filter SnapshotTests
//
// Update baselines:
//   RECORD_MODE=1 swift test --filter SnapshotTests
//
// h(x) >= 0. Always.
//

import XCTest
import SwiftUI
import SnapshotTesting
@testable import KagamiIOS

// MARK: - Snapshot Test Configuration

extension Snapshotting where Value: SwiftUI.View, Format == UIImage {
    /// Standard iPhone 15 Pro snapshot configuration
    static var iPhone15Pro: Snapshotting {
        .image(
            precision: 0.98,
            layout: .device(config: .iPhone15Pro)
        )
    }

    /// Standard iPad Pro 11 snapshot configuration
    static var iPadPro11: Snapshotting {
        .image(
            precision: 0.98,
            layout: .device(config: .iPadPro11)
        )
    }

    /// Dark mode iPhone snapshot
    static var iPhone15ProDark: Snapshotting {
        .image(
            precision: 0.98,
            layout: .device(config: .iPhone15Pro),
            traits: UITraitCollection(userInterfaceStyle: .dark)
        )
    }
}

// MARK: - Snapshot Tests

final class SnapshotTests: XCTestCase {

    // Check if we should record new baselines
    var isRecording: Bool {
        ProcessInfo.processInfo.environment["RECORD_MODE"] == "1"
    }

    override func setUp() {
        super.setUp()
        // Recording mode is controlled via RECORD_MODE env var
        // No additional setup needed - isRecording computed property handles this
    }

    // MARK: - Onboarding Flow Snapshots

    func testWelcomeStepView() {
        let view = WelcomeStepView()
            .frame(width: 393, height: 852) // iPhone 15 Pro dimensions
            .background(Color.void)
            .preferredColorScheme(.dark)

        assertSnapshot(
            of: view,
            as: .iPhone15ProDark,
            record: isRecording,
            file: #file,
            testName: "WelcomeStep",
            line: #line
        )
    }

    func testServerStepView() {
        let stateManager = OnboardingStateManager()
        let view = ServerStepView(stateManager: stateManager)
            .frame(width: 393, height: 852)
            .background(Color.void)
            .preferredColorScheme(.dark)

        assertSnapshot(
            of: view,
            as: .iPhone15ProDark,
            record: isRecording,
            file: #file,
            testName: "ServerStep",
            line: #line
        )
    }

    func testServerStepView_Connected() {
        let stateManager = OnboardingStateManager()
        stateManager.isServerConnected = true
        // Note: Test URL for snapshot comparison - production uses HTTPS
        stateManager.serverURL = "https://kagami.local:8001"

        let view = ServerStepView(stateManager: stateManager)
            .frame(width: 393, height: 852)
            .background(Color.void)
            .preferredColorScheme(.dark)

        assertSnapshot(
            of: view,
            as: .iPhone15ProDark,
            record: isRecording,
            file: #file,
            testName: "ServerStep_Connected",
            line: #line
        )
    }

    func testIntegrationStepView() {
        let stateManager = OnboardingStateManager()
        let view = IntegrationStepView(stateManager: stateManager)
            .frame(width: 393, height: 852)
            .background(Color.void)
            .preferredColorScheme(.dark)

        assertSnapshot(
            of: view,
            as: .iPhone15ProDark,
            record: isRecording,
            file: #file,
            testName: "IntegrationStep",
            line: #line
        )
    }

    func testCompletionStepView() {
        let view = CompletionStepView(onComplete: {})
            .frame(width: 393, height: 852)
            .background(Color.void)
            .preferredColorScheme(.dark)

        assertSnapshot(
            of: view,
            as: .iPhone15ProDark,
            record: isRecording,
            file: #file,
            testName: "CompletionStep",
            line: #line
        )
    }

    // MARK: - Rooms View Snapshots

    func testRoomsView_Loading() {
        let view = RoomsView()
            .frame(width: 393, height: 852)
            .background(Color.void)
            .preferredColorScheme(.dark)

        assertSnapshot(
            of: view,
            as: .iPhone15ProDark,
            record: isRecording,
            file: #file,
            testName: "RoomsView_Loading",
            line: #line
        )
    }

    // MARK: - Scenes View Snapshots

    func testScenesView() {
        let view = ScenesView()
            .frame(width: 393, height: 852)
            .background(Color.void)
            .preferredColorScheme(.dark)

        assertSnapshot(
            of: view,
            as: .iPhone15ProDark,
            record: isRecording,
            file: #file,
            testName: "ScenesView",
            line: #line
        )
    }

    // MARK: - Component Snapshots

    func testSafetyScoreCard() {
        let view = SafetyScoreCard(score: 0.85, latencyMs: 42)
            .frame(width: 350)
            .padding()
            .background(Color.void)
            .preferredColorScheme(.dark)

        assertSnapshot(
            of: view,
            as: .image(precision: 0.98),
            record: isRecording,
            file: #file,
            testName: "SafetyScoreCard",
            line: #line
        )
    }

    func testSafetyScoreCard_Caution() {
        let view = SafetyScoreCard(score: 0.25, latencyMs: 150)
            .frame(width: 350)
            .padding()
            .background(Color.void)
            .preferredColorScheme(.dark)

        assertSnapshot(
            of: view,
            as: .image(precision: 0.98),
            record: isRecording,
            file: #file,
            testName: "SafetyScoreCard_Caution",
            line: #line
        )
    }

    func testSafetyScoreCard_Violation() {
        let view = SafetyScoreCard(score: -0.5, latencyMs: 500)
            .frame(width: 350)
            .padding()
            .background(Color.void)
            .preferredColorScheme(.dark)

        assertSnapshot(
            of: view,
            as: .image(precision: 0.98),
            record: isRecording,
            file: #file,
            testName: "SafetyScoreCard_Violation",
            line: #line
        )
    }

    func testQuickActionsSection() {
        let view = QuickActionsSection()
            .frame(width: 350)
            .padding()
            .background(Color.void)
            .preferredColorScheme(.dark)

        assertSnapshot(
            of: view,
            as: .image(precision: 0.98),
            record: isRecording,
            file: #file,
            testName: "QuickActionsSection",
            line: #line
        )
    }

    func testConnectionIndicator_Connected() {
        let view = ConnectionIndicator(isConnected: true)
            .padding(20)
            .background(Color.void)
            .preferredColorScheme(.dark)

        assertSnapshot(
            of: view,
            as: .image(precision: 0.98),
            record: isRecording,
            file: #file,
            testName: "ConnectionIndicator_Connected",
            line: #line
        )
    }

    func testConnectionIndicator_Disconnected() {
        let view = ConnectionIndicator(isConnected: false)
            .padding(20)
            .background(Color.void)
            .preferredColorScheme(.dark)

        assertSnapshot(
            of: view,
            as: .image(precision: 0.98),
            record: isRecording,
            file: #file,
            testName: "ConnectionIndicator_Disconnected",
            line: #line
        )
    }

    // MARK: - Accessibility Tests (Reduced Motion)

    func testWelcomeStepView_ReducedMotion() {
        let view = WelcomeStepView()
            .frame(width: 393, height: 852)
            .background(Color.void)
            .preferredColorScheme(.dark)
            .environment(\.accessibilityReduceMotion, true)

        assertSnapshot(
            of: view,
            as: .iPhone15ProDark,
            record: isRecording,
            file: #file,
            testName: "WelcomeStep_ReducedMotion",
            line: #line
        )
    }

    // MARK: - iPad Snapshots

    func testScenesView_iPad() {
        let view = ScenesView()
            .frame(width: 834, height: 1194) // iPad Pro 11
            .background(Color.void)
            .preferredColorScheme(.dark)

        assertSnapshot(
            of: view,
            as: .iPadPro11,
            record: isRecording,
            file: #file,
            testName: "ScenesView_iPad",
            line: #line
        )
    }
}

// MARK: - Preview Snapshot Tests

/// Tests that leverage existing #Preview macros for snapshot validation
final class PreviewSnapshotTests: XCTestCase {

    var isRecording: Bool {
        ProcessInfo.processInfo.environment["RECORD_MODE"] == "1"
    }

    // Test the accessibility modifiers preview
    func testAccessibilityModifiersPreview() {
        // This tests the preview content from AccessibilityModifiers.swift
        let view = ScrollView {
            VStack(spacing: 24) {
                Text("Touch Targets")
                    .font(KagamiFont.headline())

                HStack(spacing: 16) {
                    Button("44pt") {}
                        .minimumTouchTarget()
                        .background(Color.crystal.opacity(0.3))

                    Button("Small") {}
                        .padding(4)
                        .background(Color.spark.opacity(0.3))
                }

                Divider()

                Text("Text Contrast (WCAG AA)")
                    .font(KagamiFont.headline())

                VStack(alignment: .leading, spacing: 8) {
                    Text("Primary Text (~15:1)")
                        .highContrastText(.primary)
                    Text("Secondary Text (~7:1)")
                        .highContrastText(.secondary)
                    Text("Tertiary Text (~4.6:1)")
                        .highContrastText(.tertiary)
                }
            }
            .padding()
        }
        .frame(width: 393, height: 600)
        .background(Color.void)
        .preferredColorScheme(.dark)

        assertSnapshot(
            of: view,
            as: .image(precision: 0.98),
            record: isRecording,
            file: #file,
            testName: "AccessibilityModifiers",
            line: #line
        )
    }
}

/*
 * Mirror
 * Visual consistency is verified programmatically.
 * Every pixel serves a purpose.
 * h(x) >= 0. Always.
 */
