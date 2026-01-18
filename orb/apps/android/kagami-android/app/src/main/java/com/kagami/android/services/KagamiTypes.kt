/**
 * Kagami Shared Data Models
 *
 * These types match the API schemas from /home endpoints.
 */

package com.kagami.android.services

import androidx.compose.ui.graphics.Color

// ═══════════════════════════════════════════════════════════════
// ROOM MODEL (from GET /home/rooms)
// ═══════════════════════════════════════════════════════════════

data class Light(
    val id: Int,
    val name: String,
    val level: Int  // 0-100
) {
    val isOn: Boolean get() = level > 0
}

data class Shade(
    val id: Int,
    val name: String,
    val position: Int  // 0=closed, 100=open
)

data class AudioZone(
    val id: Int,
    val name: String,
    val isActive: Boolean,
    val source: String?,
    val volume: Int  // 0-100
)

data class HVACState(
    val currentTemp: Double,
    val targetTemp: Double,
    val mode: String  // heat, cool, auto, off
)

data class RoomModel(
    val id: String,
    val name: String,
    val floor: String,
    val lights: List<Light> = emptyList(),
    val shades: List<Shade> = emptyList(),
    val audioZone: AudioZone? = null,
    val hvac: HVACState? = null,
    val occupied: Boolean = false
) {
    val avgLightLevel: Int
        get() = if (lights.isEmpty()) 0 else lights.sumOf { it.level } / lights.size

    val lightState: String
        get() = when {
            avgLightLevel == 0 -> "Off"
            avgLightLevel < 50 -> "Dim"
            else -> "On"
        }

    // Helper properties for widget and service compatibility
    val hasLights: Boolean get() = lights.isNotEmpty()
    val hasShades: Boolean get() = shades.isNotEmpty()
    val lightLevel: Int? get() = if (lights.isEmpty()) null else avgLightLevel
    val shadesOpen: Boolean? get() = if (shades.isEmpty()) null else shades.any { it.position > 0 }
}

// ═══════════════════════════════════════════════════════════════
// HOME STATUS (from GET /home/status)
// ═══════════════════════════════════════════════════════════════

data class HomeStatusModel(
    val initialized: Boolean = false,
    val integrations: Map<String, Boolean> = emptyMap(),
    val rooms: Int = 0,
    val occupiedRooms: Int = 0,
    val movieMode: Boolean = false,
    val avgTemp: Double? = null
)

// ═══════════════════════════════════════════════════════════════
// DEVICE STATES (from GET /home/devices)
// ═══════════════════════════════════════════════════════════════

data class FireplaceState(
    val isOn: Boolean = false,
    val onSince: Long? = null,
    val remainingMinutes: Int? = null
)

data class TVMountState(
    val position: String = "up",  // up, down, moving
    val preset: Int? = null
)

data class LockState(
    val name: String,
    val isLocked: Boolean,
    val doorState: String  // open, closed, unknown
)

data class DevicesResponse(
    val lights: List<Light>,
    val shades: List<Shade>,
    val audioZones: List<AudioZone>,
    val locks: List<LockState>,
    val fireplace: FireplaceState,
    val tvMount: TVMountState
)

data class RoomsResponse(
    val rooms: List<RoomModel>,
    val count: Int
)

// ═══════════════════════════════════════════════════════════════
// BRAND COLORS (Standardized)
// ═══════════════════════════════════════════════════════════════

object ColonyColors {
    // Core brand colors
    val Spark = Color(0xFFFF6B35)    // Ideation
    val Forge = Color(0xFFD4AF37)    // Implementation
    val Flow = Color(0xFF4ECDC4)     // Adaptation
    val Nexus = Color(0xFF9B7EBD)    // Integration
    val Beacon = Color(0xFFF59E0B)   // Planning
    val Grove = Color(0xFF7EB77F)    // Research
    val Crystal = Color(0xFF67D4E4)  // Verification

    // Background colors (canonical)
    val Void = Color(0xFF0A0A0F)
    val VoidLight = Color(0xFF1C1C24)

    // Safety colors (canonical - WCAG AA)
    val SafetyOk = Color(0xFF32D74B)
    val SafetyCaution = Color(0xFFFFD60A)
    val SafetyViolation = Color(0xFFFF3B30)

    fun safetyColor(score: Double?): Color = when {
        score == null -> Color.Gray
        score >= 0.5 -> SafetyOk
        score >= 0.0 -> SafetyCaution
        else -> SafetyViolation
    }
}

// ═══════════════════════════════════════════════════════════════
// SCENE ICONS (Consistent)
// ═══════════════════════════════════════════════════════════════

object SceneIcons {
    const val MOVIE_MODE = "🎬"
    const val GOODNIGHT = "🌙"
    const val WELCOME_HOME = "🏡"
    const val AWAY = "🔒"
    const val FIREPLACE = "🔥"
    const val LIGHTS = "💡"
    const val SHADES = "🪟"
    const val TV = "📺"
}

// Kagami (Mirror)
