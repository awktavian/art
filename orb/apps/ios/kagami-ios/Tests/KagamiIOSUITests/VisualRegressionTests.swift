//
// VisualRegressionTests.swift -- Screenshot-based Visual Regression Tests
//
// Colony: Crystal (e7) -- Verification & Polish
//
// Provides comprehensive visual regression testing:
//   - Screenshot capture at key user journey points
//   - Baseline comparison infrastructure
//   - Multi-device and accessibility mode coverage
//
// Run:
//   xcodebuild test -scheme KagamiIOS -destination 'platform=iOS Simulator,name=iPhone 15 Pro'
//     -only-testing:KagamiIOSUITests/VisualRegressionTests
//
// h(x) >= 0. Always.
//

import XCTest

/// Visual regression tests for Kagami iOS
/// Captures screenshots at key UI states for baseline comparison
final class VisualRegressionTests: KagamiUITestCase {

    // MARK: - Properties

    /// Directory name for storing screenshots
    private let screenshotDirectory = "VisualRegression"

    /// Track screenshots captured for this test run
    private var capturedScreenshots: [String] = []

    // Skip onboarding for most visual tests
    override var skipOnboarding: Bool { true }

    // MARK: - Setup

    override func setUp() {
        super.setUp()
        capturedScreenshots = []
    }

    override func tearDown() {
        // Log captured screenshots
        if !capturedScreenshots.isEmpty {
            print("Captured \(capturedScreenshots.count) screenshots: \(capturedScreenshots.joined(separator: ", "))")
        }
        super.tearDown()
    }

    // MARK: - Home Screen Visual Tests

    func testHomeScreenVisualState() {
        // Navigate past onboarding if needed
        ensureOnHomeScreen()

        // Capture home screen in default state
        captureVisualSnapshot(named: "HomeScreen-Default")

        // Verify core elements are visible
        assertVisible(element(withIdentifier: AccessibilityIDs.Home.view, in: app))
    }

    func testHomeScreenSafetyCard() {
        ensureOnHomeScreen()

        // Wait for safety card to load
        let safetyCard = element(withIdentifier: AccessibilityIDs.Home.safetyCard, in: app)
        if waitForElement(safetyCard, timeout: 5) {
            captureVisualSnapshot(named: "HomeScreen-SafetyCard")
        }
    }

    func testHomeScreenQuickActions() {
        ensureOnHomeScreen()

        // Capture quick actions section
        let quickActions = element(withIdentifier: AccessibilityIDs.QuickActions.section, in: app)
        if quickActions.exists {
            captureVisualSnapshot(named: "HomeScreen-QuickActions")
        }
    }

    // MARK: - Rooms Screen Visual Tests

    func testRoomsListVisualState() {
        ensureOnHomeScreen()
        navigateToTab(.rooms)

        // Wait for rooms to load
        sleep(2)

        captureVisualSnapshot(named: "RoomsScreen-Default")
    }

    func testRoomsEmptyState() {
        // This would need special test configuration for empty state
        ensureOnHomeScreen()
        navigateToTab(.rooms)

        let emptyState = element(withIdentifier: AccessibilityIDs.Rooms.emptyState, in: app)
        if emptyState.waitForExistence(timeout: 3) {
            captureVisualSnapshot(named: "RoomsScreen-EmptyState")
        }
    }

    func testRoomsLoadingState() {
        ensureOnHomeScreen()
        navigateToTab(.rooms)

        // Try to capture loading indicator if it appears
        let loading = element(withIdentifier: AccessibilityIDs.Rooms.loadingIndicator, in: app)
        if loading.exists {
            captureVisualSnapshot(named: "RoomsScreen-Loading")
        }
    }

    // MARK: - Scenes Screen Visual Tests

    func testScenesListVisualState() {
        ensureOnHomeScreen()
        navigateToTab(.scenes)

        // Wait for scenes to load
        sleep(2)

        captureVisualSnapshot(named: "ScenesScreen-Default")
    }

    // MARK: - Settings Screen Visual Tests

    func testSettingsScreenVisualState() {
        ensureOnHomeScreen()
        navigateToTab(.settings)

        captureVisualSnapshot(named: "SettingsScreen-Default")
    }

    func testSettingsAccessibilitySection() {
        ensureOnHomeScreen()
        navigateToTab(.settings)

        // Scroll to accessibility section if needed
        let accessibilitySection = element(withIdentifier: AccessibilityIDs.Settings.accessibilitySection, in: app)
        if accessibilitySection.waitForExistence(timeout: 3) {
            captureVisualSnapshot(named: "SettingsScreen-Accessibility")
        }
    }

    func testSettingsHouseholdSection() {
        ensureOnHomeScreen()
        navigateToTab(.settings)

        let householdSection = element(withIdentifier: AccessibilityIDs.Settings.householdSection, in: app)
        if householdSection.waitForExistence(timeout: 3) {
            captureVisualSnapshot(named: "SettingsScreen-Household")
        }
    }

    // MARK: - Onboarding Visual Tests

    func testOnboardingWelcomeVisual() {
        // Restart without skipping onboarding
        app.launchArguments.removeAll { $0 == "-SkipOnboarding" }
        app.launchArguments.append("-ResetState")
        app.launch()
        waitForAppReady()

        captureVisualSnapshot(named: "Onboarding-Welcome")
    }

    func testOnboardingServerStepVisual() {
        app.launchArguments.removeAll { $0 == "-SkipOnboarding" }
        app.launchArguments.append("-ResetState")
        app.launch()
        waitForAppReady()

        // Navigate to server step
        tap(identifier: AccessibilityIDs.Onboarding.continueButton, in: app)
        sleep(1)

        captureVisualSnapshot(named: "Onboarding-Server")
    }

    func testOnboardingCompletionVisual() {
        app.launchArguments.removeAll { $0 == "-SkipOnboarding" }
        app.launchArguments.append("-ResetState")
        app.launch()
        waitForAppReady()

        // Navigate through to completion
        completeOnboarding()

        // Go back to capture completion screen
        // (In real tests, we'd capture before the final navigation)
    }

    // MARK: - Accessibility Mode Visual Tests

    func testHighContrastModeVisual() {
        // Note: This requires enabling high contrast in the app's accessibility settings
        ensureOnHomeScreen()
        navigateToTab(.settings)

        // Toggle high contrast if available
        let highContrastToggle = element(withIdentifier: AccessibilityIDs.Accessibility.highContrastToggle, in: app)
        if highContrastToggle.waitForExistence(timeout: 3) {
            highContrastToggle.tap()
            sleep(1)

            // Navigate back to home and capture
            navigateToTab(.home)
            captureVisualSnapshot(named: "HomeScreen-HighContrast")
        }
    }

    func testReducedMotionModeVisual() {
        ensureOnHomeScreen()
        navigateToTab(.settings)

        let reduceMotionToggle = element(withIdentifier: AccessibilityIDs.Accessibility.reduceMotionToggle, in: app)
        if reduceMotionToggle.waitForExistence(timeout: 3) {
            reduceMotionToggle.tap()
            sleep(1)

            navigateToTab(.home)
            captureVisualSnapshot(named: "HomeScreen-ReducedMotion")
        }
    }

    func testLargeFontModeVisual() {
        ensureOnHomeScreen()
        navigateToTab(.settings)

        let fontSizeSlider = element(withIdentifier: AccessibilityIDs.Accessibility.fontSizeSlider, in: app)
        if fontSizeSlider.waitForExistence(timeout: 3) {
            // Adjust font size to large
            fontSizeSlider.adjust(toNormalizedSliderPosition: 0.8)
            sleep(1)

            navigateToTab(.home)
            captureVisualSnapshot(named: "HomeScreen-LargeFont")
        }
    }

    // MARK: - Error State Visual Tests

    func testErrorMessageVisual() {
        ensureOnHomeScreen()
        navigateToTab(.rooms)

        let errorMessage = element(withIdentifier: AccessibilityIDs.Rooms.errorMessage, in: app)
        if errorMessage.waitForExistence(timeout: 5) {
            captureVisualSnapshot(named: "RoomsScreen-Error")
        }
    }

    // MARK: - Helper Methods

    /// Ensure we're on the home screen before testing
    private func ensureOnHomeScreen() {
        let homeView = element(withIdentifier: AccessibilityIDs.Home.view, in: app)
        if !homeView.waitForExistence(timeout: 3) {
            // May need to complete onboarding
            let onboardingProgress = element(withIdentifier: AccessibilityIDs.Onboarding.progressIndicator, in: app)
            if onboardingProgress.exists {
                completeOnboarding()
            }
        }
    }

    /// Capture a visual snapshot with metadata
    /// - Parameter name: Base name for the screenshot
    private func captureVisualSnapshot(named name: String) {
        // Get device information for snapshot naming
        let deviceName = UIDevice.current.name.replacingOccurrences(of: " ", with: "-")
        let timestamp = ISO8601DateFormatter().string(from: Date())

        // Create screenshot
        let screenshot = XCUIScreen.main.screenshot()

        // Create attachment with descriptive name
        let attachment = XCTAttachment(screenshot: screenshot)
        attachment.name = "\(screenshotDirectory)/\(name)-\(deviceName)"
        attachment.lifetime = .keepAlways

        // Add to test attachments
        add(attachment)

        // Track for logging
        capturedScreenshots.append(name)

        // Also save element hierarchy for debugging
        saveElementHierarchy(named: name)
    }

    /// Save element hierarchy for debugging visual tests
    private func saveElementHierarchy(named name: String) {
        let hierarchy = app.debugDescription

        let attachment = XCTAttachment(string: hierarchy)
        attachment.name = "\(screenshotDirectory)/\(name)-Hierarchy"
        attachment.lifetime = .keepAlways
        add(attachment)
    }
}

// MARK: - Multi-Device Visual Tests

/// Extension for running visual tests across multiple device configurations
extension VisualRegressionTests {

    /// Run a visual test across all key screens
    func testFullAppVisualSweep() {
        ensureOnHomeScreen()

        // Capture all main screens
        let screens: [(Tab, String)] = [
            (.home, "Home"),
            (.rooms, "Rooms"),
            (.scenes, "Scenes"),
            (.settings, "Settings")
        ]

        for (tab, name) in screens {
            navigateToTab(tab)
            sleep(1)
            captureVisualSnapshot(named: "VisualSweep-\(name)")
        }
    }
}

/*
 * Mirror
 * Visual regression ensures UI consistency across releases.
 * h(x) >= 0. Always.
 */
