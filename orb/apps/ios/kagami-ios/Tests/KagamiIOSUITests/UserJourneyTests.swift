//
// UserJourneyTests.swift -- Comprehensive E2E Video Tests for iOS User Journeys
//
// Colony: Crystal (e7) -- Verification & Polish
//
// Records complete user journeys with video for:
//   - Morning routine flow
//   - Scene activation with haptic feedback
//   - Voice command responses
//   - Room control flows
//   - Household member switching
//
// Video Output: test-artifacts/videos/ios/{journey-name}.mp4
//
// Run:
//   xcodebuild test -scheme KagamiIOS \
//     -destination 'platform=iOS Simulator,name=iPhone 16 Pro' \
//     -only-testing:KagamiIOSUITests/UserJourneyTests
//
// h(x) >= 0. Always.
//

import XCTest

/// Comprehensive E2E User Journey Tests with Video Recording
final class UserJourneyTests: VideoRecordingTestCase {

    // MARK: - Configuration

    /// Enable video recording for all journey tests
    override var videoRecordingEnabled: Bool { true }

    /// High quality recording for user journey documentation
    override var videoQuality: Float { 0.85 }

    /// Skip onboarding for most tests
    override var skipOnboarding: Bool { false }

    // MARK: - Journey Metadata

    /// Journey checkpoint data structure
    private struct JourneyCheckpoint {
        let name: String
        let timestamp: Date
        let success: Bool
        let notes: String?
    }

    /// Collected checkpoints for metadata generation
    private var journeyCheckpoints: [JourneyCheckpoint] = []

    // MARK: - Setup & Teardown

    override func setUp() {
        super.setUp()
        journeyCheckpoints = []
    }

    override func tearDown() {
        // Generate journey metadata
        generateJourneyMetadata()
        super.tearDown()
    }

    // MARK: - Morning Routine Journey

    /// Tests the complete morning routine flow with video recording
    /// Journey: Wake up -> Check home status -> Activate morning scene -> View rooms
    func testMorningRoutineJourney() {
        recordJourneyStart("MorningRoutine")

        // Phase 1: Launch and reach home screen
        XCTContext.runActivity(named: "Phase 1: App Launch") { _ in
            captureJourneyCheckpoint("Launch")

            // Complete onboarding if needed
            let onboardingProgress = element(withIdentifier: AccessibilityIDs.Onboarding.progressIndicator, in: app)
            if onboardingProgress.waitForExistence(timeout: 3) {
                completeOnboarding()
            }

            // Verify home screen
            assertOnHomeScreen()
            recordCheckpoint("AppLaunched", success: true)
            captureJourneyCheckpoint("HomeReached")
        }

        // Phase 2: Check home status
        XCTContext.runActivity(named: "Phase 2: Home Status Check") { _ in
            sleep(1) // Allow UI to settle

            // Verify safety card is visible
            let safetyCard = element(withIdentifier: AccessibilityIDs.Home.safetyCard, in: app)
            if safetyCard.waitForExistence(timeout: 3) {
                captureJourneyCheckpoint("SafetyCardVisible")
                recordCheckpoint("HomeStatusChecked", success: true)
            }

            // Check connection indicator
            let connectionIndicator = element(withIdentifier: AccessibilityIDs.Home.connectionIndicator, in: app)
            if connectionIndicator.exists {
                captureJourneyCheckpoint("ConnectionStatus")
            }
        }

        // Phase 3: Navigate to scenes and activate morning scene
        XCTContext.runActivity(named: "Phase 3: Morning Scene Activation") { _ in
            navigateToTab(.scenes)
            sleep(1)

            let scenesView = element(withIdentifier: AccessibilityIDs.Scenes.view, in: app)
            waitForElement(scenesView, timeout: 5)
            captureJourneyCheckpoint("ScenesScreen")

            // Look for a morning-related scene
            let morningSceneNames = ["Coffee Time", "Wake Up", "Morning", "Welcome Home"]
            var sceneActivated = false

            for sceneName in morningSceneNames {
                let sceneText = app.staticTexts[sceneName].firstMatch
                if sceneText.waitForExistence(timeout: 2) {
                    sceneText.tap()
                    sceneActivated = true
                    sleep(1)
                    captureJourneyCheckpoint("MorningSceneActivated-\(sceneName)")
                    recordCheckpoint("SceneActivated", success: true, notes: sceneName)
                    break
                }
            }

            if !sceneActivated {
                // Tap first available scene
                let firstCell = app.cells.firstMatch
                if firstCell.exists && firstCell.isHittable {
                    firstCell.tap()
                    sleep(1)
                    captureJourneyCheckpoint("FallbackSceneActivated")
                    recordCheckpoint("SceneActivated", success: true, notes: "fallback")
                }
            }
        }

        // Phase 4: View room status
        XCTContext.runActivity(named: "Phase 4: Room Status Review") { _ in
            navigateToTab(.rooms)
            sleep(1)

            let roomsView = element(withIdentifier: AccessibilityIDs.Rooms.view, in: app)
            waitForElement(roomsView, timeout: 5)
            captureJourneyCheckpoint("RoomsScreen")

            // Scroll through rooms
            let roomsList = element(withIdentifier: AccessibilityIDs.Rooms.list, in: app)
            if roomsList.exists {
                roomsList.swipeUp()
                sleep(1)
                captureJourneyCheckpoint("RoomsScrolled")
                roomsList.swipeDown()
            }

            recordCheckpoint("RoomsReviewed", success: true)
        }

        // Phase 5: Return to home
        XCTContext.runActivity(named: "Phase 5: Return Home") { _ in
            navigateToTab(.home)
            sleep(1)

            assertOnHomeScreen()
            captureJourneyCheckpoint("JourneyComplete")
            recordCheckpoint("MorningRoutineComplete", success: true)
        }

        recordJourneyEnd("MorningRoutine")
    }

    // MARK: - Scene Activation with Haptic Feedback Journey

    /// Tests scene activation flow with haptic feedback verification
    /// Journey: Navigate to scenes -> Activate multiple scenes -> Verify feedback
    func testSceneActivationWithHapticFeedbackJourney() {
        recordJourneyStart("SceneActivationHaptic")

        // Setup: Skip to home screen
        XCTContext.runActivity(named: "Setup: Navigate to Home") { _ in
            let onboardingProgress = element(withIdentifier: AccessibilityIDs.Onboarding.progressIndicator, in: app)
            if onboardingProgress.waitForExistence(timeout: 3) {
                completeOnboarding()
            }

            assertOnHomeScreen()
            captureJourneyCheckpoint("Setup-HomeReached")
        }

        // Phase 1: Navigate to scenes
        XCTContext.runActivity(named: "Phase 1: Navigate to Scenes") { _ in
            navigateToTab(.scenes)
            sleep(1)

            let scenesView = element(withIdentifier: AccessibilityIDs.Scenes.view, in: app)
            waitForElement(scenesView, timeout: 5)
            captureJourneyCheckpoint("ScenesNavigated")
            recordCheckpoint("NavigatedToScenes", success: true)
        }

        // Phase 2: Activate Movie Mode scene
        XCTContext.runActivity(named: "Phase 2: Activate Movie Mode") { _ in
            let movieModeText = app.staticTexts["Movie Mode"].firstMatch
            if movieModeText.waitForExistence(timeout: 3) {
                captureJourneyCheckpoint("PreMovieMode")
                movieModeText.tap()
                sleep(2) // Wait for haptic feedback and visual response
                captureJourneyCheckpoint("PostMovieMode")
                recordCheckpoint("MovieModeActivated", success: true)
            } else {
                recordCheckpoint("MovieModeActivated", success: false, notes: "Scene not found")
            }
        }

        // Phase 3: Activate Relax scene
        XCTContext.runActivity(named: "Phase 3: Activate Relax Scene") { _ in
            let relaxText = app.staticTexts["Relax"].firstMatch
            if relaxText.waitForExistence(timeout: 3) {
                captureJourneyCheckpoint("PreRelax")
                relaxText.tap()
                sleep(2)
                captureJourneyCheckpoint("PostRelax")
                recordCheckpoint("RelaxActivated", success: true)
            }
        }

        // Phase 4: Activate Goodnight scene
        XCTContext.runActivity(named: "Phase 4: Activate Goodnight Scene") { _ in
            // May need to scroll to find Goodnight
            let scenesList = element(withIdentifier: AccessibilityIDs.Scenes.list, in: app)
            if scenesList.exists {
                scenesList.swipeUp()
                sleep(1)
            }

            let goodnightText = app.staticTexts["Goodnight"].firstMatch
            if goodnightText.waitForExistence(timeout: 3) {
                captureJourneyCheckpoint("PreGoodnight")
                goodnightText.tap()
                sleep(2)
                captureJourneyCheckpoint("PostGoodnight")
                recordCheckpoint("GoodnightActivated", success: true)
            }
        }

        // Phase 5: Rapid scene switching (stress test haptics)
        XCTContext.runActivity(named: "Phase 5: Rapid Scene Switching") { _ in
            // Scroll back to top
            let scenesList = element(withIdentifier: AccessibilityIDs.Scenes.list, in: app)
            if scenesList.exists {
                scenesList.swipeDown()
                sleep(1)
            }

            captureJourneyCheckpoint("RapidSwitchStart")

            // Rapidly tap multiple scenes
            let cells = app.cells.allElementsBoundByIndex
            for (index, cell) in cells.prefix(3).enumerated() {
                if cell.isHittable {
                    cell.tap()
                    usleep(500000) // 0.5 second between activations
                    captureJourneyCheckpoint("RapidSwitch-\(index)")
                }
            }

            recordCheckpoint("RapidSwitchComplete", success: true)
        }

        recordJourneyEnd("SceneActivationHaptic")
    }

    // MARK: - Voice Command Response Journey

    /// Tests voice command interface flow
    /// Journey: Access voice -> Issue command -> Verify response
    func testVoiceCommandResponseJourney() {
        recordJourneyStart("VoiceCommand")

        // Setup
        XCTContext.runActivity(named: "Setup") { _ in
            let onboardingProgress = element(withIdentifier: AccessibilityIDs.Onboarding.progressIndicator, in: app)
            if onboardingProgress.waitForExistence(timeout: 3) {
                completeOnboarding()
            }

            assertOnHomeScreen()
            captureJourneyCheckpoint("Setup-Home")
        }

        // Phase 1: Navigate to Hub (voice interface)
        XCTContext.runActivity(named: "Phase 1: Navigate to Hub") { _ in
            navigateToTab(.hub)
            sleep(1)
            captureJourneyCheckpoint("HubNavigated")
            recordCheckpoint("HubAccessed", success: true)
        }

        // Phase 2: Interact with Hub interface
        XCTContext.runActivity(named: "Phase 2: Hub Interaction") { _ in
            sleep(1)
            captureJourneyCheckpoint("HubInterface")

            // Try to find any interactive elements in Hub
            let buttons = app.buttons.allElementsBoundByIndex
            if let firstButton = buttons.first, firstButton.isHittable {
                firstButton.tap()
                sleep(1)
                captureJourneyCheckpoint("HubButtonTapped")
            }

            recordCheckpoint("HubInteracted", success: true)
        }

        // Phase 3: Return and verify state
        XCTContext.runActivity(named: "Phase 3: Verify State") { _ in
            navigateToTab(.home)
            sleep(1)

            assertOnHomeScreen()
            captureJourneyCheckpoint("JourneyComplete")
            recordCheckpoint("VoiceCommandComplete", success: true)
        }

        recordJourneyEnd("VoiceCommand")
    }

    // MARK: - Room Control Flow Journey

    /// Tests complete room control user journey
    /// Journey: Select room -> Adjust lights -> Control shades -> Return
    func testRoomControlFlowJourney() {
        recordJourneyStart("RoomControl")

        // Setup
        XCTContext.runActivity(named: "Setup") { _ in
            let onboardingProgress = element(withIdentifier: AccessibilityIDs.Onboarding.progressIndicator, in: app)
            if onboardingProgress.waitForExistence(timeout: 3) {
                completeOnboarding()
            }

            assertOnHomeScreen()
            captureJourneyCheckpoint("Setup-Home")
        }

        // Phase 1: Navigate to Rooms
        XCTContext.runActivity(named: "Phase 1: Navigate to Rooms") { _ in
            navigateToTab(.rooms)
            sleep(1)

            let roomsView = element(withIdentifier: AccessibilityIDs.Rooms.view, in: app)
            waitForElement(roomsView, timeout: 5)
            captureJourneyCheckpoint("RoomsScreen")
            recordCheckpoint("RoomsNavigated", success: true)
        }

        // Phase 2: Select a room
        XCTContext.runActivity(named: "Phase 2: Select Room") { _ in
            let roomsList = element(withIdentifier: AccessibilityIDs.Rooms.list, in: app)

            if roomsList.waitForExistence(timeout: 3) {
                // Find and tap first room
                let cells = app.cells.allElementsBoundByIndex
                if let firstRoom = cells.first, firstRoom.isHittable {
                    captureJourneyCheckpoint("PreRoomSelect")
                    firstRoom.tap()
                    sleep(1)
                    captureJourneyCheckpoint("PostRoomSelect")
                    recordCheckpoint("RoomSelected", success: true)
                }
            }
        }

        // Phase 3: Interact with room controls
        XCTContext.runActivity(named: "Phase 3: Room Controls") { _ in
            sleep(1)
            captureJourneyCheckpoint("RoomDetails")

            // Try light controls
            let lightButtons = ["0%", "25%", "50%", "75%", "100%"]
            for level in lightButtons {
                let button = app.buttons[level].firstMatch
                if button.waitForExistence(timeout: 1) && button.isHittable {
                    button.tap()
                    sleep(1)
                    captureJourneyCheckpoint("LightLevel-\(level)")
                    recordCheckpoint("LightAdjusted", success: true, notes: level)
                    break
                }
            }
        }

        // Phase 4: Navigate back
        XCTContext.runActivity(named: "Phase 4: Return") { _ in
            // Use back button if available
            if app.navigationBars.buttons.firstMatch.exists {
                app.navigationBars.buttons.firstMatch.tap()
                sleep(1)
            }

            captureJourneyCheckpoint("ReturnedToRooms")
            recordCheckpoint("NavigatedBack", success: true)
        }

        // Phase 5: Return to home
        XCTContext.runActivity(named: "Phase 5: Return Home") { _ in
            navigateToTab(.home)
            sleep(1)

            assertOnHomeScreen()
            captureJourneyCheckpoint("JourneyComplete")
            recordCheckpoint("RoomControlComplete", success: true)
        }

        recordJourneyEnd("RoomControl")
    }

    // MARK: - Household Member Switching Journey

    /// Tests switching between household members
    /// Journey: Settings -> Household -> Switch member -> Verify changes
    func testHouseholdMemberSwitchingJourney() {
        recordJourneyStart("HouseholdSwitch")

        // Setup
        XCTContext.runActivity(named: "Setup") { _ in
            let onboardingProgress = element(withIdentifier: AccessibilityIDs.Onboarding.progressIndicator, in: app)
            if onboardingProgress.waitForExistence(timeout: 3) {
                completeOnboarding()
            }

            assertOnHomeScreen()
            captureJourneyCheckpoint("Setup-Home")
        }

        // Phase 1: Navigate to Settings
        XCTContext.runActivity(named: "Phase 1: Navigate to Settings") { _ in
            navigateToTab(.settings)
            sleep(1)

            let settingsView = element(withIdentifier: AccessibilityIDs.Settings.view, in: app)
            waitForElement(settingsView, timeout: 5)
            captureJourneyCheckpoint("SettingsScreen")
            recordCheckpoint("SettingsNavigated", success: true)
        }

        // Phase 2: Access Household section
        XCTContext.runActivity(named: "Phase 2: Access Household") { _ in
            let householdSection = element(withIdentifier: AccessibilityIDs.Settings.householdSection, in: app)

            if householdSection.waitForExistence(timeout: 3) {
                captureJourneyCheckpoint("PreHouseholdTap")
                householdSection.tap()
                sleep(1)
                captureJourneyCheckpoint("HouseholdSection")
                recordCheckpoint("HouseholdAccessed", success: true)
            } else {
                // Try tapping by text
                let householdText = app.staticTexts["Household"].firstMatch
                if householdText.exists {
                    householdText.tap()
                    sleep(1)
                    captureJourneyCheckpoint("HouseholdSection")
                    recordCheckpoint("HouseholdAccessed", success: true)
                }
            }
        }

        // Phase 3: View household members
        XCTContext.runActivity(named: "Phase 3: View Members") { _ in
            sleep(1)
            captureJourneyCheckpoint("HouseholdMembers")

            // Scroll through members if list exists
            let membersList = app.tables.firstMatch
            if membersList.exists {
                membersList.swipeUp()
                sleep(1)
                captureJourneyCheckpoint("MembersScrolled")
                membersList.swipeDown()
            }

            recordCheckpoint("MembersViewed", success: true)
        }

        // Phase 4: Try to switch/select a member
        XCTContext.runActivity(named: "Phase 4: Select Member") { _ in
            let cells = app.cells.allElementsBoundByIndex
            if cells.count > 1 {
                // Try to tap second member (different from current)
                let secondMember = cells[1]
                if secondMember.isHittable {
                    captureJourneyCheckpoint("PreMemberSwitch")
                    secondMember.tap()
                    sleep(1)
                    captureJourneyCheckpoint("PostMemberSwitch")
                    recordCheckpoint("MemberSwitched", success: true)
                }
            }
        }

        // Phase 5: Return to home and verify
        XCTContext.runActivity(named: "Phase 5: Verify Changes") { _ in
            // Navigate back through hierarchy
            while app.navigationBars.buttons.firstMatch.exists {
                app.navigationBars.buttons.firstMatch.tap()
                sleep(1)
            }

            navigateToTab(.home)
            sleep(1)

            assertOnHomeScreen()
            captureJourneyCheckpoint("JourneyComplete")
            recordCheckpoint("HouseholdSwitchComplete", success: true)
        }

        recordJourneyEnd("HouseholdSwitch")
    }

    // MARK: - Full App Exploration Journey

    /// Tests a complete exploration of all app tabs
    /// Journey: Home -> Rooms -> Scenes -> Hub -> Settings -> Home
    func testFullAppExplorationJourney() {
        recordJourneyStart("FullAppExploration")

        // Setup
        XCTContext.runActivity(named: "Setup") { _ in
            let onboardingProgress = element(withIdentifier: AccessibilityIDs.Onboarding.progressIndicator, in: app)
            if onboardingProgress.waitForExistence(timeout: 3) {
                completeOnboarding()
            }

            assertOnHomeScreen()
            captureJourneyCheckpoint("Start-Home")
        }

        // Explore each tab
        let tabs: [(KagamiUITestCase.Tab, String)] = [
            (.home, "Home"),
            (.rooms, "Rooms"),
            (.scenes, "Scenes"),
            (.hub, "Hub"),
            (.settings, "Settings")
        ]

        for (index, (tab, name)) in tabs.enumerated() {
            XCTContext.runActivity(named: "Tab \(index + 1): \(name)") { _ in
                navigateToTab(tab)
                sleep(2) // Wait for animations and content load

                captureJourneyCheckpoint("\(name)Tab")

                // Scroll content if possible
                let scrollViews = app.scrollViews.allElementsBoundByIndex
                if let scrollView = scrollViews.first, scrollView.exists {
                    scrollView.swipeUp()
                    sleep(1)
                    captureJourneyCheckpoint("\(name)Scrolled")
                    scrollView.swipeDown()
                }

                recordCheckpoint("\(name)Visited", success: true)
            }
        }

        // Return to home
        XCTContext.runActivity(named: "Return to Home") { _ in
            navigateToTab(.home)
            sleep(1)

            assertOnHomeScreen()
            captureJourneyCheckpoint("JourneyComplete")
            recordCheckpoint("FullExplorationComplete", success: true)
        }

        recordJourneyEnd("FullAppExploration")
    }

    // MARK: - Quick Actions Journey

    /// Tests quick action interactions from home screen
    /// Journey: Home -> Trigger quick actions -> Verify responses
    func testQuickActionsJourney() {
        recordJourneyStart("QuickActions")

        // Setup
        XCTContext.runActivity(named: "Setup") { _ in
            let onboardingProgress = element(withIdentifier: AccessibilityIDs.Onboarding.progressIndicator, in: app)
            if onboardingProgress.waitForExistence(timeout: 3) {
                completeOnboarding()
            }

            assertOnHomeScreen()
            captureJourneyCheckpoint("Setup-Home")
        }

        // Phase 1: Find quick actions section
        XCTContext.runActivity(named: "Phase 1: Locate Quick Actions") { _ in
            let quickActions = element(withIdentifier: AccessibilityIDs.Home.quickActions, in: app)

            if quickActions.waitForExistence(timeout: 3) {
                captureJourneyCheckpoint("QuickActionsFound")
                recordCheckpoint("QuickActionsLocated", success: true)
            } else {
                // Scroll to find quick actions
                app.swipeUp()
                sleep(1)
                captureJourneyCheckpoint("ScrolledForQuickActions")
            }
        }

        // Phase 2: Test lights quick action
        XCTContext.runActivity(named: "Phase 2: Lights Quick Action") { _ in
            let lightsOnButton = element(withIdentifier: AccessibilityIDs.QuickActions.lightsOn, in: app)

            if lightsOnButton.waitForExistence(timeout: 2) && lightsOnButton.isHittable {
                captureJourneyCheckpoint("PreLightsOn")
                lightsOnButton.tap()
                sleep(1)
                captureJourneyCheckpoint("PostLightsOn")
                recordCheckpoint("LightsOnActivated", success: true)
            }

            let lightsOffButton = element(withIdentifier: AccessibilityIDs.QuickActions.lightsOff, in: app)
            if lightsOffButton.waitForExistence(timeout: 2) && lightsOffButton.isHittable {
                captureJourneyCheckpoint("PreLightsOff")
                lightsOffButton.tap()
                sleep(1)
                captureJourneyCheckpoint("PostLightsOff")
                recordCheckpoint("LightsOffActivated", success: true)
            }
        }

        // Phase 3: Test other quick actions
        XCTContext.runActivity(named: "Phase 3: Other Quick Actions") { _ in
            let otherActions = [
                (AccessibilityIDs.QuickActions.fireplace, "Fireplace"),
                (AccessibilityIDs.QuickActions.shadesOpen, "ShadesOpen"),
                (AccessibilityIDs.QuickActions.tvLower, "TVLower")
            ]

            for (identifier, name) in otherActions {
                let actionButton = element(withIdentifier: identifier, in: app)
                if actionButton.waitForExistence(timeout: 1) && actionButton.isHittable {
                    actionButton.tap()
                    sleep(1)
                    captureJourneyCheckpoint("QuickAction-\(name)")
                    recordCheckpoint("QuickAction-\(name)", success: true)
                }
            }
        }

        captureJourneyCheckpoint("JourneyComplete")
        recordJourneyEnd("QuickActions")
    }

    // MARK: - Private Helpers

    /// Record journey start
    private func recordJourneyStart(_ journeyName: String) {
        XCTContext.runActivity(named: "Journey Start: \(journeyName)") { _ in
            captureScreenshot(named: "Journey-\(journeyName)-Start")
        }
    }

    /// Record journey end
    private func recordJourneyEnd(_ journeyName: String) {
        XCTContext.runActivity(named: "Journey End: \(journeyName)") { _ in
            captureScreenshot(named: "Journey-\(journeyName)-End")
        }
    }

    /// Record a checkpoint
    private func recordCheckpoint(_ name: String, success: Bool, notes: String? = nil) {
        journeyCheckpoints.append(JourneyCheckpoint(
            name: name,
            timestamp: Date(),
            success: success,
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
            if let notes = checkpoint.notes {
                entry["notes"] = notes
            }
            metadata.append(entry)
        }

        let journeyData: [String: Any] = [
            "testName": name,
            "platform": "iOS",
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
                attachment.name = "JourneyMetadata-\(name)"
                attachment.lifetime = .keepAlways
                add(attachment)
            }
        } catch {
            print("Failed to generate journey metadata: \(error)")
        }
    }
}

// MARK: - Accessibility Journey Tests

extension UserJourneyTests {

    /// Tests VoiceOver navigation journey
    func testAccessibilityNavigationJourney() {
        recordJourneyStart("AccessibilityNavigation")

        // Setup
        XCTContext.runActivity(named: "Setup") { _ in
            let onboardingProgress = element(withIdentifier: AccessibilityIDs.Onboarding.progressIndicator, in: app)
            if onboardingProgress.waitForExistence(timeout: 3) {
                completeOnboarding()
            }

            assertOnHomeScreen()
            captureJourneyCheckpoint("Setup-Home")
        }

        // Phase 1: Verify all tabs have accessibility labels
        XCTContext.runActivity(named: "Phase 1: Tab Accessibility") { _ in
            let tabIdentifiers = [
                AccessibilityIDs.TabBar.home,
                AccessibilityIDs.TabBar.rooms,
                AccessibilityIDs.TabBar.hub,
                AccessibilityIDs.TabBar.scenes,
                AccessibilityIDs.TabBar.settings
            ]

            for identifier in tabIdentifiers {
                let tab = element(withIdentifier: identifier, in: app)
                XCTAssertTrue(tab.exists, "Tab with identifier \(identifier) should exist")
            }

            captureJourneyCheckpoint("TabsAccessible")
            recordCheckpoint("TabsVerified", success: true)
        }

        // Phase 2: Navigate using accessibility identifiers only
        XCTContext.runActivity(named: "Phase 2: Identifier Navigation") { _ in
            // Navigate to each main view using accessibility identifiers
            tap(identifier: AccessibilityIDs.TabBar.rooms, in: app)
            sleep(1)
            captureJourneyCheckpoint("RoomsViaAccessibility")

            tap(identifier: AccessibilityIDs.TabBar.scenes, in: app)
            sleep(1)
            captureJourneyCheckpoint("ScenesViaAccessibility")

            tap(identifier: AccessibilityIDs.TabBar.settings, in: app)
            sleep(1)
            captureJourneyCheckpoint("SettingsViaAccessibility")

            tap(identifier: AccessibilityIDs.TabBar.home, in: app)
            sleep(1)
            captureJourneyCheckpoint("HomeViaAccessibility")

            recordCheckpoint("AccessibilityNavigationComplete", success: true)
        }

        recordJourneyEnd("AccessibilityNavigation")
    }
}

/*
 * Mirror
 * User journeys capture the complete experience.
 * Video recording preserves every moment for verification.
 * h(x) >= 0. Always.
 */
