/**
 * Hub Discovery Service - mDNS-based Kagami Hub Discovery
 *
 * Colony: Nexus (e4) - Integration
 *
 * Discovers Kagami Hub devices on the local network using:
 * - Android NsdManager for mDNS service discovery
 * - Direct IP probing as fallback
 * - Automatic Hub registration with MeshCommandRouter
 *
 * h(x) >= 0. Always.
 */

package com.kagami.android.services

import android.content.Context
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.util.Log
import com.kagami.android.data.Result
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import okhttp3.OkHttpClient
import okhttp3.Request
import java.util.concurrent.ConcurrentHashMap
import javax.inject.Inject
import javax.inject.Named
import javax.inject.Singleton

/**
 * Discovered Hub information.
 */
@Serializable
data class DiscoveredHub(
    val id: String,
    val name: String,
    val host: String,
    val port: Int,
    val meshPort: Int = 8081,
    val peerId: String? = null,
    val publicKeyX25519: String? = null,
    val version: String? = null,
    val location: String? = null,
    val discoveryMethod: DiscoveryMethod = DiscoveryMethod.MDNS
)

enum class DiscoveryMethod {
    MDNS,
    DIRECT,
    CACHED
}

/**
 * Hub mesh info returned from Hub's /mesh/info endpoint.
 */
@Serializable
private data class HubMeshInfo(
    val peer_id: String,
    val public_key_x25519: String,
    val mesh_port: Int,
    val name: String? = null,
    val location: String? = null,
    val version: String? = null
)

/**
 * Service for discovering Kagami Hub devices on the network.
 *
 * Uses Android NsdManager for mDNS discovery with fallback to direct probing.
 * Automatically fetches mesh cryptographic info from discovered Hubs and
 * registers them with the MeshCommandRouter.
 */
@Singleton
class HubDiscoveryService @Inject constructor(
    @ApplicationContext private val context: Context,
    @Named("api") private val httpClient: OkHttpClient
) {

    companion object {
        private const val TAG = "HubDiscoveryService"
        private const val SERVICE_TYPE = "_kagami-hub._tcp."
        private const val MESH_SERVICE_TYPE = "_kagami-mesh._tcp."
        private const val DISCOVERY_TIMEOUT_MS = 15_000L
        private const val PREFS_NAME = "kagami_hub_discovery"
        private const val LAST_HUBS_KEY = "last_discovered_hubs"
    }

    private val json = Json { ignoreUnknownKeys = true }
    private val mutex = Mutex()
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    private var nsdManager: NsdManager? = null
    private var discoveryListener: NsdManager.DiscoveryListener? = null
    private var meshDiscoveryListener: NsdManager.DiscoveryListener? = null

    // Discovered Hubs
    private val _discoveredHubs = MutableStateFlow<Map<String, DiscoveredHub>>(emptyMap())
    val discoveredHubs: StateFlow<Map<String, DiscoveredHub>> = _discoveredHubs.asStateFlow()

    // Discovery state
    private val _isDiscovering = MutableStateFlow(false)
    val isDiscovering: StateFlow<Boolean> = _isDiscovering.asStateFlow()

    private val _discoveryError = MutableStateFlow<String?>(null)
    val discoveryError: StateFlow<String?> = _discoveryError.asStateFlow()

    // Pending resolutions to track concurrent resolves
    private val pendingResolutions = ConcurrentHashMap<String, Boolean>()

    /**
     * Start discovering Hub devices on the network.
     *
     * Combines mDNS discovery with direct probing of known addresses.
     * Discovery runs for DISCOVERY_TIMEOUT_MS before automatically stopping.
     */
    fun startDiscovery() {
        if (_isDiscovering.value) {
            Log.d(TAG, "Discovery already in progress")
            return
        }

        _isDiscovering.value = true
        _discoveryError.value = null
        _discoveredHubs.value = emptyMap()

        scope.launch {
            // Load cached hubs first
            loadCachedHubs()

            // Start mDNS discovery
            startMdnsDiscovery()

            // Start direct probing in parallel
            launch { probeDirectAddresses() }

            // Auto-stop after timeout
            delay(DISCOVERY_TIMEOUT_MS)
            stopDiscovery()
        }
    }

    /**
     * Stop active discovery.
     */
    fun stopDiscovery() {
        if (!_isDiscovering.value) return

        try {
            discoveryListener?.let { listener ->
                nsdManager?.stopServiceDiscovery(listener)
            }
            meshDiscoveryListener?.let { listener ->
                nsdManager?.stopServiceDiscovery(listener)
            }
        } catch (e: Exception) {
            Log.w(TAG, "Error stopping discovery: ${e.message}")
        }

        discoveryListener = null
        meshDiscoveryListener = null
        _isDiscovering.value = false

        // Save discovered hubs
        scope.launch { saveCachedHubs() }

        Log.d(TAG, "Discovery stopped. Found ${_discoveredHubs.value.size} hubs")
    }

    /**
     * Get mesh connection info for a discovered Hub.
     *
     * Fetches cryptographic info needed for mesh connection if not already cached.
     */
    suspend fun getHubConnectionInfo(hubId: String): Result<HubConnectionInfo> =
        withContext(Dispatchers.IO) {
            val hub = _discoveredHubs.value[hubId]
                ?: return@withContext Result.error("Hub not found: $hubId")

            // If we already have mesh info, return it
            if (hub.peerId != null && hub.publicKeyX25519 != null) {
                return@withContext Result.success(
                    HubConnectionInfo(
                        peerId = hub.peerId,
                        host = hub.host,
                        port = hub.meshPort,
                        publicKeyX25519 = hub.publicKeyX25519
                    )
                )
            }

            // Fetch mesh info from Hub
            fetchHubMeshInfo(hub)
        }

    /**
     * Refresh a specific Hub's information.
     */
    suspend fun refreshHub(hubId: String): Result<DiscoveredHub> = withContext(Dispatchers.IO) {
        val hub = _discoveredHubs.value[hubId]
            ?: return@withContext Result.error("Hub not found: $hubId")

        fetchHubMeshInfo(hub).map { connectionInfo ->
            val updated = hub.copy(
                peerId = connectionInfo.peerId,
                publicKeyX25519 = connectionInfo.publicKeyX25519
            )
            mutex.withLock {
                _discoveredHubs.value = _discoveredHubs.value + (hubId to updated)
            }
            updated
        }
    }

    private fun startMdnsDiscovery() {
        nsdManager = context.getSystemService(Context.NSD_SERVICE) as NsdManager

        // Discover _kagami-hub._tcp. services
        discoveryListener = createDiscoveryListener("Hub")
        try {
            nsdManager?.discoverServices(SERVICE_TYPE, NsdManager.PROTOCOL_DNS_SD, discoveryListener)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to start Hub mDNS discovery", e)
        }

        // Also discover _kagami-mesh._tcp. services (mesh-specific)
        meshDiscoveryListener = createDiscoveryListener("Mesh")
        try {
            nsdManager?.discoverServices(MESH_SERVICE_TYPE, NsdManager.PROTOCOL_DNS_SD, meshDiscoveryListener)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to start Mesh mDNS discovery", e)
        }
    }

    private fun createDiscoveryListener(tag: String): NsdManager.DiscoveryListener {
        return object : NsdManager.DiscoveryListener {
            override fun onDiscoveryStarted(serviceType: String) {
                Log.d(TAG, "[$tag] mDNS discovery started for $serviceType")
            }

            override fun onServiceFound(serviceInfo: NsdServiceInfo) {
                Log.d(TAG, "[$tag] Service found: ${serviceInfo.serviceName}")
                resolveService(serviceInfo)
            }

            override fun onServiceLost(serviceInfo: NsdServiceInfo) {
                Log.d(TAG, "[$tag] Service lost: ${serviceInfo.serviceName}")
                scope.launch {
                    val hubId = "${serviceInfo.serviceName}:unknown"
                    mutex.withLock {
                        _discoveredHubs.value = _discoveredHubs.value.filterKeys { it != hubId }
                    }
                }
            }

            override fun onDiscoveryStopped(serviceType: String) {
                Log.d(TAG, "[$tag] mDNS discovery stopped")
            }

            override fun onStartDiscoveryFailed(serviceType: String, errorCode: Int) {
                Log.e(TAG, "[$tag] mDNS discovery start failed: $errorCode")
                _discoveryError.value = "Discovery failed (error $errorCode)"
            }

            override fun onStopDiscoveryFailed(serviceType: String, errorCode: Int) {
                Log.w(TAG, "[$tag] mDNS discovery stop failed: $errorCode")
            }
        }
    }

    private fun resolveService(serviceInfo: NsdServiceInfo) {
        val resolutionKey = serviceInfo.serviceName

        // Prevent duplicate resolutions
        if (pendingResolutions.putIfAbsent(resolutionKey, true) != null) {
            return
        }

        nsdManager?.resolveService(serviceInfo, object : NsdManager.ResolveListener {
            override fun onServiceResolved(resolvedInfo: NsdServiceInfo) {
                pendingResolutions.remove(resolutionKey)

                val host = resolvedInfo.host?.hostAddress ?: return
                val port = resolvedInfo.port

                scope.launch {
                    processResolvedService(resolvedInfo.serviceName, host, port)
                }
            }

            override fun onResolveFailed(serviceInfo: NsdServiceInfo, errorCode: Int) {
                pendingResolutions.remove(resolutionKey)
                Log.e(TAG, "Service resolution failed for ${serviceInfo.serviceName}: $errorCode")
            }
        })
    }

    private suspend fun processResolvedService(name: String, host: String, port: Int) {
        val hubId = "$host:$port"

        // Create initial hub entry
        val hub = DiscoveredHub(
            id = hubId,
            name = name,
            host = host,
            port = port,
            discoveryMethod = DiscoveryMethod.MDNS
        )

        mutex.withLock {
            _discoveredHubs.value = _discoveredHubs.value + (hubId to hub)
        }

        // Fetch mesh info asynchronously
        scope.launch {
            fetchHubMeshInfo(hub).onSuccess { connectionInfo ->
                val updated = hub.copy(
                    peerId = connectionInfo.peerId,
                    publicKeyX25519 = connectionInfo.publicKeyX25519
                )
                mutex.withLock {
                    _discoveredHubs.value = _discoveredHubs.value + (hubId to updated)
                }
            }
        }
    }

    private suspend fun probeDirectAddresses() {
        // Common addresses to probe
        val candidates = listOf(
            "kagami-hub.local" to 8080,
            "kagami-hub.local" to 8081,
            "raspberrypi.local" to 8080,
            "192.168.1.100" to 8080,
            "192.168.1.50" to 8080,
            "192.168.1.1" to 8080
        )

        candidates.forEach { (host, port) ->
            try {
                if (probeHub(host, port)) {
                    processResolvedService("Kagami Hub", host, port)
                }
            } catch (e: Exception) {
                // Ignore probe failures
            }
        }
    }

    private suspend fun probeHub(host: String, port: Int): Boolean = withContext(Dispatchers.IO) {
        try {
            val request = Request.Builder()
                .url("http://$host:$port/health")
                .build()

            httpClient.newCall(request).execute().use { response ->
                response.isSuccessful
            }
        } catch (e: Exception) {
            false
        }
    }

    private suspend fun fetchHubMeshInfo(hub: DiscoveredHub): Result<HubConnectionInfo> =
        withContext(Dispatchers.IO) {
            try {
                val request = Request.Builder()
                    .url("http://${hub.host}:${hub.port}/mesh/info")
                    .build()

                httpClient.newCall(request).execute().use { response ->
                    if (!response.isSuccessful) {
                        return@withContext Result.error("Failed to fetch mesh info: ${response.code}")
                    }

                    val body = response.body?.string()
                        ?: return@withContext Result.error("Empty response")

                    val meshInfo = json.decodeFromString<HubMeshInfo>(body)

                    Result.success(
                        HubConnectionInfo(
                            peerId = meshInfo.peer_id,
                            host = hub.host,
                            port = meshInfo.mesh_port,
                            publicKeyX25519 = meshInfo.public_key_x25519
                        )
                    )
                }
            } catch (e: Exception) {
                Log.e(TAG, "Failed to fetch mesh info from ${hub.host}", e)
                Result.error(e)
            }
        }

    private suspend fun loadCachedHubs() {
        try {
            val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            val cachedJson = prefs.getString(LAST_HUBS_KEY, null) ?: return

            val cached = json.decodeFromString<List<DiscoveredHub>>(cachedJson)
            val hubMap = cached.associate {
                it.id to it.copy(discoveryMethod = DiscoveryMethod.CACHED)
            }

            mutex.withLock {
                _discoveredHubs.value = hubMap
            }

            Log.d(TAG, "Loaded ${cached.size} cached hubs")
        } catch (e: Exception) {
            Log.w(TAG, "Failed to load cached hubs", e)
        }
    }

    private suspend fun saveCachedHubs() {
        try {
            val hubs = _discoveredHubs.value.values.toList()
            val hubsJson = json.encodeToString(
                kotlinx.serialization.builtins.ListSerializer(DiscoveredHub.serializer()),
                hubs
            )

            context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                .edit()
                .putString(LAST_HUBS_KEY, hubsJson)
                .apply()

            Log.d(TAG, "Saved ${hubs.size} hubs to cache")
        } catch (e: Exception) {
            Log.w(TAG, "Failed to save cached hubs", e)
        }
    }

    /**
     * Clean up resources.
     */
    fun destroy() {
        stopDiscovery()
        scope.cancel()
    }
}

/*
 * Mirror
 *
 * Hub discovery enables the mesh network to find local Hub devices.
 * mDNS provides zero-configuration discovery on the local network.
 * Cached hubs enable quick reconnection on app restart.
 *
 * h(x) >= 0. Always.
 */
