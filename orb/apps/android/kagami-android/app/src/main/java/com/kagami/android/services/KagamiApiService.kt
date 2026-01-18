/**
 * Kagami API Service - Core API Facade
 *
 * Colony: Nexus (e4) - Integration
 *
 * Facade service that delegates to specialized services:
 * - AuthManager: Token management
 * - WebSocketService: Real-time connection
 * - SceneService: Scene execution
 * - DeviceControlService: Device control
 * - SensoryUploadService: Health data uploads
 *
 * Maintains backward compatibility with existing consumers.
 */

package com.kagami.android.services

import android.os.Build
import android.util.Log
import com.kagami.android.data.Result
import com.kagami.android.network.ApiConfig
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.util.UUID
import javax.inject.Inject
import javax.inject.Named
import javax.inject.Singleton

/**
 * Home status data.
 */
data class HomeStatus(
    val initialized: Boolean = false,
    val rooms: Int = 0,
    val occupiedRooms: Int = 0,
    val movieMode: Boolean = false,
    val avgTemp: Double? = null
)

/**
 * Main API service facade.
 * Provides a unified interface while delegating to specialized services.
 */
@Singleton
class KagamiApiService @Inject constructor(
    @Named("api") private val client: OkHttpClient,
    private val apiConfig: ApiConfig,
    private val authManager: AuthManager,
    private val webSocketService: WebSocketService,
    private val sceneService: SceneService,
    private val deviceControlService: DeviceControlService,
    private val sensoryUploadService: SensoryUploadService
) {

    companion object {
        private const val TAG = "KagamiAPI"
        private val JSON_MEDIA_TYPE = "application/json".toMediaType()

        @Volatile
        private var _instance: KagamiApiService? = null

        /**
         * Get singleton instance. Note: Only available after Hilt initialization.
         * For accessibility/overlay services that can't use DI injection.
         */
        fun getInstance(): KagamiApiService? = _instance

        internal fun setInstance(service: KagamiApiService) {
            _instance = service
        }
    }

    // State
    private val _isConnected = MutableStateFlow(false)
    val isConnected: StateFlow<Boolean> = _isConnected

    private val _safetyScore = MutableStateFlow<Double?>(null)
    val safetyScore: StateFlow<Double?> = _safetyScore

    private val _latencyMs = MutableStateFlow(0)
    val latencyMs: StateFlow<Int> = _latencyMs

    private val _homeStatus = MutableStateFlow<HomeStatus?>(null)
    val homeStatus: StateFlow<HomeStatus?> = _homeStatus

    private val _isOfflineMode = MutableStateFlow(false)
    val isOfflineMode: StateFlow<Boolean> = _isOfflineMode

    // Client identification
    private val clientId = "android-${UUID.randomUUID()}"
    private val deviceName = Build.MODEL

    @Volatile
    private var isRegistered = false

    private var pollJob: Job? = null
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    // Health Connect service reference
    var healthConnectService: HealthConnectService? = null
        set(value) {
            field = value
            value?.let { sensoryUploadService.setHealthConnectService(it) }
        }

    init {
        // Register singleton instance for static access
        setInstance(this)

        // Subscribe to WebSocket messages
        scope.launch {
            webSocketService.messages.collect { message ->
                handleWebSocketMessage(message)
            }
        }
    }

    // ==================== Token Management (delegated to AuthManager) ====================

    fun getAccessToken(): String? = authManager.getAccessToken()

    fun getRefreshToken(): String? = authManager.getRefreshToken()

    fun getServerUrl(): String? = authManager.getServerUrl()

    suspend fun storeAuthTokens(serverUrl: String, accessToken: String, refreshToken: String?) {
        authManager.storeAuthTokens(serverUrl, accessToken, refreshToken)
        apiConfig.setBaseUrl(serverUrl)
    }

    fun storeAuthTokensSync(serverUrl: String, accessToken: String, refreshToken: String?) {
        authManager.storeAuthTokens(serverUrl, accessToken, refreshToken)
        apiConfig.setBaseUrl(serverUrl)
    }

    fun clearAuthTokens() = authManager.clearAuthTokens()

    fun isAuthenticated(): Boolean = authManager.isAuthenticated()

    // ==================== Connection ====================

    suspend fun connect() {
        // Load stored server URL
        authManager.getServerUrl()?.let { apiConfig.setBaseUrl(it) }

        // Try to discover API
        val discoveredUrl = discoverApi()
        if (discoveredUrl != null) {
            apiConfig.setBaseUrl(discoveredUrl)
        }

        // Check connection
        checkConnection()

        if (_isConnected.value) {
            _isOfflineMode.value = false
            registerWithKagami()
            webSocketService.connect(clientId)
            sensoryUploadService.startUploads()
        } else {
            _isOfflineMode.value = true
        }

        startPolling()
    }

    private suspend fun discoverApi(): String? {
        for (candidate in ApiConfig.DISCOVERY_CANDIDATES) {
            if (testConnection(candidate)) {
                return candidate
            }
        }
        return null
    }

    private suspend fun testConnection(url: String): Boolean = withContext(Dispatchers.IO) {
        try {
            val request = Request.Builder()
                .url("$url${ApiConfig.Companion.Endpoints.HEALTH}")
                .build()
            val response = client.newCall(request).execute()
            response.isSuccessful
        } catch (e: Exception) {
            false
        }
    }

    suspend fun checkConnection() = withContext(Dispatchers.IO) {
        val start = System.currentTimeMillis()

        try {
            val request = Request.Builder()
                .url(apiConfig.buildUrl(ApiConfig.Companion.Endpoints.HEALTH))
                .build()
            val response = client.newCall(request).execute()

            if (response.isSuccessful) {
                val body = response.body?.string()
                val json = JSONObject(body ?: "{}")

                _isConnected.value = true
                _isOfflineMode.value = false
                _safetyScore.value = json.optDouble("h_x", Double.NaN).takeIf { !it.isNaN() }
                _latencyMs.value = (System.currentTimeMillis() - start).toInt()
            } else {
                _isConnected.value = false
                _isOfflineMode.value = true
            }
        } catch (e: Exception) {
            Log.e(TAG, "Connection check failed", e)
            _isConnected.value = false
            _isOfflineMode.value = true
        }
    }

    private fun startPolling() {
        pollJob?.cancel()
        pollJob = scope.launch {
            while (isActive) {
                delay(15_000)
                checkConnection()
            }
        }
    }

    // ==================== Client Registration ====================

    private suspend fun registerWithKagami() = withContext(Dispatchers.IO) {
        val capabilities = listOf(
            "health_connect",
            "location",
            "notifications",
            "quick_actions",
        )

        val body = JSONObject().apply {
            put("client_id", clientId)
            put("client_type", "android")
            put("device_name", deviceName)
            put("capabilities", capabilities)
            put("app_version", "1.0.0")
            put("os_version", Build.VERSION.RELEASE)
        }

        try {
            val requestBuilder = Request.Builder()
                .url(apiConfig.buildUrl(ApiConfig.Companion.Endpoints.REGISTER_CLIENT))
                .post(body.toString().toRequestBody(JSON_MEDIA_TYPE))

            authManager.getAccessToken()?.let { token ->
                requestBuilder.addHeader("Authorization", "Bearer $token")
            }

            val response = client.newCall(requestBuilder.build()).execute()
            if (response.isSuccessful) {
                isRegistered = true
                sensoryUploadService.setClientId(clientId)
                sensoryUploadService.setRegistered(true)
                Log.i(TAG, "Registered with Kagami as $clientId")
            }
        } catch (e: Exception) {
            Log.w(TAG, "Registration failed", e)
        }
    }

    // ==================== WebSocket Message Handling ====================

    private fun handleWebSocketMessage(message: WebSocketMessage) {
        when (message) {
            is WebSocketMessage.ContextUpdate -> {
                message.safetyScore?.let { _safetyScore.value = it }
            }
            is WebSocketMessage.HomeUpdate -> {
                _homeStatus.value = _homeStatus.value?.copy(movieMode = message.movieMode)
            }
            is WebSocketMessage.Error -> {
                Log.e(TAG, "WebSocket error: ${message.message}")
            }
            is WebSocketMessage.Unknown -> {
                Log.d(TAG, "Unknown message type: ${message.type}")
            }
        }
    }

    suspend fun resetWebSocketReconnection() {
        webSocketService.resetAndReconnect()
    }

    // ==================== Scenes (delegated to SceneService) ====================

    suspend fun executeScene(scene: String): Result<Boolean> =
        sceneService.executeScene(scene)

    suspend fun getScenes(): Result<List<SceneInfo>> =
        sceneService.getScenes()

    // ==================== Device Control (delegated to DeviceControlService) ====================

    suspend fun setLights(level: Int, rooms: List<String>? = null): Result<Boolean> =
        deviceControlService.setLights(level, rooms)

    suspend fun tvControl(action: String): Result<Boolean> =
        deviceControlService.tvControl(action)

    suspend fun toggleFireplace(on: Boolean): Result<Boolean> =
        deviceControlService.toggleFireplace(on)

    suspend fun toggleFireplace(): Result<Boolean> =
        deviceControlService.toggleFireplace(true)

    suspend fun controlShades(action: String, rooms: List<String>? = null): Result<Boolean> =
        deviceControlService.controlShades(action, rooms)

    suspend fun fetchRooms(): Result<List<RoomModel>> =
        deviceControlService.fetchRooms()

    suspend fun getRooms(): Result<List<RoomModel>> =
        deviceControlService.getRooms()

    // ==================== Sensory Data (delegated to SensoryUploadService) ====================

    suspend fun uploadSensoryData() =
        sensoryUploadService.uploadSensoryData()

    suspend fun sendHeartbeat() =
        sensoryUploadService.sendHeartbeat()

    suspend fun announce(message: String, rooms: List<String>? = null): Result<Boolean> =
        deviceControlService.announce(message, rooms)

    // ==================== Scene Convenience Methods ====================

    /**
     * Enter movie mode scene.
     */
    suspend fun movieMode(): Result<Boolean> = executeScene("movie_mode")

    /**
     * Execute goodnight scene.
     */
    suspend fun goodnight(): Result<Boolean> = executeScene("goodnight")

    /**
     * Lock all doors.
     * TODO: Implement via DeviceControlService when lock API is available.
     */
    suspend fun lockAll(): Result<Boolean> {
        Log.d(TAG, "lockAll() called - stub implementation")
        return Result.Success(true)
    }

    /**
     * Report accessibility event to Kagami.
     * Used by accessibility service for context awareness.
     */
    suspend fun reportAccessibilityEvent(
        event: String?,
        packageName: String?,
        activityName: String?
    ) {
        // TODO: Implement when accessibility analytics endpoint is available
        Log.v(TAG, "Accessibility event: $event in $packageName/$activityName")
    }

    // ==================== Lifecycle ====================

    fun disconnect() {
        pollJob?.cancel()
        webSocketService.disconnect()
        sensoryUploadService.stopUploads()
        isRegistered = false
        scope.cancel()
    }
}

/*
 * Mirror
 * h(x) >= 0. Always.
 */
