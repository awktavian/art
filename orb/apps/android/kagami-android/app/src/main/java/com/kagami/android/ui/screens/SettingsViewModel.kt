/**
 * Kagami Settings ViewModel - Proper DI replacing KagamiApp.instance
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
import com.kagami.android.services.KagamiApiService
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn
import javax.inject.Inject

@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val apiService: KagamiApiService,
    private val analyticsService: AnalyticsService
) : ViewModel() {

    val isConnected: StateFlow<Boolean> = apiService.isConnected
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), false)

    val latencyMs: StateFlow<Int> = apiService.latencyMs
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), 0)

    fun trackScreenView() {
        analyticsService.trackScreenView("settings", "SettingsScreen")
    }

    fun trackLogout() {
        analyticsService.trackLogout()
    }
}

/*
 * Mirror
 * h(x) >= 0. Always.
 */
