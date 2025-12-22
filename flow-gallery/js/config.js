// ═══════════════════════════════════════════════════════════════════════════
// FLOW GALLERY CONFIGURATION
// 🌊 e₃ — The Swallowtail Catastrophe — A₄
// "Every bug is a river that finds its way to the sea."
// ═══════════════════════════════════════════════════════════════════════════

export const CONFIG = {
    // Flow palette: deep ocean → surface → foam
    COLORS: {
        OCEAN_DEEP: '#001F3F',
        OCEAN: '#003366',
        TEAL: '#008B8B',
        CYAN: '#00CED1',
        AQUA: '#00FFFF',
        FOAM: '#E0FFFF',
        SEAFOAM: '#98FF98',
        HEALING_GREEN: '#00FF7F',
        ERROR_RED: '#FF6B6B',
        WARNING_AMBER: '#FFB347',
        INFO_BLUE: '#6BB3FF',
        VOID: '#0A0A0F',
    },
    
    // Current (debug stream) settings
    CURRENT: {
        STREAM_SPEED: 2,
        PARTICLE_COUNT: 50,
        WAVE_AMPLITUDE: 30,
        WAVE_FREQUENCY: 0.02,
    },
    
    // Swallowtail catastrophe settings
    SWALLOWTAIL: {
        CANVAS_PADDING: 50,
        LINE_WIDTH: 2.5,
        ANIMATION_SPEED: 0.012,
        SURFACE_RESOLUTION: 60,
    },
    
    // Recovery settings
    RECOVERY: {
        MAX_ERRORS: 20,
        HEAL_RATE: 100,
        SPAWN_INTERVAL: 2000,
    },
};

// Error types for the recovery visualization
export const ERROR_TYPES = [
    { type: 'TypeError', color: '#FF6B6B', severity: 3 },
    { type: 'ReferenceError', color: '#FF8C42', severity: 3 },
    { type: 'SyntaxError', color: '#FF6B6B', severity: 4 },
    { type: 'RangeError', color: '#FFB347', severity: 2 },
    { type: 'NetworkError', color: '#FF6B6B', severity: 3 },
    { type: 'Warning', color: '#FFB347', severity: 1 },
    { type: 'Info', color: '#6BB3FF', severity: 0 },
];

// Debug messages for the recovery log
export const DEBUG_MESSAGES = [
    '[TRACE] Entering debug context...',
    '[DEBUG] Inspecting stack frame...',
    '[FLOW] Following execution path...',
    '[HEAL] Applying fix to affected scope...',
    '[RECOVER] Restoring stable state...',
    '[ADAPT] Learning from error pattern...',
    '[SUCCESS] Bug resolved. Flow restored.',
    '[INFO] System returning to equilibrium...',
    '[WARN] Potential instability detected...',
    '[ERROR] Exception caught. Analyzing...',
];

