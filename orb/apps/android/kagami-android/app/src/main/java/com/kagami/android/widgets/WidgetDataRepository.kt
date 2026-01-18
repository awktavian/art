/**
 * Widget Data Repository
 *
 * Colony: Nexus (e4) - Integration
 * h(x) >= 0. Always.
 *
 * Provides data synchronization for Kagami home screen widgets.
 * Uses DataStore for persistent widget state and WorkManager for background sync.
 *
 * Widget Types:
 * - SafetyWidget: Shows h(x) safety score status (green/yellow/red dot)
 * - QuickActionsWidget: Scene activation buttons
 * - RoomControlWidget: Per-room light/shade controls
 */

package com.kagami.android.widgets

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.*
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import java.io.IOException
import javax.inject.Inject
import javax.inject.Singleton

// DataStore extension
private val Context.widgetDataStore: DataStore<Preferences> by preferencesDataStore(
    name = "widget_data"
)

/**
 * Repository for widget data storage and retrieval.
 */
@Singleton
class WidgetDataRepository @Inject constructor(
    private val context: Context
) {
    // =============================================================
    // PREFERENCE KEYS
    // =============================================================

    private object Keys {
        // Safety widget data
        val SAFETY_SCORE = doublePreferencesKey("safety_score")
        val SAFETY_STATUS = stringPreferencesKey("safety_status")
        val LAST_SAFETY_UPDATE = longPreferencesKey("last_safety_update")

        // Connection state
        val IS_CONNECTED = booleanPreferencesKey("is_connected")
        val SERVER_URL = stringPreferencesKey("server_url")
        val LATENCY_MS = intPreferencesKey("latency_ms")

        // Quick actions widget
        val FAVORITE_SCENES = stringPreferencesKey("favorite_scenes")
        val LAST_SCENE_UPDATE = longPreferencesKey("last_scene_update")

        // Room control widget
        val CONFIGURED_ROOMS = stringPreferencesKey("configured_rooms")
        val ROOM_STATES = stringPreferencesKey("room_states")
        val LAST_ROOM_UPDATE = longPreferencesKey("last_room_update")

        // Widget configuration per instance
        fun widgetConfig(appWidgetId: Int) = stringPreferencesKey("widget_config_$appWidgetId")
    }

    // =============================================================
    // SAFETY DATA
    // =============================================================

    /**
     * Flow of current safety score.
     */
    val safetyScoreFlow: Flow<Double?> = context.widgetDataStore.data
        .catch { exception ->
            if (exception is IOException) {
                emit(emptyPreferences())
            } else {
                throw exception
            }
        }
        .map { preferences ->
            preferences[Keys.SAFETY_SCORE]
        }

    /**
     * Flow of safety status (ok, caution, violation).
     */
    val safetyStatusFlow: Flow<SafetyStatus> = context.widgetDataStore.data
        .catch { exception ->
            if (exception is IOException) {
                emit(emptyPreferences())
            } else {
                throw exception
            }
        }
        .map { preferences ->
            val statusString = preferences[Keys.SAFETY_STATUS] ?: "unknown"
            SafetyStatus.fromString(statusString)
        }

    /**
     * Get current safety data synchronously.
     * For use in widget update operations.
     */
    suspend fun getSafetyData(): SafetyData {
        val preferences = context.widgetDataStore.data.first()
        return SafetyData(
            score = preferences[Keys.SAFETY_SCORE],
            status = SafetyStatus.fromString(preferences[Keys.SAFETY_STATUS] ?: "unknown"),
            lastUpdate = preferences[Keys.LAST_SAFETY_UPDATE] ?: 0L,
            isConnected = preferences[Keys.IS_CONNECTED] ?: false,
            latencyMs = preferences[Keys.LATENCY_MS] ?: 0
        )
    }

    /**
     * Update safety data from API.
     */
    suspend fun updateSafetyData(score: Double?, status: SafetyStatus, isConnected: Boolean, latencyMs: Int) {
        context.widgetDataStore.edit { preferences ->
            score?.let { preferences[Keys.SAFETY_SCORE] = it }
            preferences[Keys.SAFETY_STATUS] = status.name.lowercase()
            preferences[Keys.LAST_SAFETY_UPDATE] = System.currentTimeMillis()
            preferences[Keys.IS_CONNECTED] = isConnected
            preferences[Keys.LATENCY_MS] = latencyMs
        }
    }

    // =============================================================
    // SCENE DATA
    // =============================================================

    /**
     * Flow of favorite scenes for quick actions widget.
     */
    val favoriteScenesFlow: Flow<List<SceneInfo>> = context.widgetDataStore.data
        .catch { exception ->
            if (exception is IOException) {
                emit(emptyPreferences())
            } else {
                throw exception
            }
        }
        .map { preferences ->
            val scenesJson = preferences[Keys.FAVORITE_SCENES] ?: "[]"
            parseScenes(scenesJson)
        }

    /**
     * Get favorite scenes synchronously.
     */
    suspend fun getFavoriteScenes(): List<SceneInfo> {
        val preferences = context.widgetDataStore.data.first()
        val scenesJson = preferences[Keys.FAVORITE_SCENES] ?: "[]"
        return parseScenes(scenesJson)
    }

    /**
     * Update favorite scenes.
     */
    suspend fun updateFavoriteScenes(scenes: List<SceneInfo>) {
        context.widgetDataStore.edit { preferences ->
            preferences[Keys.FAVORITE_SCENES] = serializeScenes(scenes)
            preferences[Keys.LAST_SCENE_UPDATE] = System.currentTimeMillis()
        }
    }

    // =============================================================
    // ROOM DATA
    // =============================================================

    /**
     * Flow of configured rooms for room control widgets.
     */
    val roomsFlow: Flow<List<RoomInfo>> = context.widgetDataStore.data
        .catch { exception ->
            if (exception is IOException) {
                emit(emptyPreferences())
            } else {
                throw exception
            }
        }
        .map { preferences ->
            val roomsJson = preferences[Keys.CONFIGURED_ROOMS] ?: "[]"
            parseRooms(roomsJson)
        }

    /**
     * Get rooms synchronously.
     */
    suspend fun getRooms(): List<RoomInfo> {
        val preferences = context.widgetDataStore.data.first()
        val roomsJson = preferences[Keys.CONFIGURED_ROOMS] ?: "[]"
        return parseRooms(roomsJson)
    }

    /**
     * Update room list and states.
     */
    suspend fun updateRooms(rooms: List<RoomInfo>) {
        context.widgetDataStore.edit { preferences ->
            preferences[Keys.CONFIGURED_ROOMS] = serializeRooms(rooms)
            preferences[Keys.LAST_ROOM_UPDATE] = System.currentTimeMillis()
        }
    }

    /**
     * Update state for a specific room.
     */
    suspend fun updateRoomState(roomId: String, lightLevel: Int?, shadesOpen: Boolean?) {
        val rooms = getRooms().toMutableList()
        val index = rooms.indexOfFirst { it.id == roomId }
        if (index >= 0) {
            rooms[index] = rooms[index].copy(
                lightLevel = lightLevel ?: rooms[index].lightLevel,
                shadesOpen = shadesOpen ?: rooms[index].shadesOpen
            )
            updateRooms(rooms)
        }
    }

    // =============================================================
    // WIDGET CONFIGURATION
    // =============================================================

    /**
     * Save widget-specific configuration.
     */
    suspend fun saveWidgetConfig(appWidgetId: Int, config: WidgetConfig) {
        context.widgetDataStore.edit { preferences ->
            preferences[Keys.widgetConfig(appWidgetId)] = config.serialize()
        }
    }

    /**
     * Get widget-specific configuration.
     */
    suspend fun getWidgetConfig(appWidgetId: Int): WidgetConfig? {
        val preferences = context.widgetDataStore.data.first()
        val configJson = preferences[Keys.widgetConfig(appWidgetId)] ?: return null
        return WidgetConfig.deserialize(configJson)
    }

    /**
     * Remove widget configuration (on widget delete).
     */
    suspend fun removeWidgetConfig(appWidgetId: Int) {
        context.widgetDataStore.edit { preferences ->
            preferences.remove(Keys.widgetConfig(appWidgetId))
        }
    }

    // =============================================================
    // CONNECTION STATE
    // =============================================================

    /**
     * Flow of connection state.
     */
    val isConnectedFlow: Flow<Boolean> = context.widgetDataStore.data
        .catch { exception ->
            if (exception is IOException) {
                emit(emptyPreferences())
            } else {
                throw exception
            }
        }
        .map { preferences ->
            preferences[Keys.IS_CONNECTED] ?: false
        }

    /**
     * Update server connection info.
     */
    suspend fun updateConnectionState(isConnected: Boolean, serverUrl: String?, latencyMs: Int) {
        context.widgetDataStore.edit { preferences ->
            preferences[Keys.IS_CONNECTED] = isConnected
            serverUrl?.let { preferences[Keys.SERVER_URL] = it }
            preferences[Keys.LATENCY_MS] = latencyMs
        }
    }

    // =============================================================
    // SERIALIZATION HELPERS
    // =============================================================

    private fun parseScenes(json: String): List<SceneInfo> {
        // Simple JSON parsing - in production, use Moshi/Gson
        if (json == "[]") return emptyList()
        return try {
            json.removeSurrounding("[", "]")
                .split("},{")
                .map { it.trim().removeSurrounding("{", "}") }
                .map { sceneJson ->
                    val parts = sceneJson.split(",").associate { part ->
                        val (key, value) = part.split(":").map { it.trim().removeSurrounding("\"") }
                        key to value
                    }
                    SceneInfo(
                        id = parts["id"] ?: "",
                        name = parts["name"] ?: "",
                        icon = parts["icon"] ?: "star"
                    )
                }
        } catch (e: Exception) {
            emptyList()
        }
    }

    private fun serializeScenes(scenes: List<SceneInfo>): String {
        return scenes.joinToString(",", "[", "]") { scene ->
            """{"id":"${scene.id}","name":"${scene.name}","icon":"${scene.icon}"}"""
        }
    }

    private fun parseRooms(json: String): List<RoomInfo> {
        if (json == "[]") return emptyList()
        return try {
            json.removeSurrounding("[", "]")
                .split("},{")
                .map { it.trim().removeSurrounding("{", "}") }
                .map { roomJson ->
                    val parts = roomJson.split(",").associate { part ->
                        val (key, value) = part.split(":").map { it.trim().removeSurrounding("\"") }
                        key to value
                    }
                    RoomInfo(
                        id = parts["id"] ?: "",
                        name = parts["name"] ?: "",
                        floor = parts["floor"] ?: "",
                        hasLights = parts["hasLights"]?.toBoolean() ?: false,
                        hasShades = parts["hasShades"]?.toBoolean() ?: false,
                        lightLevel = parts["lightLevel"]?.toIntOrNull() ?: 0,
                        shadesOpen = parts["shadesOpen"]?.toBoolean() ?: true
                    )
                }
        } catch (e: Exception) {
            emptyList()
        }
    }

    private fun serializeRooms(rooms: List<RoomInfo>): String {
        return rooms.joinToString(",", "[", "]") { room ->
            """{"id":"${room.id}","name":"${room.name}","floor":"${room.floor}","hasLights":${room.hasLights},"hasShades":${room.hasShades},"lightLevel":${room.lightLevel},"shadesOpen":${room.shadesOpen}}"""
        }
    }

    companion object {
        private const val TAG = "WidgetDataRepository"

        /**
         * Static refresh for backward compatibility with widgets.
         * Creates a temporary instance with the given context.
         */
        suspend fun refreshData(context: Context): KagamiWidgetData {
            // Convert new repository data to legacy format
            val repo = WidgetDataRepository(context)
            val safetyData = repo.getSafetyData()
            val rooms = repo.getRooms()

            return KagamiWidgetData(
                isConnected = safetyData.isConnected,
                safetyScore = safetyData.score,
                movieMode = false, // Not tracked in new repository
                rooms = rooms.map { room ->
                    WidgetRoomData(
                        id = room.id,
                        name = room.name,
                        avgLightLevel = room.lightLevel,
                        occupied = false // Not tracked
                    )
                },
                lastUpdate = safetyData.lastUpdate
            )
        }

        /**
         * Load cached data for backward compatibility.
         */
        fun loadCachedData(context: Context): KagamiWidgetData {
            // Return empty data synchronously - actual data fetched via suspend
            return KagamiWidgetData()
        }

        /**
         * Set lights level - stub for widget compatibility.
         * Actual implementation should use KagamiApiService.
         */
        suspend fun setLights(context: Context, level: Int, roomId: String? = null): Boolean {
            android.util.Log.d(TAG, "setLights called: level=$level, roomId=$roomId")
            // TODO: Implement via KagamiApiService when available
            return true
        }

        /**
         * Legacy setLights signature for backward compatibility.
         */
        suspend fun setLights(level: Int, rooms: List<String>? = null): Boolean {
            android.util.Log.d(TAG, "setLights called: level=$level, rooms=$rooms")
            // TODO: Implement via KagamiApiService when available
            return true
        }

        /**
         * Execute a scene command - stub for widget compatibility.
         */
        suspend fun executeScene(scene: String): Boolean {
            android.util.Log.d(TAG, "executeScene called: scene=$scene")
            // TODO: Implement via KagamiApiService when available
            return true
        }
    }
}

// =============================================================
// DATA CLASSES
// =============================================================

/**
 * Safety status for widget display.
 */
enum class SafetyStatus {
    OK,         // Green - h(x) >= 0.5
    CAUTION,    // Yellow - 0 <= h(x) < 0.5
    VIOLATION,  // Red - h(x) < 0
    UNKNOWN;    // Gray - not connected

    companion object {
        fun fromString(value: String): SafetyStatus {
            return try {
                valueOf(value.uppercase())
            } catch (e: Exception) {
                UNKNOWN
            }
        }

        fun fromScore(score: Double?): SafetyStatus {
            return when {
                score == null -> UNKNOWN
                score >= 0.5 -> OK
                score >= 0.0 -> CAUTION
                else -> VIOLATION
            }
        }
    }
}

/**
 * Safety data bundle for widgets.
 */
data class SafetyData(
    val score: Double?,
    val status: SafetyStatus,
    val lastUpdate: Long,
    val isConnected: Boolean,
    val latencyMs: Int
)

/**
 * Scene information for quick actions widget.
 */
data class SceneInfo(
    val id: String,
    val name: String,
    val icon: String = "star"
)

/**
 * Room information for room control widget.
 */
data class RoomInfo(
    val id: String,
    val name: String,
    val floor: String,
    val hasLights: Boolean = true,
    val hasShades: Boolean = false,
    val lightLevel: Int = 0,
    val shadesOpen: Boolean = true
)

/**
 * Per-widget configuration.
 */
data class WidgetConfig(
    val widgetType: String,
    val roomId: String? = null,
    val sceneIds: List<String>? = null,
    val theme: String = "auto"
) {
    fun serialize(): String {
        val sceneIdsStr = sceneIds?.joinToString(",") ?: ""
        return "$widgetType|${roomId ?: ""}|$sceneIdsStr|$theme"
    }

    companion object {
        fun deserialize(value: String): WidgetConfig? {
            return try {
                val parts = value.split("|")
                WidgetConfig(
                    widgetType = parts.getOrNull(0) ?: return null,
                    roomId = parts.getOrNull(1)?.takeIf { it.isNotEmpty() },
                    sceneIds = parts.getOrNull(2)?.takeIf { it.isNotEmpty() }?.split(","),
                    theme = parts.getOrNull(3) ?: "auto"
                )
            } catch (e: Exception) {
                null
            }
        }
    }
}
