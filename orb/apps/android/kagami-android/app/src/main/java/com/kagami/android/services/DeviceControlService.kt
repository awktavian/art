/**
 * Device Control Service - Smart Home Device Management
 *
 * Colony: Nexus (e4) - Integration
 *
 * Controls individual smart home devices:
 * - Lights (level, room-specific)
 * - TV (raise, lower, mount controls)
 * - Fireplace (on/off with safety checks)
 * - Shades (open/close, room-specific)
 *
 * Architecture:
 *   DeviceControlService -> MeshCommandRouter (primary) -> Hub via Mesh
 *                        -> HTTP Client (fallback) -> HTTP Backend
 *
 * Migration Note (Jan 2026):
 *   Commands now route through MeshCommandRouter with Ed25519 signatures.
 *   HTTP fallback is maintained for backward compatibility during migration.
 *
 * h(x) >= 0. Always.
 */

package com.kagami.android.services

import android.util.Log
import com.kagami.android.data.Result
import com.kagami.android.network.ApiConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import javax.inject.Inject
import javax.inject.Named
import javax.inject.Singleton

// RoomModel, Light, and Shade are imported from KagamiTypes.kt
// No duplicate definitions needed here.

/**
 * Service for controlling smart home devices.
 *
 * Uses mesh routing as primary with HTTP fallback.
 */
@Singleton
class DeviceControlService @Inject constructor(
    @Named("api") private val client: OkHttpClient,
    private val apiConfig: ApiConfig,
    private val authManager: AuthManager,
    private val meshRouter: MeshCommandRouter
) {

    companion object {
        private const val TAG = "DeviceControlService"
        private val JSON_MEDIA_TYPE = "application/json".toMediaType()
    }

    // Whether mesh routing is active (vs HTTP fallback)
    private val _usingMeshRouting = MutableStateFlow(false)
    val usingMeshRouting: StateFlow<Boolean> = _usingMeshRouting

    /**
     * Initialize mesh routing (call on app startup).
     */
    suspend fun initializeMesh() {
        val result = meshRouter.initialize()
        _usingMeshRouting.value = result is Result.Success
        Log.i(TAG, "Mesh routing ${if (_usingMeshRouting.value) "enabled" else "disabled (using HTTP fallback)"}")
    }

    // ==================== Lights ====================

    /**
     * Set light level globally or for specific rooms.
     *
     * @param level Light level (0-100)
     * @param rooms Optional list of room IDs to control
     */
    suspend fun setLights(level: Int, rooms: List<String>? = null): Result<Boolean> =
        withContext(Dispatchers.IO) {
            val clampedLevel = level.coerceIn(0, 100)

            // Primary: Mesh routing with Ed25519 signature
            val result = meshRouter.executeWithFallback(
                MeshCommand.SetLights(clampedLevel, rooms)
            ) {
                // Fallback: Legacy HTTP (deprecated)
                val body = JSONObject().apply {
                    put("level", clampedLevel)
                    rooms?.let { put("rooms", it) }
                }
                postRequest(ApiConfig.Companion.Endpoints.LIGHTS_SET, body)
            }

            val routeType = if (meshRouter.connectedHubs.value.isNotEmpty()) "Mesh" else "HTTP"
            Log.d(TAG, "Set lights to $clampedLevel% via $routeType - ${if (result is Result.Success) "success" else "failed"}")

            result
        }

    // ==================== TV ====================

    /**
     * Control TV mount.
     *
     * @param action "lower" or "raise"
     */
    suspend fun tvControl(action: String): Result<Boolean> = withContext(Dispatchers.IO) {
        // Primary: Mesh routing with Ed25519 signature
        val result = meshRouter.executeWithFallback(
            MeshCommand.TvControl(action)
        ) {
            // Fallback: Legacy HTTP (deprecated)
            val endpoint = "${ApiConfig.Companion.Endpoints.TV_CONTROL}/$action"
            postRequest(endpoint)
        }

        val routeType = if (meshRouter.connectedHubs.value.isNotEmpty()) "Mesh" else "HTTP"
        Log.d(TAG, "TV $action via $routeType - ${if (result is Result.Success) "success" else "failed"}")

        result
    }

    /**
     * Lower TV to viewing position.
     */
    suspend fun lowerTv(): Result<Boolean> = tvControl("lower")

    /**
     * Raise TV to hidden position.
     */
    suspend fun raiseTv(): Result<Boolean> = tvControl("raise")

    // ==================== Fireplace ====================

    /**
     * Toggle fireplace.
     *
     * @param on True to turn on, false to turn off
     */
    suspend fun toggleFireplace(on: Boolean): Result<Boolean> = withContext(Dispatchers.IO) {
        // Primary: Mesh routing with Ed25519 signature
        val result = meshRouter.executeWithFallback(
            MeshCommand.Fireplace(on)
        ) {
            // Fallback: Legacy HTTP (deprecated)
            val endpoint = if (on) {
                ApiConfig.Companion.Endpoints.FIREPLACE_ON
            } else {
                ApiConfig.Companion.Endpoints.FIREPLACE_OFF
            }
            postRequest(endpoint)
        }

        val routeType = if (meshRouter.connectedHubs.value.isNotEmpty()) "Mesh" else "HTTP"
        Log.d(TAG, "Fireplace ${if (on) "on" else "off"} via $routeType - ${if (result is Result.Success) "success" else "failed"}")

        result
    }

    /**
     * Turn fireplace on.
     */
    suspend fun fireplaceOn(): Result<Boolean> = toggleFireplace(true)

    /**
     * Turn fireplace off.
     */
    suspend fun fireplaceOff(): Result<Boolean> = toggleFireplace(false)

    // ==================== Shades ====================

    /**
     * Control shades.
     *
     * @param action "open" or "close"
     * @param rooms Optional list of room IDs to control
     */
    suspend fun controlShades(action: String, rooms: List<String>? = null): Result<Boolean> =
        withContext(Dispatchers.IO) {
            // Primary: Mesh routing with Ed25519 signature
            val result = meshRouter.executeWithFallback(
                MeshCommand.Shades(action, rooms)
            ) {
                // Fallback: Legacy HTTP (deprecated)
                val body = JSONObject().apply {
                    rooms?.let { put("rooms", it) }
                }
                val endpoint = "${ApiConfig.Companion.Endpoints.SHADES_CONTROL}/$action"
                postRequest(endpoint, body)
            }

            val routeType = if (meshRouter.connectedHubs.value.isNotEmpty()) "Mesh" else "HTTP"
            Log.d(TAG, "Shades $action via $routeType - ${if (result is Result.Success) "success" else "failed"}")

            result
        }

    /**
     * Open shades.
     */
    suspend fun openShades(rooms: List<String>? = null): Result<Boolean> =
        controlShades("open", rooms)

    /**
     * Close shades.
     */
    suspend fun closeShades(rooms: List<String>? = null): Result<Boolean> =
        controlShades("close", rooms)

    // ==================== Audio ====================

    /**
     * Announce a message through the home audio system.
     */
    suspend fun announce(message: String, rooms: List<String>? = null): Result<Boolean> =
        withContext(Dispatchers.IO) {
            // Primary: Mesh routing with Ed25519 signature
            val result = meshRouter.executeWithFallback(
                MeshCommand.Announce(message, rooms)
            ) {
                // Fallback: Legacy HTTP (deprecated)
                try {
                    val body = JSONObject().apply {
                        put("message", message)
                        rooms?.let { put("rooms", JSONArray(it)) }
                    }
                    postRequest("/home/announce", body)
                } catch (e: Exception) {
                    Log.e(TAG, "Failed to announce", e)
                    Result.Error(e)
                }
            }

            result
        }

    // ==================== Rooms ====================

    /**
     * Fetch all rooms with their devices.
     */
    suspend fun fetchRooms(): Result<List<RoomModel>> = withContext(Dispatchers.IO) {
        try {
            val requestBuilder = Request.Builder()
                .url(apiConfig.buildUrl(ApiConfig.Companion.Endpoints.ROOMS))
                .get()

            authManager.getAccessToken()?.let { token ->
                requestBuilder.addHeader("Authorization", "Bearer $token")
            }

            val response = client.newCall(requestBuilder.build()).execute()

            if (response.isSuccessful) {
                val body = response.body?.string()
                val json = JSONObject(body ?: "{}")
                val roomsArray = json.optJSONArray("rooms")
                    ?: return@withContext Result.success(emptyList())

                val rooms = mutableListOf<RoomModel>()
                for (i in 0 until roomsArray.length()) {
                    val roomJson = roomsArray.getJSONObject(i)
                    rooms.add(parseRoom(roomJson))
                }
                Result.success(rooms)
            } else {
                Result.error("Failed to fetch rooms: ${response.code}", response.code)
            }
        } catch (e: java.net.SocketTimeoutException) {
            Result.error("Connection timed out", 0)
        } catch (e: java.net.UnknownHostException) {
            Result.error("Network unavailable - check your connection", 0)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to fetch rooms", e)
            Result.error(e)
        }
    }

    /**
     * Get rooms for widget display.
     */
    suspend fun getRooms(): Result<List<RoomModel>> = fetchRooms()

    private fun parseRoom(roomJson: JSONObject): RoomModel {
        val lights = mutableListOf<Light>()
        val shades = mutableListOf<Shade>()

        roomJson.optJSONArray("lights")?.let { lightsArray ->
            for (j in 0 until lightsArray.length()) {
                val lightJson = lightsArray.getJSONObject(j)
                lights.add(
                    Light(
                        id = lightJson.optInt("id"),
                        name = lightJson.optString("name"),
                        level = lightJson.optInt("level")
                    )
                )
            }
        }

        roomJson.optJSONArray("shades")?.let { shadesArray ->
            for (j in 0 until shadesArray.length()) {
                val shadeJson = shadesArray.getJSONObject(j)
                shades.add(
                    Shade(
                        id = shadeJson.optInt("id"),
                        name = shadeJson.optString("name"),
                        position = shadeJson.optInt("position")
                    )
                )
            }
        }

        return RoomModel(
            id = roomJson.optString("id"),
            name = roomJson.optString("name"),
            floor = roomJson.optString("floor"),
            lights = lights,
            shades = shades,
            occupied = roomJson.optBoolean("occupied", false)
        )
    }

    // ==================== Network Helpers ====================

    private suspend fun postRequest(endpoint: String, body: JSONObject? = null): Result<Boolean> =
        withContext(Dispatchers.IO) {
            try {
                val requestBody = (body?.toString() ?: "{}").toRequestBody(JSON_MEDIA_TYPE)
                val requestBuilder = Request.Builder()
                    .url(apiConfig.buildUrl(endpoint))
                    .post(requestBody)

                authManager.getAccessToken()?.let { token ->
                    requestBuilder.addHeader("Authorization", "Bearer $token")
                }

                val response = client.newCall(requestBuilder.build()).execute()

                if (response.isSuccessful) {
                    Result.success(true)
                } else {
                    Result.error("Request failed with code ${response.code}", response.code)
                }
            } catch (e: java.net.SocketTimeoutException) {
                Result.error("Connection timed out", 0)
            } catch (e: java.net.UnknownHostException) {
                Result.error("Network unavailable - check your connection", 0)
            } catch (e: Exception) {
                Log.e(TAG, "Request failed: $endpoint", e)
                Result.error(e)
            }
        }
}

/*
 * Mirror
 * h(x) >= 0. Always.
 */
