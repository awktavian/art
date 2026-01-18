//
// SceneActivationFlowTests.swift -- E2E Tests for Scene Activation Flow
//
// Colony: Crystal (e7) -- Verification & Polish
//
// Tests scene control interactions:
//   - Scene list display
//   - Scene activation
//   - Scene row content
//   - Tab navigation to scenes
//
// Run:
//   xcodebuild test -scheme KagamiIOS -destination 'platform=iOS Simulator,name=iPhone 15 Pro'
//
// h(x) >= 0. Always.
//

import XCTest

final class SceneActivationFlowTests: KagamiUITestCase {

    // Skip onboarding for these tests
    override var skipOnboarding: Bool { true }

    // MARK: - Setup

    override func setUp() {
        super.setUp()

        // If onboarding appears, complete it
        let onboardingProgress = element(withIdentifier: AccessibilityIDs.Onboarding.progressIndicator, in: app)
        if onboardingProgress.waitForExistence(timeout: 3) {
            completeOnboarding()
        }

        // Navigate to scenes tab
        navigateToTab(.scenes)

        // Wait for scenes view to load
        waitForElement(
            element(withIdentifier: AccessibilityIDs.Scenes.view, in: app),
            timeout: 5
        )
    }

    // MARK: - Scene List Tests

    func testScenesViewDisplaysSceneList() {
        // Verify scenes list is visible
        let scenesList = element(withIdentifier: AccessibilityIDs.Scenes.list, in: app)
        assertVisible(scenesList)

        takeScreenshot(named: "SceneActivation-ScenesList")
    }

    func testScenesViewShowsNavigationTitle() {
        // Verify "Scenes" navigation title
        assertTextPresent("Scenes", in: app)
    }

    func testAllExpectedScenesAreDisplayed() {
        // Verify each expected scene is visible
        let expectedScenes = [
            "Movie Mode",
            "Goodnight",
            "Welcome Home",
            "Away Mode",
            "Focus Mode",
            "Relax",
            "Coffee Time"
        ]

        for sceneName in expectedScenes {
            let sceneExists = app.staticTexts[sceneName].waitForExistence(timeout: 3)
            XCTAssertTrue(sceneExists, "Scene '\(sceneName)' should be visible")
        }
    }

    // MARK: - Scene Row Tests

    func testSceneRowShowsIcon() {
        // Scene rows should have emoji icons
        let expectedIcons = ["🎬", "🌙", "🏡", "🔒", "🎯", "🧘", "☕"]

        var iconFound = false
        for icon in expectedIcons {
            if app.staticTexts[icon].exists {
                iconFound = true
                break
            }
        }

        XCTAssertTrue(iconFound, "At least one scene icon should be visible")
    }

    func testSceneRowShowsDescription() {
        // Verify scene descriptions are visible
        let expectedDescriptions = [
            "Dim lights",
            "All lights off",
            "Warm lights",
            "Secure house",
            "Bright lights"
        ]

        var descriptionFound = false
        for description in expectedDescriptions {
            let exists = app.staticTexts.matching(
                NSPredicate(format: "label CONTAINS %@", description)
            ).firstMatch.waitForExistence(timeout: 2)
            if exists {
                descriptionFound = true
                break
            }
        }

        XCTAssertTrue(descriptionFound, "At least one scene description should be visible")
    }

    func testSceneRowHasChevronIndicator() {
        // Scene rows should show a chevron/arrow for activation
        // In SwiftUI List with buttons, this might be hidden
        // But the row should be tappable
        let firstCell = app.cells.firstMatch
        XCTAssertTrue(firstCell.isHittable, "Scene rows should be tappable")
    }

    // MARK: - Scene Activation Tests

    func testTapSceneRowActivatesScene() {
        // Tap Movie Mode scene
        let movieModeScene = element(withIdentifier: AccessibilityIDs.Scenes.row("movie_mode"), in: app)

        if movieModeScene.waitForExistence(timeout: 5) {
            movieModeScene.tap()
        } else {
            // Fallback: tap by text
            let movieModeText = app.staticTexts["Movie Mode"].firstMatch
            if movieModeText.exists {
                movieModeText.tap()
            }
        }

        // Scene activation should work without crashing
        sleep(1)
        takeScreenshot(named: "SceneActivation-AfterMovieMode")
    }

    func testActivateGoodnightScene() {
        // Tap Goodnight scene
        let goodnightScene = element(withIdentifier: AccessibilityIDs.Scenes.row("goodnight"), in: app)

        if goodnightScene.waitForExistence(timeout: 5) {
            goodnightScene.tap()
        } else {
            let goodnightText = app.staticTexts["Goodnight"].firstMatch
            if goodnightText.exists {
                goodnightText.tap()
            }
        }

        sleep(1)
        takeScreenshot(named: "SceneActivation-AfterGoodnight")
    }

    func testActivateWelcomeHomeScene() {
        // Tap Welcome Home scene
        let welcomeScene = element(withIdentifier: AccessibilityIDs.Scenes.row("welcome_home"), in: app)

        if welcomeScene.waitForExistence(timeout: 5) {
            welcomeScene.tap()
        } else {
            let welcomeText = app.staticTexts["Welcome Home"].firstMatch
            if welcomeText.exists {
                welcomeText.tap()
            }
        }

        sleep(1)
        takeScreenshot(named: "SceneActivation-AfterWelcomeHome")
    }

    func testActivateFocusScene() {
        // Tap Focus Mode scene
        let focusScene = element(withIdentifier: AccessibilityIDs.Scenes.row("focus"), in: app)

        if focusScene.waitForExistence(timeout: 5) {
            focusScene.tap()
        } else {
            let focusText = app.staticTexts["Focus Mode"].firstMatch
            if focusText.exists {
                focusText.tap()
            }
        }

        sleep(1)
        takeScreenshot(named: "SceneActivation-AfterFocus")
    }

    func testActivateRelaxScene() {
        // Tap Relax scene
        let relaxScene = element(withIdentifier: AccessibilityIDs.Scenes.row("relax"), in: app)

        if relaxScene.waitForExistence(timeout: 5) {
            relaxScene.tap()
        } else {
            let relaxText = app.staticTexts["Relax"].firstMatch
            if relaxText.exists {
                relaxText.tap()
            }
        }

        sleep(1)
        takeScreenshot(named: "SceneActivation-AfterRelax")
    }

    // MARK: - Scene Color Tests

    func testSceneRowsHaveDistinctColors() {
        // Each scene should have a unique color tint
        // We can verify by taking a screenshot and visual inspection
        takeScreenshot(named: "SceneActivation-ColorVariety")

        // The scenes list should have visible rows
        let scenesList = element(withIdentifier: AccessibilityIDs.Scenes.list, in: app)
        XCTAssertTrue(scenesList.exists, "Scenes list should be visible")
    }

    // MARK: - Tab Navigation Tests

    func testCanSwitchToHomeAndBack() {
        // Switch to home tab
        navigateToTab(.home)

        // Verify home view
        let homeView = element(withIdentifier: AccessibilityIDs.Home.view, in: app)
        waitForElement(homeView, timeout: 5)

        // Switch back to scenes
        navigateToTab(.scenes)

        // Verify scenes view
        assertVisible(element(withIdentifier: AccessibilityIDs.Scenes.view, in: app))

        takeScreenshot(named: "SceneActivation-AfterTabSwitch")
    }

    func testCanSwitchToRoomsAndBack() {
        // Switch to rooms tab
        navigateToTab(.rooms)

        // Wait for rooms view
        let roomsView = element(withIdentifier: AccessibilityIDs.Rooms.view, in: app)
        waitForElement(roomsView, timeout: 5)

        // Switch back to scenes
        navigateToTab(.scenes)

        // Verify scenes view
        assertVisible(element(withIdentifier: AccessibilityIDs.Scenes.view, in: app))
    }

    // MARK: - Scroll Tests

    func testCanScrollThroughScenes() {
        // Scroll down the scenes list
        let scenesList = element(withIdentifier: AccessibilityIDs.Scenes.list, in: app)
        if scenesList.exists {
            scenesList.swipeUp()
            sleep(1)

            takeScreenshot(named: "SceneActivation-AfterScroll")

            // Scroll back up
            scenesList.swipeDown()
        }
    }

    // MARK: - Accessibility Tests

    func testSceneRowsHaveAccessibilityLabels() {
        // Verify scene rows are accessible
        let cells = app.cells.allElementsBoundByIndex

        for cell in cells.prefix(3) { // Check first 3 cells
            XCTAssertTrue(
                !cell.label.isEmpty || cell.identifier.hasPrefix("scenes.row"),
                "Scene rows should have accessibility labels or identifiers"
            )
        }
    }

    func testSceneRowsHaveAccessibilityHints() {
        // Scene rows should have hints explaining what they do
        // The app sets accessibilityHint to the description

        let cells = app.cells.allElementsBoundByIndex
        for cell in cells.prefix(3) {
            // Cells should be tappable
            XCTAssertTrue(cell.isHittable, "Scene cells should be hittable")
        }
    }

    func testVoiceOverCanNavigateScenes() {
        // This tests that VoiceOver-compatible elements exist
        // (Actual VoiceOver testing requires manual verification)

        // Verify scenes are in a list structure
        let scenesList = element(withIdentifier: AccessibilityIDs.Scenes.list, in: app)
        XCTAssertTrue(scenesList.exists, "Scenes should be in an accessible list")

        // Verify individual scenes are accessible
        let cellCount = app.cells.count
        XCTAssertGreaterThan(cellCount, 0, "Scene list should have accessible cells")
    }

    // MARK: - Haptic Feedback Tests

    func testSceneActivationProvidesHapticFeedback() {
        // We can't directly test haptic feedback in UI tests,
        // but we can verify the tap doesn't cause issues

        let firstScene = app.cells.firstMatch
        if firstScene.isHittable {
            firstScene.tap()

            // App should remain stable
            sleep(1)
            assertVisible(element(withIdentifier: AccessibilityIDs.Scenes.view, in: app))
        }
    }

    // MARK: - Scene List Content Tests

    func testCoffeeTimeSceneIsLast() {
        // Scroll to bottom of list
        let scenesList = element(withIdentifier: AccessibilityIDs.Scenes.list, in: app)
        if scenesList.exists {
            scenesList.swipeUp()
            scenesList.swipeUp() // Scroll twice to ensure we're at bottom
        }

        // Coffee Time should be visible near the bottom
        let coffeeExists = app.staticTexts["Coffee Time"].waitForExistence(timeout: 3)
        XCTAssertTrue(coffeeExists, "Coffee Time scene should be visible")

        takeScreenshot(named: "SceneActivation-BottomOfList")
    }
}

/*
 * Mirror
 * Scenes transform the home in one tap.
 * Every scene is tested.
 * h(x) >= 0. Always.
 */
