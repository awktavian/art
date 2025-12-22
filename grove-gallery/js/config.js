// Configuration and Constants

export const CONFIG = {
    // Performance
    TARGET_FPS: 60,
    PARTICLE_LIMIT: 500,
    PARTICLE_SPAWN_RATE: 3,

    // Cursor
    CURSOR_TRAIL_LENGTH: 20,
    CURSOR_INFLUENCE_RADIUS: 150,
    CURSOR_PULL_STRENGTH: 30,

    // Particles
    PARTICLE_LIFETIME: 2000, // ms
    PARTICLE_SPEED: 1.5,
    PARTICLE_SIZE: 2,
    PARTICLE_GLOW_SIZE: 4,

    // Scroll
    SCROLL_THRESHOLD: 0.2, // Trigger animations when 20% visible

    // XR
    XR_REFERENCE_SPACE: 'local-floor',
    XR_SESSION_MODE: 'immersive-vr',

    // Timing
    DEBOUNCE_DELAY: 100,
    THROTTLE_DELAY: 16, // ~60fps
};

export const COLORS = {
    void: '#0A0A0C',
    light: '#FAFAF8',
    gold: '#D4AF37',

    // Colonies
    spark: '#FF00FF',
    forge: '#FF2D55',
    flow: '#00E5CC',
    nexus: '#AF52DE',
    beacon: '#FFD60A',
    grove: '#30D158',
    crystal: '#0A84FF',
};

export const CATASTROPHES = {
    spark: { type: 'Fold', notation: 'A₂', codimension: 1 },
    forge: { type: 'Cusp', notation: 'A₃', codimension: 2 },
    flow: { type: 'Swallowtail', notation: 'A₄', codimension: 3 },
    nexus: { type: 'Butterfly', notation: 'A₅', codimension: 4 },
    beacon: { type: 'Hyperbolic', notation: 'D₄⁺', codimension: 3 },
    grove: { type: 'Elliptic', notation: 'D₄⁻', codimension: 3 },
    crystal: { type: 'Parabolic', notation: 'D₅', codimension: 4 },
};
