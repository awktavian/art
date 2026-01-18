//
// KagamiTVTests.swift -- Unit Tests for Kagami tvOS
//
// Colony: Crystal (e7) -- Verification
//
// h(x) >= 0. Always.
//

import XCTest
@testable import KagamiTV
import KagamiCore
import KagamiDesign
import SwiftUI

final class KagamiTVTests: XCTestCase {

    // MARK: - Circuit Breaker Tests

    @MainActor
    func testCircuitBreakerInitialState() async {
        let breaker = CircuitBreaker.shared
        breaker.reset()

        XCTAssertEqual(breaker.state, .closed)
        XCTAssertTrue(breaker.allowRequest())
        XCTAssertFalse(breaker.isOpen)
    }

    @MainActor
    func testCircuitBreakerOpensAfterThreshold() async {
        let breaker = CircuitBreaker.shared
        breaker.reset()

        // Record failures up to threshold
        for _ in 0..<CircuitBreaker.failureThreshold {
            breaker.recordFailure()
        }

        XCTAssertEqual(breaker.state, .open)
        XCTAssertTrue(breaker.isOpen)
        XCTAssertFalse(breaker.allowRequest())
    }

    @MainActor
    func testCircuitBreakerResetsOnSuccess() async {
        let breaker = CircuitBreaker.shared
        breaker.reset()

        // Record some failures (but not enough to open)
        breaker.recordFailure()
        breaker.recordFailure()

        // Then success
        breaker.recordSuccess()

        XCTAssertEqual(breaker.state, .closed)
        XCTAssertEqual(breaker.consecutiveFailures, 0)
    }

    // MARK: - Action Priority Tests

    func testActionPriorityInference() {
        XCTAssertEqual(ActionPriority.from(actionType: "lockAll"), .safety)
        XCTAssertEqual(ActionPriority.from(actionType: "fireplace_off"), .safety)
        XCTAssertEqual(ActionPriority.from(actionType: "movie_mode"), .scenes)
        XCTAssertEqual(ActionPriority.from(actionType: "goodnight"), .scenes)
        XCTAssertEqual(ActionPriority.from(actionType: "setLights"), .lights)
        XCTAssertEqual(ActionPriority.from(actionType: "openShades"), .shades)
        XCTAssertEqual(ActionPriority.from(actionType: "setThermostat"), .climate)
        XCTAssertEqual(ActionPriority.from(actionType: "announce"), .other)
    }

    func testActionPriorityComparison() {
        XCTAssertTrue(ActionPriority.safety > ActionPriority.scenes)
        XCTAssertTrue(ActionPriority.scenes > ActionPriority.lights)
        XCTAssertTrue(ActionPriority.lights > ActionPriority.shades)
        XCTAssertTrue(ActionPriority.shades > ActionPriority.climate)
        XCTAssertTrue(ActionPriority.climate > ActionPriority.other)
    }

    // MARK: - Pending Action Tests

    func testPendingActionCreation() {
        let action = PendingAction(
            actionType: "setLights",
            endpoint: "/home/lights",
            bodyDict: ["level": 50],
            parameters: ["room": "Living Room"]
        )

        XCTAssertEqual(action.actionType, "setLights")
        XCTAssertEqual(action.endpoint, "/home/lights")
        XCTAssertEqual(action.priority, .lights)
        XCTAssertEqual(action.retryCount, 0)
        XCTAssertFalse(action.hasExceededRetries)
    }

    func testPendingActionRetryLimit() {
        var action = PendingAction(
            actionType: "test",
            endpoint: "/test"
        )

        // Simulate retries
        for _ in 0..<OfflineQueueService.maxRetryAttempts {
            action.retryCount += 1
        }

        XCTAssertTrue(action.hasExceededRetries)
    }

    // MARK: - Room Model Tests

    func testRoomModelLightLevel() {
        let room = RoomModel(
            id: "1",
            name: "Living Room",
            floor: "Main Floor",
            lightLevel: 75
        )

        XCTAssertEqual(room.avgLightLevel, 75)
        XCTAssertEqual(room.lightState, "On")
        XCTAssertTrue(room.occupied)
    }

    func testRoomModelDimState() {
        let room = RoomModel(
            id: "2",
            name: "Bedroom",
            floor: "Upper Floor",
            lightLevel: 30
        )

        XCTAssertEqual(room.avgLightLevel, 30)
        XCTAssertEqual(room.lightState, "Dim")
    }

    func testRoomModelOffState() {
        let room = RoomModel(
            id: "3",
            name: "Office",
            floor: "Main Floor",
            lightLevel: 0
        )

        XCTAssertEqual(room.avgLightLevel, 0)
        XCTAssertEqual(room.lightState, "Off")
        XCTAssertFalse(room.occupied)
    }

    // MARK: - Discovered Hub Tests

    func testDiscoveredHubURL() {
        let hub = DiscoveredHub(
            id: "test-hub",
            name: "Kagami Hub",
            host: "192.168.1.100",
            port: 8001
        )

        XCTAssertEqual(hub.url, "http://192.168.1.100:8001")
    }

    func testDiscoveredHubEquality() {
        let hub1 = DiscoveredHub(id: "hub-1", name: "Hub 1", host: "192.168.1.100", port: 8001)
        let hub2 = DiscoveredHub(id: "hub-1", name: "Hub 1 Updated", host: "192.168.1.101", port: 8002)
        let hub3 = DiscoveredHub(id: "hub-2", name: "Hub 2", host: "192.168.1.100", port: 8001)

        XCTAssertEqual(hub1, hub2) // Same ID
        XCTAssertNotEqual(hub1, hub3) // Different ID
    }

    // MARK: - Design System Tests

    func testTVDesignTokensSpacing() {
        // Verify spacing follows 8pt grid
        XCTAssertTrue(TVDesignTokens.spaceXS.truncatingRemainder(dividingBy: 8) == 0)
        XCTAssertTrue(TVDesignTokens.spaceSM.truncatingRemainder(dividingBy: 8) == 0)
        XCTAssertTrue(TVDesignTokens.spaceMD.truncatingRemainder(dividingBy: 8) == 0)
        XCTAssertTrue(TVDesignTokens.spaceLG.truncatingRemainder(dividingBy: 8) == 0)
        XCTAssertTrue(TVDesignTokens.spaceXL.truncatingRemainder(dividingBy: 8) == 0)
    }

    func testTVDesignTokensTypographyScaling() {
        // Verify typography is scaled appropriately for 10-foot viewing
        // Minimum body text should be at least 24pt for TV
        XCTAssertGreaterThanOrEqual(TVDesignTokens.bodySize, 24)
        XCTAssertGreaterThanOrEqual(TVDesignTokens.captionSize, 20)
        XCTAssertGreaterThanOrEqual(TVDesignTokens.headlineSize, 36)
        XCTAssertGreaterThanOrEqual(TVDesignTokens.titleSize, 48)
    }

    func testTVDesignTokensFocusSize() {
        // Apple's minimum focus target is 66pt for tvOS
        XCTAssertGreaterThanOrEqual(TVDesignTokens.minimumFocusSize, 66)
        XCTAssertGreaterThanOrEqual(TVDesignTokens.buttonHeight, TVDesignTokens.minimumFocusSize)
    }

    func testTvMotionFibonacciTiming() {
        // Verify Fibonacci sequence: 144, 233, 377, 610, 987, 1597
        XCTAssertEqual(TvMotion.instant, 0.144, accuracy: 0.001)
        XCTAssertEqual(TvMotion.fast, 0.233, accuracy: 0.001)
        XCTAssertEqual(TvMotion.normal, 0.377, accuracy: 0.001)
        XCTAssertEqual(TvMotion.slow, 0.610, accuracy: 0.001)
        XCTAssertEqual(TvMotion.slower, 0.987, accuracy: 0.001)
        XCTAssertEqual(TvMotion.slowest, 1.597, accuracy: 0.001)
    }

    func testKagamiDurationFibonacci() {
        // Verify base duration tokens follow Fibonacci
        XCTAssertEqual(KagamiDuration.instant, 0.089, accuracy: 0.001)
        XCTAssertEqual(KagamiDuration.fast, 0.144, accuracy: 0.001)
        XCTAssertEqual(KagamiDuration.normal, 0.233, accuracy: 0.001)
        XCTAssertEqual(KagamiDuration.slow, 0.377, accuracy: 0.001)
        XCTAssertEqual(KagamiDuration.slower, 0.610, accuracy: 0.001)
        XCTAssertEqual(KagamiDuration.slowest, 0.987, accuracy: 0.001)
    }

    func testTVDesignDelegatesToTokens() {
        // Verify TVDesign properly delegates to TVDesignTokens
        XCTAssertEqual(TVDesign.gridSpacing, TVDesignTokens.gridSpacing)
        XCTAssertEqual(TVDesign.cardSpacing, TVDesignTokens.cardSpacing)
        XCTAssertEqual(TVDesign.buttonHeight, TVDesignTokens.buttonHeight)
        XCTAssertEqual(TVDesign.cardRadius, TVDesignTokens.cardRadius)
    }

    // MARK: - Colony Color Tests

    func testColonyEnumCoverage() {
        // Verify all 7 colonies are defined
        XCTAssertEqual(Colony.allCases.count, 7)

        // Verify each colony has unique basis index
        let indices = Colony.allCases.map { $0.basisIndex }
        XCTAssertEqual(Set(indices).count, 7)
        XCTAssertTrue(indices.contains(1)) // spark
        XCTAssertTrue(indices.contains(7)) // crystal
    }

    func testColonyColorMapping() {
        // Each colony should have a valid color
        for colony in Colony.allCases {
            let color = colony.color
            XCTAssertNotNil(color)
        }
    }

    // MARK: - Accessibility Tests

    func testMinimumTouchTargets() {
        // All interactive elements must meet 66pt minimum
        XCTAssertGreaterThanOrEqual(TVDesignTokens.minimumFocusSize, 66)
        XCTAssertGreaterThanOrEqual(TVDesignTokens.buttonHeight, 66)
        XCTAssertGreaterThanOrEqual(TVDesignTokens.cardMinHeight, 100) // Cards should be substantial
    }

    func testHighContrastColors() {
        // TV colors should use increased opacity for better visibility
        // These are validated through visual audit but we can check the tokens exist
        XCTAssertNotNil(Color.tvTextPrimary)
        XCTAssertNotNil(Color.tvTextSecondary)
        XCTAssertNotNil(Color.tvTextTertiary)
        XCTAssertNotNil(Color.tvCardBackground)
        XCTAssertNotNil(Color.tvFocusedBackground)
    }
}

// MARK: - Design System Integration Tests

final class DesignSystemIntegrationTests: XCTestCase {

    func testTVDesignConstantsAvailable() {
        // Ensure TVDesign can be accessed without crashes
        let _ = TVDesign.gridSpacing
        let _ = TVDesign.primaryColor
        let _ = TVDesign.cardBackground
    }

    func testMotionTokensAvailable() {
        // Ensure motion tokens are accessible
        let _ = TvMotion.focus
        let _ = TvMotion.card
        let _ = TvMotion.button
        let _ = TvMotion.cinematic
    }

    func testSpacingConsistency() {
        // Verify spacing increases monotonically
        let spacings = [
            TVDesignTokens.spaceXS,
            TVDesignTokens.spaceSM,
            TVDesignTokens.spaceMD,
            TVDesignTokens.spaceLG,
            TVDesignTokens.spaceXL
        ]

        for i in 1..<spacings.count {
            XCTAssertGreaterThan(spacings[i], spacings[i-1],
                "Spacing should increase: \(spacings[i]) should be > \(spacings[i-1])")
        }
    }

    func testRadiusConsistency() {
        // Verify radius increases monotonically
        XCTAssertLessThan(TVDesignTokens.radiusSM, TVDesignTokens.radiusMD)
        XCTAssertLessThan(TVDesignTokens.radiusMD, TVDesignTokens.radiusLG)
        XCTAssertLessThan(TVDesignTokens.radiusLG, TVDesignTokens.radiusXL)
    }
}
