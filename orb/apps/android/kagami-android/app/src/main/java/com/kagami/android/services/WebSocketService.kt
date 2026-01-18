/**
 * WebSocket Service - Real-time Connection Management
 *
 * Colony: Nexus (e4) - Integration
 *
 * Manages WebSocket connection lifecycle with:
 * - Exponential backoff retry strategy
 * - Thread-safe state management
 * - Event dispatching to consumers
 */

package com.kagami.android.services

import android.util.Log
import com.kagami.android.network.ApiConfig
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import org.json.JSONObject
import javax.inject.Inject
import javax.inject.Named
import javax.inject.Singleton
import kotlin.math.min
import kotlin.math.pow

/**
 * WebSocket message types received from server.
 */
sealed class WebSocketMessage {
    data class ContextUpdate(val safetyScore: Double?) : WebSocketMessage()
    data class HomeUpdate(val movieMode: Boolean) : WebSocketMessage()
    data class Unknown(val type: String, val data: JSONObject?) : WebSocketMessage()
    data class Error(val message: String) : WebSocketMessage()
}

/**
 * WebSocket connection state.
 */
enum class WebSocketState {
    DISCONNECTED,
    CONNECTING,
    CONNECTED,
    RECONNECTING
}

/**
 * Service for managing WebSocket connection to Kagami backend.
 */
@Singleton
class WebSocketService @Inject constructor(
    @Named("websocket") private val wsClient: OkHttpClient,
    private val apiConfig: ApiConfig
) {

    companion object {
        private const val TAG = "WebSocketService"

        // Reconnection constants
        private const val INITIAL_BACKOFF_MS = 1000L
        private const val MAX_BACKOFF_MS = 60000L
        private const val BACKOFF_MULTIPLIER = 2.0
        private const val MAX_RECONNECT_ATTEMPTS = 10
    }

    // Connection state
    private val _connectionState = MutableStateFlow(WebSocketState.DISCONNECTED)
    val connectionState: StateFlow<WebSocketState> = _connectionState

    // Messages flow
    private val _messages = MutableSharedFlow<WebSocketMessage>(replay = 0, extraBufferCapacity = 16)
    val messages: SharedFlow<WebSocketMessage> = _messages

    // Thread-safe state management
    private val webSocketMutex = Mutex()
    private var webSocket: WebSocket? = null
    private var reconnectAttempt = 0
    private var isConnecting = false
    private var clientId: String? = null

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    /**
     * Connect to WebSocket with the given client ID.
     */
    fun connect(clientId: String) {
        this.clientId = clientId
        scope.launch {
            connectInternal()
        }
    }

    /**
     * Disconnect from WebSocket.
     */
    fun disconnect() {
        scope.launch {
            webSocketMutex.withLock {
                webSocket?.close(1000, "Disconnect requested")
                webSocket = null
                reconnectAttempt = 0
                isConnecting = false
            }
            _connectionState.value = WebSocketState.DISCONNECTED
        }
    }

    /**
     * Reset reconnection state and attempt reconnection.
     */
    suspend fun resetAndReconnect() {
        webSocketMutex.withLock {
            reconnectAttempt = 0
            isConnecting = false
            webSocket?.close(1000, "Manual reset")
            webSocket = null
        }
        clientId?.let { connectInternal() }
    }

    /**
     * Send a message over WebSocket.
     */
    fun send(message: String): Boolean {
        return webSocket?.send(message) ?: false
    }

    private suspend fun connectInternal() {
        val id = clientId ?: return

        // Prevent concurrent connection attempts
        val shouldConnect = webSocketMutex.withLock {
            if (isConnecting) {
                Log.d(TAG, "WebSocket connection already in progress, skipping")
                return@withLock false
            }
            isConnecting = true
            true
        }

        if (!shouldConnect) return

        _connectionState.value = WebSocketState.CONNECTING

        try {
            val wsUrl = apiConfig.wsClientUrl(id)
            val request = Request.Builder()
                .url(wsUrl)
                .build()

            val newWebSocket = wsClient.newWebSocket(request, createWebSocketListener())

            webSocketMutex.withLock {
                webSocket = newWebSocket
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to create WebSocket", e)
            webSocketMutex.withLock {
                isConnecting = false
            }
            scheduleReconnect()
        }
    }

    private fun createWebSocketListener(): WebSocketListener {
        return object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                Log.i(TAG, "WebSocket connected")
                scope.launch {
                    webSocketMutex.withLock {
                        reconnectAttempt = 0
                        isConnecting = false
                    }
                    _connectionState.value = WebSocketState.CONNECTED
                }
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                handleMessage(text)
            }

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                Log.d(TAG, "WebSocket closing: $code - $reason")
                webSocket.close(1000, null)
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                Log.d(TAG, "WebSocket closed: $code - $reason")
                scope.launch {
                    webSocketMutex.withLock {
                        isConnecting = false
                    }
                    _connectionState.value = WebSocketState.DISCONNECTED
                    scheduleReconnect()
                }
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                Log.w(TAG, "WebSocket failure", t)
                scope.launch {
                    webSocketMutex.withLock {
                        isConnecting = false
                    }
                    _connectionState.value = WebSocketState.DISCONNECTED
                    _messages.emit(WebSocketMessage.Error(t.message ?: "Unknown error"))
                    scheduleReconnect()
                }
            }
        }
    }

    private fun handleMessage(text: String) {
        scope.launch {
            try {
                val json = JSONObject(text)
                val type = json.optString("type")
                val data = json.optJSONObject("data")

                val message = when (type) {
                    "context_update" -> {
                        val safetyScore = data?.optDouble("safety_score", Double.NaN)
                            ?.takeIf { !it.isNaN() }
                        WebSocketMessage.ContextUpdate(safetyScore)
                    }
                    "home_update" -> {
                        val movieMode = data?.optBoolean("movie_mode", false) ?: false
                        WebSocketMessage.HomeUpdate(movieMode)
                    }
                    else -> WebSocketMessage.Unknown(type, data)
                }

                _messages.emit(message)
            } catch (e: Exception) {
                Log.e(TAG, "WebSocket message parse error", e)
                _messages.emit(WebSocketMessage.Error("Failed to parse message: ${e.message}"))
            }
        }
    }

    private suspend fun scheduleReconnect() {
        val attempt = webSocketMutex.withLock {
            if (reconnectAttempt >= MAX_RECONNECT_ATTEMPTS) {
                Log.w(TAG, "Max WebSocket reconnection attempts reached ($MAX_RECONNECT_ATTEMPTS)")
                return
            }
            reconnectAttempt++
            reconnectAttempt
        }

        _connectionState.value = WebSocketState.RECONNECTING

        val backoffMs = min(
            INITIAL_BACKOFF_MS * BACKOFF_MULTIPLIER.pow(attempt - 1).toLong(),
            MAX_BACKOFF_MS
        )

        Log.d(TAG, "Scheduling WebSocket reconnect attempt $attempt in ${backoffMs}ms")
        delay(backoffMs)

        connectInternal()
    }

    /**
     * Clean up resources.
     */
    fun destroy() {
        disconnect()
        scope.cancel()
    }
}

/*
 * Mirror
 * h(x) >= 0. Always.
 */
