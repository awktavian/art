package com.kagami.xr.ui.theme

import androidx.compose.ui.graphics.Color

/**
 * Spatial Design System for Kagami XR
 *
 * Defines colors, typography scaling, and spacing for spatial UI.
 * Based on Hall's Proxemic Zones (1966) for distance-aware design.
 *
 * Colony: Nexus (e4) - Integration
 *
 * These values are shared with visionOS (kagami-vision) for cross-platform
 * design consistency.
 *
 * h(x) >= 0. Always.
 */

/**
 * Colony-aware colors for Kagami spatial interfaces.
 */
object SpatialColors {
    // Primary Colony Colors
    val beacon = Color(0xFFFFB940)    // Warm amber - attention, lights
    val crystal = Color(0xFFE8E8F0)   // Cool silver - system, neutral
    val nexus = Color(0xFF7B68EE)     // Deep purple - connection, selection
    val grove = Color(0xFF4CAF50)     // Living green - success, safety
    val flow = Color(0xFF2196F3)      // River blue - process, climate

    // Semantic Colors
    val error = Color(0xFFEF5350)     // Error red
    val warning = Color(0xFFFFB940)   // Warning amber (same as beacon)
    val success = Color(0xFF4CAF50)   // Success green (same as grove)

    // Surface Colors (Dark theme optimized for XR)
    val background = Color(0xFF0D0D0F)
    val surface = Color(0xFF1A1A1E)
    val surfaceVariant = Color(0xFF2A2A30)

    // Text Colors
    val textPrimary = Color(0xFFE8E8F0)
    val textSecondary = Color(0xFF9E9EA8)
    val textDisabled = Color(0xFF5A5A64)

    // Glass effect colors (for spatial panels)
    val glassBackground = Color(0x40FFFFFF)
    val glassBorder = Color(0x20FFFFFF)
}

/**
 * Proxemic zones based on Hall's spatial relationships (1966).
 *
 * Used to adapt UI density, typography, and interaction based on
 * distance from the user.
 */
enum class ProxemicZone(
    val minDistance: Float,  // meters
    val maxDistance: Float,  // meters
    val typographyScale: Float,
    val contentDensity: ContentDensity
) {
    /**
     * Intimate zone (0-45cm): Private alerts, direct manipulation.
     * High information density, smaller text acceptable.
     */
    INTIMATE(0f, 0.45f, 0.8f, ContentDensity.HIGH),

    /**
     * Personal zone (45cm-1.2m): Control panels, conversation UI.
     * Standard density and typography.
     */
    PERSONAL(0.45f, 1.2f, 1.0f, ContentDensity.MEDIUM),

    /**
     * Social zone (1.2m-3.6m): Room visualizations, shared displays.
     * Reduced density, larger text.
     */
    SOCIAL(1.2f, 3.6f, 1.3f, ContentDensity.LOW),

    /**
     * Public zone (>3.6m): Ambient awareness, overview mode.
     * Minimal density, largest text.
     */
    PUBLIC(3.6f, Float.MAX_VALUE, 1.8f, ContentDensity.MINIMAL);

    companion object {
        /**
         * Determine zone from distance.
         */
        fun fromDistance(distance: Float): ProxemicZone {
            return entries.find { distance >= it.minDistance && distance < it.maxDistance }
                ?: PUBLIC
        }
    }
}

/**
 * Content density levels for proxemic adaptation.
 */
enum class ContentDensity {
    HIGH,     // Maximum information, intimate zone
    MEDIUM,   // Balanced, personal zone
    LOW,      // Reduced, social zone
    MINIMAL   // Essential only, public zone
}

/**
 * Spatial animation timings (Fibonacci-based for natural feel).
 *
 * Shared with visionOS for consistent motion design.
 */
object SpatialAnimation {
    const val APPEAR_MS = 377L        // Comfortable appearance
    const val TRANSFORM_MS = 610L     // Position/size changes
    const val DISMISS_MS = 233L       // Quick dismiss
    const val HOVER_MS = 144L         // Hover feedback
    const val MICRO_MS = 89L          // Micro-interactions

    // Easing suggestions
    const val EASE_OUT = "easeOut"    // Entrances
    const val EASE_IN = "easeIn"      // Exits
    const val EASE_IN_OUT = "easeInOut"  // Transforms
}

/**
 * Spatial layout constants.
 */
object SpatialLayout {
    // Panel distances (meters)
    const val INTIMATE_DISTANCE = 0.3f
    const val PERSONAL_DISTANCE = 0.8f
    const val SOCIAL_DISTANCE = 2.0f
    const val PUBLIC_DISTANCE = 4.0f

    // Default panel sizes (meters)
    const val CONTROL_PANEL_WIDTH = 0.5f
    const val CONTROL_PANEL_HEIGHT = 0.4f
    const val CONTROL_PANEL_DEPTH = 0.2f

    // Touch targets (Apple/Google HIG minimum: 44pt)
    const val MIN_TOUCH_TARGET_DP = 44
    const val RECOMMENDED_TOUCH_TARGET_DP = 48
}

/*
 * 鏡
 * h(x) >= 0. Always.
 *
 * Distance shapes density.
 * Space shapes scale.
 * Constraint shapes clarity.
 */
