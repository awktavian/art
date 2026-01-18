//
// KagamiVisionUITestCase.swift -- Base Test Case for Kagami visionOS E2E Tests
//
// Colony: Crystal (e7) -- Verification & Polish
//
// Provides common setup and utilities for visionOS E2E testing:
//   - Spatial interaction support
//   - Gaze-based navigation
//   - Screenshot capture for spatial UI
//   - visionOS-specific accessibility identifiers
//
// Run:
//   xcodebuild test -scheme KagamiVision -destination 'platform=visionOS Simulator,name=Apple Vision Pro'
//
// h(x) >= 0. Always.
//

import XCTest

/// Base test case for all Kagami visionOS UI tests
class KagamiVisionUITestCase: XCTestCase {

    // MARK: - Properties

    var app: XCUIApplication!

    /// Whether to run tests in demo mode
    var useDemoMode: Bool { true }

    /// Whether to skip onboarding
    var skipOnboarding: Bool { false }

    /// Standard timeout for element appearance
    static let defaultTimeout: TimeInterval = 5.0

    /// Extended timeout for spatial content loading
    static let extendedTimeout: TimeInterval = 20.0

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
            .matching(identifier: VisionAccessibilityIDs.Home.window).firstMatch
        let onboardingView = app.descendants(matching: .any)
            .matching(identifier: VisionAccessibilityIDs.Onboarding.window).firstMatch

        let predicate = NSPredicate { _, _ in
            homeView.exists || onboardingView.exists
        }

        let expectation = XCTNSPredicateExpectation(predicate: predicate, object: nil)
        let result = XCTWaiter.wait(for: [expectation], timeout: Self.extendedTimeout)

        if result != .completed {
            XCTFail("App did not become ready within \(Self.extendedTimeout) seconds")
        }
    }

    // MARK: - Spatial Interaction Helpers

    /// Perform a tap gesture at the center of an element
    /// In visionOS, this simulates selecting with gaze + pinch
    func tapElement(_ element: XCUIElement) {
        guard element.exists else {
            XCTFail("Element does not exist for tap: \(element)")
            return
        }
        element.tap()
        sleep(1)
    }

    /// Perform a long press gesture
    /// In visionOS, this can trigger additional options
    func longPressElement(_ element: XCUIElement, duration: TimeInterval = 1.0) {
        guard element.exists else {
            XCTFail("Element does not exist for long press: \(element)")
            return
        }
        element.press(forDuration: duration)
        sleep(1)
    }

    /// Perform a drag gesture
    /// In visionOS, this can move windows in space
    func dragElement(_ element: XCUIElement, byVector vector: CGVector) {
        guard element.exists else {
            XCTFail("Element does not exist for drag: \(element)")
            return
        }
        let start = element.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5))
        let end = start.withOffset(vector)
        start.press(forDuration: 0.1, thenDragTo: end)
        sleep(1)
    }

    /// Simulate pinch gesture for zoom
    func pinchElement(_ element: XCUIElement, scale: CGFloat) {
        guard element.exists else {
            XCTFail("Element does not exist for pinch: \(element)")
            return
        }
        element.pinch(withScale: scale, velocity: 1.0)
        sleep(1)
    }

    // MARK: - Window Management

    /// Close the current window (volumetric or 2D)
    func closeCurrentWindow() {
        let closeButton = app.buttons["Close"].firstMatch
        if closeButton.exists {
            closeButton.tap()
            sleep(1)
        }
    }

    /// Open a new window by identifier
    func openWindow(identifier: String) {
        // visionOS window management
        let element = element(withIdentifier: identifier)
        if element.exists {
            tapElement(element)
        }
    }

    // MARK: - Screenshot Helpers

    func takeScreenshot(named name: String) {
        let screenshot = XCUIScreen.main.screenshot()
        let attachment = XCTAttachment(screenshot: screenshot)
        attachment.name = "Vision-\(name)"
        attachment.lifetime = .keepAlways
        add(attachment)
    }

    func takeScreenshotOnFailure() {
        let screenshot = XCUIScreen.main.screenshot()
        let attachment = XCTAttachment(screenshot: screenshot)
        attachment.name = "Vision-Failure-\(Date().ISO8601Format())"
        attachment.lifetime = .keepAlways
        add(attachment)
    }

    /// Take a screenshot with element hierarchy for debugging
    func captureVisualState(named name: String) {
        // Screenshot
        let screenshot = XCUIScreen.main.screenshot()
        let screenshotAttachment = XCTAttachment(screenshot: screenshot)
        screenshotAttachment.name = "Vision-\(name)-Screenshot"
        screenshotAttachment.lifetime = .keepAlways
        add(screenshotAttachment)

        // Element hierarchy
        let hierarchy = app.debugDescription
        let hierarchyAttachment = XCTAttachment(string: hierarchy)
        hierarchyAttachment.name = "Vision-\(name)-Hierarchy"
        hierarchyAttachment.lifetime = .keepAlways
        add(hierarchyAttachment)
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

    // MARK: - Navigation Helpers

    func navigateToTab(_ tab: VisionTab) {
        let identifier: String
        switch tab {
        case .home:
            identifier = VisionAccessibilityIDs.TabBar.home
        case .rooms:
            identifier = VisionAccessibilityIDs.TabBar.rooms
        case .scenes:
            identifier = VisionAccessibilityIDs.TabBar.scenes
        case .settings:
            identifier = VisionAccessibilityIDs.TabBar.settings
        case .spatial:
            identifier = VisionAccessibilityIDs.TabBar.spatial
        }

        let tabElement = element(withIdentifier: identifier)
        if tabElement.waitForExistence(timeout: Self.defaultTimeout) {
            tapElement(tabElement)
        }
    }

    enum VisionTab {
        case home, rooms, scenes, settings, spatial
    }
}

// MARK: - visionOS Accessibility Identifiers

/// Accessibility identifiers for visionOS UI tests
enum VisionAccessibilityIDs {

    enum Onboarding {
        static let window = "vision.onboarding.window"
        static let continueButton = "vision.onboarding.continue"
        static let skipButton = "vision.onboarding.skip"
        static let demoModeButton = "vision.onboarding.demoMode"
        static let spatialTutorial = "vision.onboarding.spatialTutorial"
    }

    enum Home {
        static let window = "vision.home.window"
        static let controlPanel = "vision.home.controlPanel"
        static let presenceIndicator = "vision.home.presence"
        static let quickActions = "vision.home.quickActions"
    }

    enum Rooms {
        static let window = "vision.rooms.window"
        static let spatialView = "vision.rooms.spatialView"
        static let roomList = "vision.rooms.list"

        static func room(_ roomId: String) -> String {
            "vision.rooms.room.\(roomId)"
        }

        static func spatialRoom(_ roomId: String) -> String {
            "vision.rooms.spatial.\(roomId)"
        }
    }

    enum Scenes {
        static let window = "vision.scenes.window"
        static let sceneList = "vision.scenes.list"

        static func scene(_ sceneId: String) -> String {
            "vision.scenes.scene.\(sceneId)"
        }
    }

    enum Settings {
        static let window = "vision.settings.window"
        static let serverSection = "vision.settings.server"
        static let spatialSection = "vision.settings.spatial"
        static let accessibilitySection = "vision.settings.accessibility"
    }

    enum Spatial {
        static let fullExperience = "vision.spatial.fullExperience"
        static let commandPalette = "vision.spatial.commandPalette"
        static let breadcrumb = "vision.spatial.breadcrumb"
        static let roomView3D = "vision.spatial.roomView3D"
    }

    enum TabBar {
        static let home = "vision.tabBar.home"
        static let rooms = "vision.tabBar.rooms"
        static let scenes = "vision.tabBar.scenes"
        static let settings = "vision.tabBar.settings"
        static let spatial = "vision.tabBar.spatial"
    }

    enum VoiceCommand {
        static let window = "vision.voiceCommand.window"
        static let activateButton = "vision.voiceCommand.activate"
        static let statusIndicator = "vision.voiceCommand.status"
    }
}

/*
 * Mirror
 * visionOS E2E tests verify the spatial computing experience.
 * h(x) >= 0. Always.
 */
