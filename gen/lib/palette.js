/**
 * Colony Palettes — GENUX color system for generative art
 * Each colony has a distinct color identity.
 */

export const COLONY_PALETTES = {
    spark: {
        name: 'Spark',
        emoji: '🔥',
        theme: 'Ideation',
        primary: '#FF6B35',
        secondary: '#FFB347',
        accent: '#F59E0B',
        bg: '#07060B',
        surface: '#1a0a05',
        glow: 'rgba(255, 107, 53, 0.3)',
        hueRange: [15, 45]  // orange-red
    },
    forge: {
        name: 'Forge',
        emoji: '⚒️',
        theme: 'Implementation',
        primary: '#FFB347',
        secondary: '#FFD700',
        accent: '#F59E0B',
        bg: '#07060B',
        surface: '#1a1505',
        glow: 'rgba(255, 179, 71, 0.3)',
        hueRange: [35, 55]  // warm gold
    },
    flow: {
        name: 'Flow',
        emoji: '🌊',
        theme: 'Debugging',
        primary: '#4DD0E1',
        secondary: '#06B6D4',
        accent: '#0EA5E9',
        bg: '#07060B',
        surface: '#051a1e',
        glow: 'rgba(77, 208, 225, 0.3)',
        hueRange: [180, 200]  // cyan
    },
    nexus: {
        name: 'Nexus',
        emoji: '🔗',
        theme: 'Integration',
        primary: '#B388FF',
        secondary: '#A855F7',
        accent: '#8B5CF6',
        bg: '#07060B',
        surface: '#150a1e',
        glow: 'rgba(179, 136, 255, 0.3)',
        hueRange: [260, 290]  // purple
    },
    beacon: {
        name: 'Beacon',
        emoji: '🗼',
        theme: 'Planning',
        primary: '#FFE082',
        secondary: '#FFC107',
        accent: '#F59E0B',
        bg: '#07060B',
        surface: '#1a1a05',
        glow: 'rgba(255, 224, 130, 0.3)',
        hueRange: [45, 55]  // bright gold
    },
    grove: {
        name: 'Grove',
        emoji: '🌿',
        theme: 'Research',
        primary: '#81C784',
        secondary: '#10B981',
        accent: '#059669',
        bg: '#07060B',
        surface: '#051a0a',
        glow: 'rgba(129, 199, 132, 0.3)',
        hueRange: [120, 150]  // sage green
    },
    crystal: {
        name: 'Crystal',
        emoji: '💎',
        theme: 'Verification',
        primary: '#4FC3F7',
        secondary: '#03A9F4',
        accent: '#0284C7',
        bg: '#07060B',
        surface: '#051520',
        glow: 'rgba(79, 195, 247, 0.3)',
        hueRange: [195, 210]  // light blue
    }
};

/**
 * Get palette for a colony with RNG-derived variations
 */
export function getPalette(colony, rng) {
    const base = COLONY_PALETTES[colony] || COLONY_PALETTES.spark;

    // Generate variations within the colony's hue range
    const hueShift = rng ? rng.range(-10, 10) : 0;
    const satVar = rng ? rng.range(0.9, 1.1) : 1;
    const lightVar = rng ? rng.range(0.95, 1.05) : 1;

    return {
        ...base,
        hueShift,
        satVar,
        lightVar,

        // Generate additional colors within palette
        colors: rng ? generateColors(base, rng, 5) : [base.primary, base.secondary, base.accent]
    };
}

/**
 * Generate N harmonious colors within a palette's hue range
 */
function generateColors(palette, rng, count) {
    const colors = [];
    const [hMin, hMax] = palette.hueRange;

    for (let i = 0; i < count; i++) {
        const h = rng.range(hMin, hMax);
        const s = rng.range(60, 100);
        const l = rng.range(50, 70);
        colors.push(`hsl(${h}, ${s}%, ${l}%)`);
    }

    return colors;
}

/**
 * Parse hex color to RGB
 */
export function hexToRgb(hex) {
    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    return result ? {
        r: parseInt(result[1], 16),
        g: parseInt(result[2], 16),
        b: parseInt(result[3], 16)
    } : null;
}

/**
 * Create RGBA string with alpha
 */
export function withAlpha(hex, alpha) {
    const rgb = hexToRgb(hex);
    if (!rgb) return hex;
    return `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, ${alpha})`;
}

/**
 * Get all colony names
 */
export function getColonies() {
    return Object.keys(COLONY_PALETTES);
}

/**
 * Get random colony
 */
export function randomColony(rng) {
    return rng.pick(getColonies());
}

export default { COLONY_PALETTES, getPalette, hexToRgb, withAlpha, getColonies, randomColony };
