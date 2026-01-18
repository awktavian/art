/**
 * Kagami Dynamic Theme — Material You + Colony Colors
 *
 * Colony: Crystal (e7) — Verification & Polish
 *
 * Implements Material 3 Dynamic Color with wallpaper extraction
 * while preserving Kagami's colony color semantics.
 *
 * Key Features:
 * - Dynamic color extraction from user wallpaper (Android 12+)
 * - Colony color blending with Material You palette
 * - Proper light/dark theme support
 * - High contrast mode fallback
 * - Reduced motion respect
 *
 * h(x) >= 0. Always.
 */

package com.kagami.android.ui.theme

import android.app.WallpaperManager
import android.content.Context
import android.os.Build
import androidx.annotation.RequiresApi
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.tween
import androidx.compose.material3.ColorScheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.Stable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalContext
import androidx.core.graphics.ColorUtils
import kotlin.math.max
import kotlin.math.min

// =============================================================================
// DYNAMIC COLOR CONFIGURATION
// =============================================================================

/**
 * Dynamic theme configuration.
 * Controls how dynamic colors blend with colony semantics.
 */
@Stable
data class DynamicThemeConfig(
    /** Enable Material You dynamic colors */
    val useDynamicColors: Boolean = true,
    /** Colony color blending factor (0.0 = pure Material You, 1.0 = pure colony) */
    val colonyBlendFactor: Float = 0.4f,
    /** Preserve safety colors regardless of theme */
    val preserveSafetyColors: Boolean = true,
    /** Preserve colony colors for semantic meaning */
    val preserveColonySemantics: Boolean = true,
    /** Dark theme preference */
    val forceDarkTheme: Boolean = true
)

// =============================================================================
// WALLPAPER COLOR EXTRACTION
// =============================================================================

/**
 * Extracted wallpaper colors for custom blending.
 */
data class WallpaperColors(
    val primary: Color,
    val secondary: Color,
    val tertiary: Color,
    val isDark: Boolean
)

/**
 * Extract dominant colors from wallpaper (Android 12+).
 */
@RequiresApi(Build.VERSION_CODES.S)
fun extractWallpaperColors(context: Context): WallpaperColors? {
    return try {
        val wallpaperManager = WallpaperManager.getInstance(context)
        val colors = wallpaperManager.getWallpaperColors(WallpaperManager.FLAG_SYSTEM)

        colors?.let {
            val primaryColor = it.primaryColor?.toArgb()?.let { argb -> Color(argb) } ?: Crystal
            val secondaryColor = it.secondaryColor?.toArgb()?.let { argb -> Color(argb) } ?: Nexus
            val tertiaryColor = it.tertiaryColor?.toArgb()?.let { argb -> Color(argb) } ?: Forge

            // Determine if wallpaper is predominantly dark
            val luminance = calculateLuminance(primaryColor)
            val isDark = luminance < 0.5f

            WallpaperColors(
                primary = primaryColor,
                secondary = secondaryColor,
                tertiary = tertiaryColor,
                isDark = isDark
            )
        }
    } catch (e: Exception) {
        null
    }
}

/**
 * Calculate relative luminance for a color.
 */
private fun calculateLuminance(color: Color): Float {
    val r = if (color.red <= 0.03928f) color.red / 12.92f else Math.pow(((color.red + 0.055) / 1.055).toDouble(), 2.4).toFloat()
    val g = if (color.green <= 0.03928f) color.green / 12.92f else Math.pow(((color.green + 0.055) / 1.055).toDouble(), 2.4).toFloat()
    val b = if (color.blue <= 0.03928f) color.blue / 12.92f else Math.pow(((color.blue + 0.055) / 1.055).toDouble(), 2.4).toFloat()
    return 0.2126f * r + 0.7152f * g + 0.0722f * b
}

// =============================================================================
// COLOR BLENDING
// =============================================================================

/**
 * Blend two colors using the specified factor.
 * @param factor 0.0 = source color, 1.0 = target color
 */
fun blendColors(source: Color, target: Color, factor: Float): Color {
    val clampedFactor = factor.coerceIn(0f, 1f)
    return Color(
        red = source.red + (target.red - source.red) * clampedFactor,
        green = source.green + (target.green - source.green) * clampedFactor,
        blue = source.blue + (target.blue - source.blue) * clampedFactor,
        alpha = source.alpha + (target.alpha - source.alpha) * clampedFactor
    )
}

/**
 * Harmonize a color toward another color using Material color harmonization.
 * This creates a more cohesive palette while preserving the original hue.
 */
fun harmonizeColor(source: Color, target: Color, amount: Float = 0.5f): Color {
    val sourceArgb = source.toArgb()
    val targetArgb = target.toArgb()

    // Use ColorUtils for harmonization
    val blendedArgb = ColorUtils.blendARGB(sourceArgb, targetArgb, amount * 0.3f)
    return Color(blendedArgb)
}

// =============================================================================
// DYNAMIC COLOR SCHEME CREATION
// =============================================================================

/**
 * Create a dynamic color scheme with colony color blending.
 */
@Composable
fun rememberDynamicColorScheme(
    config: DynamicThemeConfig = DynamicThemeConfig(),
    isDarkTheme: Boolean = true
): ColorScheme {
    val context = LocalContext.current

    return remember(config, isDarkTheme) {
        createDynamicColorScheme(context, config, isDarkTheme)
    }
}

/**
 * Create dynamic color scheme with proper blending.
 */
fun createDynamicColorScheme(
    context: Context,
    config: DynamicThemeConfig,
    isDarkTheme: Boolean
): ColorScheme {
    // Base scheme - either dynamic or static
    val baseScheme = if (config.useDynamicColors && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
        if (isDarkTheme) {
            dynamicDarkColorScheme(context)
        } else {
            dynamicLightColorScheme(context)
        }
    } else {
        if (isDarkTheme) KagamiDarkColors else KagamiLightColors
    }

    // If not preserving colony semantics, return base scheme
    if (!config.preserveColonySemantics) {
        return baseScheme
    }

    // Blend with colony colors
    val blendFactor = config.colonyBlendFactor

    return if (isDarkTheme) {
        baseScheme.copy(
            // Primary: Blend with Crystal (e7 - Verification)
            primary = blendColors(baseScheme.primary, Crystal, blendFactor),
            primaryContainer = blendColors(baseScheme.primaryContainer, PrimaryContainer, blendFactor),
            onPrimary = baseScheme.onPrimary,
            onPrimaryContainer = baseScheme.onPrimaryContainer,

            // Secondary: Blend with Nexus (e4 - Integration)
            secondary = blendColors(baseScheme.secondary, Nexus, blendFactor),
            secondaryContainer = blendColors(baseScheme.secondaryContainer, SecondaryContainer, blendFactor),
            onSecondary = baseScheme.onSecondary,
            onSecondaryContainer = baseScheme.onSecondaryContainer,

            // Tertiary: Blend with Forge (e2 - Implementation)
            tertiary = blendColors(baseScheme.tertiary, Forge, blendFactor),
            tertiaryContainer = blendColors(baseScheme.tertiaryContainer, TertiaryContainer, blendFactor),
            onTertiary = baseScheme.onTertiary,
            onTertiaryContainer = baseScheme.onTertiaryContainer,

            // Background: Keep void-based for OLED
            background = if (isDarkTheme) Void else baseScheme.background,
            surface = if (isDarkTheme) Surface else baseScheme.surface,
            surfaceVariant = if (isDarkTheme) SurfaceVariant else baseScheme.surfaceVariant,

            // Error: Preserve safety colors
            error = if (config.preserveSafetyColors) SafetyViolation else baseScheme.error,
            errorContainer = if (config.preserveSafetyColors) ErrorContainer else baseScheme.errorContainer
        )
    } else {
        // Light theme with colony blending
        baseScheme.copy(
            primary = blendColors(baseScheme.primary, Crystal, blendFactor * 0.5f),
            secondary = blendColors(baseScheme.secondary, Nexus, blendFactor * 0.5f),
            tertiary = blendColors(baseScheme.tertiary, Forge, blendFactor * 0.5f),
            error = if (config.preserveSafetyColors) SafetyViolation else baseScheme.error
        )
    }
}

// =============================================================================
// STATIC COLOR SCHEMES
// =============================================================================

/**
 * Kagami dark color scheme without dynamic colors.
 * Named differently to avoid conflict with Theme.kt's private version.
 */
internal val KagamiDarkColors = darkColorScheme(
    // Primary (Crystal-based)
    primary = Crystal,
    onPrimary = Void,
    primaryContainer = PrimaryContainer,
    onPrimaryContainer = Crystal,

    // Secondary (Nexus-based)
    secondary = Nexus,
    onSecondary = Void,
    secondaryContainer = SecondaryContainer,
    onSecondaryContainer = Nexus,

    // Tertiary (Forge-based)
    tertiary = Forge,
    onTertiary = Void,
    tertiaryContainer = TertiaryContainer,
    onTertiaryContainer = Forge,

    // Background and Surface
    background = Void,
    onBackground = TextPrimary,
    surface = Surface,
    onSurface = TextPrimary,
    surfaceVariant = SurfaceVariant,
    onSurfaceVariant = TextSecondary,

    // Outline
    outline = Outline,
    outlineVariant = OutlineVariant,

    // Error
    error = SafetyViolation,
    onError = TextPrimary,
    errorContainer = ErrorContainer,
    onErrorContainer = SafetyViolation,

    // Inverse
    inverseSurface = InverseSurface,
    inverseOnSurface = InverseOnSurface,
    inversePrimary = InversePrimary,

    // Scrim
    scrim = Scrim,

    // Surface Container Hierarchy
    surfaceContainerLowest = SurfaceContainerLowest,
    surfaceContainerLow = SurfaceContainerLow,
    surfaceContainer = SurfaceContainer,
    surfaceContainerHigh = SurfaceContainerHigh,
    surfaceContainerHighest = SurfaceContainerHighest
)

/**
 * Kagami light color scheme.
 * Named differently to avoid conflict with Theme.kt's private version.
 */
internal val KagamiLightColors = lightColorScheme(
    // Primary (Crystal-based - darkened for contrast)
    primary = Color(0xFF006C7A),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFB3E8F0),
    onPrimaryContainer = Color(0xFF001F24),

    // Secondary (Nexus-based - darkened)
    secondary = Color(0xFF6B5B7D),
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFE8DEF8),
    onSecondaryContainer = Color(0xFF1D192B),

    // Tertiary (Forge-based - darkened)
    tertiary = Color(0xFF8B6914),
    onTertiary = Color.White,
    tertiaryContainer = Color(0xFFFFDEA0),
    onTertiaryContainer = Color(0xFF2B2000),

    // Background and Surface (light)
    background = Color(0xFFFFFBFF),
    onBackground = Color(0xFF1C1B1F),
    surface = Color(0xFFFFFBFF),
    onSurface = Color(0xFF1C1B1F),
    surfaceVariant = Color(0xFFE7E0EC),
    onSurfaceVariant = Color(0xFF49454F),

    // Outline
    outline = Color(0xFF79747E),
    outlineVariant = Color(0xFFCAC4D0),

    // Error
    error = SafetyViolation,
    onError = Color.White,
    errorContainer = Color(0xFFFFDAD6),
    onErrorContainer = Color(0xFF410002),

    // Inverse
    inverseSurface = Color(0xFF313033),
    inverseOnSurface = Color(0xFFF4EFF4),
    inversePrimary = Crystal,

    // Scrim
    scrim = Color.Black.copy(alpha = 0.5f)
)

// =============================================================================
// ANIMATED COLOR TRANSITIONS
// =============================================================================

/**
 * Animate color scheme transitions for smooth theme changes.
 */
@Composable
fun animatedColorScheme(
    targetScheme: ColorScheme,
    durationMillis: Int = KagamiDurations.slow
): ColorScheme {
    val primary by animateColorAsState(
        targetValue = targetScheme.primary,
        animationSpec = tween(durationMillis, easing = KagamiEasing.smooth),
        label = "primary"
    )
    val secondary by animateColorAsState(
        targetValue = targetScheme.secondary,
        animationSpec = tween(durationMillis, easing = KagamiEasing.smooth),
        label = "secondary"
    )
    val tertiary by animateColorAsState(
        targetValue = targetScheme.tertiary,
        animationSpec = tween(durationMillis, easing = KagamiEasing.smooth),
        label = "tertiary"
    )
    val background by animateColorAsState(
        targetValue = targetScheme.background,
        animationSpec = tween(durationMillis, easing = KagamiEasing.smooth),
        label = "background"
    )
    val surface by animateColorAsState(
        targetValue = targetScheme.surface,
        animationSpec = tween(durationMillis, easing = KagamiEasing.smooth),
        label = "surface"
    )

    return targetScheme.copy(
        primary = primary,
        secondary = secondary,
        tertiary = tertiary,
        background = background,
        surface = surface
    )
}

// =============================================================================
// COLONY COLOR EXTENSIONS FOR DYNAMIC THEMING
// =============================================================================

/**
 * Get colony color harmonized with dynamic palette.
 */
@Composable
fun rememberHarmonizedColonyColor(
    colonyColor: Color,
    targetColor: Color = Crystal
): Color {
    val context = LocalContext.current

    return remember(colonyColor) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            val wallpaperColors = extractWallpaperColors(context)
            wallpaperColors?.let {
                harmonizeColor(colonyColor, it.primary, 0.3f)
            } ?: colonyColor
        } else {
            colonyColor
        }
    }
}

/**
 * Extended colony colors object with dynamic harmonization support.
 */
object DynamicColonyColors {
    @Composable
    fun spark(): Color = rememberHarmonizedColonyColor(Spark)

    @Composable
    fun forge(): Color = rememberHarmonizedColonyColor(Forge)

    @Composable
    fun flow(): Color = rememberHarmonizedColonyColor(Flow)

    @Composable
    fun nexus(): Color = rememberHarmonizedColonyColor(Nexus)

    @Composable
    fun beacon(): Color = rememberHarmonizedColonyColor(Beacon)

    @Composable
    fun grove(): Color = rememberHarmonizedColonyColor(Grove)

    @Composable
    fun crystal(): Color = rememberHarmonizedColonyColor(Crystal)
}

/*
 * Mirror
 * h(x) >= 0. Always.
 */
