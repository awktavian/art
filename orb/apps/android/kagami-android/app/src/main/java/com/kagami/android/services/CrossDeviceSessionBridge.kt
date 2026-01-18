/**
 * Cross-Device Session Bridge - Wear/TV/Phone Session Synchronization
 *
 * Colony: Nexus (e4) - Integration
 * h(x) >= 0. Always.
 *
 * P2 Gap Fix: Implements SharedViewModel pattern for cross-device session sync.
 * Features:
 * - Wear OS DataClient-based session sync
 * - Android TV Leanback session bridging
 * - Guest mode with restricted permissions
 * - FeatureFlags integration for progressive rollout
 *
 * Session State:
 * - Current room selections
 * - Active scenes
 * - Recent commands
 * - User preferences subset
 */

package com.kagami.android.services

import android.content.Context
import android.util.Log
import com.google.android.gms.wearable.DataClient
import com.google.android.gms.wearable.DataEvent
import com.google.android.gms.wearable.DataEventBuffer
import com.google.android.gms.wearable.DataItem
import com.google.android.gms.wearable.DataMapItem
import com.google.android.gms.wearable.MessageClient
import com.google.android.gms.wearable.PutDataMapRequest
import com.google.android.gms.wearable.Wearable
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.tasks.await
import org.json.JSONArray
import org.json.JSONObject
import javax.inject.Inject
import javax.inject.Singleton

// =============================================================================
// SESSION STATE MODELS
// =============================================================================

/**
 * Cross-device session state that syncs between Phone/Wear/TV.
 */
data class SessionState(
    val selectedRoomIds: List<String> = emptyList(),
    val activeSceneId: String? = null,
    val recentCommands: List<RecentCommand> = emptyList(),
    val userMode: UserMode = UserMode.OWNER,
    val timestamp: Long = System.currentTimeMillis()
) {
    fun toJson(): JSONObject = JSONObject().apply {
        put("selectedRoomIds", JSONArray(selectedRoomIds))
        put("activeSceneId", activeSceneId)
        put("recentCommands", JSONArray(recentCommands.map { it.toJson() }))
        put("userMode", userMode.name)
        put("timestamp", timestamp)
    }

    companion object {
        fun fromJson(json: JSONObject): SessionState {
            val roomIds = mutableListOf<String>()
            json.optJSONArray("selectedRoomIds")?.let { array ->
                for (i in 0 until array.length()) {
                    roomIds.add(array.getString(i))
                }
            }

            val commands = mutableListOf<RecentCommand>()
            json.optJSONArray("recentCommands")?.let { array ->
                for (i in 0 until array.length()) {
                    commands.add(RecentCommand.fromJson(array.getJSONObject(i)))
                }
            }

            return SessionState(
                selectedRoomIds = roomIds,
                activeSceneId = json.optString("activeSceneId").takeIf { it.isNotEmpty() },
                recentCommands = commands,
                userMode = try {
                    UserMode.valueOf(json.optString("userMode", "OWNER"))
                } catch (e: Exception) {
                    UserMode.OWNER
                },
                timestamp = json.optLong("timestamp", System.currentTimeMillis())
            )
        }
    }
}

/**
 * Recent command for history sync.
 */
data class RecentCommand(
    val type: String,
    val target: String,
    val value: String?,
    val timestamp: Long = System.currentTimeMillis()
) {
    fun toJson(): JSONObject = JSONObject().apply {
        put("type", type)
        put("target", target)
        value?.let { put("value", it) }
        put("timestamp", timestamp)
    }

    companion object {
        fun fromJson(json: JSONObject): RecentCommand = RecentCommand(
            type = json.optString("type"),
            target = json.optString("target"),
            value = json.optString("value").takeIf { it.isNotEmpty() },
            timestamp = json.optLong("timestamp", System.currentTimeMillis())
        )
    }
}

/**
 * User mode for guest restrictions.
 */
enum class UserMode {
    OWNER,      // Full access
    HOUSEHOLD,  // Full access, different user
    GUEST       // Restricted access
}

/**
 * Guest mode permissions - what guests CAN do.
 */
data class GuestPermissions(
    val canControlLights: Boolean = true,
    val canControlShades: Boolean = true,
    val canActivateScenes: Boolean = true,
    val canControlFireplace: Boolean = false,  // CBF safety
    val canControlLocks: Boolean = false,      // CBF safety
    val canControlTV: Boolean = true,
    val allowedRoomIds: Set<String>? = null    // null = all rooms
) {
    companion object {
        val DEFAULT = GuestPermissions()

        val RESTRICTED = GuestPermissions(
            canControlLights = true,
            canControlShades = false,
            canActivateScenes = false,
            canControlFireplace = false,
            canControlLocks = false,
            canControlTV = false
        )
    }
}

/**
 * Device types for session sync.
 */
enum class DeviceType {
    PHONE,
    WEAR,
    TV,
    TABLET
}

/**
 * Session sync event for reactive updates.
 */
sealed class SessionSyncEvent {
    data class StateUpdated(val state: SessionState, val source: DeviceType) : SessionSyncEvent()
    data class DeviceConnected(val deviceType: DeviceType, val nodeId: String) : SessionSyncEvent()
    data class DeviceDisconnected(val deviceType: DeviceType, val nodeId: String) : SessionSyncEvent()
    data class SyncError(val error: String, val source: DeviceType?) : SessionSyncEvent()
    object SyncCompleted : SessionSyncEvent()
}

// =============================================================================
// CROSS-DEVICE SESSION BRIDGE
// =============================================================================

/**
 * Cross-Device Session Bridge
 *
 * Manages session state synchronization between Phone, Wear OS, and Android TV.
 * Uses Google Wearable Data Layer API for Wear sync and local broadcast for TV.
 */
@Singleton
class CrossDeviceSessionBridge @Inject constructor(
    private val authManager: AuthManager,
    private val featureFlagsService: FeatureFlagsService,
    private val dataClient: DataClient,
    private val messageClient: MessageClient
) : DataClient.OnDataChangedListener {

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    companion object {
        private const val TAG = "CrossDeviceSession"

        // Data paths for Wear sync
        const val PATH_SESSION_STATE = "/kagami/session/state"
        const val PATH_GUEST_MODE = "/kagami/session/guest"
        const val PATH_SYNC_REQUEST = "/kagami/session/sync_request"

        // Data keys
        const val KEY_STATE_JSON = "state_json"
        const val KEY_GUEST_ENABLED = "guest_enabled"
        const val KEY_GUEST_PERMISSIONS = "guest_permissions"
        const val KEY_SOURCE_DEVICE = "source_device"

        // Message paths
        const val MSG_REQUEST_SYNC = "/kagami/msg/request_sync"
        const val MSG_COMMAND_EXECUTED = "/kagami/msg/command_executed"

        // Limits
        private const val MAX_RECENT_COMMANDS = 10
    }

    // State
    private val _sessionState = MutableStateFlow(SessionState())
    val sessionState: StateFlow<SessionState> = _sessionState.asStateFlow()

    private val _guestPermissions = MutableStateFlow(GuestPermissions.DEFAULT)
    val guestPermissions: StateFlow<GuestPermissions> = _guestPermissions.asStateFlow()

    private val _isGuestMode = MutableStateFlow(false)
    val isGuestMode: StateFlow<Boolean> = _isGuestMode.asStateFlow()

    private val _connectedDevices = MutableStateFlow<Map<DeviceType, String>>(emptyMap())
    val connectedDevices: StateFlow<Map<DeviceType, String>> = _connectedDevices.asStateFlow()

    private val _syncEvents = MutableSharedFlow<SessionSyncEvent>(extraBufferCapacity = 16)
    val syncEvents: SharedFlow<SessionSyncEvent> = _syncEvents.asSharedFlow()

    // Track this device type
    private var thisDeviceType: DeviceType = DeviceType.PHONE

    // =============================================================
    // INITIALIZATION
    // =============================================================

    /**
     * Initialize the session bridge.
     * Call this at app startup.
     */
    suspend fun initialize(context: Context, deviceType: DeviceType = DeviceType.PHONE) {
        thisDeviceType = deviceType

        // Check feature flag
        if (!featureFlagsService.isWearOsSyncEnabled()) {
            Log.i(TAG, "Cross-device sync disabled by feature flag")
            return
        }

        // Register data listener
        dataClient.addListener(this)

        // Request initial sync from other devices
        requestSyncFromPeers()

        Log.i(TAG, "Cross-device session bridge initialized for $deviceType")
    }

    /**
     * Clean up resources.
     */
    fun shutdown() {
        dataClient.removeListener(this)
    }

    // =============================================================
    // SESSION STATE MANAGEMENT
    // =============================================================

    /**
     * Update selected rooms and sync to other devices.
     */
    suspend fun selectRooms(roomIds: List<String>) {
        val newState = _sessionState.value.copy(
            selectedRoomIds = roomIds,
            timestamp = System.currentTimeMillis()
        )
        updateAndSyncState(newState)
    }

    /**
     * Add a room to selection.
     */
    suspend fun addRoomToSelection(roomId: String) {
        val current = _sessionState.value.selectedRoomIds.toMutableList()
        if (!current.contains(roomId)) {
            current.add(roomId)
            selectRooms(current)
        }
    }

    /**
     * Set active scene and sync.
     */
    suspend fun setActiveScene(sceneId: String?) {
        val newState = _sessionState.value.copy(
            activeSceneId = sceneId,
            timestamp = System.currentTimeMillis()
        )
        updateAndSyncState(newState)
    }

    /**
     * Record a command for history sync.
     */
    suspend fun recordCommand(type: String, target: String, value: String? = null) {
        val command = RecentCommand(type, target, value)
        val commands = _sessionState.value.recentCommands.toMutableList()
        commands.add(0, command)

        // Limit to max recent commands
        while (commands.size > MAX_RECENT_COMMANDS) {
            commands.removeAt(commands.size - 1)
        }

        val newState = _sessionState.value.copy(
            recentCommands = commands,
            timestamp = System.currentTimeMillis()
        )
        updateAndSyncState(newState)
    }

    /**
     * Update state locally and sync to peers.
     */
    private suspend fun updateAndSyncState(newState: SessionState) {
        _sessionState.value = newState

        // Sync to Wear OS
        syncToWear(newState)

        // Emit event
        _syncEvents.emit(SessionSyncEvent.StateUpdated(newState, thisDeviceType))
    }

    // =============================================================
    // GUEST MODE
    // =============================================================

    /**
     * Enable guest mode with specified permissions.
     */
    suspend fun enableGuestMode(permissions: GuestPermissions = GuestPermissions.DEFAULT) {
        if (!canEnableGuestMode()) {
            Log.w(TAG, "Guest mode not allowed - feature flag disabled")
            return
        }

        _isGuestMode.value = true
        _guestPermissions.value = permissions

        val newState = _sessionState.value.copy(
            userMode = UserMode.GUEST,
            timestamp = System.currentTimeMillis()
        )
        updateAndSyncState(newState)

        // Sync guest mode to Wear
        syncGuestModeToWear(true, permissions)

        Log.i(TAG, "Guest mode enabled with permissions: $permissions")
    }

    /**
     * Disable guest mode, returning to owner mode.
     */
    suspend fun disableGuestMode() {
        _isGuestMode.value = false
        _guestPermissions.value = GuestPermissions.DEFAULT

        val newState = _sessionState.value.copy(
            userMode = UserMode.OWNER,
            timestamp = System.currentTimeMillis()
        )
        updateAndSyncState(newState)

        // Sync guest mode to Wear
        syncGuestModeToWear(false, GuestPermissions.DEFAULT)

        Log.i(TAG, "Guest mode disabled")
    }

    /**
     * Check if guest mode can be enabled (feature flag check).
     */
    fun canEnableGuestMode(): Boolean {
        // Could add a specific feature flag for guest mode
        return featureFlagsService.isEnabled(FeatureFlagsService.FLAG_WEAR_OS_SYNC)
    }

    /**
     * Check if a specific action is allowed in current mode.
     */
    fun isActionAllowed(actionType: GuestActionType): Boolean {
        if (!_isGuestMode.value) return true

        val permissions = _guestPermissions.value
        return when (actionType) {
            GuestActionType.CONTROL_LIGHTS -> permissions.canControlLights
            GuestActionType.CONTROL_SHADES -> permissions.canControlShades
            GuestActionType.ACTIVATE_SCENE -> permissions.canActivateScenes
            GuestActionType.CONTROL_FIREPLACE -> permissions.canControlFireplace
            GuestActionType.CONTROL_LOCKS -> permissions.canControlLocks
            GuestActionType.CONTROL_TV -> permissions.canControlTV
        }
    }

    /**
     * Check if a room is accessible in guest mode.
     */
    fun isRoomAccessible(roomId: String): Boolean {
        if (!_isGuestMode.value) return true

        val allowedRooms = _guestPermissions.value.allowedRoomIds
        return allowedRooms == null || allowedRooms.contains(roomId)
    }

    // =============================================================
    // WEAR OS SYNC
    // =============================================================

    /**
     * Sync session state to Wear OS via DataClient.
     */
    private suspend fun syncToWear(state: SessionState) {
        if (!featureFlagsService.isWearOsSyncEnabled()) return

        try {
            val request = PutDataMapRequest.create(PATH_SESSION_STATE).apply {
                dataMap.putString(KEY_STATE_JSON, state.toJson().toString())
                dataMap.putString(KEY_SOURCE_DEVICE, thisDeviceType.name)
                dataMap.putLong("timestamp", System.currentTimeMillis())
            }

            dataClient.putDataItem(request.asPutDataRequest().setUrgent()).await()
            Log.d(TAG, "Session state synced to Wear")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to sync to Wear", e)
            _syncEvents.emit(SessionSyncEvent.SyncError(e.message ?: "Unknown error", DeviceType.WEAR))
        }
    }

    /**
     * Sync guest mode settings to Wear.
     */
    private suspend fun syncGuestModeToWear(enabled: Boolean, permissions: GuestPermissions) {
        if (!featureFlagsService.isWearOsSyncEnabled()) return

        try {
            val request = PutDataMapRequest.create(PATH_GUEST_MODE).apply {
                dataMap.putBoolean(KEY_GUEST_ENABLED, enabled)
                dataMap.putString(KEY_GUEST_PERMISSIONS, JSONObject().apply {
                    put("canControlLights", permissions.canControlLights)
                    put("canControlShades", permissions.canControlShades)
                    put("canActivateScenes", permissions.canActivateScenes)
                    put("canControlFireplace", permissions.canControlFireplace)
                    put("canControlLocks", permissions.canControlLocks)
                    put("canControlTV", permissions.canControlTV)
                    permissions.allowedRoomIds?.let {
                        put("allowedRoomIds", JSONArray(it))
                    }
                }.toString())
                dataMap.putLong("timestamp", System.currentTimeMillis())
            }

            dataClient.putDataItem(request.asPutDataRequest().setUrgent()).await()
            Log.d(TAG, "Guest mode synced to Wear: enabled=$enabled")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to sync guest mode to Wear", e)
        }
    }

    /**
     * Request sync from peer devices.
     */
    private suspend fun requestSyncFromPeers() {
        try {
            val nodes = Wearable.getNodeClient(dataClient as Context).connectedNodes.await()
            for (node in nodes) {
                messageClient.sendMessage(node.id, MSG_REQUEST_SYNC, ByteArray(0)).await()
            }
            Log.d(TAG, "Sync request sent to ${nodes.size} peer(s)")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to request sync from peers", e)
        }
    }

    // =============================================================
    // DATA LISTENER
    // =============================================================

    override fun onDataChanged(dataEvents: DataEventBuffer) {
        dataEvents.forEach { event ->
            if (event.type == DataEvent.TYPE_CHANGED) {
                handleDataChanged(event.dataItem)
            }
        }
    }

    private fun handleDataChanged(dataItem: DataItem) {
        val path = dataItem.uri.path ?: return

        scope.launch {
            when (path) {
                PATH_SESSION_STATE -> handleSessionStateUpdate(dataItem)
                PATH_GUEST_MODE -> handleGuestModeUpdate(dataItem)
            }
        }
    }

    private suspend fun handleSessionStateUpdate(dataItem: DataItem) {
        try {
            val dataMap = DataMapItem.fromDataItem(dataItem).dataMap
            val stateJson = dataMap.getString(KEY_STATE_JSON) ?: return
            val sourceDevice = dataMap.getString(KEY_SOURCE_DEVICE) ?: return
            val source = try {
                DeviceType.valueOf(sourceDevice)
            } catch (e: Exception) {
                DeviceType.PHONE
            }

            // Don't process our own updates
            if (source == thisDeviceType) return

            val newState = SessionState.fromJson(JSONObject(stateJson))

            // Only update if newer
            if (newState.timestamp > _sessionState.value.timestamp) {
                _sessionState.value = newState
                _syncEvents.emit(SessionSyncEvent.StateUpdated(newState, source))
                Log.d(TAG, "Session state updated from $source")
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to handle session state update", e)
        }
    }

    private suspend fun handleGuestModeUpdate(dataItem: DataItem) {
        try {
            val dataMap = DataMapItem.fromDataItem(dataItem).dataMap
            val enabled = dataMap.getBoolean(KEY_GUEST_ENABLED)
            val permissionsJson = dataMap.getString(KEY_GUEST_PERMISSIONS)

            _isGuestMode.value = enabled

            if (permissionsJson != null) {
                val json = JSONObject(permissionsJson)
                val allowedRooms = json.optJSONArray("allowedRoomIds")?.let { array ->
                    (0 until array.length()).map { array.getString(it) }.toSet()
                }

                _guestPermissions.value = GuestPermissions(
                    canControlLights = json.optBoolean("canControlLights", true),
                    canControlShades = json.optBoolean("canControlShades", true),
                    canActivateScenes = json.optBoolean("canActivateScenes", true),
                    canControlFireplace = json.optBoolean("canControlFireplace", false),
                    canControlLocks = json.optBoolean("canControlLocks", false),
                    canControlTV = json.optBoolean("canControlTV", true),
                    allowedRoomIds = allowedRooms
                )
            }

            Log.d(TAG, "Guest mode updated from peer: enabled=$enabled")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to handle guest mode update", e)
        }
    }

    // =============================================================
    // TV INTEGRATION
    // =============================================================

    /**
     * Send session state to Android TV via local broadcast or Cast.
     * TV apps should register for these broadcasts.
     */
    suspend fun syncToTV(context: Context) {
        // For Android TV in the same home network, use local broadcast
        // Or use Google Cast for remote TVs
        // This is a placeholder - implement based on your TV architecture
        Log.d(TAG, "TV sync requested - implement based on TV architecture")
    }
}

/**
 * Guest action types for permission checking.
 */
enum class GuestActionType {
    CONTROL_LIGHTS,
    CONTROL_SHADES,
    ACTIVATE_SCENE,
    CONTROL_FIREPLACE,
    CONTROL_LOCKS,
    CONTROL_TV
}

/*
 * Mirror
 * h(x) >= 0. Always.
 */
