/**
 * Kagami Design System — Unified Color Palette
 *
 * Canonical color definitions matching all platforms:
 *   - kagami-ios (iOS)
 *   - kagami-vision (visionOS)
 *   - kagami-watch (watchOS)
 *   - kagami-android (Android)
 *   - kagami-desktop (Tauri)
 *   - kagami-web (Web/CSS)
 *
 * Source: packages/kagami_design_tokens/tokens.json
 */

package com.kagami.android.ui.theme

import androidx.compose.ui.graphics.Color

// =============================================================================
// CORE BRAND COLORS
// STANDARDIZED across all platforms
// =============================================================================

val Spark = Color(0xFFFF6B35)      // Ideation
val Forge = Color(0xFFD4AF37)      // Implementation
val Flow = Color(0xFF4ECDC4)       // Adaptation
val Nexus = Color(0xFF9B7EBD)      // Integration
val Beacon = Color(0xFFF59E0B)     // Planning
val Grove = Color(0xFF7EB77F)      // Research
val Crystal = Color(0xFF67D4E4)    // Verification

// =============================================================================
// VOID PALETTE (Backgrounds)
// =============================================================================

val Void = Color(0xFF0A0A0F)           // Primary background - canonical void
val VoidWarm = Color(0xFF0D0A0F)       // Tinted background
val VoidLight = Color(0xFF1C1C24)      // Card background
val Obsidian = Color(0xFF12101A)       // Elevated surface
val Carbon = Color(0xFF252330)         // Highest surface

// Surface Container Hierarchy (Material 3)
val Surface = Color(0xFF1E1E24)
val SurfaceContainerLowest = Void
val SurfaceContainerLow = VoidLight
val SurfaceContainer = Color(0xFF252530)
val SurfaceContainerHigh = Color(0xFF2C2C38)
val SurfaceContainerHighest = Color(0xFF353540)

// =============================================================================
// SAFETY COLORS
// =============================================================================

val SafetyOk = Color(0xFF32D74B)           // Safe (Apple system green)
val SafetyCaution = Color(0xFFFFD60A)      // Caution (Apple system yellow)
val SafetyViolation = Color(0xFFFF3B30)    // Warning (Apple system red)
val Alert = SafetyViolation                // Alias for accessibility demos

// Status Colors (Extended)
val StatusSuccess = Color(0xFF00FF88)
val StatusError = Color(0xFFFF4444)
val StatusWarning = Color(0xFFFFD700)

// =============================================================================
// TEXT COLORS (WCAG 2.1 AAA Compliant)
// =============================================================================

val TextPrimary = Color(0xFFF5F0E8)        // ~15:1 contrast (AAA compliant)
val TextSecondary = Color(0xFFC4C0B8)      // ~8:1 contrast (AAA compliant)
val TextTertiary = Color(0xFFA8A49C)       // ~7:1 contrast (AAA compliant)

// =============================================================================
// MODE COLORS
// =============================================================================

val ModeAsk = Grove       // Research mode
val ModePlan = Beacon     // Planning mode
val ModeAgent = Forge     // Implementation mode

// =============================================================================
// MATERIAL 3 DARK THEME COLORS - Complete Token Set
// =============================================================================

// Primary (Crystal-based)
val Primary = Crystal
val OnPrimary = Void
val PrimaryContainer = Color(0xFF1A3A40)
val OnPrimaryContainer = Crystal

// Secondary (Nexus-based)
val Secondary = Nexus
val OnSecondary = Void
val SecondaryContainer = Color(0xFF2A1F3A)
val OnSecondaryContainer = Nexus

// Tertiary (Forge-based)
val Tertiary = Forge
val OnTertiary = Void
val TertiaryContainer = Color(0xFF3A2F1A)
val OnTertiaryContainer = Forge

// Background and Surface
val Background = Void
val OnBackground = TextPrimary
val SurfaceColor = Surface
val OnSurface = TextPrimary
val OnSurfaceVariant = TextSecondary    // #C4C0B8 - AAA compliant
val SurfaceVariant = VoidLight

// Outline
val Outline = Color(0x33FFFFFF)            // 20% white
val OutlineVariant = Color(0x1AFFFFFF)     // 10% white

// Error
val Error = SafetyViolation
val OnError = TextPrimary
val ErrorContainer = Color(0xFF3A1A1A)
val OnErrorContainer = SafetyViolation

// Inverse (for Snackbars, etc.)
val InverseSurface = Color.White
val InverseOnSurface = Void
val InversePrimary = Color(0xFF006C7A)     // Darker Crystal for inverse

// Scrim
val Scrim = Color(0x80000000)              // 50% black

// =============================================================================
// HIGH CONTRAST MODE COLORS (WCAG AAA)
// =============================================================================

object HighContrastColors {
    val background = Color.Black
    val surface = Color(0xFF111111)
    val text = Color.White
    val accent = Color(0xFF00FFFF)         // High contrast cyan
    val border = Color.White
    val error = Color(0xFFFF6666)
    val success = Color(0xFF66FF66)
    val warning = Color(0xFFFFFF66)

    // High Contrast Brand Colors
    val spark = Color(0xFFFF7744)
    val forge = Color(0xFFFFD700)
    val flow = Color(0xFF00FFFF)
    val nexus = Color(0xFFCC99FF)
    val beacon = Color(0xFFFFBB00)
    val grove = Color(0xFF00FF88)
    val crystal = Color(0xFF00EEFF)
}

// =============================================================================
// KAGAMI COLORS OBJECT
// Provides unified access to all color tokens
// =============================================================================

/**
 * KagamiColors object for easy access to brand and design system colors.
 * Provides lowercase property names for consistency with string-based lookups.
 */
object KagamiColors {
    // Brand colors
    val spark = Spark
    val forge = Forge
    val flow = Flow
    val nexus = Nexus
    val beacon = Beacon
    val grove = Grove
    val crystal = Crystal

    // Safety colors
    val safetyOk = SafetyOk
    val safetyCaution = SafetyCaution
    val safetyViolation = SafetyViolation

    // Status colors
    val statusSuccess = StatusSuccess
    val statusError = StatusError
    val statusWarning = StatusWarning

    // Backgrounds
    val void = Void
    val voidWarm = VoidWarm
    val voidLight = VoidLight
    val obsidian = Obsidian
    val carbon = Carbon
    val surface = Surface

    // Text colors
    val textPrimary = TextPrimary
    val textSecondary = TextSecondary
    val textTertiary = TextTertiary

    // Mode colors
    val modeAsk = ModeAsk
    val modePlan = ModePlan
    val modeAgent = ModeAgent

    /**
     * Get brand color by name (case-insensitive)
     */
    fun brandColor(name: String): Color = when (name.lowercase()) {
        "spark" -> spark
        "forge" -> forge
        "flow" -> flow
        "nexus" -> nexus
        "beacon" -> beacon
        "grove" -> grove
        "crystal" -> crystal
        else -> crystal // Default to Crystal
    }

    /**
     * Get safety color for score (0.0 to 1.0)
     */
    fun safetyColor(score: Double?): Color = when {
        score == null -> Secondary
        score >= 0.5 -> safetyOk
        score >= 0.0 -> safetyCaution
        else -> safetyViolation
    }
}

/*
 * Unified color system for all Kagami platforms.
 */
