/**
 * Kagami Home Screen ViewModel
 *
 * Colony: Nexus (e4) - Integration
 *
 * Provides proper Hilt dependency injection for HomeScreen,
 * replacing direct KagamiApp.instance access with ViewModel pattern.
 *
 * Features:
 * - Hilt-injected KagamiApiService and AnalyticsService
 * - StateFlow for reactive UI updates
 * - Proper lifecycle management
 * - Error state handling with user-friendly messages
 */

package com.kagami.android.ui.screens

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.kagami.android.data.Result
import com.kagami.android.services.ActivationSource
import com.kagami.android.services.AnalyticsService
import com.kagami.android.services.KagamiApiService
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.util.Calendar
import javax.inject.Inject

/**
 * UI state for the Home screen.
 */
data class HomeUiState(
    val isConnected: Boolean = false,
    val safetyScore: Double? = null,
    val latencyMs: Int = 0,
    val isInitialLoading: Boolean = true,
    val isRefreshing: Boolean = false,
    val errorMessage: String? = null,
    val showErrorDialog: Boolean = false
)

/**
 * Error messages with actionable context for Home screen.
 */
private object HomeErrorMessages {
    const val NETWORK_ERROR = "Unable to connect. Check your network and try again."
    const val SERVER_ERROR = "Server error. Please try again later."
    const val TIMEOUT_ERROR = "Connection timed out. Make sure you're connected to your home network."
    const val SCENE_FAILED = "Failed to activate scene. Please try again."
    const val LIGHTS_FAILED = "Failed to control lights. Please try again."
    const val TV_FAILED = "Failed to control TV. Please try again."
    const val SHADES_FAILED = "Failed to control shades. Please try again."
    const val UNKNOWN_ERROR = "Something went wrong. Pull down to refresh."
}

@HiltViewModel
class HomeViewModel @Inject constructor(
    val apiService: KagamiApiService,
    val analyticsService: AnalyticsService
) : ViewModel() {

    companion object {
        /** Debounce duration for StateFlow updates to prevent recomposition cascade */
        private const val DEBOUNCE_MS = 50L
    }

    private val _uiState = MutableStateFlow(HomeUiState())
    val uiState: StateFlow<HomeUiState> = _uiState.asStateFlow()

    // Expose API service state flows for direct observation
    val isConnected: StateFlow<Boolean> = apiService.isConnected
    val safetyScore: StateFlow<Double?> = apiService.safetyScore
    val latencyMs: StateFlow<Int> = apiService.latencyMs

    // Job tracking for debounced updates and proper lifecycle management
    private var updateJob: Job? = null

    init {
        // Track screen view
        analyticsService.trackScreenView("home", "HomeScreen")

        // Connect to API on init
        viewModelScope.launch {
            apiService.connect()
            _uiState.value = _uiState.value.copy(isInitialLoading = false)
        }
    }

    /**
     * Update UI state with debouncing to prevent rapid recomposition.
     * P1: StateFlow debouncing (50ms) to prevent recomposition cascade.
     */
    private fun updateUiState(update: (HomeUiState) -> HomeUiState) {
        updateJob?.cancel()
        updateJob = viewModelScope.launch {
            delay(DEBOUNCE_MS)
            _uiState.value = update(_uiState.value)
        }
    }

    override fun onCleared() {
        super.onCleared()
        // P1: Proper coroutine cancellation for memory lifecycle
        updateJob?.cancel()
    }

    /**
     * Refresh connection and data.
     */
    fun refresh() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isRefreshing = true, errorMessage = null)
            try {
                apiService.connect()
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    errorMessage = HomeErrorMessages.NETWORK_ERROR,
                    showErrorDialog = true
                )
            } finally {
                _uiState.value = _uiState.value.copy(isRefreshing = false)
            }
        }
    }

    /**
     * Execute a scene with proper error handling.
     */
    fun executeScene(scene: String) {
        val hour = Calendar.getInstance().get(Calendar.HOUR_OF_DAY)
        val timeOfDay = when (hour) {
            in 6..9 -> "morning"
            in 10..17 -> "working"
            in 18..21 -> "evening"
            else -> "night"
        }

        analyticsService.trackHeroAction(scene, timeOfDay)
        analyticsService.trackSceneActivated(scene, ActivationSource.APP)

        viewModelScope.launch {
            val result = apiService.executeScene(scene)
            if (result is Result.Error) {
                _uiState.value = _uiState.value.copy(
                    errorMessage = HomeErrorMessages.SCENE_FAILED,
                    showErrorDialog = true
                )
                analyticsService.trackError("scene_execution", result.message ?: "unknown", "home", scene)
            }
        }
    }

    /**
     * Execute a quick action with proper error handling.
     */
    fun executeQuickAction(action: String) {
        analyticsService.trackQuickAction(action)

        viewModelScope.launch {
            val result = when (action) {
                "lights_on" -> apiService.setLights(100)
                "lights_off" -> apiService.setLights(0)
                "tv_lower" -> apiService.tvControl("lower")
                "tv_raise" -> apiService.tvControl("raise")
                "shades_open" -> apiService.controlShades("open")
                "shades_close" -> apiService.controlShades("close")
                else -> Result.error("Unknown action: $action")
            }

            if (result is Result.Error) {
                val errorMessage = when (action) {
                    "lights_on", "lights_off" -> HomeErrorMessages.LIGHTS_FAILED
                    "tv_lower", "tv_raise" -> HomeErrorMessages.TV_FAILED
                    "shades_open", "shades_close" -> HomeErrorMessages.SHADES_FAILED
                    else -> HomeErrorMessages.UNKNOWN_ERROR
                }
                _uiState.value = _uiState.value.copy(
                    errorMessage = errorMessage,
                    showErrorDialog = true
                )
                analyticsService.trackError("quick_action", result.message ?: "unknown", "home", action)
            }
        }
    }

    /**
     * Dismiss the error dialog.
     */
    fun dismissError() {
        _uiState.value = _uiState.value.copy(
            errorMessage = null,
            showErrorDialog = false
        )
    }

    /**
     * Mark initial loading as complete.
     */
    fun setInitialLoadingComplete() {
        _uiState.value = _uiState.value.copy(isInitialLoading = false)
    }
}
