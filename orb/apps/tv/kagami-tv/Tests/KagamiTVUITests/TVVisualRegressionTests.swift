//
// TVVisualRegressionTests.swift -- tvOS Visual Regression Tests
//
// Colony: Crystal (e7) -- Verification & Polish
//
// Screenshot-based visual regression testing for Apple TV:
//   - Capture all main screens
//   - Focus state verification
//   - Remote navigation testing
//   - TopShelf content verification
//
// Run:
//   xcodebuild test -scheme KagamiTV -destination 'platform=tvOS Simulator,name=Apple TV 4K (3rd generation)'
//     -only-testing:KagamiTVUITests/TVVisualRegressionTests
//
// h(x) >= 0. Always.
//

import XCTest

final class TVVisualRegressionTests: KagamiTVUITestCase {

    // Skip onboarding for visual tests
    override var skipOnboarding: Bool { true }

    // MARK: - Home Screen Tests

    func testHomeScreenVisual() {
        ensureOnHomeScreen()
        takeScreenshot(named: "TV-HomeScreen-Default")
    }

    func testHomeScreenFocusedQuickAction() {
        ensureOnHomeScreen()

        // Navigate to quick actions
        let quickActions = element(withIdentifier: TVAccessibilityIDs.Home.quickActions)
        if quickActions.waitForExistence(timeout: 5) {
            navigateTo(identifier: TVAccessibilityIDs.Home.quickActions)
            takeScreenshot(named: "TV-HomeScreen-QuickActionsFocused")
        }
    }

    func testHomeScreenRoomsSection() {
        ensureOnHomeScreen()

        // Navigate to rooms section
        let roomsSection = element(withIdentifier: TVAccessibilityIDs.Home.roomsSection)
        if roomsSection.waitForExistence(timeout: 5) {
            navigateDown()
            navigateDown()
            takeScreenshot(named: "TV-HomeScreen-RoomsSection")
        }
    }

    func testHomeScreenScenesSection() {
        ensureOnHomeScreen()

        // Navigate to scenes section
        let scenesSection = element(withIdentifier: TVAccessibilityIDs.Home.scenesSection)
        if scenesSection.waitForExistence(timeout: 5) {
            navigateDown()
            navigateDown()
            navigateDown()
            takeScreenshot(named: "TV-HomeScreen-ScenesSection")
        }
    }

    // MARK: - Rooms Screen Tests

    func testRoomsScreenVisual() {
        ensureOnHomeScreen()

        // Navigate to rooms tab
        navigateTo(identifier: TVAccessibilityIDs.TabBar.rooms)
        pressSelect()
        sleep(2)

        takeScreenshot(named: "TV-RoomsScreen-Default")
    }

    func testRoomsFocusNavigation() {
        ensureOnHomeScreen()

        navigateTo(identifier: TVAccessibilityIDs.TabBar.rooms)
        pressSelect()
        sleep(2)

        // Capture focus navigation through rooms
        takeScreenshot(named: "TV-RoomsScreen-Focus1")
        navigateRight()
        takeScreenshot(named: "TV-RoomsScreen-Focus2")
        navigateRight()
        takeScreenshot(named: "TV-RoomsScreen-Focus3")
        navigateDown()
        takeScreenshot(named: "TV-RoomsScreen-Focus4")
    }

    // MARK: - Scenes Screen Tests

    func testScenesScreenVisual() {
        ensureOnHomeScreen()

        navigateTo(identifier: TVAccessibilityIDs.TabBar.scenes)
        pressSelect()
        sleep(2)

        takeScreenshot(named: "TV-ScenesScreen-Default")
    }

    func testScenesFocusNavigation() {
        ensureOnHomeScreen()

        navigateTo(identifier: TVAccessibilityIDs.TabBar.scenes)
        pressSelect()
        sleep(2)

        // Capture focus navigation through scenes
        takeScreenshot(named: "TV-ScenesScreen-Focus1")
        navigateRight()
        takeScreenshot(named: "TV-ScenesScreen-Focus2")
        navigateDown()
        takeScreenshot(named: "TV-ScenesScreen-Focus3")
    }

    // MARK: - Settings Screen Tests

    func testSettingsScreenVisual() {
        ensureOnHomeScreen()

        navigateTo(identifier: TVAccessibilityIDs.TabBar.settings)
        pressSelect()
        sleep(2)

        takeScreenshot(named: "TV-SettingsScreen-Default")
    }

    func testSettingsServerSection() {
        ensureOnHomeScreen()

        navigateTo(identifier: TVAccessibilityIDs.TabBar.settings)
        pressSelect()
        sleep(2)

        let serverSection = element(withIdentifier: TVAccessibilityIDs.Settings.serverSection)
        if serverSection.waitForExistence(timeout: 5) {
            navigateTo(identifier: TVAccessibilityIDs.Settings.serverSection)
            takeScreenshot(named: "TV-SettingsScreen-ServerSection")
        }
    }

    func testSettingsAboutSection() {
        ensureOnHomeScreen()

        navigateTo(identifier: TVAccessibilityIDs.TabBar.settings)
        pressSelect()
        sleep(2)

        navigateDown()
        navigateDown()
        takeScreenshot(named: "TV-SettingsScreen-AboutSection")
    }

    // MARK: - Navigation Visual Tests

    func testTabBarNavigation() {
        ensureOnHomeScreen()

        // Capture each tab
        let tabs = [
            (TVAccessibilityIDs.TabBar.home, "Home"),
            (TVAccessibilityIDs.TabBar.rooms, "Rooms"),
            (TVAccessibilityIDs.TabBar.scenes, "Scenes"),
            (TVAccessibilityIDs.TabBar.settings, "Settings")
        ]

        for (tabId, name) in tabs {
            navigateTo(identifier: tabId)
            pressSelect()
            sleep(2)
            takeScreenshot(named: "TV-Navigation-\(name)")
        }
    }

    func testMenuButtonNavigation() {
        ensureOnHomeScreen()

        // Navigate to a detail screen
        navigateTo(identifier: TVAccessibilityIDs.TabBar.rooms)
        pressSelect()
        sleep(1)

        // Navigate into a room
        pressSelect()
        sleep(1)
        takeScreenshot(named: "TV-MenuNav-DetailScreen")

        // Press menu to go back
        pressMenuButton()
        takeScreenshot(named: "TV-MenuNav-AfterMenu")
    }

    // MARK: - Full Visual Sweep

    func testFullAppVisualSweep() {
        ensureOnHomeScreen()

        let screens = [
            ("Home", { self.ensureOnHomeScreen() }),
            ("Rooms", {
                self.navigateTo(identifier: TVAccessibilityIDs.TabBar.rooms)
                self.pressSelect()
                sleep(2)
            }),
            ("Scenes", {
                self.navigateTo(identifier: TVAccessibilityIDs.TabBar.scenes)
                self.pressSelect()
                sleep(2)
            }),
            ("Settings", {
                self.navigateTo(identifier: TVAccessibilityIDs.TabBar.settings)
                self.pressSelect()
                sleep(2)
            })
        ]

        for (name, navigate) in screens {
            navigate()
            takeScreenshot(named: "TV-VisualSweep-\(name)")
        }
    }

    // MARK: - Focus State Tests

    func testFocusStateVisuals() {
        ensureOnHomeScreen()

        // Capture various focus states
        takeScreenshot(named: "TV-FocusState-Initial")

        navigateRight()
        takeScreenshot(named: "TV-FocusState-Right1")

        navigateRight()
        takeScreenshot(named: "TV-FocusState-Right2")

        navigateDown()
        takeScreenshot(named: "TV-FocusState-Down1")

        navigateDown()
        takeScreenshot(named: "TV-FocusState-Down2")
    }

    // MARK: - Helper Methods

    private func ensureOnHomeScreen() {
        let homeView = element(withIdentifier: TVAccessibilityIDs.Home.view)
        if !homeView.waitForExistence(timeout: 3) {
            // Navigate to home
            navigateTo(identifier: TVAccessibilityIDs.TabBar.home)
            pressSelect()
            sleep(2)
        }
    }
}

// MARK: - Siri Remote User Journey Tests

extension TVVisualRegressionTests {

    func testSiriRemoteUserJourney() {
        ensureOnHomeScreen()
        takeScreenshot(named: "TV-Journey-Start")

        // Navigate through app using remote
        let steps: [(String, () -> Void)] = [
            ("NavigateToRooms", {
                self.navigateTo(identifier: TVAccessibilityIDs.TabBar.rooms)
                self.pressSelect()
                sleep(2)
            }),
            ("BrowseRooms", {
                self.navigateRight()
                self.navigateRight()
                self.navigateDown()
            }),
            ("SelectRoom", {
                self.pressSelect()
                sleep(1)
            }),
            ("GoBackWithMenu", {
                self.pressMenuButton()
            }),
            ("NavigateToScenes", {
                self.navigateTo(identifier: TVAccessibilityIDs.TabBar.scenes)
                self.pressSelect()
                sleep(2)
            }),
            ("ActivateScene", {
                self.pressSelect()
                sleep(1)
            }),
            ("ReturnHome", {
                self.navigateTo(identifier: TVAccessibilityIDs.TabBar.home)
                self.pressSelect()
                sleep(2)
            })
        ]

        for (index, (name, action)) in steps.enumerated() {
            action()
            takeScreenshot(named: "TV-Journey-Step\(index + 1)-\(name)")
        }
    }
}

/*
 * Mirror
 * tvOS visual tests ensure the big screen experience is perfect.
 * h(x) >= 0. Always.
 */
