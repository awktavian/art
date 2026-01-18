/**
 * Kagami Shared Data Types
 *
 * These types match the API schemas from /home/* endpoints.
 * All clients should use consistent data structures.
 *
 * Focus:
 */

// ═══════════════════════════════════════════════════════════════
// ROOM MODEL (from GET /home/rooms)
// ═══════════════════════════════════════════════════════════════

/**
 * @typedef {Object} Light
 * @property {number} id - Control4 device ID
 * @property {string} name - Light name
 * @property {number} level - 0-100 brightness level
 * @property {boolean} isOn - Whether light is on (level > 0)
 */

/**
 * @typedef {Object} Shade
 * @property {number} id - Control4 device ID
 * @property {string} name - Shade name
 * @property {number} position - 0-100 (0=closed, 100=open)
 */

/**
 * @typedef {Object} AudioZone
 * @property {number} id - Triad AMS zone ID
 * @property {string} name - Zone name
 * @property {boolean} isActive - Whether zone is playing
 * @property {string|null} source - Current source name
 * @property {number} volume - 0-100 volume level
 */

/**
 * @typedef {Object} HVACState
 * @property {number} currentTemp - Current temperature in Fahrenheit
 * @property {number} targetTemp - Target temperature in Fahrenheit
 * @property {string} mode - 'heat' | 'cool' | 'auto' | 'off'
 */

/**
 * @typedef {Object} Room
 * @property {string} id - Room identifier (e.g., 'living_room')
 * @property {string} name - Display name (e.g., 'Living Room')
 * @property {string} floor - Floor name ('Main', 'Upper', 'Basement')
 * @property {Light[]} lights - Lights in this room
 * @property {Shade[]} shades - Shades in this room
 * @property {AudioZone|null} audioZone - Audio zone if present
 * @property {HVACState|null} hvac - HVAC zone if present
 * @property {boolean} occupied - Whether room is occupied
 * @property {number} avgLightLevel - Average light level 0-100
 */

// ═══════════════════════════════════════════════════════════════
// HOME STATUS MODEL (from GET /home/status)
// ═══════════════════════════════════════════════════════════════

/**
 * @typedef {Object} HomeStatus
 * @property {boolean} initialized - Whether smart home is initialized
 * @property {Object.<string, boolean>} integrations - Integration status map
 * @property {number} rooms - Total room count
 * @property {number} occupiedRooms - Currently occupied rooms
 * @property {boolean} movieMode - Whether in movie mode
 * @property {number|null} avgTemp - Average temperature
 */

// ═══════════════════════════════════════════════════════════════
// DEVICE MODELS (from GET /home/devices)
// ═══════════════════════════════════════════════════════════════

/**
 * @typedef {Object} FireplaceState
 * @property {boolean} isOn - Whether fireplace is on
 * @property {number|null} onSince - Unix timestamp when turned on
 * @property {number} remainingMinutes - Minutes remaining before auto-off
 */

/**
 * @typedef {Object} TVMountState
 * @property {string} position - 'up' | 'down' | 'moving'
 * @property {number|null} preset - Current preset number if down
 */

/**
 * @typedef {Object} LockState
 * @property {string} name - Lock name
 * @property {boolean} isLocked - Whether locked
 * @property {string} doorState - 'open' | 'closed' | 'unknown'
 */

/**
 * @typedef {Object} DevicesResponse
 * @property {Light[]} lights - All lights
 * @property {Shade[]} shades - All shades
 * @property {AudioZone[]} audioZones - All audio zones
 * @property {LockState[]} locks - All locks
 * @property {FireplaceState} fireplace - Fireplace state
 * @property {TVMountState} tvMount - TV mount state
 */

// ═══════════════════════════════════════════════════════════════
// WEBSOCKET MESSAGE TYPES
// ═══════════════════════════════════════════════════════════════

/**
 * @typedef {Object} ContextUpdate
 * @property {'context_update'} type
 * @property {Object} data
 * @property {string} data.situation_phase - Current situation phase
 * @property {string} data.wakefulness - Wakefulness level
 * @property {number} [data.safety_score] - safety score value
 * @property {number} timestamp - Unix timestamp
 */

/**
 * @typedef {Object} HomeUpdate
 * @property {'home_update'} type
 * @property {Object} data
 * @property {boolean} data.movie_mode - Movie mode state
 * @property {boolean} data.fireplace_on - Fireplace state
 * @property {number} timestamp - Unix timestamp
 */

/**
 * @typedef {Object} SuggestionMessage
 * @property {'suggestion'} type
 * @property {Object} data
 * @property {string} data.action - Suggested action ID
 * @property {string} data.label - Display label
 * @property {string} data.icon - Emoji icon
 * @property {number} timestamp - Unix timestamp
 */

// ═══════════════════════════════════════════════════════════════
// COLONY COLORS (Standardized)
// ═══════════════════════════════════════════════════════════════

/**
 * Standard colony colors - use these across all platforms
 */
export const COLONY_COLORS = {
    spark: '#ff6b35',   // e₁ — Fold (A₂) — Ideation
    forge: '#d4af37',   // e₂ — Cusp (A₃) — Implementation
    flow: '#4ecdc4',    // e₃ — Swallowtail (A₄) — Adaptation
    nexus: '#9b7ebd',   // e₄ — Butterfly (A₅) — Integration
    beacon: '#f59e0b',  // e₅ — Hyperbolic (D₄⁺) — Planning
    grove: '#7eb77f',   // e₆ — Elliptic (D₄⁻) — Research
    crystal: '#67d4e4', // e₇ — Parabolic (D₅) — Verification
};

/**
 * Scene icons - SVG icon IDs from sprite sheet
 * Use with getIconSvg() from icons.js
 *
 * Example:
 *   import { getIconSvg } from './icons.js';
 *   element.innerHTML = getIconSvg(SCENE_ICONS.movie_mode);
 */
export const SCENE_ICONS = {
    movie_mode: 'action-movie-mode',
    goodnight: 'action-goodnight',
    welcome_home: 'action-welcome-home',
    away: 'action-away',
    fireplace: 'action-fireplace',
    lights: 'action-lights',
    shades: 'action-shades',
    tv: 'action-tv',
    lock: 'action-lock',
};

/**
 * Legacy emoji icons (for backward compatibility)
 * Prefer SCENE_ICONS with SVG system
 */
export const SCENE_ICONS_EMOJI = {
    movie_mode: '🎬',
    goodnight: '🌙',
    welcome_home: '🏡',
    away: '🔒',
    fireplace: '🔥',
    lights: '💡',
    shades: '🪟',
    tv: '📺',
};

/**
 * Brand icons - SVG icon IDs from sprite sheet
 */
export const COLONY_ICONS = {
    spark: 'colony-spark',
    forge: 'colony-forge',
    flow: 'colony-flow',
    nexus: 'colony-nexus',
    beacon: 'colony-beacon',
    grove: 'colony-grove',
    crystal: 'colony-crystal',
};

/**
 * Status icons - SVG icon IDs from sprite sheet
 */
export const STATUS_ICONS = {
    safe: 'status-safe',
    caution: 'status-caution',
    violation: 'status-violation',
    connected: 'status-connected',
    offline: 'status-offline',
    listening: 'status-listening',
};

/**
 * Navigation icons - SVG icon IDs from sprite sheet
 */
export const NAV_ICONS = {
    home: 'nav-home',
    rooms: 'nav-rooms',
    scenes: 'nav-scenes',
    settings: 'nav-settings',
    voice: 'nav-voice',
};

/**
 * Mode configuration for composer controls
 */
export const MODE_CONFIG = {
    ask: {
        id: 'ask',
        label: 'Ask',
        description: 'Get answers',
        colony: 'grove',
        color: COLONY_COLORS.grove,
    },
    plan: {
        id: 'plan',
        label: 'Plan',
        description: 'Think it through',
        colony: 'beacon',
        color: COLONY_COLORS.beacon,
    },
    agent: {
        id: 'agent',
        label: 'Agent',
        description: 'Make it happen',
        colony: 'forge',
        color: COLONY_COLORS.forge,
    },
};

/**
 * Safety score color thresholds
 */
export const SAFETY_COLORS = {
    ok: '#00ff88',      // safe threshold
    caution: '#ffd700', // caution threshold
    violation: '#ff4444', // violation threshold
};

/**
 * Get safety color based on score
 * @param {number|null} score - safety score value
 * @returns {string} - Hex color
 */
export function getSafetyColor(score) {
    if (score === null || score === undefined) return '#6b7280';
    if (score >= 0.5) return SAFETY_COLORS.ok;
    if (score >= 0) return SAFETY_COLORS.caution;
    return SAFETY_COLORS.violation;
}

/*
 * 鏡
 *
 */
