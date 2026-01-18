/**
 * Kagami Android Screenshot Test Base
 *
 * Base class for Roborazzi screenshot tests.
 * Provides common setup and utilities for visual regression testing.
 *
 * h(x) >= 0. Always.
 */
package com.kagami.android.ui.screens

import androidx.compose.runtime.Composable
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onRoot
import com.github.takahirom.roborazzi.captureRoboImage
import com.github.takahirom.roborazzi.RobolectricDeviceQualifiers
import com.github.takahirom.roborazzi.RoborazziOptions
import com.github.takahirom.roborazzi.RoborazziRule
import com.kagami.android.ui.AccessibilityConfig
import com.kagami.android.ui.LocalAccessibilityConfig
import com.kagami.android.ui.theme.KagamiTheme
import org.junit.Rule
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/**
 * Base class for screenshot tests using Roborazzi.
 * Provides common setup for capturing Compose UI screenshots.
 */
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34], qualifiers = RobolectricDeviceQualifiers.Pixel7)
abstract class ScreenshotTestBase {

    companion object {
        /** Snapshot output directory (relative to module root) */
        const val SNAPSHOT_DIR = "src/test/snapshots"

        /** Pixel difference threshold for anti-aliasing tolerance (0.5%) */
        const val PIXEL_DIFF_THRESHOLD = 0.005
    }

    @get:Rule
    val composeTestRule = createComposeRule()

    @get:Rule
    val roborazziRule = RoborazziRule(
        options = RoborazziRule.Options(
            outputDirectoryPath = SNAPSHOT_DIR,
            roborazziOptions = RoborazziOptions(
                recordOptions = RoborazziOptions.RecordOptions(
                    resizeScale = 0.5,
                    applyDeviceCrop = true
                ),
                compareOptions = RoborazziOptions.CompareOptions(
                    resultValidator = { result ->
                        // Allow small pixel difference for anti-aliasing variations
                        result.pixelDifference < PIXEL_DIFF_THRESHOLD
                    }
                )
            )
        )
    )

    /**
     * Default accessibility config for tests.
     */
    protected val defaultAccessibilityConfig = AccessibilityConfig(
        fontScale = 1.0f,
        isReducedMotionEnabled = true, // Disable animations in screenshots
        isHighContrastEnabled = false
    )

    /**
     * High contrast accessibility config for accessibility testing.
     */
    protected val highContrastAccessibilityConfig = AccessibilityConfig(
        fontScale = 1.0f,
        isReducedMotionEnabled = true,
        isHighContrastEnabled = true
    )

    /**
     * Large font accessibility config for accessibility testing.
     */
    protected val largeFontAccessibilityConfig = AccessibilityConfig(
        fontScale = 2.0f,
        isReducedMotionEnabled = true,
        isHighContrastEnabled = false
    )

    /**
     * Capture a screenshot of the given composable content.
     */
    protected fun captureScreen(
        testName: String,
        content: @Composable () -> Unit
    ) {
        composeTestRule.setContent {
            KagamiTheme {
                androidx.compose.runtime.CompositionLocalProvider(
                    LocalAccessibilityConfig provides defaultAccessibilityConfig
                ) {
                    content()
                }
            }
        }
        composeTestRule.onRoot().captureRoboImage(
            filePath = "$SNAPSHOT_DIR/${testName}.png"
        )
    }

    /**
     * Capture a screenshot with custom accessibility config.
     */
    protected fun captureScreenWithAccessibility(
        testName: String,
        accessibilityConfig: AccessibilityConfig,
        content: @Composable () -> Unit
    ) {
        composeTestRule.setContent {
            KagamiTheme {
                androidx.compose.runtime.CompositionLocalProvider(
                    LocalAccessibilityConfig provides accessibilityConfig
                ) {
                    content()
                }
            }
        }
        composeTestRule.onRoot().captureRoboImage(
            filePath = "$SNAPSHOT_DIR/${testName}.png"
        )
    }
}

/*
 * Mirror
 * h(x) >= 0. Always.
 */
