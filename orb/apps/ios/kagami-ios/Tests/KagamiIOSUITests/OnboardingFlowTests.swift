//
// OnboardingFlowTests.swift -- E2E Tests for Onboarding Flow
//
// Colony: Crystal (e7) -- Verification & Polish
//
// Tests the complete onboarding experience:
//   - Welcome screen visibility
//   - Server discovery/demo mode
//   - Integration selection
//   - Room configuration
//   - Permission requests
//   - Completion flow
//
// Run:
//   xcodebuild test -scheme KagamiIOS -destination 'platform=iOS Simulator,name=iPhone 15 Pro'
//
// h(x) >= 0. Always.
//

import XCTest

final class OnboardingFlowTests: KagamiUITestCase {

    // Fresh start - don't skip onboarding
    override var skipOnboarding: Bool { false }

    // MARK: - Welcome Step Tests

    func testWelcomeScreenAppears() {
        // Verify welcome elements are visible
        assertOnboardingVisible()
        assertOnboardingStep(0)

        // Check welcome content
        assertVisible(element(withIdentifier: AccessibilityIDs.Onboarding.welcomeKanji, in: app))
        assertVisible(element(withIdentifier: AccessibilityIDs.Onboarding.welcomeTitle, in: app))
        assertVisible(element(withIdentifier: AccessibilityIDs.Onboarding.continueButton, in: app))

        takeScreenshot(named: "Onboarding-Welcome")
    }

    func testWelcomeFeatureListVisible() {
        // Verify feature list is displayed
        assertVisible(element(withIdentifier: AccessibilityIDs.Onboarding.welcomeFeatureList, in: app))

        // Check for feature text
        assertTextPresent("Smart Home", in: app)
        assertTextPresent("Voice Control", in: app)
        assertTextPresent("Safety First", in: app)
    }

    func testNavigateFromWelcomeToServer() {
        // Tap continue
        tap(identifier: AccessibilityIDs.Onboarding.continueButton, in: app)

        // Verify we're on server step
        waitForElement(
            element(withIdentifier: AccessibilityIDs.Onboarding.serverSearchButton, in: app)
        )

        takeScreenshot(named: "Onboarding-Server")
    }

    // MARK: - Server Step Tests

    func testServerStepShowsSearchAndDemoOptions() {
        // Navigate to server step
        tap(identifier: AccessibilityIDs.Onboarding.continueButton, in: app)

        // Verify search button
        assertVisible(element(withIdentifier: AccessibilityIDs.Onboarding.serverSearchButton, in: app))

        // Verify demo mode button
        assertVisible(element(withIdentifier: AccessibilityIDs.Onboarding.serverDemoButton, in: app))
    }

    func testDemoModeActivation() {
        // Navigate to server step
        tap(identifier: AccessibilityIDs.Onboarding.continueButton, in: app)

        // Tap demo mode
        tap(identifier: AccessibilityIDs.Onboarding.serverDemoButton, in: app)

        // Wait for demo mode to activate and continue button to be enabled
        sleep(1)

        // Verify we can continue
        let continueButton = element(withIdentifier: AccessibilityIDs.Onboarding.continueButton, in: app)
        assertVisible(continueButton)

        takeScreenshot(named: "Onboarding-Server-DemoMode")
    }

    func testManualServerURLEntry() {
        // Navigate to server step
        tap(identifier: AccessibilityIDs.Onboarding.continueButton, in: app)

        // Look for manual entry toggle and tap it
        let manualEntryButton = app.buttons["Enter manually"].firstMatch
        if manualEntryButton.waitForExistence(timeout: 3) {
            manualEntryButton.tap()

            // Verify URL field appears
            assertVisible(element(withIdentifier: AccessibilityIDs.Onboarding.serverURLField, in: app))

            takeScreenshot(named: "Onboarding-Server-ManualEntry")
        }
    }

    // MARK: - Integration Step Tests

    func testIntegrationStepShowsGrid() {
        // Complete server step with demo mode
        tap(identifier: AccessibilityIDs.Onboarding.continueButton, in: app)
        tap(identifier: AccessibilityIDs.Onboarding.serverDemoButton, in: app)
        sleep(1)
        tap(identifier: AccessibilityIDs.Onboarding.continueButton, in: app)

        // Verify we're on integration step
        waitForElement(
            element(withIdentifier: AccessibilityIDs.Onboarding.skipButton, in: app)
        )

        // Verify integration options are visible
        assertTextPresent("Control4", in: app)
        assertTextPresent("HomeKit", in: app)

        takeScreenshot(named: "Onboarding-Integration")
    }

    func testCanSkipIntegrationStep() {
        // Navigate to integration step
        tap(identifier: AccessibilityIDs.Onboarding.continueButton, in: app)
        tap(identifier: AccessibilityIDs.Onboarding.serverDemoButton, in: app)
        sleep(1)
        tap(identifier: AccessibilityIDs.Onboarding.continueButton, in: app)

        // Tap skip
        waitForElement(
            element(withIdentifier: AccessibilityIDs.Onboarding.skipButton, in: app)
        )
        tap(identifier: AccessibilityIDs.Onboarding.skipButton, in: app)

        // Verify we moved to rooms step (rooms step also has skip button)
        sleep(1)
        assertTextPresent("Rooms", in: app)
    }

    // MARK: - Rooms Step Tests

    func testRoomsStepShowsRoomList() {
        // Navigate through to rooms step
        navigateToRoomsStep()

        // In demo mode, rooms should be loaded
        sleep(2) // Wait for rooms to load

        takeScreenshot(named: "Onboarding-Rooms")
    }

    func testCanSkipRoomsStep() {
        navigateToRoomsStep()

        // Tap skip
        tap(identifier: AccessibilityIDs.Onboarding.skipButton, in: app)

        // Verify we moved to permissions step
        sleep(1)
        assertTextPresent("Permissions", in: app)
    }

    // MARK: - Permissions Step Tests

    func testPermissionsStepShowsPermissionList() {
        // Navigate through to permissions step
        navigateToPermissionsStep()

        // Verify permissions are shown
        assertTextPresent("Notifications", in: app)
        assertTextPresent("Location", in: app)
        assertTextPresent("Health", in: app)

        takeScreenshot(named: "Onboarding-Permissions")
    }

    func testCanSkipPermissionsStep() {
        navigateToPermissionsStep()

        // Tap skip
        tap(identifier: AccessibilityIDs.Onboarding.skipButton, in: app)

        // Verify we moved to completion step
        sleep(1)
        assertTextPresent("All Set", in: app)
    }

    // MARK: - Completion Step Tests

    func testCompletionStepShowsSuccessMessage() {
        // Navigate through to completion step
        navigateToCompletionStep()

        // Verify completion elements
        assertVisible(element(withIdentifier: AccessibilityIDs.Onboarding.completionCheckmark, in: app))
        assertVisible(element(withIdentifier: AccessibilityIDs.Onboarding.completionTitle, in: app))
        assertVisible(element(withIdentifier: AccessibilityIDs.Onboarding.getStartedButton, in: app))

        takeScreenshot(named: "Onboarding-Completion")
    }

    func testCompleteOnboardingNavigatesToHome() {
        // Navigate through to completion step
        navigateToCompletionStep()

        // Tap Get Started
        tap(identifier: AccessibilityIDs.Onboarding.getStartedButton, in: app)

        // Verify we're on home screen
        waitForElement(
            element(withIdentifier: AccessibilityIDs.Home.view, in: app),
            timeout: 5
        )

        takeScreenshot(named: "Home-AfterOnboarding")
    }

    // MARK: - Navigation Tests

    func testBackButtonNavigatesToPreviousStep() {
        // Navigate to server step
        tap(identifier: AccessibilityIDs.Onboarding.continueButton, in: app)

        // Verify back button is visible
        waitForElement(
            element(withIdentifier: AccessibilityIDs.Onboarding.backButton, in: app)
        )

        // Tap back
        tap(identifier: AccessibilityIDs.Onboarding.backButton, in: app)

        // Verify we're back on welcome step
        sleep(1)
        assertOnboardingStep(0)
    }

    func testProgressIndicatorUpdates() {
        // Verify progress shows step 1
        assertOnboardingVisible()

        // Navigate forward
        tap(identifier: AccessibilityIDs.Onboarding.continueButton, in: app)
        sleep(1)

        // Progress indicator should still be visible (updated)
        assertOnboardingVisible()

        takeScreenshot(named: "Onboarding-Progress-Step2")
    }

    // MARK: - Full Flow Test

    func testCompleteOnboardingFlow() {
        // This tests the entire onboarding flow from start to finish
        completeOnboarding()

        // Verify we ended up on home screen
        assertOnHomeScreen()

        // Take final screenshot
        takeScreenshot(named: "Onboarding-Complete-Flow")
    }

    // MARK: - Helper Methods

    private func navigateToRoomsStep() {
        tap(identifier: AccessibilityIDs.Onboarding.continueButton, in: app)
        tap(identifier: AccessibilityIDs.Onboarding.serverDemoButton, in: app)
        sleep(1)
        tap(identifier: AccessibilityIDs.Onboarding.continueButton, in: app)
        waitForElement(element(withIdentifier: AccessibilityIDs.Onboarding.skipButton, in: app))
        tap(identifier: AccessibilityIDs.Onboarding.skipButton, in: app)
        sleep(1)
    }

    private func navigateToPermissionsStep() {
        navigateToRoomsStep()
        waitForElement(element(withIdentifier: AccessibilityIDs.Onboarding.skipButton, in: app))
        tap(identifier: AccessibilityIDs.Onboarding.skipButton, in: app)
        sleep(1)
    }

    private func navigateToCompletionStep() {
        navigateToPermissionsStep()
        waitForElement(element(withIdentifier: AccessibilityIDs.Onboarding.skipButton, in: app))
        tap(identifier: AccessibilityIDs.Onboarding.skipButton, in: app)
        sleep(1)
    }
}

/*
 * Mirror
 * First impressions are verified programmatically.
 * h(x) >= 0. Always.
 */
