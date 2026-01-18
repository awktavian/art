/**
 * PrismEffects.kt — Kagami Glass Effects for Android
 *
 * Glass effects with chromatic dispersion.
 *
 * The 7 brand colors map to spectral wavelengths, creating rainbow effects
 * that emerge from glass surfaces like light through a prism.
 *
 * P2 Optimization:
 * - Hardware layers for complex animations (LAYER_TYPE_HARDWARE)
 * - Reduced overdraw via compositingStrategy
 * - Cached brush instances to reduce allocations
 * - Conditional animation complexity based on device capability
 */

package com.kagami.android.ui.effects

import android.graphics.BlurMaskFilter
import android.os.Build
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.*
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.composed
import androidx.compose.ui.draw.BlurredEdgeTreatment
import androidx.compose.ui.draw.blur
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.draw.drawWithCache
import androidx.compose.ui.draw.drawWithContent
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.*
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.kagami.android.ui.theme.*
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlin.math.cos
import kotlin.math.sin

// =============================================================================
// PERFORMANCE OPTIMIZATION UTILITIES
// =============================================================================

/**
 * Configuration for animation performance optimization.
 */
object PrismPerformanceConfig {
    /**
     * Whether to use hardware layers for complex animations.
     * Hardware layers are cached on the GPU for faster compositing.
     */
    var useHardwareLayers: Boolean = true

    /**
     * Whether to reduce animation complexity on low-end devices.
     */
    var reduceComplexityOnLowEnd: Boolean = true

    /**
     * Maximum number of simultaneous animated effects.
     * Reduces overdraw on complex screens.
     */
    var maxSimultaneousEffects: Int = 3

    /**
     * Threshold for simplified rendering (device RAM in MB).
     */
    var lowEndThresholdMb: Int = 2048

    /**
     * Check if device is low-end based on API level and other heuristics.
     */
    fun isLowEndDevice(): Boolean {
        return Build.VERSION.SDK_INT < Build.VERSION_CODES.O ||
                Runtime.getRuntime().maxMemory() < lowEndThresholdMb * 1024 * 1024
    }
}

/**
 * Modifier extension for applying hardware layer during animation.
 * This caches the composable as a texture on the GPU for faster compositing.
 */
fun Modifier.hardwareLayerDuringAnimation(
    isAnimating: Boolean
): Modifier = this.graphicsLayer {
    // Use hardware layer during animation, software when static
    compositingStrategy = if (isAnimating && PrismPerformanceConfig.useHardwareLayers) {
        CompositingStrategy.Offscreen
    } else {
        CompositingStrategy.Auto
    }
}

/**
 * Optimized compositing strategy for animations.
 * Reduces overdraw by batching draw calls.
 */
fun Modifier.optimizedCompositing(): Modifier = this.graphicsLayer {
    // Offscreen compositing reduces overdraw for complex effects
    compositingStrategy = CompositingStrategy.Offscreen
}

// =============================================================================
// SPECTRAL COLORS (Wavelength Mapping)
// =============================================================================

/**
 * Spectral color mapping following physical light wavelengths:
 * Red (620nm) → Violet (400nm)
 */
enum class SpectralColor(
    val color: Color,
    val wavelengthNm: Int,
    val dispersionDelayMs: Int
) {
    SPARK(Spark, 620, 0),      // Red arrives first
    FORGE(Forge, 590, 8),      // Orange
    FLOW(Flow, 570, 16),       // Yellow-Teal
    NEXUS(Nexus, 510, 24),     // Green-Purple
    BEACON(Beacon, 475, 32),   // Cyan-Amber
    GROVE(Grove, 445, 40),     // Blue-Green
    CRYSTAL(Crystal, 400, 48); // Violet arrives last

    companion object {
        val all = values().toList()

        /** Get color at a normalized phase (0-1) */
        fun at(phase: Float): Color {
            val idx = ((phase * 7) % 7).toInt().coerceIn(0, 6)
            return values()[idx].color
        }

        /** Get spectral color by index */
        fun byIndex(index: Int): SpectralColor = values()[index.coerceIn(0, 6)]
    }
}

// =============================================================================
// COLOR LINE GRADIENTS
// =============================================================================

/**
 * Color line combinations for triadic color relationships.
 * Each line represents a complementary color combination.
 */
object FanoLines {
    // Line 123: Spark-Forge-Flow (Warm spectrum concentration)
    val line123 = listOf(SpectralColor.SPARK, SpectralColor.FORGE, SpectralColor.FLOW)

    // Line 145: Spark-Nexus-Beacon (Red-green-cyan diagonal)
    val line145 = listOf(SpectralColor.SPARK, SpectralColor.NEXUS, SpectralColor.BEACON)

    // Line 176: Spark-Crystal-Grove (Red-violet-blue harmonic)
    val line176 = listOf(SpectralColor.SPARK, SpectralColor.CRYSTAL, SpectralColor.GROVE)

    // Line 246: Forge-Nexus-Grove (Orange-green-blue triadic)
    val line246 = listOf(SpectralColor.FORGE, SpectralColor.NEXUS, SpectralColor.GROVE)

    // Line 257: Forge-Beacon-Crystal (Warm-to-cool transition)
    val line257 = listOf(SpectralColor.FORGE, SpectralColor.BEACON, SpectralColor.CRYSTAL)

    // Line 347: Flow-Nexus-Crystal (Yellow-green-violet path)
    val line347 = listOf(SpectralColor.FLOW, SpectralColor.NEXUS, SpectralColor.CRYSTAL)

    // Line 365: Flow-Grove-Beacon (Yellow-blue-cyan arc)
    val line365 = listOf(SpectralColor.FLOW, SpectralColor.GROVE, SpectralColor.BEACON)

    val allLines = listOf(line123, line145, line176, line246, line257, line347, line365)

    /**
     * Find the Fano line containing two colonies and return the third (product)
     */
    fun findProduct(first: SpectralColor, second: SpectralColor): SpectralColor? {
        for (line in allLines) {
            if (line.contains(first) && line.contains(second)) {
                return line.find { it != first && it != second }
            }
        }
        return null
    }

    /**
     * Check if three colonies form a Fano line
     */
    fun isValidLine(a: SpectralColor, b: SpectralColor, c: SpectralColor): Boolean {
        val set = setOf(a, b, c)
        return allLines.any { it.toSet() == set }
    }
}

/**
 * Color line gradient brushes for visual effects
 */
object FanoGradients {
    fun line123(angle: Float = 135f): Brush = Brush.linearGradient(
        colorStops = arrayOf(
            0f to Spark,
            0.5f to Forge,
            1f to Flow
        ),
        start = Offset.Zero,
        end = Offset(1f, 1f)
    )

    fun line145(angle: Float = 135f): Brush = Brush.linearGradient(
        colorStops = arrayOf(
            0f to Spark,
            0.5f to Nexus,
            1f to Beacon
        ),
        start = Offset.Zero,
        end = Offset(1f, 1f)
    )

    fun line176(angle: Float = 135f): Brush = Brush.linearGradient(
        colorStops = arrayOf(
            0f to Spark,
            0.5f to Crystal,
            1f to Grove
        ),
        start = Offset.Zero,
        end = Offset(1f, 1f)
    )

    fun line246(angle: Float = 135f): Brush = Brush.linearGradient(
        colorStops = arrayOf(
            0f to Forge,
            0.5f to Nexus,
            1f to Grove
        ),
        start = Offset.Zero,
        end = Offset(1f, 1f)
    )

    fun line257(angle: Float = 135f): Brush = Brush.linearGradient(
        colorStops = arrayOf(
            0f to Forge,
            0.5f to Beacon,
            1f to Crystal
        ),
        start = Offset.Zero,
        end = Offset(1f, 1f)
    )

    fun line347(angle: Float = 135f): Brush = Brush.linearGradient(
        colorStops = arrayOf(
            0f to Flow,
            0.5f to Nexus,
            1f to Crystal
        ),
        start = Offset.Zero,
        end = Offset(1f, 1f)
    )

    fun line365(angle: Float = 135f): Brush = Brush.linearGradient(
        colorStops = arrayOf(
            0f to Flow,
            0.5f to Grove,
            1f to Beacon
        ),
        start = Offset.Zero,
        end = Offset(1f, 1f)
    )

    /** Get gradient for a Fano line by index */
    fun forLine(index: Int): Brush = when (index % 7) {
        0 -> line123()
        1 -> line145()
        2 -> line176()
        3 -> line246()
        4 -> line257()
        5 -> line347()
        6 -> line365()
        else -> line123()
    }

    /** Create gradient from specific line colors */
    fun fromLine(line: List<SpectralColor>): Brush = Brush.linearGradient(
        colorStops = arrayOf(
            0f to line[0].color,
            0.5f to line[1].color,
            1f to line[2].color
        ),
        start = Offset.Zero,
        end = Offset(1f, 1f)
    )
}

// =============================================================================
// DISCOVERY STATES (Effects intensify with sustained interaction)
// =============================================================================

/**
 * Discovery states for glass effects:
 * Effects are discovered, not announced.
 */
enum class DiscoveryState(
    val opacity: Float,
    val animationIntensity: Float
) {
    REST(0f, 0f),           // Default state
    GLANCE(0.10f, 0.2f),    // < 150ms touch
    INTEREST(0.25f, 0.5f),  // 150-500ms touch
    FOCUS(0.40f, 0.8f),     // > 500ms touch
    ENGAGE(0.60f, 1.0f);    // Active tap/click

    companion object {
        fun fromTouchDuration(durationMs: Long): DiscoveryState = when {
            durationMs < 150 -> GLANCE
            durationMs < 500 -> INTEREST
            else -> FOCUS
        }
    }
}

// =============================================================================
// DISPERSION TIMING (Physics-accurate delays)
// =============================================================================

/**
 * Physics-accurate dispersion delays based on wavelength.
 * Red light arrives first, violet arrives last (8ms between adjacent colors).
 */
object DispersionTiming {
    const val SPARK_DELAY = 0
    const val FORGE_DELAY = 8
    const val FLOW_DELAY = 16
    const val NEXUS_DELAY = 24
    const val BEACON_DELAY = 32
    const val GROVE_DELAY = 40
    const val CRYSTAL_DELAY = 48

    fun delayForColor(color: SpectralColor): Int = color.dispersionDelayMs

    /** Create staggered animation specs for each color */
    fun staggeredSpec(baseDuration: Int): List<Pair<SpectralColor, TweenSpec<Float>>> =
        SpectralColor.all.map { color ->
            color to tween(
                durationMillis = baseDuration,
                delayMillis = color.dispersionDelayMs,
                easing = KagamiEasing.smooth
            )
        }
}

// =============================================================================
// SPECTRAL DISCOVERY MODIFIER
// =============================================================================

/**
 * Modifier that tracks touch duration and intensifies prismatic effects.
 * Implements the "Reveal, Don't Announce" principle.
 *
 * @param onDiscoveryChange Callback when discovery state changes
 * @param baseColor The colony color to use for effects
 */
fun Modifier.spectralDiscovery(
    baseColor: SpectralColor = SpectralColor.CRYSTAL,
    onDiscoveryChange: ((DiscoveryState) -> Unit)? = null
): Modifier = composed {
    val reducedMotion = rememberReducedMotionEnabled()
    val scope = rememberCoroutineScope()

    var discoveryState by remember { mutableStateOf(DiscoveryState.REST) }
    var touchStartTime by remember { mutableStateOf(0L) }
    var isTouching by remember { mutableStateOf(false) }

    // Animated opacity based on discovery state
    val effectOpacity by animateFloatAsState(
        targetValue = if (reducedMotion) 0f else discoveryState.opacity,
        animationSpec = spring(
            dampingRatio = 0.7f,
            stiffness = Spring.StiffnessMediumLow
        ),
        label = "discovery_opacity"
    )

    // Animated intensity
    val animationIntensity by animateFloatAsState(
        targetValue = discoveryState.animationIntensity,
        animationSpec = spring(dampingRatio = 0.8f),
        label = "discovery_intensity"
    )

    // Update discovery state based on touch duration
    LaunchedEffect(isTouching) {
        if (isTouching && !reducedMotion) {
            touchStartTime = System.currentTimeMillis()
            discoveryState = DiscoveryState.GLANCE
            onDiscoveryChange?.invoke(discoveryState)

            // Progress through states
            delay(150)
            if (isTouching) {
                discoveryState = DiscoveryState.INTEREST
                onDiscoveryChange?.invoke(discoveryState)
            }

            delay(350)
            if (isTouching) {
                discoveryState = DiscoveryState.FOCUS
                onDiscoveryChange?.invoke(discoveryState)
            }
        } else {
            discoveryState = DiscoveryState.REST
            onDiscoveryChange?.invoke(discoveryState)
        }
    }

    this
        .pointerInput(Unit) {
            detectTapGestures(
                onPress = {
                    isTouching = true
                    tryAwaitRelease()
                    // Flash to ENGAGE on release if we had focus
                    if (discoveryState == DiscoveryState.FOCUS && !reducedMotion) {
                        discoveryState = DiscoveryState.ENGAGE
                        onDiscoveryChange?.invoke(discoveryState)
                        scope.launch {
                            delay(200)
                            discoveryState = DiscoveryState.REST
                            onDiscoveryChange?.invoke(discoveryState)
                        }
                    }
                    isTouching = false
                }
            )
        }
        .drawWithContent {
            drawContent()

            if (effectOpacity > 0.01f) {
                // Chromatic edge effect
                val dispersion = 3.dp.toPx() * animationIntensity

                // Warm edge (red arrives first)
                val warmBrush = Brush.linearGradient(
                    colorStops = arrayOf(
                        0f to Spark.copy(alpha = 0.25f * effectOpacity),
                        0.14f to Forge.copy(alpha = 0.18f * effectOpacity),
                        0.28f to Flow.copy(alpha = 0.12f * effectOpacity),
                        0.42f to Color.Transparent
                    ),
                    start = Offset.Zero,
                    end = Offset(size.width * 0.5f, size.height * 0.5f)
                )

                // Cool edge (violet arrives last)
                val coolBrush = Brush.linearGradient(
                    colorStops = arrayOf(
                        0f to Crystal.copy(alpha = 0.25f * effectOpacity),
                        0.14f to Grove.copy(alpha = 0.18f * effectOpacity),
                        0.28f to Beacon.copy(alpha = 0.12f * effectOpacity),
                        0.42f to Color.Transparent
                    ),
                    start = Offset(size.width, size.height),
                    end = Offset(size.width * 0.5f, size.height * 0.5f)
                )

                drawRect(brush = warmBrush, blendMode = BlendMode.Screen)
                drawRect(brush = coolBrush, blendMode = BlendMode.Screen)
            }
        }
}

// =============================================================================
// FANO LINE GLOW
// =============================================================================

/**
 * Shows the multiplication relationship when colonies interact.
 * When two colonies on a Fano line are brought together, the third glows.
 *
 * @param firstColony The first colony in the interaction
 * @param secondColony The second colony in the interaction
 * @param isActive Whether the glow is currently active
 */
@Composable
fun FanoLineGlow(
    firstColony: SpectralColor,
    secondColony: SpectralColor,
    isActive: Boolean,
    modifier: Modifier = Modifier
) {
    val reducedMotion = rememberReducedMotionEnabled()
    val productColony = remember(firstColony, secondColony) {
        FanoLines.findProduct(firstColony, secondColony)
    }

    if (productColony == null) return

    val glowAlpha by animateFloatAsState(
        targetValue = if (isActive && !reducedMotion) 0.6f else 0f,
        animationSpec = spring(
            dampingRatio = 0.6f,
            stiffness = Spring.StiffnessMediumLow
        ),
        label = "fano_glow_alpha"
    )

    val pulseScale = if (isActive && !reducedMotion) {
        val infiniteTransition = rememberInfiniteTransition(label = "fano_pulse")
        infiniteTransition.animateFloat(
            initialValue = 1f,
            targetValue = 1.15f,
            animationSpec = infiniteRepeatable(
                animation = tween(987, easing = EaseInOutSine),
                repeatMode = RepeatMode.Reverse
            ),
            label = "fano_pulse_scale"
        ).value
    } else 1f

    Box(
        modifier = modifier,
        contentAlignment = Alignment.Center
    ) {
        // The Fano line gradient connecting the three
        Canvas(
            modifier = Modifier
                .fillMaxSize()
                .graphicsLayer {
                    alpha = glowAlpha
                    scaleX = pulseScale
                    scaleY = pulseScale
                }
        ) {
            val line = listOf(firstColony, productColony, secondColony)
            val brush = Brush.sweepGradient(
                colors = line.map { it.color } + firstColony.color,
                center = Offset(size.width / 2, size.height / 2)
            )

            drawCircle(
                brush = brush,
                radius = size.minDimension / 2,
                blendMode = BlendMode.Screen
            )

            // Inner product glow
            drawCircle(
                color = productColony.color.copy(alpha = 0.4f),
                radius = size.minDimension / 4,
                blendMode = BlendMode.Screen
            )
        }
    }
}

/**
 * Composable showing Fano line discovery when dragging across elements
 */
@Composable
fun FanoLineReveal(
    startColony: SpectralColor?,
    endColony: SpectralColor?,
    modifier: Modifier = Modifier
) {
    val reducedMotion = rememberReducedMotionEnabled()

    val productColony = remember(startColony, endColony) {
        if (startColony != null && endColony != null && startColony != endColony) {
            FanoLines.findProduct(startColony, endColony)
        } else null
    }

    val revealAlpha by animateFloatAsState(
        targetValue = if (productColony != null && !reducedMotion) 1f else 0f,
        animationSpec = tween(
            durationMillis = KagamiDurations.normal,
            easing = KagamiEasing.smooth
        ),
        label = "fano_reveal"
    )

    if (productColony != null && startColony != null && endColony != null && revealAlpha > 0.01f) {
        Box(
            modifier = modifier
                .graphicsLayer { alpha = revealAlpha },
            contentAlignment = Alignment.Center
        ) {
            Text(
                text = "${startColony.name} + ${endColony.name} = ${productColony.name}",
                color = productColony.color,
                style = TextStyle(fontSize = 14.sp, fontWeight = FontWeight.Medium)
            )
        }
    }
}

// =============================================================================
// CHROMATIC PULSE
// =============================================================================

/**
 * Success animation using color state transitions.
 * Creates a subtle color wave on successful action.
 *
 * @param isSuccess Whether to show success animation
 * @param baseColor The base color to pulse from
 * @param onAnimationComplete Callback when animation completes
 */
@Composable
fun Modifier.chromaticPulse(
    isSuccess: Boolean,
    baseColor: Color = Crystal,
    onAnimationComplete: (() -> Unit)? = null
): Modifier = composed {
    val reducedMotion = rememberReducedMotionEnabled()
    val scope = rememberCoroutineScope()

    var pulsePhase by remember { mutableStateOf(0f) }

    // Animate through spectrum on success
    LaunchedEffect(isSuccess) {
        if (isSuccess && !reducedMotion) {
            // Animate phase from 0 to 1 (full spectrum cycle)
            val startTime = System.currentTimeMillis()
            val duration = KagamiDurations.slower.toLong()

            while (System.currentTimeMillis() - startTime < duration) {
                pulsePhase = (System.currentTimeMillis() - startTime).toFloat() / duration
                delay(16) // ~60fps
            }
            pulsePhase = 0f
            onAnimationComplete?.invoke()
        }
    }

    // Animated color based on pulse phase
    val pulseColor by animateColorAsState(
        targetValue = if (pulsePhase > 0f && !reducedMotion) {
            SpectralColor.at(pulsePhase)
        } else baseColor,
        animationSpec = tween(
            durationMillis = KagamiDurations.instant,
            easing = LinearEasing
        ),
        label = "chromatic_pulse_color"
    )

    val pulseAlpha by animateFloatAsState(
        targetValue = if (pulsePhase > 0f && !reducedMotion) {
            0.3f + 0.2f * sin(pulsePhase * Math.PI.toFloat())
        } else 0f,
        animationSpec = tween(durationMillis = KagamiDurations.instant),
        label = "chromatic_pulse_alpha"
    )

    this.drawWithContent {
        drawContent()
        if (pulseAlpha > 0.01f) {
            drawRect(
                color = pulseColor.copy(alpha = pulseAlpha),
                blendMode = BlendMode.Screen
            )
        }
    }
}

/**
 * Standalone chromatic pulse composable for success states
 */
@Composable
fun ChromaticPulseOverlay(
    isActive: Boolean,
    modifier: Modifier = Modifier,
    onComplete: (() -> Unit)? = null
) {
    val reducedMotion = rememberReducedMotionEnabled()

    val infiniteTransition = if (isActive && !reducedMotion) {
        rememberInfiniteTransition(label = "chromatic_pulse")
    } else null

    val hueRotation = infiniteTransition?.animateFloat(
        initialValue = 0f,
        targetValue = 360f,
        animationSpec = infiniteRepeatable(
            animation = tween(
                durationMillis = KagamiDurations.slower,
                easing = LinearEasing
            ),
            repeatMode = RepeatMode.Restart
        ),
        label = "hue_rotation"
    )?.value ?: 0f

    val pulseAlpha by animateFloatAsState(
        targetValue = if (isActive && !reducedMotion) 0.4f else 0f,
        animationSpec = spring(dampingRatio = 0.7f),
        label = "pulse_alpha"
    )

    if (pulseAlpha > 0.01f) {
        Canvas(modifier = modifier.fillMaxSize()) {
            val colors = (0..7).map { i ->
                val phase = (hueRotation / 360f + i / 7f) % 1f
                SpectralColor.at(phase).copy(alpha = pulseAlpha)
            }

            val brush = Brush.sweepGradient(
                colors = colors,
                center = Offset(size.width / 2, size.height / 2)
            )

            drawRect(brush = brush, blendMode = BlendMode.Screen)
        }
    }
}

// =============================================================================
// SPECTRAL SHIMMER (Enhanced)
// =============================================================================

/**
 * Animated rainbow shimmer overlay using Canvas with dispersion timing
 */
@Composable
fun SpectralShimmer(
    modifier: Modifier = Modifier,
    phase: Float = 0f,
    animated: Boolean = true,
    useDispersionTiming: Boolean = false
) {
    val reducedMotion = rememberReducedMotionEnabled()

    val infiniteTransition = if (animated && !reducedMotion) {
        rememberInfiniteTransition(label = "shimmer")
    } else null

    val animatedPhase = infiniteTransition?.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(8000, easing = LinearEasing),
            repeatMode = RepeatMode.Restart
        ),
        label = "shimmer_phase"
    )

    // Staggered color phases for dispersion effect
    val colorPhases = if (useDispersionTiming && !reducedMotion) {
        SpectralColor.all.mapIndexed { index, color ->
            val staggeredTransition = rememberInfiniteTransition(label = "stagger_$index")
            staggeredTransition.animateFloat(
                initialValue = 0f,
                targetValue = 1f,
                animationSpec = infiniteRepeatable(
                    animation = tween(
                        durationMillis = 8000,
                        delayMillis = color.dispersionDelayMs * 2, // Amplify for visibility
                        easing = LinearEasing
                    ),
                    repeatMode = RepeatMode.Restart
                ),
                label = "color_phase_$index"
            ).value
        }
    } else null

    val currentPhase = if (animated && !reducedMotion) {
        (animatedPhase?.value ?: 0f) + phase
    } else phase

    Canvas(modifier = modifier.fillMaxSize()) {
        val colors = if (colorPhases != null) {
            colorPhases.mapIndexed { i, p ->
                SpectralColor.byIndex(i).color.copy(alpha = 0.3f + 0.2f * sin(p * Math.PI.toFloat()))
            }
        } else {
            (0..7).map { i ->
                val p = (currentPhase + i / 7f) % 1f
                SpectralColor.at(p)
            }
        }

        val brush = Brush.linearGradient(
            colors = colors,
            start = Offset.Zero,
            end = Offset(size.width, size.height)
        )

        drawRect(brush = brush, blendMode = BlendMode.Overlay)
    }
}

// =============================================================================
// SPECTRAL BORDER (Enhanced with Fano Lines)
// =============================================================================

/**
 * Animated rainbow border effect with optional Fano line mode
 */
fun Modifier.spectralBorder(
    width: Dp = 2.dp,
    cornerRadius: Dp = 12.dp,
    animated: Boolean = true,
    fanoLineIndex: Int? = null
): Modifier = composed {
    val reducedMotion = rememberReducedMotionEnabled()
    val shouldAnimate = animated && !reducedMotion

    // P2 Optimization: Check if we should use simplified rendering on low-end devices
    val useSimplifiedRendering = PrismPerformanceConfig.reduceComplexityOnLowEnd &&
            PrismPerformanceConfig.isLowEndDevice()

    val infiniteTransition = if (shouldAnimate && !useSimplifiedRendering) {
        rememberInfiniteTransition(label = "spectral_border")
    } else null

    val rotation = infiniteTransition?.animateFloat(
        initialValue = 0f,
        targetValue = 360f,
        animationSpec = infiniteRepeatable(
            // P2: Slower animation for better battery life
            animation = tween(
                durationMillis = if (useSimplifiedRendering) 12000 else 6000,
                easing = LinearEasing
            ),
            repeatMode = RepeatMode.Restart
        ),
        label = "border_rotation"
    )

    val currentRotation = rotation?.value ?: 0f

    // P2: Use hardware layer during animation for reduced overdraw
    this
        .hardwareLayerDuringAnimation(shouldAnimate && currentRotation != 0f)
        .drawWithCache {
            // P2: Cache the Fano line outside of draw call to reduce allocations
            val line = if (fanoLineIndex != null) FanoLines.allLines[fanoLineIndex % 7] else null

            onDrawWithContent {
                drawContent()

                val brush = if (line != null && !reducedMotion) {
                    // Use specific Fano line gradient
                    Brush.sweepGradient(
                        colors = line.map { it.color } + line.first().color,
                        center = Offset(size.width / 2, size.height / 2)
                    )
                } else {
                    // Full spectrum sweep
                    val spectralColors = SpectralColor.all.map { it.color } + SpectralColor.SPARK.color
                    Brush.sweepGradient(
                        colors = spectralColors,
                        center = Offset(size.width / 2, size.height / 2)
                    )
                }

                rotate(currentRotation) {
                    drawRoundRect(
                        brush = brush,
                        cornerRadius = androidx.compose.ui.geometry.CornerRadius(cornerRadius.toPx()),
                        style = Stroke(width = width.toPx())
                    )
                }
            }
        }
}

// =============================================================================
// CAUSTIC BACKGROUND (Enhanced)
// =============================================================================

/**
 * Animated light pattern background tracing Fano line directions
 */
@Composable
fun CausticBackground(
    modifier: Modifier = Modifier,
    intensity: Float = 1f
) {
    val reducedMotion = rememberReducedMotionEnabled()
    val actualIntensity = if (reducedMotion) 0.5f else intensity

    val infiniteTransition = if (!reducedMotion) {
        rememberInfiniteTransition(label = "caustics")
    } else null

    // Three caustic layers tracing different Fano lines
    val phase123 = infiniteTransition?.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(25000, easing = LinearEasing),
            repeatMode = RepeatMode.Restart
        ),
        label = "caustic_123"
    )?.value ?: 0f

    val phase145 = infiniteTransition?.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(30000, easing = LinearEasing),
            repeatMode = RepeatMode.Restart,
            initialStartOffset = StartOffset(10000)
        ),
        label = "caustic_145"
    )?.value ?: 0f

    val phase176 = infiniteTransition?.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(35000, easing = LinearEasing),
            repeatMode = RepeatMode.Restart,
            initialStartOffset = StartOffset(5000)
        ),
        label = "caustic_176"
    )?.value ?: 0f

    Canvas(modifier = modifier.fillMaxSize()) {
        // Line 123: Warm spectrum arc (Spark-Forge-Flow)
        drawCausticLayer(
            colors = listOf(
                Spark.copy(alpha = 0.03f * actualIntensity),
                Forge.copy(alpha = 0.03f * actualIntensity),
                Flow.copy(alpha = 0.03f * actualIntensity)
            ),
            phase = phase123,
            offsetScale = 20f,
            position = Offset(0.2f, 0.3f)
        )

        // Line 145: Red-cyan diagonal (Spark-Nexus-Beacon)
        drawCausticLayer(
            colors = listOf(
                Spark.copy(alpha = 0.03f * actualIntensity),
                Nexus.copy(alpha = 0.03f * actualIntensity),
                Beacon.copy(alpha = 0.03f * actualIntensity)
            ),
            phase = phase145,
            offsetScale = 15f,
            position = Offset(0.6f, 0.7f)
        )

        // Line 176: Red-violet harmonic (Spark-Crystal-Grove)
        drawCausticLayer(
            colors = listOf(
                Spark.copy(alpha = 0.02f * actualIntensity),
                Crystal.copy(alpha = 0.02f * actualIntensity),
                Grove.copy(alpha = 0.02f * actualIntensity)
            ),
            phase = phase176,
            offsetScale = 18f,
            position = Offset(0.8f, 0.2f)
        )
    }
}

private fun DrawScope.drawCausticLayer(
    colors: List<Color>,
    phase: Float,
    offsetScale: Float,
    position: Offset = Offset(0.5f, 0.5f)
) {
    val offsetX = cos(phase * 2 * Math.PI).toFloat() * offsetScale
    val offsetY = sin(phase * 2 * Math.PI).toFloat() * offsetScale
    val scale = 1f + sin(phase * Math.PI).toFloat() * 0.05f

    val centerX = size.width * position.x + offsetX
    val centerY = size.height * position.y + offsetY

    val brush = Brush.radialGradient(
        colors = colors + Color.Transparent,
        center = Offset(centerX, centerY),
        radius = (size.minDimension * 0.7f) * scale
    )

    drawRect(brush = brush)
}

// =============================================================================
// SHIMMER TEXT
// =============================================================================

/**
 * Text with animated rainbow shimmer
 */
@Composable
fun ShimmerText(
    text: String,
    modifier: Modifier = Modifier,
    style: TextStyle = TextStyle(fontSize = 24.sp, fontWeight = FontWeight.Bold),
    animated: Boolean = true
) {
    val reducedMotion = rememberReducedMotionEnabled()

    val infiniteTransition = if (animated && !reducedMotion) {
        rememberInfiniteTransition(label = "text_shimmer")
    } else null

    val phase = infiniteTransition?.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(8000, easing = LinearEasing),
            repeatMode = RepeatMode.Restart
        ),
        label = "shimmer_text_phase"
    )?.value ?: 0f

    val colors = (0..7).map { i ->
        val p = (phase + i / 7f) % 1f
        SpectralColor.at(p)
    }

    val brush = Brush.horizontalGradient(colors)

    Text(
        text = text,
        modifier = modifier,
        style = style.copy(
            brush = brush
        )
    )
}

// =============================================================================
// PRISM CARD (Enhanced with Discovery States)
// =============================================================================

/**
 * Card with glassmorphism base and spectral effects based on discovery state
 */
@Composable
fun PrismCard(
    elementId: Int,
    modifier: Modifier = Modifier,
    onClick: (() -> Unit)? = null,
    content: @Composable BoxScope.() -> Unit
) {
    val reducedMotion = rememberReducedMotionEnabled()
    var discoveryState by remember { mutableStateOf(DiscoveryState.REST) }

    // Fano-based phase offset
    val shimmerPhase = (elementId % 7) / 7f
    val fanoLineIndex = elementId % 7

    val shimmerOpacity by animateFloatAsState(
        targetValue = if (!reducedMotion) discoveryState.opacity else 0f,
        animationSpec = spring(dampingRatio = 0.7f),
        label = "shimmer_opacity"
    )

    val dispersionWidth by animateFloatAsState(
        targetValue = if (!reducedMotion) 3f + 3f * discoveryState.animationIntensity else 3f,
        animationSpec = tween(
            durationMillis = KagamiDurations.slow,
            easing = KagamiEasing.cusp
        ),
        label = "dispersion_width"
    )

    // P2 Optimization: Use hardware layer during active animation
    val isAnimating = shimmerOpacity > 0.01f || discoveryState != DiscoveryState.REST

    Box(
        modifier = modifier
            .clip(RoundedCornerShape(KagamiRadius.md))
            // P2: Hardware layer during animation for reduced overdraw
            .hardwareLayerDuringAnimation(isAnimating)
            .background(Obsidian.copy(alpha = 0.8f))
            .then(
                if (onClick != null) {
                    Modifier.clickable(
                        interactionSource = remember { MutableInteractionSource() },
                        indication = null,
                        onClick = onClick
                    )
                } else Modifier
            )
            .spectralDiscovery(
                baseColor = SpectralColor.byIndex(fanoLineIndex),
                onDiscoveryChange = { state -> discoveryState = state }
            )
            // P2: Use drawWithCache to reduce allocations during animation
            .drawWithCache {
                // Cache the Fano line colors outside of the draw call
                val line = FanoLines.allLines[fanoLineIndex]

                onDrawWithContent {
                    drawContent()

                    // Shimmer overlay based on discovery state
                    if (shimmerOpacity > 0.01f) {
                        val colors = line.map { it.color.copy(alpha = shimmerOpacity) }

                        val brush = Brush.linearGradient(
                            colors = colors,
                            start = Offset.Zero,
                            end = Offset(size.width, size.height)
                        )
                        drawRect(brush = brush, blendMode = BlendMode.Overlay)
                    }
                }
            }
            .border(
                width = 1.dp,
                color = Color.White.copy(alpha = 0.1f),
                shape = RoundedCornerShape(KagamiRadius.md)
            )
    ) {
        content()
    }
}

// =============================================================================
// PRISM GLOW
// =============================================================================

/**
 * Soft colored glow that pulses
 */
fun Modifier.prismGlow(
    color: Color = Crystal,
    radius: Dp = 20.dp,
    animated: Boolean = true
): Modifier = composed {
    val reducedMotion = rememberReducedMotionEnabled()

    val infiniteTransition = if (animated && !reducedMotion) {
        rememberInfiniteTransition(label = "glow")
    } else null

    val glowAlpha = infiniteTransition?.animateFloat(
        initialValue = 0f,
        targetValue = 0.4f,
        animationSpec = infiniteRepeatable(
            animation = tween(1597, easing = EaseInOutSine),
            repeatMode = RepeatMode.Reverse
        ),
        label = "glow_alpha"
    )?.value ?: 0.3f

    this.drawBehind {
        val paint = Paint().apply {
            this.color = color.copy(alpha = glowAlpha)
        }
        drawContext.canvas.nativeCanvas.apply {
            drawCircle(
                size.width / 2,
                size.height / 2,
                size.minDimension / 2 + radius.toPx(),
                paint.asFrameworkPaint().apply {
                    maskFilter = BlurMaskFilter(radius.toPx(), BlurMaskFilter.Blur.NORMAL)
                }
            )
        }
    }
}

// =============================================================================
// CHROMATIC TEXT
// =============================================================================

/**
 * Creates red/cyan offset effect on text (for headers/logos)
 */
@Composable
fun ChromaticText(
    text: String,
    modifier: Modifier = Modifier,
    style: TextStyle = TextStyle(fontSize = 48.sp, fontWeight = FontWeight.Bold),
    offset: Dp = 2.dp
) {
    val reducedMotion = rememberReducedMotionEnabled()
    var isHovered by remember { mutableStateOf(false) }

    val animatedOffset by animateFloatAsState(
        targetValue = if (isHovered && !reducedMotion) offset.value else 0f,
        animationSpec = spring(dampingRatio = 0.75f),
        label = "chromatic_offset"
    )

    val animatedAlpha by animateFloatAsState(
        targetValue = if (isHovered && !reducedMotion) 0.5f else 0f,
        animationSpec = spring(dampingRatio = 0.75f),
        label = "chromatic_alpha"
    )

    Box(
        modifier = modifier
            .clickable(
                interactionSource = remember { MutableInteractionSource() },
                indication = null,
                onClick = {}
            )
            .pointerInput(Unit) {
                detectTapGestures(
                    onPress = {
                        isHovered = true
                        tryAwaitRelease()
                        isHovered = false
                    }
                )
            },
        contentAlignment = Alignment.Center
    ) {
        // Red channel (left offset)
        Text(
            text = text,
            style = style.copy(color = Spark.copy(alpha = animatedAlpha)),
            modifier = Modifier.offset(x = (-animatedOffset).dp)
        )

        // Cyan channel (right offset)
        Text(
            text = text,
            style = style.copy(color = Crystal.copy(alpha = animatedAlpha)),
            modifier = Modifier.offset(x = animatedOffset.dp)
        )

        // Main text
        Text(
            text = text,
            style = style.copy(color = TextPrimary)
        )
    }
}

// =============================================================================
// PRISM RIPPLE
// =============================================================================

/**
 * Rainbow ripple effect on tap with dispersion timing
 */
@Composable
fun Modifier.prismRipple(): Modifier = composed {
    val reducedMotion = rememberReducedMotionEnabled()
    val scope = rememberCoroutineScope()

    data class RippleState(
        val id: Int,
        val location: Offset,
        val color: Color,
        val progress: Animatable<Float, AnimationVector1D>
    )

    var rippleCounter by remember { mutableStateOf(0) }
    val ripples = remember { mutableStateListOf<RippleState>() }

    this
        .pointerInput(Unit) {
            detectTapGestures { offset ->
                if (reducedMotion) return@detectTapGestures

                scope.launch {
                    val color = SpectralColor.at(kotlin.random.Random.nextFloat())
                    val progress = Animatable(0f)
                    val ripple = RippleState(
                        id = rippleCounter++,
                        location = offset,
                        color = color,
                        progress = progress
                    )
                    ripples.add(ripple)

                    progress.animateTo(
                        targetValue = 1f,
                        animationSpec = tween(987, easing = EaseOut)
                    )

                    ripples.remove(ripple)
                }
            }
        }
        .drawWithContent {
            drawContent()

            ripples.forEach { ripple ->
                val progress = ripple.progress.value
                val maxRadius = size.maxDimension
                val radius = maxRadius * progress

                // Create staggered color bands following dispersion timing
                val colorStops = SpectralColor.all.mapIndexed { index, spectralColor ->
                    val delay = spectralColor.dispersionDelayMs / 48f // Normalize to 0-1
                    val adjustedProgress = (progress - delay * 0.1f).coerceIn(0f, 1f)
                    val alpha = 0.25f * (1f - adjustedProgress)
                    (index / 7f) to spectralColor.color.copy(alpha = alpha)
                }.toTypedArray()

                val brush = Brush.radialGradient(
                    colorStops = colorStops + (1f to Color.Transparent),
                    center = ripple.location,
                    radius = radius
                )

                drawRect(brush = brush, blendMode = BlendMode.Screen)
            }
        }
}

// =============================================================================
// PRISM CATCH (Corner Flash Effect)
// =============================================================================

/**
 * Brief spectral flash when cursor crosses a corner
 */
@Composable
fun Modifier.prismCatch(): Modifier = composed {
    val reducedMotion = rememberReducedMotionEnabled()
    var catchActive by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    val catchAlpha by animateFloatAsState(
        targetValue = if (catchActive && !reducedMotion) 0.4f else 0f,
        animationSpec = tween(
            durationMillis = KagamiDurations.normal,
            easing = EaseOut
        ),
        label = "catch_alpha"
    )

    this
        .pointerInput(Unit) {
            detectTapGestures(
                onPress = { offset ->
                    // Check if near corner (within 40dp)
                    val cornerThreshold = 40.dp.toPx()
                    val nearCorner = (offset.x < cornerThreshold && offset.y < cornerThreshold) ||
                            (offset.x > size.width - cornerThreshold && offset.y < cornerThreshold) ||
                            (offset.x < cornerThreshold && offset.y > size.height - cornerThreshold) ||
                            (offset.x > size.width - cornerThreshold && offset.y > size.height - cornerThreshold)

                    if (nearCorner && !reducedMotion) {
                        catchActive = true
                        scope.launch {
                            delay(KagamiDurations.normal.toLong())
                            catchActive = false
                        }
                    }
                    tryAwaitRelease()
                }
            )
        }
        .drawWithContent {
            drawContent()

            if (catchAlpha > 0.01f) {
                val brush = Brush.sweepGradient(
                    colors = listOf(
                        Spark.copy(alpha = catchAlpha),
                        Flow.copy(alpha = catchAlpha),
                        Beacon.copy(alpha = catchAlpha),
                        Crystal.copy(alpha = catchAlpha),
                        Spark.copy(alpha = catchAlpha)
                    ),
                    center = Offset(size.width / 2, size.height / 2)
                )

                drawRect(brush = brush, blendMode = BlendMode.Screen)
            }
        }
}

// =============================================================================
// KAGAMI THEME INTEGRATION
// =============================================================================

/**
 * Prism effect configuration for theme integration
 */
data class PrismConfig(
    val blur: Dp = 16.dp,
    val dispersion: Dp = 2.dp,
    val opacity: Float = 0.6f,
    val borderOpacity: Float = 0.2f,
    val refraction: Float = 1.0f,
    val animationsEnabled: Boolean = true
)

/**
 * Platform-specific prism configurations per spec
 */
object PrismPlatformConfig {
    // Android/iOS: Touch-first, reduced for battery
    val mobile = PrismConfig(
        blur = 16.dp,
        dispersion = 2.dp,
        opacity = 0.6f,
        animationsEnabled = true
    )

    // Watch: Minimal effects for battery
    val watch = PrismConfig(
        blur = 8.dp,
        dispersion = 0.dp,
        opacity = 0.6f,
        animationsEnabled = false
    )

    // Desktop: Full experience
    val desktop = PrismConfig(
        blur = 20.dp,
        dispersion = 3.dp,
        opacity = 0.6f,
        animationsEnabled = true
    )
}

val LocalPrismConfig = compositionLocalOf { PrismPlatformConfig.mobile }

// =============================================================================
// PREVIEW
// =============================================================================

@androidx.compose.ui.tooling.preview.Preview
@Composable
private fun PrismEffectsPreview() {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Void)
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        // Shimmer Text
        ShimmerText("KAGAMI")

        // Chromatic Text
        ChromaticText("鏡")

        // Prism Card with discovery states
        PrismCard(elementId = 1) {
            Column(modifier = Modifier.padding(16.dp)) {
                Text("Prism Card", color = TextPrimary, fontWeight = FontWeight.Bold)
                Text("Hold to discover effects", color = TextSecondary, fontSize = 12.sp)
            }
        }

        // Spectral Border with Fano line
        Box(
            modifier = Modifier
                .size(120.dp, 48.dp)
                .background(Obsidian, RoundedCornerShape(8.dp))
                .spectralBorder(cornerRadius = 8.dp, fanoLineIndex = 0),
            contentAlignment = Alignment.Center
        ) {
            Text("Fano 123", color = TextPrimary, fontSize = 12.sp)
        }

        // Fano Line Glow demo
        var showFanoGlow by remember { mutableStateOf(false) }
        Row(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Box(
                modifier = Modifier
                    .size(40.dp)
                    .background(Spark, CircleShape)
                    .clickable { showFanoGlow = !showFanoGlow }
            )
            Box(
                modifier = Modifier.size(60.dp)
            ) {
                FanoLineGlow(
                    firstColony = SpectralColor.SPARK,
                    secondColony = SpectralColor.FORGE,
                    isActive = showFanoGlow,
                    modifier = Modifier.fillMaxSize()
                )
            }
            Box(
                modifier = Modifier
                    .size(40.dp)
                    .background(Forge, CircleShape)
                    .clickable { showFanoGlow = !showFanoGlow }
            )
        }
        Text(
            "Tap to show: Spark + Forge = Flow",
            color = TextSecondary,
            fontSize = 10.sp
        )

        // Glow
        Box(
            modifier = Modifier
                .size(40.dp)
                .background(Crystal, CircleShape)
                .prismGlow()
        )

        // Ripple
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(80.dp)
                .background(Obsidian, RoundedCornerShape(12.dp))
                .prismRipple()
                .prismCatch(),
            contentAlignment = Alignment.Center
        ) {
            Text("Tap for ripple, corners for catch", color = TextSecondary, fontSize = 12.sp)
        }
    }
}
