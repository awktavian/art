/**
 * Kagami Analytics Service
 *
 * Colony: Crystal (e7) - Synthesis
 * h(x) >= 0. Always.
 *
 * Tracks key user events for product insights:
 * - Screen views and navigation
 * - Scene activations
 * - Room interactions
 * - Widget usage
 * - Wear OS sync
 * - Voice commands
 * - Onboarding completion
 * - Errors and performance
 *
 * Privacy-first: No PII, anonymized device ID, user can opt out.
 */

package com.kagami.android.services

import android.os.Bundle
import com.google.firebase.analytics.FirebaseAnalytics
import com.google.firebase.analytics.ktx.analytics
import com.google.firebase.analytics.logEvent
import com.google.firebase.ktx.Firebase
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AnalyticsService @Inject constructor() {

    private val analytics: FirebaseAnalytics = Firebase.analytics

    // ===============================================================
    // GENERIC EVENT TRACKING
    // ===============================================================

    /**
     * Track a generic custom event with parameters.
     *
     * @param eventName The event name
     * @param params Optional parameters to attach to the event
     */
    fun trackEvent(eventName: String, params: Map<String, Any> = emptyMap()) {
        analytics.logEvent(eventName) {
            params.forEach { (key, value) ->
                when (value) {
                    is String -> param(key, value)
                    is Int -> param(key, value.toLong())
                    is Long -> param(key, value)
                    is Double -> param(key, value)
                    is Boolean -> param(key, if (value) "true" else "false")
                    else -> param(key, value.toString())
                }
            }
        }
    }

    // ===============================================================
    // SCREEN VIEW EVENTS
    // ===============================================================

    /**
     * Track screen view. Call this on every screen appear.
     *
     * @param screenName The screen identifier (e.g., "home", "rooms", "login")
     * @param screenClass The screen class name for Firebase
     */
    fun trackScreenView(screenName: String, screenClass: String? = null) {
        analytics.logEvent(FirebaseAnalytics.Event.SCREEN_VIEW) {
            param(FirebaseAnalytics.Param.SCREEN_NAME, screenName)
            screenClass?.let { param(FirebaseAnalytics.Param.SCREEN_CLASS, it) }
        }
    }

    /**
     * Track navigation event between screens.
     */
    fun trackNavigation(fromScreen: String, toScreen: String, trigger: String = "tap") {
        analytics.logEvent("navigate") {
            param("from_screen", fromScreen)
            param("to_screen", toScreen)
            param("trigger", trigger)
        }
    }

    // ===============================================================
    // USER ACTION EVENTS
    // ===============================================================

    /**
     * Track button tap or user action.
     *
     * @param actionName The action identifier (e.g., "lights_on", "refresh_rooms")
     * @param context Additional context (screen, component, etc.)
     */
    fun trackAction(actionName: String, context: Map<String, String> = emptyMap()) {
        analytics.logEvent("user_action") {
            param("action_name", actionName)
            context.forEach { (key, value) ->
                param(key, value)
            }
        }
    }

    /**
     * Track quick action usage from home screen.
     */
    fun trackQuickAction(action: String) {
        analytics.logEvent("quick_action") {
            param("action", action)
            param("source", "home_screen")
        }
    }

    /**
     * Track hero action (context-aware main action) activation.
     */
    fun trackHeroAction(action: String, timeOfDay: String) {
        analytics.logEvent("hero_action") {
            param("action", action)
            param("time_of_day", timeOfDay)
        }
    }

    // ═══════════════════════════════════════════════════════════
    // SCENE EVENTS
    // ═══════════════════════════════════════════════════════════

    /**
     * Track scene activation.
     *
     * @param sceneName The scene identifier (e.g., "movie_mode", "goodnight")
     * @param source How the scene was activated (app, widget, shortcut, assistant, wear)
     */
    fun trackSceneActivated(sceneName: String, source: ActivationSource) {
        analytics.logEvent("scene_activated") {
            param("scene_name", sceneName)
            param("activation_source", source.name.lowercase())
        }
    }

    // ═══════════════════════════════════════════════════════════
    // ROOM EVENTS
    // ═══════════════════════════════════════════════════════════

    /**
     * Track room view.
     */
    fun trackRoomViewed(roomName: String) {
        analytics.logEvent("room_viewed") {
            param("room_name", roomName)
        }
    }

    /**
     * Track light adjustment.
     *
     * @param roomName The room where lights were adjusted
     * @param level The brightness level (0-100)
     */
    fun trackLightAdjusted(roomName: String, level: Int) {
        analytics.logEvent("light_adjusted") {
            param("room_name", roomName)
            param("brightness_level", level.toLong())
        }
    }

    /**
     * Track device toggled (lights, shades, etc).
     */
    fun trackDeviceToggled(roomName: String, deviceType: String, isOn: Boolean) {
        analytics.logEvent("device_toggled") {
            param("room_name", roomName)
            param("device_type", deviceType)
            param("is_on", if (isOn) "true" else "false")
        }
    }

    // ═══════════════════════════════════════════════════════════
    // DEVICE-SPECIFIC ACTIONS
    // ═══════════════════════════════════════════════════════════

    /**
     * Track shade control action.
     *
     * @param roomName The room where shades were controlled (optional, for "all")
     * @param action The action performed (open, close, position)
     * @param position The shade position (0-100), null for open/close
     */
    fun trackShadeAction(roomName: String?, action: String, position: Int? = null) {
        analytics.logEvent("shade_action") {
            roomName?.let { param("room_name", it) }
            param("action", action)
            position?.let { param("position", it.toLong()) }
        }
    }

    /**
     * Track fireplace control action.
     *
     * CBF Safety: Fireplace has safety constraints - track all toggles for audit.
     *
     * @param isOn Whether fireplace was turned on or off
     * @param source The source of the action (app, widget, voice, etc.)
     */
    fun trackFireplaceAction(isOn: Boolean, source: ActivationSource = ActivationSource.APP) {
        analytics.logEvent("fireplace_action") {
            param("is_on", if (isOn) "true" else "false")
            param("source", source.name.lowercase())
        }
    }

    /**
     * Track TV mount control action.
     *
     * @param action The action performed (lower, raise)
     * @param preset The preset used (1, 2, etc.), null for raise
     */
    fun trackTVMountAction(action: String, preset: Int? = null) {
        analytics.logEvent("tv_mount_action") {
            param("action", action)
            preset?.let { param("preset", it.toLong()) }
        }
    }

    /**
     * Track door lock action.
     *
     * CBF Safety: Lock state changes are audited for security.
     *
     * @param lockName The lock identifier (front_door, garage, etc.)
     * @param isLocked Whether the lock was locked or unlocked
     * @param source The source of the action
     */
    fun trackLockAction(lockName: String, isLocked: Boolean, source: ActivationSource = ActivationSource.APP) {
        analytics.logEvent("lock_action") {
            param("lock_name", lockName)
            param("is_locked", if (isLocked) "true" else "false")
            param("source", source.name.lowercase())
        }
    }

    /**
     * Track climate/thermostat control action.
     *
     * @param roomName The room or zone being controlled
     * @param targetTemp The target temperature in Fahrenheit
     * @param mode The HVAC mode (heat, cool, auto, off)
     */
    fun trackClimateAction(roomName: String, targetTemp: Int, mode: String? = null) {
        analytics.logEvent("climate_action") {
            param("room_name", roomName)
            param("target_temp", targetTemp.toLong())
            mode?.let { param("mode", it) }
        }
    }

    /**
     * Track audio/speaker control action.
     *
     * @param zone The audio zone name
     * @param action The action (play, pause, volume, source)
     * @param volume The volume level (0-100), if applicable
     */
    fun trackAudioAction(zone: String, action: String, volume: Int? = null) {
        analytics.logEvent("audio_action") {
            param("zone", zone)
            param("action", action)
            volume?.let { param("volume", it.toLong()) }
        }
    }

    // ═══════════════════════════════════════════════════════════
    // WIDGET EVENTS
    // ═══════════════════════════════════════════════════════════

    /**
     * Track widget added to home screen.
     */
    fun trackWidgetAdded(widgetType: WidgetType) {
        analytics.logEvent("widget_added") {
            param("widget_type", widgetType.name.lowercase())
        }
    }

    /**
     * Track widget interaction.
     */
    fun trackWidgetInteraction(widgetType: WidgetType, action: String) {
        analytics.logEvent("widget_interaction") {
            param("widget_type", widgetType.name.lowercase())
            param("action", action)
        }
    }

    // ═══════════════════════════════════════════════════════════
    // WEAR OS EVENTS
    // ═══════════════════════════════════════════════════════════

    /**
     * Track Wear OS sync status.
     */
    fun trackWearSync(isConnected: Boolean, deviceName: String?) {
        analytics.logEvent("wear_sync") {
            param("is_connected", if (isConnected) "true" else "false")
            deviceName?.let { param("device_name", it) }
        }
    }

    /**
     * Track Wear OS tile added.
     */
    fun trackWearTileAdded() {
        analytics.logEvent("wear_tile_added") { }
    }

    /**
     * Track Wear OS complication added.
     */
    fun trackWearComplicationAdded(complicationType: String) {
        analytics.logEvent("wear_complication_added") {
            param("complication_type", complicationType)
        }
    }

    // ═══════════════════════════════════════════════════════════
    // VOICE & ASSISTANT EVENTS
    // ═══════════════════════════════════════════════════════════

    /**
     * Track voice command via Google Assistant.
     */
    fun trackAssistantCommand(intentName: String, feature: String?) {
        analytics.logEvent("assistant_command") {
            param("intent_name", intentName)
            feature?.let { param("feature", it) }
        }
    }

    /**
     * Track app shortcut used.
     */
    fun trackShortcutUsed(shortcutId: String) {
        analytics.logEvent("shortcut_used") {
            param("shortcut_id", shortcutId)
        }
    }

    /**
     * Track deep link opened.
     */
    fun trackDeepLinkOpened(deepLinkUri: String) {
        analytics.logEvent("deep_link_opened") {
            param("deep_link_uri", deepLinkUri)
        }
    }

    // ═══════════════════════════════════════════════════════════
    // ONBOARDING & USER JOURNEY
    // ═══════════════════════════════════════════════════════════

    /**
     * Track onboarding step completion.
     */
    fun trackOnboardingStep(stepNumber: Int, stepName: String) {
        analytics.logEvent("onboarding_step") {
            param("step_number", stepNumber.toLong())
            param("step_name", stepName)
        }
    }

    /**
     * Track onboarding completion.
     */
    fun trackOnboardingComplete() {
        analytics.logEvent("onboarding_complete") { }
    }

    /**
     * Track server connection.
     */
    fun trackServerConnected(serverUrl: String) {
        // Hash the server URL for privacy
        val hashedUrl = serverUrl.hashCode().toString()
        analytics.logEvent("server_connected") {
            param("server_hash", hashedUrl)
        }
    }

    // ═══════════════════════════════════════════════════════════
    // ERROR TRACKING
    // ═══════════════════════════════════════════════════════════

    /**
     * Track non-fatal error for debugging.
     *
     * @param errorType Category of error (network, validation, api, etc.)
     * @param errorMessage Brief description of the error
     * @param screen The screen where error occurred
     * @param action The action that triggered the error
     */
    fun trackError(
        errorType: String,
        errorMessage: String,
        screen: String? = null,
        action: String? = null
    ) {
        analytics.logEvent("app_error") {
            param("error_type", errorType)
            param("error_message", errorMessage.take(100)) // Limit message length
            screen?.let { param("screen", it) }
            action?.let { param("action", it) }
        }
    }

    /**
     * Track API error with status code.
     */
    fun trackApiError(endpoint: String, statusCode: Int, errorMessage: String) {
        analytics.logEvent("api_error") {
            param("endpoint", endpoint.take(50))
            param("status_code", statusCode.toLong())
            param("error_message", errorMessage.take(100))
        }
    }

    /**
     * Track network connectivity error.
     */
    fun trackNetworkError(action: String, errorType: String) {
        analytics.logEvent("network_error") {
            param("action", action)
            param("error_type", errorType)
        }
    }

    // ═══════════════════════════════════════════════════════════
    // PERFORMANCE TRACKING
    // ═══════════════════════════════════════════════════════════

    /**
     * Track API request latency.
     */
    fun trackApiLatency(endpoint: String, latencyMs: Long, success: Boolean) {
        analytics.logEvent("api_latency") {
            param("endpoint", endpoint.take(50))
            param("latency_ms", latencyMs)
            param("success", if (success) "true" else "false")
        }
    }

    /**
     * Track app launch time.
     */
    fun trackAppLaunch(coldStart: Boolean, launchTimeMs: Long) {
        analytics.logEvent("app_launch") {
            param("cold_start", if (coldStart) "true" else "false")
            param("launch_time_ms", launchTimeMs)
        }
    }

    // ═══════════════════════════════════════════════════════════
    // LOGIN / AUTH EVENTS
    // ═══════════════════════════════════════════════════════════

    /**
     * Track login attempt.
     */
    fun trackLoginAttempt(method: String = "password") {
        analytics.logEvent(FirebaseAnalytics.Event.LOGIN) {
            param(FirebaseAnalytics.Param.METHOD, method)
        }
    }

    /**
     * Track login success.
     */
    fun trackLoginSuccess(method: String = "password") {
        analytics.logEvent("login_success") {
            param("method", method)
        }
    }

    /**
     * Track login failure.
     */
    fun trackLoginFailure(reason: String) {
        analytics.logEvent("login_failure") {
            param("reason", reason.take(50))
        }
    }

    /**
     * Track logout.
     */
    fun trackLogout() {
        analytics.logEvent("logout") { }
    }

    // ═══════════════════════════════════════════════════════════
    // VOICE COMMAND EVENTS
    // ═══════════════════════════════════════════════════════════

    /**
     * Track in-app voice command start.
     */
    fun trackVoiceCommandStart() {
        analytics.logEvent("voice_command_start") { }
    }

    /**
     * Track in-app voice command result.
     */
    fun trackVoiceCommandResult(success: Boolean, command: String?) {
        analytics.logEvent("voice_command_result") {
            param("success", if (success) "true" else "false")
            command?.let { param("command", it.take(50)) }
        }
    }

    // ═══════════════════════════════════════════════════════════
    // USER PROPERTIES
    // ═══════════════════════════════════════════════════════════

    /**
     * Set user property for segmentation.
     */
    fun setUserProperty(name: String, value: String) {
        analytics.setUserProperty(name, value)
    }

    /**
     * Set number of rooms configured.
     */
    fun setRoomCount(count: Int) {
        setUserProperty("room_count", count.toString())
    }

    /**
     * Set number of scenes configured.
     */
    fun setSceneCount(count: Int) {
        setUserProperty("scene_count", count.toString())
    }

    /**
     * Set whether user has Wear OS connected.
     */
    fun setHasWearOS(hasWear: Boolean) {
        setUserProperty("has_wear_os", if (hasWear) "true" else "false")
    }

    // ═══════════════════════════════════════════════════════════
    // PRIVACY CONTROLS
    // ═══════════════════════════════════════════════════════════

    /**
     * Enable or disable analytics collection.
     */
    fun setAnalyticsEnabled(enabled: Boolean) {
        analytics.setAnalyticsCollectionEnabled(enabled)
    }
}

/**
 * Source of scene activation.
 */
enum class ActivationSource {
    APP,        // Main phone app
    WIDGET,     // Home screen widget
    SHORTCUT,   // App shortcut (long-press launcher)
    ASSISTANT,  // Google Assistant voice command
    WEAR,       // Wear OS watch
    DEEP_LINK,  // URL deep link
    NOTIFICATION // Push notification action
}

/**
 * Widget types for analytics.
 */
enum class WidgetType {
    SAFETY,         // h(x) safety score widget
    QUICK_ACTIONS,  // Scene buttons widget
    ROOM_CONTROL    // Per-room control widget
}
