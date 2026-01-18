/**
 * Kagami Design System - Android Design Tokens
 *
 * Extensible design foundation for Android/WearOS.
 * All values should be semantic and overridable.
 *
 * Accessibility:
 * - Minimum 48dp touch targets
 * - High contrast mode support
 * - Reduced motion support via system settings
 * - Font scaling support (200%)
 */

package com.kagami.android.ui.theme

import android.content.Context
import android.provider.Settings
import androidx.compose.animation.*
import androidx.compose.animation.core.*
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.composed
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.draw.blur
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

// =============================================================================
// COLOR TOKENS (Extended Palette)
// =============================================================================
// NOTE: Primary colors are now defined in Color.kt. This file re-exports
// necessary tokens for backwards compatibility and provides design system utilities.
// See Color.kt for the canonical color definitions.

// Re-export from Color.kt for backwards compatibility
// These are imported via: import com.kagami.android.ui.theme.*

// =============================================================================
// ACCESSIBILITY - TOUCH TARGETS
// =============================================================================

/**
 * Minimum touch target size per Android accessibility guidelines
 * https://support.google.com/accessibility/android/answer/7101858
 */
val MinTouchTargetSize: Dp = 48.dp

/**
 * Recommended touch target size for primary actions
 */
val RecommendedTouchTargetSize: Dp = 56.dp

/**
 * Modifier to ensure minimum touch target size
 */
fun Modifier.accessibleTouchTarget(): Modifier = this.defaultMinSize(
    minWidth = MinTouchTargetSize,
    minHeight = MinTouchTargetSize
)

// =============================================================================
// MOTION TOKENS - Standard Durations
// =============================================================================

object KagamiDurations {
    const val instant = 89
    const val fast = 144
    const val normal = 233
    const val slow = 377
    const val slower = 610
    const val slowest = 987
}

// =============================================================================
// MOTION TOKENS - Standard Easings
// =============================================================================

object KagamiEasing {
    val snap = CubicBezierEasing(0.7f, 0f, 0.3f, 1f)            // Sudden snap
    val sharp = CubicBezierEasing(0.4f, 0f, 0.2f, 1f)           // Decisive
    val bounce = CubicBezierEasing(0.34f, 1.2f, 0.64f, 1f)      // Overshoot
    val elastic = CubicBezierEasing(0.68f, -0.2f, 0.32f, 1.2f)  // Complex
    val smooth = CubicBezierEasing(0.16f, 1f, 0.3f, 1f)         // Default expo-out

    // Deprecated aliases for backwards compatibility
    @Deprecated("Use snap instead", ReplaceWith("snap"))
    val fold = snap
    @Deprecated("Use sharp instead", ReplaceWith("sharp"))
    val cusp = sharp
    @Deprecated("Use bounce instead", ReplaceWith("bounce"))
    val swallowtail = bounce
    @Deprecated("Use elastic instead", ReplaceWith("elastic"))
    val butterfly = elastic
}

// =============================================================================
// SPRING SPECS
// =============================================================================

object KagamiSpring {
    val micro = spring<Float>(dampingRatio = 0.8f, stiffness = Spring.StiffnessHigh)
    val fast = spring<Float>(dampingRatio = 0.75f, stiffness = Spring.StiffnessMediumLow)
    val default = spring<Float>(dampingRatio = 0.7f, stiffness = Spring.StiffnessMedium)
    val soft = spring<Float>(dampingRatio = 0.65f, stiffness = Spring.StiffnessLow)
}

// =============================================================================
// SPACING TOKENS - 8px Grid
// =============================================================================

object KagamiSpacing {
    val unit: Dp = 8.dp
    val xs: Dp = 4.dp
    val sm: Dp = 8.dp
    val md: Dp = 16.dp
    val lg: Dp = 24.dp
    val xl: Dp = 32.dp
    val xxl: Dp = 48.dp
}

// =============================================================================
// RADIUS TOKENS
// =============================================================================

object KagamiRadius {
    val xs: Dp = 4.dp
    val sm: Dp = 8.dp
    val md: Dp = 12.dp
    val lg: Dp = 16.dp
    val xl: Dp = 20.dp
    val full: Dp = 9999.dp
}

// =============================================================================
// GLASS MORPHISM EFFECT
// =============================================================================

/**
 * Glass morphism effect - frosted glass appearance
 *
 * Creates a translucent, blurred background effect commonly used in
 * modern UI design for cards, overlays, and surfaces.
 *
 * @param blurRadius The amount of blur applied (default: 20.dp)
 * @param opacity The background opacity (default: 0.6f)
 * @param tint Optional color tint for the glass (default: null - no tint)
 *
 * Usage:
 * ```
 * Box(
 *     modifier = Modifier
 *         .glassMorphism()
 *         .clip(RoundedCornerShape(16.dp))
 * )
 * ```
 */
fun Modifier.glassMorphism(
    blurRadius: Dp = 20.dp,
    opacity: Float = 0.6f,
    tint: Color? = null
): Modifier = composed {
    val glassColor = tint ?: VoidLight
    val gradientColors = listOf(
        glassColor.copy(alpha = opacity * 0.8f),
        glassColor.copy(alpha = opacity * 0.4f),
        glassColor.copy(alpha = opacity * 0.6f)
    )

    this
        .blur(blurRadius)
        .drawBehind {
            // Multi-layered gradient for depth
            drawRect(
                brush = Brush.linearGradient(
                    colors = gradientColors,
                    start = Offset(0f, 0f),
                    end = Offset(size.width, size.height)
                )
            )
            // Subtle highlight at top edge
            drawRect(
                brush = Brush.verticalGradient(
                    colors = listOf(
                        Color.White.copy(alpha = 0.15f),
                        Color.Transparent
                    ),
                    startY = 0f,
                    endY = size.height * 0.3f
                )
            )
        }
}

/**
 * Glass morphism variant with border highlight
 * Adds a subtle luminous border effect
 */
fun Modifier.glassMorphismWithBorder(
    blurRadius: Dp = 20.dp,
    opacity: Float = 0.6f,
    borderColor: Color = Crystal,
    borderOpacity: Float = 0.3f
): Modifier = composed {
    this
        .glassMorphism(blurRadius, opacity)
        .graphicsLayer {
            // Border glow effect via shadow
            shadowElevation = 4f
            ambientShadowColor = borderColor.copy(alpha = borderOpacity)
            spotShadowColor = borderColor.copy(alpha = borderOpacity)
        }
}

// =============================================================================
// ACCESSIBILITY - REDUCED MOTION SUPPORT
// =============================================================================

/**
 * Check if reduced motion is enabled via system settings
 * Uses ANIMATOR_DURATION_SCALE as per Android guidelines
 */
fun isReducedMotionEnabled(context: Context): Boolean {
    return try {
        val scale = Settings.Global.getFloat(
            context.contentResolver,
            Settings.Global.ANIMATOR_DURATION_SCALE,
            1.0f
        )
        // If animation scale is 0, user has disabled animations
        scale == 0f
    } catch (e: Exception) {
        false
    }
}

/**
 * Composable to check reduced motion setting
 */
@Composable
@ReadOnlyComposable
fun rememberReducedMotionEnabled(): Boolean {
    val context = LocalContext.current
    return isReducedMotionEnabled(context)
}

/**
 * Get animation duration respecting reduced motion settings
 */
@Composable
fun accessibleDuration(normalDuration: Int): Int {
    return if (rememberReducedMotionEnabled()) 0 else normalDuration
}

// =============================================================================
// ANIMATION MODIFIERS
// =============================================================================

/**
 * Press effect - scales down slightly when pressed
 * Respects reduced motion settings
 */
fun Modifier.pressEffect(
    pressScale: Float = 0.95f
): Modifier = composed {
    val reducedMotion = rememberReducedMotionEnabled()
    val interactionSource = remember { MutableInteractionSource() }
    val isPressed by interactionSource.collectIsPressedAsState()

    val scale by animateFloatAsState(
        targetValue = if (isPressed && !reducedMotion) pressScale else 1f,
        animationSpec = KagamiSpring.micro,
        label = "press_scale"
    )

    this
        .scale(scale)
        .clickable(
            interactionSource = interactionSource,
            indication = null,
            onClick = {}
        )
}

/**
 * Pulse effect - continuous subtle scale animation
 * Disabled when reduced motion is enabled
 */
fun Modifier.pulseEffect(): Modifier = composed {
    val reducedMotion = rememberReducedMotionEnabled()

    if (reducedMotion) {
        return@composed this
    }

    val infiniteTransition = rememberInfiniteTransition(label = "pulse")

    val scale by infiniteTransition.animateFloat(
        initialValue = 1f,
        targetValue = 1.05f,
        animationSpec = infiniteRepeatable(
            animation = tween(987, easing = EaseInOutSine),
            repeatMode = RepeatMode.Reverse
        ),
        label = "pulse_scale"
    )

    val alpha by infiniteTransition.animateFloat(
        initialValue = 1f,
        targetValue = 0.7f,
        animationSpec = infiniteRepeatable(
            animation = tween(987, easing = EaseInOutSine),
            repeatMode = RepeatMode.Reverse
        ),
        label = "pulse_alpha"
    )

    this.graphicsLayer {
        scaleX = scale
        scaleY = scale
        this.alpha = alpha
    }
}

/**
 * Glow effect - animated radial glow using Canvas
 * Creates a pulsing luminous effect around the element.
 * Disabled when reduced motion is enabled.
 *
 * @param color The color of the glow (default: Crystal)
 * @param glowRadius The maximum radius of the glow effect in dp
 * @param minAlpha Minimum alpha of the glow animation
 * @param maxAlpha Maximum alpha of the glow animation
 */
fun Modifier.glowEffect(
    color: Color = Crystal,
    glowRadius: Dp = 16.dp,
    minAlpha: Float = 0.1f,
    maxAlpha: Float = 0.5f
): Modifier = composed {
    val reducedMotion = rememberReducedMotionEnabled()

    if (reducedMotion) {
        return@composed this
    }

    val infiniteTransition = rememberInfiniteTransition(label = "glow")

    val glowAlpha by infiniteTransition.animateFloat(
        initialValue = minAlpha,
        targetValue = maxAlpha,
        animationSpec = infiniteRepeatable(
            animation = tween(1597, easing = EaseInOutSine),
            repeatMode = RepeatMode.Reverse
        ),
        label = "glow_alpha"
    )

    val glowScale by infiniteTransition.animateFloat(
        initialValue = 0.8f,
        targetValue = 1.2f,
        animationSpec = infiniteRepeatable(
            animation = tween(1597, easing = EaseInOutSine),
            repeatMode = RepeatMode.Reverse
        ),
        label = "glow_scale"
    )

    this.drawBehind {
        // Draw multiple layers of radial gradient for soft glow
        val centerX = size.width / 2f
        val centerY = size.height / 2f
        val baseRadius = minOf(size.width, size.height) / 2f
        val effectiveRadius = (baseRadius + glowRadius.toPx()) * glowScale

        // Outer glow layer (softest, largest)
        drawCircle(
            brush = Brush.radialGradient(
                colors = listOf(
                    color.copy(alpha = glowAlpha * 0.3f),
                    color.copy(alpha = glowAlpha * 0.1f),
                    Color.Transparent
                ),
                center = Offset(centerX, centerY),
                radius = effectiveRadius * 1.5f
            ),
            radius = effectiveRadius * 1.5f,
            center = Offset(centerX, centerY)
        )

        // Middle glow layer
        drawCircle(
            brush = Brush.radialGradient(
                colors = listOf(
                    color.copy(alpha = glowAlpha * 0.5f),
                    color.copy(alpha = glowAlpha * 0.2f),
                    Color.Transparent
                ),
                center = Offset(centerX, centerY),
                radius = effectiveRadius
            ),
            radius = effectiveRadius,
            center = Offset(centerX, centerY)
        )

        // Inner glow layer (brightest, smallest)
        drawCircle(
            brush = Brush.radialGradient(
                colors = listOf(
                    color.copy(alpha = glowAlpha * 0.8f),
                    color.copy(alpha = glowAlpha * 0.4f),
                    Color.Transparent
                ),
                center = Offset(centerX, centerY),
                radius = effectiveRadius * 0.6f
            ),
            radius = effectiveRadius * 0.6f,
            center = Offset(centerX, centerY)
        )
    }
}

/**
 * Static glow effect - non-animated glow using Canvas
 * Use this when reduced motion is preferred or for constant glow.
 *
 * @param color The color of the glow
 * @param alpha The alpha/intensity of the glow
 * @param radius The radius of the glow effect
 */
fun Modifier.staticGlow(
    color: Color = Crystal,
    alpha: Float = 0.4f,
    radius: Dp = 12.dp
): Modifier = this.drawBehind {
    val centerX = size.width / 2f
    val centerY = size.height / 2f
    val baseRadius = minOf(size.width, size.height) / 2f
    val effectiveRadius = baseRadius + radius.toPx()

    drawCircle(
        brush = Brush.radialGradient(
            colors = listOf(
                color.copy(alpha = alpha),
                color.copy(alpha = alpha * 0.5f),
                Color.Transparent
            ),
            center = Offset(centerX, centerY),
            radius = effectiveRadius
        ),
        radius = effectiveRadius,
        center = Offset(centerX, centerY)
    )
}

/**
 * Slide up entrance animation
 */
@Composable
fun slideUpEntranceSpec(delayMillis: Int = 0): AnimatedContentTransitionScope<*>.() -> ContentTransform {
    val reducedMotion = rememberReducedMotionEnabled()
    val duration = if (reducedMotion) 0 else KagamiDurations.normal
    val fastDuration = if (reducedMotion) 0 else KagamiDurations.fast
    val actualDelay = if (reducedMotion) 0 else delayMillis

    return {
        fadeIn(
            animationSpec = tween(
                durationMillis = duration,
                delayMillis = actualDelay,
                easing = KagamiEasing.smooth
            )
        ) + slideInVertically(
            animationSpec = tween(
                durationMillis = duration,
                delayMillis = actualDelay,
                easing = KagamiEasing.smooth
            ),
            initialOffsetY = { if (reducedMotion) 0 else it / 4 }
        ) togetherWith fadeOut(
            animationSpec = tween(
                durationMillis = fastDuration,
                easing = KagamiEasing.sharp
            )
        )
    }
}

// =============================================================================
// THEME OVERRIDE - Extensibility
// =============================================================================

/**
 * Theme configuration for design visionary overrides
 * Includes accessibility options
 */
data class KagamiThemeConfig(
    val accentColor: Color = Crystal,
    val modeAskColor: Color = Grove,
    val modePlanColor: Color = Beacon,
    val modeAgentColor: Color = Forge,
    val animationScale: Float = 1f,  // 0 = no animations, 2 = exaggerated
    val hapticsEnabled: Boolean = true,
    // Accessibility options
    val isHighContrastMode: Boolean = false,
    val isReducedMotionMode: Boolean = false
)

val LocalKagamiTheme = compositionLocalOf { KagamiThemeConfig() }

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

/**
 * Create a tween with Kagami easing
 * Respects reduced motion settings
 */
@Composable
fun <T> kagamiTweenAccessible(
    normalDurationMillis: Int = KagamiDurations.normal,
    delayMillis: Int = 0,
    easing: Easing = KagamiEasing.smooth
): TweenSpec<T> {
    val duration = accessibleDuration(normalDurationMillis)
    return tween(
        durationMillis = duration,
        delayMillis = if (duration == 0) 0 else delayMillis,
        easing = easing
    )
}

/**
 * Create a tween with Kagami easing (non-composable version)
 */
fun <T> kagamiTween(
    durationMillis: Int = KagamiDurations.normal,
    delayMillis: Int = 0,
    easing: Easing = KagamiEasing.smooth
): TweenSpec<T> = tween(
    durationMillis = durationMillis,
    delayMillis = delayMillis,
    easing = easing
)

/**
 * Staggered delay for list items
 * Returns 0 if reduced motion is enabled
 */
@Composable
fun staggeredDelayAccessible(index: Int, baseDelay: Int = 30): Int {
    return if (rememberReducedMotionEnabled()) 0 else index * baseDelay
}

/**
 * Staggered delay for list items (non-composable version)
 */
fun staggeredDelay(index: Int, baseDelay: Int = 30): Int = index * baseDelay

// =============================================================================
// ACCESSIBILITY - COLOR UTILITIES
// =============================================================================

/**
 * Get accessible color based on high contrast mode
 */
@Composable
fun accessibleColor(
    normalColor: Color,
    highContrastColor: Color
): Color {
    val config = LocalKagamiTheme.current
    return if (config.isHighContrastMode) highContrastColor else normalColor
}

/**
 * Get text color with sufficient contrast
 * Returns white or black based on background luminance
 */
fun getContrastingTextColor(backgroundColor: Color): Color {
    // Calculate relative luminance using sRGB formula
    val r = backgroundColor.red
    val g = backgroundColor.green
    val b = backgroundColor.blue
    val luminance = 0.299f * r + 0.587f * g + 0.114f * b

    // Return white for dark backgrounds, black for light backgrounds
    return if (luminance < 0.5f) Color.White else Color.Black
}
