/**
 * Kagami Wear OS - Haptic Feedback Utility
 *
 * Colony: Grove (e6) - Research
 *
 * Provides consistent haptic feedback across all Wear screens.
 * Handles API level differences automatically.
 */

package com.kagami.wear.util

import android.content.Context
import android.os.Build
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager

/**
 * Centralized haptic feedback for Wear OS app.
 *
 * Usage:
 * ```
 * HapticFeedback.trigger(context, HapticFeedback.Type.TAP)
 * HapticFeedback.trigger(context, HapticFeedback.Type.SUCCESS)
 * ```
 */
object HapticFeedback {

    /**
     * Types of haptic feedback.
     */
    enum class Type {
        /** Short, confirming feedback for successful actions */
        SUCCESS,

        /** Longer pattern for errors or failures */
        ERROR,

        /** Brief tap feedback for button presses */
        TAP,

        /** Very brief click for list item selections */
        CLICK,

        /** Double tap for confirmations */
        CONFIRM
    }

    /**
     * Trigger haptic feedback.
     *
     * @param context Android context for vibrator service
     * @param type Type of haptic feedback
     */
    fun trigger(context: Context, type: Type) {
        val vibrator = getVibrator(context)

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val effect = when (type) {
                Type.SUCCESS -> VibrationEffect.createOneShot(
                    50,
                    VibrationEffect.DEFAULT_AMPLITUDE
                )
                Type.ERROR -> VibrationEffect.createWaveform(
                    longArrayOf(0, 100, 50, 100),
                    -1
                )
                Type.TAP -> VibrationEffect.createOneShot(
                    25,
                    VibrationEffect.DEFAULT_AMPLITUDE
                )
                Type.CLICK -> VibrationEffect.createOneShot(
                    10,
                    VibrationEffect.DEFAULT_AMPLITUDE
                )
                Type.CONFIRM -> VibrationEffect.createWaveform(
                    longArrayOf(0, 30, 30, 30),
                    -1
                )
            }
            vibrator.vibrate(effect)
        } else {
            @Suppress("DEPRECATION")
            when (type) {
                Type.SUCCESS -> vibrator.vibrate(50)
                Type.ERROR -> vibrator.vibrate(longArrayOf(0, 100, 50, 100), -1)
                Type.TAP -> vibrator.vibrate(25)
                Type.CLICK -> vibrator.vibrate(10)
                Type.CONFIRM -> vibrator.vibrate(longArrayOf(0, 30, 30, 30), -1)
            }
        }
    }

    /**
     * Trigger success haptic.
     */
    fun success(context: Context) = trigger(context, Type.SUCCESS)

    /**
     * Trigger error haptic.
     */
    fun error(context: Context) = trigger(context, Type.ERROR)

    /**
     * Trigger tap haptic.
     */
    fun tap(context: Context) = trigger(context, Type.TAP)

    /**
     * Trigger click haptic.
     */
    fun click(context: Context) = trigger(context, Type.CLICK)

    /**
     * Trigger confirm haptic.
     */
    fun confirm(context: Context) = trigger(context, Type.CONFIRM)

    private fun getVibrator(context: Context): Vibrator {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            val vibratorManager = context.getSystemService(
                Context.VIBRATOR_MANAGER_SERVICE
            ) as VibratorManager
            vibratorManager.defaultVibrator
        } else {
            @Suppress("DEPRECATION")
            context.getSystemService(Context.VIBRATOR_SERVICE) as Vibrator
        }
    }
}
