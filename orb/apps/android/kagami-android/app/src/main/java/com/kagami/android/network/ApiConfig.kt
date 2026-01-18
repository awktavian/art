/**
 * API Configuration - Centralized URL Management
 *
 * Colony: Nexus (e4) - Integration
 *
 * Single source of truth for all API endpoints and configuration.
 */

package com.kagami.android.network

import android.content.SharedPreferences
import javax.inject.Inject
import javax.inject.Named
import javax.inject.Singleton

/**
 * Centralized API configuration.
 * Manages base URLs and endpoint paths.
 */
@Singleton
class ApiConfig @Inject constructor(
    @Named("encrypted") private val encryptedPrefs: SharedPreferences
) {

    companion object {
        // Default server URL
        const val DEFAULT_BASE_URL = "http://kagami.local:8001"

        // Server discovery candidates (in order of preference)
        val DISCOVERY_CANDIDATES = listOf(
            "http://kagami.local:8001",
            "http://192.168.1.100:8001",
            "http://192.168.1.50:8001",
            "http://10.0.0.100:8001",
        )

        // Preferences key
        private const val KEY_SERVER_URL = "server_url"

        // API Endpoints
        object Endpoints {
            // Health
            const val HEALTH = "/health"

            // Authentication
            const val REGISTER_CLIENT = "/api/home/clients/register"

            // Home Control
            const val LIGHTS_SET = "/home/lights/set"
            const val TV_CONTROL = "/home/tv" // append action: /home/tv/{action}
            const val FIREPLACE_ON = "/home/fireplace/on"
            const val FIREPLACE_OFF = "/home/fireplace/off"
            const val SHADES_CONTROL = "/home/shades" // append action: /home/shades/{action}
            const val ROOMS = "/home/rooms"

            // Scenes
            const val MOVIE_MODE_ENTER = "/home/movie-mode/enter"
            const val MOVIE_MODE_EXIT = "/home/movie-mode/exit"
            const val GOODNIGHT = "/home/goodnight"
            const val WELCOME_HOME = "/home/welcome-home"
            const val AWAY = "/home/away"

            // Sensory Data
            fun clientSense(clientId: String) = "/api/home/clients/$clientId/sense"
            fun clientHeartbeat(clientId: String) = "/api/home/clients/$clientId/heartbeat"

            // Notifications
            const val NOTIFICATIONS_REGISTER = "/api/notifications/register"
            fun notificationDelivered(id: String) = "/api/notifications/mark-delivered/$id"
            fun notificationRead(id: String) = "/api/notifications/mark-read/$id"

            // Alerts
            fun acknowledgeAlert(id: String) = "/api/alerts/$id/acknowledge"

            // Routines
            fun executeRoutine(id: String) = "/api/routines/$id/execute"
            fun snoozeRoutine(id: String) = "/api/routines/$id/snooze"

            // Security
            const val SECURITY_ARM = "/api/security/arm"
            const val SECURITY_DISARM = "/api/security/disarm"
        }
    }

    /**
     * Current base URL. Defaults to stored URL or DEFAULT_BASE_URL.
     */
    @Volatile
    private var _baseUrl: String = encryptedPrefs.getString(KEY_SERVER_URL, null) ?: DEFAULT_BASE_URL

    val baseUrl: String
        get() = _baseUrl

    /**
     * WebSocket URL derived from base URL.
     */
    val wsBaseUrl: String
        get() = _baseUrl.replace("http://", "ws://").replace("https://", "wss://")

    /**
     * Update the base URL.
     */
    fun setBaseUrl(url: String) {
        _baseUrl = url
        encryptedPrefs.edit()
            .putString(KEY_SERVER_URL, url)
            .apply()
    }

    /**
     * Get stored server URL.
     */
    fun getStoredServerUrl(): String? = encryptedPrefs.getString(KEY_SERVER_URL, null)

    /**
     * Build a full URL from an endpoint path.
     */
    fun buildUrl(endpoint: String): String = "$_baseUrl$endpoint"

    /**
     * Build a full WebSocket URL from an endpoint path.
     */
    fun buildWsUrl(endpoint: String): String = "$wsBaseUrl$endpoint"

    /**
     * WebSocket client endpoint.
     */
    fun wsClientUrl(clientId: String): String = buildWsUrl("/ws/client/$clientId")
}

/*
 * Mirror
 * h(x) >= 0. Always.
 */
