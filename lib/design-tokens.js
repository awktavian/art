/**
 * Kagami Design Tokens for Three.js
 * ==================================
 * 
 * Exported from packages/kagami-design-tokens/tokens.json
 * Single source of truth for all visual constants.
 * 
 * Note: This module does NOT import THREE.js directly.
 * Use the helper functions with THREE passed as parameter.
 * 
 * h(x) ≥ 0 always
 */

// ═══════════════════════════════════════════════════════════════════════════
// COLONY COLORS (Octonion basis e1-e7)
// ═══════════════════════════════════════════════════════════════════════════

export const COLONY_COLORS = {
    spark:   { hex: '#FF6B35', num: 0xFF6B35, rgb: [255, 107, 53],  basis: 'e1', name: 'Ideation' },
    forge:   { hex: '#D4AF37', num: 0xD4AF37, rgb: [212, 175, 55],  basis: 'e2', name: 'Implementation' },
    flow:    { hex: '#4ECDC4', num: 0x4ECDC4, rgb: [78, 205, 196],  basis: 'e3', name: 'Adaptation' },
    nexus:   { hex: '#9B7EBD', num: 0x9B7EBD, rgb: [155, 126, 189], basis: 'e4', name: 'Integration' },
    beacon:  { hex: '#F59E0B', num: 0xF59E0B, rgb: [245, 158, 11],  basis: 'e5', name: 'Planning' },
    grove:   { hex: '#7EB77F', num: 0x7EB77F, rgb: [126, 183, 127], basis: 'e6', name: 'Research' },
    crystal: { hex: '#67D4E4', num: 0x67D4E4, rgb: [103, 212, 228], basis: 'e7', name: 'Verification' }
};

// Array order for iteration (matches Fano plane points)
export const COLONY_ORDER = ['spark', 'forge', 'flow', 'nexus', 'beacon', 'grove', 'crystal'];

// Get colony color as hex number
export function getColonyHex(index) {
    const name = COLONY_ORDER[index % 7];
    return COLONY_COLORS[name].num;
}

// Get colony color as hex string
export function getColonyHexString(index) {
    const name = COLONY_ORDER[index % 7];
    return COLONY_COLORS[name].hex;
}

// ═══════════════════════════════════════════════════════════════════════════
// VOID PALETTE (Backgrounds) - Hex numbers
// ═══════════════════════════════════════════════════════════════════════════

export const VOID_COLORS = {
    void:            0x07060B,
    voidWarm:        0x0D0A0F,
    obsidian:        0x12101A,
    voidLight:       0x1A1820,
    carbon:          0x252330,
    surfaceElevated: 0x1F1D24
};

// ═══════════════════════════════════════════════════════════════════════════
// STATUS COLORS
// ═══════════════════════════════════════════════════════════════════════════

export const STATUS_COLORS = {
    success: 0x00FF88,
    error:   0xFF4444,
    warning: 0xFFD700,
    info:    0x5AC8FA
};

// Safety colors for h(x) visualization
export const SAFETY_COLORS = {
    ok:        0x4ADE80,  // h(x) >= 0.5
    caution:   0xFBBF24,  // 0 <= h(x) < 0.5
    violation: 0xF87171   // h(x) < 0
};

export function getSafetyHex(hx) {
    if (hx >= 0.5) return SAFETY_COLORS.ok;
    if (hx >= 0) return SAFETY_COLORS.caution;
    return SAFETY_COLORS.violation;
}

// ═══════════════════════════════════════════════════════════════════════════
// TEXT COLORS
// ═══════════════════════════════════════════════════════════════════════════

export const TEXT_COLORS = {
    primary:   0xF5F0E8,
    secondary: 0xC4BFBA,
    tertiary:  0x9E9994,
    disabled:  0x5A5550
};

// ═══════════════════════════════════════════════════════════════════════════
// MOTION TIMING (Fibonacci-based) - NEVER use 100ms, 200ms, 300ms, 500ms
// ═══════════════════════════════════════════════════════════════════════════

export const DURATION = {
    instant:   89,
    fast:      144,
    normal:    233,
    slow:      377,
    slower:    610,
    slowest:   987,
    glacial:   1597,
    breathing: 2584
};

// Convert to seconds for Three.js animations
export const DURATION_S = {
    instant:   0.089,
    fast:      0.144,
    normal:    0.233,
    slow:      0.377,
    slower:    0.610,
    slowest:   0.987,
    glacial:   1.597,
    breathing: 2.584
};

// Fibonacci sequence for custom timing
export const FIBONACCI = [89, 144, 233, 377, 610, 987, 1597, 2584];

// ═══════════════════════════════════════════════════════════════════════════
// EASING CURVES (cubic-bezier)
// ═══════════════════════════════════════════════════════════════════════════

export const EASING = {
    snap:    { bezier: [0.7, 0, 0.3, 1],       name: 'snap' },
    sharp:   { bezier: [0.4, 0, 0.2, 1],       name: 'sharp' },
    bounce:  { bezier: [0.34, 1.2, 0.64, 1],   name: 'bounce' },
    elastic: { bezier: [0.68, -0.2, 0.32, 1.2], name: 'elastic' },
    smooth:  { bezier: [0.16, 1, 0.3, 1],      name: 'smooth' },
    linear:  { bezier: [0, 0, 1, 1],           name: 'linear' }
};

// GSAP-compatible easing functions
export function getEasingFunction(name) {
    const curves = {
        snap:    t => t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2,
        sharp:   t => t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2,
        bounce:  t => {
            const c4 = (2 * Math.PI) / 3;
            return t === 0 ? 0 : t === 1 ? 1 
                : Math.pow(2, -10 * t) * Math.sin((t * 10 - 0.75) * c4) + 1;
        },
        smooth:  t => t === 0 ? 0 : t === 1 ? 1 : 1 - Math.pow(2, -10 * t),
        linear:  t => t
    };
    return curves[name] || curves.smooth;
}

// ═══════════════════════════════════════════════════════════════════════════
// SPACING (8pt grid)
// ═══════════════════════════════════════════════════════════════════════════

export const SPACING = {
    unit: 8,
    xxs:  2,
    xs:   4,
    sm:   8,
    md:   16,
    lg:   24,
    xl:   32,
    '2xl': 40,
    '3xl': 48,
    '4xl': 64,
    '5xl': 80,
    '6xl': 96
};

// Convert to Three.js world units (1 unit = 1 meter in XR)
export const SPACING_M = {
    xxs:  0.002,
    xs:   0.004,
    sm:   0.008,
    md:   0.016,
    lg:   0.024,
    xl:   0.032,
    '2xl': 0.040,
    '3xl': 0.048,
    '4xl': 0.064
};

// ═══════════════════════════════════════════════════════════════════════════
// CORNER RADIUS
// ═══════════════════════════════════════════════════════════════════════════

export const RADIUS = {
    none: 0,
    xs:   4,
    sm:   8,
    md:   12,
    lg:   16,
    xl:   20,
    '2xl': 24,
    '3xl': 32,
    full: 9999
};

// ═══════════════════════════════════════════════════════════════════════════
// XR SPATIAL DESIGN
// ═══════════════════════════════════════════════════════════════════════════

export const XR = {
    // Proxemic zones (meters)
    proxemicZones: {
        intimate: { min: 0,    max: 0.45, scale: 0.7,  opacity: 0.95 },
        personal: { min: 0.45, max: 1.2,  scale: 1.0,  opacity: 0.85 },
        social:   { min: 1.2,  max: 3.6,  scale: 1.3,  opacity: 0.75 },
        public:   { min: 3.6,  max: 7.6,  scale: 1.6,  opacity: 0.65 }
    },
    
    // Optimal content placement
    optimalContentZone: { min: 1.25, max: 5.0 },
    
    // Viewing angles (degrees)
    viewingAngles: {
        comfortable: { horizontal: 30, vertical: 20 },
        extended:    { horizontal: 55, vertical: 30 },
        maximum:     { horizontal: 90, vertical: 60 }
    },
    
    // Minimum target sizes (meters)
    buttonMinSize: 0.044,
    buttonRecommendedSize: 0.06,
    grabZone: 0.05,
    hoverDetection: 0.1,
    
    // Animation timing (Fibonacci)
    animationTiming: [89, 144, 233, 377, 610, 987]
};

// ═══════════════════════════════════════════════════════════════════════════
// EFFECTS (Prismorphism)
// ═══════════════════════════════════════════════════════════════════════════

export const EFFECTS = {
    glass: {
        blur: { thin: 10, regular: 20, thick: 40 },
        transparency: { min: 0.70, default: 0.80, max: 0.90 },
        borderWidth: 1,
        borderOpacity: 0.10
    },
    
    spectral: {
        phaseCount: 7,  // Octonion basis
        shimmerDuration: 8000,
        shimmerOpacity: { idle: 0, hover: 0.3, active: 0.5 },
        borderDuration: 6000
    },
    
    caustics: {
        layers: 3,
        durations: [25000, 30000, 35000],
        opacity: { min: 0.4, max: 0.7 }
    },
    
    bloom: {
        strength: 1.5,
        radius: 0.4,
        threshold: 0.8
    },
    
    chromaticAberration: {
        offset: 0.002
    }
};

// ═══════════════════════════════════════════════════════════════════════════
// HIGH CONTRAST MODE (WCAG AAA)
// ═══════════════════════════════════════════════════════════════════════════

export const HIGH_CONTRAST = {
    background:    0x000000,
    surface:       0x121212,
    text:          0xFFFFFF,
    textSecondary: 0xE0E0E0,
    accent:        0x00FFFF,
    border:        0xFFFFFF,
    colony: {
        spark:   0xFF7744,
        forge:   0xFFD700,
        flow:    0x00FFFF,
        nexus:   0xCC99FF,
        beacon:  0xFFBB00,
        grove:   0x00FF88,
        crystal: 0x00EEFF
    }
};

// ═══════════════════════════════════════════════════════════════════════════
// FANO PLANE GEOMETRY DATA
// ═══════════════════════════════════════════════════════════════════════════

// Fano plane points (7 points, arranged for visual clarity)
export const FANO_POINTS = [
    [0, 2, 0],        // 0 - Spark (top)
    [-1.5, 0.5, 0],   // 1 - Forge (upper left)
    [1.5, 0.5, 0],    // 2 - Flow (upper right)
    [-2, -1.5, 0],    // 3 - Nexus (lower left)
    [0, -0.5, 0],     // 4 - Beacon (center)
    [2, -1.5, 0],     // 5 - Grove (lower right)
    [0, -2.5, 0]      // 6 - Crystal (bottom)
];

// Fano plane lines (each line connects 3 collinear points)
export const FANO_LINES = [
    [0, 1, 3],  // Spark-Forge-Nexus
    [0, 2, 5],  // Spark-Flow-Grove
    [0, 4, 6],  // Spark-Beacon-Crystal (vertical)
    [1, 2, 4],  // Forge-Flow-Beacon
    [1, 5, 6],  // Forge-Grove-Crystal
    [2, 3, 6],  // Flow-Nexus-Crystal
    [3, 4, 5]   // Nexus-Beacon-Grove
];

// Colony to Fano point mapping
export const COLONY_FANO_MAP = {
    spark:   0,
    forge:   1,
    flow:    2,
    nexus:   3,
    beacon:  4,
    grove:   5,
    crystal: 6
};

// ═══════════════════════════════════════════════════════════════════════════
// PATENT DATA
// ═══════════════════════════════════════════════════════════════════════════

export const PATENT_CATEGORIES = [
    { id: 'A', name: 'Mathematical Foundations', icon: '∞', count: 8, colony: 'crystal' },
    { id: 'B', name: 'AI Safety Systems', icon: '🛡️', count: 6, colony: 'beacon' },
    { id: 'C', name: 'Distributed Consensus', icon: '🔗', count: 5, colony: 'nexus' },
    { id: 'D', name: 'World Models / Training', icon: '🌍', count: 7, colony: 'grove' },
    { id: 'E', name: 'Post-Quantum Crypto', icon: '🔐', count: 4, colony: 'forge' },
    { id: 'F', name: 'Smart Home', icon: '🏠', count: 7, colony: 'flow' },
    { id: 'G', name: 'Voice / Audio', icon: '🎙️', count: 4, colony: 'spark' },
    { id: 'H', name: 'Economic / Autonomous', icon: '💹', count: 4, colony: 'beacon' },
    { id: 'I', name: 'Platform / Architecture', icon: '⚡', count: 5, colony: 'forge' },
    { id: 'J', name: 'Reasoning / Cognition', icon: '🧠', count: 3, colony: 'nexus' },
    { id: 'K', name: 'Visualization / Media', icon: '👁️', count: 1, colony: 'spark' }
];

export const PATENT_PRIORITIES = {
    P1: { color: 0xFFD700, scale: 1.2, distance: 8,  opacity: 1.0,  count: 6 },
    P2: { color: 0x67D4E4, scale: 1.0, distance: 12, opacity: 0.8,  count: 18 },
    P3: { color: 0xF5F0E8, scale: 0.8, distance: 16, opacity: 0.5,  count: 30 }
};

// ═══════════════════════════════════════════════════════════════════════════
// THREE.JS HELPER FUNCTIONS (pass THREE as argument)
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Get a Three.js Color for a colony
 */
export function getColonyColor(THREE, index) {
    const name = COLONY_ORDER[index % 7];
    return new THREE.Color(COLONY_COLORS[name].num);
}

/**
 * Create colony material
 */
export function createColonyMaterial(THREE, colonyName, options = {}) {
    const colorData = COLONY_COLORS[colonyName] || COLONY_COLORS.crystal;
    const color = new THREE.Color(colorData.num);
    
    return new THREE.MeshPhysicalMaterial({
        color: color,
        emissive: color.clone().multiplyScalar(0.3),
        emissiveIntensity: options.emissiveIntensity || 0.5,
        metalness: options.metalness || 0.1,
        roughness: options.roughness || 0.3,
        clearcoat: options.clearcoat || 0.8,
        clearcoatRoughness: options.clearcoatRoughness || 0.2,
        transparent: options.transparent !== false,
        opacity: options.opacity || 0.9,
        ...options
    });
}

/**
 * Create glow material
 */
export function createGlowMaterial(THREE, color, options = {}) {
    const baseColor = typeof color === 'number' ? new THREE.Color(color) : color;
    
    return new THREE.MeshBasicMaterial({
        color: baseColor,
        transparent: true,
        opacity: options.opacity || 0.3,
        side: THREE.BackSide,
        blending: THREE.AdditiveBlending,
        ...options
    });
}

/**
 * Create void material
 */
export function createVoidMaterial(THREE, options = {}) {
    return new THREE.MeshStandardMaterial({
        color: VOID_COLORS.obsidian,
        metalness: 0.9,
        roughness: 0.1,
        ...options
    });
}

/**
 * Lerp between two colors
 */
export function lerpColor(THREE, colorA, colorB, t) {
    const result = new THREE.Color();
    result.r = colorA.r + (colorB.r - colorA.r) * t;
    result.g = colorA.g + (colorB.g - colorA.g) * t;
    result.b = colorA.b + (colorB.b - colorA.b) * t;
    return result;
}

/**
 * Get a Fibonacci-timed phase value (0-1) for animations
 */
export function getFibonacciPhase(timeMs, duration = 'normal') {
    const d = DURATION[duration] || DURATION.normal;
    return (timeMs % d) / d;
}

/**
 * Smooth step function for animations
 */
export function smoothstep(edge0, edge1, x) {
    const t = Math.max(0, Math.min(1, (x - edge0) / (edge1 - edge0)));
    return t * t * (3 - 2 * t);
}

/**
 * Get proxemic zone based on distance
 */
export function getProxemicZone(distance) {
    for (const [zone, config] of Object.entries(XR.proxemicZones)) {
        if (distance >= config.min && distance < config.max) {
            return { zone, ...config };
        }
    }
    return { zone: 'public', ...XR.proxemicZones.public };
}

export default {
    COLONY_COLORS,
    COLONY_ORDER,
    VOID_COLORS,
    STATUS_COLORS,
    SAFETY_COLORS,
    TEXT_COLORS,
    DURATION,
    DURATION_S,
    FIBONACCI,
    EASING,
    SPACING,
    SPACING_M,
    RADIUS,
    XR,
    EFFECTS,
    HIGH_CONTRAST,
    FANO_POINTS,
    FANO_LINES,
    PATENT_CATEGORIES,
    PATENT_PRIORITIES,
    getColonyHex,
    getColonyHexString,
    getSafetyHex,
    getEasingFunction,
    getColonyColor,
    createColonyMaterial,
    createGlowMaterial,
    createVoidMaterial,
    lerpColor,
    getFibonacciPhase,
    smoothstep,
    getProxemicZone
};
