package com.kagami.android.services

import android.content.Context
import android.os.Build
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import android.view.HapticFeedbackConstants
import android.view.View
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import javax.inject.Inject
import javax.inject.Singleton

/**
 * KagamiHaptics — Unified Haptic Feedback Service for Android
 *
 * Colony: 💎 Crystal (e7) — Verification & Polish
 *
 * Provides consistent haptic patterns across the app:
 * - Success: Confirmation of completed actions
 * - Error: Alert for failures or blocked actions
 * - Warning: Attention needed, non-critical
 * - Selection: UI element selection feedback
 * - Impact: Physical interaction feedback (light, medium, heavy)
 * - Discovery: Progressive engagement feedback (glance → engage)
 * - Compound: Multi-step patterns (double tap, long press, tick)
 *
 * Uses VibrationEffect.Composition for rich haptics (API 30+)
 * with performHapticFeedback fallback for older devices.
 *
 * h(x) >= 0. Always.
 */

/**
 * Semantic haptic feedback types matching iOS KagamiHaptics.swift
 */
enum class HapticPattern {
    // Core patterns
    SUCCESS,
    ERROR,
    WARNING,
    SELECTION,

    // Impact patterns
    LIGHT_IMPACT,
    MEDIUM_IMPACT,
    HEAVY_IMPACT,
    SOFT_IMPACT,
    RIGID_IMPACT,

    // Discovery effects (Glass UI)
    DISCOVERY_GLANCE,     // Initial hover (subtle)
    DISCOVERY_INTEREST,   // Sustained attention
    DISCOVERY_FOCUS,      // Full engagement
    DISCOVERY_ENGAGE,     // Action taken

    // Compound patterns
    DOUBLE_TAP,
    LONG_PRESS,
    TICK,

    // Scene-specific
    SCENE_ACTIVATED,
    LIGHTS_CHANGED,
    LOCK_ENGAGED,

    // Safety
    SAFETY_VIOLATION
}

@Singleton
class KagamiHaptics @Inject constructor(
    @ApplicationContext private val context: Context
) {
    private val scope = CoroutineScope(Dispatchers.Main)

    /**
     * Get the system vibrator service
     */
    private val vibrator: Vibrator by lazy {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            val vibratorManager = context.getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as VibratorManager
            vibratorManager.defaultVibrator
        } else {
            @Suppress("DEPRECATION")
            context.getSystemService(Context.VIBRATOR_SERVICE) as Vibrator
        }
    }

    /**
     * Check if haptics are supported on this device
     */
    val isSupported: Boolean
        get() = vibrator.hasVibrator()

    /**
     * Check if amplitude control is supported (for rich haptics)
     */
    val hasAmplitudeControl: Boolean
        get() = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            vibrator.hasAmplitudeControl()
        } else {
            false
        }

    // ========================================================================
    // Public API
    // ========================================================================

    /**
     * Play a haptic pattern
     *
     * @param pattern The semantic haptic pattern to play
     */
    fun play(pattern: HapticPattern) {
        if (!isSupported) return

        when (pattern) {
            HapticPattern.SUCCESS -> playSuccess()
            HapticPattern.ERROR -> playError()
            HapticPattern.WARNING -> playWarning()
            HapticPattern.SELECTION -> playSelection()
            HapticPattern.LIGHT_IMPACT -> playImpact(amplitude = 64)
            HapticPattern.MEDIUM_IMPACT -> playImpact(amplitude = 128)
            HapticPattern.HEAVY_IMPACT -> playImpact(amplitude = 200)
            HapticPattern.SOFT_IMPACT -> playImpact(amplitude = 48, duration = 30)
            HapticPattern.RIGID_IMPACT -> playImpact(amplitude = 180, duration = 15)
            HapticPattern.DISCOVERY_GLANCE -> playDiscoveryGlance()
            HapticPattern.DISCOVERY_INTEREST -> playDiscoveryInterest()
            HapticPattern.DISCOVERY_FOCUS -> playDiscoveryFocus()
            HapticPattern.DISCOVERY_ENGAGE -> playDiscoveryEngage()
            HapticPattern.DOUBLE_TAP -> playDoubleTap()
            HapticPattern.LONG_PRESS -> playLongPress()
            HapticPattern.TICK -> playTick()
            HapticPattern.SCENE_ACTIVATED -> playSceneActivated()
            HapticPattern.LIGHTS_CHANGED -> playLightsChanged()
            HapticPattern.LOCK_ENGAGED -> playLockEngaged()
            HapticPattern.SAFETY_VIOLATION -> playSafetyViolation()
        }
    }

    /**
     * Play a haptic pattern with custom intensity (0.0 - 1.0)
     *
     * @param pattern Base pattern to modify
     * @param intensity Intensity multiplier (0.0 to 1.0)
     */
    fun play(pattern: HapticPattern, intensity: Float) {
        if (!isSupported) return

        val clampedIntensity = intensity.coerceIn(0f, 1f)
        val amplitude = (clampedIntensity * 255).toInt().coerceIn(1, 255)

        when (pattern) {
            HapticPattern.LIGHT_IMPACT,
            HapticPattern.MEDIUM_IMPACT,
            HapticPattern.HEAVY_IMPACT,
            HapticPattern.SOFT_IMPACT,
            HapticPattern.RIGID_IMPACT -> playImpact(amplitude = amplitude)
            else -> play(pattern)
        }
    }

    /**
     * Play haptic feedback through a View (uses system haptic constants)
     *
     * @param view The view to trigger haptic feedback on
     * @param pattern The haptic pattern to play
     */
    fun playWithView(view: View, pattern: HapticPattern) {
        val feedbackConstant = when (pattern) {
            HapticPattern.SUCCESS -> {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                    HapticFeedbackConstants.CONFIRM
                } else {
                    HapticFeedbackConstants.VIRTUAL_KEY
                }
            }
            HapticPattern.ERROR -> {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                    HapticFeedbackConstants.REJECT
                } else {
                    HapticFeedbackConstants.LONG_PRESS
                }
            }
            HapticPattern.WARNING -> HapticFeedbackConstants.LONG_PRESS
            HapticPattern.SELECTION -> {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
                    HapticFeedbackConstants.SEGMENT_FREQUENT_TICK
                } else {
                    HapticFeedbackConstants.CLOCK_TICK
                }
            }
            HapticPattern.LIGHT_IMPACT,
            HapticPattern.DISCOVERY_GLANCE -> {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O_MR1) {
                    HapticFeedbackConstants.TEXT_HANDLE_MOVE
                } else {
                    HapticFeedbackConstants.KEYBOARD_TAP
                }
            }
            HapticPattern.MEDIUM_IMPACT,
            HapticPattern.DISCOVERY_ENGAGE -> HapticFeedbackConstants.VIRTUAL_KEY
            HapticPattern.HEAVY_IMPACT -> HapticFeedbackConstants.LONG_PRESS
            HapticPattern.TICK -> {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O_MR1) {
                    HapticFeedbackConstants.TEXT_HANDLE_MOVE
                } else {
                    HapticFeedbackConstants.CLOCK_TICK
                }
            }
            else -> HapticFeedbackConstants.VIRTUAL_KEY
        }

        view.performHapticFeedback(feedbackConstant)
    }

    // ========================================================================
    // Core Patterns
    // ========================================================================

    private fun playSuccess() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            vibrator.vibrate(
                VibrationEffect.createPredefined(VibrationEffect.EFFECT_CLICK)
            )
        } else {
            playImpact(amplitude = 128, duration = 30)
        }
    }

    private fun playError() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            vibrator.vibrate(
                VibrationEffect.createPredefined(VibrationEffect.EFFECT_DOUBLE_CLICK)
            )
        } else {
            // Fallback: two quick vibrations
            scope.launch {
                playImpact(amplitude = 180, duration = 40)
                delay(80)
                playImpact(amplitude = 180, duration = 40)
            }
        }
    }

    private fun playWarning() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            vibrator.vibrate(
                VibrationEffect.createPredefined(VibrationEffect.EFFECT_HEAVY_CLICK)
            )
        } else {
            playImpact(amplitude = 200, duration = 50)
        }
    }

    private fun playSelection() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            vibrator.vibrate(
                VibrationEffect.createPredefined(VibrationEffect.EFFECT_TICK)
            )
        } else {
            playImpact(amplitude = 64, duration = 10)
        }
    }

    // ========================================================================
    // Impact Patterns
    // ========================================================================

    private fun playImpact(amplitude: Int, duration: Long = 20) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val clampedAmplitude = if (hasAmplitudeControl) {
                amplitude.coerceIn(1, 255)
            } else {
                VibrationEffect.DEFAULT_AMPLITUDE
            }
            vibrator.vibrate(
                VibrationEffect.createOneShot(duration, clampedAmplitude)
            )
        } else {
            @Suppress("DEPRECATION")
            vibrator.vibrate(duration)
        }
    }

    // ========================================================================
    // Discovery Patterns (Glass UI)
    // ========================================================================

    private fun playDiscoveryGlance() {
        // Subtle feedback for initial hover (30% intensity)
        playImpact(amplitude = 76, duration = 15)
    }

    private fun playDiscoveryInterest() {
        // Slightly stronger for sustained attention (50% intensity)
        playImpact(amplitude = 128, duration = 20)
    }

    private fun playDiscoveryFocus() {
        // Full light impact for focus state (80% intensity)
        playImpact(amplitude = 204, duration = 25)
    }

    private fun playDiscoveryEngage() {
        // Medium impact for engagement
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            vibrator.vibrate(
                VibrationEffect.createPredefined(VibrationEffect.EFFECT_CLICK)
            )
        } else {
            playImpact(amplitude = 180, duration = 30)
        }
    }

    // ========================================================================
    // Compound Patterns
    // ========================================================================

    private fun playDoubleTap() {
        scope.launch {
            playImpact(amplitude = 153, duration = 20)  // 60% intensity
            delay(80)
            playImpact(amplitude = 204, duration = 25)  // 80% intensity
        }
    }

    private fun playLongPress() {
        // Building pressure effect
        scope.launch {
            playImpact(amplitude = 76, duration = 15)   // 30%
            delay(100)
            playImpact(amplitude = 128, duration = 20)  // 50%
            delay(100)
            playImpact(amplitude = 180, duration = 30)  // 70%
        }
    }

    private fun playTick() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            vibrator.vibrate(
                VibrationEffect.createPredefined(VibrationEffect.EFFECT_TICK)
            )
        } else {
            playImpact(amplitude = 48, duration = 10)
        }
    }

    // ========================================================================
    // Scene-Specific Patterns
    // ========================================================================

    private fun playSceneActivated() {
        // Satisfying confirmation: medium click + subtle tail
        scope.launch {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                vibrator.vibrate(
                    VibrationEffect.createPredefined(VibrationEffect.EFFECT_CLICK)
                )
            } else {
                playImpact(amplitude = 150, duration = 25)
            }
            delay(50)
            playImpact(amplitude = 64, duration = 15)  // Subtle tail
        }
    }

    private fun playLightsChanged() {
        // Smooth ramp-up
        scope.launch {
            playImpact(amplitude = 48, duration = 15)
            delay(40)
            playImpact(amplitude = 96, duration = 20)
            delay(40)
            playImpact(amplitude = 140, duration = 25)
        }
    }

    private fun playLockEngaged() {
        // Secure "click-clunk" pattern
        scope.launch {
            playImpact(amplitude = 200, duration = 15)  // Sharp click
            delay(30)
            playImpact(amplitude = 128, duration = 40)  // Resonant thud
        }
    }

    // ========================================================================
    // Safety Patterns
    // ========================================================================

    private fun playSafetyViolation() {
        // Three strong pulses (h(x) < 0 warning)
        scope.launch {
            playImpact(amplitude = 255, duration = 50)
            delay(150)
            playImpact(amplitude = 255, duration = 50)
            delay(150)
            playImpact(amplitude = 255, duration = 50)
        }
    }

    // ========================================================================
    // Composition API (API 30+)
    // ========================================================================

    /**
     * Play a custom haptic composition (API 30+)
     *
     * @param primitives List of primitive types to compose
     * @param scales Corresponding scale values (0.0-1.0) for each primitive
     */
    fun playComposition(primitives: List<Int>, scales: List<Float>) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            try {
                val composition = VibrationEffect.startComposition()
                primitives.zip(scales).forEach { (primitive, scale) ->
                    composition.addPrimitive(primitive, scale.coerceIn(0f, 1f))
                }
                vibrator.vibrate(composition.compose())
            } catch (e: Exception) {
                // Fallback to simple impact
                playImpact(amplitude = 128)
            }
        } else {
            // Fallback for older API
            playImpact(amplitude = 128)
        }
    }

    /**
     * Play spectral sweep haptic (for glass effects)
     * Creates a sweeping intensity pattern
     */
    fun playSpectralSweep() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            playComposition(
                primitives = listOf(
                    VibrationEffect.Composition.PRIMITIVE_LOW_TICK,
                    VibrationEffect.Composition.PRIMITIVE_TICK,
                    VibrationEffect.Composition.PRIMITIVE_CLICK,
                    VibrationEffect.Composition.PRIMITIVE_QUICK_RISE,
                ),
                scales = listOf(0.3f, 0.5f, 0.7f, 0.9f)
            )
        } else {
            // Fallback: progressive impact pattern
            scope.launch {
                for (i in 1..4) {
                    playImpact(amplitude = 50 + i * 40, duration = (10 + i * 5).toLong())
                    delay(50)
                }
            }
        }
    }

    companion object {
        /**
         * Convenience function for Composable contexts
         */
        @Volatile
        private var instance: KagamiHaptics? = null

        fun getInstance(context: Context): KagamiHaptics {
            return instance ?: synchronized(this) {
                instance ?: KagamiHaptics(context.applicationContext).also { instance = it }
            }
        }
    }
}

/**
 * Extension function for View to easily trigger haptic feedback
 */
fun View.playHaptic(pattern: HapticPattern) {
    KagamiHaptics.getInstance(context).playWithView(this, pattern)
}

/*
 * Mirror 鏡
 * Haptics provide non-visual feedback for accessibility.
 * Consistent patterns build user intuition.
 * h(x) >= 0. Always.
 */
