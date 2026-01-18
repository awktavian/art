/**
 * Kagami Rooms Screen ViewModel
 *
 * Colony: Nexus (e4) - Integration
 *
 * Provides proper Hilt dependency injection for RoomsScreen,
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
import com.kagami.android.services.AnalyticsService
import com.kagami.android.services.KagamiApiService
import com.kagami.android.services.RoomModel
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

/**
 * UI state for the Rooms screen.
 */
data class RoomsUiState(
    val rooms: List<RoomModel> = emptyList(),
    val isLoading: Boolean = true,
    val isRefreshing: Boolean = false,
    val errorMessage: String? = null,
    val showErrorDialog: Boolean = false,
    val actionErrorMessage: String? = null,
    val showActionError: Boolean = false
)

/**
 * Error messages with actionable context for Rooms screen.
 */
private object RoomsErrorMessages {
    const val NETWORK_ERROR = "Unable to load rooms. Check your network connection and try again."
    const val SERVER_ERROR = "Server error while loading rooms. Please try again later."
    const val TIMEOUT_ERROR = "Connection timed out. Make sure you're connected to your home network."
    const val AUTH_ERROR = "Session expired. Please sign in again to view your rooms."
    const val UNKNOWN_ERROR = "Something went wrong loading rooms. Pull down to refresh."
    const val LIGHTS_ON_FAILED = "Failed to turn on lights. Please try again."
    const val LIGHTS_OFF_FAILED = "Failed to turn off lights. Please try again."
    const val LIGHTS_DIM_FAILED = "Failed to dim lights. Please try again."
}

@HiltViewModel
class RoomsViewModel @Inject constructor(
    val apiService: KagamiApiService,
    val analyticsService: AnalyticsService
) : ViewModel() {

    companion object {
        /** Debounce duration for StateFlow updates to prevent recomposition cascade */
        private const val DEBOUNCE_MS = 50L
    }

    private val _uiState = MutableStateFlow(RoomsUiState())
    val uiState: StateFlow<RoomsUiState> = _uiState.asStateFlow()

    // Job tracking for debounced updates and proper lifecycle management
    private var updateJob: Job? = null

    init {
        // Track screen view
        analyticsService.trackScreenView("rooms", "RoomsScreen")

        // Fetch rooms on init
        fetchRooms()
    }

    /**
     * Update UI state with debouncing to prevent rapid recomposition.
     * P1: StateFlow debouncing (50ms) to prevent recomposition cascade.
     */
    private fun updateUiState(update: (RoomsUiState) -> RoomsUiState) {
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
     * Fetch rooms from API.
     */
    fun fetchRooms() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, errorMessage = null)

            when (val result = apiService.fetchRooms()) {
                is Result.Success -> {
                    _uiState.value = _uiState.value.copy(
                        rooms = result.data,
                        isLoading = false,
                        errorMessage = null,
                        showErrorDialog = false
                    )
                }
                is Result.Error -> {
                    val message = result.message ?: result.exception?.message ?: "unknown"
                    val userMessage = mapErrorToUserMessage(message)
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        errorMessage = userMessage,
                        showErrorDialog = true
                    )
                    analyticsService.trackError("rooms_load", message, "rooms", "fetch_rooms")
                }
            }
        }
    }

    /**
     * Refresh rooms - pull to refresh handler.
     */
    fun refreshRooms() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isRefreshing = true)
            analyticsService.trackAction("refresh_rooms", mapOf("screen" to "rooms"))

            when (val result = apiService.fetchRooms()) {
                is Result.Success -> {
                    _uiState.value = _uiState.value.copy(
                        rooms = result.data,
                        isRefreshing = false,
                        errorMessage = null,
                        showErrorDialog = false
                    )
                }
                is Result.Error -> {
                    val message = result.message ?: result.exception?.message ?: "unknown"
                    val userMessage = mapErrorToUserMessage(message)
                    _uiState.value = _uiState.value.copy(
                        isRefreshing = false,
                        errorMessage = userMessage,
                        showErrorDialog = true
                    )
                    analyticsService.trackError("rooms_refresh", message, "rooms", "refresh_rooms")
                }
            }
        }
    }

    /**
     * Set lights to full brightness for a room.
     */
    fun setLightsOn(roomId: String, roomName: String) {
        viewModelScope.launch {
            analyticsService.trackLightAdjusted(roomName, 100)

            when (val result = apiService.setLights(100, listOf(roomId))) {
                is Result.Success -> {
                    // Refresh rooms to show updated state
                    refreshRoomsQuietly()
                }
                is Result.Error -> {
                    _uiState.value = _uiState.value.copy(
                        actionErrorMessage = RoomsErrorMessages.LIGHTS_ON_FAILED,
                        showActionError = true
                    )
                    analyticsService.trackError("lights_on", result.message ?: "unknown", "rooms", "set_lights")
                }
            }
        }
    }

    /**
     * Turn off lights for a room.
     */
    fun setLightsOff(roomId: String, roomName: String) {
        viewModelScope.launch {
            analyticsService.trackLightAdjusted(roomName, 0)

            when (val result = apiService.setLights(0, listOf(roomId))) {
                is Result.Success -> {
                    refreshRoomsQuietly()
                }
                is Result.Error -> {
                    _uiState.value = _uiState.value.copy(
                        actionErrorMessage = RoomsErrorMessages.LIGHTS_OFF_FAILED,
                        showActionError = true
                    )
                    analyticsService.trackError("lights_off", result.message ?: "unknown", "rooms", "set_lights")
                }
            }
        }
    }

    /**
     * Dim lights for a room.
     */
    fun setLightsDim(roomId: String, roomName: String) {
        viewModelScope.launch {
            analyticsService.trackLightAdjusted(roomName, 30)

            when (val result = apiService.setLights(30, listOf(roomId))) {
                is Result.Success -> {
                    refreshRoomsQuietly()
                }
                is Result.Error -> {
                    _uiState.value = _uiState.value.copy(
                        actionErrorMessage = RoomsErrorMessages.LIGHTS_DIM_FAILED,
                        showActionError = true
                    )
                    analyticsService.trackError("lights_dim", result.message ?: "unknown", "rooms", "set_lights")
                }
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
     * Dismiss the action error (snackbar).
     */
    fun dismissActionError() {
        _uiState.value = _uiState.value.copy(
            actionErrorMessage = null,
            showActionError = false
        )
    }

    /**
     * Refresh rooms without showing loading indicators.
     */
    private suspend fun refreshRoomsQuietly() {
        when (val result = apiService.fetchRooms()) {
            is Result.Success -> {
                _uiState.value = _uiState.value.copy(rooms = result.data)
            }
            is Result.Error -> {
                // Silently ignore refresh errors after action
            }
        }
    }

    /**
     * Map technical error messages to user-friendly messages.
     */
    private fun mapErrorToUserMessage(message: String): String {
        return when {
            message.contains("timeout", ignoreCase = true) -> RoomsErrorMessages.TIMEOUT_ERROR
            message.contains("401") || message.contains("unauthorized", ignoreCase = true) -> RoomsErrorMessages.AUTH_ERROR
            message.contains("5") && message.contains("0") -> RoomsErrorMessages.SERVER_ERROR
            message.contains("network", ignoreCase = true) ||
            message.contains("connect", ignoreCase = true) -> RoomsErrorMessages.NETWORK_ERROR
            else -> RoomsErrorMessages.UNKNOWN_ERROR
        }
    }
}
