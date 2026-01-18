//
// KagamiTVUITestCase.swift -- Base Test Case for Kagami tvOS E2E Tests
//
// Colony: Crystal (e7) -- Verification & Polish
//
// Provides common setup and utilities for tvOS E2E testing:
//   - Siri Remote navigation support
//   - Focus-based element interaction
//   - Screenshot capture at key points
//   - tvOS-specific accessibility identifiers
//
// Run:
//   xcodebuild test -scheme KagamiTV -destination 'platform=tvOS Simulator,name=Apple TV 4K (3rd generation)'
//
// h(x) >= 0. Always.
//

import XCTest

/// Base test case for all Kagami tvOS UI tests
class KagamiTVUITestCase: XCTestCase {

    // MARK: - Properties

    var app: XCUIApplication!

    /// Whether to run tests in demo mode
    var useDemoMode: Bool { true }

    /// Whether to skip onboarding
    var skipOnboarding: Bool { false }

    /// Standard timeout for element appearance
    static let defaultTimeout: TimeInterval = 5.0

    /// Extended timeout for slow operations
    static let extendedTimeout: TimeInterval = 15.0

    // MARK: - Setup & Teardown

    override func setUp() {
        super.setUp()

        continueAfterFailure = false

        app = XCUIApplication()
        configureLaunchArguments()
        app.launch()

        waitForAppReady()
    }

    override func tearDown() {
        if testRun?.hasSucceeded == false {
            takeScreenshotOnFailure()
        }

        app.terminate()
        app = nil

        super.tearDown()
    }

    // MARK: - Configuration

    func configureLaunchArguments() {
        app.launchArguments.append("-UITesting")

        if useDemoMode {
            app.launchArguments.append("-DemoMode")
        }

        if skipOnboarding {
            app.launchArguments.append("-SkipOnboarding")
        }

        app.launchArguments.append("-DisableAnimations")
        app.launchArguments.append("-ResetState")
    }

    func waitForAppReady() {
        let homeView = app.descendants(matching: .any)
            .matching(identifier: TVAccessibilityIDs.Home.view).firstMatch
        let onboardingView = app.descendants(matching: .any)
            .matching(identifier: TVAccessibilityIDs.Onboarding.view).firstMatch

        let predicate = NSPredicate { _, _ in
            homeView.exists || onboardingView.exists
        }

        let expectation = XCTNSPredicateExpectation(predicate: predicate, object: nil)
        let result = XCTWaiter.wait(for: [expectation], timeout: Self.extendedTimeout)

        if result != .completed {
            XCTFail("App did not become ready within \(Self.extendedTimeout) seconds")
        }
    }

    // MARK: - Siri Remote Navigation

    /// Press the Menu button on the Siri Remote
    func pressMenuButton() {
        XCUIRemote.shared.press(.menu)
        sleep(1)
    }

    /// Press the Play/Pause button on the Siri Remote
    func pressPlayPause() {
        XCUIRemote.shared.press(.playPause)
        sleep(1)
    }

    /// Press the Select button on the Siri Remote
    func pressSelect() {
        XCUIRemote.shared.press(.select)
        sleep(1)
    }

    /// Navigate up on the Siri Remote
    func navigateUp() {
        XCUIRemote.shared.press(.up)
        sleep(1)
    }

    /// Navigate down on the Siri Remote
    func navigateDown() {
        XCUIRemote.shared.press(.down)
        sleep(1)
    }

    /// Navigate left on the Siri Remote
    func navigateLeft() {
        XCUIRemote.shared.press(.left)
        sleep(1)
    }

    /// Navigate right on the Siri Remote
    func navigateRight() {
        XCUIRemote.shared.press(.right)
        sleep(1)
    }

    // MARK: - Focus Helpers

    /// Get the currently focused element
    func focusedElement() -> XCUIElement {
        return app.descendants(matching: .any).element(matching: NSPredicate(format: "hasFocus == true"))
    }

    /// Wait for an element to gain focus
    @discardableResult
    func waitForFocus(on element: XCUIElement, timeout: TimeInterval = defaultTimeout) -> Bool {
        let predicate = NSPredicate(format: "hasFocus == true")
        let expectation = XCTNSPredicateExpectation(predicate: predicate, object: element)
        return XCTWaiter.wait(for: [expectation], timeout: timeout) == .completed
    }

    /// Navigate to a specific element using remote navigation
    func navigateTo(identifier: String) {
        let element = app.descendants(matching: .any).matching(identifier: identifier).firstMatch

        // Try to find and focus the element
        for _ in 0..<10 {
            if element.exists && element.hasFocus {
                return
            }

            // Try navigating in different directions
            navigateRight()
            if element.hasFocus { return }

            navigateDown()
            if element.hasFocus { return }
        }
    }

    // MARK: - Screenshot Helpers

    func takeScreenshot(named name: String) {
        let screenshot = XCUIScreen.main.screenshot()
        let attachment = XCTAttachment(screenshot: screenshot)
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }

    func takeScreenshotOnFailure() {
        let screenshot = XCUIScreen.main.screenshot()
        let attachment = XCTAttachment(screenshot: screenshot)
        attachment.name = "Failure-\(Date().ISO8601Format())"
        attachment.lifetime = .keepAlways
        add(attachment)
    }

    // MARK: - Element Helpers

    func element(withIdentifier identifier: String) -> XCUIElement {
        return app.descendants(matching: .any).matching(identifier: identifier).firstMatch
    }

    @discardableResult
    func waitForElement(_ element: XCUIElement, timeout: TimeInterval = defaultTimeout) -> Bool {
        return element.waitForExistence(timeout: timeout)
    }

    func assertVisible(_ element: XCUIElement, timeout: TimeInterval = defaultTimeout) {
        XCTAssertTrue(
            element.waitForExistence(timeout: timeout),
            "Element \(element) should be visible"
        )
    }

    func assertTextPresent(_ text: String, timeout: TimeInterval = defaultTimeout) {
        let element = app.staticTexts[text].firstMatch
        XCTAssertTrue(
            element.waitForExistence(timeout: timeout),
            "Text '\(text)' should be present on screen"
        )
    }
}

// MARK: - tvOS Accessibility Identifiers

/// Accessibility identifiers for tvOS UI tests
enum TVAccessibilityIDs {

    enum Onboarding {
        static let view = "tv.onboarding.view"
        static let continueButton = "tv.onboarding.continue"
        static let skipButton = "tv.onboarding.skip"
        static let demoModeButton = "tv.onboarding.demoMode"
    }

    enum Home {
        static let view = "tv.home.view"
        static let quickActions = "tv.home.quickActions"
        static let roomsSection = "tv.home.rooms"
        static let scenesSection = "tv.home.scenes"
    }

    enum Rooms {
        static let view = "tv.rooms.view"
        static let list = "tv.rooms.list"

        static func row(_ roomId: String) -> String {
            "tv.rooms.row.\(roomId)"
        }
    }

    enum Scenes {
        static let view = "tv.scenes.view"
        static let list = "tv.scenes.list"

        static func row(_ sceneId: String) -> String {
            "tv.scenes.row.\(sceneId)"
        }
    }

    enum Settings {
        static let view = "tv.settings.view"
        static let serverSection = "tv.settings.server"
        static let aboutSection = "tv.settings.about"
    }

    enum TabBar {
        static let home = "tv.tabBar.home"
        static let rooms = "tv.tabBar.rooms"
        static let scenes = "tv.tabBar.scenes"
        static let settings = "tv.tabBar.settings"
    }
}

/*
 * Mirror
 * tvOS E2E tests verify the living room experience.
 * h(x) >= 0. Always.
 */
