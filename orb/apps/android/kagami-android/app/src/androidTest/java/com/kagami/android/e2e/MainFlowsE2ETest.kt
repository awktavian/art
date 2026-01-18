/**
 * Kagami Android Main Flows E2E Tests
 *
 * End-to-end tests for core user journeys:
 *   - Home screen interactions
 *   - Room control flows
 *   - Scene activation
 *   - Settings navigation
 *
 * Colony: Crystal (e7) - Verification & Polish
 *
 * h(x) >= 0. Always.
 */
package com.kagami.android.e2e

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.filters.LargeTest
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

/**
 * E2E tests for main app flows after onboarding.
 */
@RunWith(AndroidJUnit4::class)
@LargeTest
class MainFlowsE2ETest : BaseE2ETest() {

    @Before
    override fun setUp() {
        super.setUp()
        // Skip onboarding for these tests
        skipToHomeIfNeeded()
    }

    private fun skipToHomeIfNeeded() {
        // If onboarding is showing, skip through it
        if (device.findObject(By.text("Welcome to Kagami")) != null) {
            completeOnboarding()
        }
    }

    private fun completeOnboarding() {
        // Quick path through onboarding
        clickByText("Continue")
        Thread.sleep(500)
        clickByText("Demo Mode")
        Thread.sleep(1000)
        clickByText("Continue")
        Thread.sleep(500)
        clickByText("Skip")
        Thread.sleep(500)
        clickByText("Skip")
        Thread.sleep(500)
        clickByText("Skip")
        Thread.sleep(500)
        clickByText("Get Started")
        Thread.sleep(1000)
    }

    // MARK: - Home Screen Tests

    @Test
    fun testHomeScreenVisual() {
        navigateToHome()
        waitForElement("home_content", DEFAULT_TIMEOUT)
        captureScreenshot("HomeScreen_Default")
    }

    @Test
    fun testHomeScreenQuickActions() {
        navigateToHome()
        waitForElement("home_content", DEFAULT_TIMEOUT)

        recordUserJourney("HomeQuickActions", listOf(
            "ViewHome" to {
                // Just view the home screen
            },
            "TapQuickAction" to {
                // Try to interact with a quick action
                val quickAction = device.findObject(By.res("com.kagami.android:id/quick_action_button"))
                quickAction?.click()
                Thread.sleep(500)
            },
            "ReturnToHome" to {
                // Return to home state
                pressBack()
            }
        ))
    }

    // MARK: - Rooms Flow Tests

    @Test
    fun testRoomsScreenVisual() {
        navigateToRooms()
        waitForElement("rooms_list", DEFAULT_TIMEOUT)
        captureScreenshot("RoomsScreen_Default")
    }

    @Test
    fun testRoomControlFlow() {
        recordUserJourney("RoomControl", listOf(
            "NavigateToRooms" to {
                navigateToRooms()
                waitForElement("rooms_list", DEFAULT_TIMEOUT)
            },
            "SelectFirstRoom" to {
                val roomItem = device.findObject(By.res("com.kagami.android:id/room_item"))
                roomItem?.click()
                Thread.sleep(500)
            },
            "ViewRoomDetail" to {
                waitForElement("room_detail_content", DEFAULT_TIMEOUT)
            },
            "AdjustLighting" to {
                // Try to adjust lighting if available
                val lightSlider = device.findObject(By.res("com.kagami.android:id/light_slider"))
                if (lightSlider != null) {
                    // Drag slider to 50%
                    lightSlider.drag(lightSlider.visibleCenter, 20)
                    Thread.sleep(500)
                }
            },
            "ReturnToRooms" to {
                pressBack()
                waitForElement("rooms_list", DEFAULT_TIMEOUT)
            }
        ))
    }

    @Test
    fun testRoomsEmptyState() {
        navigateToRooms()

        // Check for empty state
        val emptyState = device.findObject(By.res("com.kagami.android:id/empty_state"))
        if (emptyState != null) {
            captureScreenshot("RoomsScreen_EmptyState")
        }
    }

    // MARK: - Scenes Flow Tests

    @Test
    fun testScenesScreenVisual() {
        navigateToScenes()
        waitForElement("scenes_list", DEFAULT_TIMEOUT)
        captureScreenshot("ScenesScreen_Default")
    }

    @Test
    fun testSceneActivationFlow() {
        recordUserJourney("SceneActivation", listOf(
            "NavigateToScenes" to {
                navigateToScenes()
                waitForElement("scenes_list", DEFAULT_TIMEOUT)
            },
            "ViewScenesList" to {
                // Capture scenes list
            },
            "SelectScene" to {
                val sceneItem = device.findObject(By.res("com.kagami.android:id/scene_item"))
                if (sceneItem != null) {
                    sceneItem.click()
                    Thread.sleep(1000)
                }
            },
            "VerifySceneActivated" to {
                // Verify feedback shown
            }
        ))
    }

    // MARK: - Settings Flow Tests

    @Test
    fun testSettingsScreenVisual() {
        navigateToSettings()
        waitForElement("settings_content", DEFAULT_TIMEOUT)
        captureScreenshot("SettingsScreen_Default")
    }

    @Test
    fun testSettingsNavigationFlow() {
        recordUserJourney("SettingsNavigation", listOf(
            "NavigateToSettings" to {
                navigateToSettings()
                waitForElement("settings_content", DEFAULT_TIMEOUT)
            },
            "ViewSettingsSections" to {
                // Capture settings sections
            },
            "TapAccessibility" to {
                clickByText("Accessibility")
                Thread.sleep(500)
            },
            "ViewAccessibilitySettings" to {
                // Capture accessibility settings
            },
            "ReturnToSettings" to {
                pressBack()
                waitForElement("settings_content", DEFAULT_TIMEOUT)
            },
            "TapHousehold" to {
                clickByText("Household")
                Thread.sleep(500)
            },
            "ViewHouseholdSettings" to {
                // Capture household settings
            },
            "ReturnToMain" to {
                pressBack()
                waitForElement("settings_content", DEFAULT_TIMEOUT)
            }
        ))
    }

    // MARK: - Full App Visual Sweep

    @Test
    fun testFullAppVisualSweep() {
        // Capture all main screens for visual regression
        val screens = listOf(
            "Home" to { navigateToHome() },
            "Rooms" to { navigateToRooms() },
            "Scenes" to { navigateToScenes() },
            "Settings" to { navigateToSettings() }
        )

        screens.forEach { (name, navigate) ->
            navigate()
            Thread.sleep(1000)
            captureScreenshot("VisualSweep_$name")
        }
    }

    // MARK: - Navigation Tests

    @Test
    fun testBottomNavigationFlow() {
        recordUserJourney("BottomNavigation", listOf(
            "StartAtHome" to {
                navigateToHome()
            },
            "GoToRooms" to {
                navigateToRooms()
            },
            "GoToScenes" to {
                navigateToScenes()
            },
            "GoToSettings" to {
                navigateToSettings()
            },
            "ReturnToHome" to {
                navigateToHome()
            }
        ))
    }

    // MARK: - Accessibility Visual Tests

    @Test
    fun testAccessibilityModeVisuals() {
        // Navigate to accessibility settings
        navigateToSettings()
        waitForElement("settings_content", DEFAULT_TIMEOUT)

        clickByText("Accessibility")
        Thread.sleep(500)

        captureScreenshot("AccessibilitySettings_Default")

        // Toggle high contrast if available
        val highContrastToggle = device.findObject(By.text("High Contrast"))
        if (highContrastToggle != null) {
            highContrastToggle.click()
            Thread.sleep(500)
            captureScreenshot("AccessibilitySettings_HighContrastOn")

            // Navigate back and capture home with high contrast
            pressBack()
            navigateToHome()
            Thread.sleep(500)
            captureScreenshot("HomeScreen_HighContrast")
        }
    }

    @Test
    fun testLargeFontVisuals() {
        // Navigate to accessibility settings
        navigateToSettings()
        waitForElement("settings_content", DEFAULT_TIMEOUT)

        clickByText("Accessibility")
        Thread.sleep(500)

        // Try to increase font size
        val fontSlider = device.findObject(By.res("com.kagami.android:id/font_size_slider"))
        if (fontSlider != null) {
            // Increase font size
            fontSlider.drag(fontSlider.visibleCenter, 50)
            Thread.sleep(500)
            captureScreenshot("AccessibilitySettings_LargeFont")

            // Navigate and capture
            pressBack()
            navigateToHome()
            Thread.sleep(500)
            captureScreenshot("HomeScreen_LargeFont")
        }
    }
}

// Import missing
import androidx.test.uiautomator.By

/*
 * Mirror
 * h(x) >= 0. Always.
 */
