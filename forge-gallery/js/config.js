// ═══════════════════════════════════════════════════════════════════════════
// FORGE GALLERY CONFIGURATION
// ⚒️ e₂ — The Cusp Catastrophe — A₃
// "Every line of code is a hammer strike."
// ═══════════════════════════════════════════════════════════════════════════

export const CONFIG = {
    // Forge palette: molten → steel → iron
    COLORS: {
        MOLTEN: '#FF6B00',
        FORGE_ORANGE: '#FF8C00',
        EMBER: '#FF4500',
        STEEL: '#71797E',
        STEEL_LIGHT: '#A9A9A9',
        IRON: '#434343',
        WHITE_HOT: '#FFFAF0',
        SPARK_YELLOW: '#FFD700',
        COOL_STEEL: '#B0C4DE',
        VOID: '#0A0A0A',
    },
    
    // Anvil settings
    ANVIL: {
        MAX_STRIKES: 100,
        SPARK_COUNT: 30,
        SHAKE_INTENSITY: 5,
        REBOUND_SPEED: 150,
    },
    
    // Cusp catastrophe settings
    CUSP: {
        CANVAS_PADDING: 50,
        LINE_WIDTH: 3,
        ANIMATION_SPEED: 0.015,
        SURFACE_RESOLUTION: 50,
    },
    
    // Foundry settings
    FOUNDRY: {
        MAX_PARTICLES: 200,
        POUR_RATE: 10,
        COOLING_RATE: 5,
        MAX_TEMP: 1500,
        MIN_TEMP: 20,
    },
};

// Metal types for the foundry
export const METAL_TYPES = [
    { name: 'IRON', color: '#434343', meltPoint: 1538 },
    { name: 'STEEL', color: '#71797E', meltPoint: 1370 },
    { name: 'COPPER', color: '#B87333', meltPoint: 1085 },
    { name: 'GOLD', color: '#FFD700', meltPoint: 1064 },
    { name: 'SILVER', color: '#C0C0C0', meltPoint: 962 },
];

// Code snippets for the construct visualization
export const CODE_FRAGMENTS = [
    'function forge(idea) {',
    '  return implement(idea);',
    '}',
    'const build = (spec) => {',
    '  validate(spec);',
    '  construct(spec);',
    '  return artifact;',
    '};',
    'class Builder {',
    '  hammer(code) {}',
    '  temper(tests) {}',
    '  quench(deploy) {}',
    '}',
    'while (!perfect) {',
    '  refine();',
    '  iterate();',
    '}',
];

