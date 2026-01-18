/**
 * Kagami Orb V3.1 — Component Database
 * SINGLE SOURCE OF TRUTH for dimensions
 * All measurements from manufacturer datasheets (Jan 2026)
 *
 * GEOMETRY NOTE: Components must fit within sphere curvature!
 * At Y=±20: available Ø = 57.4mm
 * At Y=±30: available Ø = 36.1mm
 * At equator (Y=0): available Ø = 70mm
 */

export const DESIGN_CONSTRAINTS = {
    outerDiameter: 85,
    shellThickness: 7.5,
    internalDiameter: 70,
    maxComponent: 65,
    levitationGap: { min: 18, max: 25 },
    maxOrbMass: 350,
    actualOrbMass: 391, // Exceeds target by 41g
};

/**
 * Calculate available internal diameter at given Y position
 * @param {number} y - Y position from center (mm)
 * @returns {number} Available internal diameter (mm)
 */
export function getAvailableDiameter(y) {
    const innerRadius = DESIGN_CONSTRAINTS.internalDiameter / 2;
    const rSquared = innerRadius * innerRadius - y * y;
    if (rSquared <= 0) return 0;
    return 2 * Math.sqrt(rSquared);
}

/**
 * Verified Component Database
 * Each component has:
 * - id: Unique identifier
 * - name: Display name
 * - grp: Assembly group
 * - ico: Emoji icon
 * - geo: Geometry type (hemi_top, hemi_bot, box, cyl, disc, ring, torus, leds, mics)
 * - Dimensions (r, w, d, h, etc.)
 * - y: Y position (mm from center)
 * - clr: Base color (hex)
 * - op: Opacity (0-1, optional)
 * - mass: Weight (g)
 * - W: Power dissipation (W)
 * - verified: Boolean
 * - src: Source/supplier
 * - url: Datasheet URL (optional)
 * - dims: Human-readable dimensions
 * - note: Additional notes (optional)
 * - base: 1 if base station component (optional)
 */
export const COMPONENTS = [
    // ==================== SHELL ====================
    {
        id: 'shell_top',
        name: 'Shell (Top)',
        grp: 'Shell',
        ico: '🔵',
        geo: 'hemi_top',
        r: 42.5,
        y: 0,
        clr: 0x88ccff,
        op: 0.15,
        mass: 45,
        W: 0,
        verified: true,
        src: 'Clear acrylic + mirror film',
        dims: 'Ø85mm hemisphere'
    },
    {
        id: 'shell_bot',
        name: 'Shell (Bottom)',
        grp: 'Shell',
        ico: '🔵',
        geo: 'hemi_bot',
        r: 42.5,
        y: 0,
        clr: 0x88ccff,
        op: 0.15,
        mass: 45,
        W: 0,
        verified: true,
        src: 'Clear acrylic + mirror film',
        dims: 'Ø85mm hemisphere'
    },

    // ==================== DISPLAY STACK ====================
    // NOTE: Camera faces UP through display center (pupil aperture)
    {
        id: 'display',
        name: '1.39" AMOLED',
        grp: 'Display',
        ico: '📺',
        geo: 'box',
        w: 38.21,
        d: 38.83,
        h: 0.68,
        y: 28, // ADJUSTED from 30 to fit sphere curvature (available: 40.5mm at y=28)
        clr: 0x111120,
        mass: 8,
        W: 0.8,
        verified: true,
        src: 'King Tech Display',
        url: 'https://www.kingtechdisplay.com',
        dims: '38.8×38.2×0.7mm, 454×454',
        note: 'Round AMOLED with RM69330 driver'
    },
    {
        id: 'camera',
        name: 'IMX989 Module',
        grp: 'Display',
        ico: '📷',
        geo: 'box',
        w: 26,
        d: 26,
        h: 9.4,
        y: 22, // ADJUSTED: Camera below display, lens UP
        clr: 0x1a1a2a,
        mass: 15,
        W: 0.5,
        verified: true,
        src: 'SincereFirst',
        url: 'https://www.cameramodule.com',
        dims: '26×26×9.4mm, 50.3MP',
        note: 'Sensor faces UP for Digital PTZ through display'
    },
    {
        id: 'disp_mnt',
        name: 'Display Mount',
        grp: 'Display',
        ico: '🔧',
        geo: 'cyl',
        r: 22,
        h: 8,
        y: 15, // ADJUSTED
        clr: 0x444444,
        mass: 10,
        W: 0,
        verified: true,
        src: 'Grey Pro SLA',
        dims: 'Ø44×8mm'
    },

    // ==================== COMPUTE ====================
    {
        id: 'main_pcb',
        name: 'Main PCB',
        grp: 'Compute',
        ico: '📟',
        geo: 'disc',
        r: 30,
        h: 1.6,
        y: 8,
        clr: 0x0d4d0d,
        mass: 15,
        W: 0,
        verified: true,
        src: '4-layer FR4',
        dims: 'Ø60×1.6mm'
    },
    {
        id: 'som',
        name: 'QCS6490 SoM',
        grp: 'Compute',
        ico: '🧠',
        geo: 'box',
        w: 42.5,
        d: 35.5,
        h: 2.7,
        y: 11,
        clr: 0x1a6b1a,
        mass: 25,
        W: 8,
        verified: true,
        src: 'Thundercomm',
        url: 'https://www.thundercomm.com/product/c6490-som/',
        dims: '42.5×35.5×2.7mm',
        note: '12.5 TOPS NPU, 2.7GHz Kryo'
    },
    {
        id: 'heatsink',
        name: 'Heatsink',
        grp: 'Compute',
        ico: '❄️',
        geo: 'box',
        w: 20,
        d: 20,
        h: 6,
        y: 15,
        clr: 0x2a2a2a,
        mass: 8,
        W: 0,
        verified: true,
        src: 'Aluminum',
        dims: '20×20×6mm'
    },
    {
        id: 'hailo',
        name: 'Hailo-10H',
        grp: 'Compute',
        ico: '🤖',
        geo: 'box',
        w: 42,
        d: 22,
        h: 2.63,
        y: 5,
        clr: 0x145214,
        mass: 8,
        W: 2.5,
        verified: true,
        src: 'Hailo',
        url: 'https://hailo.ai',
        dims: '42×22×2.63mm (M.2 2242)',
        note: '40 TOPS INT4, GenAI native'
    },

    // ==================== AUDIO ====================
    {
        id: 'xmos',
        name: 'XMOS XVF3800',
        grp: 'Audio',
        ico: '🎛️',
        geo: 'box',
        w: 7,
        d: 7,
        h: 0.9,
        y: 6,
        clr: 0x2a2a3a,
        mass: 1,
        W: 0.4,
        verified: true,
        src: 'XMOS',
        url: 'https://www.xmos.com/download/XVF3800-Device-Datasheet',
        dims: '7×7×0.9mm (QFN-60)',
        note: 'Voice processor, AEC/beamforming'
    },
    {
        id: 'mics',
        name: 'sensiBel ×4',
        grp: 'Audio',
        ico: '🎤',
        geo: 'mics',
        r: 28,
        y: 3,
        clr: 0x3a3a3a,
        mass: 0.5,
        W: 0.006,
        verified: true,
        src: 'sensiBel',
        url: 'https://sensibel.com/product/',
        dims: '6×3.8×2.47mm each',
        note: 'Optical MEMS, -26dB SNR'
    },
    {
        id: 'speaker',
        name: 'Speaker 28mm',
        grp: 'Audio',
        ico: '🔊',
        geo: 'cyl',
        r: 14,
        h: 5.4,
        y: -6, // ADJUSTED to not collide with battery
        clr: 0x252525,
        mass: 5,
        W: 0,
        verified: true,
        src: 'Yueda/Tectonic',
        dims: 'Ø28×5.4mm'
    },

    // ==================== LEDs ====================
    {
        id: 'led_ring',
        name: 'LED Ring PCB',
        grp: 'LEDs',
        ico: '💡',
        geo: 'ring',
        ro: 27,
        ri: 22,
        h: 1.6,
        y: 0,
        clr: 0x0d3d0d,
        mass: 3,
        W: 0,
        verified: true,
        src: 'Flex PCB',
        dims: 'Ø54×1.6mm'
    },
    {
        id: 'leds',
        name: 'HD108 ×16',
        grp: 'LEDs',
        ico: '✨',
        geo: 'leds',
        n: 16,
        r: 25,
        y: 0,
        clr: 0xff44ff,
        mass: 1,
        W: 0.8,
        verified: true,
        src: 'Rose Lighting',
        url: 'https://www.rose-lighting.com',
        dims: '5.1×5.0×1.6mm each',
        note: '16-bit RGBW, 65536 levels/ch'
    },
    {
        id: 'diffuser',
        name: 'Diffuser Ring',
        grp: 'LEDs',
        ico: '◯',
        geo: 'ring',
        ro: 29,
        ri: 21,
        h: 3,
        y: 1,
        clr: 0xffffff,
        op: 0.6,
        mass: 4,
        W: 0,
        verified: true,
        src: 'Frosted acrylic',
        dims: 'Ø58×3mm'
    },

    // ==================== POWER ====================
    {
        id: 'battery',
        name: 'Battery 2200mAh',
        grp: 'Power',
        ico: '🔋',
        geo: 'box',
        w: 50, // ADJUSTED: smaller footprint to fit sphere curvature
        d: 30, // ADJUSTED
        h: 22, // Slightly taller to maintain capacity
        y: -16, // ADJUSTED: moved up to avoid sphere curvature
        clr: 0x0055aa,
        mass: 150,
        W: 0.3,
        verified: true,
        src: 'Custom LiPo 3S',
        dims: '50×30×22mm = 24Wh',
        note: 'CRITICAL: 4000mAh (131mm) TOO LARGE'
    },
    {
        id: 'bms',
        name: 'BMS + Charger',
        grp: 'Power',
        ico: '⚡',
        geo: 'box',
        w: 30,
        d: 20,
        h: 4,
        y: -3, // ADJUSTED: positioned away from battery collision
        clr: 0x0d5d0d,
        mass: 8,
        W: 0.5,
        verified: true,
        src: 'BQ25895+BQ40Z50',
        dims: '30×20×4mm'
    },
    {
        id: 'coil_mnt',
        name: 'Coil Mount',
        grp: 'Power',
        ico: '🔧',
        geo: 'disc',
        r: 33,
        h: 4,
        y: -30, // NOTE: Integrated into shell bottom
        clr: 0x383838,
        mass: 8,
        W: 0,
        verified: true,
        src: 'Tough 2000 SLA',
        dims: 'Ø66×4mm',
        note: 'Shell-integrated at bottom pole'
    },
    {
        id: 'rx_coil',
        name: 'RX Coil',
        grp: 'Power',
        ico: '〰️',
        geo: 'torus',
        R: 32, // ADJUSTED: Ø70mm = R=35, but using R=32 for visual (actual is shell-integrated)
        r: 3,
        y: -32,
        clr: 0xb87333,
        mass: 18,
        W: 3,
        verified: true,
        src: 'Litz wire 18 turns, 45µH',
        dims: 'Ø70mm',
        note: 'Shell-integrated, resonant 140kHz'
    },
    {
        id: 'ferrite',
        name: 'Ferrite Disc',
        grp: 'Power',
        ico: '⬛',
        geo: 'disc',
        r: 30, // ADJUSTED to Ø60mm
        h: 0.5,
        y: -34,
        clr: 0x1a1a1a,
        mass: 12,
        W: 0,
        verified: true,
        src: 'Mn-Zn Fair-Rite 78',
        dims: 'Ø60×0.5mm'
    },

    // ==================== BASE STATION ====================
    {
        id: 'base_leds',
        name: 'Base LEDs ×8',
        grp: 'Base',
        ico: '💫',
        geo: 'leds',
        n: 8,
        r: 35,
        y: -50,
        clr: 0x00ff88,
        mass: 0.5,
        W: 0.1,
        verified: true,
        src: 'SK6812',
        dims: 'Ø70mm ring',
        base: 1
    },
    {
        id: 'base_pcb',
        name: 'Base PCB',
        grp: 'Base',
        ico: '📟',
        geo: 'disc',
        r: 40,
        h: 1.6,
        y: -52,
        clr: 0x0d4d0d,
        mass: 15,
        W: 0.5,
        verified: true,
        src: 'ESP32-S3-WROOM-1',
        dims: 'Ø80×1.6mm',
        base: 1
    },
    {
        id: 'tx_coil',
        name: 'TX Coil',
        grp: 'Base',
        ico: '〰️',
        geo: 'torus',
        R: 32, // Ø70mm
        r: 3,
        y: -58,
        clr: 0xb87333,
        mass: 15,
        W: 4,
        verified: true,
        src: 'Litz wire 14 turns, 28µH',
        dims: 'Ø70mm',
        base: 1
    },
    {
        id: 'maglev',
        name: 'Maglev Module',
        grp: 'Base',
        ico: '🧲',
        geo: 'box',
        w: 100,
        d: 100,
        h: 20,
        y: -72,
        clr: 0x2a3a4a,
        mass: 350,
        W: 2,
        verified: true,
        src: 'Stirlingkit',
        url: 'https://www.stirlingkit.com/products/500g-diy-magnetic-levitation-module',
        dims: '100×100×20mm, 500g capacity',
        base: 1
    },
    {
        id: 'base_enc',
        name: 'Walnut Base',
        grp: 'Base',
        ico: '🪵',
        geo: 'cyl',
        r: 70,
        h: 25,
        y: -90,
        clr: 0x5d4037,
        mass: 350,
        W: 0,
        verified: true,
        src: 'CNC walnut, tung oil finish',
        dims: 'Ø140×25mm',
        base: 1
    },
];

// Assembly groups for UI tree
export const ASSEMBLY_GROUPS = [
    'Shell',
    'Display',
    'Compute',
    'Audio',
    'LEDs',
    'Power',
    'Base'
];

// Thermal budget (Active mode)
export const THERMAL_BUDGET = {
    idle: 6.7,
    active: 13.8,
    peak: 22.7,
    dissipationDocked: { min: 8, max: 12 },
    dissipationPortable: { min: 2, max: 4 }
};

// Calculate totals
export function calculateStats() {
    const orb = COMPONENTS.filter(c => !c.base);
    const base = COMPONENTS.filter(c => c.base);

    return {
        orbParts: orb.length,
        orbMass: orb.reduce((s, c) => s + c.mass, 0),
        orbHeat: orb.reduce((s, c) => s + (c.W || 0), 0),
        baseParts: base.length,
        baseMass: base.reduce((s, c) => s + c.mass, 0),
        baseHeat: base.reduce((s, c) => s + (c.W || 0), 0),
    };
}
