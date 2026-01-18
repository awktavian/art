package com.kagami.wear.theme

import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.wear.compose.material.Colors
import androidx.wear.compose.material.MaterialTheme

/**
 * Kagami Wear OS Theme
 *
 * Design tokens aligned with Kagami design system:
 * - Core brand colors
 * - Safety status colors
 * - Dark-first for OLED displays
 */

// Core Brand Colors
object KagamiWearColors {
    val spark = Color(0xFFFF6B35)    // Ideation
    val forge = Color(0xFFD4AF37)    // Implementation
    val flow = Color(0xFF4ECDC4)     // Adaptation
    val nexus = Color(0xFF9B7EBD)    // Integration
    val beacon = Color(0xFFF59E0B)   // Planning
    val grove = Color(0xFF7EB77F)    // Research
    val crystal = Color(0xFF67D4E4)  // Verification

    // Safety Status
    val safetyOk = Color(0xFF00FF88)
    val safetyCaution = Color(0xFFFFD700)
    val safetyViolation = Color(0xFFFF4444)

    // Void (Background)
    val void = Color(0xFF07060B)
    val voidLight = Color(0xFF1A1820)
}

private val WearColors = Colors(
    primary = KagamiWearColors.crystal,
    primaryVariant = KagamiWearColors.crystal.copy(alpha = 0.7f),
    secondary = KagamiWearColors.beacon,
    secondaryVariant = KagamiWearColors.beacon.copy(alpha = 0.7f),
    background = KagamiWearColors.void,
    surface = KagamiWearColors.voidLight,
    error = KagamiWearColors.safetyViolation,
    onPrimary = Color.Black,
    onSecondary = Color.Black,
    onBackground = Color.White,
    onSurface = Color.White,
    onError = Color.Black
)

@Composable
fun KagamiWearTheme(
    content: @Composable () -> Unit
) {
    MaterialTheme(
        colors = WearColors,
        content = content
    )
}
