package com.kagami.wear.services

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.TimeUnit

// DataStore extension for caching
private val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "kagami_wear_cache")

/**
 * Kagami Wear API Service
 *
 * Colony: Nexus (e4) - Integration
 *
 * Simplified API client for Wear OS with:
 * - Short timeouts for watch
 * - Offline caching via DataStore
 * - Proper JSON serialization
 * - Room data fetching
 */
object KagamiWearApiService {

    private var baseUrl = "http://kagami.local:8001"
    private var appContext: Context? = null

    private val client = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(5, TimeUnit.SECONDS)
        .build()

    private val jsonMediaType = "application/json".toMediaType()

    // Cache keys
    private val KEY_CACHED_ROOMS = stringPreferencesKey("cached_rooms")
    private val KEY_CACHED_HEALTH = stringPreferencesKey("cached_health")
    private val KEY_SERVER_URL = stringPreferencesKey("server_url")

    data class HealthResponse(
        val status: String,
        val safetyScore: Double?,
        val isConnected: Boolean = true
    )

    data class Room(
        val id: String,
        val name: String,
        val lightLevel: Int,
        val isOccupied: Boolean
    )

    /**
     * Initialize with application context for DataStore
     */
    fun initialize(context: Context) {
        appContext = context.applicationContext
    }

    /**
     * Configure the API base URL
     */
    suspend fun configure(url: String) {
        baseUrl = url.trimEnd('/')
        appContext?.let { ctx ->
            ctx.dataStore.edit { prefs ->
                prefs[KEY_SERVER_URL] = baseUrl
            }
        }
    }

    /**
     * Get configured server URL
     */
    suspend fun getServerUrl(): String {
        return appContext?.let { ctx ->
            ctx.dataStore.data.map { prefs ->
                prefs[KEY_SERVER_URL] ?: baseUrl
            }.first()
        } ?: baseUrl
    }

    /**
     * Fetch health status with offline fallback
     */
    suspend fun fetchHealth(): HealthResponse = withContext(Dispatchers.IO) {
        try {
            val request = Request.Builder()
                .url("$baseUrl/health")
                .get()
                .build()

            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) {
                    throw Exception("Request failed: ${response.code}")
                }

                val body = response.body?.string() ?: "{}"
                val json = JSONObject(body)

                // Cache the response
                appContext?.dataStore?.edit { prefs ->
                    prefs[KEY_CACHED_HEALTH] = body
                }

                HealthResponse(
                    status = json.optString("status", "unknown"),
                    safetyScore = if (json.has("h_x")) json.getDouble("h_x") else 0.85,
                    isConnected = true
                )
            }
        } catch (e: Exception) {
            // Try to return cached data
            appContext?.let { ctx ->
                val cached = ctx.dataStore.data.map { prefs ->
                    prefs[KEY_CACHED_HEALTH]
                }.first()

                if (cached != null) {
                    val json = JSONObject(cached)
                    return@withContext HealthResponse(
                        status = json.optString("status", "unknown"),
                        safetyScore = if (json.has("h_x")) json.getDouble("h_x") else null,
                        isConnected = false
                    )
                }
            }
            HealthResponse(status = "offline", safetyScore = null, isConnected = false)
        }
    }

    /**
     * Fetch rooms from API
     */
    suspend fun fetchRooms(): List<Room> = withContext(Dispatchers.IO) {
        try {
            val request = Request.Builder()
                .url("$baseUrl/home/rooms")
                .get()
                .build()

            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) {
                    throw Exception("Request failed: ${response.code}")
                }

                val body = response.body?.string() ?: "[]"

                // Cache the response
                appContext?.dataStore?.edit { prefs ->
                    prefs[KEY_CACHED_ROOMS] = body
                }

                parseRoomsJson(body)
            }
        } catch (e: Exception) {
            // Try to return cached data
            appContext?.let { ctx ->
                val cached = ctx.dataStore.data.map { prefs ->
                    prefs[KEY_CACHED_ROOMS]
                }.first()

                if (cached != null) {
                    return@withContext parseRoomsJson(cached)
                }
            }
            // Return default rooms if no cache
            getDefaultRooms()
        }
    }

    private fun parseRoomsJson(json: String): List<Room> {
        val rooms = mutableListOf<Room>()
        try {
            val jsonArray = JSONArray(json)
            for (i in 0 until jsonArray.length()) {
                val roomObj = jsonArray.getJSONObject(i)
                rooms.add(
                    Room(
                        id = roomObj.optString("id", ""),
                        name = roomObj.optString("name", "Unknown Room"),
                        lightLevel = roomObj.optInt("light_level", 0),
                        isOccupied = roomObj.optBoolean("is_occupied", false)
                    )
                )
            }
        } catch (e: Exception) {
            return getDefaultRooms()
        }
        return rooms.ifEmpty { getDefaultRooms() }
    }

    private fun getDefaultRooms(): List<Room> = listOf(
        Room("57", "Living Room", 0, false),
        Room("59", "Kitchen", 0, false),
        Room("47", "Office", 0, false),
        Room("36", "Primary Bedroom", 0, false),
        Room("39", "Game Room", 0, false),
        Room("41", "Gym", 0, false)
    )

    /**
     * Execute a scene
     */
    suspend fun executeScene(sceneId: String): Boolean = withContext(Dispatchers.IO) {
        val endpoint = when (sceneId) {
            "movie_mode" -> "/home/movie-mode/enter"
            "goodnight" -> "/home/goodnight"
            "welcome_home" -> "/home/welcome-home"
            "away" -> "/home/away"
            "good_morning" -> "/home/welcome-home" // Reuse welcome home
            "focus" -> "/home/lights/set"
            "sleep" -> "/home/goodnight" // Reuse goodnight
            else -> return@withContext false
        }

        val body = if (sceneId == "focus") {
            // Properly serialize the JSON with JSONArray
            JSONObject().apply {
                put("level", 60)
                put("rooms", JSONArray().apply {
                    put("Office")
                })
            }.toString().toRequestBody(jsonMediaType)
        } else {
            "{}".toRequestBody(jsonMediaType)
        }

        val request = Request.Builder()
            .url("$baseUrl$endpoint")
            .post(body)
            .build()

        try {
            client.newCall(request).execute().use { response ->
                response.isSuccessful
            }
        } catch (e: Exception) {
            false
        }
    }

    /**
     * Set lights level with proper JSON serialization
     */
    suspend fun setLights(level: Int, rooms: List<String>? = null): Boolean = withContext(Dispatchers.IO) {
        val json = JSONObject().apply {
            put("level", level)
            rooms?.let {
                // Properly serialize rooms as JSONArray
                val roomsArray = JSONArray()
                it.forEach { room -> roomsArray.put(room) }
                put("rooms", roomsArray)
            }
        }

        val request = Request.Builder()
            .url("$baseUrl/home/lights/set")
            .post(json.toString().toRequestBody(jsonMediaType))
            .build()

        try {
            client.newCall(request).execute().use { response ->
                response.isSuccessful
            }
        } catch (e: Exception) {
            false
        }
    }

    /**
     * Control TV
     */
    suspend fun tvControl(action: String): Boolean = withContext(Dispatchers.IO) {
        val request = Request.Builder()
            .url("$baseUrl/home/tv/$action")
            .post("{}".toRequestBody(jsonMediaType))
            .build()

        try {
            client.newCall(request).execute().use { response ->
                response.isSuccessful
            }
        } catch (e: Exception) {
            false
        }
    }

    /**
     * Toggle fireplace
     */
    suspend fun toggleFireplace(on: Boolean): Boolean = withContext(Dispatchers.IO) {
        val endpoint = if (on) "/home/fireplace/on" else "/home/fireplace/off"

        val request = Request.Builder()
            .url("$baseUrl$endpoint")
            .post("{}".toRequestBody(jsonMediaType))
            .build()

        try {
            client.newCall(request).execute().use { response ->
                response.isSuccessful
            }
        } catch (e: Exception) {
            false
        }
    }

    /**
     * Test connection to server
     */
    suspend fun testConnection(): Boolean = withContext(Dispatchers.IO) {
        try {
            val request = Request.Builder()
                .url("$baseUrl/health")
                .get()
                .build()

            client.newCall(request).execute().use { response ->
                response.isSuccessful
            }
        } catch (e: Exception) {
            false
        }
    }
}
