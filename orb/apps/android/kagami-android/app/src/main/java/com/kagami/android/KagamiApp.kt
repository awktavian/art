/**
 * Kagami Android - Application Entry Point
 *
 * Colony: Nexus (e4) - Integration
 *
 * h(x) >= 0. Always.
 */

package com.kagami.android

import android.app.Application
import android.util.Log
import androidx.hilt.work.HiltWorkerFactory
import androidx.work.Configuration
import com.google.firebase.crashlytics.FirebaseCrashlytics
import com.kagami.android.data.Result
import com.kagami.android.services.AnalyticsService
import com.kagami.android.services.KagamiApiService
import com.kagami.android.services.MeshCommandRouter
import com.kagami.android.widgets.WidgetUpdateWorker
import dagger.hilt.android.HiltAndroidApp
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltAndroidApp
class KagamiApp : Application(), Configuration.Provider {

    companion object {
        private const val TAG = "KagamiApp"

        lateinit var instance: KagamiApp
            private set
    }

    @Inject
    lateinit var crashlytics: FirebaseCrashlytics

    @Inject
    lateinit var apiService: KagamiApiService

    @Inject
    lateinit var analyticsService: AnalyticsService

    @Inject
    lateinit var meshCommandRouter: MeshCommandRouter

    @Inject
    lateinit var workerFactory: HiltWorkerFactory

    private var appStartTime: Long = 0
    private val applicationScope = CoroutineScope(SupervisorJob() + Dispatchers.Main)

    override fun onCreate() {
        super.onCreate()
        appStartTime = System.currentTimeMillis()
        instance = this

        // Configure Crashlytics
        crashlytics.setCrashlyticsCollectionEnabled(!BuildConfig.DEBUG)

        // Schedule widget updates if any widgets exist
        WidgetUpdateWorker.schedulePeriodicUpdate(this)

        // Initialize mesh network in background
        initializeMeshNetwork()
    }

    /**
     * Initialize the mesh network for local Hub communication.
     *
     * This runs in the background and:
     * 1. Initializes the MeshService (Ed25519 identity)
     * 2. Starts Hub discovery via mDNS
     * 3. Auto-connects to discovered Hubs
     */
    private fun initializeMeshNetwork() {
        applicationScope.launch(Dispatchers.IO) {
            try {
                Log.i(TAG, "Initializing mesh network...")

                when (val result = meshCommandRouter.initialize()) {
                    is Result.Success -> {
                        Log.i(TAG, "Mesh network initialized successfully")
                    }
                    is Result.Error -> {
                        Log.w(TAG, "Mesh network initialization failed: ${result.message}")
                        // Not fatal - app can still use HTTP fallback
                        crashlytics.recordException(
                            RuntimeException("Mesh init failed: ${result.message}")
                        )
                    }
                    else -> {}
                }
            } catch (e: Exception) {
                Log.e(TAG, "Mesh network initialization error", e)
                crashlytics.recordException(e)
            }
        }
    }

    /**
     * WorkManager configuration for HiltWorker support.
     * Required for @HiltWorker-annotated workers like WidgetUpdateWorker.
     */
    override val workManagerConfiguration: Configuration
        get() = Configuration.Builder()
            .setWorkerFactory(workerFactory)
            .build()

    /**
     * Track app launch time. Call this after initial UI is rendered.
     */
    fun trackLaunchComplete(coldStart: Boolean = true) {
        val launchTime = System.currentTimeMillis() - appStartTime
        analyticsService.trackAppLaunch(coldStart, launchTime)
    }

    /**
     * Get mesh connection status.
     */
    val isMeshConnected: Boolean
        get() = meshCommandRouter.isConnected.value

    /**
     * Restart Hub discovery if needed.
     */
    fun restartHubDiscovery() {
        meshCommandRouter.restartDiscovery()
    }

    override fun onTerminate() {
        super.onTerminate()
        meshCommandRouter.destroy()
    }
}

/*
 * Mirror
 *
 * The app initializes the mesh network on startup for local Hub communication.
 * Hub discovery uses mDNS for zero-configuration networking.
 * Commands are signed with Ed25519 and encrypted with XChaCha20-Poly1305.
 *
 * h(x) >= 0. Always.
 */
