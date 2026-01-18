package com.kagami.wear.services

import android.content.Intent
import android.util.Log
import com.google.android.gms.wearable.DataEventBuffer
import com.google.android.gms.wearable.MessageEvent
import com.google.android.gms.wearable.WearableListenerService
import com.kagami.wear.complications.KagamiComplicationService
import com.kagami.wear.tiles.KagamiTileService
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import org.json.JSONObject

/**
 * Wear Data Layer Service - Phone/Watch Sync
 *
 * Colony: Nexus (e4) - Integration
 *
 * Handles:
 * - Receiving settings from phone
 * - Syncing state between phone and watch
 * - Message-based commands from phone companion app
 */
class WearDataLayerService : WearableListenerService() {

    private val serviceJob = SupervisorJob()
    private val serviceScope = CoroutineScope(Dispatchers.IO + serviceJob)

    companion object {
        private const val TAG = "WearDataLayer"

        // Data paths
        const val PATH_CONFIG = "/kagami/config"
        const val PATH_ROOMS = "/kagami/rooms"
        const val PATH_STATUS = "/kagami/status"

        // Message paths
        const val PATH_EXECUTE_SCENE = "/kagami/execute_scene"
        const val PATH_SET_LIGHTS = "/kagami/set_lights"
        const val PATH_REFRESH = "/kagami/refresh"

        // Data keys
        const val KEY_SERVER_URL = "server_url"
        const val KEY_ROOMS_JSON = "rooms_json"
        const val KEY_SAFETY_SCORE = "safety_score"
    }

    override fun onDestroy() {
        super.onDestroy()
        serviceScope.cancel()
        serviceJob.cancel()
    }

    override fun onDataChanged(dataEvents: DataEventBuffer) {
        super.onDataChanged(dataEvents)

        dataEvents.forEach { event ->
            val dataItem = event.dataItem
            val path = dataItem.uri.path ?: return@forEach

            when (path) {
                PATH_CONFIG -> {
                    // Phone sent new configuration
                    serviceScope.launch {
                        handleConfigUpdate(dataItem.data)
                    }
                }
                PATH_ROOMS -> {
                    // Phone sent room data update
                    serviceScope.launch {
                        handleRoomsUpdate(dataItem.data)
                    }
                }
                PATH_STATUS -> {
                    // Phone sent status update
                    serviceScope.launch {
                        handleStatusUpdate(dataItem.data)
                    }
                }
            }
        }
    }

    override fun onMessageReceived(messageEvent: MessageEvent) {
        super.onMessageReceived(messageEvent)

        val path = messageEvent.path
        val data = messageEvent.data

        when (path) {
            PATH_EXECUTE_SCENE -> {
                // Phone requested scene execution
                val sceneId = String(data)
                serviceScope.launch {
                    val success = KagamiWearApiService.executeScene(sceneId)
                    if (success) {
                        // Update tile and complication after scene execution
                        requestUiUpdates()
                    }
                    Log.d(TAG, "Scene executed from phone: $sceneId, success: $success")
                }
            }
            PATH_SET_LIGHTS -> {
                // Phone requested lights change
                serviceScope.launch {
                    try {
                        val json = JSONObject(String(data))
                        val level = json.getInt("level")
                        val rooms = if (json.has("rooms")) {
                            val roomsArray = json.getJSONArray("rooms")
                            (0 until roomsArray.length()).map { roomsArray.getString(it) }
                        } else null
                        val success = KagamiWearApiService.setLights(level, rooms)
                        if (success) {
                            requestUiUpdates()
                        }
                        Log.d(TAG, "Lights set from phone: level=$level, success: $success")
                    } catch (e: Exception) {
                        Log.e(TAG, "Invalid lights JSON", e)
                    }
                }
            }
            PATH_REFRESH -> {
                // Phone requested status refresh
                serviceScope.launch {
                    KagamiWearApiService.fetchHealth()
                    requestUiUpdates()
                    Log.d(TAG, "Status refresh requested from phone")
                }
            }
        }
    }

    private suspend fun handleConfigUpdate(data: ByteArray?) {
        data ?: return
        try {
            val json = JSONObject(String(data))
            if (json.has(KEY_SERVER_URL)) {
                val serverUrl = json.getString(KEY_SERVER_URL)
                KagamiWearApiService.configure(serverUrl)
                Log.d(TAG, "Server URL updated: $serverUrl")
                // Refresh after config change
                requestUiUpdates()
            }
        } catch (e: Exception) {
            Log.e(TAG, "Invalid config data", e)
        }
    }

    private suspend fun handleRoomsUpdate(data: ByteArray?) {
        // Room updates are cached automatically when fetched
        // This path is for push updates from phone
        data ?: return
        // Trigger UI update for rooms data
        requestUiUpdates()
    }

    private suspend fun handleStatusUpdate(data: ByteArray?) {
        // Status updates from phone
        // Can be used to update complications
        data ?: return

        try {
            val json = JSONObject(String(data))
            val safetyScore = json.optDouble(KEY_SAFETY_SCORE, -1.0)
            if (safetyScore >= 0) {
                Log.d(TAG, "Status update received, safety score: $safetyScore")
                // Update complications with new safety score
                requestUiUpdates()
            }
        } catch (e: Exception) {
            Log.e(TAG, "Invalid status data", e)
        }
    }

    /**
     * Request updates for tile and complications.
     */
    private fun requestUiUpdates() {
        try {
            KagamiTileService.requestTileUpdate(applicationContext)
            KagamiComplicationService.requestUpdate(applicationContext)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to request UI updates", e)
        }
    }
}
