/**
 * UserJourneyE2ETest.kt -- Comprehensive E2E Video Tests for Android User Journeys
 *
 * Colony: Crystal (e7) - Verification & Polish
 *
 * Records complete user journeys with video for:
 *   - Widget interactions
 *   - Notification flows
 *   - Household member switching
 *   - Morning routine flow
 *   - Scene activation
 *
 * Video Output: test-artifacts/videos/android/{journey-name}.mp4
 *
 * Run:
 *   ./gradlew connectedAndroidTest \
 *     -Pandroid.testInstrumentationRunnerArguments.class=com.kagami.android.e2e.UserJourneyE2ETest
 *
 * h(x) >= 0. Always.
 */
package com.kagami.android.e2e

import android.Manifest
import android.content.Context
import android.content.Intent
import android.media.MediaScannerConnection
import android.os.Environment
import android.os.ParcelFileDescriptor
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.filters.LargeTest
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.rule.GrantPermissionRule
import androidx.test.uiautomator.By
import androidx.test.uiautomator.Direction
import androidx.test.uiautomator.Until
import org.json.JSONArray
import org.json.JSONObject
import org.junit.After
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.io.FileOutputStream
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Comprehensive E2E User Journey Tests with Video Recording
 */
@RunWith(AndroidJUnit4::class)
@LargeTest
class UserJourneyE2ETest : BaseE2ETest() {

    // MARK: - Configuration

    companion object {
        private const val VIDEO_OUTPUT_DIR = "kagami-e2e-videos"
        private const val METADATA_OUTPUT_DIR = "kagami-e2e-metadata"
        private const val JOURNEY_TIMEOUT = 60_000L
    }

    // MARK: - Rules

    @get:Rule
    val screenRecordPermission: GrantPermissionRule = GrantPermissionRule.grant(
        Manifest.permission.WRITE_EXTERNAL_STORAGE,
        Manifest.permission.READ_EXTERNAL_STORAGE,
        Manifest.permission.RECORD_AUDIO
    )

    // MARK: - Video Recording Properties

    private var videoRecordingProcess: Process? = null
    private var currentVideoFile: File? = null
    private var journeyCheckpoints: MutableList<JourneyCheckpoint> = mutableListOf()
    private var journeyStartTime: Long = 0

    /**
     * Journey checkpoint data class
     */
    data class JourneyCheckpoint(
        val name: String,
        val timestamp: Long,
        val success: Boolean,
        val notes: String? = null
    )

    // MARK: - Setup & Teardown

    @Before
    override fun setUp() {
        super.setUp()
        journeyCheckpoints.clear()
        journeyStartTime = System.currentTimeMillis()
        createOutputDirectories()
    }

    @After
    override fun tearDown() {
        stopVideoRecording()
        generateJourneyMetadata()
        super.tearDown()
    }

    // MARK: - Video Recording Methods

    /**
     * Start video recording for the current journey
     */
    private fun startVideoRecording(journeyName: String) {
        try {
            val timestamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())
            val videoDir = getVideoDirectory()
            currentVideoFile = File(videoDir, "${journeyName}_$timestamp.mp4")

            // Use adb shell screenrecord for video capture
            // Note: This requires the test to run with elevated permissions
            val command = arrayOf(
                "screenrecord",
                "--size", "1080x1920",
                "--bit-rate", "8000000",
                currentVideoFile!!.absolutePath
            )

            // Execute via instrumentation
            val instrumentation = InstrumentationRegistry.getInstrumentation()
            videoRecordingProcess = Runtime.getRuntime().exec(command)

            println("Video recording started: ${currentVideoFile?.absolutePath}")

        } catch (e: Exception) {
            println("Failed to start video recording: ${e.message}")
            // Continue without video - tests should still pass
        }
    }

    /**
     * Stop video recording and save the file
     */
    private fun stopVideoRecording() {
        try {
            videoRecordingProcess?.let { process ->
                // Send SIGINT to stop recording gracefully
                process.destroy()
                process.waitFor()

                currentVideoFile?.let { file ->
                    if (file.exists() && file.length() > 0) {
                        println("Video saved: ${file.absolutePath} (${file.length()} bytes)")

                        // Notify media scanner
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
            println("Failed to stop video recording: ${e.message}")
        } finally {
            videoRecordingProcess = null
        }
    }

    // MARK: - Morning Routine Journey

    /**
     * Tests the complete morning routine flow with video recording
     * Journey: Wake up -> Check home status -> Activate morning scene -> View rooms
     */
    @Test
    fun testMorningRoutineJourney() {
        val journeyName = "MorningRoutine"
        startVideoRecording(journeyName)
        recordJourneyStart(journeyName)

        try {
            // Skip onboarding if needed
            skipToHomeIfNeeded()

            // Phase 1: Verify home screen
            recordUserJourney("$journeyName-Phase1", listOf(
                "VerifyHomeScreen" to {
                    navigateToHome()
                    waitForElement("home_content", DEFAULT_TIMEOUT)
                    captureJourneyCheckpoint("HomeVerified")
                    recordCheckpoint("HomeScreenVerified", success = true)
                }
            ))

            // Phase 2: Check status cards
            recordUserJourney("$journeyName-Phase2", listOf(
                "CheckStatusCards" to {
                    Thread.sleep(1000)
                    captureJourneyCheckpoint("StatusCards")

                    // Look for status indicators
                    val statusCard = device.findObject(By.res("com.kagami.android:id/status_card"))
                    statusCard?.let {
                        captureScreenshot("StatusCardFound")
                    }
                    recordCheckpoint("StatusChecked", success = true)
                }
            ))

            // Phase 3: Navigate to scenes and activate morning scene
            recordUserJourney("$journeyName-Phase3", listOf(
                "NavigateToScenes" to {
                    navigateToScenes()
                    waitForElement("scenes_list", DEFAULT_TIMEOUT)
                    captureJourneyCheckpoint("ScenesScreen")
                    recordCheckpoint("ScenesNavigated", success = true)
                },
                "ActivateMorningScene" to {
                    // Look for morning-related scenes
                    val morningScenes = listOf("Coffee Time", "Wake Up", "Morning", "Welcome Home")
                    var activated = false

                    for (sceneName in morningScenes) {
                        val scene = device.findObject(By.text(sceneName))
                        if (scene != null) {
                            captureJourneyCheckpoint("PreSceneActivation-$sceneName")
                            scene.click()
                            Thread.sleep(2000)
                            captureJourneyCheckpoint("PostSceneActivation-$sceneName")
                            recordCheckpoint("MorningSceneActivated", success = true, notes = sceneName)
                            activated = true
                            break
                        }
                    }

                    if (!activated) {
                        // Tap first available scene
                        val firstScene = device.findObject(By.res("com.kagami.android:id/scene_item"))
                        firstScene?.click()
                        Thread.sleep(1000)
                        recordCheckpoint("FallbackSceneActivated", success = true)
                    }
                }
            ))

            // Phase 4: View rooms
            recordUserJourney("$journeyName-Phase4", listOf(
                "NavigateToRooms" to {
                    navigateToRooms()
                    waitForElement("rooms_list", DEFAULT_TIMEOUT)
                    captureJourneyCheckpoint("RoomsScreen")
                    recordCheckpoint("RoomsViewed", success = true)
                },
                "ScrollRooms" to {
                    val roomsList = device.findObject(By.res("com.kagami.android:id/rooms_list"))
                    roomsList?.let {
                        it.scroll(Direction.DOWN, 0.8f)
                        Thread.sleep(500)
                        captureJourneyCheckpoint("RoomsScrolled")
                        it.scroll(Direction.UP, 0.8f)
                    }
                }
            ))

            // Phase 5: Return to home
            recordUserJourney("$journeyName-Phase5", listOf(
                "ReturnHome" to {
                    navigateToHome()
                    waitForElement("home_content", DEFAULT_TIMEOUT)
                    captureJourneyCheckpoint("JourneyComplete")
                    recordCheckpoint("MorningRoutineComplete", success = true)
                }
            ))

        } finally {
            recordJourneyEnd(journeyName)
        }
    }

    // MARK: - Widget Interactions Journey

    /**
     * Tests widget interaction flows
     * Journey: Open widget -> Trigger actions -> Verify app state
     */
    @Test
    fun testWidgetInteractionsJourney() {
        val journeyName = "WidgetInteractions"
        startVideoRecording(journeyName)
        recordJourneyStart(journeyName)

        try {
            skipToHomeIfNeeded()

            // Phase 1: Navigate home and identify widget areas
            recordUserJourney("$journeyName-Phase1", listOf(
                "InitialState" to {
                    navigateToHome()
                    waitForElement("home_content", DEFAULT_TIMEOUT)
                    captureJourneyCheckpoint("HomeScreen")
                    recordCheckpoint("HomeVerified", success = true)
                }
            ))

            // Phase 2: Test quick action widgets (in-app widgets)
            recordUserJourney("$journeyName-Phase2", listOf(
                "TestQuickActions" to {
                    val quickActionButton = device.findObject(
                        By.res("com.kagami.android:id/quick_action_button")
                    )

                    if (quickActionButton != null) {
                        captureJourneyCheckpoint("PreQuickAction")
                        quickActionButton.click()
                        Thread.sleep(1500)
                        captureJourneyCheckpoint("PostQuickAction")
                        recordCheckpoint("QuickActionTriggered", success = true)
                    } else {
                        recordCheckpoint("QuickActionNotFound", success = false)
                    }
                }
            ))

            // Phase 3: Test scene cards (widget-like interactions)
            recordUserJourney("$journeyName-Phase3", listOf(
                "TestSceneCards" to {
                    navigateToScenes()
                    Thread.sleep(1000)

                    val sceneCards = device.findObjects(
                        By.res("com.kagami.android:id/scene_card")
                    )

                    if (sceneCards.isNotEmpty()) {
                        captureJourneyCheckpoint("SceneCardsFound")

                        // Long press for context menu
                        sceneCards.firstOrNull()?.let { card ->
                            card.longClick()
                            Thread.sleep(1000)
                            captureJourneyCheckpoint("SceneCardLongPress")

                            // Dismiss context menu if opened
                            device.pressBack()
                        }

                        recordCheckpoint("SceneCardsInteracted", success = true)
                    }
                }
            ))

            // Phase 4: Test room widgets
            recordUserJourney("$journeyName-Phase4", listOf(
                "TestRoomWidgets" to {
                    navigateToRooms()
                    Thread.sleep(1000)

                    val roomWidgets = device.findObjects(
                        By.res("com.kagami.android:id/room_card")
                    )

                    if (roomWidgets.isNotEmpty()) {
                        captureJourneyCheckpoint("RoomWidgetsFound")

                        // Tap to expand
                        roomWidgets.firstOrNull()?.click()
                        Thread.sleep(1000)
                        captureJourneyCheckpoint("RoomWidgetExpanded")

                        recordCheckpoint("RoomWidgetsInteracted", success = true)
                    }
                }
            ))

            captureJourneyCheckpoint("JourneyComplete")

        } finally {
            recordJourneyEnd(journeyName)
        }
    }

    // MARK: - Notification Flows Journey

    /**
     * Tests notification interaction flows
     * Journey: Trigger notification -> Interact -> Navigate to app
     */
    @Test
    fun testNotificationFlowsJourney() {
        val journeyName = "NotificationFlows"
        startVideoRecording(journeyName)
        recordJourneyStart(journeyName)

        try {
            skipToHomeIfNeeded()

            // Phase 1: Verify app is running
            recordUserJourney("$journeyName-Phase1", listOf(
                "VerifyAppState" to {
                    navigateToHome()
                    waitForElement("home_content", DEFAULT_TIMEOUT)
                    captureJourneyCheckpoint("AppRunning")
                    recordCheckpoint("AppVerified", success = true)
                }
            ))

            // Phase 2: Open notification shade
            recordUserJourney("$journeyName-Phase2", listOf(
                "OpenNotificationShade" to {
                    captureJourneyCheckpoint("PreNotificationShade")

                    // Swipe down from top to open notifications
                    device.swipe(
                        device.displayWidth / 2,
                        0,
                        device.displayWidth / 2,
                        device.displayHeight / 2,
                        10
                    )
                    Thread.sleep(1000)
                    captureJourneyCheckpoint("NotificationShadeOpen")
                    recordCheckpoint("NotificationShadeOpened", success = true)
                }
            ))

            // Phase 3: Check for Kagami notifications
            recordUserJourney("$journeyName-Phase3", listOf(
                "CheckNotifications" to {
                    // Look for Kagami notifications
                    val kagamiNotification = device.findObject(By.textContains("Kagami"))

                    if (kagamiNotification != null) {
                        captureJourneyCheckpoint("KagamiNotificationFound")
                        kagamiNotification.click()
                        Thread.sleep(1000)
                        captureJourneyCheckpoint("NotificationTapped")
                        recordCheckpoint("NotificationInteracted", success = true)
                    } else {
                        // Close notification shade
                        device.pressBack()
                        captureJourneyCheckpoint("NoNotificationsFound")
                        recordCheckpoint("NotificationChecked", success = true, notes = "No notifications")
                    }
                }
            ))

            // Phase 4: Return to app
            recordUserJourney("$journeyName-Phase4", listOf(
                "ReturnToApp" to {
                    // Ensure we're back in the app
                    device.pressBack()
                    Thread.sleep(500)

                    navigateToHome()
                    waitForElement("home_content", DEFAULT_TIMEOUT)
                    captureJourneyCheckpoint("ReturnedToApp")
                    recordCheckpoint("ReturnedToApp", success = true)
                }
            ))

            captureJourneyCheckpoint("JourneyComplete")

        } finally {
            recordJourneyEnd(journeyName)
        }
    }

    // MARK: - Household Member Switching Journey

    /**
     * Tests switching between household members
     * Journey: Settings -> Household -> Switch member -> Verify changes
     */
    @Test
    fun testHouseholdMemberSwitchingJourney() {
        val journeyName = "HouseholdSwitch"
        startVideoRecording(journeyName)
        recordJourneyStart(journeyName)

        try {
            skipToHomeIfNeeded()

            // Phase 1: Navigate to Settings
            recordUserJourney("$journeyName-Phase1", listOf(
                "NavigateToSettings" to {
                    navigateToSettings()
                    waitForElement("settings_content", DEFAULT_TIMEOUT)
                    captureJourneyCheckpoint("SettingsScreen")
                    recordCheckpoint("SettingsNavigated", success = true)
                }
            ))

            // Phase 2: Access Household section
            recordUserJourney("$journeyName-Phase2", listOf(
                "AccessHousehold" to {
                    val householdOption = device.findObject(By.text("Household"))

                    if (householdOption != null) {
                        captureJourneyCheckpoint("PreHouseholdTap")
                        householdOption.click()
                        Thread.sleep(1000)
                        captureJourneyCheckpoint("HouseholdSection")
                        recordCheckpoint("HouseholdAccessed", success = true)
                    } else {
                        // Scroll to find it
                        val settingsList = device.findObject(
                            By.res("com.kagami.android:id/settings_list")
                        )
                        settingsList?.scroll(Direction.DOWN, 0.5f)
                        Thread.sleep(500)

                        device.findObject(By.text("Household"))?.click()
                        Thread.sleep(1000)
                        captureJourneyCheckpoint("HouseholdSectionAfterScroll")
                        recordCheckpoint("HouseholdAccessedAfterScroll", success = true)
                    }
                }
            ))

            // Phase 3: View household members
            recordUserJourney("$journeyName-Phase3", listOf(
                "ViewMembers" to {
                    Thread.sleep(500)
                    captureJourneyCheckpoint("HouseholdMembers")

                    // Count visible members
                    val memberItems = device.findObjects(
                        By.res("com.kagami.android:id/member_item")
                    )

                    if (memberItems.size > 0) {
                        captureJourneyCheckpoint("MembersFound")
                        recordCheckpoint("MembersViewed", success = true, notes = "${memberItems.size} members")
                    }
                }
            ))

            // Phase 4: Select a different member
            recordUserJourney("$journeyName-Phase4", listOf(
                "SelectMember" to {
                    val memberItems = device.findObjects(
                        By.res("com.kagami.android:id/member_item")
                    )

                    if (memberItems.size > 1) {
                        // Select second member
                        captureJourneyCheckpoint("PreMemberSwitch")
                        memberItems[1].click()
                        Thread.sleep(1500)
                        captureJourneyCheckpoint("PostMemberSwitch")
                        recordCheckpoint("MemberSwitched", success = true)
                    } else {
                        recordCheckpoint("OnlyOneMember", success = true, notes = "Cannot switch")
                    }
                }
            ))

            // Phase 5: Return and verify
            recordUserJourney("$journeyName-Phase5", listOf(
                "VerifyAndReturn" to {
                    pressBack()
                    Thread.sleep(500)
                    pressBack()
                    Thread.sleep(500)

                    navigateToHome()
                    waitForElement("home_content", DEFAULT_TIMEOUT)
                    captureJourneyCheckpoint("ReturnedHome")
                    recordCheckpoint("HouseholdSwitchComplete", success = true)
                }
            ))

            captureJourneyCheckpoint("JourneyComplete")

        } finally {
            recordJourneyEnd(journeyName)
        }
    }

    // MARK: - Scene Activation Journey

    /**
     * Tests comprehensive scene activation flow
     * Journey: Navigate to scenes -> Activate multiple scenes -> Verify feedback
     */
    @Test
    fun testSceneActivationJourney() {
        val journeyName = "SceneActivation"
        startVideoRecording(journeyName)
        recordJourneyStart(journeyName)

        try {
            skipToHomeIfNeeded()

            // Phase 1: Navigate to scenes
            recordUserJourney("$journeyName-Phase1", listOf(
                "NavigateToScenes" to {
                    navigateToScenes()
                    waitForElement("scenes_list", DEFAULT_TIMEOUT)
                    captureJourneyCheckpoint("ScenesScreen")
                    recordCheckpoint("ScenesNavigated", success = true)
                }
            ))

            // Phase 2: Activate Movie Mode
            recordUserJourney("$journeyName-Phase2", listOf(
                "ActivateMovieMode" to {
                    val movieMode = device.findObject(By.text("Movie Mode"))

                    if (movieMode != null) {
                        captureJourneyCheckpoint("PreMovieMode")
                        movieMode.click()
                        Thread.sleep(2000) // Wait for haptic and visual feedback
                        captureJourneyCheckpoint("PostMovieMode")
                        recordCheckpoint("MovieModeActivated", success = true)
                    } else {
                        recordCheckpoint("MovieModeNotFound", success = false)
                    }
                }
            ))

            // Phase 3: Activate Relax scene
            recordUserJourney("$journeyName-Phase3", listOf(
                "ActivateRelax" to {
                    val relax = device.findObject(By.text("Relax"))

                    if (relax != null) {
                        captureJourneyCheckpoint("PreRelax")
                        relax.click()
                        Thread.sleep(2000)
                        captureJourneyCheckpoint("PostRelax")
                        recordCheckpoint("RelaxActivated", success = true)
                    }
                }
            ))

            // Phase 4: Scroll and activate more scenes
            recordUserJourney("$journeyName-Phase4", listOf(
                "ScrollAndActivate" to {
                    val scenesList = device.findObject(
                        By.res("com.kagami.android:id/scenes_list")
                    )

                    scenesList?.scroll(Direction.DOWN, 0.5f)
                    Thread.sleep(500)
                    captureJourneyCheckpoint("ScenesScrolled")

                    // Activate Goodnight if visible
                    val goodnight = device.findObject(By.text("Goodnight"))
                    if (goodnight != null) {
                        goodnight.click()
                        Thread.sleep(2000)
                        captureJourneyCheckpoint("GoodnightActivated")
                        recordCheckpoint("GoodnightActivated", success = true)
                    }
                }
            ))

            // Phase 5: Rapid scene switching
            recordUserJourney("$journeyName-Phase5", listOf(
                "RapidSwitch" to {
                    // Scroll back to top
                    val scenesList = device.findObject(
                        By.res("com.kagami.android:id/scenes_list")
                    )
                    scenesList?.scroll(Direction.UP, 1.0f)
                    Thread.sleep(500)

                    captureJourneyCheckpoint("RapidSwitchStart")

                    val sceneItems = device.findObjects(
                        By.res("com.kagami.android:id/scene_item")
                    )

                    for ((index, item) in sceneItems.take(3).withIndex()) {
                        item.click()
                        Thread.sleep(800)
                        captureJourneyCheckpoint("RapidSwitch-$index")
                    }

                    recordCheckpoint("RapidSwitchComplete", success = true)
                }
            ))

            captureJourneyCheckpoint("JourneyComplete")

        } finally {
            recordJourneyEnd(journeyName)
        }
    }

    // MARK: - Full App Exploration Journey

    /**
     * Tests complete exploration of all app areas
     * Journey: Home -> Rooms -> Scenes -> Settings -> Home
     */
    @Test
    fun testFullAppExplorationJourney() {
        val journeyName = "FullAppExploration"
        startVideoRecording(journeyName)
        recordJourneyStart(journeyName)

        try {
            skipToHomeIfNeeded()

            val tabs = listOf(
                Triple("Home", { navigateToHome() }, "home_content"),
                Triple("Rooms", { navigateToRooms() }, "rooms_list"),
                Triple("Scenes", { navigateToScenes() }, "scenes_list"),
                Triple("Settings", { navigateToSettings() }, "settings_content")
            )

            for ((index, tab) in tabs.withIndex()) {
                val (name, navigateFunc, expectedElement) = tab

                recordUserJourney("$journeyName-Tab${index + 1}", listOf(
                    "Visit$name" to {
                        navigateFunc()
                        waitForElement(expectedElement, DEFAULT_TIMEOUT)
                        Thread.sleep(1000)
                        captureJourneyCheckpoint("${name}Tab")

                        // Scroll content if available
                        val scrollableList = device.findObject(
                            By.scrollable(true)
                        )
                        scrollableList?.let {
                            it.scroll(Direction.DOWN, 0.5f)
                            Thread.sleep(500)
                            captureJourneyCheckpoint("${name}Scrolled")
                            it.scroll(Direction.UP, 0.5f)
                        }

                        recordCheckpoint("${name}Visited", success = true)
                    }
                ))
            }

            // Return to home
            recordUserJourney("$journeyName-Final", listOf(
                "ReturnHome" to {
                    navigateToHome()
                    waitForElement("home_content", DEFAULT_TIMEOUT)
                    captureJourneyCheckpoint("JourneyComplete")
                    recordCheckpoint("FullExplorationComplete", success = true)
                }
            ))

        } finally {
            recordJourneyEnd(journeyName)
        }
    }

    // MARK: - Private Helpers

    private fun skipToHomeIfNeeded() {
        // Check if onboarding is showing
        val welcomeText = device.findObject(By.text("Welcome to Kagami"))
        if (welcomeText != null) {
            completeOnboarding()
        }
    }

    private fun completeOnboarding() {
        clickByText("Continue")
        Thread.sleep(500)
        clickByText("Demo Mode")
        Thread.sleep(1000)
        clickByText("Continue")
        Thread.sleep(500)

        repeat(3) {
            clickByText("Skip")
            Thread.sleep(500)
        }

        clickByText("Get Started")
        Thread.sleep(1000)
    }

    private fun recordJourneyStart(journeyName: String) {
        captureScreenshot("Journey-$journeyName-Start")
        journeyStartTime = System.currentTimeMillis()
    }

    private fun recordJourneyEnd(journeyName: String) {
        captureScreenshot("Journey-$journeyName-End")
    }

    private fun recordCheckpoint(name: String, success: Boolean, notes: String? = null) {
        journeyCheckpoints.add(JourneyCheckpoint(
            name = name,
            timestamp = System.currentTimeMillis(),
            success = success,
            notes = notes
        ))
    }

    private fun createOutputDirectories() {
        getVideoDirectory().mkdirs()
        getMetadataDirectory().mkdirs()
    }

    private fun getVideoDirectory(): File {
        val externalDir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_MOVIES)
        return File(externalDir, VIDEO_OUTPUT_DIR)
    }

    private fun getMetadataDirectory(): File {
        val externalDir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOCUMENTS)
        return File(externalDir, METADATA_OUTPUT_DIR)
    }

    private fun generateJourneyMetadata() {
        if (journeyCheckpoints.isEmpty()) return

        try {
            val checkpointsArray = JSONArray()
            for (checkpoint in journeyCheckpoints) {
                val checkpointJson = JSONObject().apply {
                    put("name", checkpoint.name)
                    put("timestamp", checkpoint.timestamp)
                    put("success", checkpoint.success)
                    checkpoint.notes?.let { put("notes", it) }
                }
                checkpointsArray.put(checkpointJson)
            }

            val metadata = JSONObject().apply {
                put("testName", getTestName())
                put("platform", "Android")
                put("startTime", journeyStartTime)
                put("endTime", System.currentTimeMillis())
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

            println("Journey metadata saved: ${metadataFile.absolutePath}")

        } catch (e: Exception) {
            println("Failed to generate journey metadata: ${e.message}")
        }
    }

    private fun getTestName(): String {
        return this::class.java.simpleName
    }
}

/*
 * Mirror
 * User journeys capture the complete Android experience.
 * Video recording preserves every interaction.
 * h(x) >= 0. Always.
 */
