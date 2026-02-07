/**
 * Unified Typography System for Kagami Patent Museum
 * 
 * Provides consistent font tokens and canvas rendering helpers
 * for all text elements: signs, floating text, plaques, and UI.
 */

// ============================================================================
// FONT TOKENS
// ============================================================================

export const FONTS = {
    // Display (Orbitron) - Heroes, titles, dramatic text
    display: {
        family: '"Orbitron", sans-serif',
        weights: { regular: 500, semibold: 600, bold: 700 }
    },
    
    // Sans (IBM Plex Sans) - UI, labels, body text
    sans: {
        family: '"IBM Plex Sans", -apple-system, BlinkMacSystemFont, sans-serif',
        weights: { regular: 400, medium: 500, semibold: 600 }
    },
    
    // Mono (IBM Plex Mono) - Code, IDs, metadata, technical
    mono: {
        family: '"IBM Plex Mono", "SF Mono", Consolas, monospace',
        weights: { regular: 400, medium: 500 }
    }
};

// ============================================================================
// SIZE SCALE (in pixels, following 8px grid)
// ============================================================================

export const SIZES = {
    xs: 11,
    sm: 12,
    base: 14,
    md: 16,
    lg: 20,
    xl: 24,
    '2xl': 28,
    '3xl': 36,
    '4xl': 48,
    '5xl': 64,
    '6xl': 80,
    '7xl': 96
};

// ============================================================================
// LINE HEIGHTS
// ============================================================================

export const LINE_HEIGHTS = {
    tight: 1.2,
    normal: 1.4,
    relaxed: 1.6
};

// ============================================================================
// CANVAS FONT HELPERS
// ============================================================================

/**
 * Get a CSS font string for canvas rendering
 * @param {number} size - Font size in pixels
 * @param {string} variant - 'display', 'sans', 'sansBold', 'mono'
 * @returns {string} CSS font string
 */
export function getCanvasFont(size, variant = 'sans') {
    const fontMap = {
        display: { weight: FONTS.display.weights.semibold, family: FONTS.display.family },
        displayBold: { weight: FONTS.display.weights.bold, family: FONTS.display.family },
        sans: { weight: FONTS.sans.weights.regular, family: FONTS.sans.family },
        sansMedium: { weight: FONTS.sans.weights.medium, family: FONTS.sans.family },
        sansBold: { weight: FONTS.sans.weights.semibold, family: FONTS.sans.family },
        mono: { weight: FONTS.mono.weights.regular, family: FONTS.mono.family },
        monoMedium: { weight: FONTS.mono.weights.medium, family: FONTS.mono.family }
    };
    
    const font = fontMap[variant] || fontMap.sans;
    return `${font.weight} ${size}px ${font.family}`;
}

/**
 * Setup a high-DPI canvas for crisp text rendering
 * @param {HTMLCanvasElement} canvas - Canvas element
 * @param {number} width - Logical width
 * @param {number} height - Logical height
 * @param {number} scale - DPI scale (default 2 for retina)
 * @returns {CanvasRenderingContext2D} Configured context
 */
export function setupHiDPICanvas(canvas, width, height, scale = 2) {
    canvas.width = width * scale;
    canvas.height = height * scale;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    
    const ctx = canvas.getContext('2d');
    ctx.scale(scale, scale);
    
    // Enable subpixel rendering
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = 'high';
    
    return ctx;
}

/**
 * Draw text with consistent styling
 * @param {CanvasRenderingContext2D} ctx - Canvas context
 * @param {string} text - Text to render
 * @param {number} x - X position
 * @param {number} y - Y position
 * @param {Object} options - Styling options
 */
export function drawText(ctx, text, x, y, options = {}) {
    const {
        size = SIZES.base,
        variant = 'sans',
        color = '#F5F0E8',
        align = 'left',
        baseline = 'middle',
        shadow = null,
        maxWidth = undefined
    } = options;
    
    ctx.save();
    
    ctx.font = getCanvasFont(size, variant);
    ctx.fillStyle = color;
    ctx.textAlign = align;
    ctx.textBaseline = baseline;
    
    if (shadow) {
        ctx.shadowColor = shadow.color || color;
        ctx.shadowBlur = shadow.blur || 10;
        ctx.shadowOffsetX = shadow.offsetX || 0;
        ctx.shadowOffsetY = shadow.offsetY || 0;
    }
    
    if (maxWidth) {
        ctx.fillText(text, x, y, maxWidth);
    } else {
        ctx.fillText(text, x, y);
    }
    
    ctx.restore();
}

/**
 * Measure text width with consistent styling
 * @param {CanvasRenderingContext2D} ctx - Canvas context
 * @param {string} text - Text to measure
 * @param {number} size - Font size
 * @param {string} variant - Font variant
 * @returns {number} Text width in pixels
 */
export function measureText(ctx, text, size, variant = 'sans') {
    ctx.save();
    ctx.font = getCanvasFont(size, variant);
    const metrics = ctx.measureText(text);
    ctx.restore();
    return metrics.width;
}

// ============================================================================
// COLONY COLOR UTILITIES
// ============================================================================

export const COLONY_COLORS = {
    spark: { hex: 0xFF6B35, rgb: [255, 107, 53], name: 'Spark' },
    forge: { hex: 0xF7931E, rgb: [247, 147, 30], name: 'Forge' },
    flow: { hex: 0x7ECFC0, rgb: [126, 207, 192], name: 'Flow' },
    nexus: { hex: 0xE8D44D, rgb: [232, 212, 77], name: 'Nexus' },
    beacon: { hex: 0xC78FFF, rgb: [199, 143, 255], name: 'Beacon' },
    grove: { hex: 0x95E17B, rgb: [149, 225, 123], name: 'Grove' },
    crystal: { hex: 0x67D4E4, rgb: [103, 212, 228], name: 'Crystal' }
};

/**
 * Convert colony hex to CSS color string
 * @param {string} colony - Colony name
 * @param {number} alpha - Optional alpha (0-1)
 * @returns {string} CSS color string
 */
export function getColonyColor(colony, alpha = 1) {
    const c = COLONY_COLORS[colony];
    if (!c) return '#F5F0E8';
    
    if (alpha < 1) {
        return `rgba(${c.rgb.join(',')}, ${alpha})`;
    }
    return `#${c.hex.toString(16).padStart(6, '0')}`;
}

// ============================================================================
// TEXT STYLE PRESETS
// ============================================================================

export const TEXT_PRESETS = {
    // Sign title (colony names on hanging signs)
    signTitle: {
        size: 72,
        variant: 'sansBold',
        transform: 'uppercase'
    },
    
    // Sign subtitle ("WING", etc.)
    signSubtitle: {
        size: 36,
        variant: 'sans',
        color: '#888888'
    },
    
    // Plaque title (patent names)
    plaqueTitle: {
        size: 24,
        variant: 'sansBold',
        color: '#F5F0E8'
    },
    
    // Plaque body (descriptions)
    plaqueBody: {
        size: 14,
        variant: 'sans',
        color: '#9E9994',
        lineHeight: LINE_HEIGHTS.relaxed
    },
    
    // Plaque ID (patent IDs like P1-001)
    plaqueId: {
        size: 14,
        variant: 'mono',
        transform: 'uppercase'
    },
    
    // Floating labels (above artworks)
    floatingLabel: {
        size: 32,
        variant: 'mono',
        shadow: { blur: 15 }
    },
    
    // UI labels
    uiLabel: {
        size: 14,
        variant: 'sans',
        color: '#F5F0E8'
    },
    
    // Minimap labels
    minimapLabel: {
        size: 10,
        variant: 'sans'
    }
};

/**
 * Apply a text preset to canvas context
 * @param {CanvasRenderingContext2D} ctx - Canvas context
 * @param {string} presetName - Name of preset from TEXT_PRESETS
 * @param {string} color - Optional color override
 */
export function applyPreset(ctx, presetName, color = null) {
    const preset = TEXT_PRESETS[presetName];
    if (!preset) return;
    
    ctx.font = getCanvasFont(preset.size, preset.variant);
    ctx.fillStyle = color || preset.color || '#F5F0E8';
    
    if (preset.shadow) {
        ctx.shadowColor = color || preset.shadow.color || '#FFFFFF';
        ctx.shadowBlur = preset.shadow.blur || 0;
    }
}

// ============================================================================
// EXPORTS
// ============================================================================

export default {
    FONTS,
    SIZES,
    LINE_HEIGHTS,
    COLONY_COLORS,
    TEXT_PRESETS,
    getCanvasFont,
    setupHiDPICanvas,
    drawText,
    measureText,
    getColonyColor,
    applyPreset
};
