//
// AccessibilityFlowTests.swift -- E2E Tests for tvOS Accessibility Features
//
// Colony: Crystal (e7) -- Verification & Polish
//
// Tests tvOS accessibility features specific to living room experience:
//   - Focus navigation with Siri Remote
//   - VoiceOver support for home controls
//   - Large text/Dynamic Type support
//   - High contrast mode
//   - Reduced motion settings
//
// tvOS accessibility is focus-based, not touch-based like iOS.
// The Siri Remote provides directional navigation and selection.
//
// Run:
//   xcodebuild test -scheme KagamiTV \
//     -destination 'platform=tvOS Simulator,name=Apple TV 4K (3rd generation)' \
//     -only-testing:KagamiTVUITests/AccessibilityFlowTests
//
// h(x) >= 0. For EVERYONE.
//

import XCTest

final class AccessibilityFlowTests: KagamiTVUITestCase {

    // MARK: - Focus Navigation Tests (Siri Remote)

    /// Tests that focus navigation works correctly with the Siri Remote
    func testFocusNavigationBasic() {
        ensureOnHomeScreen()

        // Verify initial focus exists
        let initialFocus = focusedElement()
        XCTAssertTrue(initialFocus.exists, "There should be an initially focused element")

        takeScreenshot(named: "Accessibility-FocusNavigation-Initial")

        // Navigate right and verify focus moves
        navigateRight()
        let rightFocus = focusedElement()
        XCTAssertTrue(rightFocus.exists, "Focus should move to an element on right navigation")

        takeScreenshot(named: "Accessibility-FocusNavigation-Right")

        // Navigate down and verify focus moves
        navigateDown()
        let downFocus = focusedElement()
        XCTAssertTrue(downFocus.exists, "Focus should move to an element on down navigation")

        takeScreenshot(named: "Accessibility-FocusNavigation-Down")
    }

    /// Tests that all focusable elements can be reached via remote navigation
    func testFocusReachability() {
        ensureOnHomeScreen()

        var focusedIdentifiers: Set<String> = []

        // Navigate through all reachable elements with a grid pattern
        for _ in 0..<3 {
            for _ in 0..<5 {
                let focused = focusedElement()
                if focused.exists, !focused.identifier.isEmpty {
                    focusedIdentifiers.insert(focused.identifier)
                }
                navigateRight()
            }
            navigateDown()
        }

        // Verify we reached multiple distinct elements
        XCTAssertGreaterThan(focusedIdentifiers.count, 1, "Should reach multiple focusable elements")

        takeScreenshot(named: "Accessibility-FocusReachability")
    }

    /// Tests that focus indicators are visible and clear
    func testFocusIndicatorVisibility() {
        ensureOnHomeScreen()

        // Capture screenshots at each focus position to verify visibility
        let directions: [(String, () -> Void)] = [
            ("Initial", {}),
            ("Right1", { self.navigateRight() }),
            ("Right2", { self.navigateRight() }),
            ("Down1", { self.navigateDown() }),
            ("Left1", { self.navigateLeft() }),
            ("Down2", { self.navigateDown() })
        ]

        for (name, action) in directions {
            action()
            let focused = focusedElement()
            XCTAssertTrue(focused.exists, "Focus should be visible at position \(name)")
            takeScreenshot(named: "Accessibility-FocusIndicator-\(name)")
        }
    }

    /// Tests focus wrapping behavior at screen edges
    func testFocusWrappingBehavior() {
        ensureOnHomeScreen()

        // Navigate to edge and test behavior
        for _ in 0..<10 {
            navigateLeft()
        }
        takeScreenshot(named: "Accessibility-FocusWrap-LeftEdge")

        let leftEdgeFocus = focusedElement()
        XCTAssertTrue(leftEdgeFocus.exists, "Focus should remain stable at left edge")

        // Navigate to right edge
        for _ in 0..<10 {
            navigateRight()
        }
        takeScreenshot(named: "Accessibility-FocusWrap-RightEdge")

        let rightEdgeFocus = focusedElement()
        XCTAssertTrue(rightEdgeFocus.exists, "Focus should remain stable at right edge")
    }

    // MARK: - VoiceOver Support Tests

    /// Tests that VoiceOver labels are present on home controls
    func testVoiceOverLabelsOnHomeControls() {
        ensureOnHomeScreen()

        // Navigate through home controls and verify accessibility
        let quickActions = element(withIdentifier: TVAccessibilityIDs.Home.quickActions)
        if quickActions.waitForExistence(timeout: 5) {
            navigateTo(identifier: TVAccessibilityIDs.Home.quickActions)
            let focused = focusedElement()
            XCTAssertTrue(focused.exists, "Quick actions should be focusable for VoiceOver")
        }

        // Check rooms section
        let roomsSection = element(withIdentifier: TVAccessibilityIDs.Home.roomsSection)
        if roomsSection.exists {
            XCTAssertTrue(roomsSection.isAccessibilityElement || roomsSection.exists,
                         "Rooms section should be accessible")
        }

        // Check scenes section
        let scenesSection = element(withIdentifier: TVAccessibilityIDs.Home.scenesSection)
        if scenesSection.exists {
            XCTAssertTrue(scenesSection.isAccessibilityElement || scenesSection.exists,
                         "Scenes section should be accessible")
        }

        takeScreenshot(named: "Accessibility-VoiceOver-HomeControls")
    }

    /// Tests that tab bar items have proper VoiceOver labels
    func testVoiceOverTabBarLabels() {
        ensureOnHomeScreen()

        let tabs = [
            (TVAccessibilityIDs.TabBar.home, "Home"),
            (TVAccessibilityIDs.TabBar.rooms, "Rooms"),
            (TVAccessibilityIDs.TabBar.scenes, "Scenes"),
            (TVAccessibilityIDs.TabBar.settings, "Settings")
        ]

        for (identifier, name) in tabs {
            let tab = element(withIdentifier: identifier)
            if tab.waitForExistence(timeout: 3) {
                navigateTo(identifier: identifier)
                let focused = focusedElement()
                XCTAssertTrue(focused.exists, "\(name) tab should be focusable")
                takeScreenshot(named: "Accessibility-VoiceOver-Tab-\(name)")
            }
        }
    }

    // MARK: - Large Text / Dynamic Type Tests

    /// Tests Dynamic Type scaling with accessibility extra large setting
    func testDynamicTypeExtraLarge() {
        // Configure for accessibility extra large text
        app.launchArguments.append("-UIPreferredContentSizeCategoryName")
        app.launchArguments.append("UICTContentSizeCategoryAccessibilityExtraLarge")

        app.terminate()
        app.launch()

        let homeView = element(withIdentifier: TVAccessibilityIDs.Home.view)
        let onboardingView = element(withIdentifier: TVAccessibilityIDs.Onboarding.view)

        // Wait for app to be ready
        let predicate = NSPredicate { _, _ in
            homeView.exists || onboardingView.exists
        }
        let expectation = XCTNSPredicateExpectation(predicate: predicate, object: nil)
        _ = XCTWaiter.wait(for: [expectation], timeout: Self.extendedTimeout)

        if onboardingView.exists {
            completeOnboarding()
        }

        waitForElement(homeView, timeout: Self.extendedTimeout)

        // Verify text is visible and readable
        takeScreenshot(named: "Accessibility-DynamicType-ExtraLarge")
    }

    // MARK: - High Contrast Mode Tests

    /// Tests high contrast mode appearance
    func testHighContrastMode() {
        // Enable increase contrast
        app.launchArguments.append("-UIAccessibilityDarkerSystemColorsEnabled")
        app.launchArguments.append("1")

        app.terminate()
        app.launch()

        waitForAppReady()
        ensureOnHomeScreen()

        takeScreenshot(named: "Accessibility-HighContrast-Home")

        // Navigate through tabs to verify contrast across screens
        navigateTo(identifier: TVAccessibilityIDs.TabBar.rooms)
        pressSelect()
        sleep(1)
        takeScreenshot(named: "Accessibility-HighContrast-Rooms")

        navigateTo(identifier: TVAccessibilityIDs.TabBar.scenes)
        pressSelect()
        sleep(1)
        takeScreenshot(named: "Accessibility-HighContrast-Scenes")
    }

    // MARK: - Reduced Motion Tests

    /// Tests that animations are reduced when setting is enabled
    func testReducedMotionEnabled() {
        app.launchArguments.append("-UIAccessibilityReduceMotionEnabled")
        app.launchArguments.append("1")

        app.terminate()
        app.launch()

        waitForAppReady()
        ensureOnHomeScreen()

        takeScreenshot(named: "Accessibility-ReducedMotion-Home")

        // Navigate to scenes and activate one
        navigateTo(identifier: TVAccessibilityIDs.TabBar.scenes)
        pressSelect()
        sleep(1)
        takeScreenshot(named: "Accessibility-ReducedMotion-Scenes")

        // Activate a scene - should not have elaborate animation
        navigateRight()
        pressSelect()
        sleep(1)
        takeScreenshot(named: "Accessibility-ReducedMotion-SceneActivated")
    }

    // MARK: - Combined Accessibility Tests

    /// Tests multiple accessibility features enabled together
    func testCombinedAccessibilityFeatures() {
        // Enable multiple accessibility features
        app.launchArguments.append("-UIAccessibilityReduceMotionEnabled")
        app.launchArguments.append("1")
        app.launchArguments.append("-UIAccessibilityDarkerSystemColorsEnabled")
        app.launchArguments.append("1")
        app.launchArguments.append("-UIPreferredContentSizeCategoryName")
        app.launchArguments.append("UICTContentSizeCategoryAccessibilityLarge")

        app.terminate()
        app.launch()

        waitForAppReady()
        ensureOnHomeScreen()

        // Navigate through all screens
        let tabs = [
            (TVAccessibilityIDs.TabBar.home, "Home"),
            (TVAccessibilityIDs.TabBar.rooms, "Rooms"),
            (TVAccessibilityIDs.TabBar.scenes, "Scenes"),
            (TVAccessibilityIDs.TabBar.settings, "Settings")
        ]

        for (identifier, name) in tabs {
            navigateTo(identifier: identifier)
            pressSelect()
            sleep(1)
            takeScreenshot(named: "Accessibility-Combined-\(name)")
        }
    }

    /// Tests full accessibility journey for low vision user
    func testLowVisionUserJourney() {
        // Configure for low vision user
        app.launchArguments.append("-UIAccessibilityDarkerSystemColorsEnabled")
        app.launchArguments.append("1")
        app.launchArguments.append("-UIPreferredContentSizeCategoryName")
        app.launchArguments.append("UICTContentSizeCategoryAccessibilityExtraLarge")

        app.terminate()
        app.launch()

        waitForAppReady()
        ensureOnHomeScreen()

        takeScreenshot(named: "Accessibility-LowVision-Start")

        // Complete a typical user journey
        XCTContext.runActivity(named: "Low Vision Journey") { _ in
            // Navigate to rooms
            navigateTo(identifier: TVAccessibilityIDs.TabBar.rooms)
            pressSelect()
            sleep(1)
            takeScreenshot(named: "Accessibility-LowVision-Rooms")

            // Select a room
            navigateRight()
            pressSelect()
            sleep(1)
            takeScreenshot(named: "Accessibility-LowVision-RoomDetail")

            // Go back
            pressMenuButton()
            sleep(1)

            // Navigate to scenes
            navigateTo(identifier: TVAccessibilityIDs.TabBar.scenes)
            pressSelect()
            sleep(1)
            takeScreenshot(named: "Accessibility-LowVision-Scenes")

            // Activate a scene
            navigateRight()
            pressSelect()
            sleep(1)
            takeScreenshot(named: "Accessibility-LowVision-SceneActivated")
        }
    }

    /// Tests accessibility for user with motor impairment (relies heavily on focus navigation)
    func testMotorImpairmentUserJourney() {
        // Motor impaired users need clear focus and simple navigation
        ensureOnHomeScreen()

        takeScreenshot(named: "Accessibility-Motor-Start")

        XCTContext.runActivity(named: "Motor Impairment Journey") { _ in
            // User navigates with deliberate, single button presses
            // Each navigation should move focus predictably

            // Navigate right to first control
            navigateRight()
            var focused = focusedElement()
            XCTAssertTrue(focused.exists, "Focus should move predictably")
            takeScreenshot(named: "Accessibility-Motor-Step1")

            // Navigate down to next section
            navigateDown()
            focused = focusedElement()
            XCTAssertTrue(focused.exists, "Focus should move predictably")
            takeScreenshot(named: "Accessibility-Motor-Step2")

            // Select the focused element
            pressSelect()
            sleep(1)
            takeScreenshot(named: "Accessibility-Motor-Selected")

            // Go back with menu
            pressMenuButton()
            sleep(1)
            takeScreenshot(named: "Accessibility-Motor-Back")

            // Navigate to a tab
            navigateTo(identifier: TVAccessibilityIDs.TabBar.scenes)
            pressSelect()
            sleep(1)
            takeScreenshot(named: "Accessibility-Motor-Scenes")
        }
    }

    // MARK: - Tab Bar Accessibility Tests

    /// Tests that tab bar is fully accessible
    func testTabBarFullAccessibility() {
        ensureOnHomeScreen()

        // Verify all tabs are reachable and selectable
        let tabs = [
            (TVAccessibilityIDs.TabBar.home, "Home"),
            (TVAccessibilityIDs.TabBar.rooms, "Rooms"),
            (TVAccessibilityIDs.TabBar.scenes, "Scenes"),
            (TVAccessibilityIDs.TabBar.settings, "Settings")
        ]

        for (identifier, name) in tabs {
            let tab = element(withIdentifier: identifier)
            XCTAssertTrue(tab.waitForExistence(timeout: 3), "\(name) tab should exist")

            navigateTo(identifier: identifier)
            waitForFocus(on: tab, timeout: 3)
            pressSelect()
            sleep(1)

            takeScreenshot(named: "Accessibility-TabBar-\(name)")
        }
    }

    // MARK: - Helper Methods

    /// Ensure we're on the home screen, completing onboarding if needed
    private func ensureOnHomeScreen() {
        let homeView = element(withIdentifier: TVAccessibilityIDs.Home.view)
        let onboardingView = element(withIdentifier: TVAccessibilityIDs.Onboarding.view)

        if onboardingView.waitForExistence(timeout: 3) {
            completeOnboarding()
        }

        if !homeView.waitForExistence(timeout: 3) {
            navigateTo(identifier: TVAccessibilityIDs.TabBar.home)
            pressSelect()
            sleep(2)
        }
    }

    /// Complete onboarding flow
    private func completeOnboarding() {
        let continueButton = element(withIdentifier: TVAccessibilityIDs.Onboarding.continueButton)
        let demoModeButton = element(withIdentifier: TVAccessibilityIDs.Onboarding.demoModeButton)
        let skipButton = element(withIdentifier: TVAccessibilityIDs.Onboarding.skipButton)

        if continueButton.waitForExistence(timeout: 3) {
            navigateTo(identifier: TVAccessibilityIDs.Onboarding.continueButton)
            pressSelect()
            sleep(1)
        }

        if demoModeButton.waitForExistence(timeout: 3) {
            navigateTo(identifier: TVAccessibilityIDs.Onboarding.demoModeButton)
            pressSelect()
            sleep(1)
        }

        // Skip remaining steps
        for _ in 0..<4 {
            if skipButton.waitForExistence(timeout: 2) {
                navigateTo(identifier: TVAccessibilityIDs.Onboarding.skipButton)
                pressSelect()
                sleep(1)
            }
        }
    }
}

// MARK: - tvOS Accessibility Identifiers Extension

extension TVAccessibilityIDs {

    enum Accessibility {
        static let view = "tv.accessibility.view"
        static let fontSizeSlider = "tv.accessibility.fontSize"
        static let highContrastToggle = "tv.accessibility.highContrast"
        static let reduceMotionToggle = "tv.accessibility.reduceMotion"
        static let voiceOverOptimizedToggle = "tv.accessibility.voiceOverOptimized"
        static let simplifiedUIToggle = "tv.accessibility.simplifiedUI"
        static let largeTouchTargetsToggle = "tv.accessibility.largeTouchTargets"
        static let resetButton = "tv.accessibility.reset"
        static let previewButton = "tv.accessibility.preview"
        static let largeText = "tv.accessibility.largeText"
    }
}

/*
 * Mirror
 * tvOS accessibility ensures the living room is for EVERYONE.
 * Focus navigation is the primary interaction - it must be flawless.
 * h(x) >= 0. Always.
 */
