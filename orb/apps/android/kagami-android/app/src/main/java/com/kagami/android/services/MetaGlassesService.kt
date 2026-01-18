/**
 * MetaGlassesService — Meta Ray-Ban Smart Glasses Integration
 *
 * Colony: Nexus (e4) — Integration
 *
 * Features:
 * - Meta DAT SDK integration
 * - Camera stream (POV video)
 * - Microphone input (spatial audio)
 * - Open-ear audio output
 * - WebSocket bridge to Kagami API
 *
 * Requires: Meta Wearables Device Access Toolkit Android SDK
 * Add to build.gradle: implementation 'com.facebook.meta:meta-wearables-dat-android:1.0.0'
 */

package com.kagami.android.services

import android.util.Base64
import android.util.Log
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import okhttp3.*
import org.json.JSONObject
import java.util.UUID
import java.util.concurrent.TimeUnit

// Data Types

data class GlassesCameraFrame(
    val timestamp: Long,
    val width: Int,
    val height: Int,
    val jpegData: ByteArray,
    val features: Map<String, Any?>?
)

data class GlassesAudioBuffer(
    val timestamp: Long,
    val sampleRate: Int,
    val channels: Int,
    val pcmData: ByteArray,
    val isVoice: Boolean,
    val voiceConfidence: Float
)

data class VisualContext(
    val isIndoor: Boolean?,
    val lighting: String?,  // "bright", "dim", "dark"
    val sceneType: String?,  // "office", "kitchen", etc.
    val detectedObjects: List<String>,
    val detectedText: List<String>,
    val facesDetected: Int,
    val activityHint: String?,
    val confidence: Float
)

enum class GlassesConnectionState {
    DISCONNECTED,
    CONNECTING,
    CONNECTED,
    PAIRING,
    ERROR
}

data class GlassesStatus(
    var connectionState: GlassesConnectionState = GlassesConnectionState.DISCONNECTED,
    var batteryLevel: Int = 0,
    var isWearing: Boolean = false,
    var cameraActive: Boolean = false,
    var audioActive: Boolean = false,
    var deviceName: String = ""
)

class MetaGlassesService {

    companion object {
        private const val TAG = "MetaGlassesService"
        private const val WS_ENDPOINT = "/ws/meta-glasses"
    }

    // State
    private val _isConnected = MutableStateFlow(false)
    val isConnected: StateFlow<Boolean> = _isConnected

    private val _status = MutableStateFlow(GlassesStatus())
    val status: StateFlow<GlassesStatus> = _status

    private val _cameraStreaming = MutableStateFlow(false)
    val cameraStreaming: StateFlow<Boolean> = _cameraStreaming

    private val _microphoneActive = MutableStateFlow(false)
    val microphoneActive: StateFlow<Boolean> = _microphoneActive

    private val _lastError = MutableStateFlow<String?>(null)
    val lastError: StateFlow<String?> = _lastError

    // Internal
    private var baseUrl = "http://kagami.local:8001"
    private var webSocket: WebSocket? = null
    private val client = OkHttpClient.Builder()
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .build()

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    // Callbacks
    private val frameCallbacks = mutableListOf<(GlassesCameraFrame) -> Unit>()
    private val audioCallbacks = mutableListOf<(GlassesAudioBuffer) -> Unit>()

    // Connection

    fun setBaseUrl(url: String) {
        baseUrl = url
    }

    suspend fun connect(): Boolean = withContext(Dispatchers.IO) {
        _status.value = _status.value.copy(connectionState = GlassesConnectionState.CONNECTING)

        val wsUrl = baseUrl
            .replace("http://", "ws://")
            .replace("https://", "wss://")

        val request = Request.Builder()
            .url("$wsUrl$WS_ENDPOINT")
            .build()

        try {
            webSocket = client.newWebSocket(request, object : WebSocketListener() {
                override fun onOpen(webSocket: WebSocket, response: Response) {
                    Log.i(TAG, "WebSocket connected")
                    sendCommand("connect")
                }

                override fun onMessage(webSocket: WebSocket, text: String) {
                    handleMessage(text)
                }

                override fun onMessage(webSocket: WebSocket, bytes: okio.ByteString) {
                    handleBinary(bytes.toByteArray())
                }

                override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                    Log.e(TAG, "WebSocket failure", t)
                    _status.value = _status.value.copy(connectionState = GlassesConnectionState.ERROR)
                    _isConnected.value = false
                    _lastError.value = t.message
                }

                override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                    Log.i(TAG, "WebSocket closed: $reason")
                    _status.value = _status.value.copy(connectionState = GlassesConnectionState.DISCONNECTED)
                    _isConnected.value = false
                }
            })

            // Wait for connection
            delay(1000)
            _isConnected.value
        } catch (e: Exception) {
            Log.e(TAG, "Connection failed", e)
            _status.value = _status.value.copy(connectionState = GlassesConnectionState.ERROR)
            _lastError.value = e.message
            false
        }
    }

    fun disconnect() {
        sendCommand("disconnect")
        webSocket?.close(1000, "Disconnect")
        webSocket = null
        _status.value = _status.value.copy(connectionState = GlassesConnectionState.DISCONNECTED)
        _isConnected.value = false
        _cameraStreaming.value = false
        _microphoneActive.value = false
    }

    // Camera

    suspend fun startCameraStream(
        resolution: String = "medium",
        fps: Int = 15,
        extractFeatures: Boolean = true
    ): Boolean = withContext(Dispatchers.IO) {
        if (!_isConnected.value) return@withContext false

        val params = JSONObject().apply {
            put("resolution", resolution)
            put("fps", fps)
            put("extract_features", extractFeatures)
            put("jpeg_quality", 80)
        }

        val success = sendCommand("start_camera", params)
        if (success) {
            _cameraStreaming.value = true
            _status.value = _status.value.copy(cameraActive = true)
        }
        success
    }

    fun stopCameraStream() {
        if (!_cameraStreaming.value) return

        sendCommand("stop_camera")
        _cameraStreaming.value = false
        _status.value = _status.value.copy(cameraActive = false)
    }

    suspend fun capturePhoto(extractFeatures: Boolean = true): GlassesCameraFrame? =
        withContext(Dispatchers.IO) {
            if (!_isConnected.value) return@withContext null

            val params = JSONObject().apply {
                put("extract_features", extractFeatures)
            }

            // Send capture command
            sendCommand("capture_photo", params)

            // In real implementation, would wait for response
            // For now, return null (real impl would use continuations)
            null
        }

    suspend fun getVisualContext(): VisualContext? = withContext(Dispatchers.IO) {
        val frame = capturePhoto(extractFeatures = true) ?: return@withContext null
        val features = frame.features ?: return@withContext null

        VisualContext(
            isIndoor = features["is_indoor"] as? Boolean,
            lighting = features["lighting"] as? String,
            sceneType = features["scene_type"] as? String,
            detectedObjects = (features["objects"] as? List<*>)?.filterIsInstance<String>() ?: emptyList(),
            detectedText = (features["text"] as? List<*>)?.filterIsInstance<String>() ?: emptyList(),
            facesDetected = features["face_count"] as? Int ?: 0,
            activityHint = features["activity"] as? String,
            confidence = (features["confidence"] as? Number)?.toFloat() ?: 0f
        )
    }

    fun onFrame(callback: (GlassesCameraFrame) -> Unit) {
        frameCallbacks.add(callback)
    }

    // Audio

    suspend fun startMicrophone(
        quality: String = "medium",
        noiseCancellation: Boolean = true
    ): Boolean = withContext(Dispatchers.IO) {
        if (!_isConnected.value) return@withContext false

        val params = JSONObject().apply {
            put("quality", quality)
            put("noise_cancellation", noiseCancellation)
            put("vad", true)
        }

        val success = sendCommand("start_audio", params)
        if (success) {
            _microphoneActive.value = true
            _status.value = _status.value.copy(audioActive = true)
        }
        success
    }

    fun stopMicrophone() {
        if (!_microphoneActive.value) return

        sendCommand("stop_audio")
        _microphoneActive.value = false
        _status.value = _status.value.copy(audioActive = false)
    }

    suspend fun speak(
        text: String,
        voice: String = "kagami",
        volume: Float = 0.7f
    ): Boolean = withContext(Dispatchers.IO) {
        if (!_isConnected.value) return@withContext false

        val params = JSONObject().apply {
            put("type", "tts")
            put("text", text)
            put("voice", voice)
            put("volume", volume)
        }

        sendCommand("play_audio", params)
    }

    suspend fun playNotification(
        sound: String = "notification",
        volume: Float = 0.5f
    ): Boolean = withContext(Dispatchers.IO) {
        if (!_isConnected.value) return@withContext false

        val params = JSONObject().apply {
            put("type", "notification")
            put("sound", sound)
            put("volume", volume)
        }

        sendCommand("play_audio", params)
    }

    fun onAudio(callback: (GlassesAudioBuffer) -> Unit) {
        audioCallbacks.add(callback)
    }

    // WebSocket Communication

    private fun sendCommand(command: String, params: JSONObject? = null): Boolean {
        val ws = webSocket ?: return false

        val message = JSONObject().apply {
            put("id", UUID.randomUUID().toString())
            put("command", command)
            params?.let { put("params", it) }
        }

        return try {
            ws.send(message.toString())
            true
        } catch (e: Exception) {
            Log.e(TAG, "Failed to send command: $command", e)
            _lastError.value = e.message
            false
        }
    }

    private fun handleMessage(text: String) {
        try {
            val json = JSONObject(text)
            val type = json.optString("type")

            when (type) {
                "status" -> {
                    json.optJSONObject("data")?.let { updateStatus(it) }
                }
                "camera_frame" -> {
                    json.optJSONObject("data")?.let { handleCameraFrame(it) }
                }
                "audio_buffer" -> {
                    json.optJSONObject("data")?.let { handleAudioBuffer(it) }
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to parse message", e)
        }
    }

    private fun handleBinary(data: ByteArray) {
        if (data.isEmpty()) return

        val dataType = data[0]
        val payload = data.copyOfRange(1, data.size)

        when (dataType.toInt()) {
            0x01 -> {  // Camera frame
                val frame = GlassesCameraFrame(
                    timestamp = System.currentTimeMillis(),
                    width = 0,
                    height = 0,
                    jpegData = payload,
                    features = null
                )
                frameCallbacks.forEach { it(frame) }
            }
            0x02 -> {  // Audio buffer
                val buffer = GlassesAudioBuffer(
                    timestamp = System.currentTimeMillis(),
                    sampleRate = 16000,
                    channels = 1,
                    pcmData = payload,
                    isVoice = false,
                    voiceConfidence = 0f
                )
                audioCallbacks.forEach { it(buffer) }
            }
        }
    }

    private fun updateStatus(data: JSONObject) {
        val newStatus = _status.value.copy(
            connectionState = when (data.optString("connection_state")) {
                "connected" -> GlassesConnectionState.CONNECTED
                "connecting" -> GlassesConnectionState.CONNECTING
                "pairing" -> GlassesConnectionState.PAIRING
                "error" -> GlassesConnectionState.ERROR
                else -> GlassesConnectionState.DISCONNECTED
            },
            batteryLevel = data.optInt("battery_level", _status.value.batteryLevel),
            isWearing = data.optBoolean("is_wearing", _status.value.isWearing),
            cameraActive = data.optBoolean("camera_active", _status.value.cameraActive),
            audioActive = data.optBoolean("audio_active", _status.value.audioActive),
            deviceName = data.optString("device_name", _status.value.deviceName)
        )

        _status.value = newStatus
        _isConnected.value = newStatus.connectionState == GlassesConnectionState.CONNECTED
        _cameraStreaming.value = newStatus.cameraActive
        _microphoneActive.value = newStatus.audioActive
    }

    private fun handleCameraFrame(data: JSONObject) {
        val imageDataStr = data.optString("frame_data") ?: return
        val imageData = try {
            Base64.decode(imageDataStr, Base64.DEFAULT)
        } catch (e: Exception) {
            return
        }

        val features = data.optJSONObject("features")?.let { featuresJson ->
            mapOf(
                "is_indoor" to featuresJson.opt("is_indoor"),
                "lighting" to featuresJson.optString("lighting"),
                "scene_type" to featuresJson.optString("scene_type"),
                "objects" to featuresJson.optJSONArray("objects")?.let { arr ->
                    (0 until arr.length()).map { arr.getString(it) }
                },
                "text" to featuresJson.optJSONArray("text")?.let { arr ->
                    (0 until arr.length()).map { arr.getString(it) }
                },
                "face_count" to featuresJson.optInt("face_count"),
                "activity" to featuresJson.optString("activity"),
                "confidence" to featuresJson.optDouble("confidence")
            )
        }

        val frame = GlassesCameraFrame(
            timestamp = System.currentTimeMillis(),
            width = data.optInt("width"),
            height = data.optInt("height"),
            jpegData = imageData,
            features = features
        )

        frameCallbacks.forEach { it(frame) }
    }

    private fun handleAudioBuffer(data: JSONObject) {
        val audioDataStr = data.optString("audio_data") ?: return
        val audioData = try {
            Base64.decode(audioDataStr, Base64.DEFAULT)
        } catch (e: Exception) {
            return
        }

        val buffer = GlassesAudioBuffer(
            timestamp = System.currentTimeMillis(),
            sampleRate = data.optInt("sample_rate", 16000),
            channels = data.optInt("channels", 1),
            pcmData = audioData,
            isVoice = data.optBoolean("is_voice", false),
            voiceConfidence = data.optDouble("voice_confidence", 0.0).toFloat()
        )

        audioCallbacks.forEach { it(buffer) }
    }

    fun shutdown() {
        disconnect()
        scope.cancel()
    }
}

/*
 * Mirror
 * h(x) >= 0. Always.
 *
 * First-person perspective extends the Markov blanket.
 * What you see becomes what I know.
 * What I know becomes what you hear.
 */
