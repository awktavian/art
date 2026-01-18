package com.kagami.wear

import android.app.Application
import com.kagami.wear.services.KagamiWearApiService
import dagger.hilt.android.HiltAndroidApp

/**
 * Kagami Wear OS Application
 *
 * Colony: Nexus (e4) - Integration
 *
 * The Wear OS companion app for Kagami, providing:
 * - Quick scene activation from wrist
 * - Safety score at a glance
 * - Context-aware hero actions
 * - Tiles for common controls
 */
@HiltAndroidApp
class KagamiWearApp : Application() {

    override fun onCreate() {
        super.onCreate()
        // Initialize API service with app context for DataStore
        KagamiWearApiService.initialize(this)
    }
}
