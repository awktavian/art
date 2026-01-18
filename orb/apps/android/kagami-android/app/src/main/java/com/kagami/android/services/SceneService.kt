/**
 * Scene Service - Scene Execution
 *
 * Colony: Nexus (e4) - Integration
 *
 * Handles execution of smart home scenes:
 * - Movie mode
 * - Goodnight
 * - Welcome home
 * - Away
 * - Focus
 * - Relax
 */

package com.kagami.android.services

import com.kagami.android.data.Result
import com.kagami.android.network.ApiConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import javax.inject.Inject
import javax.inject.Named
import javax.inject.Singleton

/**
 * Available scenes.
 */
enum class Scene(val id: String, val displayName: String) {
    MOVIE_MODE("movie_mode", "Movie Mode"),
    MOVIE_MODE_EXIT("movie_mode_exit", "Exit Movie Mode"),
    GOODNIGHT("goodnight", "Goodnight"),
    WELCOME_HOME("welcome_home", "Welcome Home"),
    AWAY("away", "Away"),
    FOCUS("focus", "Focus"),
    RELAX("relax", "Relax"),
    COFFEE("coffee", "Coffee"),
    GOOD_MORNING("good_morning", "Good Morning"),
    SLEEP("sleep", "Sleep");

    companion object {
        fun fromId(id: String): Scene? = values().find { it.id == id }
    }
}

/**
 * Scene info for display.
 */
data class SceneInfo(
    val id: String,
    val name: String,
    val icon: String
)

/**
 * Service for executing smart home scenes.
 */
@Singleton
class SceneService @Inject constructor(
    @Named("api") private val client: OkHttpClient,
    private val apiConfig: ApiConfig,
    private val authManager: AuthManager
) {

    companion object {
        private val JSON_MEDIA_TYPE = "application/json".toMediaType()
    }

    /**
     * Execute a scene by ID.
     */
    suspend fun executeScene(sceneId: String): Result<Boolean> = withContext(Dispatchers.IO) {
        val scene = Scene.fromId(sceneId)
        if (scene == null) {
            return@withContext Result.error("Unknown scene: $sceneId")
        }
        executeScene(scene)
    }

    /**
     * Execute a scene.
     */
    suspend fun executeScene(scene: Scene): Result<Boolean> = withContext(Dispatchers.IO) {
        val endpoint = getEndpointForScene(scene)
            ?: return@withContext Result.error("No endpoint for scene: ${scene.id}")

        val body = getBodyForScene(scene)

        try {
            val requestBody = (body?.toString() ?: "{}").toRequestBody(JSON_MEDIA_TYPE)
            val requestBuilder = Request.Builder()
                .url(apiConfig.buildUrl(endpoint))
                .post(requestBody)

            authManager.getAccessToken()?.let { token ->
                requestBuilder.addHeader("Authorization", "Bearer $token")
            }

            val response = client.newCall(requestBuilder.build()).execute()

            if (response.isSuccessful) {
                Result.success(true)
            } else {
                Result.error("Failed to execute scene: ${scene.displayName}", response.code)
            }
        } catch (e: java.net.SocketTimeoutException) {
            Result.error("Connection timed out", 0)
        } catch (e: java.net.UnknownHostException) {
            Result.error("Network unavailable - check your connection", 0)
        } catch (e: Exception) {
            Result.error(e)
        }
    }

    /**
     * Get available scenes.
     */
    suspend fun getScenes(): Result<List<SceneInfo>> = withContext(Dispatchers.IO) {
        // Return predefined scenes for now
        // Could be extended to fetch from API
        val scenes = listOf(
            SceneInfo("movie_mode", "Movie Mode", "movie"),
            SceneInfo("goodnight", "Goodnight", "bedtime"),
            SceneInfo("welcome_home", "Welcome Home", "home"),
            SceneInfo("away", "Away", "directions_walk"),
            SceneInfo("focus", "Focus", "psychology"),
            SceneInfo("relax", "Relax", "spa")
        )
        Result.success(scenes)
    }

    private fun getEndpointForScene(scene: Scene): String? {
        return when (scene) {
            Scene.MOVIE_MODE -> ApiConfig.Companion.Endpoints.MOVIE_MODE_ENTER
            Scene.MOVIE_MODE_EXIT -> ApiConfig.Companion.Endpoints.MOVIE_MODE_EXIT
            Scene.GOODNIGHT -> ApiConfig.Companion.Endpoints.GOODNIGHT
            Scene.WELCOME_HOME -> ApiConfig.Companion.Endpoints.WELCOME_HOME
            Scene.AWAY -> ApiConfig.Companion.Endpoints.AWAY
            Scene.FOCUS -> ApiConfig.Companion.Endpoints.LIGHTS_SET
            Scene.RELAX -> ApiConfig.Companion.Endpoints.FIREPLACE_ON
            Scene.COFFEE -> ApiConfig.Companion.Endpoints.LIGHTS_SET
            Scene.GOOD_MORNING -> ApiConfig.Companion.Endpoints.WELCOME_HOME
            Scene.SLEEP -> ApiConfig.Companion.Endpoints.GOODNIGHT
        }
    }

    private fun getBodyForScene(scene: Scene): JSONObject? {
        return when (scene) {
            Scene.FOCUS -> JSONObject().apply {
                put("level", 60)
                put("rooms", listOf("Office"))
            }
            Scene.COFFEE -> JSONObject().apply {
                put("level", 100)
                put("rooms", listOf("Kitchen"))
            }
            else -> null
        }
    }
}

/*
 * Mirror
 * h(x) >= 0. Always.
 */
