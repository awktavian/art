/**
 * Mesh Transport - WebSocket-based Mesh Network Transport
 *
 * Colony: Nexus (e4) - Integration
 *
 * Provides real WebSocket transport for mesh network communication:
 * - Connects to Hub via WebSocket
 * - Handles message send/receive with timeouts
 * - Automatic reconnection with circuit breaker
 * - Ed25519 signed and XChaCha20-Poly1305 encrypted messages
 *
 * h(x) >= 0. Always.
 */

package com.kagami.android.services

import android.util.Log
import com.kagami.android.data.Result
import kotlinx.coroutines.*
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import okhttp3.*
import java.util.UUID
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.TimeUnit
import javax.inject.Inject
import javax.inject.Named
import javax.inject.Singleton

/**
 * Mesh transport message envelope.
 */
@Serializable
data class MeshEnvelope(
    val id: String,
    val senderId: String,
    val recipientId: String,
    val commandType: String,
    val payload: String,
    val signature: String,
    val timestamp: Long
)

/**
 * Mesh response envelope.
 */
@Serializable
data class MeshResponseEnvelope(
    val id: String,
    val success: Boolean,
    val result: String? = null,
    val error: String? = null,
    val signature: String? = null,
    val timestamp: Long = System.currentTimeMillis()
)

/**
 * Pending request tracker for request/response correlation.
 */
private data class PendingRequest(
    val id: String,
    val responseChannel: Channel<MeshResponseEnvelope>,
    val timestamp: Long = System.currentTimeMillis()
)

/**
 * Connection info for a Hub peer.
 */
data class HubConnectionInfo(
    val peerId: String,
    val host: String,
    val port: Int,
    val publicKeyX25519: String,
    val sharedKey: String? = null
) {
    val wsUrl: String get() = "ws://$host:$port/mesh"
}

/**
 * WebSocket-based mesh transport.
 *
 * Manages WebSocket connections to Hub peers and handles:
 * - Connection lifecycle with circuit breaker pattern
 * - Request/response correlation with timeouts
 * - Message signing and encryption via MeshService
 */
@Singleton
class MeshTransport @Inject constructor(
    @Named("websocket") private val wsClient: OkHttpClient,
    private val meshService: MeshService
) {

    companion object {
        private const val TAG = "MeshTransport"
        private const val DEFAULT_TIMEOUT_MS = 30_000L
        private const val PING_INTERVAL_MS = 30_000L
        private const val RECONNECT_DELAY_MS = 5_000L
        private const val MAX_RECONNECT_ATTEMPTS = 5
    }

    private val json = Json { ignoreUnknownKeys = true }
    private val mutex = Mutex()
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    // Hub connections: peerId -> WebSocket
    private val hubConnections = ConcurrentHashMap<String, WebSocket>()
    private val hubConnectionInfo = ConcurrentHashMap<String, HubConnectionInfo>()

    // Pending requests for request/response correlation
    private val pendingRequests = ConcurrentHashMap<String, PendingRequest>()

    // Connection state
    private val _connectedHubs = MutableStateFlow<Set<String>>(emptySet())
    val connectedHubs: StateFlow<Set<String>> = _connectedHubs.asStateFlow()

    private val _connectionEvents = MutableSharedFlow<MeshTransportEvent>(
        replay = 0,
        extraBufferCapacity = 16
    )
    val connectionEvents: SharedFlow<MeshTransportEvent> = _connectionEvents.asSharedFlow()

    // Reconnection tracking
    private val reconnectAttempts = ConcurrentHashMap<String, Int>()

    /**
     * Connect to a Hub peer.
     *
     * @param info Hub connection information
     * @return Result indicating success or failure
     */
    suspend fun connectToHub(info: HubConnectionInfo): Result<Unit> = withContext(Dispatchers.IO) {
        mutex.withLock {
            if (hubConnections.containsKey(info.peerId)) {
                Log.d(TAG, "Already connected to Hub ${info.peerId.take(16)}...")
                return@withContext Result.success(Unit)
            }

            try {
                // Derive shared key if not provided
                val connectionWithKey = if (info.sharedKey == null) {
                    val keyPair = meshService.generateX25519KeyPair()
                    val derivedKey = meshService.deriveSharedKey(keyPair.first, info.publicKeyX25519)
                    if (derivedKey is Result.Error) {
                        return@withContext Result.error("Key derivation failed: ${derivedKey.message}")
                    }
                    info.copy(sharedKey = (derivedKey as Result.Success).data)
                } else {
                    info
                }

                hubConnectionInfo[info.peerId] = connectionWithKey

                val request = Request.Builder()
                    .url(info.wsUrl)
                    .build()

                val webSocket = wsClient.newWebSocket(request, createWebSocketListener(info.peerId))
                hubConnections[info.peerId] = webSocket

                meshService.onConnecting()
                Log.i(TAG, "Connecting to Hub ${info.peerId.take(16)}... at ${info.wsUrl}")

                Result.success(Unit)
            } catch (e: Exception) {
                Log.e(TAG, "Failed to connect to Hub", e)
                Result.error(e)
            }
        }
    }

    /**
     * Disconnect from a Hub peer.
     */
    suspend fun disconnectFromHub(peerId: String) {
        mutex.withLock {
            hubConnections.remove(peerId)?.close(1000, "Disconnect requested")
            hubConnectionInfo.remove(peerId)
            reconnectAttempts.remove(peerId)
            updateConnectedHubs()
            meshService.onDisconnected("User requested disconnect")
        }
    }

    /**
     * Disconnect from all Hubs.
     */
    suspend fun disconnectAll() {
        mutex.withLock {
            hubConnections.forEach { (_, ws) ->
                ws.close(1000, "Disconnect all requested")
            }
            hubConnections.clear()
            hubConnectionInfo.clear()
            reconnectAttempts.clear()
            _connectedHubs.value = emptySet()
        }
    }

    /**
     * Send a message to a Hub and wait for response.
     *
     * @param hubPeerId Target Hub peer ID
     * @param commandType Command type identifier
     * @param payload Encrypted payload
     * @param signature Ed25519 signature
     * @param timeoutMs Timeout in milliseconds
     * @return Response envelope or error
     */
    suspend fun sendAndWait(
        hubPeerId: String,
        commandType: String,
        payload: String,
        signature: String,
        timeoutMs: Long = DEFAULT_TIMEOUT_MS
    ): Result<MeshResponseEnvelope> = withContext(Dispatchers.IO) {
        val webSocket = hubConnections[hubPeerId]
            ?: return@withContext Result.error("Not connected to Hub $hubPeerId")

        val peerId = meshService.peerId
            ?: return@withContext Result.error("Mesh service not initialized")

        val messageId = UUID.randomUUID().toString()

        // Create envelope
        val envelope = MeshEnvelope(
            id = messageId,
            senderId = peerId,
            recipientId = hubPeerId,
            commandType = commandType,
            payload = payload,
            signature = signature,
            timestamp = System.currentTimeMillis()
        )

        // Register pending request
        val responseChannel = Channel<MeshResponseEnvelope>(1)
        val pendingRequest = PendingRequest(messageId, responseChannel)
        pendingRequests[messageId] = pendingRequest

        try {
            // Send message
            val messageJson = json.encodeToString(envelope)
            val sent = webSocket.send(messageJson)

            if (!sent) {
                pendingRequests.remove(messageId)
                return@withContext Result.error("Failed to send message")
            }

            Log.d(TAG, "Sent message $messageId to Hub ${hubPeerId.take(16)}...")

            // Wait for response with timeout
            val response = withTimeoutOrNull(timeoutMs) {
                responseChannel.receive()
            }

            pendingRequests.remove(messageId)

            if (response == null) {
                return@withContext Result.error("Request timed out after ${timeoutMs}ms")
            }

            Result.success(response)

        } catch (e: Exception) {
            pendingRequests.remove(messageId)
            Log.e(TAG, "Send failed", e)
            Result.error(e)
        }
    }

    /**
     * Send a fire-and-forget message (no response expected).
     */
    suspend fun sendFireAndForget(
        hubPeerId: String,
        commandType: String,
        payload: String,
        signature: String
    ): Result<Unit> = withContext(Dispatchers.IO) {
        val webSocket = hubConnections[hubPeerId]
            ?: return@withContext Result.error("Not connected to Hub $hubPeerId")

        val peerId = meshService.peerId
            ?: return@withContext Result.error("Mesh service not initialized")

        val envelope = MeshEnvelope(
            id = UUID.randomUUID().toString(),
            senderId = peerId,
            recipientId = hubPeerId,
            commandType = commandType,
            payload = payload,
            signature = signature,
            timestamp = System.currentTimeMillis()
        )

        val messageJson = json.encodeToString(envelope)
        val sent = webSocket.send(messageJson)

        if (sent) Result.success(Unit) else Result.error("Failed to send message")
    }

    /**
     * Check if connected to a specific Hub.
     */
    fun isConnectedTo(hubPeerId: String): Boolean {
        return hubConnections.containsKey(hubPeerId)
    }

    /**
     * Get connection info for a Hub.
     */
    fun getConnectionInfo(hubPeerId: String): HubConnectionInfo? {
        return hubConnectionInfo[hubPeerId]
    }

    private fun createWebSocketListener(hubPeerId: String): WebSocketListener {
        return object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                Log.i(TAG, "WebSocket connected to Hub ${hubPeerId.take(16)}...")
                scope.launch {
                    meshService.onConnected()
                    updateConnectedHubs()
                    reconnectAttempts[hubPeerId] = 0
                    _connectionEvents.emit(MeshTransportEvent.Connected(hubPeerId))
                }
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                handleMessage(hubPeerId, text)
            }

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                Log.d(TAG, "WebSocket closing: $code - $reason")
                webSocket.close(1000, null)
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                Log.d(TAG, "WebSocket closed: $code - $reason")
                scope.launch {
                    handleDisconnect(hubPeerId, reason)
                }
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                Log.e(TAG, "WebSocket failure", t)
                scope.launch {
                    handleDisconnect(hubPeerId, t.message ?: "Unknown error")
                }
            }
        }
    }

    private fun handleMessage(hubPeerId: String, text: String) {
        scope.launch {
            try {
                val response = json.decodeFromString<MeshResponseEnvelope>(text)

                // Check if this is a response to a pending request
                val pending = pendingRequests[response.id]
                if (pending != null) {
                    pending.responseChannel.send(response)
                } else {
                    // This is an unsolicited message (e.g., push notification)
                    _connectionEvents.emit(MeshTransportEvent.Message(hubPeerId, response))
                }
            } catch (e: Exception) {
                Log.w(TAG, "Failed to parse message from Hub", e)
                _connectionEvents.emit(MeshTransportEvent.Error(hubPeerId, "Parse error: ${e.message}"))
            }
        }
    }

    private suspend fun handleDisconnect(hubPeerId: String, reason: String) {
        mutex.withLock {
            hubConnections.remove(hubPeerId)
            updateConnectedHubs()
        }

        meshService.onConnectionFailed(reason)
        _connectionEvents.emit(MeshTransportEvent.Disconnected(hubPeerId, reason))

        // Attempt reconnection if we have connection info
        val info = hubConnectionInfo[hubPeerId]
        if (info != null) {
            scheduleReconnect(hubPeerId, info)
        }
    }

    private fun scheduleReconnect(hubPeerId: String, info: HubConnectionInfo) {
        val attempts = reconnectAttempts.getOrDefault(hubPeerId, 0)
        if (attempts >= MAX_RECONNECT_ATTEMPTS) {
            Log.w(TAG, "Max reconnect attempts reached for Hub ${hubPeerId.take(16)}")
            scope.launch {
                _connectionEvents.emit(MeshTransportEvent.ReconnectFailed(hubPeerId))
            }
            return
        }

        reconnectAttempts[hubPeerId] = attempts + 1
        val delayMs = RECONNECT_DELAY_MS * (attempts + 1)

        Log.d(TAG, "Scheduling reconnect to Hub ${hubPeerId.take(16)} in ${delayMs}ms (attempt ${attempts + 1})")

        scope.launch {
            _connectionEvents.emit(
                MeshTransportEvent.Reconnecting(hubPeerId, attempts + 1, delayMs)
            )
            delay(delayMs)

            if (meshService.shouldAttemptConnection()) {
                connectToHub(info)
            }
        }
    }

    private fun updateConnectedHubs() {
        _connectedHubs.value = hubConnections.keys.toSet()
    }

    /**
     * Clean up resources.
     */
    fun destroy() {
        scope.launch {
            disconnectAll()
        }
        scope.cancel()
        pendingRequests.values.forEach { it.responseChannel.close() }
        pendingRequests.clear()
    }
}

/**
 * Events emitted by the mesh transport.
 */
sealed class MeshTransportEvent {
    data class Connected(val hubPeerId: String) : MeshTransportEvent()
    data class Disconnected(val hubPeerId: String, val reason: String) : MeshTransportEvent()
    data class Reconnecting(val hubPeerId: String, val attempt: Int, val delayMs: Long) : MeshTransportEvent()
    data class ReconnectFailed(val hubPeerId: String) : MeshTransportEvent()
    data class Message(val hubPeerId: String, val response: MeshResponseEnvelope) : MeshTransportEvent()
    data class Error(val hubPeerId: String, val message: String) : MeshTransportEvent()
}

/*
 * Mirror
 *
 * The mesh transport provides the actual WebSocket connection to Hub peers.
 * Messages are signed with Ed25519 and encrypted with XChaCha20-Poly1305.
 * The circuit breaker pattern prevents cascade failures.
 *
 * h(x) >= 0. Always.
 */
