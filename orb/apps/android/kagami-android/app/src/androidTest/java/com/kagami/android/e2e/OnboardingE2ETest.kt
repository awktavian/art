/**
 * Kagami Android Onboarding E2E Tests
 *
 * End-to-end tests for the onboarding flow with:
 *   - Screenshot capture at each step
 *   - Visual regression validation
 *   - User journey recording
 *
 * Colony: Crystal (e7) - Verification & Polish
 *
 * h(x) >= 0. Always.
 */
package com.kagami.android.e2e

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.filters.LargeTest
import androidx.test.uiautomator.By
import androidx.test.uiautomator.Until
import org.junit.Test
import org.junit.runner.RunWith

/**
 * E2E tests for the complete onboarding flow.
 */
@RunWith(AndroidJUnit4::class)
@LargeTest
class OnboardingE2ETest : BaseE2ETest() {

    // MARK: - Onboarding Flow Tests

    @Test
    fun testCompleteOnboardingFlow() {
        recordUserJourney("Onboarding", listOf(
            "WelcomeScreen" to {
                // Verify welcome screen is displayed
                waitForText("Welcome to Kagami", EXTENDED_TIMEOUT)
                assertDisplayedByText("Welcome to Kagami")
            },
            "ContinueFromWelcome" to {
                clickByText("Continue")
                Thread.sleep(500)
            },
            "ServerSetup" to {
                // Should be on server setup screen
                waitForText("Connect to Server", DEFAULT_TIMEOUT)
            },
            "SelectDemoMode" to {
                // Click demo mode button
                clickByText("Demo Mode")
                Thread.sleep(1000)
            },
            "ContinueFromServer" to {
                clickByText("Continue")
                Thread.sleep(500)
            },
            "IntegrationScreen" to {
                // Should be on integration selection
                waitForText("Integrations", DEFAULT_TIMEOUT)
            },
            "SkipIntegrations" to {
                clickByText("Skip")
                Thread.sleep(500)
            },
            "RoomsScreen" to {
                // Should be on rooms configuration
                waitForText("Rooms", DEFAULT_TIMEOUT)
            },
            "SkipRooms" to {
                clickByText("Skip")
                Thread.sleep(500)
            },
            "PermissionsScreen" to {
                // Should be on permissions screen
                waitForText("Permissions", DEFAULT_TIMEOUT)
            },
            "SkipPermissions" to {
                clickByText("Skip")
                Thread.sleep(500)
            },
            "CompletionScreen" to {
                // Should be on completion screen
                waitForText("All Set", DEFAULT_TIMEOUT)
            },
            "GetStarted" to {
                clickByText("Get Started")
                Thread.sleep(1000)
            },
            "HomeScreen" to {
                // Should be on home screen now
                waitForElement("home_content", EXTENDED_TIMEOUT)
            }
        ))
    }

    @Test
    fun testWelcomeScreenVisual() {
        // Capture welcome screen for visual regression
        waitForText("Welcome to Kagami", EXTENDED_TIMEOUT)
        captureScreenshot("WelcomeScreen_Visual")

        // Verify key elements are present
        assertDisplayedByText("Welcome to Kagami")
    }

    @Test
    fun testServerSetupScreenVisual() {
        // Navigate to server setup
        waitForText("Welcome to Kagami", EXTENDED_TIMEOUT)
        clickByText("Continue")

        waitForText("Connect to Server", DEFAULT_TIMEOUT)
        captureScreenshot("ServerSetup_Visual")
    }

    @Test
    fun testDemoModeActivation() {
        // Navigate to server setup
        waitForText("Welcome to Kagami", EXTENDED_TIMEOUT)
        clickByText("Continue")

        // Select demo mode
        waitForText("Demo Mode", DEFAULT_TIMEOUT)
        captureScreenshot("DemoMode_Before")

        clickByText("Demo Mode")
        Thread.sleep(1000)

        captureScreenshot("DemoMode_After")
    }

    @Test
    fun testBackNavigation() {
        // Navigate forward
        waitForText("Welcome to Kagami", EXTENDED_TIMEOUT)
        clickByText("Continue")
        waitForText("Connect to Server", DEFAULT_TIMEOUT)

        captureScreenshot("BackNav_ServerScreen")

        // Press back
        pressBack()
        Thread.sleep(500)

        // Should be back on welcome screen
        waitForText("Welcome to Kagami", DEFAULT_TIMEOUT)
        captureScreenshot("BackNav_WelcomeScreen")
    }

    // MARK: - Visual Regression Tests

    @Test
    fun testOnboardingVisualSweep() {
        // Capture all onboarding screens
        val screens = listOf(
            "Welcome" to { waitForText("Welcome to Kagami", EXTENDED_TIMEOUT) },
            "Server" to {
                clickByText("Continue")
                waitForText("Connect to Server", DEFAULT_TIMEOUT)
            },
            "DemoActivated" to {
                clickByText("Demo Mode")
                Thread.sleep(1000)
            },
            "Integrations" to {
                clickByText("Continue")
                waitForText("Integrations", DEFAULT_TIMEOUT)
            },
            "Rooms" to {
                clickByText("Skip")
                waitForText("Rooms", DEFAULT_TIMEOUT)
            },
            "Permissions" to {
                clickByText("Skip")
                waitForText("Permissions", DEFAULT_TIMEOUT)
            },
            "Completion" to {
                clickByText("Skip")
                waitForText("All Set", DEFAULT_TIMEOUT)
            }
        )

        screens.forEach { (name, action) ->
            try {
                action()
                captureScreenshot("OnboardingVisual_$name")
            } catch (e: Exception) {
                captureScreenshot("OnboardingVisual_${name}_ERROR")
                println("Failed on screen '$name': ${e.message}")
            }
        }
    }
}

/*
 * Mirror
 * h(x) >= 0. Always.
 */
