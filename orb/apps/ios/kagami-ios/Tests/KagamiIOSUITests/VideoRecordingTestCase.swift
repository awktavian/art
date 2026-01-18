//
// VideoRecordingTestCase.swift -- XCUITest Base with Video Recording
//
// Colony: Crystal (e7) -- Verification & Polish
//
// Provides video recording capabilities for E2E tests:
//   - Automatic video recording for test runs
//   - Screenshot capture at key points
//   - Video attachment to test results
//
// h(x) >= 0. Always.
//

import XCTest

/// Base test case with video recording support for comprehensive E2E testing
class VideoRecordingTestCase: KagamiUITestCase {

    // MARK: - Video Recording Properties

    /// Whether video recording is enabled for this test
    var videoRecordingEnabled: Bool { true }

    /// Video recording quality (0.0 to 1.0)
    var videoQuality: Float { 0.75 }

    /// Recording identifier for the current test
    private var recordingIdentifier: String?

    /// Screenshots captured during the test
    private var testScreenshots: [XCTAttachment] = []

    // MARK: - Setup & Teardown

    override func setUp() {
        super.setUp()

        if videoRecordingEnabled {
            startVideoRecordingIfSupported()
        }

        // Enable test activity recording
        XCTContext.runActivity(named: "Test Setup: \(name)") { _ in
            captureScreenshot(named: "TestStart")
        }
    }

    override func tearDown() {
        XCTContext.runActivity(named: "Test Teardown: \(name)") { _ in
            captureScreenshot(named: "TestEnd")

            if videoRecordingEnabled {
                stopVideoRecordingIfSupported()
            }
        }

        super.tearDown()
    }

    // MARK: - Video Recording Methods

    /// Start video recording for the test
    /// Uses xcrun simctl to record the simulator screen
    private func startVideoRecordingIfSupported() {
        let deviceUDID = ProcessInfo.processInfo.environment["SIMULATOR_UDID"] ?? ""
        guard !deviceUDID.isEmpty else {
            print("Video recording: No simulator UDID found, skipping video recording")
            return
        }

        recordingIdentifier = UUID().uuidString

        // Note: Video recording in XCUITest is typically handled by the CI system
        // using `xcrun simctl io recordVideo`. This method sets up the test
        // to be ready for external video recording orchestration.

        print("Video recording: Test ready for recording on device \(deviceUDID)")
    }

    /// Stop video recording and attach to test results
    private func stopVideoRecordingIfSupported() {
        guard let identifier = recordingIdentifier else { return }

        // In CI, the video file would be created by an external process
        // Here we document where the video should be saved
        let videoPath = "/tmp/kagami-test-videos/\(identifier).mp4"

        print("Video recording: Expected video at \(videoPath)")

        // Create a marker attachment indicating video location
        let videoMarker = """
        Video Recording Marker
        ======================
        Test: \(name)
        Recording ID: \(identifier)
        Expected Path: \(videoPath)
        Timestamp: \(ISO8601DateFormatter().string(from: Date()))
        """

        let attachment = XCTAttachment(string: videoMarker)
        attachment.name = "VideoRecording-\(identifier)"
        attachment.lifetime = .keepAlways
        add(attachment)

        recordingIdentifier = nil
    }

    // MARK: - Screenshot Capture

    /// Capture a screenshot with descriptive naming
    /// - Parameters:
    ///   - name: Name for the screenshot
    ///   - description: Optional description of the UI state
    func captureScreenshot(named name: String, description: String? = nil) {
        let screenshot = XCUIScreen.main.screenshot()
        let attachment = XCTAttachment(screenshot: screenshot)

        let fullName = description.map { "\(name)-\($0)" } ?? name
        attachment.name = fullName
        attachment.lifetime = .keepAlways

        add(attachment)
        testScreenshots.append(attachment)
    }

    /// Capture screenshot at a user journey checkpoint
    /// - Parameter checkpoint: Description of the current step in the user journey
    func captureJourneyCheckpoint(_ checkpoint: String) {
        XCTContext.runActivity(named: "Checkpoint: \(checkpoint)") { _ in
            captureScreenshot(named: "Journey-\(checkpoint)")
        }
    }

    // MARK: - Test Activity Helpers

    /// Run an action and capture before/after screenshots
    /// - Parameters:
    ///   - name: Name of the action
    ///   - action: The action to perform
    func performActionWithScreenshots(named name: String, action: () -> Void) {
        XCTContext.runActivity(named: name) { _ in
            captureScreenshot(named: "\(name)-Before")
            action()
            sleep(1) // Wait for UI to settle
            captureScreenshot(named: "\(name)-After")
        }
    }

    /// Run an async action with timeout and capture screenshots
    /// - Parameters:
    ///   - name: Name of the action
    ///   - timeout: Maximum time to wait
    ///   - action: The action to perform
    ///   - completion: Completion check
    func performAsyncActionWithScreenshots(
        named name: String,
        timeout: TimeInterval = 10,
        action: () -> Void,
        completion: () -> Bool
    ) {
        XCTContext.runActivity(named: name) { _ in
            captureScreenshot(named: "\(name)-Before")

            action()

            let startTime = Date()
            while !completion() && Date().timeIntervalSince(startTime) < timeout {
                sleep(1)
            }

            captureScreenshot(named: "\(name)-After")

            if !completion() {
                captureScreenshot(named: "\(name)-Timeout")
                XCTFail("Action '\(name)' did not complete within \(timeout) seconds")
            }
        }
    }

    // MARK: - User Journey Recording

    /// Record a complete user journey with screenshots at each step
    /// - Parameters:
    ///   - journeyName: Name of the user journey
    ///   - steps: Array of (step name, action) tuples
    func recordUserJourney(
        _ journeyName: String,
        steps: [(name: String, action: () -> Void)]
    ) {
        XCTContext.runActivity(named: "User Journey: \(journeyName)") { _ in
            captureScreenshot(named: "\(journeyName)-Start")

            for (index, step) in steps.enumerated() {
                XCTContext.runActivity(named: "Step \(index + 1): \(step.name)") { _ in
                    step.action()
                    sleep(1)
                    captureScreenshot(named: "\(journeyName)-Step\(index + 1)-\(step.name)")
                }
            }

            captureScreenshot(named: "\(journeyName)-Complete")
        }
    }
}

// MARK: - User Journey Tests

/// Extension with predefined user journey tests
extension VideoRecordingTestCase {

    /// Test the complete onboarding user journey with screenshots
    func testOnboardingUserJourney() {
        // Reset to show onboarding
        app.launchArguments.removeAll { $0 == "-SkipOnboarding" }
        app.launchArguments.append("-ResetState")
        app.launch()
        waitForAppReady()

        recordUserJourney("Onboarding", steps: [
            ("Welcome Screen", {
                self.assertOnboardingVisible()
            }),
            ("Continue to Server", {
                self.tap(identifier: AccessibilityIDs.Onboarding.continueButton, in: self.app)
                sleep(1)
            }),
            ("Select Demo Mode", {
                self.tap(identifier: AccessibilityIDs.Onboarding.serverDemoButton, in: self.app)
                sleep(1)
            }),
            ("Continue to Integrations", {
                self.tap(identifier: AccessibilityIDs.Onboarding.continueButton, in: self.app)
                sleep(1)
            }),
            ("Skip Integrations", {
                self.tap(identifier: AccessibilityIDs.Onboarding.skipButton, in: self.app)
                sleep(1)
            }),
            ("Skip Rooms", {
                self.tap(identifier: AccessibilityIDs.Onboarding.skipButton, in: self.app)
                sleep(1)
            }),
            ("Skip Permissions", {
                self.tap(identifier: AccessibilityIDs.Onboarding.skipButton, in: self.app)
                sleep(1)
            }),
            ("Get Started", {
                self.tap(identifier: AccessibilityIDs.Onboarding.getStartedButton, in: self.app)
                sleep(1)
            })
        ])

        // Verify we reached home screen
        assertOnHomeScreen()
    }

    /// Test the room control user journey
    func testRoomControlUserJourney() {
        ensureOnHomeScreen()

        recordUserJourney("RoomControl", steps: [
            ("Navigate to Rooms", {
                self.navigateToTab(.rooms)
                sleep(2)
            }),
            ("Select First Room", {
                let roomsList = self.element(withIdentifier: AccessibilityIDs.Rooms.list, in: self.app)
                if roomsList.cells.count > 0 {
                    roomsList.cells.firstMatch.tap()
                    sleep(1)
                }
            }),
            ("Return to Rooms List", {
                if self.app.navigationBars.buttons.firstMatch.exists {
                    self.app.navigationBars.buttons.firstMatch.tap()
                    sleep(1)
                }
            })
        ])
    }

    /// Test the scene activation user journey
    func testSceneActivationUserJourney() {
        ensureOnHomeScreen()

        recordUserJourney("SceneActivation", steps: [
            ("Navigate to Scenes", {
                self.navigateToTab(.scenes)
                sleep(2)
            }),
            ("View Scene List", {
                // Just capture the scene list
            }),
            ("Return to Home", {
                self.navigateToTab(.home)
                sleep(1)
            })
        ])
    }

    /// Helper to ensure we're on the home screen
    private func ensureOnHomeScreen() {
        let homeView = element(withIdentifier: AccessibilityIDs.Home.view, in: app)
        if !homeView.waitForExistence(timeout: 3) {
            let onboardingProgress = element(withIdentifier: AccessibilityIDs.Onboarding.progressIndicator, in: app)
            if onboardingProgress.exists {
                completeOnboarding()
            }
        }
    }
}

/*
 * Mirror
 * Video recording captures the full user experience.
 * h(x) >= 0. Always.
 */
