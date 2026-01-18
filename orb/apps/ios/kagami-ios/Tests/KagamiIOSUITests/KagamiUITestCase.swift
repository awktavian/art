//
// KagamiUITestCase.swift -- Base Test Case for Kagami iOS E2E Tests
//
// Colony: Crystal (e7) -- Verification & Polish
//
// Provides common setup and teardown for all E2E tests:
//   - App launch configuration
//   - Demo mode setup
//   - Screenshot capture on failure
//   - Accessibility identifier constants
//
// h(x) >= 0. Always.
//

import XCTest

/// Base test case for all Kagami iOS UI tests
class KagamiUITestCase: XCTestCase {

    // MARK: - Properties

    var app: XCUIApplication!

    /// Whether to run tests in demo mode (no server required)
    var useDemoMode: Bool { true }

    /// Whether to skip onboarding (use stored state)
    var skipOnboarding: Bool { false }

    /// Whether to capture screenshots on failure
    var screenshotOnFailure: Bool { true }

    // MARK: - Setup & Teardown

    override func setUp() {
        super.setUp()

        // Stop immediately when a failure occurs
        continueAfterFailure = false

        // Initialize the app
        app = XCUIApplication()

        // Configure launch arguments
        configureLaunchArguments()

        // Launch the app
        app.launch()

        // Wait for app to be ready
        waitForAppReady()
    }

    override func tearDown() {
        // Take screenshot on failure
        if screenshotOnFailure && testRun?.hasSucceeded == false {
            takeScreenshotOnFailure()
        }

        app.terminate()
        app = nil

        super.tearDown()
    }

    // MARK: - Configuration

    /// Configure launch arguments for the app
    func configureLaunchArguments() {
        // Enable UI testing mode
        app.launchArguments.append("-UITesting")

        // Configure demo mode
        if useDemoMode {
            app.launchArguments.append("-DemoMode")
        }

        // Skip onboarding if needed
        if skipOnboarding {
            app.launchArguments.append("-SkipOnboarding")
        }

        // Disable animations for faster tests
        app.launchArguments.append("-DisableAnimations")

        // Reset state for clean tests
        app.launchArguments.append("-ResetState")
    }

    /// Wait for the app to be ready for interaction
    func waitForAppReady() {
        // Wait for either onboarding or main content to appear
        let onboardingView = app.descendants(matching: .any)
            .matching(identifier: AccessibilityIDs.Onboarding.progressIndicator).firstMatch
        let homeView = app.descendants(matching: .any)
            .matching(identifier: AccessibilityIDs.Home.view).firstMatch

        let predicate = NSPredicate { _, _ in
            onboardingView.exists || homeView.exists
        }

        let expectation = XCTNSPredicateExpectation(predicate: predicate, object: nil)
        let result = XCTWaiter.wait(for: [expectation], timeout: 10)

        if result != .completed {
            XCTFail("App did not become ready within 10 seconds")
        }
    }

    // MARK: - Common Actions

    /// Complete onboarding flow using demo mode
    func completeOnboarding() {
        // Step 1: Welcome - tap Continue
        tap(identifier: AccessibilityIDs.Onboarding.continueButton, in: app)

        // Step 2: Server - tap Demo Mode
        waitForElement(
            element(withIdentifier: AccessibilityIDs.Onboarding.serverDemoButton, in: app)
        )
        tap(identifier: AccessibilityIDs.Onboarding.serverDemoButton, in: app)

        // Wait for demo mode to activate
        sleep(1)

        // Tap Continue
        tap(identifier: AccessibilityIDs.Onboarding.continueButton, in: app)

        // Step 3: Integration - Skip
        waitForElement(
            element(withIdentifier: AccessibilityIDs.Onboarding.skipButton, in: app)
        )
        tap(identifier: AccessibilityIDs.Onboarding.skipButton, in: app)

        // Step 4: Rooms - Skip
        waitForElement(
            element(withIdentifier: AccessibilityIDs.Onboarding.skipButton, in: app)
        )
        tap(identifier: AccessibilityIDs.Onboarding.skipButton, in: app)

        // Step 5: Permissions - Skip
        waitForElement(
            element(withIdentifier: AccessibilityIDs.Onboarding.skipButton, in: app)
        )
        tap(identifier: AccessibilityIDs.Onboarding.skipButton, in: app)

        // Step 6: Completion - Get Started
        waitForElement(
            element(withIdentifier: AccessibilityIDs.Onboarding.getStartedButton, in: app)
        )
        tap(identifier: AccessibilityIDs.Onboarding.getStartedButton, in: app)

        // Wait for home view
        waitForElement(
            element(withIdentifier: AccessibilityIDs.Home.view, in: app),
            timeout: 5
        )
    }

    /// Navigate to a specific tab
    func navigateToTab(_ tab: Tab) {
        let identifier: String
        switch tab {
        case .home:
            identifier = AccessibilityIDs.TabBar.home
        case .rooms:
            identifier = AccessibilityIDs.TabBar.rooms
        case .hub:
            identifier = AccessibilityIDs.TabBar.hub
        case .scenes:
            identifier = AccessibilityIDs.TabBar.scenes
        case .settings:
            identifier = AccessibilityIDs.TabBar.settings
        }
        tap(identifier: identifier, in: app)
    }

    enum Tab {
        case home, rooms, hub, scenes, settings
    }

    // MARK: - Assertions

    /// Assert that we are on the home screen
    func assertOnHomeScreen() {
        assertVisible(element(withIdentifier: AccessibilityIDs.Home.view, in: app))
    }

    /// Assert that onboarding is showing
    func assertOnboardingVisible() {
        assertVisible(element(withIdentifier: AccessibilityIDs.Onboarding.progressIndicator, in: app))
    }

    /// Assert that a specific onboarding step is showing
    func assertOnboardingStep(_ step: Int) {
        let stepIdentifier = AccessibilityIDs.Onboarding.step(step)
        assertVisible(element(withIdentifier: stepIdentifier, in: app))
    }
}

// MARK: - Accessibility Identifier Constants

/// Mirror of AccessibilityIdentifiers for use in UI tests
/// (Since UI tests can't import the main target directly)
enum AccessibilityIDs {

    enum Onboarding {
        static let progressIndicator = "onboarding.progress"
        static let skipButton = "onboarding.skip"
        static let backButton = "onboarding.back"
        static let continueButton = "onboarding.continue"
        static let getStartedButton = "onboarding.getStarted"

        static let welcomeKanji = "onboarding.welcome.kanji"
        static let welcomeTitle = "onboarding.welcome.title"
        static let welcomeSubtitle = "onboarding.welcome.subtitle"
        static let welcomeFeatureList = "onboarding.welcome.features"

        static let serverSearchButton = "onboarding.server.search"
        static let serverURLField = "onboarding.server.urlField"
        static let serverDemoButton = "onboarding.server.demo"
        static let serverConnectionStatus = "onboarding.server.status"

        static let integrationGrid = "onboarding.integration.grid"
        static let integrationTestButton = "onboarding.integration.test"
        static let integrationStatus = "onboarding.integration.status"

        static let roomsList = "onboarding.rooms.list"
        static let roomsSelectAll = "onboarding.rooms.selectAll"

        static let permissionsList = "onboarding.permissions.list"
        static let permissionsEnableAll = "onboarding.permissions.enableAll"

        static let completionCheckmark = "onboarding.completion.checkmark"
        static let completionTitle = "onboarding.completion.title"

        static func step(_ step: Int) -> String {
            "onboarding.step.\(step)"
        }

        static func integrationCard(_ id: String) -> String {
            "onboarding.integration.card.\(id)"
        }

        static func roomToggle(_ roomId: String) -> String {
            "onboarding.rooms.toggle.\(roomId)"
        }

        static func permissionRow(_ permissionId: String) -> String {
            "onboarding.permissions.row.\(permissionId)"
        }
    }

    enum Home {
        static let view = "home.view"
        static let kanji = "home.kanji"
        static let safetyCard = "home.safetyCard"
        static let safetyScore = "home.safetyScore"
        static let heroAction = "home.heroAction"
        static let quickActions = "home.quickActions"
        static let connectionIndicator = "home.connectionIndicator"
    }

    enum Rooms {
        static let view = "rooms.view"
        static let list = "rooms.list"
        static let refreshButton = "rooms.refresh"
        static let emptyState = "rooms.emptyState"
        static let loadingIndicator = "rooms.loading"
        static let errorMessage = "rooms.error"
        static let retryButton = "rooms.retry"

        static func row(_ roomId: String) -> String {
            "rooms.row.\(roomId)"
        }

        static func lightButton(_ roomId: String, level: String) -> String {
            "rooms.row.\(roomId).light.\(level)"
        }
    }

    enum Scenes {
        static let view = "scenes.view"
        static let list = "scenes.list"

        static func row(_ sceneId: String) -> String {
            "scenes.row.\(sceneId)"
        }

        static func activateButton(_ sceneId: String) -> String {
            "scenes.row.\(sceneId).activate"
        }
    }

    enum QuickActions {
        static let section = "quickActions.section"
        static let lightsOn = "quickActions.lightsOn"
        static let lightsOff = "quickActions.lightsOff"
        static let fireplace = "quickActions.fireplace"
        static let tvLower = "quickActions.tvLower"
        static let tvRaise = "quickActions.tvRaise"
        static let shadesOpen = "quickActions.shadesOpen"
    }

    enum Settings {
        static let view = "settings.view"
        static let logoutButton = "settings.logout"
        static let householdSection = "settings.household"
        static let accessibilitySection = "settings.accessibility"
        static let privacySection = "settings.privacy"
        static let aboutSection = "settings.about"
    }

    enum Household {
        static let view = "household.view"
        static let addMemberButton = "household.addMember"
        static let memberNameField = "household.memberName"
        static let roleSelector = "household.roleSelector"
        static let saveButton = "household.save"
        static let adminBadge = "household.adminBadge"
        static let parentalControlsToggle = "household.parentalControls"
        static let authoritySelector = "household.authoritySelector"
        static let pronounsSection = "household.pronounsSection"

        // Accessibility
        static let accessibilitySection = "household.accessibilitySection"
        static let visionLevelSelector = "household.visionLevel"
        static let hearingLevelSelector = "household.hearingLevel"
        static let motorControlSelector = "household.motorControl"
        static let cognitiveNeedsSelector = "household.cognitiveNeeds"

        // Cultural
        static let culturalSection = "household.culturalSection"
        static let languageSelector = "household.language"
        static let privacyOrientationSelector = "household.privacyOrientation"

        // Household Type
        static let householdTypeSelector = "household.typeSelector"
        static let accessibilityDefaultsApplied = "household.accessibilityDefaultsApplied"

        // Emergency
        static let emergencySection = "household.emergencySection"
        static let isEmergencyContactToggle = "household.isEmergencyContact"
    }

    enum Accessibility {
        static let view = "accessibility.view"
        static let fontSizeSlider = "accessibility.fontSize"
        static let highContrastToggle = "accessibility.highContrast"
        static let reduceMotionToggle = "accessibility.reduceMotion"
        static let voiceOverOptimizedToggle = "accessibility.voiceOverOptimized"
        static let largeTouchTargetsToggle = "accessibility.largeTouchTargets"
        static let simplifiedUIToggle = "accessibility.simplifiedUI"
        static let previewButton = "accessibility.preview"
        static let resetButton = "accessibility.reset"

        // Test-specific identifiers
        static let largeText = "accessibility.largeText"
        static let normalText = "accessibility.normalText"
        static let touchTarget = "accessibility.touchTarget"
        static let animatedElement = "accessibility.animatedElement"
        static let staticElement = "accessibility.staticElement"
    }

    enum TabBar {
        static let home = "tabBar.home"
        static let rooms = "tabBar.rooms"
        static let hub = "tabBar.hub"
        static let scenes = "tabBar.scenes"
        static let settings = "tabBar.settings"
    }
}

/*
 * Mirror
 * E2E tests verify the complete user journey.
 * h(x) >= 0. Always.
 */
