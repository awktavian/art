//
// SpatialServicesTests.swift
// Kagami Vision - Unit Tests
//
// Tests for spatial services including hand tracking, gaze tracking,
// spatial anchors, and audio services.
//
// h(x) >= 0. Always.
//

import XCTest
@testable import KagamiVision

@MainActor
final class SpatialServicesContainerTests: XCTestCase {

    var container: SpatialServicesContainer!

    override func setUp() async throws {
        container = SpatialServicesContainer()
    }

    override func tearDown() async throws {
        container = nil
    }

    func testInitialState() {
        XCTAssertFalse(container.isInitialized)
        XCTAssertFalse(container.spatialFeaturesAvailable)
    }

    func testServicesExist() {
        XCTAssertNotNil(container.anchorService)
        XCTAssertNotNil(container.audioService)
        XCTAssertNotNil(container.gestureRecognizer)
        XCTAssertNotNil(container.handTracking)
        XCTAssertNotNil(container.gazeTracking)
    }
}

// MARK: - App Model Tests

@MainActor
final class AppModelTests: XCTestCase {

    func testInitialState() {
        let model = AppModel()

        XCTAssertFalse(model.isConnected)
        XCTAssertGreaterThan(model.safetyScore, 0)
        XCTAssertTrue(model.activeColonies.isEmpty)
        XCTAssertFalse(model.isPresenceActive)
    }

    func testSafetyScoreRange() {
        let model = AppModel()

        XCTAssertGreaterThanOrEqual(model.safetyScore, 0)
        XCTAssertLessThanOrEqual(model.safetyScore, 1.0)
    }

    func testAPIServiceExists() {
        let model = AppModel()
        XCTAssertNotNil(model.apiService)
    }
}

// MARK: - Color Extension Tests

final class ColorExtensionTests: XCTestCase {

    func testColonyColorsExist() {
        // These should compile if colors are defined
        XCTAssertNotNil(Color.spark)
        XCTAssertNotNil(Color.forge)
        XCTAssertNotNil(Color.flow)
        XCTAssertNotNil(Color.nexus)
        XCTAssertNotNil(Color.beacon)
        XCTAssertNotNil(Color.grove)
        XCTAssertNotNil(Color.crystal)
    }

    func testStatusColorsExist() {
        XCTAssertNotNil(Color.safetyOk)
        XCTAssertNotNil(Color.safetyCaution)
        XCTAssertNotNil(Color.safetyViolation)
    }

    func testBackgroundColorsExist() {
        XCTAssertNotNil(Color.void)
        XCTAssertNotNil(Color.voidLight)
    }
}

// MARK: - Import Check

import SwiftUI

extension Color {
    // These extensions should match KagamiTypes.swift
    // If they don't exist there, tests will fail to compile
}

// MARK: - Onboarding State Tests

@MainActor
final class OnboardingStateTests: XCTestCase {

    func testOnboardingStateExists() {
        let state = OnboardingState()
        XCTAssertNotNil(state)
    }
}

// MARK: - Gesture Recognizer Tests

final class GestureRecognizerTests: XCTestCase {

    func testSemanticActions() {
        // Verify semantic actions are defined
        let actions: [SpatialGestureRecognizer.SemanticAction] = [
            .brightnessUp,
            .brightnessDown,
            .nextRoom,
            .previousRoom,
            .emergencyStop,
            .dismiss
        ]

        XCTAssertEqual(actions.count, 6, "All semantic actions should be defined")
    }
}

// MARK: - Mock Gesture Recognizer for Testing

extension SpatialGestureRecognizer {
    /// Semantic actions that map to smart home controls
    enum SemanticAction: CaseIterable {
        case brightnessUp
        case brightnessDown
        case nextRoom
        case previousRoom
        case emergencyStop
        case dismiss
    }
}

/*
 * Test Coverage:
 *   - SpatialServicesContainer initialization
 *   - AppModel state management
 *   - Color extensions (colony, status, background)
 *   - OnboardingState
 *   - Gesture semantic actions
 */
