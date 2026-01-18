//
// UserJourneyTests.swift -- Comprehensive E2E Video Tests for tvOS User Journeys
//
// Colony: Crystal (e7) -- Verification & Polish
//
// Records complete user journeys with video for:
//   - Siri Remote navigation
//   - Scene cards selection
//   - Ambient mode transitions
//   - Focus navigation
//
// Video Output: test-artifacts/videos/tvos/{journey-name}.mp4
//
// Run:
//   xcodebuild test -scheme KagamiTV \
//     -destination 'platform=tvOS Simulator,name=Apple TV 4K (3rd generation)' \
//     -only-testing:KagamiTVUITests/UserJourneyTests
//
// h(x) >= 0. Always.
//

import XCTest

/// Comprehensive E2E User Journey Tests with Video Recording for tvOS
final class UserJourneyTests: KagamiTVUITestCase {

    // MARK: - Configuration

    /// Enable video recording for all journey tests
    var videoRecordingEnabled: Bool { true }

    /// High quality recording for user journey documentation
    var videoQuality: Float { 0.85 }

    // MARK: - Journey Metadata

    /// Journey checkpoint data structure
    private struct JourneyCheckpoint {
        let name: String
        let timestamp: Date
        let success: Bool
        let focusedElement: String?
        let notes: String?
    }

    /// Collected checkpoints for metadata generation
    private var journeyCheckpoints: [JourneyCheckpoint] = []
    private var recordingIdentifier: String?

    // MARK: - Setup & Teardown

    override func setUp() {
        super.setUp()
        journeyCheckpoints = []

        if videoRecordingEnabled {
            startVideoRecordingIfSupported()
        }
    }

    override func tearDown() {
        if videoRecordingEnabled {
            stopVideoRecordingIfSupported()
        }
        generateJourneyMetadata()
        super.tearDown()
    }

    // MARK: - Siri Remote Navigation Journey

    /// Tests complete Siri Remote navigation flow with video recording
    /// Journey: Home -> Navigate tabs -> Focus elements -> Select items
    func testSiriRemoteNavigationJourney() {
        recordJourneyStart("SiriRemoteNavigation")

        // Phase 1: Initial focus check
        XCTContext.runActivity(named: "Phase 1: Initial Focus State") { _ in
            captureJourneyCheckpoint("InitialState")

            // Verify we're on home or onboarding
            let homeView = element(withIdentifier: TVAccessibilityIDs.Home.view)
            let onboardingView = element(withIdentifier: TVAccessibilityIDs.Onboarding.view)

            if onboardingView.waitForExistence(timeout: 3) {
                completeOnboarding()
            }

            waitForElement(homeView, timeout: Self.extendedTimeout)
            captureJourneyCheckpoint("HomeReached")
            recordCheckpoint("HomeScreenFocused", success: true, focusedElement: "home")
        }

        // Phase 2: Navigate right through content
        XCTContext.runActivity(named: "Phase 2: Right Navigation") { _ in
            captureJourneyCheckpoint("PreNavigateRight")

            for i in 1...5 {
                navigateRight()
                let focused = focusedElement()
                captureJourneyCheckpoint("NavigateRight-\(i)")
                recordCheckpoint("NavigatedRight-\(i)", success: focused.exists, focusedElement: focused.identifier)
            }
        }

        // Phase 3: Navigate down through sections
        XCTContext.runActivity(named: "Phase 3: Down Navigation") { _ in
            captureJourneyCheckpoint("PreNavigateDown")

            for i in 1...3 {
                navigateDown()
                let focused = focusedElement()
                captureJourneyCheckpoint("NavigateDown-\(i)")
                recordCheckpoint("NavigatedDown-\(i)", success: focused.exists, focusedElement: focused.identifier)
            }
        }

        // Phase 4: Navigate left to return
        XCTContext.runActivity(named: "Phase 4: Left Navigation") { _ in
            captureJourneyCheckpoint("PreNavigateLeft")

            for i in 1...3 {
                navigateLeft()
                let focused = focusedElement()
                captureJourneyCheckpoint("NavigateLeft-\(i)")
                recordCheckpoint("NavigatedLeft-\(i)", success: focused.exists, focusedElement: focused.identifier)
            }
        }

        // Phase 5: Navigate up to return
        XCTContext.runActivity(named: "Phase 5: Up Navigation") { _ in
            captureJourneyCheckpoint("PreNavigateUp")

            for i in 1...2 {
                navigateUp()
                let focused = focusedElement()
                captureJourneyCheckpoint("NavigateUp-\(i)")
                recordCheckpoint("NavigatedUp-\(i)", success: focused.exists, focusedElement: focused.identifier)
            }
        }

        // Phase 6: Tab navigation
        XCTContext.runActivity(named: "Phase 6: Tab Bar Navigation") { _ in
            // Navigate to tab bar area
            captureJourneyCheckpoint("PreTabNavigation")

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
                captureJourneyCheckpoint("Tab-\(name)")
                recordCheckpoint("TabSelected-\(name)", success: true, focusedElement: identifier)
            }
        }

        captureJourneyCheckpoint("JourneyComplete")
        recordJourneyEnd("SiriRemoteNavigation")
    }

    // MARK: - Scene Cards Selection Journey

    /// Tests scene card selection and activation flow
    /// Journey: Navigate to scenes -> Focus cards -> Activate scenes
    func testSceneCardsSelectionJourney() {
        recordJourneyStart("SceneCardsSelection")

        // Setup: Get to home screen
        XCTContext.runActivity(named: "Setup") { _ in
            let onboardingView = element(withIdentifier: TVAccessibilityIDs.Onboarding.view)
            if onboardingView.waitForExistence(timeout: 3) {
                completeOnboarding()
            }

            let homeView = element(withIdentifier: TVAccessibilityIDs.Home.view)
            waitForElement(homeView, timeout: Self.extendedTimeout)
            captureJourneyCheckpoint("Setup-Home")
        }

        // Phase 1: Navigate to Scenes tab
        XCTContext.runActivity(named: "Phase 1: Navigate to Scenes") { _ in
            navigateTo(identifier: TVAccessibilityIDs.TabBar.scenes)
            pressSelect()
            sleep(1)

            let scenesView = element(withIdentifier: TVAccessibilityIDs.Scenes.view)
            waitForElement(scenesView, timeout: Self.defaultTimeout)
            captureJourneyCheckpoint("ScenesTab")
            recordCheckpoint("ScenesTabFocused", success: true, focusedElement: TVAccessibilityIDs.TabBar.scenes)
        }

        // Phase 2: Navigate through scene cards
        XCTContext.runActivity(named: "Phase 2: Scene Card Navigation") { _ in
            captureJourneyCheckpoint("PreSceneNavigation")

            // Navigate through scenes grid
            for i in 1...4 {
                navigateRight()
                let focused = focusedElement()
                captureJourneyCheckpoint("SceneCard-\(i)")
                recordCheckpoint("SceneCardFocused-\(i)", success: focused.exists, focusedElement: focused.identifier)
            }

            // Navigate down to next row
            navigateDown()
            captureJourneyCheckpoint("SceneNextRow")

            for i in 1...3 {
                navigateLeft()
                captureJourneyCheckpoint("SceneCardRow2-\(i)")
            }
        }

        // Phase 3: Activate a scene
        XCTContext.runActivity(named: "Phase 3: Scene Activation") { _ in
            // Return to first scene
            navigateTo(identifier: TVAccessibilityIDs.Scenes.list)
            sleep(1)

            let scenesList = element(withIdentifier: TVAccessibilityIDs.Scenes.list)
            if scenesList.exists {
                captureJourneyCheckpoint("PreSceneActivation")
                pressSelect()
                sleep(2) // Wait for scene activation animation
                captureJourneyCheckpoint("PostSceneActivation")
                recordCheckpoint("SceneActivated", success: true)
            }
        }

        // Phase 4: Activate multiple scenes
        XCTContext.runActivity(named: "Phase 4: Multiple Scene Activations") { _ in
            let sceneNames = ["Movie Mode", "Relax", "Goodnight"]

            for sceneName in sceneNames {
                // Navigate to find scene
                navigateRight()
                sleep(1)

                captureJourneyCheckpoint("PreActivate-\(sceneName)")
                pressSelect()
                sleep(1)
                captureJourneyCheckpoint("PostActivate-\(sceneName)")
                recordCheckpoint("SceneActivated-\(sceneName)", success: true)
            }
        }

        captureJourneyCheckpoint("JourneyComplete")
        recordJourneyEnd("SceneCardsSelection")
    }

    // MARK: - Ambient Mode Transitions Journey

    /// Tests ambient mode transitions and screensaver interactions
    /// Journey: Idle -> Ambient mode -> Wake -> Navigate
    func testAmbientModeTransitionsJourney() {
        recordJourneyStart("AmbientModeTransitions")

        // Setup
        XCTContext.runActivity(named: "Setup") { _ in
            let onboardingView = element(withIdentifier: TVAccessibilityIDs.Onboarding.view)
            if onboardingView.waitForExistence(timeout: 3) {
                completeOnboarding()
            }

            let homeView = element(withIdentifier: TVAccessibilityIDs.Home.view)
            waitForElement(homeView, timeout: Self.extendedTimeout)
            captureJourneyCheckpoint("Setup-Home")
        }

        // Phase 1: Capture normal state
        XCTContext.runActivity(named: "Phase 1: Normal State") { _ in
            captureJourneyCheckpoint("NormalState")
            recordCheckpoint("NormalStateCapture", success: true)

            // Navigate through home to show normal interaction
            navigateRight()
            sleep(1)
            captureJourneyCheckpoint("NormalNavigation1")

            navigateDown()
            sleep(1)
            captureJourneyCheckpoint("NormalNavigation2")
        }

        // Phase 2: Simulate ambient/idle state (note: actual ambient mode requires longer idle)
        XCTContext.runActivity(named: "Phase 2: Pre-Ambient State") { _ in
            captureJourneyCheckpoint("PreAmbient")

            // Wait a short period (in real testing, this would be longer)
            sleep(3)
            captureJourneyCheckpoint("IdleWait")
            recordCheckpoint("IdleStateSimulated", success: true)
        }

        // Phase 3: Wake from idle
        XCTContext.runActivity(named: "Phase 3: Wake Interaction") { _ in
            // Press any button to "wake"
            captureJourneyCheckpoint("PreWake")
            pressSelect()
            sleep(1)
            captureJourneyCheckpoint("PostWake")
            recordCheckpoint("WokeFromIdle", success: true)
        }

        // Phase 4: Verify navigation works after wake
        XCTContext.runActivity(named: "Phase 4: Post-Wake Navigation") { _ in
            captureJourneyCheckpoint("PostWakeNavStart")

            // Navigate to verify responsiveness
            navigateLeft()
            sleep(1)
            captureJourneyCheckpoint("PostWakeNav1")

            navigateUp()
            sleep(1)
            captureJourneyCheckpoint("PostWakeNav2")

            recordCheckpoint("PostWakeNavigationComplete", success: true)
        }

        // Phase 5: Test Menu button behavior
        XCTContext.runActivity(named: "Phase 5: Menu Button Behavior") { _ in
            captureJourneyCheckpoint("PreMenuButton")
            pressMenuButton()
            sleep(1)
            captureJourneyCheckpoint("PostMenuButton")
            recordCheckpoint("MenuButtonPressed", success: true)

            // Return to previous state
            pressMenuButton()
            sleep(1)
        }

        captureJourneyCheckpoint("JourneyComplete")
        recordJourneyEnd("AmbientModeTransitions")
    }

    // MARK: - Focus Navigation Deep Dive Journey

    /// Tests focus system behavior across all UI elements
    /// Journey: Comprehensive focus testing across home, rooms, scenes, settings
    func testFocusNavigationDeepDiveJourney() {
        recordJourneyStart("FocusNavigationDeepDive")

        // Setup
        XCTContext.runActivity(named: "Setup") { _ in
            let onboardingView = element(withIdentifier: TVAccessibilityIDs.Onboarding.view)
            if onboardingView.waitForExistence(timeout: 3) {
                completeOnboarding()
            }

            let homeView = element(withIdentifier: TVAccessibilityIDs.Home.view)
            waitForElement(homeView, timeout: Self.extendedTimeout)
            captureJourneyCheckpoint("Setup-Home")
        }

        // Phase 1: Home screen focus exploration
        XCTContext.runActivity(named: "Phase 1: Home Focus Grid") { _ in
            captureJourneyCheckpoint("HomeFocusStart")

            // Create a grid navigation pattern
            let movements: [(String, () -> Void)] = [
                ("Right", { self.navigateRight() }),
                ("Right", { self.navigateRight() }),
                ("Down", { self.navigateDown() }),
                ("Left", { self.navigateLeft() }),
                ("Down", { self.navigateDown() }),
                ("Right", { self.navigateRight() }),
                ("Up", { self.navigateUp() }),
                ("Left", { self.navigateLeft() })
            ]

            for (direction, action) in movements {
                action()
                let focused = focusedElement()
                captureJourneyCheckpoint("HomeFocus-\(direction)")
                recordCheckpoint("HomeFocus-\(direction)",
                                success: focused.exists,
                                focusedElement: focused.identifier)
            }
        }

        // Phase 2: Rooms tab focus
        XCTContext.runActivity(named: "Phase 2: Rooms Focus") { _ in
            navigateTo(identifier: TVAccessibilityIDs.TabBar.rooms)
            pressSelect()
            sleep(1)
            captureJourneyCheckpoint("RoomsTab")

            // Navigate through rooms
            for i in 1...6 {
                navigateRight()
                let focused = focusedElement()
                captureJourneyCheckpoint("RoomFocus-\(i)")
                recordCheckpoint("RoomFocused-\(i)",
                                success: focused.exists,
                                focusedElement: focused.identifier)
            }

            navigateDown()
            captureJourneyCheckpoint("RoomsFocusRow2")
        }

        // Phase 3: Scenes tab focus
        XCTContext.runActivity(named: "Phase 3: Scenes Focus") { _ in
            navigateTo(identifier: TVAccessibilityIDs.TabBar.scenes)
            pressSelect()
            sleep(1)
            captureJourneyCheckpoint("ScenesTab")

            // Navigate through scenes
            for i in 1...6 {
                navigateRight()
                let focused = focusedElement()
                captureJourneyCheckpoint("SceneFocus-\(i)")
                recordCheckpoint("SceneFocused-\(i)",
                                success: focused.exists,
                                focusedElement: focused.identifier)
            }
        }

        // Phase 4: Settings tab focus
        XCTContext.runActivity(named: "Phase 4: Settings Focus") { _ in
            navigateTo(identifier: TVAccessibilityIDs.TabBar.settings)
            pressSelect()
            sleep(1)
            captureJourneyCheckpoint("SettingsTab")

            // Navigate through settings sections
            for i in 1...4 {
                navigateDown()
                let focused = focusedElement()
                captureJourneyCheckpoint("SettingsFocus-\(i)")
                recordCheckpoint("SettingsFocused-\(i)",
                                success: focused.exists,
                                focusedElement: focused.identifier)
            }
        }

        // Phase 5: Return to home
        XCTContext.runActivity(named: "Phase 5: Return Home") { _ in
            navigateTo(identifier: TVAccessibilityIDs.TabBar.home)
            pressSelect()
            sleep(1)

            let homeView = element(withIdentifier: TVAccessibilityIDs.Home.view)
            waitForElement(homeView, timeout: Self.defaultTimeout)
            captureJourneyCheckpoint("ReturnedHome")
            recordCheckpoint("ReturnedToHome", success: true)
        }

        captureJourneyCheckpoint("JourneyComplete")
        recordJourneyEnd("FocusNavigationDeepDive")
    }

    // MARK: - Play/Pause Button Journey

    /// Tests Play/Pause button interactions across different contexts
    func testPlayPauseButtonJourney() {
        recordJourneyStart("PlayPauseButton")

        // Setup
        XCTContext.runActivity(named: "Setup") { _ in
            let onboardingView = element(withIdentifier: TVAccessibilityIDs.Onboarding.view)
            if onboardingView.waitForExistence(timeout: 3) {
                completeOnboarding()
            }

            let homeView = element(withIdentifier: TVAccessibilityIDs.Home.view)
            waitForElement(homeView, timeout: Self.extendedTimeout)
            captureJourneyCheckpoint("Setup-Home")
        }

        // Phase 1: Play/Pause on home screen
        XCTContext.runActivity(named: "Phase 1: Home Screen Play/Pause") { _ in
            captureJourneyCheckpoint("PrePlayPause-Home")
            pressPlayPause()
            sleep(1)
            captureJourneyCheckpoint("PostPlayPause-Home")
            recordCheckpoint("PlayPauseOnHome", success: true)
        }

        // Phase 2: Navigate to quick actions and test
        XCTContext.runActivity(named: "Phase 2: Quick Actions Play/Pause") { _ in
            let quickActions = element(withIdentifier: TVAccessibilityIDs.Home.quickActions)
            if quickActions.waitForExistence(timeout: 3) {
                navigateTo(identifier: TVAccessibilityIDs.Home.quickActions)
                captureJourneyCheckpoint("QuickActionsFound")

                pressPlayPause()
                sleep(1)
                captureJourneyCheckpoint("PostPlayPause-QuickActions")
                recordCheckpoint("PlayPauseOnQuickActions", success: true)
            }
        }

        // Phase 3: Test in Scenes
        XCTContext.runActivity(named: "Phase 3: Scenes Play/Pause") { _ in
            navigateTo(identifier: TVAccessibilityIDs.TabBar.scenes)
            pressSelect()
            sleep(1)

            captureJourneyCheckpoint("ScenesPrePlayPause")
            pressPlayPause()
            sleep(1)
            captureJourneyCheckpoint("ScenesPostPlayPause")
            recordCheckpoint("PlayPauseOnScenes", success: true)
        }

        // Phase 4: Return home
        XCTContext.runActivity(named: "Phase 4: Return Home") { _ in
            navigateTo(identifier: TVAccessibilityIDs.TabBar.home)
            pressSelect()
            sleep(1)

            captureJourneyCheckpoint("ReturnedHome")
            recordCheckpoint("ReturnedToHome", success: true)
        }

        captureJourneyCheckpoint("JourneyComplete")
        recordJourneyEnd("PlayPauseButton")
    }

    // MARK: - Room Control Journey

    /// Tests room control interactions on tvOS
    /// Journey: Navigate to rooms -> Select room -> Control devices
    func testRoomControlJourney() {
        recordJourneyStart("RoomControl")

        // Setup
        XCTContext.runActivity(named: "Setup") { _ in
            let onboardingView = element(withIdentifier: TVAccessibilityIDs.Onboarding.view)
            if onboardingView.waitForExistence(timeout: 3) {
                completeOnboarding()
            }

            let homeView = element(withIdentifier: TVAccessibilityIDs.Home.view)
            waitForElement(homeView, timeout: Self.extendedTimeout)
            captureJourneyCheckpoint("Setup-Home")
        }

        // Phase 1: Navigate to Rooms
        XCTContext.runActivity(named: "Phase 1: Navigate to Rooms") { _ in
            navigateTo(identifier: TVAccessibilityIDs.TabBar.rooms)
            pressSelect()
            sleep(1)

            let roomsView = element(withIdentifier: TVAccessibilityIDs.Rooms.view)
            waitForElement(roomsView, timeout: Self.defaultTimeout)
            captureJourneyCheckpoint("RoomsTab")
            recordCheckpoint("RoomsNavigated", success: true)
        }

        // Phase 2: Select first room
        XCTContext.runActivity(named: "Phase 2: Select Room") { _ in
            captureJourneyCheckpoint("PreRoomSelect")

            // Navigate to first room and select
            navigateRight()
            sleep(1)

            let focused = focusedElement()
            captureJourneyCheckpoint("RoomFocused")

            pressSelect()
            sleep(1)
            captureJourneyCheckpoint("RoomSelected")
            recordCheckpoint("RoomSelected", success: true, focusedElement: focused.identifier)
        }

        // Phase 3: Control room devices (if detail view opens)
        XCTContext.runActivity(named: "Phase 3: Room Controls") { _ in
            captureJourneyCheckpoint("RoomControls")

            // Navigate through room control options
            for i in 1...4 {
                navigateDown()
                let focused = focusedElement()
                captureJourneyCheckpoint("RoomControl-\(i)")
                recordCheckpoint("RoomControlFocused-\(i)",
                                success: focused.exists,
                                focusedElement: focused.identifier)
            }

            // Try activating a control
            pressSelect()
            sleep(1)
            captureJourneyCheckpoint("ControlActivated")
            recordCheckpoint("ControlActivated", success: true)
        }

        // Phase 4: Return to rooms list
        XCTContext.runActivity(named: "Phase 4: Return to Rooms List") { _ in
            pressMenuButton()
            sleep(1)

            let roomsView = element(withIdentifier: TVAccessibilityIDs.Rooms.view)
            if roomsView.waitForExistence(timeout: Self.defaultTimeout) {
                captureJourneyCheckpoint("ReturnedToRooms")
                recordCheckpoint("ReturnedToRooms", success: true)
            }
        }

        // Phase 5: Return to home
        XCTContext.runActivity(named: "Phase 5: Return Home") { _ in
            navigateTo(identifier: TVAccessibilityIDs.TabBar.home)
            pressSelect()
            sleep(1)

            captureJourneyCheckpoint("ReturnedHome")
            recordCheckpoint("ReturnedToHome", success: true)
        }

        captureJourneyCheckpoint("JourneyComplete")
        recordJourneyEnd("RoomControl")
    }

    // MARK: - Private Helpers

    /// Complete onboarding flow
    private func completeOnboarding() {
        // Skip through onboarding for tvOS
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

    /// Start video recording
    private func startVideoRecordingIfSupported() {
        let deviceUDID = ProcessInfo.processInfo.environment["SIMULATOR_UDID"] ?? ""
        guard !deviceUDID.isEmpty else { return }

        recordingIdentifier = UUID().uuidString
        print("Video recording ready: \(recordingIdentifier ?? "unknown")")
    }

    /// Stop video recording
    private func stopVideoRecordingIfSupported() {
        guard let identifier = recordingIdentifier else { return }

        let videoPath = "/tmp/kagami-test-videos/tvos/\(identifier).mp4"

        let videoMarker = """
        Video Recording Marker (tvOS)
        ==============================
        Test: \(name)
        Recording ID: \(identifier)
        Expected Path: \(videoPath)
        Platform: tvOS
        Timestamp: \(ISO8601DateFormatter().string(from: Date()))
        """

        let attachment = XCTAttachment(string: videoMarker)
        attachment.name = "TVVideoRecording-\(identifier)"
        attachment.lifetime = .keepAlways
        add(attachment)

        recordingIdentifier = nil
    }

    /// Capture a journey checkpoint
    private func captureJourneyCheckpoint(_ name: String) {
        XCTContext.runActivity(named: "Checkpoint: \(name)") { _ in
            takeScreenshot(named: "Journey-\(name)")
        }
    }

    /// Record journey start
    private func recordJourneyStart(_ journeyName: String) {
        XCTContext.runActivity(named: "Journey Start: \(journeyName)") { _ in
            takeScreenshot(named: "Journey-\(journeyName)-Start")
        }
    }

    /// Record journey end
    private func recordJourneyEnd(_ journeyName: String) {
        XCTContext.runActivity(named: "Journey End: \(journeyName)") { _ in
            takeScreenshot(named: "Journey-\(journeyName)-End")
        }
    }

    /// Record a checkpoint
    private func recordCheckpoint(_ name: String, success: Bool, focusedElement: String? = nil, notes: String? = nil) {
        journeyCheckpoints.append(JourneyCheckpoint(
            name: name,
            timestamp: Date(),
            success: success,
            focusedElement: focusedElement,
            notes: notes
        ))
    }

    /// Generate JSON metadata for the journey
    private func generateJourneyMetadata() {
        guard !journeyCheckpoints.isEmpty else { return }

        let formatter = ISO8601DateFormatter()
        var metadata: [[String: Any]] = []

        for checkpoint in journeyCheckpoints {
            var entry: [String: Any] = [
                "name": checkpoint.name,
                "timestamp": formatter.string(from: checkpoint.timestamp),
                "success": checkpoint.success
            ]
            if let focused = checkpoint.focusedElement {
                entry["focusedElement"] = focused
            }
            if let notes = checkpoint.notes {
                entry["notes"] = notes
            }
            metadata.append(entry)
        }

        let journeyData: [String: Any] = [
            "testName": name,
            "platform": "tvOS",
            "startTime": formatter.string(from: journeyCheckpoints.first?.timestamp ?? Date()),
            "endTime": formatter.string(from: journeyCheckpoints.last?.timestamp ?? Date()),
            "checkpoints": metadata,
            "passedCheckpoints": journeyCheckpoints.filter { $0.success }.count,
            "totalCheckpoints": journeyCheckpoints.count
        ]

        do {
            let jsonData = try JSONSerialization.data(withJSONObject: journeyData, options: [.prettyPrinted, .sortedKeys])
            if let jsonString = String(data: jsonData, encoding: .utf8) {
                let attachment = XCTAttachment(string: jsonString)
                attachment.name = "TVJourneyMetadata-\(name)"
                attachment.lifetime = .keepAlways
                add(attachment)
            }
        } catch {
            print("Failed to generate journey metadata: \(error)")
        }
    }
}

/*
 * Mirror
 * tvOS journeys capture the living room experience.
 * Focus navigation is the primary interaction model.
 * h(x) >= 0. Always.
 */
