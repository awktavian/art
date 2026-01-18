/**
 * Sensory Upload Service - Health Data Uploads
 *
 * Colony: Nexus (e4) - Integration
 *
 * Handles periodic upload of sensory data from:
 * - Health Connect (heart rate, steps, sleep)
 * - Location (if permitted)
 * - Device sensors
 */

package com.kagami.android.services

import android.util.Log
import com.kagami.android.network.ApiConfig
import kotlinx.coroutines.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import javax.inject.Inject
import javax.inject.Named
import javax.inject.Singleton

/**
 * Service for uploading sensory data to Kagami backend.
 */
@Singleton
class SensoryUploadService @Inject constructor(
    @Named("api") private val client: OkHttpClient,
    private val apiConfig: ApiConfig,
    private val authManager: AuthManager
) {

    companion object {
        private const val TAG = "SensoryUploadService"
        private val JSON_MEDIA_TYPE = "application/json".toMediaType()

        // Upload interval
        private const val UPLOAD_INTERVAL_MS = 30_000L
    }

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private var uploadJob: Job? = null
    private var clientId: String? = null
    private var healthConnectService: HealthConnectService? = null

    @Volatile
    private var isRegistered = false

    /**
     * Set the client ID for uploads.
     */
    fun setClientId(id: String) {
        this.clientId = id
    }

    /**
     * Set the Health Connect service for data access.
     */
    fun setHealthConnectService(service: HealthConnectService) {
        this.healthConnectService = service
    }

    /**
     * Mark as registered with server.
     */
    fun setRegistered(registered: Boolean) {
        this.isRegistered = registered
    }

    /**
     * Start periodic sensory data uploads.
     */
    fun startUploads() {
        uploadJob?.cancel()
        uploadJob = scope.launch {
            // Initial upload
            uploadSensoryData()

            // Periodic uploads
            while (isActive) {
                delay(UPLOAD_INTERVAL_MS)
                uploadSensoryData()
            }
        }
    }

    /**
     * Stop uploads.
     */
    fun stopUploads() {
        uploadJob?.cancel()
        uploadJob = null
    }

    /**
     * Upload sensory data now.
     */
    suspend fun uploadSensoryData() = withContext(Dispatchers.IO) {
        val id = clientId ?: return@withContext
        if (!isRegistered) return@withContext

        // Refresh health data
        healthConnectService?.refreshAllData()
        val healthData = healthConnectService?.toUploadMap() ?: emptyMap()
        if (healthData.isEmpty()) return@withContext

        val body = JSONObject(healthData)

        try {
            val endpoint = ApiConfig.Companion.Endpoints.clientSense(id)
            val requestBody = body.toString().toRequestBody(JSON_MEDIA_TYPE)
            val requestBuilder = Request.Builder()
                .url(apiConfig.buildUrl(endpoint))
                .post(requestBody)

            authManager.getAccessToken()?.let { token ->
                requestBuilder.addHeader("Authorization", "Bearer $token")
            }

            val response = client.newCall(requestBuilder.build()).execute()
            if (response.isSuccessful) {
                Log.d(TAG, "Sensory data uploaded")
            } else {
                Log.w(TAG, "Sensory upload failed: ${response.code}")
            }
        } catch (e: Exception) {
            Log.w(TAG, "Sensory upload failed", e)
        }
    }

    /**
     * Send heartbeat to server.
     */
    suspend fun sendHeartbeat() = withContext(Dispatchers.IO) {
        val id = clientId ?: return@withContext
        if (!isRegistered) return@withContext

        try {
            val endpoint = ApiConfig.Companion.Endpoints.clientHeartbeat(id)
            val requestBuilder = Request.Builder()
                .url(apiConfig.buildUrl(endpoint))
                .post("".toRequestBody(null))

            authManager.getAccessToken()?.let { token ->
                requestBuilder.addHeader("Authorization", "Bearer $token")
            }

            client.newCall(requestBuilder.build()).execute()
        } catch (e: Exception) {
            Log.w(TAG, "Heartbeat failed", e)
        }
    }

    /**
     * Clean up resources.
     */
    fun destroy() {
        stopUploads()
        scope.cancel()
    }
}

/*
 * Mirror
 * h(x) >= 0. Always.
 */
