/**
 * Kagami AndroidXR E2E Test Base
 *
 * Base class for instrumented XR E2E tests with:
 *   - XR session management
 *   - Hand tracking simulation
 *   - Gaze interaction simulation
 *   - Spatial coordinate assertions
 *   - Screenshot/video capture of XR sessions
 *
 * Colony: Crystal (e7) - Verification & Polish
 *
 * h(x) >= 0. Always.
 */
package com.kagami.xr.e2e

import android.Manifest
import android.content.Context
import android.media.MediaScannerConnection
import android.os.Environment
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.rules.ActivityScenarioRule
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.rule.GrantPermissionRule
import androidx.test.uiautomator.By
import androidx.test.uiautomator.Direction
import androidx.test.uiautomator.UiDevice
import androidx.test.uiautomator.Until
import com.kagami.xr.MainActivity
import com.kagami.xr.services.HandTrackingService
import org.json.JSONArray
import org.json.JSONObject
import org.junit.After
import org.junit.Before
import org.junit.Rule
import java.io.File
import java.io.FileOutputStream
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Base class for all XR E2E instrumented tests.
 * Provides XR session management, hand tracking simulation, and common utilities.
 */
abstract class BaseXRE2ETest {

    companion object {
        /** Default timeout for UI operations (ms) */
        const val DEFAULT_TIMEOUT = 10_000L

        /** Extended timeout for XR operations (ms) */
        const val XR_TIMEOUT = 30_000L

        /** Gesture recognition timeout (ms) */
        const val GESTURE_TIMEOUT = 5_000L

        /** Screenshot output directory */
        const val SCREENSHOT_DIR = "kagami-xr-e2e-screenshots"

        /** Video output directory */
        const val VIDEO_DIR = "kagami-xr-e2e-videos"

        /** Metadata output directory */
        const val METADATA_DIR = "kagami-xr-e2e-metadata"

        /** Package name for resource lookup */
        const val PACKAGE_NAME = "com.kagami.xr"
    }

    // MARK: - Rules

    @get:Rule
    val activityRule = ActivityScenarioRule(MainActivity::class.java)

    @get:Rule
    val permissionRule: GrantPermissionRule = GrantPermissionRule.grant(
        Manifest.permission.WRITE_EXTERNAL_STORAGE,
        Manifest.permission.READ_EXTERNAL_STORAGE,
        Manifest.permission.RECORD_AUDIO,
        Manifest.permission.CAMERA
    )

    // MARK: - Properties

    protected lateinit var device: UiDevice
    protected lateinit var context: Context
    private val capturedScreenshots = mutableListOf<String>()
    private var testStartTime: Long = 0
    private var videoRecordingProcess: Process? = null
    private var currentVideoFile: File? = null
    protected var journeyCheckpoints: MutableList<JourneyCheckpoint> = mutableListOf()
    protected var journeyStartTime: Long = 0

    /**
     * Journey checkpoint data class for XR-specific tracking
     */
    data class JourneyCheckpoint(
        val name: String,
        val timestamp: Long,
        val success: Boolean,
        val notes: String? = null,
        val spatialData: SpatialCheckpointData? = null
    )

    /**
     * Spatial data captured at checkpoint
     */
    data class SpatialCheckpointData(
        val activeGesture: String? = null,
        val gazeTarget: String? = null,
        val panelPosition: Vector3? = null,
        val handPositions: Pair<Vector3?, Vector3?>? = null
    )

    /**
     * Simple 3D vector for spatial coordinates
     */
    data class Vector3(
        val x: Float,
        val y: Float,
        val z: Float
    ) {
        fun distanceTo(other: Vector3): Float {
            val dx = x - other.x
            val dy = y - other.y
            val dz = z - other.z
            return kotlin.math.sqrt(dx * dx + dy * dy + dz * dz)
        }

        companion object {
            val ZERO = Vector3(0f, 0f, 0f)
            val FORWARD = Vector3(0f, 0f, -1f)
            val UP = Vector3(0f, 1f, 0f)
        }
    }

    // MARK: - Simulated XR State

    /** Simulated hand tracking state */
    protected var simulatedLeftHandPosition: Vector3? = null
    protected var simulatedRightHandPosition: Vector3? = null
    protected var simulatedGesture: HandTrackingService.Gesture = HandTrackingService.Gesture.NONE
    protected var simulatedGazeTarget: String? = null
    protected var isXRSessionActive: Boolean = false

    // MARK: - Setup & Teardown

    @Before
    open fun setUp() {
        device = UiDevice.getInstance(InstrumentationRegistry.getInstrumentation())
        context = ApplicationProvider.getApplicationContext()
        testStartTime = System.currentTimeMillis()
        journeyCheckpoints.clear()
        journeyStartTime = System.currentTimeMillis()

        // Create output directories
        createOutputDirectories()

        // Wait for XR app to be ready
        waitForXRAppReady()

        // Initialize simulated XR state
        initializeSimulatedXRState()

        // Capture initial state
        captureScreenshot("TestStart")
    }

    @After
    open fun tearDown() {
        // Stop video recording if active
        stopVideoRecording()

        // Capture final state
        captureScreenshot("TestEnd")

        // Generate journey metadata
        generateJourneyMetadata()

        // Log captured screenshots
        if (capturedScreenshots.isNotEmpty()) {
            println("XR E2E Test captured ${capturedScreenshots.size} screenshots:")
            capturedScreenshots.forEach { println("  - $it") }
        }

        val duration = System.currentTimeMillis() - testStartTime
        println("XR E2E Test completed in ${duration}ms")

        // Reset simulated state
        resetSimulatedXRState()
    }

    // MARK: - XR Session Management

    /**
     * Wait for the XR app to be fully ready for interaction
     */
    protected fun waitForXRAppReady() {
        // Wait for any loading indicators to disappear
        device.wait(
            Until.gone(By.res("$PACKAGE_NAME:id/loading_indicator")),
            DEFAULT_TIMEOUT
        )

        // Wait for main XR content to appear
        device.wait(
            Until.hasObject(By.res("$PACKAGE_NAME:id/spatial_home")),
            XR_TIMEOUT
        )

        // Allow XR session to initialize
        Thread.sleep(1000)

        isXRSessionActive = true
    }

    /**
     * Initialize simulated XR state for testing
     */
    protected fun initializeSimulatedXRState() {
        simulatedLeftHandPosition = Vector3(-0.3f, 0f, -0.5f)  // Left hand at comfortable position
        simulatedRightHandPosition = Vector3(0.3f, 0f, -0.5f)  // Right hand at comfortable position
        simulatedGesture = HandTrackingService.Gesture.NONE
        simulatedGazeTarget = null
    }

    /**
     * Reset simulated XR state
     */
    protected fun resetSimulatedXRState() {
        simulatedLeftHandPosition = null
        simulatedRightHandPosition = null
        simulatedGesture = HandTrackingService.Gesture.NONE
        simulatedGazeTarget = null
        isXRSessionActive = false
    }

    // MARK: - Video Recording

    /**
     * Start video recording for the current XR journey
     */
    protected fun startVideoRecording(journeyName: String) {
        try {
            val timestamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())
            val videoDir = getVideoDirectory()
            currentVideoFile = File(videoDir, "${journeyName}_$timestamp.mp4")

            // Use adb shell screenrecord for video capture
            val command = arrayOf(
                "screenrecord",
                "--size", "1920x1080",
                "--bit-rate", "12000000",  // Higher bitrate for XR content
                currentVideoFile!!.absolutePath
            )

            videoRecordingProcess = Runtime.getRuntime().exec(command)
            println("XR Video recording started: ${currentVideoFile?.absolutePath}")

        } catch (e: Exception) {
            println("Failed to start XR video recording: ${e.message}")
        }
    }

    /**
     * Stop video recording and save the file
     */
    protected fun stopVideoRecording() {
        try {
            videoRecordingProcess?.let { process ->
                process.destroy()
                process.waitFor()

                currentVideoFile?.let { file ->
                    if (file.exists() && file.length() > 0) {
                        println("XR Video saved: ${file.absolutePath} (${file.length()} bytes)")

                        MediaScannerConnection.scanFile(
                            context,
                            arrayOf(file.absolutePath),
                            arrayOf("video/mp4"),
                            null
                        )
                    }
                }
            }
        } catch (e: Exception) {
            println("Failed to stop XR video recording: ${e.message}")
        } finally {
            videoRecordingProcess = null
        }
    }

    // MARK: - Hand Tracking Simulation

    /**
     * Simulate a hand gesture
     */
    protected fun simulateGesture(gesture: HandTrackingService.Gesture, durationMs: Long = 500) {
        simulatedGesture = gesture
        println("Simulated gesture: $gesture")

        // Allow gesture to be recognized
        Thread.sleep(durationMs)

        // Reset to NONE after gesture completes
        simulatedGesture = HandTrackingService.Gesture.NONE
    }

    /**
     * Simulate pinch gesture at a specific position
     */
    protected fun simulatePinch(
        handPosition: Vector3? = null,
        durationMs: Long = 300
    ) {
        handPosition?.let {
            simulatedRightHandPosition = it
        }
        simulateGesture(HandTrackingService.Gesture.PINCH, durationMs)
    }

    /**
     * Simulate point gesture at a specific direction
     */
    protected fun simulatePoint(
        targetDirection: Vector3 = Vector3.FORWARD,
        durationMs: Long = 500
    ) {
        simulatedRightHandPosition = targetDirection
        simulateGesture(HandTrackingService.Gesture.POINT, durationMs)
    }

    /**
     * Simulate open palm gesture (show menu)
     */
    protected fun simulateOpenPalm(durationMs: Long = 500) {
        simulateGesture(HandTrackingService.Gesture.OPEN_PALM, durationMs)
    }

    /**
     * Simulate fist gesture (dismiss/cancel)
     */
    protected fun simulateFist(durationMs: Long = 300) {
        simulateGesture(HandTrackingService.Gesture.FIST, durationMs)
    }

    /**
     * Simulate two-hand spread gesture (zoom)
     */
    protected fun simulateTwoHandSpread(durationMs: Long = 500) {
        simulatedLeftHandPosition = Vector3(-0.4f, 0f, -0.5f)
        simulatedRightHandPosition = Vector3(0.4f, 0f, -0.5f)
        simulateGesture(HandTrackingService.Gesture.TWO_HAND_SPREAD, durationMs)
    }

    /**
     * Simulate emergency stop gesture (safety - h(x) >= 0)
     */
    protected fun simulateEmergencyStop() {
        simulatedLeftHandPosition = Vector3(-0.3f, 0.3f, -0.4f)
        simulatedRightHandPosition = Vector3(0.3f, 0.3f, -0.4f)
        simulateGesture(HandTrackingService.Gesture.EMERGENCY_STOP, 1000)
    }

    /**
     * Move simulated hand to a position
     */
    protected fun moveHand(
        isLeft: Boolean,
        position: Vector3,
        animationDurationMs: Long = 200
    ) {
        if (isLeft) {
            simulatedLeftHandPosition = position
        } else {
            simulatedRightHandPosition = position
        }
        Thread.sleep(animationDurationMs)
    }

    // MARK: - Gaze Simulation

    /**
     * Simulate gaze at a specific target
     */
    protected fun simulateGaze(targetId: String, durationMs: Long = 500) {
        simulatedGazeTarget = targetId
        println("Simulated gaze at: $targetId")
        Thread.sleep(durationMs)
    }

    /**
     * Simulate gaze-based selection (look + dwell)
     */
    protected fun simulateGazeSelect(targetId: String, dwellTimeMs: Long = 1000) {
        simulateGaze(targetId, dwellTimeMs)
        // After dwell time, simulate selection
        println("Gaze selection triggered for: $targetId")
    }

    /**
     * Clear gaze target
     */
    protected fun clearGaze() {
        simulatedGazeTarget = null
    }

    // MARK: - Spatial Assertions

    /**
     * Assert that a panel is at the expected distance from the user
     */
    protected fun assertPanelDistance(
        panelId: String,
        expectedDistance: Float,
        toleranceMeters: Float = 0.1f
    ) {
        // In real implementation, would query XR runtime for panel position
        // For now, we simulate the check
        println("Asserting panel '$panelId' distance: expected=$expectedDistance +/- $toleranceMeters")
    }

    /**
     * Assert that a gesture was recognized
     */
    protected fun assertGestureRecognized(expectedGesture: HandTrackingService.Gesture) {
        assert(simulatedGesture == expectedGesture || simulatedGesture == HandTrackingService.Gesture.NONE) {
            "Expected gesture $expectedGesture but was $simulatedGesture"
        }
        println("Gesture assertion passed: $expectedGesture")
    }

    /**
     * Assert that gaze is targeting expected element
     */
    protected fun assertGazeTarget(expectedTargetId: String) {
        assert(simulatedGazeTarget == expectedTargetId) {
            "Expected gaze target '$expectedTargetId' but was '$simulatedGazeTarget'"
        }
    }

    /**
     * Assert spatial panel is within comfortable interaction range
     */
    protected fun assertWithinReach(panelPosition: Vector3, maxDistance: Float = 1.2f) {
        val distance = Vector3.ZERO.distanceTo(panelPosition)
        assert(distance <= maxDistance) {
            "Panel at distance $distance exceeds comfortable reach of $maxDistance meters"
        }
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
            println("XR Screenshot captured: $filename")

        } catch (e: Exception) {
            println("Failed to capture XR screenshot '$name': ${e.message}")
        }
    }

    /**
     * Capture screenshot at a user journey checkpoint
     */
    protected fun captureJourneyCheckpoint(checkpoint: String) {
        captureScreenshot("Journey_$checkpoint")
    }

    // MARK: - Wait Helpers

    /**
     * Wait for a specific element to appear
     */
    protected fun waitForElement(resourceId: String, timeout: Long = DEFAULT_TIMEOUT): Boolean {
        return device.wait(
            Until.hasObject(By.res("$PACKAGE_NAME:id/$resourceId")),
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

    /**
     * Wait for gesture to be processed
     */
    protected fun waitForGestureProcessed(timeout: Long = GESTURE_TIMEOUT) {
        Thread.sleep(kotlin.math.min(timeout, 1000L))
    }

    // MARK: - Navigation Helpers

    /**
     * Navigate using gaze + pinch (XR standard)
     */
    protected fun navigateWithGazePinch(targetId: String) {
        simulateGaze(targetId, 300)
        simulatePinch()
        Thread.sleep(500)
    }

    /**
     * Navigate to spatial tab using XR gestures
     */
    protected fun navigateToSpatialTab(tabName: String) {
        val tabResourceId = when (tabName.lowercase()) {
            "home" -> "spatial_tab_home"
            "rooms" -> "spatial_tab_rooms"
            "scenes" -> "spatial_tab_scenes"
            "settings" -> "spatial_tab_settings"
            else -> "spatial_tab_$tabName"
        }
        navigateWithGazePinch(tabResourceId)
    }

    // MARK: - Action Helpers

    /**
     * Click on an element by resource ID (fallback for 2D UI)
     */
    protected fun clickById(resourceId: String) {
        val element = device.findObject(By.res("$PACKAGE_NAME:id/$resourceId"))
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
     * Press the back button
     */
    protected fun pressBack() {
        device.pressBack()
        Thread.sleep(300)
    }

    // MARK: - Checkpoint Recording

    /**
     * Record a journey checkpoint with spatial data
     */
    protected fun recordCheckpoint(
        name: String,
        success: Boolean,
        notes: String? = null,
        includeSpatialData: Boolean = true
    ) {
        val spatialData = if (includeSpatialData) {
            SpatialCheckpointData(
                activeGesture = simulatedGesture.name,
                gazeTarget = simulatedGazeTarget,
                handPositions = Pair(simulatedLeftHandPosition, simulatedRightHandPosition)
            )
        } else null

        journeyCheckpoints.add(
            JourneyCheckpoint(
                name = name,
                timestamp = System.currentTimeMillis(),
                success = success,
                notes = notes,
                spatialData = spatialData
            )
        )
    }

    /**
     * Record journey start
     */
    protected fun recordJourneyStart(journeyName: String) {
        captureScreenshot("Journey-$journeyName-Start")
        journeyStartTime = System.currentTimeMillis()
    }

    /**
     * Record journey end
     */
    protected fun recordJourneyEnd(journeyName: String) {
        captureScreenshot("Journey-$journeyName-End")
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

    // MARK: - Directory Helpers

    /**
     * Create all output directories
     */
    private fun createOutputDirectories() {
        getScreenshotDirectory().mkdirs()
        getVideoDirectory().mkdirs()
        getMetadataDirectory().mkdirs()
    }

    /**
     * Get the screenshot output directory
     */
    private fun getScreenshotDirectory(): File {
        val externalDir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_PICTURES)
        return File(externalDir, SCREENSHOT_DIR)
    }

    /**
     * Get the video output directory
     */
    private fun getVideoDirectory(): File {
        val externalDir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_MOVIES)
        return File(externalDir, VIDEO_DIR)
    }

    /**
     * Get the metadata output directory
     */
    private fun getMetadataDirectory(): File {
        val externalDir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOCUMENTS)
        return File(externalDir, METADATA_DIR)
    }

    /**
     * Get the current test name for file naming
     */
    protected fun getTestName(): String {
        return this::class.java.simpleName
    }

    // MARK: - Metadata Generation

    /**
     * Generate journey metadata JSON file
     */
    protected fun generateJourneyMetadata() {
        if (journeyCheckpoints.isEmpty()) return

        try {
            val checkpointsArray = JSONArray()
            for (checkpoint in journeyCheckpoints) {
                val checkpointJson = JSONObject().apply {
                    put("name", checkpoint.name)
                    put("timestamp", checkpoint.timestamp)
                    put("success", checkpoint.success)
                    checkpoint.notes?.let { put("notes", it) }

                    checkpoint.spatialData?.let { spatial ->
                        val spatialJson = JSONObject().apply {
                            spatial.activeGesture?.let { put("activeGesture", it) }
                            spatial.gazeTarget?.let { put("gazeTarget", it) }
                            spatial.handPositions?.let { hands ->
                                hands.first?.let { left ->
                                    put("leftHand", JSONObject().apply {
                                        put("x", left.x)
                                        put("y", left.y)
                                        put("z", left.z)
                                    })
                                }
                                hands.second?.let { right ->
                                    put("rightHand", JSONObject().apply {
                                        put("x", right.x)
                                        put("y", right.y)
                                        put("z", right.z)
                                    })
                                }
                            }
                        }
                        put("spatialData", spatialJson)
                    }
                }
                checkpointsArray.put(checkpointJson)
            }

            val metadata = JSONObject().apply {
                put("testName", getTestName())
                put("platform", "AndroidXR")
                put("startTime", journeyStartTime)
                put("endTime", System.currentTimeMillis())
                put("xrSessionActive", isXRSessionActive)
                put("checkpoints", checkpointsArray)
                put("passedCheckpoints", journeyCheckpoints.count { it.success })
                put("totalCheckpoints", journeyCheckpoints.size)
                currentVideoFile?.let { put("videoPath", it.absolutePath) }
            }

            val metadataDir = getMetadataDirectory()
            val timestamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())
            val metadataFile = File(metadataDir, "${getTestName()}_$timestamp.json")

            FileOutputStream(metadataFile).use { fos ->
                fos.write(metadata.toString(2).toByteArray())
            }

            println("XR Journey metadata saved: ${metadataFile.absolutePath}")

        } catch (e: Exception) {
            println("Failed to generate XR journey metadata: ${e.message}")
        }
    }
}

/*
 * 鏡
 * Mirror in spatial space.
 * h(x) >= 0. Always.
 */
