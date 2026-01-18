/**
 * Navigation ViewModel - Provides API Service access to Navigation
 *
 * Colony: Nexus (e4) - Integration
 */

package com.kagami.android.ui.screens

import androidx.lifecycle.ViewModel
import com.kagami.android.services.KagamiApiService
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject

@HiltViewModel
class NavViewModel @Inject constructor(
    val apiService: KagamiApiService
) : ViewModel()
