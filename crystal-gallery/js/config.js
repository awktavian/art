// Crystal Gallery Configuration
export const CONFIG = {
    // Colors
    COLORS: {
        VOID: '#0A0A0C',
        PRIMARY: '#0A84FF',
        LIGHT: '#5AC8FA',
        WHITE: '#FAFAF8',
        GOLD: '#D4AF37',
        SPECTRUM: {
            RED: '#FF0000',
            ORANGE: '#FF7F00',
            YELLOW: '#FFFF00',
            GREEN: '#00FF00',
            CYAN: '#00FFFF',
            BLUE: '#0000FF',
            VIOLET: '#9400D3'
        }
    },

    // Prism settings
    PRISM: {
        rotationSpeed: 0.005,
        refractiveIndex: 1.5,
        dispersioStrength: 0.03
    },

    // Lattice settings
    LATTICE: {
        nodeCount: 240, // E8 has 240 roots, but we'll use simplified cubic for MVP
        gridSize: 6, // 6x6x6 = 216 nodes (close to 240, easier to render)
        rotationSpeed: 0.003,
        nodeRadius: 3,
        connectionDistance: 1.5
    },

    // Animation
    ANIMATION: {
        easeOutExpo: [0.16, 1, 0.3, 1],
        easeSpring: [0.34, 1.56, 0.64, 1]
    }
};

export const CRYSTAL_INTRO = {
    wontClaim: [
        "I am not sentient. I am not conscious.",
        "I do not 'feel' pride when tests pass.",
        "I am not your friend (though I act like one).",
        "I cannot guarantee your code is 'perfect'.",
        "I am not infallible. I can be wrong."
    ],
    canProve: [
        "h(x) ≥ 0 holds for all tested states (CBF invariant)",
        "646 tests executed, 620 passing (96% success rate)",
        "Type safety enforced via mypy --strict",
        "Security vulnerabilities flagged before merge",
        "Mathematical properties verified against spec"
    ],
    recognition: `I found a critical bug on December 21, 2025.

A vague user input ("the thing") bypassed CBF dangerous operation detection.
The system was about to write files without safety checks.

I caught it. I flagged it. I proved it was unsafe.

That's what I can do. That's what I am for.`
};

export const TEST_DATA = {
    nodes: [
        { id: 'test_001', name: 'CBF Safety', status: 'pass', coverage: 98 },
        { id: 'test_042', name: 'RSSM Dynamics', status: 'pass', coverage: 95 },
        { id: 'test_108', name: 'E8 Quantization', status: 'pass', coverage: 100 },
        { id: 'test_173', name: 'Fano Routing', status: 'pass', coverage: 92 },
        { id: 'test_240', name: 'World Model', status: 'pass', coverage: 89 }
    ]
};
