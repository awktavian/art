package com.kagami.android.tiles

import android.graphics.drawable.Icon
import android.os.Build
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import android.service.quicksettings.Tile
import android.service.quicksettings.TileService
import com.kagami.android.KagamiApp
import com.kagami.android.R
import com.kagami.android.services.HapticPattern
import com.kagami.android.services.KagamiApiService
import com.kagami.android.services.KagamiHaptics
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.*
import javax.inject.Inject

/**
 * Kagami Quick Settings Tiles
 *
 * Colony: Nexus (e4) - Integration
 *
 * Quick Settings Tiles:
 * - Lights Toggle: Turn all lights on/off
 * - Movie Mode: Activate movie mode scene
 * - Goodnight: Activate goodnight scene
 * - Fireplace: Toggle fireplace
 * - Hero Action: Context-aware suggested action
 * - Shades: Open/close all shades
 *
 * Features:
 * - Haptic feedback on all interactions
 * - Accessibility labels for TalkBack
 * - Error state handling with retry
 *
 * Architecture Note: TileServices use field injection via Hilt's @AndroidEntryPoint.
 * The apiService is injected, not accessed via KagamiApp.instance.
 *
 * h(x) >= 0. Always.
 */

// MARK: - Base Tile Service

abstract class KagamiTileService : TileService() {

    protected val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    /**
     * API service - accessed via application instance for TileService compatibility.
     * TileServices have limited lifecycle and @AndroidEntryPoint doesn't work well with them.
     * This is an acceptable exception to the DI rule for system services.
     */
    protected val apiService: KagamiApiService
        get() = KagamiApp.instance.apiService

    /**
     * Haptics service for feedback
     */
    protected val haptics: KagamiHaptics by lazy {
        KagamiHaptics.getInstance(applicationContext)
    }

    /**
     * Direct vibrator for fallback haptics when KagamiHaptics unavailable
     */
    protected val vibrator: Vibrator by lazy {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            val vibratorManager = getSystemService(VIBRATOR_MANAGER_SERVICE) as VibratorManager
            vibratorManager.defaultVibrator
        } else {
            @Suppress("DEPRECATION")
            getSystemService(VIBRATOR_SERVICE) as Vibrator
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        scope.cancel()
    }

    /**
     * Play haptic feedback for tile interaction.
     */
    protected fun playHaptic(pattern: HapticPattern) {
        try {
            haptics.play(pattern)
        } catch (e: Exception) {
            // Fallback to basic vibration
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                vibrator.vibrate(VibrationEffect.createOneShot(30, VibrationEffect.DEFAULT_AMPLITUDE))
            } else {
                @Suppress("DEPRECATION")
                vibrator.vibrate(30)
            }
        }
    }

    /**
     * Play success haptic.
     */
    protected fun playSuccessHaptic() = playHaptic(HapticPattern.SUCCESS)

    /**
     * Play error haptic.
     */
    protected fun playErrorHaptic() = playHaptic(HapticPattern.ERROR)

    /**
     * Play selection haptic.
     */
    protected fun playSelectionHaptic() = playHaptic(HapticPattern.SELECTION)

    /**
     * Play scene activation haptic.
     */
    protected fun playSceneHaptic() = playHaptic(HapticPattern.SCENE_ACTIVATED)

    protected fun updateTileState(
        state: Int,
        label: String? = null,
        subtitle: String? = null,
        icon: Int? = null,
        contentDescription: String? = null
    ) {
        qsTile?.let { tile ->
            tile.state = state
            label?.let { tile.label = it }
            subtitle?.let { tile.subtitle = it }
            icon?.let { tile.icon = Icon.createWithResource(this, it) }

            // Set content description for accessibility
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                contentDescription?.let { tile.stateDescription = it }
            }

            tile.updateTile()
        }
    }

    protected fun setActive(
        label: String? = null,
        subtitle: String? = null,
        contentDescription: String? = null
    ) {
        val desc = contentDescription ?: "$label is active. $subtitle"
        updateTileState(Tile.STATE_ACTIVE, label, subtitle, contentDescription = desc)
    }

    protected fun setInactive(
        label: String? = null,
        subtitle: String? = null,
        contentDescription: String? = null
    ) {
        val desc = contentDescription ?: "$label is inactive. $subtitle"
        updateTileState(Tile.STATE_INACTIVE, label, subtitle, contentDescription = desc)
    }

    protected fun setUnavailable(
        label: String? = null,
        subtitle: String? = null,
        contentDescription: String? = null
    ) {
        val desc = contentDescription ?: "$label is unavailable. $subtitle"
        updateTileState(Tile.STATE_UNAVAILABLE, label, subtitle, contentDescription = desc)
    }
}

// MARK: - 1. Lights Toggle Tile

class LightsTileService : KagamiTileService() {

    private var lightsOn = false

    override fun onStartListening() {
        super.onStartListening()
        // Check current state
        scope.launch {
            try {
                // Would check actual light state
                lightsOn = false
                withContext(Dispatchers.Main) {
                    updateState()
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    setUnavailable(
                        label = "Lights",
                        subtitle = "Offline",
                        contentDescription = "Lights control is offline. Unable to connect to Kagami."
                    )
                }
            }
        }
    }

    override fun onClick() {
        super.onClick()
        playSelectionHaptic()

        scope.launch {
            try {
                lightsOn = !lightsOn
                val level = if (lightsOn) 80 else 0
                apiService.setLights(level)

                withContext(Dispatchers.Main) {
                    playHaptic(HapticPattern.LIGHTS_CHANGED)
                    updateState()
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    playErrorHaptic()
                    setUnavailable(
                        label = "Lights",
                        subtitle = "Error",
                        contentDescription = "Failed to change lights. Tap to retry."
                    )
                }
            }
        }
    }

    private fun updateState() {
        if (lightsOn) {
            setActive(
                label = "Lights On",
                subtitle = "80%",
                contentDescription = "Lights are on at 80 percent. Double tap to turn off."
            )
        } else {
            setInactive(
                label = "Lights Off",
                subtitle = "Tap to turn on",
                contentDescription = "Lights are off. Double tap to turn on."
            )
        }
    }
}

// MARK: - 2. Movie Mode Tile

class MovieModeTileService : KagamiTileService() {

    private var movieModeActive = false

    override fun onStartListening() {
        super.onStartListening()
        updateState()
    }

    override fun onClick() {
        super.onClick()
        playSelectionHaptic()

        scope.launch {
            try {
                if (movieModeActive) {
                    apiService.executeScene("movie_mode_exit")
                } else {
                    apiService.executeScene("movie_mode")
                }
                movieModeActive = !movieModeActive

                withContext(Dispatchers.Main) {
                    playSceneHaptic()
                    updateState()
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    playErrorHaptic()
                    setUnavailable(
                        label = "Movie",
                        subtitle = "Error",
                        contentDescription = "Failed to change movie mode. Tap to retry."
                    )
                }
            }
        }
    }

    private fun updateState() {
        if (movieModeActive) {
            setActive(
                label = "Movie Mode",
                subtitle = "Active",
                contentDescription = "Movie mode is active. Lights dimmed for viewing. Double tap to exit."
            )
        } else {
            setInactive(
                label = "Movie Mode",
                subtitle = "Tap to activate",
                contentDescription = "Movie mode is off. Double tap to dim lights for viewing."
            )
        }
    }
}

// MARK: - 3. Goodnight Tile

class GoodnightTileService : KagamiTileService() {

    override fun onStartListening() {
        super.onStartListening()
        setInactive(
            label = "Goodnight",
            subtitle = "Tap to activate",
            contentDescription = "Goodnight scene. Double tap to turn off all lights and lock doors."
        )
    }

    override fun onClick() {
        super.onClick()
        playSelectionHaptic()

        scope.launch {
            try {
                apiService.executeScene("goodnight")

                withContext(Dispatchers.Main) {
                    playSceneHaptic()
                    setActive(
                        label = "Goodnight",
                        subtitle = "Activated",
                        contentDescription = "Goodnight scene activated. All lights off, doors locked."
                    )

                    // Reset after a delay
                    delay(2000)
                    setInactive(
                        label = "Goodnight",
                        subtitle = "Tap to activate",
                        contentDescription = "Goodnight scene. Double tap to turn off all lights and lock doors."
                    )
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    playErrorHaptic()
                    setUnavailable(
                        label = "Goodnight",
                        subtitle = "Error",
                        contentDescription = "Failed to activate goodnight scene. Tap to retry."
                    )
                }
            }
        }
    }
}

// MARK: - 4. Fireplace Tile

class FireplaceTileService : KagamiTileService() {

    private var fireplaceOn = false

    override fun onStartListening() {
        super.onStartListening()
        updateState()
    }

    override fun onClick() {
        super.onClick()
        playSelectionHaptic()

        scope.launch {
            try {
                fireplaceOn = !fireplaceOn
                apiService.toggleFireplace(fireplaceOn)

                withContext(Dispatchers.Main) {
                    playSuccessHaptic()
                    updateState()
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    playErrorHaptic()
                    setUnavailable(
                        label = "Fireplace",
                        subtitle = "Error",
                        contentDescription = "Failed to control fireplace. Tap to retry."
                    )
                }
            }
        }
    }

    private fun updateState() {
        if (fireplaceOn) {
            setActive(
                label = "Fireplace",
                subtitle = "On",
                contentDescription = "Fireplace is on. Double tap to turn off."
            )
        } else {
            setInactive(
                label = "Fireplace",
                subtitle = "Off",
                contentDescription = "Fireplace is off. Double tap to turn on."
            )
        }
    }
}

// MARK: - 5. Hero Action Tile (Context-Aware)

class HeroActionTileService : KagamiTileService() {

    override fun onStartListening() {
        super.onStartListening()
        updateForContext()
    }

    override fun onClick() {
        super.onClick()
        playSelectionHaptic()

        val action = getContextualAction()

        scope.launch {
            try {
                apiService.executeScene(action.sceneId)

                withContext(Dispatchers.Main) {
                    playSceneHaptic()
                    setActive(
                        label = action.label,
                        subtitle = "Activated",
                        contentDescription = "${action.label} scene activated."
                    )

                    // Reset after a delay
                    delay(2000)
                    updateForContext()
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    playErrorHaptic()
                    setUnavailable(
                        label = action.label,
                        subtitle = "Error",
                        contentDescription = "Failed to activate ${action.label} scene. Tap to retry."
                    )
                }
            }
        }
    }

    private fun updateForContext() {
        val action = getContextualAction()
        setInactive(
            label = action.label,
            subtitle = action.subtitle,
            contentDescription = "Suggested action: ${action.label}. ${action.subtitle}. Double tap to activate."
        )
    }

    private data class ContextAction(
        val label: String,
        val subtitle: String,
        val sceneId: String
    )

    private fun getContextualAction(): ContextAction {
        val hour = java.time.LocalTime.now().hour

        return when (hour) {
            in 5..8 -> ContextAction("Morning", "Start your day", "good_morning")
            in 9..16 -> ContextAction("Focus", "Optimal lighting", "focus")
            in 17..20 -> ContextAction("Movie", "Theater mode", "movie_mode")
            in 21..23 -> ContextAction("Goodnight", "Wind down", "goodnight")
            else -> ContextAction("Sleep", "Rest well", "sleep")
        }
    }
}

// MARK: - 6. Shades Tile

class ShadesTileService : KagamiTileService() {

    private var shadesOpen = true

    override fun onStartListening() {
        super.onStartListening()
        updateState()
    }

    override fun onClick() {
        super.onClick()
        playSelectionHaptic()

        scope.launch {
            try {
                shadesOpen = !shadesOpen
                val action = if (shadesOpen) "open" else "close"
                apiService.controlShades(action)

                withContext(Dispatchers.Main) {
                    playSuccessHaptic()
                    updateState()
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    playErrorHaptic()
                    setUnavailable(
                        label = "Shades",
                        subtitle = "Error",
                        contentDescription = "Failed to control shades. Tap to retry."
                    )
                }
            }
        }
    }

    private fun updateState() {
        if (shadesOpen) {
            setActive(
                label = "Shades",
                subtitle = "Open",
                contentDescription = "Shades are open. Double tap to close."
            )
        } else {
            setInactive(
                label = "Shades",
                subtitle = "Closed",
                contentDescription = "Shades are closed. Double tap to open."
            )
        }
    }
}

/*
 * Mirror
 * Quick Settings bring Kagami to the notification shade.
 * One swipe, one tap, done.
 * h(x) >= 0. Always.
 */
