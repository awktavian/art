package com.kagami.xr.ui.theme

import android.app.Activity
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat

/**
 * Kagami XR Theme
 *
 * Material 3 theme optimized for XR experiences.
 * Uses dark theme by default for reduced eye strain in headsets.
 *
 * Colony: Nexus (e4) - Integration
 *
 * h(x) >= 0. Always.
 */

private val DarkColorScheme = darkColorScheme(
    primary = SpatialColors.nexus,
    secondary = SpatialColors.beacon,
    tertiary = SpatialColors.grove,
    background = SpatialColors.background,
    surface = SpatialColors.surface,
    surfaceVariant = SpatialColors.surfaceVariant,
    onPrimary = SpatialColors.textPrimary,
    onSecondary = SpatialColors.textPrimary,
    onTertiary = SpatialColors.textPrimary,
    onBackground = SpatialColors.textPrimary,
    onSurface = SpatialColors.textPrimary,
    onSurfaceVariant = SpatialColors.textSecondary,
    error = SpatialColors.error,
    onError = SpatialColors.textPrimary
)

private val LightColorScheme = lightColorScheme(
    primary = SpatialColors.nexus,
    secondary = SpatialColors.beacon,
    tertiary = SpatialColors.grove,
    // Note: Light theme is rarely used in XR but provided for completeness
)

@Composable
fun KagamiXRTheme(
    darkTheme: Boolean = true,  // Default to dark for XR
    content: @Composable () -> Unit
) {
    val colorScheme = if (darkTheme) DarkColorScheme else LightColorScheme

    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as Activity).window
            window.statusBarColor = colorScheme.background.toArgb()
            WindowCompat.getInsetsController(window, view).isAppearanceLightStatusBars = !darkTheme
        }
    }

    MaterialTheme(
        colorScheme = colorScheme,
        typography = KagamiTypography,
        content = content
    )
}

/*
 * 鏡
 * Dark is kind to eyes in space.
 */
