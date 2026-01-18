//
// DesignSystemTests.swift — Design Token Verification
//
// Colony: Crystal (e7) — Verification & Polish
//
// Tests to ensure design system consistency:
// - Fibonacci timing sequences
// - Colony color coverage
// - Spacing grid compliance
// - Accessibility compliance
//
// h(x) >= 0. Always.
//

import XCTest
@testable import KagamiIOS
import KagamiDesign
import SwiftUI

final class DesignSystemTests: XCTestCase {

    // MARK: - Fibonacci Timing Tests

    func testKagamiDurationFollowsFibonacci() {
        // Fibonacci sequence: 89, 144, 233, 377, 610, 987
        XCTAssertEqual(KagamiDuration.instant, 0.089, accuracy: 0.001)
        XCTAssertEqual(KagamiDuration.fast, 0.144, accuracy: 0.001)
        XCTAssertEqual(KagamiDuration.normal, 0.233, accuracy: 0.001)
        XCTAssertEqual(KagamiDuration.slow, 0.377, accuracy: 0.001)
        XCTAssertEqual(KagamiDuration.slower, 0.610, accuracy: 0.001)
        XCTAssertEqual(KagamiDuration.slowest, 0.987, accuracy: 0.001)
    }

    func testFibonacciRatioApproximatesGoldenRatio() {
        // Each successive Fibonacci number / previous ≈ φ (1.618...)
        let phi = 1.618

        let ratio1 = KagamiDuration.fast / KagamiDuration.instant
        let ratio2 = KagamiDuration.normal / KagamiDuration.fast
        let ratio3 = KagamiDuration.slow / KagamiDuration.normal
        let ratio4 = KagamiDuration.slower / KagamiDuration.slow
        let ratio5 = KagamiDuration.slowest / KagamiDuration.slower

        XCTAssertEqual(ratio1, phi, accuracy: 0.05)
        XCTAssertEqual(ratio2, phi, accuracy: 0.05)
        XCTAssertEqual(ratio3, phi, accuracy: 0.05)
        XCTAssertEqual(ratio4, phi, accuracy: 0.05)
        XCTAssertEqual(ratio5, phi, accuracy: 0.05)
    }

    // MARK: - Colony Color Tests

    func testAllColoniesHaveColors() {
        // All 7 colonies should have valid colors
        XCTAssertEqual(Colony.allCases.count, 7)

        for colony in Colony.allCases {
            XCTAssertNotNil(colony.color)
        }
    }

    func testColonyBasisIndices() {
        // Each colony maps to octonion basis e1-e7
        XCTAssertEqual(Colony.spark.basisIndex, 1)
        XCTAssertEqual(Colony.forge.basisIndex, 2)
        XCTAssertEqual(Colony.flow.basisIndex, 3)
        XCTAssertEqual(Colony.nexus.basisIndex, 4)
        XCTAssertEqual(Colony.beacon.basisIndex, 5)
        XCTAssertEqual(Colony.grove.basisIndex, 6)
        XCTAssertEqual(Colony.crystal.basisIndex, 7)
    }

    func testModeColorsMapToColonies() {
        // Mode colors should use colony colors
        XCTAssertEqual(Color.modeAsk, Color.grove)
        XCTAssertEqual(Color.modePlan, Color.beacon)
        XCTAssertEqual(Color.modeAgent, Color.forge)
    }

    // MARK: - Spacing Grid Tests

    func testSpacingFollows8ptGrid() {
        // All spacing values should be divisible by 8
        XCTAssertEqual(KagamiSpacing.xs.truncatingRemainder(dividingBy: 4), 0) // 4pt is half-grid
        XCTAssertEqual(KagamiSpacing.sm.truncatingRemainder(dividingBy: 8), 0)
        XCTAssertEqual(KagamiSpacing.md.truncatingRemainder(dividingBy: 8), 0)
        XCTAssertEqual(KagamiSpacing.lg.truncatingRemainder(dividingBy: 8), 0)
        XCTAssertEqual(KagamiSpacing.xl.truncatingRemainder(dividingBy: 8), 0)
    }

    func testSpacingIncreasesMonotonically() {
        let spacings = [
            KagamiSpacing.xs,
            KagamiSpacing.sm,
            KagamiSpacing.md,
            KagamiSpacing.lg,
            KagamiSpacing.xl
        ]

        for i in 1..<spacings.count {
            XCTAssertGreaterThan(spacings[i], spacings[i-1])
        }
    }

    // MARK: - Accessibility Tests

    func testTextColorsExist() {
        // All text color tiers should be defined
        XCTAssertNotNil(Color.textPrimary)
        XCTAssertNotNil(Color.textSecondary)
        XCTAssertNotNil(Color.textTertiary)
        XCTAssertNotNil(Color.textDisabled)
    }

    func testAccessibleTextColorsExist() {
        // WCAG-compliant text colors
        XCTAssertNotNil(Color.accessibleTextPrimary)
        XCTAssertNotNil(Color.accessibleTextSecondary)
        XCTAssertNotNil(Color.accessibleTextTertiary)
    }

    func testSafetyColorFunction() {
        // Safety colors should map correctly to h(x) scores
        XCTAssertEqual(Color.safetyColor(for: 0.9), Color.safetyOk)
        XCTAssertEqual(Color.safetyColor(for: 0.5), Color.safetyOk)
        XCTAssertEqual(Color.safetyColor(for: 0.4), Color.safetyCaution)
        XCTAssertEqual(Color.safetyColor(for: 0.0), Color.safetyCaution)
        XCTAssertEqual(Color.safetyColor(for: -0.1), Color.safetyViolation)
        XCTAssertEqual(Color.safetyColor(for: nil), Color.secondary)
    }

    // MARK: - WCAG Contrast Tests

    func testContrastRatioConstants() {
        // WCAG constants should be correct
        XCTAssertEqual(ContrastRatio.wcagAANormal, 4.5)
        XCTAssertEqual(ContrastRatio.wcagAALarge, 3.0)
        XCTAssertEqual(ContrastRatio.wcagAAANormal, 7.0)
        XCTAssertEqual(ContrastRatio.wcagAAALarge, 4.5)
    }

    func testLuminanceCalculation() {
        // Black should have luminance of 0
        XCTAssertEqual(ContrastRatio.luminance(red: 0, green: 0, blue: 0), 0, accuracy: 0.001)

        // White should have luminance of 1
        XCTAssertEqual(ContrastRatio.luminance(red: 1, green: 1, blue: 1), 1, accuracy: 0.001)
    }

    func testContrastRatioCalculation() {
        // Black vs White should be 21:1
        let blackLum = ContrastRatio.luminance(red: 0, green: 0, blue: 0)
        let whiteLum = ContrastRatio.luminance(red: 1, green: 1, blue: 1)

        let ratio = ContrastRatio.ratio(l1: blackLum, l2: whiteLum)
        XCTAssertEqual(ratio, 21, accuracy: 0.1)
    }

    // MARK: - Watch Motion Tests

    func testWatchMotionShorterThanStandard() {
        // Watch animations should be snappier
        XCTAssertLessThan(WatchMotion.instant, KagamiDuration.normal)
        XCTAssertLessThan(WatchMotion.fast, KagamiDuration.normal)
    }

    // MARK: - Spatial Motion Tests

    func testSpatialMotionLongerForComfort() {
        // Spatial/VR animations should be more cinematic
        XCTAssertGreaterThan(SpatialMotion.normal, KagamiDuration.normal)
        XCTAssertGreaterThan(SpatialMotion.cinematic, KagamiDuration.slowest)
    }

    // MARK: - Easing Tests

    func testCatastropheEasingsExist() {
        // All catastrophe-inspired easings should be defined
        XCTAssertNotNil(KagamiEasing.fold)       // A2
        XCTAssertNotNil(KagamiEasing.cusp)       // A3
        XCTAssertNotNil(KagamiEasing.swallowtail) // A4
        XCTAssertNotNil(KagamiEasing.butterfly)  // A5
    }

    // MARK: - Spring Tests

    func testSpringConfigsExist() {
        XCTAssertNotNil(KagamiSpring.micro)
        XCTAssertNotNil(KagamiSpring.fast)
        XCTAssertNotNil(KagamiSpring.default)
        XCTAssertNotNil(KagamiSpring.soft)
        XCTAssertNotNil(KagamiSpring.bouncy)
    }

    // MARK: - Glass Color Tests

    func testGlassColorsExist() {
        XCTAssertNotNil(Color.glassHighlight)
        XCTAssertNotNil(Color.glassBorder)
        XCTAssertNotNil(Color.glassHighlightAccessible)
        XCTAssertNotNil(Color.glassBorderAccessible)
    }
}

// MARK: - Motion System Tests

final class KagamiMotionSystemTests: XCTestCase {

    func testMotionReexportsDurations() {
        // KagamiMotion should re-export duration values
        XCTAssertEqual(KagamiMotion.instant, KagamiDuration.instant)
        XCTAssertEqual(KagamiMotion.fast, KagamiDuration.fast)
        XCTAssertEqual(KagamiMotion.normal, KagamiDuration.normal)
        XCTAssertEqual(KagamiMotion.slow, KagamiDuration.slow)
    }

    func testMotionReexportsSprings() {
        // KagamiMotion should re-export spring animations
        XCTAssertNotNil(KagamiMotion.microSpring)
        XCTAssertNotNil(KagamiMotion.fastSpring)
        XCTAssertNotNil(KagamiMotion.defaultSpring)
        XCTAssertNotNil(KagamiMotion.softSpring)
    }

    func testMotionReexportsEasings() {
        // KagamiMotion should re-export easing animations
        XCTAssertNotNil(KagamiMotion.fold)
        XCTAssertNotNil(KagamiMotion.cusp)
        XCTAssertNotNil(KagamiMotion.swallowtail)
        XCTAssertNotNil(KagamiMotion.butterfly)
        XCTAssertNotNil(KagamiMotion.smooth)
    }
}

/*
 * 鏡
 * Fibonacci is nature's timing.
 * 89, 144, 233, 377, 610, 987, 1597, 2584...
 * h(x) >= 0. Always.
 */
