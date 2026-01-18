/**
 * Firebase Remote Config Feature Flags Service
 *
 * Colony: Beacon (e5) - Planning & Configuration
 * h(x) >= 0. Always.
 *
 * Provides feature flag management via Firebase Remote Config.
 * Enables A/B testing, gradual rollouts, and kill switches.
 *
 * Usage:
 * ```kotlin
 * val featureFlags = FeatureFlagsService.getInstance()
 * if (featureFlags.isEnabled("new_onboarding_flow")) {
 *     // Show new onboarding
 * }
 * ```
 */

package com.kagami.android.services

import android.util.Log
import com.google.firebase.ktx.Firebase
import com.google.firebase.remoteconfig.FirebaseRemoteConfig
import com.google.firebase.remoteconfig.ktx.remoteConfig
import com.google.firebase.remoteconfig.ktx.remoteConfigSettings
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.tasks.await
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class FeatureFlagsService @Inject constructor() {

    private val remoteConfig: FirebaseRemoteConfig = Firebase.remoteConfig

    // State
    private val _isInitialized = MutableStateFlow(false)
    val isInitialized: StateFlow<Boolean> = _isInitialized.asStateFlow()

    private val _lastFetchStatus = MutableStateFlow<FetchStatus>(FetchStatus.NotFetched)
    val lastFetchStatus: StateFlow<FetchStatus> = _lastFetchStatus.asStateFlow()

    companion object {
        private const val TAG = "FeatureFlags"

        // =============================================================
        // FEATURE FLAG KEYS
        // =============================================================

        // Onboarding
        const val FLAG_NEW_ONBOARDING_FLOW = "new_onboarding_flow"
        const val FLAG_SKIP_PERMISSIONS_STEP = "skip_permissions_step"

        // UI Features
        const val FLAG_DYNAMIC_COLORS = "dynamic_colors_enabled"
        const val FLAG_SHOW_SAFETY_SCORE = "show_safety_score"
        const val FLAG_HERO_ACTION_ENABLED = "hero_action_enabled"
        const val FLAG_PULL_TO_REFRESH = "pull_to_refresh_enabled"

        // Widget Features
        const val FLAG_WIDGETS_ENABLED = "widgets_enabled"
        const val FLAG_GLANCE_WIDGETS = "glance_widgets_enabled"

        // Wear OS Features
        const val FLAG_WEAR_OS_SYNC = "wear_os_sync_enabled"
        const val FLAG_WEAR_TILES = "wear_tiles_enabled"
        const val FLAG_WEAR_COMPLICATIONS = "wear_complications_enabled"

        // Voice Features
        const val FLAG_VOICE_COMMANDS = "voice_commands_enabled"
        const val FLAG_ASSISTANT_ACTIONS = "assistant_actions_enabled"

        // Analytics & Debug
        const val FLAG_DEBUG_MODE = "debug_mode_enabled"
        const val FLAG_VERBOSE_LOGGING = "verbose_logging_enabled"

        // Safety Features (CBF)
        const val FLAG_FIREPLACE_ENABLED = "fireplace_control_enabled"
        const val FLAG_LOCK_CONTROL_ENABLED = "lock_control_enabled"

        // Experiment rollout percentages
        const val CONFIG_TABLET_LAYOUT_PERCENT = "tablet_layout_rollout_percent"
        const val CONFIG_NEW_ROOMS_UI_PERCENT = "new_rooms_ui_rollout_percent"

        // Cache settings
        private const val FETCH_INTERVAL_DEBUG = 60L // 1 minute for debug
        private const val FETCH_INTERVAL_RELEASE = 3600L // 1 hour for release
    }

    init {
        configureRemoteConfig()
    }

    /**
     * Configure Remote Config settings.
     */
    private fun configureRemoteConfig() {
        val configSettings = remoteConfigSettings {
            // Use shorter cache interval for debug builds
            minimumFetchIntervalInSeconds = if (BuildConfig.DEBUG) {
                FETCH_INTERVAL_DEBUG
            } else {
                FETCH_INTERVAL_RELEASE
            }
        }
        remoteConfig.setConfigSettingsAsync(configSettings)

        // Set default values
        remoteConfig.setDefaultsAsync(getDefaultValues())
    }

    /**
     * Default values for all feature flags.
     * These are used when Remote Config hasn't been fetched yet.
     */
    private fun getDefaultValues(): Map<String, Any> = mapOf(
        // Onboarding
        FLAG_NEW_ONBOARDING_FLOW to true,
        FLAG_SKIP_PERMISSIONS_STEP to false,

        // UI Features
        FLAG_DYNAMIC_COLORS to true,
        FLAG_SHOW_SAFETY_SCORE to false, // Hide h(x) from users per plan
        FLAG_HERO_ACTION_ENABLED to true,
        FLAG_PULL_TO_REFRESH to true,

        // Widget Features
        FLAG_WIDGETS_ENABLED to true,
        FLAG_GLANCE_WIDGETS to true,

        // Wear OS Features
        FLAG_WEAR_OS_SYNC to true,
        FLAG_WEAR_TILES to true,
        FLAG_WEAR_COMPLICATIONS to true,

        // Voice Features
        FLAG_VOICE_COMMANDS to true,
        FLAG_ASSISTANT_ACTIONS to true,

        // Analytics & Debug
        FLAG_DEBUG_MODE to BuildConfig.DEBUG,
        FLAG_VERBOSE_LOGGING to BuildConfig.DEBUG,

        // Safety Features
        FLAG_FIREPLACE_ENABLED to true,
        FLAG_LOCK_CONTROL_ENABLED to true,

        // Experiment rollouts (percentage of users)
        CONFIG_TABLET_LAYOUT_PERCENT to 100L,
        CONFIG_NEW_ROOMS_UI_PERCENT to 0L
    )

    // =============================================================
    // INITIALIZATION
    // =============================================================

    /**
     * Initialize feature flags by fetching from Remote Config.
     * Call this at app startup.
     */
    suspend fun initialize() {
        try {
            _lastFetchStatus.value = FetchStatus.Fetching

            // Fetch and activate
            val fetchSuccessful = remoteConfig.fetchAndActivate().await()

            _lastFetchStatus.value = if (fetchSuccessful) {
                FetchStatus.FetchedAndActivated
            } else {
                FetchStatus.FetchedNoChange
            }

            _isInitialized.value = true
            Log.i(TAG, "Feature flags initialized. Fetch successful: $fetchSuccessful")

        } catch (e: Exception) {
            Log.e(TAG, "Failed to fetch feature flags", e)
            _lastFetchStatus.value = FetchStatus.Failed(e.message ?: "Unknown error")

            // Still mark as initialized - we'll use default values
            _isInitialized.value = true
        }
    }

    /**
     * Force refresh feature flags from server.
     * Useful when user returns to app after being away.
     */
    suspend fun refresh() {
        initialize()
    }

    // =============================================================
    // FLAG ACCESSORS
    // =============================================================

    /**
     * Check if a boolean feature flag is enabled.
     */
    fun isEnabled(key: String): Boolean {
        return remoteConfig.getBoolean(key)
    }

    /**
     * Get a string configuration value.
     */
    fun getString(key: String): String {
        return remoteConfig.getString(key)
    }

    /**
     * Get a long configuration value.
     */
    fun getLong(key: String): Long {
        return remoteConfig.getLong(key)
    }

    /**
     * Get a double configuration value.
     */
    fun getDouble(key: String): Double {
        return remoteConfig.getDouble(key)
    }

    // =============================================================
    // CONVENIENCE METHODS
    // =============================================================

    /**
     * Check if dynamic colors (Material You) are enabled.
     */
    fun isDynamicColorsEnabled(): Boolean = isEnabled(FLAG_DYNAMIC_COLORS)

    /**
     * Check if widgets feature is enabled.
     */
    fun isWidgetsEnabled(): Boolean = isEnabled(FLAG_WIDGETS_ENABLED)

    /**
     * Check if Wear OS sync is enabled.
     */
    fun isWearOsSyncEnabled(): Boolean = isEnabled(FLAG_WEAR_OS_SYNC)

    /**
     * Check if voice commands are enabled.
     */
    fun isVoiceCommandsEnabled(): Boolean = isEnabled(FLAG_VOICE_COMMANDS)

    /**
     * Check if fireplace control is enabled (safety feature).
     */
    fun isFireplaceControlEnabled(): Boolean = isEnabled(FLAG_FIREPLACE_ENABLED)

    /**
     * Check if lock control is enabled (safety feature).
     */
    fun isLockControlEnabled(): Boolean = isEnabled(FLAG_LOCK_CONTROL_ENABLED)

    /**
     * Check if pull-to-refresh is enabled.
     */
    fun isPullToRefreshEnabled(): Boolean = isEnabled(FLAG_PULL_TO_REFRESH)

    /**
     * Check if debug mode is enabled.
     */
    fun isDebugModeEnabled(): Boolean = isEnabled(FLAG_DEBUG_MODE)

    // =============================================================
    // A/B TESTING HELPERS
    // =============================================================

    /**
     * Check if user is in a rollout percentage.
     * Uses stable user ID hashing for consistent assignment.
     *
     * @param rolloutPercent Percentage of users (0-100)
     * @param userId Stable user identifier
     */
    fun isInRollout(rolloutPercent: Long, userId: String): Boolean {
        if (rolloutPercent >= 100) return true
        if (rolloutPercent <= 0) return false

        // Use hash for consistent bucket assignment
        val bucket = (userId.hashCode().toLong() and 0x7FFFFFFF) % 100
        return bucket < rolloutPercent
    }

    /**
     * Check if user should see new tablet layout.
     */
    fun shouldUseTabletLayout(userId: String): Boolean {
        val percent = getLong(CONFIG_TABLET_LAYOUT_PERCENT)
        return isInRollout(percent, userId)
    }

    /**
     * Check if user should see new rooms UI.
     */
    fun shouldUseNewRoomsUi(userId: String): Boolean {
        val percent = getLong(CONFIG_NEW_ROOMS_UI_PERCENT)
        return isInRollout(percent, userId)
    }
}

/**
 * Placeholder for BuildConfig access.
 * In a real project, this would come from the generated BuildConfig.
 */
private object BuildConfig {
    const val DEBUG = true
}

/**
 * Status of feature flag fetch operation.
 */
sealed class FetchStatus {
    object NotFetched : FetchStatus()
    object Fetching : FetchStatus()
    object FetchedAndActivated : FetchStatus()
    object FetchedNoChange : FetchStatus()
    data class Failed(val error: String) : FetchStatus()
}
