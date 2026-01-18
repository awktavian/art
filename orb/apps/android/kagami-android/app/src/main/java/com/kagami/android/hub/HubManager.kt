package com.kagami.android.hub

import android.content.Context
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.util.Log
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.IOException
import java.util.concurrent.TimeUnit
import javax.inject.Inject
import javax.inject.Singleton

/**
 * 鏡 Hub Manager — Discover and control Kagami Hub devices
 *
 * Colony: Nexus (e4) — Integration
 *
 * Features:
 * - mDNS/NSD service discovery
 * - Hub configuration and control
 * - Voice proxy (phone as Hub's ears)
 * - LED ring control
 * - Real-time status via WebSocket
 */

// ═══════════════════════════════════════════════════════════════════════════
// Data Classes
// ═══════════════════════════════════════════════════════════════════════════

@Serializable
data class HubDevice(
    val id: String,
    val name: String,
    val location: String,
    val host: String,
    val port: Int,
    val isConnected: Boolean = false
) {
    val baseUrl: String get() = "http://$host:$port"
}

@Serializable
data class HubStatus(
    val name: String,
    val location: String,
    val api_url: String,
    val api_connected: Boolean,
    val safety_score: Double? = null,
    val led_ring_enabled: Boolean,
    val led_brightness: Float,
    val wake_word: String,
    val is_listening: Boolean,
    val current_colony: String? = null,
    val uptime_seconds: Long,
    val version: String
)

@Serializable
data class HubConfig(
    val name: String,
    val location: String,
    val api_url: String,
    val wake_word: String,
    val wake_sensitivity: Float,
    val led_enabled: Boolean,
    val led_brightness: Float,
    val led_count: Int,
    val tts_volume: Float,
    val tts_colony: String
)

// ═══════════════════════════════════════════════════════════════════════════
// Hub Manager
// ═══════════════════════════════════════════════════════════════════════════

@Singleton
class HubManager @Inject constructor(
    @dagger.hilt.android.qualifiers.ApplicationContext private val context: Context
) {
    companion object {
        private const val TAG = "HubManager"
        private const val SERVICE_TYPE = "_kagami-hub._tcp."
        private const val PREFS_KEY = "kagami_hub_prefs"
        private const val LAST_HOST_KEY = "last_hub_host"
        private const val LAST_PORT_KEY = "last_hub_port"
    }

    private val json = Json { ignoreUnknownKeys = true }

    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(10, TimeUnit.SECONDS)
        .build()

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    // ═══════════════════════════════════════════════════════════════════════
    // State
    // ═══════════════════════════════════════════════════════════════════════

    private val _discoveredHubs = MutableStateFlow<List<HubDevice>>(emptyList())
    val discoveredHubs: StateFlow<List<HubDevice>> = _discoveredHubs.asStateFlow()

    private val _connectedHub = MutableStateFlow<HubDevice?>(null)
    val connectedHub: StateFlow<HubDevice?> = _connectedHub.asStateFlow()

    private val _hubStatus = MutableStateFlow<HubStatus?>(null)
    val hubStatus: StateFlow<HubStatus?> = _hubStatus.asStateFlow()

    private val _hubConfig = MutableStateFlow<HubConfig?>(null)
    val hubConfig: StateFlow<HubConfig?> = _hubConfig.asStateFlow()

    private val _isDiscovering = MutableStateFlow(false)
    val isDiscovering: StateFlow<Boolean> = _isDiscovering.asStateFlow()

    private val _isConnecting = MutableStateFlow(false)
    val isConnecting: StateFlow<Boolean> = _isConnecting.asStateFlow()

    private val _error = MutableStateFlow<String?>(null)
    val error: StateFlow<String?> = _error.asStateFlow()

    private var nsdManager: NsdManager? = null
    private var discoveryListener: NsdManager.DiscoveryListener? = null
    private var webSocket: WebSocket? = null

    // ═══════════════════════════════════════════════════════════════════════
    // Discovery via NSD (Android's mDNS)
    // ═══════════════════════════════════════════════════════════════════════

    fun startDiscovery() {
        if (_isDiscovering.value) return

        _isDiscovering.value = true
        _discoveredHubs.value = emptyList()
        _error.value = null

        nsdManager = context.getSystemService(Context.NSD_SERVICE) as NsdManager

        discoveryListener = object : NsdManager.DiscoveryListener {
            override fun onDiscoveryStarted(serviceType: String) {
                Log.d(TAG, "Discovery started for $serviceType")
            }

            override fun onServiceFound(serviceInfo: NsdServiceInfo) {
                Log.d(TAG, "Service found: ${serviceInfo.serviceName}")
                resolveService(serviceInfo)
            }

            override fun onServiceLost(serviceInfo: NsdServiceInfo) {
                Log.d(TAG, "Service lost: ${serviceInfo.serviceName}")
                _discoveredHubs.value = _discoveredHubs.value.filterNot {
                    it.name == serviceInfo.serviceName
                }
            }

            override fun onDiscoveryStopped(serviceType: String) {
                Log.d(TAG, "Discovery stopped")
                _isDiscovering.value = false
            }

            override fun onStartDiscoveryFailed(serviceType: String, errorCode: Int) {
                Log.e(TAG, "Discovery start failed: $errorCode")
                _error.value = "Discovery failed (error $errorCode)"
                _isDiscovering.value = false
            }

            override fun onStopDiscoveryFailed(serviceType: String, errorCode: Int) {
                Log.e(TAG, "Discovery stop failed: $errorCode")
            }
        }

        nsdManager?.discoverServices(SERVICE_TYPE, NsdManager.PROTOCOL_DNS_SD, discoveryListener)

        // Also try direct discovery
        scope.launch {
            tryDirectDiscovery()
        }

        // Stop discovery after 10 seconds
        scope.launch {
            delay(10_000)
            stopDiscovery()
        }
    }

    fun stopDiscovery() {
        discoveryListener?.let { listener ->
            try {
                nsdManager?.stopServiceDiscovery(listener)
            } catch (e: Exception) {
                Log.w(TAG, "Error stopping discovery: ${e.message}")
            }
        }
        discoveryListener = null
        _isDiscovering.value = false
    }

    private fun resolveService(serviceInfo: NsdServiceInfo) {
        nsdManager?.resolveService(serviceInfo, object : NsdManager.ResolveListener {
            override fun onServiceResolved(resolvedInfo: NsdServiceInfo) {
                val host = resolvedInfo.host?.hostAddress ?: return
                val port = resolvedInfo.port

                val hub = HubDevice(
                    id = "$host:$port",
                    name = resolvedInfo.serviceName,
                    location = "Discovered",
                    host = host,
                    port = port
                )

                scope.launch {
                    val current = _discoveredHubs.value.toMutableList()
                    if (current.none { it.id == hub.id }) {
                        current.add(hub)
                        _discoveredHubs.value = current
                    }
                }
            }

            override fun onResolveFailed(serviceInfo: NsdServiceInfo, errorCode: Int) {
                Log.e(TAG, "Resolve failed: $errorCode")
            }
        })
    }

    private suspend fun tryDirectDiscovery() {
        val candidates = listOf(
            "kagami-hub.local" to 8080,
            "raspberrypi.local" to 8080,
            "192.168.1.100" to 8080,
            "192.168.1.50" to 8080,
        )

        candidates.forEach { (host, port) ->
            if (testConnection(host, port)) {
                val hub = HubDevice(
                    id = "$host:$port",
                    name = "Kagami Hub",
                    location = "Direct",
                    host = host,
                    port = port
                )

                val current = _discoveredHubs.value.toMutableList()
                if (current.none { it.id == hub.id }) {
                    current.add(hub)
                    _discoveredHubs.value = current
                }
            }
        }
    }

    private suspend fun testConnection(host: String, port: Int): Boolean {
        return withContext(Dispatchers.IO) {
            try {
                val request = Request.Builder()
                    .url("http://$host:$port/health")
                    .build()

                client.newCall(request).execute().use { response ->
                    response.isSuccessful
                }
            } catch (e: Exception) {
                false
            }
        }
    }

    // ═══════════════════════════════════════════════════════════════════════
    // Connection
    // ═══════════════════════════════════════════════════════════════════════

    suspend fun connect(hub: HubDevice) {
        _isConnecting.value = true
        _error.value = null

        try {
            val status = fetchStatus(hub)
            val config = fetchConfig(hub)

            _connectedHub.value = hub.copy(
                isConnected = true,
                name = status.name,
                location = status.location
            )
            _hubStatus.value = status
            _hubConfig.value = config

            // Connect WebSocket
            connectWebSocket(hub)

            // Save as last hub
            saveLastHub(hub)

        } catch (e: Exception) {
            _error.value = "Connection failed: ${e.message}"
            Log.e(TAG, "Connection error", e)
        }

        _isConnecting.value = false
    }

    fun disconnect() {
        webSocket?.close(1000, "User disconnected")
        webSocket = null
        _connectedHub.value = null
        _hubStatus.value = null
        _hubConfig.value = null
    }

    // ═══════════════════════════════════════════════════════════════════════
    // API Calls
    // ═══════════════════════════════════════════════════════════════════════

    private suspend fun fetchStatus(hub: HubDevice): HubStatus {
        return withContext(Dispatchers.IO) {
            val request = Request.Builder()
                .url("${hub.baseUrl}/status")
                .build()

            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) throw IOException("Status fetch failed")
                json.decodeFromString(response.body!!.string())
            }
        }
    }

    private suspend fun fetchConfig(hub: HubDevice): HubConfig {
        return withContext(Dispatchers.IO) {
            val request = Request.Builder()
                .url("${hub.baseUrl}/config")
                .build()

            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) throw IOException("Config fetch failed")
                json.decodeFromString(response.body!!.string())
            }
        }
    }

    suspend fun updateConfig(config: HubConfig) {
        val hub = _connectedHub.value ?: return

        withContext(Dispatchers.IO) {
            val body = json.encodeToString(HubConfig.serializer(), config)
                .toRequestBody("application/json".toMediaType())

            val request = Request.Builder()
                .url("${hub.baseUrl}/config")
                .post(body)
                .build()

            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) throw IOException("Config update failed")
                _hubConfig.value = json.decodeFromString(response.body!!.string())
            }
        }
    }

    suspend fun controlLED(pattern: String, colony: Int? = null, brightness: Float? = null) {
        val hub = _connectedHub.value ?: return

        withContext(Dispatchers.IO) {
            val bodyJson = org.json.JSONObject().apply {
                put("pattern", pattern)
                colony?.let { put("colony", it) }
                brightness?.let { put("brightness", it.toDouble()) }
            }

            val body = bodyJson.toString().toRequestBody("application/json".toMediaType())

            val request = Request.Builder()
                .url("${hub.baseUrl}/led")
                .post(body)
                .build()

            client.newCall(request).execute().close()
        }
    }

    suspend fun testLED() {
        val hub = _connectedHub.value ?: return

        withContext(Dispatchers.IO) {
            val request = Request.Builder()
                .url("${hub.baseUrl}/led/test")
                .post("".toRequestBody())
                .build()

            client.newCall(request).execute().close()
        }
    }

    suspend fun triggerListen() {
        val hub = _connectedHub.value ?: return

        withContext(Dispatchers.IO) {
            val request = Request.Builder()
                .url("${hub.baseUrl}/voice/listen")
                .post("".toRequestBody())
                .build()

            client.newCall(request).execute().close()
        }
    }

    suspend fun executeCommand(command: String) {
        val hub = _connectedHub.value ?: return

        withContext(Dispatchers.IO) {
            val body = """{"command":"$command"}"""
                .toRequestBody("application/json".toMediaType())

            val request = Request.Builder()
                .url("${hub.baseUrl}/command")
                .post(body)
                .build()

            client.newCall(request).execute().close()
        }
    }

    // ═══════════════════════════════════════════════════════════════════════
    // WebSocket
    // ═══════════════════════════════════════════════════════════════════════

    private fun connectWebSocket(hub: HubDevice) {
        val request = Request.Builder()
            .url("ws://${hub.host}:${hub.port}/ws")
            .build()

        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                Log.d(TAG, "WebSocket connected")
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                handleWebSocketMessage(text)
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                Log.e(TAG, "WebSocket error", t)
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                Log.d(TAG, "WebSocket closed: $reason")
            }
        })
    }

    private fun handleWebSocketMessage(text: String) {
        try {
            val event = json.decodeFromString<HubEvent>(text)

            when (event.event_type) {
                "status_update" -> {
                    // Parse nested status
                    _hubStatus.value?.let { current ->
                        // Update from event data
                    }
                }
                "listening_started" -> {
                    _hubStatus.value = _hubStatus.value?.copy(is_listening = true)
                }
                "config_updated" -> {
                    // Re-fetch config
                    scope.launch {
                        _connectedHub.value?.let { hub ->
                            _hubConfig.value = fetchConfig(hub)
                        }
                    }
                }
            }
        } catch (e: Exception) {
            Log.w(TAG, "Failed to parse WebSocket message", e)
        }
    }

    @Serializable
    private data class HubEvent(
        val event_type: String,
        val timestamp: Long
    )

    // ═══════════════════════════════════════════════════════════════════════
    // Persistence
    // ═══════════════════════════════════════════════════════════════════════

    private fun saveLastHub(hub: HubDevice) {
        context.getSharedPreferences(PREFS_KEY, Context.MODE_PRIVATE).edit()
            .putString(LAST_HOST_KEY, hub.host)
            .putInt(LAST_PORT_KEY, hub.port)
            .apply()
    }

    suspend fun connectToLastHub() {
        val prefs = context.getSharedPreferences(PREFS_KEY, Context.MODE_PRIVATE)
        val host = prefs.getString(LAST_HOST_KEY, null) ?: return
        val port = prefs.getInt(LAST_PORT_KEY, 8080)

        val hub = HubDevice(
            id = "$host:$port",
            name = "Last Hub",
            location = "Saved",
            host = host,
            port = port
        )

        connect(hub)
    }

    fun cleanup() {
        stopDiscovery()
        disconnect()
        scope.cancel()
    }
}

/*
 * 鏡
 */
