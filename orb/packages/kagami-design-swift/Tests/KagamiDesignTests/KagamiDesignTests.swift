//
// KagamiDesignTests.swift — Design System Tests
//
// Tests for KagamiDesign shared design tokens.
//

import XCTest
import SwiftUI
@testable import KagamiDesign

final class KagamiDesignTests: XCTestCase {

    // MARK: - Color Tests

    func testColonyColorsExist() {
        // Verify all 7 colony colors are defined
        let colonies: [Color] = [.spark, .forge, .flow, .nexus, .beacon, .grove, .crystal]
        XCTAssertEqual(colonies.count, 7, "Should have 7 colony colors")
    }

    func testColonyEnumMapsToColors() {
        // Each colony should have a corresponding color
        for colony in Colony.allCases {
            let color = colony.color
            XCTAssertNotNil(color, "\(colony.rawValue) should have a color")
        }
    }

    func testColonyBasisIndices() {
        XCTAssertEqual(Colony.spark.basisIndex, 1)
        XCTAssertEqual(Colony.forge.basisIndex, 2)
        XCTAssertEqual(Colony.flow.basisIndex, 3)
        XCTAssertEqual(Colony.nexus.basisIndex, 4)
        XCTAssertEqual(Colony.beacon.basisIndex, 5)
        XCTAssertEqual(Colony.grove.basisIndex, 6)
        XCTAssertEqual(Colony.crystal.basisIndex, 7)
    }

    func testHexColorInitializer() {
        // Test 6-character hex
        let color6 = Color(hex: "#FF6B35")
        XCTAssertNotNil(color6)

        // Test without hash
        let colorNoHash = Color(hex: "FF6B35")
        XCTAssertNotNil(colorNoHash)

        // Test 3-character hex
        let color3 = Color(hex: "#FFF")
        XCTAssertNotNil(color3)
    }

    func testSafetyColorForScore() {
        XCTAssertEqual(Color.safetyColor(for: 0.8), .safetyOk)
        XCTAssertEqual(Color.safetyColor(for: 0.5), .safetyOk)
        XCTAssertEqual(Color.safetyColor(for: 0.3), .safetyCaution)
        XCTAssertEqual(Color.safetyColor(for: 0.0), .safetyCaution)
        XCTAssertEqual(Color.safetyColor(for: -0.1), .safetyViolation)
        XCTAssertEqual(Color.safetyColor(for: nil), .secondary)
    }

    // MARK: - Spacing Tests

    func testSpacingValues() {
        XCTAssertEqual(KagamiSpacing.unit, 8)
        XCTAssertEqual(KagamiSpacing.xs, 4)
        XCTAssertEqual(KagamiSpacing.sm, 8)
        XCTAssertEqual(KagamiSpacing.md, 16)
        XCTAssertEqual(KagamiSpacing.lg, 24)
        XCTAssertEqual(KagamiSpacing.xl, 32)
        XCTAssertEqual(KagamiSpacing.xxl, 48)
    }

    func testRadiusValues() {
        XCTAssertEqual(KagamiRadius.xs, 4)
        XCTAssertEqual(KagamiRadius.sm, 8)
        XCTAssertEqual(KagamiRadius.md, 12)
        XCTAssertEqual(KagamiRadius.lg, 16)
        XCTAssertEqual(KagamiRadius.xl, 20)
        XCTAssertEqual(KagamiRadius.full, 9999)
    }

    func testLayoutValues() {
        XCTAssertEqual(KagamiLayout.minTouchTarget, 44)
        XCTAssertEqual(KagamiLayout.tabBarHeight, 49)
    }

    // MARK: - Motion Tests

    func testDurationValues() {
        // Fibonacci-based durations
        XCTAssertEqual(KagamiDuration.instant, 0.089)
        XCTAssertEqual(KagamiDuration.fast, 0.144)
        XCTAssertEqual(KagamiDuration.normal, 0.233)
        XCTAssertEqual(KagamiDuration.slow, 0.377)
        XCTAssertEqual(KagamiDuration.slower, 0.610)
        XCTAssertEqual(KagamiDuration.slowest, 0.987)
    }

    func testMotionReexports() {
        // KagamiMotion should re-export durations
        XCTAssertEqual(KagamiMotion.instant, KagamiDuration.instant)
        XCTAssertEqual(KagamiMotion.fast, KagamiDuration.fast)
        XCTAssertEqual(KagamiMotion.normal, KagamiDuration.normal)
    }

    // MARK: - Typography Tests

    func testFontSizeValues() {
        XCTAssertEqual(KagamiFontSize.xs, 12)
        XCTAssertEqual(KagamiFontSize.sm, 14)
        XCTAssertEqual(KagamiFontSize.md, 16)
        XCTAssertEqual(KagamiFontSize.lg, 18)
        XCTAssertEqual(KagamiFontSize.xl, 20)
        XCTAssertEqual(KagamiFontSize.xxl, 24)
        XCTAssertEqual(KagamiFontSize.display, 32)
    }

    func testKagamiFontCreation() {
        // Verify fonts can be created without crashing
        let _ = KagamiFont.headline()
        let _ = KagamiFont.body()
        let _ = KagamiFont.caption()
        let _ = KagamiFont.mono()
    }

    // MARK: - Version Tests

    func testVersionInfo() {
        XCTAssertFalse(KagamiDesignVersion.version.isEmpty)
        XCTAssertFalse(KagamiDesignVersion.buildDate.isEmpty)
        XCTAssertFalse(KagamiDesignVersion.tokenSource.isEmpty)
    }
}
