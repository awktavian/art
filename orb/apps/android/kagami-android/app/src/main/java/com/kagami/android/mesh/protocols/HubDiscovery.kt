package com.kagami.android.mesh.protocols

import android.content.Context
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.util.Log
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import kotlinx.serialization.Serializable
import okhttp3.OkHttpClient
import okhttp3.Request
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.TimeUnit

/**
 * Hub Discovery — Unified hub discovery interface
 *
 * Defines the platform-agnostic interface for discovering Kagami Hubs.
 * Android implements using NsdManager.
 *
 * This interface mirrors the Rust SDK's HubDiscoveryService.
 *
 * 鏡 h(x) >= 0. Always.
 */

// ═══════════════════════════════════════════════════════════════════════════
// Constants
// ═══════════════════════════════════════════════════════════════════════════

/** mDNS service type for Kagami Hub discovery. */
const val KAGAMI_HUB_SERVICE_TYPE = "_kagami-hub._tcp."

/** Default hub HTTP port. */
const val DEFAULT_HUB_PORT = 8080

// ═══════════════════════════════════════════════════════════════════════════
// Data Classes
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Method by which a hub was discovered.
 */
@Serializable
enum class HubDiscoveryMethod {
    /** Discovered via Android NSD. */
    NSD,
    /** Manual configuration. */
    MANUAL,
    /** Direct IP probe. */
    DIRECT_PROBE,
    /** Saved from previous session. */
    CACHED
}

/**
 * Current state of hub discovery.
 */
sealed class HubDiscoveryState {
    /** Discovery not started. */
    object Idle : HubDiscoveryState()
    /** Discovery in progress. */
    object Discovering : HubDiscoveryState()
    /** Discovery completed. */
    object Completed : HubDiscoveryState()
    /** Discovery failed. */
    data class Failed(val error: Throwable) : HubDiscoveryState()
}

/**
 * Information about a discovered hub.
 */
@Serializable
data class DiscoveredHub(
    /** Unique identifier (host:port). */
    val id: String,
    /** Human-readable hub name. */
    var name: String,
    /** Location description. */
    var location: String = "Unknown",
    /** IP address or hostname. */
    val host: String,
    /** HTTP API port. */
    val port: Int = DEFAULT_HUB_PORT,
    /** Discovery method used. */
    val discoveryMethod: HubDiscoveryMethod = HubDiscoveryMethod.MANUAL,
    /** Last seen timestamp (Unix epoch millis). */
    var lastSeen: Long = System.currentTimeMillis(),
    /** Whether this hub is currently reachable. */
    var isReachable: Boolean = false,
    /** Hub version if known. */
    var version: String? = null,
    /** TXT record attributes from mDNS. */
    var attributes: Map<String, String> = emptyMap()
) {
    /** Base URL for HTTP API calls. */
    val baseUrl: String get() = "http://$host:$port"

    /** WebSocket URL. */
    val websocketUrl: String get() = "ws://$host:$port/ws"

    /** Health check URL. */
    val healthUrl: String get() = "$baseUrl/health"

    /** Update last seen timestamp. */
    fun touch() {
        lastSeen = System.currentTimeMillis()
    }

    /** Check if hub was seen within a duration (millis). */
    fun seenWithin(durationMs: Long): Boolean {
        return System.currentTimeMillis() - lastSeen < durationMs
    }

    companion object {
        fun create(name: String, host: String, port: Int = DEFAULT_HUB_PORT, method: HubDiscoveryMethod = HubDiscoveryMethod.MANUAL): DiscoveredHub {
            return DiscoveredHub(
                id = "$host:$port",
                name = name,
                host = host,
                port = port,
                discoveryMethod = method
            )
        }
    }
}

/**
 * Events emitted during discovery.
 */
sealed class HubDiscoveryEvent {
    /** Discovery started. */
    object Started : HubDiscoveryEvent()
    /** A hub was discovered. */
    data class HubFound(val hub: DiscoveredHub) : HubDiscoveryEvent()
    /** A hub was lost (no longer advertising). */
    data class HubLost(val hubId: String) : HubDiscoveryEvent()
    /** A hub's reachability changed. */
    data class ReachabilityChanged(val hubId: String, val isReachable: Boolean) : HubDiscoveryEvent()
    /** Discovery completed. */
    data class Completed(val hubCount: Int) : HubDiscoveryEvent()
    /** Discovery failed. */
    data class Failed(val error: Throwable) : HubDiscoveryEvent()
    /** Discovery timed out. */
    object Timeout : HubDiscoveryEvent()
}

/**
 * Configuration for hub discovery.
 */
data class HubDiscoveryConfig(
    /** Service type for mDNS. */
    val serviceType: String = KAGAMI_HUB_SERVICE_TYPE,
    /** Discovery timeout in milliseconds. */
    val timeoutMs: Long = 10_000,
    /** Whether to probe known addresses directly. */
    val probeKnownAddresses: Boolean = true,
    /** Known addresses to probe. */
    val knownAddresses: List<Pair<String, Int>> = listOf(
        "kagami-hub.local" to DEFAULT_HUB_PORT,
        "raspberrypi.local" to DEFAULT_HUB_PORT
    ),
    /** Whether to cache discovered hubs. */
    val enableCaching: Boolean = true,
    /** Hub cache TTL in milliseconds. */
    val cacheTtlMs: Long = 300_000 // 5 minutes
)

// ═══════════════════════════════════════════════════════════════════════════
// Hub Discovery Listener
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Listener interface for receiving discovery events.
 */
interface HubDiscoveryListener {
    /** Called when a hub is discovered. */
    fun onHubFound(hub: DiscoveredHub)

    /** Called when a hub is lost. */
    fun onHubLost(hubId: String)

    /** Called when discovery state changes. */
    fun onStateChanged(state: HubDiscoveryState)

    /** Called when an error occurs. */
    fun onError(error: Throwable)
}

// ═══════════════════════════════════════════════════════════════════════════
// Hub Discovery Service Interface
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Interface for hub discovery service implementations.
 */
interface HubDiscoveryService {
    /** The discovery configuration. */
    val config: HubDiscoveryConfig

    /** Current discovery state as a Flow. */
    val stateFlow: StateFlow<HubDiscoveryState>

    /** Discovered hubs as a Flow. */
    val hubsFlow: StateFlow<List<DiscoveredHub>>

    /** Events as a SharedFlow. */
    val eventsFlow: SharedFlow<HubDiscoveryEvent>

    /** Start hub discovery. */
    fun startDiscovery()

    /** Stop hub discovery. */
    fun stopDiscovery()

    /** Check if a specific hub is reachable. */
    suspend fun checkReachability(hubId: String): Boolean

    /** Manually add a hub. */
    fun addManualHub(host: String, port: Int, name: String? = null)

    /** Remove a hub from the list. */
    fun removeHub(hubId: String)

    /** Clear all discovered hubs. */
    fun clearHubs()

    /** Get a specific hub by ID. */
    fun getHub(hubId: String): DiscoveredHub?

    /** Get reachable hubs only. */
    fun getReachableHubs(): List<DiscoveredHub>

    /** Add a listener. */
    fun addListener(listener: HubDiscoveryListener)

    /** Remove a listener. */
    fun removeListener(listener: HubDiscoveryListener)

    /** Clean up resources. */
    fun cleanup()
}

// ═══════════════════════════════════════════════════════════════════════════
// NSD Hub Discovery Service Implementation
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Android NSD-based hub discovery service implementation.
 */
class NsdHubDiscoveryService(
    private val context: Context,
    override val config: HubDiscoveryConfig = HubDiscoveryConfig()
) : HubDiscoveryService {

    companion object {
        private const val TAG = "NsdHubDiscovery"
    }

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private val hubs = ConcurrentHashMap<String, DiscoveredHub>()
    private val listeners = mutableListOf<HubDiscoveryListener>()

    private val _stateFlow = MutableStateFlow<HubDiscoveryState>(HubDiscoveryState.Idle)
    override val stateFlow: StateFlow<HubDiscoveryState> = _stateFlow.asStateFlow()

    private val _hubsFlow = MutableStateFlow<List<DiscoveredHub>>(emptyList())
    override val hubsFlow: StateFlow<List<DiscoveredHub>> = _hubsFlow.asStateFlow()

    private val _eventsFlow = MutableSharedFlow<HubDiscoveryEvent>(replay = 0, extraBufferCapacity = 16)
    override val eventsFlow: SharedFlow<HubDiscoveryEvent> = _eventsFlow.asSharedFlow()

    private var nsdManager: NsdManager? = null
    private var discoveryListener: NsdManager.DiscoveryListener? = null
    private var timeoutJob: Job? = null

    private val httpClient = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(5, TimeUnit.SECONDS)
        .build()

    override fun startDiscovery() {
        if (_stateFlow.value is HubDiscoveryState.Discovering) return

        _stateFlow.value = HubDiscoveryState.Discovering
        hubs.clear()
        updateHubsFlow()
        notifyStateChanged()
        emitEvent(HubDiscoveryEvent.Started)

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
                val hubId = hubs.entries.find { it.value.name == serviceInfo.serviceName }?.key
                hubId?.let { id ->
                    hubs.remove(id)
                    updateHubsFlow()
                    notifyHubLost(id)
                    emitEvent(HubDiscoveryEvent.HubLost(id))
                }
            }

            override fun onDiscoveryStopped(serviceType: String) {
                Log.d(TAG, "Discovery stopped")
                _stateFlow.value = HubDiscoveryState.Completed
                notifyStateChanged()
            }

            override fun onStartDiscoveryFailed(serviceType: String, errorCode: Int) {
                Log.e(TAG, "Discovery start failed: $errorCode")
                val error = Exception("Discovery failed with error code: $errorCode")
                _stateFlow.value = HubDiscoveryState.Failed(error)
                notifyStateChanged()
                notifyError(error)
                emitEvent(HubDiscoveryEvent.Failed(error))
            }

            override fun onStopDiscoveryFailed(serviceType: String, errorCode: Int) {
                Log.e(TAG, "Discovery stop failed: $errorCode")
            }
        }

        nsdManager?.discoverServices(config.serviceType, NsdManager.PROTOCOL_DNS_SD, discoveryListener)

        // Probe known addresses if configured
        if (config.probeKnownAddresses) {
            scope.launch {
                probeKnownAddresses()
            }
        }

        // Set discovery timeout
        timeoutJob = scope.launch {
            delay(config.timeoutMs)
            handleTimeout()
        }
    }

    override fun stopDiscovery() {
        timeoutJob?.cancel()
        timeoutJob = null

        discoveryListener?.let { listener ->
            try {
                nsdManager?.stopServiceDiscovery(listener)
            } catch (e: Exception) {
                Log.w(TAG, "Error stopping discovery: ${e.message}")
            }
        }
        discoveryListener = null

        _stateFlow.value = HubDiscoveryState.Completed
        notifyStateChanged()
        emitEvent(HubDiscoveryEvent.Completed(hubs.size))
    }

    private fun resolveService(serviceInfo: NsdServiceInfo) {
        nsdManager?.resolveService(serviceInfo, object : NsdManager.ResolveListener {
            override fun onServiceResolved(resolvedInfo: NsdServiceInfo) {
                val host = resolvedInfo.host?.hostAddress ?: return
                val port = resolvedInfo.port

                val hub = DiscoveredHub.create(
                    name = resolvedInfo.serviceName,
                    host = host,
                    port = port,
                    method = HubDiscoveryMethod.NSD
                )

                addHubInternal(hub)
            }

            override fun onResolveFailed(serviceInfo: NsdServiceInfo, errorCode: Int) {
                Log.e(TAG, "Resolve failed for ${serviceInfo.serviceName}: $errorCode")
            }
        })
    }

    private suspend fun probeKnownAddresses() {
        config.knownAddresses.forEach { (host, port) ->
            val hub = DiscoveredHub.create(
                name = "Kagami Hub",
                host = host,
                port = port,
                method = HubDiscoveryMethod.DIRECT_PROBE
            )

            if (checkReachabilityInternal(hub)) {
                hub.isReachable = true
                addHubInternal(hub)
            }
        }
    }

    private fun addHubInternal(hub: DiscoveredHub) {
        val isNew = !hubs.containsKey(hub.id)
        hubs[hub.id] = hub
        updateHubsFlow()

        if (isNew) {
            notifyHubFound(hub)
            emitEvent(HubDiscoveryEvent.HubFound(hub))
        }
    }

    private fun updateHubsFlow() {
        _hubsFlow.value = hubs.values.toList()
    }

    override suspend fun checkReachability(hubId: String): Boolean {
        val hub = hubs[hubId] ?: return false
        val isReachable = checkReachabilityInternal(hub)

        val wasReachable = hub.isReachable
        hub.isReachable = isReachable
        hub.touch()

        if (wasReachable != isReachable) {
            updateHubsFlow()
            emitEvent(HubDiscoveryEvent.ReachabilityChanged(hubId, isReachable))
        }

        return isReachable
    }

    private suspend fun checkReachabilityInternal(hub: DiscoveredHub): Boolean {
        return withContext(Dispatchers.IO) {
            try {
                val request = Request.Builder()
                    .url(hub.healthUrl)
                    .build()

                httpClient.newCall(request).execute().use { response ->
                    response.isSuccessful
                }
            } catch (e: Exception) {
                false
            }
        }
    }

    override fun addManualHub(host: String, port: Int, name: String?) {
        val hub = DiscoveredHub.create(
            name = name ?: "Manual Hub",
            host = host,
            port = port,
            method = HubDiscoveryMethod.MANUAL
        )
        addHubInternal(hub)
    }

    override fun removeHub(hubId: String) {
        hubs.remove(hubId)
        updateHubsFlow()
        notifyHubLost(hubId)
        emitEvent(HubDiscoveryEvent.HubLost(hubId))
    }

    override fun clearHubs() {
        hubs.clear()
        updateHubsFlow()
    }

    override fun getHub(hubId: String): DiscoveredHub? {
        return hubs[hubId]
    }

    override fun getReachableHubs(): List<DiscoveredHub> {
        return hubs.values.filter { it.isReachable }
    }

    override fun addListener(listener: HubDiscoveryListener) {
        synchronized(listeners) {
            listeners.add(listener)
        }
    }

    override fun removeListener(listener: HubDiscoveryListener) {
        synchronized(listeners) {
            listeners.remove(listener)
        }
    }

    private fun handleTimeout() {
        stopDiscovery()
        emitEvent(HubDiscoveryEvent.Timeout)
    }

    private fun notifyHubFound(hub: DiscoveredHub) {
        synchronized(listeners) {
            listeners.forEach { it.onHubFound(hub) }
        }
    }

    private fun notifyHubLost(hubId: String) {
        synchronized(listeners) {
            listeners.forEach { it.onHubLost(hubId) }
        }
    }

    private fun notifyStateChanged() {
        synchronized(listeners) {
            listeners.forEach { it.onStateChanged(_stateFlow.value) }
        }
    }

    private fun notifyError(error: Throwable) {
        synchronized(listeners) {
            listeners.forEach { it.onError(error) }
        }
    }

    private fun emitEvent(event: HubDiscoveryEvent) {
        scope.launch {
            _eventsFlow.emit(event)
        }
    }

    override fun cleanup() {
        stopDiscovery()
        scope.cancel()
        httpClient.dispatcher.executorService.shutdown()
        httpClient.connectionPool.evictAll()
    }
}

/*
 * 鏡 Kagami Hub Discovery Service
 * h(x) >= 0. Always.
 */
