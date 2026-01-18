//
// VisionVisualRegressionTests.swift -- visionOS Visual Regression Tests
//
// Colony: Crystal (e7) -- Verification & Polish
//
// Screenshot-based visual regression testing for Apple Vision Pro:
//   - 2D window interface captures
//   - Spatial UI element testing
//   - Interaction state verification
//   - Volumetric content screenshots (where applicable)
//
// Run:
//   xcodebuild test -scheme KagamiVision -destination 'platform=visionOS Simulator,name=Apple Vision Pro'
//     -only-testing:KagamiVisionUITests/VisionVisualRegressionTests
//
// h(x) >= 0. Always.
//

import XCTest

final class VisionVisualRegressionTests: KagamiVisionUITestCase {

    // Skip onboarding for visual tests
    override var skipOnboarding: Bool { true }

    // MARK: - Home Window Tests

    func testHomeWindowVisual() {
        ensureOnHomeWindow()
        captureVisualState(named: "HomeWindow-Default")
    }

    func testHomeWindowControlPanel() {
        ensureOnHomeWindow()

        let controlPanel = element(withIdentifier: VisionAccessibilityIDs.Home.controlPanel)
        if controlPanel.waitForExistence(timeout: 5) {
            captureVisualState(named: "HomeWindow-ControlPanel")
        }
    }

    func testHomeWindowQuickActions() {
        ensureOnHomeWindow()

        let quickActions = element(withIdentifier: VisionAccessibilityIDs.Home.quickActions)
        if quickActions.waitForExistence(timeout: 5) {
            captureVisualState(named: "HomeWindow-QuickActions")
        }
    }

    // MARK: - Rooms Window Tests

    func testRoomsWindowVisual() {
        ensureOnHomeWindow()
        navigateToTab(.rooms)
        sleep(2)

        captureVisualState(named: "RoomsWindow-Default")
    }

    func testRoomsSpatialView() {
        ensureOnHomeWindow()
        navigateToTab(.rooms)
        sleep(2)

        let spatialView = element(withIdentifier: VisionAccessibilityIDs.Rooms.spatialView)
        if spatialView.waitForExistence(timeout: 5) {
            captureVisualState(named: "RoomsWindow-SpatialView")
        }
    }

    func testRoomsListView() {
        ensureOnHomeWindow()
        navigateToTab(.rooms)
        sleep(2)

        let roomList = element(withIdentifier: VisionAccessibilityIDs.Rooms.roomList)
        if roomList.waitForExistence(timeout: 5) {
            captureVisualState(named: "RoomsWindow-ListView")
        }
    }

    // MARK: - Scenes Window Tests

    func testScenesWindowVisual() {
        ensureOnHomeWindow()
        navigateToTab(.scenes)
        sleep(2)

        captureVisualState(named: "ScenesWindow-Default")
    }

    func testScenesList() {
        ensureOnHomeWindow()
        navigateToTab(.scenes)
        sleep(2)

        let sceneList = element(withIdentifier: VisionAccessibilityIDs.Scenes.sceneList)
        if sceneList.waitForExistence(timeout: 5) {
            captureVisualState(named: "ScenesWindow-List")
        }
    }

    // MARK: - Settings Window Tests

    func testSettingsWindowVisual() {
        ensureOnHomeWindow()
        navigateToTab(.settings)
        sleep(2)

        captureVisualState(named: "SettingsWindow-Default")
    }

    func testSettingsSpatialSection() {
        ensureOnHomeWindow()
        navigateToTab(.settings)
        sleep(2)

        let spatialSection = element(withIdentifier: VisionAccessibilityIDs.Settings.spatialSection)
        if spatialSection.waitForExistence(timeout: 5) {
            tapElement(spatialSection)
            sleep(1)
            captureVisualState(named: "SettingsWindow-Spatial")
        }
    }

    func testSettingsAccessibilitySection() {
        ensureOnHomeWindow()
        navigateToTab(.settings)
        sleep(2)

        let accessibilitySection = element(withIdentifier: VisionAccessibilityIDs.Settings.accessibilitySection)
        if accessibilitySection.waitForExistence(timeout: 5) {
            tapElement(accessibilitySection)
            sleep(1)
            captureVisualState(named: "SettingsWindow-Accessibility")
        }
    }

    // MARK: - Spatial Experience Tests

    func testSpatialExperienceVisual() {
        ensureOnHomeWindow()
        navigateToTab(.spatial)
        sleep(3)

        let fullExperience = element(withIdentifier: VisionAccessibilityIDs.Spatial.fullExperience)
        if fullExperience.waitForExistence(timeout: 10) {
            captureVisualState(named: "SpatialExperience-Full")
        }
    }

    func testCommandPaletteVisual() {
        ensureOnHomeWindow()
        navigateToTab(.spatial)
        sleep(2)

        let commandPalette = element(withIdentifier: VisionAccessibilityIDs.Spatial.commandPalette)
        if commandPalette.waitForExistence(timeout: 5) {
            captureVisualState(named: "SpatialExperience-CommandPalette")
        }
    }

    func testSpatialBreadcrumbVisual() {
        ensureOnHomeWindow()
        navigateToTab(.spatial)
        sleep(2)

        let breadcrumb = element(withIdentifier: VisionAccessibilityIDs.Spatial.breadcrumb)
        if breadcrumb.waitForExistence(timeout: 5) {
            captureVisualState(named: "SpatialExperience-Breadcrumb")
        }
    }

    func testRoom3DViewVisual() {
        ensureOnHomeWindow()
        navigateToTab(.spatial)
        sleep(2)

        let roomView3D = element(withIdentifier: VisionAccessibilityIDs.Spatial.roomView3D)
        if roomView3D.waitForExistence(timeout: 5) {
            captureVisualState(named: "SpatialExperience-Room3D")
        }
    }

    // MARK: - Voice Command Window Tests

    func testVoiceCommandWindowVisual() {
        ensureOnHomeWindow()

        let voiceActivate = element(withIdentifier: VisionAccessibilityIDs.VoiceCommand.activateButton)
        if voiceActivate.waitForExistence(timeout: 5) {
            tapElement(voiceActivate)
            sleep(1)

            let voiceWindow = element(withIdentifier: VisionAccessibilityIDs.VoiceCommand.window)
            if voiceWindow.waitForExistence(timeout: 5) {
                captureVisualState(named: "VoiceCommand-Active")
            }
        }
    }

    // MARK: - Interaction State Tests

    func testTapInteractionVisual() {
        ensureOnHomeWindow()

        // Find a tappable element
        let button = app.buttons.firstMatch
        if button.waitForExistence(timeout: 5) {
            // Capture before tap
            captureVisualState(named: "Interaction-BeforeTap")

            // Tap
            tapElement(button)

            // Capture after tap
            captureVisualState(named: "Interaction-AfterTap")
        }
    }

    func testHoverStateVisual() {
        ensureOnHomeWindow()

        // In visionOS, hover is gaze-based
        // The simulator shows hover when the cursor is over an element
        let card = app.otherElements.matching(identifier: "prism-card").firstMatch
        if card.waitForExistence(timeout: 5) {
            // Capture hover state
            captureVisualState(named: "Interaction-HoverState")
        }
    }

    // MARK: - Full Visual Sweep

    func testFullAppVisualSweep() {
        ensureOnHomeWindow()

        let screens: [(String, () -> Void)] = [
            ("Home", { self.ensureOnHomeWindow() }),
            ("Rooms", {
                self.navigateToTab(.rooms)
                sleep(2)
            }),
            ("Scenes", {
                self.navigateToTab(.scenes)
                sleep(2)
            }),
            ("Settings", {
                self.navigateToTab(.settings)
                sleep(2)
            }),
            ("Spatial", {
                self.navigateToTab(.spatial)
                sleep(3)
            })
        ]

        for (name, navigate) in screens {
            navigate()
            captureVisualState(named: "VisualSweep-\(name)")
        }
    }

    // MARK: - Onboarding Visual Tests

    func testOnboardingVisual() {
        // Reset to show onboarding
        app.launchArguments.removeAll { $0 == "-SkipOnboarding" }
        app.launchArguments.append("-ResetState")
        app.launch()
        waitForAppReady()

        let onboardingWindow = element(withIdentifier: VisionAccessibilityIDs.Onboarding.window)
        if onboardingWindow.waitForExistence(timeout: 10) {
            captureVisualState(named: "Onboarding-Welcome")
        }
    }

    func testOnboardingSpatialTutorialVisual() {
        app.launchArguments.removeAll { $0 == "-SkipOnboarding" }
        app.launchArguments.append("-ResetState")
        app.launch()
        waitForAppReady()

        // Navigate to spatial tutorial step
        let continueButton = element(withIdentifier: VisionAccessibilityIDs.Onboarding.continueButton)
        if continueButton.waitForExistence(timeout: 5) {
            tapElement(continueButton)
            sleep(1)
            tapElement(continueButton)
            sleep(1)

            let spatialTutorial = element(withIdentifier: VisionAccessibilityIDs.Onboarding.spatialTutorial)
            if spatialTutorial.waitForExistence(timeout: 5) {
                captureVisualState(named: "Onboarding-SpatialTutorial")
            }
        }
    }

    // MARK: - Helper Methods

    private func ensureOnHomeWindow() {
        let homeWindow = element(withIdentifier: VisionAccessibilityIDs.Home.window)
        if !homeWindow.waitForExistence(timeout: 3) {
            navigateToTab(.home)
            sleep(2)
        }
    }
}

// MARK: - Spatial User Journey Tests

extension VisionVisualRegressionTests {

    func testSpatialUserJourney() {
        ensureOnHomeWindow()
        captureVisualState(named: "Journey-Start")

        let steps: [(String, () -> Void)] = [
            ("OpenRooms", {
                self.navigateToTab(.rooms)
                sleep(2)
            }),
            ("ViewSpatialRoom", {
                let spatialView = self.element(withIdentifier: VisionAccessibilityIDs.Rooms.spatialView)
                if spatialView.exists {
                    self.tapElement(spatialView)
                    sleep(2)
                }
            }),
            ("InteractWithDevice", {
                // Find a device control
                let deviceControl = self.app.buttons.matching(NSPredicate(format: "identifier CONTAINS 'device'")).firstMatch
                if deviceControl.exists {
                    self.tapElement(deviceControl)
                    sleep(1)
                }
            }),
            ("OpenCommandPalette", {
                let commandPalette = self.element(withIdentifier: VisionAccessibilityIDs.Spatial.commandPalette)
                if commandPalette.exists {
                    self.tapElement(commandPalette)
                    sleep(1)
                }
            }),
            ("ExecuteCommand", {
                // Type a command if possible
                let commandInput = self.app.textFields.firstMatch
                if commandInput.exists {
                    commandInput.tap()
                    commandInput.typeText("lights 50")
                    sleep(1)
                }
            }),
            ("ReturnHome", {
                self.navigateToTab(.home)
                sleep(2)
            })
        ]

        for (index, (name, action)) in steps.enumerated() {
            action()
            captureVisualState(named: "Journey-Step\(index + 1)-\(name)")
        }

        captureVisualState(named: "Journey-Complete")
    }
}

/*
 * Mirror
 * visionOS visual tests ensure spatial computing excellence.
 * h(x) >= 0. Always.
 */
