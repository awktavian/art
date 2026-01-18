/**
 * Kagami Login ViewModel - Proper DI replacing KagamiApp.instance
 *
 * Colony: Nexus (e4) - Integration
 *
 * Follows Clean Architecture:
 * - Injected dependencies via Hilt
 * - StateFlow for reactive UI state
 * - Proper separation of concerns
 */

package com.kagami.android.ui.screens

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.kagami.android.services.AnalyticsService
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.util.concurrent.TimeUnit
import javax.inject.Inject

// State and sealed classes moved here to avoid duplication
data class LoginUiState(
    val serverUrl: String = "",
    val username: String = "",
    val password: String = "",
    val isLoading: Boolean = false,
    val isDiscovering: Boolean = false,
    val error: String? = null,
    val discoveredServers: List<String> = emptyList(),
    val showServerSelection: Boolean = false
)

sealed class LoginResultType {
    data class Success(
        val accessToken: String,
        val refreshToken: String?,
        val expiresIn: Int
    ) : LoginResultType()

    data class Error(val message: String) : LoginResultType()
}

@HiltViewModel
class LoginViewModelDI @Inject constructor(
    private val analyticsService: AnalyticsService
) : ViewModel() {

    private val _state = MutableStateFlow(LoginUiState())
    val state: StateFlow<LoginUiState> = _state.asStateFlow()

    private val client = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(10, TimeUnit.SECONDS)
        .build()

    companion object {
        private val JSON_MEDIA_TYPE = "application/json".toMediaType()
        private val DEFAULT_SERVERS = listOf(
            "http://kagami.local:8001",
            "http://192.168.1.100:8001",
            "http://192.168.1.50:8001",
            "http://10.0.0.100:8001",
            "http://localhost:8001"
        )
    }

    fun trackScreenView() {
        analyticsService.trackScreenView("login", "LoginScreen")
    }

    fun updateServerUrl(url: String) {
        _state.value = _state.value.copy(serverUrl = url, error = null)
    }

    fun updateUsername(username: String) {
        _state.value = _state.value.copy(username = username, error = null)
    }

    fun updatePassword(password: String) {
        _state.value = _state.value.copy(password = password, error = null)
    }

    fun selectServer(url: String) {
        _state.value = _state.value.copy(
            serverUrl = url,
            showServerSelection = false,
            error = null
        )
    }

    fun dismissServerSelection() {
        _state.value = _state.value.copy(showServerSelection = false)
    }

    fun discoverServers() {
        viewModelScope.launch {
            _state.value = _state.value.copy(isDiscovering = true, error = null)

            val discovered = mutableListOf<String>()

            withContext(Dispatchers.IO) {
                for (candidate in DEFAULT_SERVERS) {
                    if (testConnection(candidate)) {
                        discovered.add(candidate)
                    }
                }
            }

            _state.value = _state.value.copy(
                isDiscovering = false,
                discoveredServers = discovered,
                showServerSelection = discovered.isNotEmpty(),
                error = if (discovered.isEmpty()) "No Kagami servers found on your network" else null
            )

            // Auto-select if only one server found
            if (discovered.size == 1) {
                _state.value = _state.value.copy(
                    serverUrl = discovered.first(),
                    showServerSelection = false
                )
            }
        }
    }

    private fun testConnection(url: String): Boolean {
        return try {
            val request = Request.Builder().url("$url/health").build()
            val response = client.newCall(request).execute()
            response.isSuccessful
        } catch (e: Exception) {
            false
        }
    }

    fun login(onSuccess: (accessToken: String, refreshToken: String?) -> Unit) {
        val currentState = _state.value

        // Validation
        if (currentState.serverUrl.isBlank()) {
            _state.value = currentState.copy(error = "Please enter a server URL")
            return
        }
        if (currentState.username.isBlank()) {
            _state.value = currentState.copy(error = "Please enter your username")
            return
        }
        if (currentState.password.isBlank()) {
            _state.value = currentState.copy(error = "Please enter your password")
            return
        }

        viewModelScope.launch {
            _state.value = currentState.copy(isLoading = true, error = null)

            try {
                val result = withContext(Dispatchers.IO) {
                    performLogin(
                        serverUrl = currentState.serverUrl.trimEnd('/'),
                        username = currentState.username,
                        password = currentState.password
                    )
                }

                when (result) {
                    is LoginResultType.Success -> {
                        _state.value = _state.value.copy(isLoading = false, error = null)
                        onSuccess(result.accessToken, result.refreshToken)
                    }
                    is LoginResultType.Error -> {
                        _state.value = _state.value.copy(
                            isLoading = false,
                            error = result.message
                        )
                    }
                }
            } catch (e: Exception) {
                _state.value = _state.value.copy(
                    isLoading = false,
                    error = "Connection failed: ${e.message ?: "Unknown error"}"
                )
            }
        }
    }

    private fun performLogin(
        serverUrl: String,
        username: String,
        password: String
    ): LoginResultType {
        val body = JSONObject().apply {
            put("username", username)
            put("password", password)
            put("grant_type", "password")
        }

        val request = Request.Builder()
            .url("$serverUrl/api/user/token")
            .post(body.toString().toRequestBody(JSON_MEDIA_TYPE))
            .build()

        return try {
            val response = client.newCall(request).execute()
            val responseBody = response.body?.string()

            if (response.isSuccessful && responseBody != null) {
                val json = JSONObject(responseBody)
                LoginResultType.Success(
                    accessToken = json.getString("access_token"),
                    refreshToken = json.optString("refresh_token", null),
                    expiresIn = json.optInt("expires_in", 3600)
                )
            } else {
                val errorJson = responseBody?.let {
                    try { JSONObject(it) } catch (e: Exception) { null }
                }
                val errorDetail = errorJson?.optString("detail") ?: "Authentication failed"
                LoginResultType.Error(errorDetail)
            }
        } catch (e: Exception) {
            LoginResultType.Error("Network error: ${e.message ?: "Unable to connect"}")
        }
    }

    fun clearError() {
        _state.value = _state.value.copy(error = null)
    }
}

/*
 * Mirror
 * h(x) >= 0. Always.
 */
