/**
 * Mesh Command Router - Routes commands through the mesh network
 *
 * Colony: Nexus (e4) - Integration
 *
 * Routes commands through the Kagami mesh network instead of HTTP.
 * Commands are signed with Ed25519 and routed to Hub peers.
 *
 * Architecture:
 *   MeshCommandRouter -> MeshTransport (WebSocket) -> Hub
 *                    -> MeshService (Ed25519 signing, XChaCha20 encryption)
 *
 * Migration Note (Jan 2026):
 *   This router provides mesh-first routing with HTTP fallback.
 *   Once all devices are mesh-enabled, HTTP fallback will be removed.
 *
 * h(x) >= 0. Always.
 */

package com.kagami.android.services

import android.util.Log
import com.kagami.android.data.Result
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.util.UUID
import java.util.concurrent.ConcurrentLinkedQueue
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Commands that can be sent through the mesh network.
 */
@Serializable
sealed class MeshCommand {
    abstract val commandType: String

    // Device Control
    @Serializable
    data class SetLights(val level: Int, val rooms: List<String>?) : MeshCommand() {
        override val commandType = "device.lights.set"
    }

    @Serializable
    data class TvControl(val action: String, val preset: Int? = null) : MeshCommand() {
        override val commandType = "device.tv.control"
    }

    @Serializable
    data class Fireplace(val on: Boolean) : MeshCommand() {
        override val commandType = "device.fireplace.toggle"
    }

    @Serializable
    data class Shades(val action: String, val rooms: List<String>?) : MeshCommand() {
        override val commandType = "device.shades.control"
    }

    @Serializable
    data object LockAll : MeshCommand() {
        override val commandType = "device.locks.lockAll"
    }

    @Serializable
    data class Unlock(val lockId: String) : MeshCommand() {
        override val commandType = "device.locks.unlock"
    }

    @Serializable
    data class SetTemperature(val temp: Double, val room: String) : MeshCommand() {
        override val commandType = "device.climate.set"
    }

    // Scenes
    @Serializable
    data class ExecuteScene(val sceneId: String) : MeshCommand() {
        override val commandType = "scene.execute"
    }

    @Serializable
    data object ExitMovieMode : MeshCommand() {
        override val commandType = "scene.exitMovieMode"
    }

    // Audio
    @Serializable
    data class Announce(val message: String, val rooms: List<String>?) : MeshCommand() {
        override val commandType = "audio.announce"
    }

    // Status
    @Serializable
    data object HealthCheck : MeshCommand() {
        override val commandType = "status.health"
    }

    @Serializable
    data object FetchRooms : MeshCommand() {
        override val commandType = "status.rooms"
    }

    @Serializable
    data object FetchStatus : MeshCommand() {
        override val commandType = "status.home"
    }
}

/**
 * Response from a mesh command.
 */
@Serializable
data class MeshCommandResponse(
    val success: Boolean,
    val commandId: String,
    val result: String? = null,
    val error: String? = null,
    val timestamp: Long = System.currentTimeMillis()
)

/**
 * Queued command for offline support.
 */
private data class QueuedCommand(
    val id: String,
    val command: MeshCommand,
    val timestamp: Long
)

/**
 * Routes commands through the mesh network with Ed25519 signatures.
 *
 * The router:
 * 1. Discovers Hub peers via the HubDiscoveryService
 * 2. Signs commands with the local Ed25519 identity
 * 3. Encrypts payloads with XChaCha20-Poly1305
 * 4. Sends via the MeshTransport WebSocket layer
 * 5. Validates responses
 *
 * Falls back to legacy HTTP if mesh is unavailable (for migration).
 */
@Singleton
class MeshCommandRouter @Inject constructor(
    private val meshService: MeshService,
    private val meshTransport: MeshTransport,
    private val hubDiscoveryService: HubDiscoveryService
) {

    companion object {
        private const val TAG = "MeshCommandRouter"
        private const val MAX_QUEUE_SIZE = 100
        private const val COMMAND_TIMEOUT_MS = 30_000L
    }

    private val mutex = Mutex()
    private val json = Json { ignoreUnknownKeys = true }
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    // Hub connections: peerId -> encryption key
    private val hubKeys = mutableMapOf<String, String>()
    private var x25519SecretKey: String? = null
    private var x25519PublicKey: String? = null

    // Command queue for offline support
    private val commandQueue = ConcurrentLinkedQueue<QueuedCommand>()

    // State
    private val _isConnected = MutableStateFlow(false)
    val isConnected: StateFlow<Boolean> = _isConnected

    private val _connectedHubs = MutableStateFlow<List<String>>(emptyList())
    val connectedHubs: StateFlow<List<String>> = _connectedHubs

    private val _pendingCommands = MutableStateFlow(0)
    val pendingCommands: StateFlow<Int> = _pendingCommands

    init {
        // Observe transport connection state
        scope.launch {
            meshTransport.connectedHubs.collect { hubs ->
                _connectedHubs.value = hubs.toList()
                _isConnected.value = hubs.isNotEmpty()

                // Process queued commands when hub connects
                if (hubs.isNotEmpty() && commandQueue.isNotEmpty()) {
                    processQueue()
                }
            }
        }

        // Observe transport events
        scope.launch {
            meshTransport.connectionEvents.collect { event ->
                when (event) {
                    is MeshTransportEvent.Connected -> {
                        Log.i(TAG, "Hub connected: ${event.hubPeerId.take(16)}...")
                    }
                    is MeshTransportEvent.Disconnected -> {
                        Log.w(TAG, "Hub disconnected: ${event.hubPeerId.take(16)}... - ${event.reason}")
                        hubKeys.remove(event.hubPeerId)
                    }
                    is MeshTransportEvent.ReconnectFailed -> {
                        Log.e(TAG, "Hub reconnection failed: ${event.hubPeerId.take(16)}...")
                    }
                    else -> {}
                }
            }
        }
    }

    /**
     * Initialize the router and start Hub discovery.
     */
    suspend fun initialize(): Result<Unit> = withContext(Dispatchers.IO) {
        mutex.withLock {
            try {
                // Ensure mesh service is initialized
                if (!meshService.isInitialized.value) {
                    val initResult = meshService.initialize()
                    if (initResult is Result.Error) {
                        return@withContext Result.error("Mesh service initialization failed: ${initResult.message}")
                    }
                }

                // Generate X25519 keypair for hub encryption
                val keyPair = meshService.generateX25519KeyPair()
                x25519SecretKey = keyPair.first
                x25519PublicKey = keyPair.second

                Log.i(TAG, "MeshCommandRouter initialized. Peer ID: ${meshService.peerId}")

                // Start Hub discovery
                hubDiscoveryService.startDiscovery()

                // Auto-connect to discovered hubs
                scope.launch {
                    autoConnectToDiscoveredHubs()
                }

                Result.success(Unit)
            } catch (e: Exception) {
                Log.e(TAG, "Failed to initialize MeshCommandRouter", e)
                Result.error(e)
            }
        }
    }

    /**
     * Auto-connect to discovered Hubs as they appear.
     */
    private suspend fun autoConnectToDiscoveredHubs() {
        hubDiscoveryService.discoveredHubs.collect { hubs ->
            hubs.values.forEach { hub ->
                // Skip if already connected
                if (hub.peerId != null && meshTransport.isConnectedTo(hub.peerId)) {
                    return@forEach
                }

                // Get connection info and connect
                hub.peerId?.let { peerId ->
                    if (!meshTransport.isConnectedTo(peerId)) {
                        scope.launch {
                            connectToHub(hub.id)
                        }
                    }
                } ?: run {
                    // Need to fetch mesh info first
                    scope.launch {
                        connectToHub(hub.id)
                    }
                }
            }
        }
    }

    /**
     * Connect to a discovered Hub.
     */
    suspend fun connectToHub(hubId: String): Result<Unit> = withContext(Dispatchers.IO) {
        try {
            val connectionInfoResult = hubDiscoveryService.getHubConnectionInfo(hubId)
            if (connectionInfoResult is Result.Error) {
                return@withContext Result.error("Failed to get Hub connection info: ${connectionInfoResult.message}")
            }

            val connectionInfo = (connectionInfoResult as Result.Success).data
            val secretKey = x25519SecretKey
                ?: return@withContext Result.error("X25519 key not generated")

            // Derive shared encryption key
            val sharedKeyResult = meshService.deriveSharedKey(secretKey, connectionInfo.publicKeyX25519)
            if (sharedKeyResult is Result.Error) {
                return@withContext Result.error("Key derivation failed: ${sharedKeyResult.message}")
            }

            val sharedKey = (sharedKeyResult as Result.Success).data
            hubKeys[connectionInfo.peerId] = sharedKey

            // Connect via transport
            val connectResult = meshTransport.connectToHub(
                connectionInfo.copy(sharedKey = sharedKey)
            )

            if (connectResult is Result.Error) {
                hubKeys.remove(connectionInfo.peerId)
                return@withContext Result.error("Transport connection failed: ${connectResult.message}")
            }

            Log.i(TAG, "Connected to Hub ${connectionInfo.peerId.take(16)}...")
            Result.success(Unit)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to connect to Hub", e)
            Result.error(e)
        }
    }

    /**
     * Manually register a Hub peer for command routing.
     *
     * @param peerId The Hub's Ed25519 public key (hex)
     * @param publicKeyX25519 The Hub's X25519 public key for encryption
     * @param host Hub host address
     * @param port Hub mesh port
     */
    suspend fun registerHub(
        peerId: String,
        publicKeyX25519: String,
        host: String,
        port: Int
    ): Result<Unit> = withContext(Dispatchers.IO) {
        mutex.withLock {
            try {
                val secretKey = x25519SecretKey
                    ?: return@withContext Result.error("X25519 key not generated")

                // Derive shared encryption key
                val sharedKeyResult = meshService.deriveSharedKey(secretKey, publicKeyX25519)
                if (sharedKeyResult is Result.Error) {
                    return@withContext Result.error("Key derivation failed: ${sharedKeyResult.message}")
                }

                val sharedKey = (sharedKeyResult as Result.Success).data
                hubKeys[peerId] = sharedKey

                // Connect via transport
                val connectionInfo = HubConnectionInfo(
                    peerId = peerId,
                    host = host,
                    port = port,
                    publicKeyX25519 = publicKeyX25519,
                    sharedKey = sharedKey
                )

                val connectResult = meshTransport.connectToHub(connectionInfo)
                if (connectResult is Result.Error) {
                    hubKeys.remove(peerId)
                    return@withContext Result.error("Transport connection failed: ${connectResult.message}")
                }

                Log.i(TAG, "Registered Hub peer: ${peerId.take(16)}...")
                Result.success(Unit)
            } catch (e: Exception) {
                Log.e(TAG, "Failed to register Hub", e)
                Result.error(e)
            }
        }
    }

    /**
     * Unregister a Hub peer.
     */
    suspend fun unregisterHub(peerId: String) {
        hubKeys.remove(peerId)
        meshTransport.disconnectFromHub(peerId)
    }

    /**
     * Execute a command through the mesh network.
     *
     * The command is:
     * 1. Serialized to JSON
     * 2. Signed with Ed25519
     * 3. Encrypted with the Hub's shared key
     * 4. Sent via WebSocket transport
     * 5. Response decrypted and verified
     *
     * @param command The command to execute
     * @return The command response
     */
    suspend fun execute(command: MeshCommand): Result<MeshCommandResponse> =
        withContext(Dispatchers.IO) {
            if (!meshService.isInitialized.value) {
                return@withContext Result.error("Mesh service not initialized")
            }

            _pendingCommands.value++

            try {
                val commandId = UUID.randomUUID().toString()

                // Get connected Hub
                val hubPeerId = meshTransport.connectedHubs.value.firstOrNull()
                val encryptionKey = hubPeerId?.let { hubKeys[it] }

                if (hubPeerId == null || encryptionKey == null) {
                    // Queue command for when Hub connects
                    queueCommand(command, commandId)
                    return@withContext Result.success(
                        MeshCommandResponse(
                            success = false,
                            commandId = commandId,
                            error = "No Hub available - command queued"
                        )
                    )
                }

                // Build and sign command envelope
                val envelope = buildCommandEnvelope(command, commandId)
                val envelopeBytes = envelope.toByteArray(Charsets.UTF_8)

                val signatureResult = meshService.sign(envelopeBytes)
                if (signatureResult is Result.Error) {
                    return@withContext Result.error("Signing failed: ${signatureResult.message}")
                }
                val signature = (signatureResult as Result.Success).data

                // Encrypt payload
                val encryptResult = meshService.encrypt(encryptionKey, envelopeBytes)
                if (encryptResult is Result.Error) {
                    return@withContext Result.error("Encryption failed: ${encryptResult.message}")
                }
                val encryptedPayload = (encryptResult as Result.Success).data

                // Send via transport and wait for response
                val transportResult = meshTransport.sendAndWait(
                    hubPeerId = hubPeerId,
                    commandType = command.commandType,
                    payload = encryptedPayload,
                    signature = signature,
                    timeoutMs = COMMAND_TIMEOUT_MS
                )

                if (transportResult is Result.Error) {
                    return@withContext Result.error("Transport failed: ${transportResult.message}")
                }

                val responseEnvelope = (transportResult as Result.Success).data

                // Convert response
                Result.success(
                    MeshCommandResponse(
                        success = responseEnvelope.success,
                        commandId = responseEnvelope.id,
                        result = responseEnvelope.result,
                        error = responseEnvelope.error,
                        timestamp = responseEnvelope.timestamp
                    )
                )

            } catch (e: Exception) {
                Log.e(TAG, "Command execution failed", e)
                Result.error(e)
            } finally {
                _pendingCommands.value--
            }
        }

    /**
     * Execute with automatic retry and fallback.
     *
     * @param command The mesh command
     * @param legacyFallback Optional fallback function for HTTP execution
     */
    suspend fun executeWithFallback(
        command: MeshCommand,
        legacyFallback: (suspend () -> Result<Boolean>)? = null
    ): Result<Boolean> = withContext(Dispatchers.IO) {
        val meshResult = execute(command)

        when (meshResult) {
            is Result.Success -> {
                if (meshResult.data.success) {
                    return@withContext Result.success(true)
                }
            }
            is Result.Error -> {
                Log.d(TAG, "Mesh execution failed: ${meshResult.message}. Trying fallback...")
            }
            else -> {}
        }

        // Try legacy HTTP fallback if provided
        legacyFallback?.invoke() ?: Result.success(false)
    }

    private fun buildCommandEnvelope(command: MeshCommand, commandId: String): String {
        return json.encodeToString(
            CommandEnvelope(
                id = commandId,
                type = command.commandType,
                payload = json.encodeToString(MeshCommand.serializer(), command),
                timestamp = System.currentTimeMillis(),
                peerId = meshService.peerId ?: ""
            )
        )
    }

    private fun queueCommand(command: MeshCommand, id: String) {
        val queued = QueuedCommand(id, command, System.currentTimeMillis())

        if (commandQueue.size >= MAX_QUEUE_SIZE) {
            commandQueue.poll() // Remove oldest
        }

        commandQueue.offer(queued)
        Log.d(TAG, "Queued command $id (queue size: ${commandQueue.size})")
    }

    /**
     * Process queued commands when Hub becomes available.
     */
    suspend fun processQueue() {
        if (meshTransport.connectedHubs.value.isEmpty()) return

        Log.d(TAG, "Processing ${commandQueue.size} queued commands")

        while (commandQueue.isNotEmpty()) {
            val queued = commandQueue.poll() ?: break
            try {
                execute(queued.command)
            } catch (e: Exception) {
                Log.e(TAG, "Failed to process queued command ${queued.id}", e)
            }
        }
    }

    /**
     * Restart Hub discovery.
     */
    fun restartDiscovery() {
        hubDiscoveryService.startDiscovery()
    }

    /**
     * Get the number of queued commands.
     */
    val queuedCommandCount: Int
        get() = commandQueue.size

    /**
     * Clean up resources.
     */
    fun destroy() {
        scope.cancel()
        meshTransport.destroy()
        hubDiscoveryService.destroy()
    }
}

@Serializable
private data class CommandEnvelope(
    val id: String,
    val type: String,
    val payload: String,
    val timestamp: Long,
    val peerId: String
)

/*
 * Mirror
 *
 * The mesh command router provides a cryptographically secure alternative
 * to legacy HTTP API calls. Commands are authenticated with Ed25519 signatures
 * and encrypted with XChaCha20-Poly1305.
 *
 * Real transport is now implemented via WebSocket connections to Hub peers.
 * Hub discovery uses mDNS for zero-configuration networking.
 *
 * h(x) >= 0. Always.
 */
