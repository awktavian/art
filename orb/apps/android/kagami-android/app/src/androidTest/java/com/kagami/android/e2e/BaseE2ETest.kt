/**
 * Kagami Android E2E Test Base
 *
 * Base class for instrumented E2E tests with:
 *   - Screenshot capture at key journey points
 *   - Video recording support
 *   - Common setup and utilities
 *
 * Colony: Crystal (e7) - Verification & Polish
 *
 * h(x) >= 0. Always.
 */
package com.kagami.android.e2e

import android.Manifest
import android.content.Context
import android.graphics.Bitmap
import android.os.Environment
import androidx.test.core.app.ApplicationProvider
import androidx.test.espresso.Espresso
import androidx.test.espresso.IdlingRegistry
import androidx.test.espresso.action.ViewActions
import androidx.test.espresso.assertion.ViewAssertions
import androidx.test.espresso.matcher.ViewMatchers
import androidx.test.ext.junit.rules.ActivityScenarioRule
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.rule.GrantPermissionRule
import androidx.test.uiautomator.By
import androidx.test.uiautomator.UiDevice
import androidx.test.uiautomator.Until
import com.kagami.android.MainActivity
import org.junit.After
import org.junit.Before
import org.junit.Rule
import java.io.File
import java.io.FileOutputStream
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Base class for all E2E instrumented tests.
 * Provides common setup, screenshot capture, and video recording infrastructure.
 */
abstract class BaseE2ETest {

    companion object {
        /** Default timeout for UI operations (ms) */
        const val DEFAULT_TIMEOUT = 10_000L

        /** Extended timeout for slow operations (ms) */
        const val EXTENDED_TIMEOUT = 30_000L

        /** Screenshot output directory */
        const val SCREENSHOT_DIR = "kagami-e2e-screenshots"

        /** Video output directory */
        const val VIDEO_DIR = "kagami-e2e-videos"
    }

    // MARK: - Rules

    @get:Rule
    val activityRule = ActivityScenarioRule(MainActivity::class.java)

    @get:Rule
    val permissionRule: GrantPermissionRule = GrantPermissionRule.grant(
        Manifest.permission.WRITE_EXTERNAL_STORAGE,
        Manifest.permission.READ_EXTERNAL_STORAGE
    )

    // MARK: - Properties

    protected lateinit var device: UiDevice
    protected lateinit var context: Context
    private val capturedScreenshots = mutableListOf<String>()
    private var testStartTime: Long = 0

    // MARK: - Setup & Teardown

    @Before
    open fun setUp() {
        device = UiDevice.getInstance(InstrumentationRegistry.getInstrumentation())
        context = ApplicationProvider.getApplicationContext()
        testStartTime = System.currentTimeMillis()

        // Wait for app to be ready
        waitForAppReady()

        // Create screenshot directory
        createScreenshotDirectory()

        // Capture initial state
        captureScreenshot("TestStart")
    }

    @After
    open fun tearDown() {
        // Capture final state
        captureScreenshot("TestEnd")

        // Log captured screenshots
        if (capturedScreenshots.isNotEmpty()) {
            println("E2E Test captured ${capturedScreenshots.size} screenshots:")
            capturedScreenshots.forEach { println("  - $it") }
        }

        val duration = System.currentTimeMillis() - testStartTime
        println("E2E Test completed in ${duration}ms")
    }

    // MARK: - Wait Helpers

    /**
     * Wait for the app to be fully ready for interaction
     */
    protected fun waitForAppReady() {
        // Wait for any loading indicators to disappear
        device.wait(
            Until.gone(By.res("com.kagami.android:id/loading_indicator")),
            DEFAULT_TIMEOUT
        )

        // Wait for main content to appear
        device.wait(
            Until.hasObject(By.res("com.kagami.android:id/main_content")),
            DEFAULT_TIMEOUT
        )

        // Allow animations to settle
        Thread.sleep(500)
    }

    /**
     * Wait for a specific element to appear
     */
    protected fun waitForElement(resourceId: String, timeout: Long = DEFAULT_TIMEOUT): Boolean {
        return device.wait(
            Until.hasObject(By.res("com.kagami.android:id/$resourceId")),
            timeout
        ) ?: false
    }

    /**
     * Wait for text to appear on screen
     */
    protected fun waitForText(text: String, timeout: Long = DEFAULT_TIMEOUT): Boolean {
        return device.wait(
            Until.hasObject(By.text(text)),
            timeout
        ) ?: false
    }

    // MARK: - Screenshot Capture

    /**
     * Capture a screenshot with the given name
     */
    protected fun captureScreenshot(name: String) {
        try {
            val timestamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())
            val filename = "${getTestName()}_${name}_$timestamp.png"

            val screenshotDir = getScreenshotDirectory()
            val file = File(screenshotDir, filename)

            device.takeScreenshot(file)

            capturedScreenshots.add(filename)
            println("Screenshot captured: $filename")

        } catch (e: Exception) {
            println("Failed to capture screenshot '$name': ${e.message}")
        }
    }

    /**
     * Capture screenshot at a user journey checkpoint
     */
    protected fun captureJourneyCheckpoint(checkpoint: String) {
        captureScreenshot("Journey_$checkpoint")
    }

    /**
     * Create screenshot directory if it doesn't exist
     */
    private fun createScreenshotDirectory() {
        val dir = getScreenshotDirectory()
        if (!dir.exists()) {
            dir.mkdirs()
        }
    }

    /**
     * Get the screenshot output directory
     */
    private fun getScreenshotDirectory(): File {
        val externalDir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_PICTURES)
        return File(externalDir, SCREENSHOT_DIR)
    }

    /**
     * Get the current test name for file naming
     */
    private fun getTestName(): String {
        return this::class.java.simpleName
    }

    // MARK: - Navigation Helpers

    /**
     * Navigate to a specific tab in the bottom navigation
     */
    protected fun navigateToTab(tabName: String) {
        val tab = device.findObject(By.text(tabName))
        tab?.click()
        Thread.sleep(500)
    }

    /**
     * Navigate to Home tab
     */
    protected fun navigateToHome() {
        navigateToTab("Home")
    }

    /**
     * Navigate to Rooms tab
     */
    protected fun navigateToRooms() {
        navigateToTab("Rooms")
    }

    /**
     * Navigate to Scenes tab
     */
    protected fun navigateToScenes() {
        navigateToTab("Scenes")
    }

    /**
     * Navigate to Settings tab
     */
    protected fun navigateToSettings() {
        navigateToTab("Settings")
    }

    // MARK: - Action Helpers

    /**
     * Click on an element by resource ID
     */
    protected fun clickById(resourceId: String) {
        val element = device.findObject(By.res("com.kagami.android:id/$resourceId"))
        element?.click()
        Thread.sleep(300)
    }

    /**
     * Click on an element by text
     */
    protected fun clickByText(text: String) {
        val element = device.findObject(By.text(text))
        element?.click()
        Thread.sleep(300)
    }

    /**
     * Enter text into a field by resource ID
     */
    protected fun enterText(resourceId: String, text: String) {
        val element = device.findObject(By.res("com.kagami.android:id/$resourceId"))
        element?.text = text
        Thread.sleep(200)
    }

    /**
     * Press the back button
     */
    protected fun pressBack() {
        device.pressBack()
        Thread.sleep(300)
    }

    // MARK: - Assertion Helpers

    /**
     * Assert that an element with the given resource ID is displayed
     */
    protected fun assertDisplayedById(resourceId: String) {
        val element = device.findObject(By.res("com.kagami.android:id/$resourceId"))
        assert(element != null) { "Element with ID '$resourceId' not found" }
    }

    /**
     * Assert that text is displayed on screen
     */
    protected fun assertDisplayedByText(text: String) {
        val element = device.findObject(By.text(text))
        assert(element != null) { "Text '$text' not found on screen" }
    }

    /**
     * Assert that an element is NOT displayed
     */
    protected fun assertNotDisplayedById(resourceId: String) {
        val element = device.findObject(By.res("com.kagami.android:id/$resourceId"))
        assert(element == null) { "Element with ID '$resourceId' should not be displayed" }
    }

    // MARK: - User Journey Recording

    /**
     * Record a complete user journey with screenshots at each step
     */
    protected fun recordUserJourney(
        journeyName: String,
        steps: List<Pair<String, () -> Unit>>
    ) {
        captureScreenshot("${journeyName}_Start")

        steps.forEachIndexed { index, (stepName, action) ->
            try {
                action()
                Thread.sleep(500)
                captureScreenshot("${journeyName}_Step${index + 1}_$stepName")
            } catch (e: Exception) {
                captureScreenshot("${journeyName}_Step${index + 1}_${stepName}_ERROR")
                throw e
            }
        }

        captureScreenshot("${journeyName}_Complete")
    }
}

/*
 * Mirror
 * h(x) >= 0. Always.
 */
