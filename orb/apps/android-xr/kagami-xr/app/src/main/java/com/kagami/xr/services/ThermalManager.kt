package com.kagami.xr.services

import android.app.Application
import android.os.PowerManager
import android.util.Log
import androidx.lifecycle.AndroidViewModel
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import javax.inject.Inject

/**
 * Thermal Manager for AndroidXR
 *
 * Manages quality profiles based on device thermal state.
 * Critical for battery life and user comfort in XR experiences.
 *
 * Colony: Nexus (e4) - Integration
 *
 * Quality Profiles:
 *   ULTRA   - 90fps, all effects (nominal thermal)
 *   HIGH    - 72fps, most effects (light thermal)
 *   MEDIUM  - 60fps, reduced effects (moderate thermal)
 *   LOW     - 45fps, minimal effects (severe thermal)
 *   MINIMAL - 30fps, essential only (critical thermal)
 *
 * Strategy:
 *   - Decrease quality immediately when thermal increases
 *   - Increase quality only after 30s hysteresis (prevent oscillation)
 *
 * h(x) >= 0. Always.
 */
@HiltViewModel
class ThermalManager @Inject constructor(
    application: Application
) : AndroidViewModel(application) {

    companion object {
        private const val TAG = "ThermalManager"
        private const val HYSTERESIS_MS = 30_000L  // 30 seconds before increasing quality
    }

    /**
     * Quality profiles that adapt to thermal state.
     */
    enum class QualityProfile(
        val targetFps: Int,
        val particlesEnabled: Boolean,
        val spatialAudioEnabled: Boolean,
        val shadowQuality: ShadowQuality,
        val maxEntities: Int
    ) {
        ULTRA(90, true, true, ShadowQuality.HIGH, 100),
        HIGH(72, true, true, ShadowQuality.MEDIUM, 75),
        MEDIUM(60, true, true, ShadowQuality.LOW, 50),
        LOW(45, false, true, ShadowQuality.NONE, 30),
        MINIMAL(30, false, false, ShadowQuality.NONE, 15);

        /**
         * Get resolution scale factor for this quality level.
         */
        val resolutionScale: Float
            get() = when (this) {
                ULTRA -> 1.0f
                HIGH -> 0.9f
                MEDIUM -> 0.75f
                LOW -> 0.6f
                MINIMAL -> 0.5f
            }
    }

    enum class ShadowQuality {
        HIGH,
        MEDIUM,
        LOW,
        NONE
    }

    // Current quality profile
    private val _currentProfile = MutableStateFlow(QualityProfile.HIGH)
    val currentProfile: StateFlow<QualityProfile> = _currentProfile.asStateFlow()

    // Current thermal state
    private val _thermalState = MutableStateFlow(PowerManager.THERMAL_STATUS_NONE)
    val thermalState: StateFlow<Int> = _thermalState.asStateFlow()

    // Last time we decreased quality (for hysteresis)
    private var lastQualityDecreaseTime: Long = 0

    init {
        setupThermalListener()
    }

    private fun setupThermalListener() {
        try {
            val powerManager = getApplication<Application>()
                .getSystemService(PowerManager::class.java)

            powerManager?.addThermalStatusListener { status ->
                Log.d(TAG, "Thermal status changed: $status")
                _thermalState.value = status
                updateQualityProfile(status)
            }

            Log.i(TAG, "Thermal monitoring initialized")
        } catch (e: Exception) {
            Log.w(TAG, "Failed to setup thermal listener: ${e.message}")
            // Continue with default profile
        }
    }

    /**
     * Update quality profile based on thermal status.
     *
     * Strategy:
     * - Immediately decrease quality when thermal increases
     * - Only increase quality after hysteresis period
     */
    private fun updateQualityProfile(thermalStatus: Int) {
        val targetProfile = when (thermalStatus) {
            PowerManager.THERMAL_STATUS_NONE,
            PowerManager.THERMAL_STATUS_LIGHT -> QualityProfile.HIGH
            PowerManager.THERMAL_STATUS_MODERATE -> QualityProfile.MEDIUM
            PowerManager.THERMAL_STATUS_SEVERE -> QualityProfile.LOW
            PowerManager.THERMAL_STATUS_CRITICAL,
            PowerManager.THERMAL_STATUS_EMERGENCY,
            PowerManager.THERMAL_STATUS_SHUTDOWN -> QualityProfile.MINIMAL
            else -> QualityProfile.MEDIUM
        }

        val currentOrdinal = _currentProfile.value.ordinal
        val targetOrdinal = targetProfile.ordinal
        val now = System.currentTimeMillis()

        when {
            // Decrease quality immediately (higher ordinal = lower quality)
            targetOrdinal > currentOrdinal -> {
                Log.i(TAG, "Decreasing quality: ${_currentProfile.value} -> $targetProfile")
                _currentProfile.value = targetProfile
                lastQualityDecreaseTime = now
            }

            // Increase quality only with hysteresis
            targetOrdinal < currentOrdinal -> {
                val timeSinceDecrease = now - lastQualityDecreaseTime
                if (timeSinceDecrease >= HYSTERESIS_MS) {
                    // Increase one level at a time
                    val newProfile = QualityProfile.entries[currentOrdinal - 1]
                    Log.i(TAG, "Increasing quality: ${_currentProfile.value} -> $newProfile")
                    _currentProfile.value = newProfile
                } else {
                    Log.d(TAG, "Quality increase pending (${timeSinceDecrease}ms / ${HYSTERESIS_MS}ms)")
                }
            }
        }
    }

    /**
     * Force a specific quality profile (for testing/debugging).
     */
    fun forceProfile(profile: QualityProfile) {
        Log.w(TAG, "Forcing quality profile: $profile")
        _currentProfile.value = profile
    }

    /**
     * Get recommended frame time budget for current profile.
     */
    val frameTimeBudgetMs: Float
        get() = 1000f / _currentProfile.value.targetFps

    /**
     * Check if current profile allows a specific feature.
     */
    fun isFeatureEnabled(feature: Feature): Boolean {
        return when (feature) {
            Feature.PARTICLES -> _currentProfile.value.particlesEnabled
            Feature.SPATIAL_AUDIO -> _currentProfile.value.spatialAudioEnabled
            Feature.SHADOWS -> _currentProfile.value.shadowQuality != ShadowQuality.NONE
            Feature.HIGH_RES_TEXTURES -> _currentProfile.value.ordinal <= QualityProfile.MEDIUM.ordinal
        }
    }

    enum class Feature {
        PARTICLES,
        SPATIAL_AUDIO,
        SHADOWS,
        HIGH_RES_TEXTURES
    }
}

/*
 * 鏡
 * h(x) >= 0. Always.
 *
 * Heat is information.
 * Constraint is design.
 * Adaptation is intelligence.
 */
