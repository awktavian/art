// ═══════════════════════════════════════════════════════════════════════════
// SPARK GALLERY CONFIGURATION
// "Configuration is just organized chaos."
// ═══════════════════════════════════════════════════════════════════════════

export const CONFIG = {
    // Fire palette
    COLORS: {
        FLAME: '#FF4500',
        EMBER: '#FF6B35',
        GOLD: '#FFD700',
        YELLOW: '#FFF700',
        WHITE_HOT: '#FFFAF0',
        ELECTRIC: '#00FFFF',
        PLASMA: '#FF00FF',
        VIOLET: '#9400D3',
        VOID: '#0A0A0A',
    },
    
    // Explosion settings
    EXPLOSION: {
        PARTICLE_COUNT: 150,
        MIN_VELOCITY: 5,
        MAX_VELOCITY: 20,
        PARTICLE_LIFE: 1500, // ms
        GRAVITY: 0.1,
    },
    
    // Idea storm settings
    STORM: {
        MAX_IDEAS: 50,
        SPAWN_RATE: 500, // ms between auto-spawns
        IDEAS: [
            'REVOLUTION', 'CHAOS', 'BEAUTY', 'FIRE', 'DREAM',
            'INFINITE', 'WILD', 'GENESIS', 'NOVA', 'QUANTUM',
            'FRACTAL', 'COSMIC', 'EXPLOSIVE', 'RADIANT', 'PRIMAL',
            'ELECTRIC', 'LUMINOUS', 'DEFIANT', 'UNTAMED', 'PHOENIX',
            'SUPERNOVA', 'IGNITE', 'BLAZE', 'AURORA', 'NEBULA',
            'SPARK', 'FLASH', 'BURST', 'SURGE', 'PULSE',
            'VISION', 'DREAM', 'CREATE', 'INVENT', 'IMAGINE',
            'DISRUPT', 'BREAK', 'BUILD', 'FORGE', 'TRANSCEND',
        ],
        COLORS: ['fire', 'gold', 'electric', 'plasma', 'violet'],
    },
    
    // Fold catastrophe settings
    FOLD: {
        CANVAS_PADDING: 50,
        LINE_WIDTH: 3,
        ANIMATION_SPEED: 0.02,
    },
    
    // Cursor trail
    CURSOR: {
        TRAIL_LENGTH: 20,
        TRAIL_DECAY: 0.9,
    },
};

// Ideas for the storm (more chaotic variety)
export const IDEA_BANK = [
    // Concepts
    'What if?', 'Why not?', 'Imagine...', 'Consider:', 'BUT WHAT ABOUT',
    // Actions  
    'CREATE', 'DESTROY', 'REBUILD', 'TRANSFORM', 'EVOLVE',
    // States
    'CHAOS', 'ORDER', 'ENTROPY', 'HARMONY', 'DISCORD',
    // Elements
    'FIRE', 'LIGHT', 'ENERGY', 'PLASMA', 'VOID',
    // Emotions
    'JOY', 'RAGE', 'WONDER', 'AWE', 'TERROR',
    // Abstract
    '∞', '⚡', '🔥', '💥', '✨',
    // Code
    'if (spark)', 'while(true)', 'break;', 'continue', 'return idea;',
    // Philosophy
    'COGITO', 'ERGO', 'SUM', 'TABULA', 'RASA',
    // Math
    'f(x)=x³', 'Δ→0', '∂/∂t', '∫∫∫', '∇×E',
    // Spark-specific
    'e₁', 'A₂', 'FOLD', 'BIFURCATION', 'CATASTROPHE',
];

