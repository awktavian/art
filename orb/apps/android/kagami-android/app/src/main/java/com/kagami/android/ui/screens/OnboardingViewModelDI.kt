/**
 * Kagami Onboarding ViewModel - Proper DI with Hilt
 *
 * Colony: Beacon (e5) - Planning
 *
 * Follows Clean Architecture:
 * - Injected dependencies via Hilt
 * - StateFlow for reactive UI state
 * - Proper separation of concerns
 */

package com.kagami.android.ui.screens

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.content.ContextCompat
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.kagami.android.services.AnalyticsService
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.TimeUnit
import javax.inject.Inject

/**
 * Hilt-injectable ViewModel for Onboarding flow.
 *
 * Manages:
 * - Server discovery and connection testing
 * - Smart home integration setup
 * - Room configuration
 * - Permission management
 * - Progress persistence
 */
@HiltViewModel
class OnboardingViewModelDI @Inject constructor(
    private val analyticsService: AnalyticsService,
    @ApplicationContext private val appContext: Context
) : ViewModel() {

    private val _state = MutableStateFlow(OnboardingState())
    val state: StateFlow<OnboardingState> = _state.asStateFlow()

    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(10, TimeUnit.SECONDS)
        .build()

    companion object {
        private val JSON_MEDIA_TYPE = "application/json".toMediaType()
        private val DEFAULT_SERVERS = listOf(
            "http://kagami.local:8001",
            "http://192.168.1.100:8001",
            "http://192.168.1.50:8001",
            "http://10.0.0.100:8001"
        )
        const val PREFS_NAME = "kagami_onboarding"
        const val KEY_SERVER_URL = "server_url"
        const val KEY_CURRENT_PAGE = "current_page"
        const val KEY_INTEGRATION = "selected_integration"
        const val KEY_SELECTED_ROOMS = "selected_rooms"
    }

    init {
        // Load progress on initialization
        loadProgress()
    }

    fun trackScreenView(pageName: String) {
        analyticsService.trackScreenView("onboarding_$pageName", "OnboardingScreen")
    }

    private fun loadProgress() {
        val prefs = appContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val serverUrl = prefs.getString(KEY_SERVER_URL, "") ?: ""
        val currentPage = prefs.getInt(KEY_CURRENT_PAGE, 0)
        val integrationName = prefs.getString(KEY_INTEGRATION, null)
        val selectedRoomsJson = prefs.getString(KEY_SELECTED_ROOMS, "[]") ?: "[]"

        val selectedRooms = try {
            val array = JSONArray(selectedRoomsJson)
            (0 until array.length()).map { array.getString(it) }.toSet()
        } catch (e: Exception) {
            emptySet()
        }

        val integration = integrationName?.let {
            try { SmartHomeIntegration.valueOf(it) } catch (e: Exception) { null }
        }

        _state.value = _state.value.copy(
            serverUrl = serverUrl,
            currentPage = currentPage,
            selectedIntegration = integration,
            selectedRooms = selectedRooms,
            notificationPermissionGranted = checkNotificationPermission(),
            locationPermissionGranted = checkLocationPermission()
        )
    }

    fun saveProgress() {
        val prefs = appContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val currentState = _state.value

        prefs.edit()
            .putString(KEY_SERVER_URL, currentState.serverUrl)
            .putInt(KEY_CURRENT_PAGE, currentState.currentPage)
            .putString(KEY_INTEGRATION, currentState.selectedIntegration?.name)
            .putString(KEY_SELECTED_ROOMS, JSONArray(currentState.selectedRooms.toList()).toString())
            .apply()
    }

    fun clearProgress() {
        val prefs = appContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        prefs.edit().clear().apply()
    }

    private fun checkNotificationPermission(): Boolean {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            ContextCompat.checkSelfPermission(
                appContext,
                Manifest.permission.POST_NOTIFICATIONS
            ) == PackageManager.PERMISSION_GRANTED
        } else {
            true
        }
    }

    private fun checkLocationPermission(): Boolean {
        return ContextCompat.checkSelfPermission(
            appContext,
            Manifest.permission.ACCESS_FINE_LOCATION
        ) == PackageManager.PERMISSION_GRANTED
    }

    fun setPage(page: Int) {
        _state.value = _state.value.copy(currentPage = page)
        saveProgress()
    }

    fun updateServerUrl(url: String) {
        _state.value = _state.value.copy(
            serverUrl = url,
            connectionSuccess = null,
            connectionError = null
        )
    }

    fun discoverServers() {
        viewModelScope.launch {
            _state.value = _state.value.copy(isDiscovering = true, connectionError = null)

            val discovered = mutableListOf<String>()
            withContext(Dispatchers.IO) {
                for (candidate in DEFAULT_SERVERS) {
                    if (testConnection(candidate)) {
                        discovered.add(candidate)
                    }
                }
            }

            _state.value = _state.value.copy(
                isDiscovering = false,
                discoveredServers = discovered,
                connectionError = if (discovered.isEmpty()) "No Kagami servers found" else null
            )

            // Auto-select if only one found
            if (discovered.size == 1) {
                _state.value = _state.value.copy(serverUrl = discovered.first())
            }
        }
    }

    private fun testConnection(url: String): Boolean {
        return try {
            val request = Request.Builder().url("$url/health").build()
            val response = client.newCall(request).execute()
            response.isSuccessful
        } catch (e: Exception) {
            false
        }
    }

    fun testServerConnection() {
        val url = _state.value.serverUrl.trimEnd('/')
        if (url.isBlank()) {
            _state.value = _state.value.copy(connectionError = "Please enter a server URL")
            return
        }

        viewModelScope.launch {
            _state.value = _state.value.copy(
                isTestingConnection = true,
                connectionSuccess = null,
                connectionError = null
            )

            val success = withContext(Dispatchers.IO) { testConnection(url) }

            _state.value = _state.value.copy(
                isTestingConnection = false,
                connectionSuccess = success,
                connectionError = if (!success) "Could not connect to server" else null
            )

            if (success) {
                analyticsService.trackEvent("onboarding_server_connected", mapOf("url" to url))
            }
        }
    }

    fun selectIntegration(integration: SmartHomeIntegration?) {
        _state.value = _state.value.copy(
            selectedIntegration = integration,
            integrationCredentials = emptyMap(),
            integrationConnected = false,
            integrationError = null
        )
    }

    fun updateIntegrationCredential(key: String, value: String) {
        val current = _state.value.integrationCredentials.toMutableMap()
        current[key] = value
        _state.value = _state.value.copy(integrationCredentials = current)
    }

    fun connectIntegration() {
        val integration = _state.value.selectedIntegration ?: return
        val credentials = _state.value.integrationCredentials
        val serverUrl = _state.value.serverUrl.trimEnd('/')

        // Validate required fields
        val missingFields = integration.requiredFields.filter {
            credentials[it.key].isNullOrBlank()
        }
        if (missingFields.isNotEmpty()) {
            _state.value = _state.value.copy(
                integrationError = "Please fill in: ${missingFields.joinToString { it.label }}"
            )
            return
        }

        viewModelScope.launch {
            _state.value = _state.value.copy(
                isConnectingIntegration = true,
                integrationError = null
            )

            val result = withContext(Dispatchers.IO) {
                try {
                    val body = JSONObject().apply {
                        put("integration_type", integration.name.lowercase())
                        put("credentials", JSONObject(credentials))
                    }

                    val request = Request.Builder()
                        .url("$serverUrl/api/user/smart-home/connect")
                        .post(body.toString().toRequestBody(JSON_MEDIA_TYPE))
                        .build()

                    val response = client.newCall(request).execute()
                    if (response.isSuccessful) {
                        Result.success(Unit)
                    } else {
                        val errorBody = response.body?.string()
                        val errorJson = try { JSONObject(errorBody ?: "{}") } catch (e: Exception) { null }
                        val detail = errorJson?.optString("detail") ?: "Connection failed"
                        Result.failure(Exception(detail))
                    }
                } catch (e: Exception) {
                    Result.failure(e)
                }
            }

            result.fold(
                onSuccess = {
                    _state.value = _state.value.copy(
                        isConnectingIntegration = false,
                        integrationConnected = true
                    )
                    analyticsService.trackEvent("onboarding_integration_connected", mapOf(
                        "integration" to integration.name
                    ))
                    // Load rooms after successful connection
                    loadRooms()
                },
                onFailure = {
                    _state.value = _state.value.copy(
                        isConnectingIntegration = false,
                        integrationError = it.message ?: "Unknown error"
                    )
                }
            )
        }
    }

    fun loadRooms() {
        val serverUrl = _state.value.serverUrl.trimEnd('/')

        viewModelScope.launch {
            _state.value = _state.value.copy(isLoadingRooms = true)

            val rooms = withContext(Dispatchers.IO) {
                try {
                    val request = Request.Builder()
                        .url("$serverUrl/home/rooms")
                        .build()

                    val response = client.newCall(request).execute()
                    if (response.isSuccessful) {
                        val body = response.body?.string()
                        val json = JSONObject(body ?: "{}")
                        val roomsArray = json.optJSONArray("rooms") ?: JSONArray()

                        (0 until roomsArray.length()).map { i ->
                            val room = roomsArray.getJSONObject(i)
                            RoomConfig(
                                id = room.optString("id"),
                                name = room.optString("name"),
                                floor = room.optString("floor", "Main"),
                                hasLights = room.optJSONArray("lights")?.length() ?: 0 > 0,
                                hasShades = room.optJSONArray("shades")?.length() ?: 0 > 0,
                                hasClimate = room.has("thermostat")
                            )
                        }
                    } else {
                        emptyList()
                    }
                } catch (e: Exception) {
                    emptyList()
                }
            }

            _state.value = _state.value.copy(
                isLoadingRooms = false,
                availableRooms = rooms,
                selectedRooms = rooms.map { it.id }.toSet() // Select all by default
            )
        }
    }

    fun toggleRoom(roomId: String) {
        val current = _state.value.selectedRooms.toMutableSet()
        if (roomId in current) {
            current.remove(roomId)
        } else {
            current.add(roomId)
        }
        _state.value = _state.value.copy(selectedRooms = current)
    }

    fun selectAllRooms() {
        _state.value = _state.value.copy(
            selectedRooms = _state.value.availableRooms.map { it.id }.toSet()
        )
    }

    fun deselectAllRooms() {
        _state.value = _state.value.copy(selectedRooms = emptySet())
    }

    fun updateNotificationPermission(granted: Boolean) {
        _state.value = _state.value.copy(notificationPermissionGranted = granted)
    }

    fun updateLocationPermission(granted: Boolean) {
        _state.value = _state.value.copy(locationPermissionGranted = granted)
    }

    fun markComplete() {
        analyticsService.trackEvent("onboarding_completed", mapOf(
            "has_integration" to (_state.value.selectedIntegration != null).toString(),
            "rooms_count" to _state.value.selectedRooms.size.toString()
        ))
        clearProgress()
        _state.value = _state.value.copy(isComplete = true)
    }
}

/*
 * Mirror
 * h(x) >= 0. Always.
 */
