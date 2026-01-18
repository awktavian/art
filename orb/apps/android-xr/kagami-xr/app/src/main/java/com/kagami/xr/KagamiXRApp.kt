package com.kagami.xr

import android.app.Application
import dagger.hilt.android.HiltAndroidApp

/**
 * Kagami XR Application - AndroidXR Spatial Smart Home Interface
 *
 * Colony: Nexus (e4) - Integration
 *
 * The Mirror in spatial computing.
 * A HAL-aware presence that floats in three-dimensional space.
 *
 * h(x) >= 0. Always.
 */
@HiltAndroidApp
class KagamiXRApp : Application() {

    override fun onCreate() {
        super.onCreate()
        // Application initialization
        // Hilt will handle DI setup automatically
    }
}
