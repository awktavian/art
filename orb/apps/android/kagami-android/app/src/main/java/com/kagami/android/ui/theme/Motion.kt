/**
 * Kagami Motion System — Material Motion
 *
 * Implements a comprehensive motion system based on:
 * - Standard animation timing (89, 144, 233, 377, 610, 987ms)
 * - Standard easing curves
 * - Material 3 Expressive patterns
 * - Proper reduced motion support
 *
 * All animations in Kagami should use these tokens for consistency.
 */

package com.kagami.android.ui.theme

import androidx.compose.animation.*
import androidx.compose.animation.core.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.composed
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.LocalContext
import com.kagami.android.ui.LocalAccessibilityConfig

// =============================================================================
// DURATION TOKENS
// =============================================================================

/**
 * Standard duration tokens for consistent animation timing.
 */
object KagamiFibonacciDurations {
    // Core Fibonacci sequence
    const val F8 = 89       // Micro-interactions (button press, toggle)
    const val F9 = 144      // Fast transitions (state changes)
    const val F10 = 233     // Normal transitions (page changes)
    const val F11 = 377     // Slow transitions (modal appear)
    const val F12 = 610     // Complex reveals (navigation)
    const val F13 = 987     // Ambient motion (breathing effects)
    const val F14 = 1597    // Very slow (background animations)
    const val F15 = 2584    // Ultra slow (breathing cycles)
    const val F16 = 4181    // Extended ambient

    // Semantic aliases for Material 3 compatibility
    const val Instant = 50
    const val Micro = F8
    const val Fast = F9
    const val Normal = F10
    const val Slow = F11
    const val Slower = F12
    const val Slowest = F13
    const val Breathing = F15

    // Material 3 Expressive token mapping
    const val DurationShort1 = F8
    const val DurationShort2 = F9
    const val DurationMedium1 = F10
    const val DurationMedium2 = F11
    const val DurationLong1 = F12
    const val DurationLong2 = F13
    const val DurationExtraLong1 = F14
    const val DurationExtraLong2 = F15
}

// =============================================================================
// STANDARD EASING CURVES
// =============================================================================

/**
 * Standard easing curves for expressive motion.
 */
object KagamiCatastropheEasing {
    /**
     * Snap — Sudden snap transition
     * Use for: Toggle switches, binary state changes
     */
    val Snap = CubicBezierEasing(0.7f, 0f, 0.3f, 1f)
    @Deprecated("Use Snap instead", ReplaceWith("Snap"))
    val Fold = Snap

    /**
     * Sharp — Decisive, confident motion
     * Use for: Primary actions, navigation
     */
    val Sharp = CubicBezierEasing(0.4f, 0f, 0.2f, 1f)
    @Deprecated("Use Sharp instead", ReplaceWith("Sharp"))
    val Cusp = Sharp

    /**
     * Bounce — Overshoot with recovery
     * Use for: Bouncy entrances, playful feedback
     */
    val Bounce = CubicBezierEasing(0.34f, 1.2f, 0.64f, 1f)
    @Deprecated("Use Bounce instead", ReplaceWith("Bounce"))
    val Swallowtail = Bounce

    /**
     * Elastic — Complex, multi-phase motion
     * Use for: Complex reveals, orchestrated animations
     */
    val Elastic = CubicBezierEasing(0.68f, -0.2f, 0.32f, 1.2f)
    @Deprecated("Use Elastic instead", ReplaceWith("Elastic"))
    val Butterfly = Elastic

    /**
     * Smooth — Standard exponential-out
     * Use for: General transitions, safe default
     */
    val Smooth = CubicBezierEasing(0.16f, 1f, 0.3f, 1f)

    /**
     * Spring — Natural spring-like motion
     * Use for: Interactive feedback, press effects
     */
    val Spring = CubicBezierEasing(0.34f, 1.56f, 0.64f, 1f)
}

// =============================================================================
// MATERIAL 3 EASING CURVES
// =============================================================================

/**
 * Material 3 standard easing curves.
 */
object KagamiM3Easing {
    // Standard curves
    val Standard = CubicBezierEasing(0.2f, 0.0f, 0f, 1.0f)
    val StandardAccelerate = CubicBezierEasing(0.3f, 0f, 1f, 1f)
    val StandardDecelerate = CubicBezierEasing(0f, 0f, 0f, 1f)

    // Emphasized curves
    val Emphasized = CubicBezierEasing(0.2f, 0.0f, 0f, 1.0f)
    val EmphasizedAccelerate = CubicBezierEasing(0.3f, 0f, 0.8f, 0.15f)
    val EmphasizedDecelerate = CubicBezierEasing(0.05f, 0.7f, 0.1f, 1f)

    // Legacy curves (for compatibility)
    val Legacy = CubicBezierEasing(0.4f, 0f, 0.2f, 1f)
    val LegacyAccelerate = CubicBezierEasing(0.4f, 0f, 1f, 1f)
    val LegacyDecelerate = CubicBezierEasing(0f, 0f, 0.2f, 1f)

    // Linear (for progress indicators)
    val Linear = LinearEasing
}

// =============================================================================
// SPRING SPECIFICATIONS
// =============================================================================

/**
 * Spring-based animation specifications for natural motion.
 */
object KagamiSpringSpecs {
    /**
     * Micro spring — Quick, snappy feedback
     */
    val Micro = spring<Float>(
        dampingRatio = Spring.DampingRatioMediumBouncy,
        stiffness = Spring.StiffnessHigh
    )

    /**
     * Fast spring — Responsive interactions
     */
    val Fast = spring<Float>(
        dampingRatio = Spring.DampingRatioLowBouncy,
        stiffness = Spring.StiffnessMediumLow
    )

    /**
     * Default spring — Standard motion
     */
    val Default = spring<Float>(
        dampingRatio = Spring.DampingRatioMediumBouncy,
        stiffness = Spring.StiffnessMedium
    )

    /**
     * Soft spring — Gentle, ambient motion
     */
    val Soft = spring<Float>(
        dampingRatio = Spring.DampingRatioHighBouncy,
        stiffness = Spring.StiffnessLow
    )

    /**
     * No bounce spring — Smooth deceleration
     */
    val NoBounce = spring<Float>(
        dampingRatio = Spring.DampingRatioNoBouncy,
        stiffness = Spring.StiffnessMedium
    )
}

// Note: Accessible animation helpers (accessibleDuration, staggeredDelay, etc.)
// are defined in DesignSystem.kt to avoid duplication

// =============================================================================
// ANIMATION MODIFIERS
// =============================================================================

/**
 * Scale animation on press with Fibonacci timing.
 */
fun Modifier.kagamiPressScale(
    pressedScale: Float = 0.96f
): Modifier = composed {
    val config = LocalAccessibilityConfig.current
    if (config.isReducedMotionEnabled) {
        this
    } else {
        // Implementation would use interaction source
        this
    }
}

/**
 * Pulse animation for active/listening states.
 */
fun Modifier.kagamiPulse(
    minScale: Float = 1f,
    maxScale: Float = 1.05f,
    durationMillis: Int = KagamiFibonacciDurations.Slowest
): Modifier = composed {
    val config = LocalAccessibilityConfig.current
    if (config.isReducedMotionEnabled) {
        this
    } else {
        val infiniteTransition = rememberInfiniteTransition(label = "pulse")
        val scale = infiniteTransition.animateFloat(
            initialValue = minScale,
            targetValue = maxScale,
            animationSpec = infiniteRepeatable(
                animation = tween(durationMillis, easing = EaseInOutSine),
                repeatMode = RepeatMode.Reverse
            ),
            label = "pulse_scale"
        )
        this.scale(scale.value)
    }
}

/**
 * Breathing animation for ambient states.
 */
fun Modifier.kagamiBreathe(
    minAlpha: Float = 0.7f,
    maxAlpha: Float = 1f,
    durationMillis: Int = KagamiFibonacciDurations.Breathing
): Modifier = composed {
    val config = LocalAccessibilityConfig.current
    if (config.isReducedMotionEnabled) {
        this
    } else {
        val infiniteTransition = rememberInfiniteTransition(label = "breathe")
        val alpha = infiniteTransition.animateFloat(
            initialValue = minAlpha,
            targetValue = maxAlpha,
            animationSpec = infiniteRepeatable(
                animation = tween(durationMillis, easing = EaseInOutSine),
                repeatMode = RepeatMode.Reverse
            ),
            label = "breathe_alpha"
        )
        this.graphicsLayer { this.alpha = alpha.value }
    }
}

/**
 * Spectral shimmer effect for glass design.
 */
fun Modifier.kagamiSpectralShimmer(
    durationMillis: Int = KagamiFibonacciDurations.F14
): Modifier = composed {
    val config = LocalAccessibilityConfig.current
    if (config.isReducedMotionEnabled) {
        this
    } else {
        val infiniteTransition = rememberInfiniteTransition(label = "shimmer")
        val offset = infiniteTransition.animateFloat(
            initialValue = -1f,
            targetValue = 2f,
            animationSpec = infiniteRepeatable(
                animation = tween(durationMillis, easing = LinearEasing),
                repeatMode = RepeatMode.Restart
            ),
            label = "shimmer_offset"
        )
        // Shimmer would be implemented with shader or gradient
        this.graphicsLayer { translationX = offset.value * 10 }
    }
}

// Note: Navigation animation specifications (kagamiEnterTransition, etc.)
// are defined in DesignSystem.kt which has the KagamiTransitions object

/*
 * Motion creates emotional connection.
 */
