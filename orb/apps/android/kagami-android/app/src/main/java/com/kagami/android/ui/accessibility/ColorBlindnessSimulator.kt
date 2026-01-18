/**
 * Color Blindness Simulator - Accessibility Testing Filters
 *
 * Colony: Grove (e6) - Adaptation
 * h(x) >= 0. Always.
 *
 * P2 Gap Fix: Protan/Deutan/Tritan color vision deficiency simulation.
 * Features:
 * - Real-time color blindness simulation filters
 * - Debug overlay for accessibility testing
 * - Contrast ratio validation (WCAG 2.1 AA/AAA)
 * - ColorMatrix transformations based on scientific models
 *
 * Color Blindness Types:
 * - Protanopia/Protanomaly: Red blindness/weakness (~1.3% of males)
 * - Deuteranopia/Deuteranomaly: Green blindness/weakness (~5.9% of males)
 * - Tritanopia/Tritanomaly: Blue blindness/weakness (~0.001% of population)
 * - Achromatopsia: Complete color blindness (rare)
 *
 * References:
 * - Brettel, H., Vienot, F., & Mollon, J. D. (1997). Computerized simulation
 *   of color appearance for dichromats.
 * - WCAG 2.1 Success Criterion 1.4.3 Contrast (Minimum)
 */

package com.kagami.android.ui.accessibility

import android.graphics.ColorMatrix
import android.graphics.ColorMatrixColorFilter
import android.graphics.RenderEffect
import android.graphics.Shader
import android.os.Build
import androidx.annotation.RequiresApi
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Visibility
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asComposeRenderEffect
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.kagami.android.ui.minTouchTarget
import com.kagami.android.ui.theme.*
import kotlin.math.pow

// =============================================================================
// COLOR BLINDNESS TYPES
// =============================================================================

/**
 * Types of color vision deficiency for simulation.
 */
enum class ColorBlindnessType(
    val displayName: String,
    val shortName: String,
    val description: String,
    val prevalence: String
) {
    NONE(
        displayName = "Normal Vision",
        shortName = "Normal",
        description = "Standard color vision",
        prevalence = "~92% of population"
    ),
    PROTANOPIA(
        displayName = "Protanopia",
        shortName = "Protan",
        description = "Red blindness - difficulty distinguishing red from green",
        prevalence = "~1.3% of males"
    ),
    PROTANOMALY(
        displayName = "Protanomaly",
        shortName = "Protan (mild)",
        description = "Red weakness - reduced sensitivity to red light",
        prevalence = "~1% of males"
    ),
    DEUTERANOPIA(
        displayName = "Deuteranopia",
        shortName = "Deutan",
        description = "Green blindness - difficulty distinguishing red from green",
        prevalence = "~1.2% of males"
    ),
    DEUTERANOMALY(
        displayName = "Deuteranomaly",
        shortName = "Deutan (mild)",
        description = "Green weakness - most common color blindness",
        prevalence = "~4.6% of males"
    ),
    TRITANOPIA(
        displayName = "Tritanopia",
        shortName = "Tritan",
        description = "Blue blindness - difficulty distinguishing blue from yellow",
        prevalence = "~0.001% of population"
    ),
    TRITANOMALY(
        displayName = "Tritanomaly",
        shortName = "Tritan (mild)",
        description = "Blue weakness - reduced sensitivity to blue light",
        prevalence = "~0.01% of population"
    ),
    ACHROMATOPSIA(
        displayName = "Achromatopsia",
        shortName = "Achromat",
        description = "Complete color blindness - sees only grayscale",
        prevalence = "~0.003% of population"
    );

    companion object {
        val commonTypes = listOf(NONE, PROTANOPIA, DEUTERANOPIA, TRITANOPIA)
        val allTypes = values().toList()
    }
}

// =============================================================================
// COLOR MATRICES
// =============================================================================

/**
 * Color transformation matrices for simulating color blindness.
 *
 * Based on the Brettel, Vienot & Mollon (1997) simulation model and
 * the Machado, Oliveira & Fernandes (2009) model for anomalous trichromacy.
 */
object ColorBlindnessMatrices {

    /**
     * Identity matrix (no transformation).
     */
    val NORMAL = floatArrayOf(
        1f, 0f, 0f, 0f, 0f,
        0f, 1f, 0f, 0f, 0f,
        0f, 0f, 1f, 0f, 0f,
        0f, 0f, 0f, 1f, 0f
    )

    /**
     * Protanopia (red blindness) - Dichromat simulation.
     * L-cone (long wavelength) absent.
     */
    val PROTANOPIA = floatArrayOf(
        0.567f, 0.433f, 0.000f, 0f, 0f,
        0.558f, 0.442f, 0.000f, 0f, 0f,
        0.000f, 0.242f, 0.758f, 0f, 0f,
        0f, 0f, 0f, 1f, 0f
    )

    /**
     * Protanomaly (red weakness) - Anomalous trichromacy.
     * Shifted L-cone sensitivity.
     */
    val PROTANOMALY = floatArrayOf(
        0.817f, 0.183f, 0.000f, 0f, 0f,
        0.333f, 0.667f, 0.000f, 0f, 0f,
        0.000f, 0.125f, 0.875f, 0f, 0f,
        0f, 0f, 0f, 1f, 0f
    )

    /**
     * Deuteranopia (green blindness) - Dichromat simulation.
     * M-cone (medium wavelength) absent.
     */
    val DEUTERANOPIA = floatArrayOf(
        0.625f, 0.375f, 0.000f, 0f, 0f,
        0.700f, 0.300f, 0.000f, 0f, 0f,
        0.000f, 0.300f, 0.700f, 0f, 0f,
        0f, 0f, 0f, 1f, 0f
    )

    /**
     * Deuteranomaly (green weakness) - Anomalous trichromacy.
     * Shifted M-cone sensitivity.
     */
    val DEUTERANOMALY = floatArrayOf(
        0.800f, 0.200f, 0.000f, 0f, 0f,
        0.258f, 0.742f, 0.000f, 0f, 0f,
        0.000f, 0.142f, 0.858f, 0f, 0f,
        0f, 0f, 0f, 1f, 0f
    )

    /**
     * Tritanopia (blue blindness) - Dichromat simulation.
     * S-cone (short wavelength) absent.
     */
    val TRITANOPIA = floatArrayOf(
        0.950f, 0.050f, 0.000f, 0f, 0f,
        0.000f, 0.433f, 0.567f, 0f, 0f,
        0.000f, 0.475f, 0.525f, 0f, 0f,
        0f, 0f, 0f, 1f, 0f
    )

    /**
     * Tritanomaly (blue weakness) - Anomalous trichromacy.
     * Shifted S-cone sensitivity.
     */
    val TRITANOMALY = floatArrayOf(
        0.967f, 0.033f, 0.000f, 0f, 0f,
        0.000f, 0.733f, 0.267f, 0f, 0f,
        0.000f, 0.183f, 0.817f, 0f, 0f,
        0f, 0f, 0f, 1f, 0f
    )

    /**
     * Achromatopsia (total color blindness) - Monochromacy.
     * Uses standard luminance weights (ITU-R BT.709).
     */
    val ACHROMATOPSIA = floatArrayOf(
        0.2126f, 0.7152f, 0.0722f, 0f, 0f,
        0.2126f, 0.7152f, 0.0722f, 0f, 0f,
        0.2126f, 0.7152f, 0.0722f, 0f, 0f,
        0f, 0f, 0f, 1f, 0f
    )

    /**
     * Get the color matrix for a given color blindness type.
     */
    fun getMatrix(type: ColorBlindnessType): FloatArray = when (type) {
        ColorBlindnessType.NONE -> NORMAL
        ColorBlindnessType.PROTANOPIA -> PROTANOPIA
        ColorBlindnessType.PROTANOMALY -> PROTANOMALY
        ColorBlindnessType.DEUTERANOPIA -> DEUTERANOPIA
        ColorBlindnessType.DEUTERANOMALY -> DEUTERANOMALY
        ColorBlindnessType.TRITANOPIA -> TRITANOPIA
        ColorBlindnessType.TRITANOMALY -> TRITANOMALY
        ColorBlindnessType.ACHROMATOPSIA -> ACHROMATOPSIA
    }

    /**
     * Create a ColorMatrix for Android graphics operations.
     */
    fun getColorMatrix(type: ColorBlindnessType): ColorMatrix {
        return ColorMatrix(getMatrix(type))
    }

    /**
     * Create a ColorMatrixColorFilter for Android graphics operations.
     */
    fun getColorFilter(type: ColorBlindnessType): ColorMatrixColorFilter {
        return ColorMatrixColorFilter(getColorMatrix(type))
    }
}

// =============================================================================
// COLOR TRANSFORMATION
// =============================================================================

/**
 * Color blindness simulator utility object.
 */
object ColorBlindnessSimulator {

    /**
     * Transform a color to simulate how it appears with color blindness.
     */
    fun simulateColor(color: Color, type: ColorBlindnessType): Color {
        if (type == ColorBlindnessType.NONE) return color

        val matrix = ColorBlindnessMatrices.getMatrix(type)

        val r = color.red
        val g = color.green
        val b = color.blue
        val a = color.alpha

        // Apply transformation matrix
        val newR = (matrix[0] * r + matrix[1] * g + matrix[2] * b).coerceIn(0f, 1f)
        val newG = (matrix[5] * r + matrix[6] * g + matrix[7] * b).coerceIn(0f, 1f)
        val newB = (matrix[10] * r + matrix[11] * g + matrix[12] * b).coerceIn(0f, 1f)

        return Color(newR, newG, newB, a)
    }

    /**
     * Transform an ARGB integer color to simulate color blindness.
     */
    fun simulateColorInt(argb: Int, type: ColorBlindnessType): Int {
        return simulateColor(Color(argb), type).toArgb()
    }

    /**
     * Get the RenderEffect for API 31+ color blindness simulation.
     */
    @RequiresApi(Build.VERSION_CODES.S)
    fun getRenderEffect(type: ColorBlindnessType): RenderEffect? {
        if (type == ColorBlindnessType.NONE) return null

        return RenderEffect.createColorFilterEffect(
            ColorBlindnessMatrices.getColorFilter(type)
        )
    }
}

// =============================================================================
// CONTRAST RATIO VALIDATION
// =============================================================================

/**
 * WCAG contrast level requirements.
 */
enum class ContrastLevel(val minRatio: Float, val description: String) {
    FAIL(0f, "Fails accessibility requirements"),
    AA_LARGE(3f, "WCAG 2.1 AA for large text (18pt+ or 14pt+ bold)"),
    AA(4.5f, "WCAG 2.1 AA for normal text"),
    AAA_LARGE(4.5f, "WCAG 2.1 AAA for large text"),
    AAA(7f, "WCAG 2.1 AAA for normal text")
}

/**
 * Contrast ratio validation utilities.
 */
object ContrastValidator {

    /**
     * Calculate the contrast ratio between two colors.
     * Returns a value between 1:1 (same color) and 21:1 (black/white).
     */
    fun calculateContrastRatio(foreground: Color, background: Color): Float {
        val luminance1 = foreground.luminance()
        val luminance2 = background.luminance()

        val lighter = maxOf(luminance1, luminance2)
        val darker = minOf(luminance1, luminance2)

        return (lighter + 0.05f) / (darker + 0.05f)
    }

    /**
     * Calculate relative luminance using sRGB color space.
     * Based on WCAG 2.1 definition.
     */
    fun calculateRelativeLuminance(color: Color): Float {
        fun transform(value: Float): Float {
            return if (value <= 0.03928f) {
                value / 12.92f
            } else {
                ((value + 0.055f) / 1.055f).pow(2.4f)
            }
        }

        val r = transform(color.red)
        val g = transform(color.green)
        val b = transform(color.blue)

        return 0.2126f * r + 0.7152f * g + 0.0722f * b
    }

    /**
     * Check if a contrast ratio meets a specific level.
     */
    fun meetsContrastLevel(ratio: Float, level: ContrastLevel): Boolean {
        return ratio >= level.minRatio
    }

    /**
     * Get the highest contrast level met by a ratio.
     */
    fun getContrastLevel(ratio: Float): ContrastLevel {
        return when {
            ratio >= ContrastLevel.AAA.minRatio -> ContrastLevel.AAA
            ratio >= ContrastLevel.AA.minRatio -> ContrastLevel.AA
            ratio >= ContrastLevel.AA_LARGE.minRatio -> ContrastLevel.AA_LARGE
            else -> ContrastLevel.FAIL
        }
    }

    /**
     * Validate a color pair and return a detailed result.
     */
    fun validateColorPair(
        foreground: Color,
        background: Color,
        forLargeText: Boolean = false
    ): ContrastValidationResult {
        val ratio = calculateContrastRatio(foreground, background)
        val requiredLevel = if (forLargeText) ContrastLevel.AA_LARGE else ContrastLevel.AA
        val achievedLevel = getContrastLevel(ratio)

        return ContrastValidationResult(
            foreground = foreground,
            background = background,
            ratio = ratio,
            achievedLevel = achievedLevel,
            meetsRequirement = ratio >= requiredLevel.minRatio,
            forLargeText = forLargeText
        )
    }

    /**
     * Validate a color pair under different color blindness simulations.
     */
    fun validateForColorBlindness(
        foreground: Color,
        background: Color,
        types: List<ColorBlindnessType> = ColorBlindnessType.commonTypes
    ): Map<ColorBlindnessType, ContrastValidationResult> {
        return types.associateWith { type ->
            val simFg = ColorBlindnessSimulator.simulateColor(foreground, type)
            val simBg = ColorBlindnessSimulator.simulateColor(background, type)
            validateColorPair(simFg, simBg)
        }
    }
}

/**
 * Result of contrast validation.
 */
data class ContrastValidationResult(
    val foreground: Color,
    val background: Color,
    val ratio: Float,
    val achievedLevel: ContrastLevel,
    val meetsRequirement: Boolean,
    val forLargeText: Boolean
) {
    val ratioString: String get() = "%.2f:1".format(ratio)
}

// =============================================================================
// COMPOSITION LOCAL
// =============================================================================

/**
 * CompositionLocal for current color blindness simulation mode.
 */
val LocalColorBlindnessMode = staticCompositionLocalOf { ColorBlindnessType.NONE }

// =============================================================================
// COMPOSABLES
// =============================================================================

/**
 * Modifier to apply color blindness simulation using RenderEffect (API 31+).
 */
@Composable
fun Modifier.colorBlindnessSimulation(
    type: ColorBlindnessType = LocalColorBlindnessMode.current
): Modifier {
    if (type == ColorBlindnessType.NONE) return this

    return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
        val renderEffect = remember(type) {
            ColorBlindnessSimulator.getRenderEffect(type)?.asComposeRenderEffect()
        }
        this.graphicsLayer {
            this.renderEffect = renderEffect
        }
    } else {
        // Pre-API 31: RenderEffect not available
        // The simulation would need to be applied differently (e.g., at draw time)
        this
    }
}

/**
 * Provider for color blindness simulation mode.
 */
@Composable
fun ColorBlindnessSimulationProvider(
    mode: ColorBlindnessType,
    content: @Composable () -> Unit
) {
    CompositionLocalProvider(LocalColorBlindnessMode provides mode) {
        Box(modifier = Modifier.colorBlindnessSimulation(mode)) {
            content()
        }
    }
}

/**
 * Debug overlay for accessibility testing.
 */
@Composable
fun ColorBlindnessDebugOverlay(
    currentMode: ColorBlindnessType,
    onModeChange: (ColorBlindnessType) -> Unit,
    onDismiss: () -> Unit,
    modifier: Modifier = Modifier
) {
    var expanded by remember { mutableStateOf(false) }

    Surface(
        modifier = modifier
            .padding(16.dp),
        shape = RoundedCornerShape(16.dp),
        color = Obsidian.copy(alpha = 0.95f),
        shadowElevation = 8.dp
    ) {
        Column(
            modifier = Modifier.padding(16.dp)
        ) {
            // Header
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        imageVector = Icons.Default.Visibility,
                        contentDescription = null,
                        tint = Grove,
                        modifier = Modifier.size(24.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "Color Vision Testing",
                        style = MaterialTheme.typography.titleMedium,
                        color = TextPrimary,
                        fontWeight = FontWeight.SemiBold
                    )
                }

                IconButton(
                    onClick = onDismiss,
                    modifier = Modifier
                        .minTouchTarget()
                        .semantics {
                            contentDescription = "Close color blindness testing overlay"
                        }
                ) {
                    Icon(
                        imageVector = Icons.Default.Close,
                        contentDescription = null,
                        tint = TextSecondary
                    )
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            // Current mode display
            Text(
                text = "Simulation Mode",
                style = MaterialTheme.typography.labelMedium,
                color = TextSecondary
            )

            Spacer(modifier = Modifier.height(4.dp))

            // Mode selector
            Box {
                Surface(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable { expanded = true },
                    shape = RoundedCornerShape(8.dp),
                    color = VoidLight.copy(alpha = 0.5f)
                ) {
                    Row(
                        modifier = Modifier.padding(12.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column {
                            Text(
                                text = currentMode.displayName,
                                style = MaterialTheme.typography.bodyLarge,
                                color = TextPrimary
                            )
                            Text(
                                text = currentMode.prevalence,
                                style = MaterialTheme.typography.bodySmall,
                                color = TextSecondary
                            )
                        }
                    }
                }

                DropdownMenu(
                    expanded = expanded,
                    onDismissRequest = { expanded = false }
                ) {
                    ColorBlindnessType.allTypes.forEach { type ->
                        DropdownMenuItem(
                            text = {
                                Column {
                                    Text(
                                        text = type.displayName,
                                        style = MaterialTheme.typography.bodyMedium
                                    )
                                    Text(
                                        text = type.description,
                                        style = MaterialTheme.typography.bodySmall,
                                        color = TextSecondary
                                    )
                                }
                            },
                            onClick = {
                                onModeChange(type)
                                expanded = false
                            }
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Color swatches preview
            Text(
                text = "Colony Colors Preview",
                style = MaterialTheme.typography.labelMedium,
                color = TextSecondary
            )

            Spacer(modifier = Modifier.height(8.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceEvenly
            ) {
                ColorSwatch(
                    name = "Spark",
                    color = ColorBlindnessSimulator.simulateColor(Spark, currentMode)
                )
                ColorSwatch(
                    name = "Forge",
                    color = ColorBlindnessSimulator.simulateColor(Forge, currentMode)
                )
                ColorSwatch(
                    name = "Flow",
                    color = ColorBlindnessSimulator.simulateColor(Flow, currentMode)
                )
                ColorSwatch(
                    name = "Nexus",
                    color = ColorBlindnessSimulator.simulateColor(Nexus, currentMode)
                )
            }

            Spacer(modifier = Modifier.height(8.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceEvenly
            ) {
                ColorSwatch(
                    name = "Beacon",
                    color = ColorBlindnessSimulator.simulateColor(Beacon, currentMode)
                )
                ColorSwatch(
                    name = "Grove",
                    color = ColorBlindnessSimulator.simulateColor(Grove, currentMode)
                )
                ColorSwatch(
                    name = "Crystal",
                    color = ColorBlindnessSimulator.simulateColor(Crystal, currentMode)
                )
                ColorSwatch(
                    name = "Alert",
                    color = ColorBlindnessSimulator.simulateColor(Alert, currentMode)
                )
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Contrast info
            val contrastRatio = ContrastValidator.calculateContrastRatio(TextPrimary, Void)
            val contrastLevel = ContrastValidator.getContrastLevel(contrastRatio)

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Column {
                    Text(
                        text = "Text Contrast",
                        style = MaterialTheme.typography.labelMedium,
                        color = TextSecondary
                    )
                    Text(
                        text = "%.2f:1 (${contrastLevel.name})".format(contrastRatio),
                        style = MaterialTheme.typography.bodyMedium,
                        color = if (contrastLevel != ContrastLevel.FAIL) Grove else Alert
                    )
                }
            }
        }
    }
}

/**
 * Color swatch composable for preview.
 */
@Composable
private fun ColorSwatch(
    name: String,
    color: Color,
    modifier: Modifier = Modifier
) {
    Column(
        modifier = modifier,
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Box(
            modifier = Modifier
                .size(32.dp)
                .clip(CircleShape)
                .background(color)
                .border(1.dp, Color.White.copy(alpha = 0.2f), CircleShape)
        )
        Spacer(modifier = Modifier.height(4.dp))
        Text(
            text = name,
            style = MaterialTheme.typography.labelSmall,
            color = TextSecondary,
            fontSize = 10.sp
        )
    }
}

/**
 * Standalone composable for color blindness testing wrapper.
 */
@Composable
fun ColorBlindnessTestWrapper(
    content: @Composable () -> Unit
) {
    var isOverlayVisible by remember { mutableStateOf(false) }
    var currentMode by remember { mutableStateOf(ColorBlindnessType.NONE) }

    Box(modifier = Modifier.fillMaxSize()) {
        ColorBlindnessSimulationProvider(mode = currentMode) {
            content()
        }

        // Debug toggle button (only in debug builds)
        if (isDebugBuild) {
            IconButton(
                onClick = { isOverlayVisible = !isOverlayVisible },
                modifier = Modifier
                    .align(Alignment.TopEnd)
                    .padding(8.dp)
                    .minTouchTarget()
            ) {
                Icon(
                    imageVector = Icons.Default.Visibility,
                    contentDescription = "Toggle color blindness testing",
                    tint = if (currentMode != ColorBlindnessType.NONE) Grove else TextSecondary
                )
            }
        }

        // Overlay
        if (isOverlayVisible) {
            ColorBlindnessDebugOverlay(
                currentMode = currentMode,
                onModeChange = { currentMode = it },
                onDismiss = { isOverlayVisible = false },
                modifier = Modifier.align(Alignment.TopCenter)
            )
        }
    }
}

// BuildConfig.DEBUG is provided by the actual com.kagami.android.BuildConfig at compile time
// This provides a fallback for preview/testing when BuildConfig isn't available
private val isDebugBuild: Boolean
    get() = try {
        Class.forName("com.kagami.android.BuildConfig")
            .getField("DEBUG")
            .getBoolean(null)
    } catch (e: Exception) {
        // Fallback for preview/testing - default to false for safety
        false
    }

/*
 * Mirror
 * h(x) >= 0. Always.
 */
