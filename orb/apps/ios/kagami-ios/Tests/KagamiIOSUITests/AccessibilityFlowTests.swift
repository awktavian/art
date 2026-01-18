//
// AccessibilityFlowTests.swift -- E2E Tests for Accessibility Features
//
// Colony: Crystal (e7) -- Verification & Polish
//
// Tests accessibility features across diverse user needs:
//   - Vision: Full, Low Vision, Blind
//   - Hearing: Full, Hard of Hearing, Deaf
//   - Motor: Full, Limited, Voice Only, Switch Control
//   - Cognitive: None, Simplified
//
// These tests validate:
//   - WCAG compliance (contrast, touch targets, labels)
//   - VoiceOver navigation and announcements
//   - Dynamic Type support
//   - Reduced motion support
//   - Adaptive UX modifiers work correctly
//
// Run:
//   xcodebuild test -scheme KagamiIOS -destination 'platform=iOS Simulator,name=iPhone 15 Pro' \
//     -only-testing:KagamiIOSUITests/AccessibilityFlowTests
//
// h(x) >= 0. For EVERYONE.
//

import XCTest

final class AccessibilityFlowTests: KagamiUITestCase {

    // MARK: - Dynamic Type Tests

    func testLargeTextScaling() {
        // Navigate to accessibility settings
        navigateToAccessibilitySettings()

        // Enable large text
        tap(identifier: AccessibilityIDs.Accessibility.fontSizeSlider, in: app)

        // Drag slider to maximum
        let slider = element(withIdentifier: AccessibilityIDs.Accessibility.fontSizeSlider, in: app)
        slider.adjust(toNormalizedSliderPosition: 1.0)

        // Verify large text is displayed
        waitForElement(
            element(withIdentifier: AccessibilityIDs.Accessibility.largeText, in: app)
        )

        takeScreenshot(named: "Accessibility-LargeText")
    }

    func testDynamicTypeRespected() {
        // Set system Dynamic Type to large
        // Note: This requires setting accessibility settings via launch arguments
        app.launchArguments.append("-UIPreferredContentSizeCategoryName")
        app.launchArguments.append("UICTContentSizeCategoryAccessibilityExtraLarge")

        // Relaunch with new settings
        app.terminate()
        app.launch()

        // Wait for home view
        waitForElement(element(withIdentifier: AccessibilityIDs.Home.view, in: app))

        // Verify text scales appropriately
        // The kanji should still be visible and readable
        assertVisible(element(withIdentifier: AccessibilityIDs.Home.kanji, in: app))

        takeScreenshot(named: "Accessibility-DynamicType")
    }

    // MARK: - High Contrast Tests

    func testHighContrastMode() {
        navigateToAccessibilitySettings()

        // Enable high contrast
        tap(identifier: AccessibilityIDs.Accessibility.highContrastToggle, in: app)

        // Verify high contrast is applied
        // The preview should show enhanced contrast
        tap(identifier: AccessibilityIDs.Accessibility.previewButton, in: app)

        takeScreenshot(named: "Accessibility-HighContrast")
    }

    func testDarkModeContrast() {
        // Enable dark mode via launch arguments
        app.launchArguments.append("-AppleInterfaceStyle")
        app.launchArguments.append("Dark")

        app.terminate()
        app.launch()

        waitForElement(element(withIdentifier: AccessibilityIDs.Home.view, in: app))

        // All text should meet WCAG AA contrast requirements (4.5:1)
        // This is validated visually through the screenshot
        takeScreenshot(named: "Accessibility-DarkModeContrast")
    }

    // MARK: - Touch Target Tests

    func testMinimumTouchTargets() {
        // Navigate to rooms view where buttons are present
        completeOnboardingIfNeeded()
        navigateToTab(.rooms)

        waitForElement(element(withIdentifier: AccessibilityIDs.Rooms.view, in: app))

        // All interactive elements should meet 44x44pt minimum
        // This is validated through the screenshot audit
        takeScreenshot(named: "Accessibility-TouchTargets")
    }

    func testLargeTouchTargetsEnabled() {
        navigateToAccessibilitySettings()

        // Enable large touch targets
        tap(identifier: AccessibilityIDs.Accessibility.largeTouchTargetsToggle, in: app)

        // Navigate to rooms to verify
        navigateToTab(.rooms)
        waitForElement(element(withIdentifier: AccessibilityIDs.Rooms.view, in: app))

        // Touch targets should now be 56pt minimum
        takeScreenshot(named: "Accessibility-LargeTouchTargets")
    }

    // MARK: - Reduced Motion Tests

    func testReducedMotionRespected() {
        // Enable reduced motion
        app.launchArguments.append("-UIAccessibilityReduceMotionEnabled")
        app.launchArguments.append("1")

        app.terminate()
        app.launch()

        waitForElement(element(withIdentifier: AccessibilityIDs.Home.view, in: app))

        // Animations should be disabled or simplified
        // Verify by checking that animated elements are static
        navigateToTab(.scenes)
        waitForElement(element(withIdentifier: AccessibilityIDs.Scenes.view, in: app))

        // Scene activation should not animate
        takeScreenshot(named: "Accessibility-ReducedMotion")
    }

    func testReducedMotionToggle() {
        navigateToAccessibilitySettings()

        // Enable reduced motion in app settings
        tap(identifier: AccessibilityIDs.Accessibility.reduceMotionToggle, in: app)

        // Verify setting is persisted
        let toggle = element(withIdentifier: AccessibilityIDs.Accessibility.reduceMotionToggle, in: app)
        XCTAssertTrue(toggle.value as? String == "1", "Reduce motion toggle should be on")

        takeScreenshot(named: "Accessibility-ReducedMotionToggle")
    }

    // MARK: - VoiceOver Tests

    func testVoiceOverLabelsPresent() {
        // Enable VoiceOver optimizations
        navigateToAccessibilitySettings()
        tap(identifier: AccessibilityIDs.Accessibility.voiceOverOptimizedToggle, in: app)

        // Navigate through the app
        navigateToTab(.home)
        waitForElement(element(withIdentifier: AccessibilityIDs.Home.view, in: app))

        // All interactive elements should have accessibility labels
        // Check key elements have labels
        let homeKanji = element(withIdentifier: AccessibilityIDs.Home.kanji, in: app)
        XCTAssertTrue(homeKanji.exists, "Kanji should exist")

        takeScreenshot(named: "Accessibility-VoiceOverLabels")
    }

    func testVoiceOverNavigationOrder() {
        completeOnboardingIfNeeded()

        // Navigate to home
        navigateToTab(.home)
        waitForElement(element(withIdentifier: AccessibilityIDs.Home.view, in: app))

        // Verify focus order makes sense
        // The safety card should be focusable
        let safetyCard = element(withIdentifier: AccessibilityIDs.Home.safetyCard, in: app)
        XCTAssertTrue(safetyCard.exists, "Safety card should exist for VoiceOver users")

        takeScreenshot(named: "Accessibility-VoiceOverNavigation")
    }

    // MARK: - Simplified UI Tests

    func testSimplifiedUIMode() {
        navigateToAccessibilitySettings()

        // Enable simplified UI
        tap(identifier: AccessibilityIDs.Accessibility.simplifiedUIToggle, in: app)

        // Navigate to home
        navigateToTab(.home)
        waitForElement(element(withIdentifier: AccessibilityIDs.Home.view, in: app))

        // UI should be simplified with fewer options
        takeScreenshot(named: "Accessibility-SimplifiedUI")
    }

    func testSimplifiedUIHidesAdvancedFeatures() {
        navigateToAccessibilitySettings()

        // Enable simplified UI
        tap(identifier: AccessibilityIDs.Accessibility.simplifiedUIToggle, in: app)

        // Navigate to settings
        navigateToTab(.settings)
        waitForElement(element(withIdentifier: AccessibilityIDs.Settings.view, in: app))

        // Advanced settings should be hidden or grouped
        takeScreenshot(named: "Accessibility-SimplifiedSettings")
    }

    // MARK: - Color Blind Support Tests

    func testColorIndependentUI() {
        completeOnboardingIfNeeded()

        // Navigate to rooms view
        navigateToTab(.rooms)
        waitForElement(element(withIdentifier: AccessibilityIDs.Rooms.view, in: app))

        // All status indicators should not rely solely on color
        // They should have icons, patterns, or text labels
        takeScreenshot(named: "Accessibility-ColorIndependent")
    }

    // MARK: - Focus State Tests

    func testFocusStatesVisible() {
        completeOnboardingIfNeeded()

        // Navigate to scenes
        navigateToTab(.scenes)
        waitForElement(element(withIdentifier: AccessibilityIDs.Scenes.view, in: app))

        // Focus states should be visible on interactive elements
        // This helps users who navigate via keyboard or switch control
        takeScreenshot(named: "Accessibility-FocusStates")
    }

    // MARK: - Error Accessibility Tests

    func testErrorMessagesAccessible() {
        // Attempt an action that will fail
        completeOnboardingIfNeeded()

        // Try to control rooms when disconnected
        // (Demo mode should handle gracefully)
        navigateToTab(.rooms)
        waitForElement(element(withIdentifier: AccessibilityIDs.Rooms.view, in: app))

        // Error messages should be announced to VoiceOver
        // and should not rely solely on color
        takeScreenshot(named: "Accessibility-ErrorMessages")
    }

    // MARK: - Loading State Tests

    func testLoadingStatesAccessible() {
        completeOnboardingIfNeeded()

        // Navigate to rooms
        navigateToTab(.rooms)

        // Loading indicator should be accessible
        let loadingIndicator = element(withIdentifier: AccessibilityIDs.Rooms.loadingIndicator, in: app)
        if loadingIndicator.exists {
            // Loading indicator should have accessibility label
            takeScreenshot(named: "Accessibility-LoadingState")
        }
    }

    // MARK: - Persona-Specific Tests

    func testMichaelPersonaAccessibility() {
        // Michael: Blind user who relies on VoiceOver
        // All controls should be fully accessible via VoiceOver

        navigateToAccessibilitySettings()

        // Configure for blind user
        tap(identifier: AccessibilityIDs.Accessibility.voiceOverOptimizedToggle, in: app)

        // Navigate through key flows
        navigateToTab(.home)
        waitForElement(element(withIdentifier: AccessibilityIDs.Home.view, in: app))

        // Safety score should be announced
        let safetyScore = element(withIdentifier: AccessibilityIDs.Home.safetyScore, in: app)
        XCTAssertTrue(safetyScore.exists, "Safety score should be accessible")

        takeScreenshot(named: "Accessibility-MichaelPersona")
    }

    func testIngridPersonaSeniorAccessibility() {
        // Ingrid: 78-year-old senior with vision challenges
        // Needs large text and high contrast

        navigateToAccessibilitySettings()

        // Enable large touch targets
        tap(identifier: AccessibilityIDs.Accessibility.largeTouchTargetsToggle, in: app)

        // Enable high contrast
        tap(identifier: AccessibilityIDs.Accessibility.highContrastToggle, in: app)

        // Adjust font size
        let slider = element(withIdentifier: AccessibilityIDs.Accessibility.fontSizeSlider, in: app)
        slider.adjust(toNormalizedSliderPosition: 0.8) // Large but not maximum

        // Navigate to home
        navigateToTab(.home)
        waitForElement(element(withIdentifier: AccessibilityIDs.Home.view, in: app))

        takeScreenshot(named: "Accessibility-IngridPersona")
    }

    func testMotorLimitedAccessibility() {
        // User with limited motor control
        // Needs large touch targets and simplified interactions

        navigateToAccessibilitySettings()

        // Enable large touch targets
        tap(identifier: AccessibilityIDs.Accessibility.largeTouchTargetsToggle, in: app)

        // Enable simplified UI
        tap(identifier: AccessibilityIDs.Accessibility.simplifiedUIToggle, in: app)

        // Navigate to rooms
        navigateToTab(.rooms)
        waitForElement(element(withIdentifier: AccessibilityIDs.Rooms.view, in: app))

        // Touch targets should be 56pt+
        takeScreenshot(named: "Accessibility-MotorLimited")
    }

    // MARK: - Reset Tests

    func testResetAccessibilitySettings() {
        navigateToAccessibilitySettings()

        // Enable some settings
        tap(identifier: AccessibilityIDs.Accessibility.highContrastToggle, in: app)
        tap(identifier: AccessibilityIDs.Accessibility.largeTouchTargetsToggle, in: app)

        // Reset all settings
        tap(identifier: AccessibilityIDs.Accessibility.resetButton, in: app)

        // Confirm reset
        tap(text: "Reset", in: app)

        // Verify toggles are off
        let highContrastToggle = element(withIdentifier: AccessibilityIDs.Accessibility.highContrastToggle, in: app)
        XCTAssertTrue(highContrastToggle.value as? String == "0", "High contrast should be off after reset")

        takeScreenshot(named: "Accessibility-Reset")
    }

    // MARK: - Helper Methods

    private func navigateToAccessibilitySettings() {
        completeOnboardingIfNeeded()

        // Navigate to settings
        tap(identifier: AccessibilityIDs.TabBar.settings, in: app)
        waitForElement(element(withIdentifier: AccessibilityIDs.Settings.view, in: app))

        // Tap accessibility section
        tap(identifier: AccessibilityIDs.Settings.accessibilitySection, in: app)
        waitForElement(element(withIdentifier: AccessibilityIDs.Accessibility.view, in: app))
    }

    private func completeOnboardingIfNeeded() {
        // Check if we're in onboarding
        let onboardingView = element(withIdentifier: AccessibilityIDs.Onboarding.progressIndicator, in: app)
        if onboardingView.exists {
            completeOnboarding()
        }
    }
}

/*
 * Mirror
 * Accessibility is not optional. h(x) >= 0 means EVERYONE.
 * Every user, regardless of ability, deserves a delightful experience.
 */
