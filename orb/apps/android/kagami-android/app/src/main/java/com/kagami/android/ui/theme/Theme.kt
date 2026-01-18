/**
 * Kagami Theme - Material 3 Dynamic Theme
 *
 * Features:
 * - Dynamic color support (Material You on Android 12+)
 * - Wallpaper color extraction and colony blending
 * - High contrast mode support
 * - Reduced motion support
 * - Font scaling support (200%)
 * - Motion tokens for consistent animations (Fibonacci timing)
 * - Predictive back gesture support
 * - Edge-to-edge design
 * - Integrates AccessibilityProvider
 *
 * Colony: Crystal (e7) — Verification & Polish
 */

package com.kagami.android.ui.theme

import android.app.Activity
import android.os.Build
import androidx.activity.BackEventCompat
import androidx.activity.compose.PredictiveBackHandler
import androidx.compose.animation.core.CubicBezierEasing
import androidx.compose.animation.core.Easing
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsControllerCompat
import com.kagami.android.ui.AccessibilityConfig
import com.kagami.android.ui.AccessibilityProvider
import com.kagami.android.ui.LocalAccessibilityConfig
import com.kagami.android.ui.isHighContrastEnabled
import com.kagami.android.ui.isReducedMotionEnabled
import com.kagami.android.ui.isTalkBackEnabled
import kotlinx.coroutines.flow.Flow

// =============================================================================
// MOTION TOKENS (M3 Expressive)
// =============================================================================

/**
 * Motion tokens for consistent animation timing across the app.
 * Based on Material Design 3 motion specifications.
 *
 * Use these instead of hardcoded tween() values:
 * - DurationShort1/2: Micro-interactions (buttons, checkboxes)
 * - DurationMedium1/2: State changes (expansion, selection)
 * - DurationLong1/2: Complex transitions (navigation, dialogs)
 *
 * Example:
 * ```
 * animateFloatAsState(
 *     targetValue = if (expanded) 1f else 0f,
 *     animationSpec = tween(
 *         durationMillis = KagamiMotion.DurationMedium1,
 *         easing = KagamiMotion.EasingStandard
 *     )
 * )
 * ```
 */
object KagamiMotion {
    // Duration tokens (in milliseconds) - Fibonacci sequence
    // Aligned with DesignSystem.kt KagamiDurations for consistency
    const val DurationShort1 = 89     // instant - micro-interactions
    const val DurationShort2 = 144    // fast - button presses
    const val DurationShort3 = 144    // fast (alias)
    const val DurationShort4 = 233    // normal - modal appearances

    const val DurationMedium1 = 233   // normal - state changes
    const val DurationMedium2 = 377   // slow - page transitions
    const val DurationMedium3 = 377   // slow (alias)
    const val DurationMedium4 = 610   // slower - complex reveals

    const val DurationLong1 = 610     // slower - navigation
    const val DurationLong2 = 987     // slowest - ambient motion
    const val DurationLong3 = 987     // slowest (alias)
    const val DurationLong4 = 1597    // background animations

    const val DurationExtraLong1 = 1597  // background animations
    const val DurationExtraLong2 = 2584  // breathing effects
    const val DurationExtraLong3 = 2584  // breathing effects (alias)
    const val DurationExtraLong4 = 4181  // very slow ambient

    // Easing curves (M3 standard)
    val EasingStandard: Easing = CubicBezierEasing(0.2f, 0.0f, 0f, 1.0f)
    val EasingStandardAccelerate: Easing = CubicBezierEasing(0.3f, 0f, 1f, 1f)
    val EasingStandardDecelerate: Easing = CubicBezierEasing(0f, 0f, 0f, 1f)

    val EasingEmphasized: Easing = CubicBezierEasing(0.2f, 0.0f, 0f, 1.0f)
    val EasingEmphasizedAccelerate: Easing = CubicBezierEasing(0.3f, 0f, 0.8f, 0.15f)
    val EasingEmphasizedDecelerate: Easing = CubicBezierEasing(0.05f, 0.7f, 0.1f, 1f)

    val EasingLegacy: Easing = CubicBezierEasing(0.4f, 0f, 0.2f, 1f)
    val EasingLegacyAccelerate: Easing = CubicBezierEasing(0.4f, 0f, 1f, 1f)
    val EasingLegacyDecelerate: Easing = CubicBezierEasing(0f, 0f, 0.2f, 1f)

    val EasingLinear: Easing = CubicBezierEasing(0f, 0f, 1f, 1f)
}

// =============================================================================
// COLOR SCHEMES
// =============================================================================

private val KagamiDarkColorScheme = darkColorScheme(
    // Primary (Crystal-based)
    primary = Primary,
    onPrimary = OnPrimary,
    primaryContainer = PrimaryContainer,
    onPrimaryContainer = OnPrimaryContainer,

    // Secondary (Nexus-based)
    secondary = Secondary,
    onSecondary = OnSecondary,
    secondaryContainer = SecondaryContainer,
    onSecondaryContainer = OnSecondaryContainer,

    // Tertiary (Forge-based)
    tertiary = Tertiary,
    onTertiary = OnTertiary,
    tertiaryContainer = TertiaryContainer,
    onTertiaryContainer = OnTertiaryContainer,

    // Background and Surface (Void palette)
    background = Background,
    onBackground = OnBackground,
    surface = SurfaceColor,
    onSurface = OnSurface,
    surfaceVariant = SurfaceVariant,
    onSurfaceVariant = OnSurfaceVariant,

    // Outline
    outline = Outline,
    outlineVariant = OutlineVariant,

    // Error (SafetyViolation-based)
    error = Error,
    onError = OnError,
    errorContainer = ErrorContainer,
    onErrorContainer = OnErrorContainer,

    // Inverse colors
    inverseSurface = InverseSurface,
    inverseOnSurface = InverseOnSurface,
    inversePrimary = InversePrimary,

    // Scrim
    scrim = Scrim,

    // Surface Container Hierarchy (Material 3)
    surfaceContainerLowest = SurfaceContainerLowest,
    surfaceContainerLow = SurfaceContainerLow,
    surfaceContainer = SurfaceContainer,
    surfaceContainerHigh = SurfaceContainerHigh,
    surfaceContainerHighest = SurfaceContainerHighest,
)

private val KagamiHighContrastColorScheme = darkColorScheme(
    // Primary - High contrast cyan for maximum visibility
    primary = HighContrastColors.accent,
    onPrimary = HighContrastColors.background,
    primaryContainer = HighContrastColors.surface,
    onPrimaryContainer = HighContrastColors.accent,

    // Secondary
    secondary = HighContrastColors.accent,
    onSecondary = HighContrastColors.background,
    secondaryContainer = HighContrastColors.surface,
    onSecondaryContainer = HighContrastColors.accent,

    // Tertiary
    tertiary = HighContrastColors.warning,
    onTertiary = HighContrastColors.background,
    tertiaryContainer = HighContrastColors.surface,
    onTertiaryContainer = HighContrastColors.warning,

    // Background and Surface - Pure black for OLED
    background = HighContrastColors.background,
    onBackground = HighContrastColors.text,
    surface = HighContrastColors.surface,
    onSurface = HighContrastColors.text,
    surfaceVariant = HighContrastColors.surface,
    onSurfaceVariant = HighContrastColors.text,

    // Outline - Full white for maximum contrast
    outline = HighContrastColors.border,
    outlineVariant = HighContrastColors.border,

    // Error
    error = HighContrastColors.error,
    onError = HighContrastColors.background,
    errorContainer = HighContrastColors.surface,
    onErrorContainer = HighContrastColors.error,

    // Inverse
    inverseSurface = HighContrastColors.text,
    inverseOnSurface = HighContrastColors.background,
    inversePrimary = HighContrastColors.accent,

    // Scrim
    scrim = Color.Black,

    // Surface Container Hierarchy - Simplified for high contrast
    surfaceContainerLowest = HighContrastColors.background,
    surfaceContainerLow = HighContrastColors.surface,
    surfaceContainer = HighContrastColors.surface,
    surfaceContainerHigh = HighContrastColors.surface,
    surfaceContainerHighest = Color(0xFF222222),
)

/**
 * Main Kagami theme composable with full Material 3 dynamic color support.
 *
 * @param dynamicColor Enable Material You dynamic colors (Android 12+)
 * @param darkTheme Force dark theme (default true for OLED optimization)
 * @param colonyBlendFactor How much to blend colony colors (0.0-1.0)
 * @param content Theme content
 */
@Composable
fun KagamiTheme(
    dynamicColor: Boolean = true, // Dynamic color enabled by default on Android 12+
    darkTheme: Boolean = true, // Force dark theme for OLED optimization
    colonyBlendFactor: Float = 0.4f, // Colony color blending strength
    content: @Composable () -> Unit
) {
    val context = LocalContext.current

    // Build accessibility configuration
    val accessibilityConfig = remember(context) {
        AccessibilityConfig(
            isReducedMotionEnabled = isReducedMotionEnabled(context),
            isHighContrastEnabled = isHighContrastEnabled(context),
            isTalkBackEnabled = isTalkBackEnabled(context),
            fontScale = context.resources.configuration.fontScale
        )
    }

    // Create dynamic theme configuration
    val dynamicThemeConfig = remember(dynamicColor, colonyBlendFactor) {
        DynamicThemeConfig(
            useDynamicColors = dynamicColor,
            colonyBlendFactor = colonyBlendFactor,
            preserveSafetyColors = true,
            preserveColonySemantics = true,
            forceDarkTheme = darkTheme
        )
    }

    // Choose color scheme based on accessibility and dynamic settings
    val colorScheme = when {
        accessibilityConfig.isHighContrastEnabled -> KagamiHighContrastColorScheme
        dynamicColor && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S -> {
            // Create blended dynamic color scheme
            createDynamicColorScheme(context, dynamicThemeConfig, darkTheme)
        }
        else -> if (darkTheme) KagamiDarkColorScheme else KagamiLightColors
    }

    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as Activity).window

            // Enable edge-to-edge
            WindowCompat.setDecorFitsSystemWindows(window, false)

            // Set transparent status bar for edge-to-edge
            window.statusBarColor = Color.Transparent.toArgb()
            window.navigationBarColor = Color.Transparent.toArgb()

            // Configure status bar appearance
            val insetsController = WindowCompat.getInsetsController(window, view)
            insetsController.isAppearanceLightStatusBars = !darkTheme
            insetsController.isAppearanceLightNavigationBars = !darkTheme
        }
    }

    // Build theme config with accessibility settings
    val themeConfig = remember(accessibilityConfig, dynamicThemeConfig) {
        KagamiThemeConfig(
            isHighContrastMode = accessibilityConfig.isHighContrastEnabled,
            isReducedMotionMode = accessibilityConfig.isReducedMotionEnabled
        )
    }

    CompositionLocalProvider(
        LocalAccessibilityConfig provides accessibilityConfig,
        LocalKagamiTheme provides themeConfig,
        LocalDynamicThemeConfig provides dynamicThemeConfig
    ) {
        MaterialTheme(
            colorScheme = colorScheme,
            typography = Typography,
            content = content
        )
    }
}

/**
 * Composition local for dynamic theme configuration.
 */
val LocalDynamicThemeConfig = androidx.compose.runtime.compositionLocalOf { DynamicThemeConfig() }

/**
 * Predictive back handler with Kagami animations.
 * Provides smooth back gesture with visual feedback.
 */
@Composable
fun KagamiPredictiveBackHandler(
    enabled: Boolean = true,
    onBack: () -> Unit,
    content: @Composable (progress: Float) -> Unit
) {
    var backProgress by remember { mutableFloatStateOf(0f) }

    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
        PredictiveBackHandler(enabled = enabled) { backEvent: Flow<BackEventCompat> ->
            try {
                backEvent.collect { event ->
                    backProgress = event.progress
                }
                // Back gesture completed
                onBack()
            } catch (e: Exception) {
                // Gesture cancelled
            } finally {
                backProgress = 0f
            }
        }
    }

    content(backProgress)
}
